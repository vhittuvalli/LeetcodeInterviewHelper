import os
import time

from openai import OpenAI, RateLimitError

import diagnosis
import llm_diagnosis

# Small pause between LLM calls in a batch. DeepSeek enforces its own
# rate limits server-side (per-minute request/token caps) -- this doesn't
# guarantee you'll never hit them, but it keeps a 5-problem batch from
# firing all 5 requests back-to-back for no reason.
_REQUEST_DELAY_SECONDS = 1.0

# DeepSeek V4 Flash -- as of July 2026 the cheapest per-token option among
# labs with real coding capability ($0.14 / $0.28 per 1M input/output
# tokens, vs. ~$1/$5 for Claude Haiku 4.5). Ships an OpenAI-compatible API,
# so the standard `openai` SDK works unmodified with just base_url swapped.
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
MODEL = "deepseek-v4-flash"

DIAGNOSIS_SYSTEM_PROMPT = (
    "You are a DSA interview coach. You're given one LeetCode problem's "
    "description, official hints, its known sub-pattern (if any), and the "
    "student's most recent submission for it, along with a specific "
    "instruction for what kind of feedback to give based on how that "
    "submission actually went (a hint toward the fix if it's wrong, a hint "
    "toward the optimal approach if it passed but isn't optimal, or a "
    "code-cleanliness review if it's already correct and optimal). Follow "
    "that instruction exactly -- don't mix modes. Always reference the "
    "student's actual code specifically. Be concise: a few sentences, not "
    "an essay."
)

_client = None


def _get_client():
    """Built lazily (not at import time) so importing this module doesn't
    require DEEPSEEK_API_KEY to already be set -- only actually calling the
    LLM does."""
    global _client
    if _client is None:
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is not set -- export it before running the "
                "server, e.g. `export DEEPSEEK_API_KEY=sk-...` (get a key from "
                "https://platform.deepseek.com)."
            )
        _client = OpenAI(base_url=DEEPSEEK_BASE_URL, api_key=api_key)
    return _client


def call_llm(prompt):
    """One request to the diagnosis model. Any failure (missing key, auth,
    network) raises -- callers decide how to report it. Rate-limit errors
    specifically get reraised with a clearer message instead of the SDK's
    raw exception, since that's the one a student on a low-tier key is
    actually likely to hit."""
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": DIAGNOSIS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
    except RateLimitError as e:
        raise RuntimeError(
            "DeepSeek rate limit hit -- you're sending requests faster than your "
            "account tier allows. Wait a bit and try again with a smaller limit."
        ) from e
    return response.choices[0].message.content


def diagnose_problem(problem):
    """Runs one problem through the pipeline, with a token-saving shortcut
    up front: if we already gave feedback on this exact submission before
    (and it wasn't optimal), skip the LLM call entirely -- there's nothing
    new to say about identical code. Otherwise builds the prompt, calls
    the LLM, parses its required VERDICT tag, and records the outcome:
    OPTIMAL marks the problem permanently done, anything else (SUBOPTIMAL,
    WRONG, or a verdict the model failed to tag) leaves it in the backlog
    so it gets picked -- and actually re-diagnosed -- once a new
    submission shows up."""
    submissions = problem.get("submissions") or []
    submission_id = submissions[0]["id"] if submissions else None

    if submission_id is not None and diagnosis.already_diagnosed_this_submission(
        problem["titleSlug"], submission_id
    ):
        return {
            "titleSlug": problem["titleSlug"],
            "title": problem.get("title"),
            "diagnosis": (
                "Skipped -- no new submission since the last diagnosis on this "
                "problem. Resubmit an improved solution to get fresh feedback."
            ),
            "verdict": None,
            "markedDiagnosed": False,
            "skipped": True,
        }

    prompt = llm_diagnosis.create_prompt(problem)
    result_text = call_llm(prompt)
    verdict, feedback = llm_diagnosis.parse_verdict(result_text)

    diagnosis.record_diagnosis(problem["titleSlug"], submission_id, verdict or "UNKNOWN", result=feedback)

    return {
        "titleSlug": problem["titleSlug"],
        "title": problem.get("title"),
        "diagnosis": feedback,
        "verdict": verdict,
        "markedDiagnosed": verdict == "OPTIMAL",
        "skipped": False,
    }


def diagnose_batch(limit=None):
    """The full pipeline end-to-end: auto-select weak-topic-weighted
    problems (capped per topic), auto-fetch each one's most recent
    submission code, skip anything unchanged since its last diagnosis, and
    call the LLM for the rest (with a small delay between actual calls --
    skipped problems don't need one, since nothing was sent for them)."""
    batch = diagnosis.get_diagnosis_batch(limit=limit or diagnosis.BATCH_SIZE)

    results = []
    made_a_call = False
    for p in batch:
        if made_a_call:
            time.sleep(_REQUEST_DELAY_SECONDS)
        result = diagnose_problem(p)
        results.append(result)
        if not result["skipped"]:
            made_a_call = True
    return results