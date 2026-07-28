"""Company mock interview: pick a company, get a problem sampled the way
that company's real interviews actually skew (by difficulty, weighted by
how often each problem has been reported), work it under a countdown, and
get graded on whether you'd plausibly have passed the round.

Deliberately separate from diagnosis.py's backlog tables -- a mock
interview round isn't "diagnose this problem once and mark it done," it's
"grade this specific timed attempt," so nothing here writes to
problem_diagnoses/diagnosis_history. It has its own append-only history
table instead (mock_interview_rounds), logged from evaluate_round() every
time a round actually gets graded. The round itself is still tracked
client-side while it's in progress -- the frontend holds which problem and
when it started, and hands that back to evaluate_round() when the round
ends -- logging only happens at that final step, not while a round is
still live.

single-round mode (num_rounds=1) is what's wired up to the API right now;
select_round_problems() already generalizes to a full multi-round loop for
later without needing to be rewritten.
"""
import random
import time

import company_bank
import db
import leetcode_service
import llm_client
import llm_diagnosis
import recommendations
import submission_history

# 45 minutes -- matches the real-world norm for a single technical round
# (one problem, not several): most interviewers expect a working solution
# with time left over for discussion, not a multi-problem sprint.
ROUND_TIME_SECONDS = 45 * 60

DIFFICULTIES = ["Easy", "Medium", "Hard"]

OUTCOME_LABELS = {
    "strong_pass": "Strong Pass",
    "pass": "Pass",
    "no_pass": "No Pass",
}


class MockInterviewError(Exception):
    """No usable problem data for the request (unknown company, empty
    bank, etc) -- distinct from company_bank.CompanyBankError so routes
    can tell "GitHub is having issues" apart from "there's just nothing
    to pick from for this company"."""
    pass


_slug_to_frontend_id_cache = None


def _slug_to_frontend_id():
    """Company-bank problems only carry a titleSlug, but llm_diagnosis's
    reference lookup (description/hints/sub-pattern) is keyed by
    frontend_id -- this bridges the two datasets. Not every company-tagged
    problem will be in merged_problems.json's ~2900-problem coverage; a
    miss just means create_prompt() falls back to "no reference available"
    and still works, so this doesn't need to be exhaustive."""
    global _slug_to_frontend_id_cache
    if _slug_to_frontend_id_cache is None:
        _slug_to_frontend_id_cache = {
            p["problem_slug"]: p["frontend_id"] for p in recommendations._load_all_problems()
        }
    return _slug_to_frontend_id_cache


def difficulty_mix(company, window="all"):
    """This company's own real difficulty distribution, weighted by how
    often each problem has actually been reported (frequency) rather than
    a hand-picked guess. This is both the answer to "what's the difficulty
    mix" for the UI to show, and exactly what select_round_problems()
    samples from -- so the mix shown is the mix actually used."""
    problems = company_bank.get_company_problems(company, window=window)
    if not problems:
        return {"Easy": 0, "Medium": 0, "Hard": 0}

    totals = {"Easy": 0.0, "Medium": 0.0, "Hard": 0.0}
    for p in problems:
        if p["difficulty"] in totals:
            # Floor so a problem with a 0/near-0 frequency score isn't
            # literally impossible to ever land on -- it just becomes rare.
            totals[p["difficulty"]] += max(p["frequency"], 0.1)

    grand_total = sum(totals.values())
    if grand_total == 0:
        return {"Easy": 0, "Medium": 0, "Hard": 0}

    return {d: round(totals[d] / grand_total * 100) for d in DIFFICULTIES}


def _weighted_choice(problems):
    weights = [max(p["frequency"], 0.1) for p in problems]
    return random.choices(problems, weights=weights, k=1)[0]


def select_round_problems(company, num_rounds=1, window="all", solved_slugs=None):
    """Picks num_rounds problems for this company, one per round, no
    repeats. Each round's difficulty is sampled from the company's own
    weighted distribution (difficulty_mix) first, then a problem is picked
    -- also frequency-weighted -- from within that difficulty tier. That's
    what makes a Google-shaped loop skew harder and an Amazon-shaped one
    skew medium-heavy without hardcoding either company: it falls straight
    out of the dataset instead of a guessed table.

    solved_slugs, if given, steers away from problems already solved on
    LeetCode so a round doesn't hand back something already done --
    falls back to the full pool if that filter would leave nothing."""
    problems = company_bank.get_company_problems(company, window=window)
    if not problems:
        raise MockInterviewError(f"No problem data available for '{company}'")

    solved = set(solved_slugs or [])
    by_difficulty = {d: [p for p in problems if p["difficulty"] == d] for d in DIFFICULTIES}

    mix = difficulty_mix(company, window=window)
    weighted_difficulties = [d for d in DIFFICULTIES if mix.get(d, 0) > 0] or DIFFICULTIES

    slug_map = _slug_to_frontend_id()
    picked = []
    used_slugs = set()

    for _ in range(num_rounds):
        pool_weights = [mix.get(d, 1) or 1 for d in weighted_difficulties]
        difficulty = random.choices(weighted_difficulties, weights=pool_weights, k=1)[0]

        candidates = [p for p in by_difficulty.get(difficulty, []) if p["titleSlug"] not in used_slugs]
        remaining = [p for p in problems if p["titleSlug"] not in used_slugs]

        # Fallback order: unsolved + this difficulty, then unsolved + any
        # difficulty, then (only if truly nothing unsolved is left) allow
        # already-solved problems back in -- same difficulty first, then
        # any. This way a solved problem only ever gets picked as a last
        # resort, never ahead of an unsolved alternative in another tier.
        fresh = (
            [p for p in candidates if p["titleSlug"] not in solved]
            or [p for p in remaining if p["titleSlug"] not in solved]
            or candidates
            or remaining
        )

        if not fresh:
            break  # genuinely out of problems for this company

        chosen = _weighted_choice(fresh)
        used_slugs.add(chosen["titleSlug"])
        picked.append({
            "titleSlug": chosen["titleSlug"],
            "title": chosen["title"],
            "difficulty": chosen["difficulty"],
            "frontendId": slug_map.get(chosen["titleSlug"]),
            "topics": chosen["topics"],
        })

    return picked


# Real onsite loops researched at 3-5 separate rounds -- capped at 6 here
# mostly to keep a single sitting from ballooning past what anyone would
# actually do in one go (6 rounds x 45 min is already a 4.5-hour session).
MAX_LOOP_ROUNDS = 6


def _best_effort_solved_slugs():
    """Used to steer round selection away from problems you've already
    solved. Best-effort on purpose: if fetching your solved list fails for
    any reason (auth hiccup, LeetCode flakiness), that filter is just
    skipped rather than blocking the round entirely."""
    try:
        return {p["titleSlug"] for p in leetcode_service.fetch_solved()}
    except Exception:
        return set()


def start_round(company, window="all"):
    """Single-round mode's entry point: picks one problem for this
    company and starts the clock."""
    picked = select_round_problems(
        company, num_rounds=1, window=window, solved_slugs=_best_effort_solved_slugs()
    )
    if not picked:
        raise MockInterviewError(f"Couldn't find an eligible problem for '{company}'")

    return {
        "problem": picked[0],
        "difficultyMix": difficulty_mix(company, window=window),
        "timeLimitSeconds": ROUND_TIME_SECONDS,
        "startedAt": int(time.time()),
    }


def start_loop(company, num_rounds, window="all"):
    """Multi-round mode's entry point: picks num_rounds non-repeating
    problems for this company in one shot (via select_round_problems,
    which single-round mode already uses with num_rounds=1) so the whole
    loop is decided upfront -- no risk of round 3 accidentally repeating
    round 1's problem.

    Deliberately does NOT stamp a startedAt here the way start_round()
    does: a loop's rounds happen one at a time, often with a pause between
    them while the frontend shows that round's result, so each round's
    clock should start when the candidate actually begins THAT round, not
    when the whole loop was requested. The frontend captures its own
    "now" the moment it displays each round and sends that to
    evaluate_round() -- same value start_round() would have stamped
    anyway, just captured at the moment it's actually needed."""
    num_rounds = max(1, min(int(num_rounds), MAX_LOOP_ROUNDS))

    picked = select_round_problems(
        company, num_rounds=num_rounds, window=window, solved_slugs=_best_effort_solved_slugs()
    )
    if not picked:
        raise MockInterviewError(f"Couldn't find eligible problems for '{company}'")

    return {
        "problems": picked,
        "difficultyMix": difficulty_mix(company, window=window),
        "timeLimitSeconds": ROUND_TIME_SECONDS,
    }


def _log_round(company, problem, started_at, result):
    """Append-only log of a graded round, feeding both a future "your
    performance over time" view and (later) excluding recently-seen
    problems from being picked again. Best-effort on purpose -- a logging
    hiccup shouldn't stop the actual result from reaching the user, so
    any failure here is swallowed rather than raised. Skipped entirely if
    no company was given (keeps evaluate_round callable without logging,
    e.g. from a script or a future caller that doesn't track a company)."""
    if not company:
        return
    try:
        db.record_mock_interview_round(
            db.get_default_user_id(),
            company=company,
            title_slug=problem["titleSlug"],
            title=problem.get("title") or problem["titleSlug"],
            difficulty=problem.get("difficulty") or "Unknown",
            outcome=result["outcome"],
            verdict=result["verdict"],
            within_time=result["withinTime"],
            time_taken_seconds=result["timeTakenSeconds"],
            started_at=started_at,
        )
    except Exception:
        pass


def evaluate_round(problem, started_at, time_limit_seconds=ROUND_TIME_SECONDS, company=None):
    """Grades one finished (or timed-out) round. `problem` is the dict
    start_round()/start_loop() returned; `started_at` is the unix
    timestamp the frontend captured when this specific round began.
    `company` is optional but should be passed whenever it's known -- it's
    what gets logged to mock_interview_rounds; without it, this still
    grades the round correctly, it just doesn't get recorded to history.

    Always re-fetches the latest submission fresh from LeetCode
    (force_refresh=True) instead of trusting any cache -- a cached
    submission from before the round even started would otherwise make an
    unsolved round look solved. A submission timestamped before started_at
    is treated the same as no submission: it's leftover from some earlier
    session, not evidence you solved it during this round.

    Only calls the LLM if there's actually a submission worth grading --
    same one-call cost as a single diagnosis card, and nothing is spent if
    nothing was ever submitted.

    Outcome is three-tier, not binary, because that's closer to how real
    interviews are actually debriefed:
      - "strong_pass": accepted within time, and the solution is optimal
      - "pass": accepted within time, but not the optimal approach --
        real interviews often still pass this if you communicated well
      - "no_pass": not accepted, not within time, or nothing submitted
    Feedback is still shown even on a "no_pass" caused only by running
    over time, since the code itself might still be worth learning from."""
    title_slug = problem["titleSlug"]
    deadline = started_at + time_limit_seconds

    history = submission_history.get_submission_history(title_slug, force_refresh=True)
    submission = history[0] if history else None

    if submission is None or submission["timestamp"] < started_at:
        result = {
            "outcome": "no_pass",
            "outcomeLabel": OUTCOME_LABELS["no_pass"],
            "solved": False,
            "withinTime": False,
            "verdict": None,
            "feedback": "No submission was found for this round -- nothing was submitted before evaluating.",
            "timeTakenSeconds": None,
        }
        _log_round(company, problem, started_at, result)
        return result

    within_time = submission["timestamp"] <= deadline
    time_taken = submission["timestamp"] - started_at

    prompt_problem = {
        "frontendId": problem.get("frontendId"),
        "title": problem.get("title"),
        "titleSlug": title_slug,
        "difficulty": problem.get("difficulty"),
        "submissions": [submission],
    }
    response_text = llm_client.call_llm(llm_diagnosis.create_prompt(prompt_problem))
    verdict, feedback = llm_diagnosis.parse_verdict(response_text)

    accepted = submission["status"] == "Accepted"

    if not accepted or not within_time:
        outcome = "no_pass"
    elif verdict == "OPTIMAL":
        outcome = "strong_pass"
    else:  # SUBOPTIMAL, or a verdict the model didn't tag cleanly -- same
        # safe-default reasoning diagnosis.py uses: don't overclaim.
        outcome = "pass"

    result = {
        "outcome": outcome,
        "outcomeLabel": OUTCOME_LABELS[outcome],
        "solved": accepted,
        "withinTime": within_time,
        "verdict": verdict,
        "feedback": feedback,
        "timeTakenSeconds": time_taken,
    }
    _log_round(company, problem, started_at, result)
    return result