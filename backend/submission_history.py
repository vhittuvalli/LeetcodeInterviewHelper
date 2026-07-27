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


def _select_important(submissions):
    """Cuts a problem's full submission list down to the ones that actually
    matter for diagnosis, instead of pulling code for every single attempt:

    - the very first attempt ever made on this problem (shows the original approach)
    - the last failed attempt right before it passed (shows the mistake that got fixed)
    - the accepted submission (the final working solution)

    That's at most 3 code pulls per problem no matter how many times you
    actually attempted it -- someone who needed 15 tries and someone who
    needed 2 both end up with the same-shaped, small bundle."""
    if not submissions:
        return []

    # Sort newest -> oldest by timestamp so we don't depend on whatever
    # order the API happens to return them in.
    newest_first = sorted(submissions, key=lambda s: s["timestamp"], reverse=True)
    oldest_first = list(reversed(newest_first))

    first_attempt = oldest_first[0]

    # The FIRST time it was accepted, not the most recent -- if they revisited
    # an already-solved problem later, that revisit isn't the interesting part.
    accepted = next((s for s in oldest_first if s["statusDisplay"] == "Accepted"), None)

    last_failed_before_accept = None
    if accepted:
        for s in newest_first:
            if s["id"] == accepted["id"]:
                continue
            if s["timestamp"] < accepted["timestamp"]:
                last_failed_before_accept = s
                break  # newest_first order -> first match here is the most recent failure

    important = []
    seen_ids = set()
    for s in (first_attempt, last_failed_before_accept, accepted):
        if s is not None and s["id"] not in seen_ids:
            important.append(s)
            seen_ids.add(s["id"])

    return important


def get_submission_history(title_slug, force_refresh=False):
    """Returns the important submissions (with code) for one problem.
    Cached to disk so repeat calls -- e.g. re-running diagnosis on the same
    problem later -- don't re-hit LeetCode for data that won't change.
    Pass force_refresh=True to bypass the cache (e.g. if you resubmit after
    getting a diagnosis and want the new attempt reflected).

    Each entry in the returned list: id, status, lang, timestamp, code.
    """
    state = _load_state()

    if not force_refresh and title_slug in state:
        return state[title_slug]

    all_submissions = leetcode_service.fetch_submission_list(title_slug)
    important = _select_important(all_submissions)

    history = []
    for s in important:
        detail = leetcode_service.fetch_submission_code(s["id"])
        history.append({
            "id": s["id"],
            "status": s["statusDisplay"],
            "lang": s["lang"],
            "timestamp": s["timestamp"],
            "code": detail.get("code", ""),
        })

    state[title_slug] = history
    _save_state(state)
    return history