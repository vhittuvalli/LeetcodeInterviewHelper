import json
import os

import leetcode_service

STATE_FILE = os.path.join(os.path.dirname(__file__), "submission_history.json")


def _load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def _save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_submission_history(title_slug, force_refresh=False):
    """Just the most recent submission for one problem, with code -- one
    LeetCode call to find it (fetch_latest_submission) and one to pull its
    code (fetch_submission_code), instead of the full first-attempt/last-
    failure/accepted bundle. Cheaper on both ends: fewer LeetCode requests,
    and a smaller prompt means fewer LLM tokens per diagnosis.

    Still returns a list (of 0 or 1 items) to keep the shape the rest of
    the pipeline (diagnosis.py, llm_diagnosis.py) already expects.
    Cached to disk so repeat calls don't re-hit LeetCode."""
    state = _load_state()

    if not force_refresh and title_slug in state:
        return state[title_slug]

    latest = leetcode_service.fetch_latest_submission(title_slug)
    if latest is None:
        state[title_slug] = []
        _save_state(state)
        return []

    detail = leetcode_service.fetch_submission_code(latest["id"])
    history = [{
        "id": latest["id"],
        "status": latest["statusDisplay"],
        "lang": latest["lang"],
        "timestamp": latest["timestamp"],
        "code": detail.get("code", ""),
    }]

    state[title_slug] = history
    _save_state(state)
    return history