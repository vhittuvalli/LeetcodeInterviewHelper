import json
import os
import random
from datetime import date

# Simple local-file persistence -- same "placeholder until there's a real
# database" tradeoff as the in-memory credential store: fine for one user,
# survives server restarts (unlike the in-memory credentials), but won't
# scale to multiple users without being swapped out later.
STATE_FILE = os.path.join(os.path.dirname(__file__), "spaced_repetition_state.json")


def _load_state():
    if not os.path.exists(STATE_FILE):
        return {"reviewed": [], "current": None}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def _save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _pick_problem(candidates, neetcode_slugs):
    """Favor NeetCode 150 problems first -- only fall back to the rest of
    the solved list once every NeetCode 150 problem has already been
    reviewed at least once."""
    neetcode_candidates = [p for p in candidates if p["titleSlug"] in neetcode_slugs]
    pool = neetcode_candidates if neetcode_candidates else candidates
    return random.choice(pool)


def get_todays_problem(solved_problems, neetcode_slugs):
    state = _load_state()
    today = date.today().isoformat()

    # Already picked something for today and it hasn't been marked done yet --
    # keep returning the same one instead of re-rolling on every page refresh.
    if state["current"] and state["current"]["date"] == today:
        slug = state["current"]["slug"]
        match = next((p for p in solved_problems if p["titleSlug"] == slug), None)
        if match:
            return {
                "problem": match,
                "isNeetcode150": slug in neetcode_slugs,
                "reviewedCount": len(state["reviewed"]),
                "totalSolved": len(solved_problems),
            }
        # If that problem vanished from the solved list somehow, fall
        # through and pick a fresh one instead of erroring.

    reviewed = set(state["reviewed"])
    candidates = [p for p in solved_problems if p["titleSlug"] not in reviewed]

    if not candidates and solved_problems:
        # Everything's been reviewed at least once -- start a new cycle
        # rather than returning nothing forever.
        reviewed = set()
        candidates = solved_problems

    if not candidates:
        return None  # nothing solved yet at all

    chosen = _pick_problem(candidates, neetcode_slugs)

    state["reviewed"] = list(reviewed)
    state["current"] = {"date": today, "slug": chosen["titleSlug"]}
    _save_state(state)

    return {
        "problem": chosen,
        "isNeetcode150": chosen["titleSlug"] in neetcode_slugs,
        "reviewedCount": len(state["reviewed"]),
        "totalSolved": len(solved_problems),
    }


def mark_reviewed(slug):
    state = _load_state()
    reviewed = set(state["reviewed"])
    reviewed.add(slug)
    state["reviewed"] = list(reviewed)
    # Clear "current" so the next request picks something fresh instead of
    # waiting until tomorrow -- lets someone review more than one a day if
    # they want to.
    state["current"] = None
    _save_state(state)
    return {"reviewedCount": len(state["reviewed"])}