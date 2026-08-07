import json
import os
from collections import defaultdict

import leetcode_service

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "merged_problems.json")

MIN_SOLVED_FOR_RANKING = 3

DIFFICULTY_GAP_WEIGHT = 1.5
ATTEMPTED_UNSOLVED_WEIGHT = 2.0

HARDER_DIFFICULTIES = ["Medium", "Hard"]
DIFFICULTY_ORDER = {"Easy": 0, "Medium": 1, "Hard": 2}


def _load_all_problems():
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    return data["questions"]


def _topic_for_dataset_problem(problem, neetcode_map):
    normalized = {
        "titleSlug": problem["problem_slug"],
        "topicTags": [{"name": t} for t in problem.get("topics", [])],
    }
    return leetcode_service.primary_topic(normalized, neetcode_map)


def _group_by_topic(problems, neetcode_map):
    by_topic = defaultdict(list)
    for p in problems:
        topic = leetcode_service.primary_topic(p, neetcode_map)
        by_topic[topic].append(p)
    return by_topic


def _rank_weak_topics(solved_problems, attempted_problems, neetcode_map):
    solved_by_topic = _group_by_topic(solved_problems, neetcode_map)
    attempted_by_topic = _group_by_topic(attempted_problems, neetcode_map)

    all_topics = set(solved_by_topic) | set(attempted_by_topic)

    scores = {}
    for topic in all_topics:
        solved = solved_by_topic.get(topic, [])
        attempted = attempted_by_topic.get(topic, [])

        has_enough_solved_data = len(solved) >= MIN_SOLVED_FOR_RANKING
        has_stuck_attempts = len(attempted) > 0

        if not has_enough_solved_data and not has_stuck_attempts:
            continue

        avg_submissions = 0
        missing = []
        if has_enough_solved_data:
            avg_submissions = sum(p.get("numSubmitted", 1) or 1 for p in solved) / len(solved)
            difficulties_seen = {p["difficulty"] for p in solved}
            missing = [d for d in HARDER_DIFFICULTIES if d not in difficulties_seen]

        weakness_score = (
            avg_submissions
            + len(missing) * DIFFICULTY_GAP_WEIGHT
            + len(attempted) * ATTEMPTED_UNSOLVED_WEIGHT
        )

        scores[topic] = {
            "avgSubmissions": round(avg_submissions, 2),
            "missingDifficulties": missing,
            "attemptedUnsolvedCount": len(attempted),
            "attemptedUnsolved": [
                {
                    "frontendId": p["frontendId"],
                    "title": p["title"],
                    "titleSlug": p["titleSlug"],
                    "difficulty": p["difficulty"],
                }
                for p in attempted
            ],
            "weaknessScore": round(weakness_score, 2),
        }

    return dict(sorted(scores.items(), key=lambda kv: kv[1]["weaknessScore"], reverse=True))


def _index_candidates_by_topic(all_problems, solved_slugs, neetcode_slugs, neetcode_map):
    """Every dataset problem that's unsolved and not part of the NeetCode 150
    track, bucketed by topic -- computed once, not per weak topic."""
    by_topic = defaultdict(list)
    for p in all_problems:
        slug = p["problem_slug"]
        if slug in solved_slugs or slug in neetcode_slugs:
            continue
        topic = _topic_for_dataset_problem(p, neetcode_map)
        by_topic[topic].append(p)
    return by_topic


def _explain(info):
    parts = []
    if info["attemptedUnsolvedCount"] > 0:
        parts.append(f"{info['attemptedUnsolvedCount']} attempted but never solved")
    if info["avgSubmissions"] > 1.5:
        parts.append(f"averaging {info['avgSubmissions']} submissions per solved problem")
    if info["missingDifficulties"]:
        parts.append(f"no solved {'/'.join(info['missingDifficulties'])} problems yet")
    return "; ".join(parts) if parts else "lower relative mastery"


def get_recommendations(user_id, limit=5):
    solved_problems = leetcode_service.fetch_solved(user_id)
    attempted_problems = leetcode_service.fetch_attempted(user_id)
    neetcode_map = leetcode_service.load_neetcode_map()
    all_problems = _load_all_problems()

    solved_slugs = {p["titleSlug"] for p in solved_problems}
    neetcode_slugs = set(neetcode_map.keys())

    weak_topics = _rank_weak_topics(solved_problems, attempted_problems, neetcode_map)
    if not weak_topics:
        return {"weakTopics": {}, "recommendations": []}

    candidates_by_topic = _index_candidates_by_topic(all_problems, solved_slugs, neetcode_slugs, neetcode_map)

    recommendations = []
    for topic, info in weak_topics.items():
        if info["attemptedUnsolved"]:
            recommendations.append({
                "topic": topic,
                "weaknessScore": info["weaknessScore"],
                "reason": _explain(info),
                "problem": info["attemptedUnsolved"][0],
                "isRetry": True,
            })
            if len(recommendations) >= limit:
                break
            continue

        candidates = candidates_by_topic.get(topic, [])
        if not candidates:
            continue

        gap = set(info["missingDifficulties"])
        if gap:
            candidates = sorted(candidates, key=lambda p: 0 if p["difficulty"] in gap else 1)
        else:
            candidates = sorted(candidates, key=lambda p: DIFFICULTY_ORDER.get(p["difficulty"], 3))

        pick = candidates[0]
        recommendations.append({
            "topic": topic,
            "weaknessScore": info["weaknessScore"],
            "reason": _explain(info),
            "problem": {
                "frontendId": pick["frontend_id"],
                "title": pick["title"],
                "titleSlug": pick["problem_slug"],
                "difficulty": pick["difficulty"],
            },
            "isRetry": False,
        })

        if len(recommendations) >= limit:
            break

    return {"weakTopics": weak_topics, "recommendations": recommendations}