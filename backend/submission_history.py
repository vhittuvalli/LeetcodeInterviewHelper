import db
import leetcode_service


def get_submission_history(title_slug, force_refresh=False):
    """Just the most recent submission for one problem, with code -- one
    LeetCode call to find it (fetch_latest_submission) and one to pull its
    code (fetch_submission_code), instead of the full first-attempt/last-
    failure/accepted bundle. Cheaper on both ends: fewer LeetCode requests,
    and a smaller prompt means fewer LLM tokens per diagnosis.

    Still returns a list (of 0 or 1 items) to keep the shape the rest of
    the pipeline (diagnosis.py, llm_diagnosis.py) already expects. Cached
    in submission_cache so repeat calls don't re-hit LeetCode -- note this
    means "no submission found last time" isn't itself cached (unlike the
    old JSON version), so a problem that had nothing on record will retry
    LeetCode on every call until it actually finds something. That's a
    minor tradeoff worth knowing about, not a bug: it's cheap (one list
    call) and self-correcting once a submission actually exists."""
    user_id = db.get_default_user_id()

    if not force_refresh:
        cached = db.get_cached_submission(user_id, title_slug)
        if cached is not None:
            return [cached]

    latest = leetcode_service.fetch_latest_submission(title_slug)
    if latest is None:
        return []

    detail = leetcode_service.fetch_submission_code(latest["id"])
    submission = {
        "id": latest["id"],
        "status": latest["statusDisplay"],
        "lang": latest["lang"],
        "timestamp": latest["timestamp"],
        "code": detail.get("code", ""),
    }

    db.upsert_cached_submission(user_id, title_slug, submission)
    return [submission]