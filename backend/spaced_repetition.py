import random
from datetime import date

import db


def _pick_problem(candidates, neetcode_slugs):
    """Favor NeetCode 150 problems first -- only fall back to the rest of
    the solved list once every NeetCode 150 problem has already been
    reviewed at least once."""
    neetcode_candidates = [p for p in candidates if p["titleSlug"] in neetcode_slugs]
    pool = neetcode_candidates if neetcode_candidates else candidates
    return random.choice(pool)


def get_todays_problem(user_id, solved_problems, neetcode_slugs):
    today = date.today()

    # Already picked something for today and it hasn't been marked done yet --
    # keep returning the same one instead of re-rolling on every page refresh.
    current = db.get_current_pick(user_id, today)
    if current:
        slug = current["titleSlug"]
        match = next((p for p in solved_problems if p["titleSlug"] == slug), None)
        if match:
            reviewed = db.get_reviewed_slugs(user_id)
            return {
                "problem": match,
                "isNeetcode150": slug in neetcode_slugs,
                "reviewedCount": len(reviewed),
                "totalSolved": len(solved_problems),
            }
        # If that problem vanished from the solved list somehow, fall
        # through and pick a fresh one instead of erroring. The stale
        # today-row stays in the table (harmless, still unreviewed) but a
        # newer row inserted below takes over as "current" since
        # get_current_pick() always returns the most recent one.

    reviewed = db.get_reviewed_slugs(user_id)
    candidates = [p for p in solved_problems if p["titleSlug"] not in reviewed]

    if not candidates and solved_problems:
        # Everything's been reviewed at least once. The old JSON version
        # wiped review history back to zero here to start a "new cycle" --
        # the DB keeps full history instead (that's the point of making
        # this table append-only), so this just means every solved problem
        # is eligible again, and reviewedCount below still honestly shows
        # everything you've actually reviewed rather than resetting to 0.
        candidates = solved_problems

    if not candidates:
        return None  # nothing solved yet at all

    chosen = _pick_problem(candidates, neetcode_slugs)
    db.assign_problem(user_id, chosen["titleSlug"], today)

    return {
        "problem": chosen,
        "isNeetcode150": chosen["titleSlug"] in neetcode_slugs,
        "reviewedCount": len(reviewed),
        "totalSolved": len(solved_problems),
    }


def mark_reviewed(user_id, slug):
    today = date.today()
    db.mark_reviewed(user_id, slug, today)
    reviewed = db.get_reviewed_slugs(user_id)
    return {"reviewedCount": len(reviewed)}