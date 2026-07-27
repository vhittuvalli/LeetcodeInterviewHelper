import json
import os
from collections import defaultdict

import leetcode_service
import recommendations

STATE_FILE = os.path.join(os.path.dirname(__file__), "diagnosis_state.json")

BATCH_SIZE = 5

# Cap on how many picks can come from the same topic -- without this, a
# single very-weak topic (e.g. Stack) could fill the entire batch, and
# you'd never see a diagnosis from anywhere else.
MAX_PER_TOPIC = 2


def _load_state():
    if not os.path.exists(STATE_FILE):
        return {"diagnosed": [], "history": []}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def _save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _pick_score(problem, weak_topics, neetcode_map):
    """How much a problem is a struggle (its own numSubmitted) plus a bonus
    if it falls in a topic already flagged weak -- so a problem can still
    surface on its own merit even in an otherwise-strong topic, but gets
    boosted when both signals agree."""
    topic = leetcode_service.primary_topic(problem, neetcode_map)
    num_submitted = problem.get("numSubmitted", 1) or 1
    weakness_bonus = weak_topics.get(topic, {}).get("weaknessScore", 0)
    return num_submitted + weakness_bonus


def select_problems_to_diagnose(limit=BATCH_SIZE, max_per_topic=MAX_PER_TOPIC):
    """Returns up to `limit` solved problems worth running an LLM diagnosis
    on next -- highest pick_score first, excluding anything already
    diagnosed in a previous call, and capped at `max_per_topic` picks from
    any single topic so the batch stays spread out instead of being
    dominated by whichever topic happens to be weakest. No date/schedule
    logic: this is a backlog, not a daily cache -- call it whenever, it
    just returns what's new."""
    state = _load_state()
    diagnosed_slugs = set(state["diagnosed"])

    solved_problems = leetcode_service.fetch_solved()
    attempted_problems = leetcode_service.fetch_attempted()
    neetcode_map = leetcode_service.load_neetcode_map()

    weak_topics = recommendations._rank_weak_topics(solved_problems, attempted_problems, neetcode_map)

    backlog = [p for p in solved_problems if p["titleSlug"] not in diagnosed_slugs]
    if not backlog:
        return []

    scored = [(p, _pick_score(p, weak_topics, neetcode_map)) for p in backlog]
    # Highest score first; tiebreak by most recently submitted.
    scored.sort(key=lambda pair: (pair[1], pair[0].get("lastSubmittedAt") or 0), reverse=True)

    selected = []
    topic_counts = defaultdict(int)
    for p, _score in scored:
        if len(selected) >= limit:
            break
        topic = leetcode_service.primary_topic(p, neetcode_map)
        if topic_counts[topic] >= max_per_topic:
            continue  # this topic already has its 2 -- move on to the next best pick
        selected.append(p)
        topic_counts[topic] += 1

    return selected


def mark_diagnosed(titleSlug, result=None):
    """Call once a problem has actually been run through the (not-yet-built)
    LLM diagnosis step, so it drops out of future backlogs."""
    state = _load_state()
    if titleSlug not in state["diagnosed"]:
        state["diagnosed"].append(titleSlug)
    if result is not None:
        state["history"].append({"titleSlug": titleSlug, "result": result})
    _save_state(state)