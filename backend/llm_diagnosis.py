import json
import os

import recommendations

SUBPATTERNS_FILE = os.path.join(os.path.dirname(__file__), "data", "subpatterns.json")

# Both of these are expensive to build (94-pattern JSON parse / 2900-problem
# scan) but never change during a run, so cache them the first time each is
# needed instead of redoing the work on every prompt.
_subpatterns_cache = None
_problem_index_cache = None


def _load_subpatterns():
    global _subpatterns_cache
    if _subpatterns_cache is None:
        with open(SUBPATTERNS_FILE, "r") as f:
            _subpatterns_cache = json.load(f)
    return _subpatterns_cache


def _load_problem_index():
    """frontend_id (str) -> full problem dict from merged_problems.json,
    built once instead of scanning the ~2900-problem list on every lookup."""
    global _problem_index_cache
    if _problem_index_cache is None:
        _problem_index_cache = {
            str(p["frontend_id"]): p for p in recommendations._load_all_problems()
        }
    return _problem_index_cache


def get_subpatterns(frontend_id):
    """Named technique(s) this problem falls under in the 94-pattern sheet --
    finer-grained than the topic (e.g. 'Converging' instead of just 'Two
    Pointers'). A problem can have more than one if it's solvable multiple
    ways. Returns [] if the sheet doesn't cover this problem."""
    data = _load_subpatterns()
    return data["problem_to_patterns"].get(str(frontend_id), [])


def get_problem_reference(frontend_id):
    """Description/hints/topics for a problem from merged_problems.json, or
    None if it's not in that dataset (it covers ~2900 of LeetCode's
    problems, not all of them)."""
    return _load_problem_index().get(str(frontend_id))


def _format_submissions(submissions):
    if not submissions:
        return "(no submission code available for this problem)"

    parts = []
    for s in submissions:
        parts.append(f"--- {s['status']} ({s['lang']}) ---\n{s['code']}")
    return "\n\n".join(parts)


def create_prompt(problem):
    """Builds the full diagnosis prompt for one problem -- takes an entry
    from diagnosis.get_diagnosis_batch() (title/difficulty/titleSlug/
    frontendId/submissions) and pulls in everything else needed to actually
    diagnose it:
      - the problem's own description + official hints (from merged_problems.json)
      - its named sub-pattern(s) from the 94-pattern sheet, if it's covered
      - its important submission code (first attempt, last failure, accepted)
    No LLM call happens here -- this only assembles the text that would be sent."""
    frontend_id = problem.get("frontendId")
    reference = get_problem_reference(frontend_id)
    subpatterns = get_subpatterns(frontend_id)

    lines = [f"Problem: {frontend_id}. {problem.get('title')} ({problem.get('difficulty')})"]

    if reference:
        topics = reference.get("topics") or []
        if topics:
            lines.append(f"Topics: {', '.join(topics)}")
        if reference.get("description"):
            lines.append(f"\nDescription:\n{reference['description']}")
        hints = reference.get("hints") or []
        if hints:
            lines.append("\nOfficial hints:")
            lines.extend(f"- {h}" for h in hints)
    else:
        lines.append("(no reference description available for this problem)")

    if subpatterns:
        lines.append(f"\nKnown sub-pattern(s) this problem falls under: {', '.join(subpatterns)}")
    else:
        lines.append("\nNo specific sub-pattern on file for this problem -- diagnose from the code alone.")

    lines.append("\nSubmission history (oldest to newest):")
    lines.append(_format_submissions(problem.get("submissions", [])))

    lines.append(
        "\nBased on the above, identify the specific sub-pattern or technique this student "
        "struggled with, and explain concretely what changed between their failed attempt(s) "
        "and the accepted solution. Also compare their solutions to the MOST optimal solution that you know of for that problem. Provide EXTREMELY detailed information about what the code could improve on. (Ex: YOu could improve on the duplicate checking process for the right and left pointers for 3 sum)"
    )

    return "\n".join(lines)


def build_prompts(batch):
    """Runs create_prompt() over a whole diagnosis.get_diagnosis_batch()
    result. Returns a list of {titleSlug, title, prompt} -- ready to hand to
    an LLM call once that part is built."""
    return [
        {
            "titleSlug": p["titleSlug"],
            "title": p.get("title"),
            "prompt": create_prompt(p),
        }
        for p in batch
    ]