from collections import defaultdict

import db
import leetcode_service
import recommendations
import submission_history

BATCH_SIZE = 5

MAX_PER_TOPIC = 2


def _pick_score(problem, weak_topics, neetcode_map):
    """How much a problem is a struggle (its own numSubmitted) plus a bonus
    if it falls in a topic already flagged weak -- so a problem can still
    surface on its own merit even in an otherwise-strong topic, but gets
    boosted when both signals agree."""
    topic = leetcode_service.primary_topic(problem, neetcode_map)
    num_submitted = problem.get("numSubmitted", 1) or 1
    weakness_bonus = weak_topics.get(topic, {}).get("weaknessScore", 0)
    return num_submitted + weakness_bonus


def select_problems_to_diagnose(user_id, limit=BATCH_SIZE, max_per_topic=MAX_PER_TOPIC):
    """Returns up to `limit` solved problems worth running an LLM diagnosis
    on next -- highest pick_score first, excluding anything already
    diagnosed in a previous call, and capped at `max_per_topic` picks from
    any single topic so the batch stays spread out instead of being
    dominated by whichever topic happens to be weakest. No date/schedule
    logic: this is a backlog, not a daily cache -- call it whenever, it
    just returns what's new."""
    diagnosed_slugs = db.get_diagnosed_slugs(user_id)

    solved_problems = leetcode_service.fetch_solved(user_id)
    attempted_problems = leetcode_service.fetch_attempted(user_id)
    neetcode_map = leetcode_service.load_neetcode_map()

    weak_topics = recommendations._rank_weak_topics(solved_problems, attempted_problems, neetcode_map)

    backlog = [p for p in solved_problems if p["titleSlug"] not in diagnosed_slugs]
    if not backlog:
        return []

    scored = [(p, _pick_score(p, weak_topics, neetcode_map)) for p in backlog]
    scored.sort(key=lambda pair: (pair[1], pair[0].get("lastSubmittedAt") or 0), reverse=True)

    selected = []
    topic_counts = defaultdict(int)
    for p, _score in scored:
        if len(selected) >= limit:
            break
        topic = leetcode_service.primary_topic(p, neetcode_map)
        if topic_counts[topic] >= max_per_topic:
            continue
        selected.append(p)
        topic_counts[topic] += 1

    return selected


def get_diagnosis_batch(user_id, limit=BATCH_SIZE, max_per_topic=MAX_PER_TOPIC):
    """The full pipeline in one call, nothing to type in by hand:
    1. select_problems_to_diagnose() auto-picks which solved problems are
       worth analyzing, weighted toward weak topics and capped per topic.
    2. For each one, submission_history.get_submission_history() auto-fetches
       its most recent submission's code (just the one, to keep LeetCode
       calls and LLM tokens down).
    Returns a list ready to hand to an LLM later -- problem info + the code
    for each pick."""
    picked = select_problems_to_diagnose(user_id, limit=limit, max_per_topic=max_per_topic)

    batch = []
    for p in picked:
        history = submission_history.get_submission_history(user_id, p["titleSlug"])
        batch.append({
            "frontendId": p.get("frontendId"),
            "title": p.get("title"),
            "titleSlug": p["titleSlug"],
            "difficulty": p.get("difficulty"),
            "numSubmitted": p.get("numSubmitted"),
            "submissions": history,
        })
    return batch


def record_diagnosis(user_id, titleSlug, submission_id, verdict, result=None):
    """Call once an LLM diagnosis actually comes back for a problem.
    Only an OPTIMAL verdict marks the problem permanently done -- WRONG,
    SUBOPTIMAL, and anything the model didn't tag cleanly all leave it in
    the backlog so it keeps getting picked (and re-diagnosed) until an
    actual better submission shows up. That's the point: it keeps nudging
    you back to unfinished problems instead of letting them quietly drop
    off once you've gotten one round of feedback.

    Also remembers which submission_id this verdict was about, so
    already_diagnosed_this_submission() can tell "still the same code,
    skip re-diagnosing it" apart from "they resubmitted, diagnose it
    again" without spending another LLM call to find out."""
    db.record_diagnosis(user_id, titleSlug, submission_id, verdict, result=result)


def already_diagnosed_this_submission(user_id, titleSlug, submission_id):
    """True if the last diagnosis on this problem was about this exact
    submission and it wasn't OPTIMAL (if it had been, the problem would be
    in "diagnosed" and wouldn't be selected again at all). Callers use this
    to skip the LLM call entirely when nothing has changed since last time
    -- there's nothing new to say about identical code, so don't pay for it."""
    pending = db.get_pending_diagnosis(user_id, titleSlug)
    return pending is not None and pending.get("submissionId") == submission_id