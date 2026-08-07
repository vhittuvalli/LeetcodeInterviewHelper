import json
import os
import re

import recommendations

_VERDICT_RE = re.compile(r"^\s*VERDICT:\s*(OPTIMAL|SUBOPTIMAL|WRONG)\s*\n?", re.IGNORECASE)

SUBPATTERNS_FILE = os.path.join(os.path.dirname(__file__), "data", "subpatterns.json")

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


_VERDICT_LINE = (
    "\nStart your reply with exactly one tag on its own first line -- {options} -- "
    "then a blank line, then your feedback. The tag drives whether this problem "
    "gets marked done or stays in the backlog for another round, so it must "
    "match your actual judgment."
)


def _diagnosis_instructions(status):
    if status is None:
        return (
            "\nNo submission code is available for this problem, so diagnose "
            "from the description, hints, and sub-pattern alone -- explain the "
            "technique this problem calls for and how to approach it."
            + _VERDICT_LINE.format(options="'VERDICT: WRONG'")
        )

    if status != "Accepted":
        return (
            f"\nThis submission did NOT pass (status: {status}). Do not just hand "
            "over the full solution -- give a hint that points the student toward "
            "the correct approach or technique, referencing what's actually wrong "
            "in their code specifically enough that they can act on it."
            + _VERDICT_LINE.format(options="'VERDICT: WRONG'")
        )

    return (
        "\nThis submission passed. First judge whether it actually uses the "
        "optimal time and space complexity for this problem, based on the "
        "problem's constraints and the expected technique -- not just whether "
        "it runs. If it is NOT optimal, explain that a better approach exists "
        "and hint toward what that optimal solution would look like (again, "
        "hint -- don't fully spell it out). If it IS already optimal, instead "
        "review the code itself for small cleanliness issues -- unnecessary "
        "if-statements, unused or redundant variables, or other minor "
        "inefficiencies -- and give concrete feedback referencing the actual "
        "lines. Only do one of these two, not both."
        + _VERDICT_LINE.format(options="'VERDICT: SUBOPTIMAL' or 'VERDICT: OPTIMAL'")
    )


def create_prompt(problem):
    """Builds the full diagnosis prompt for one problem -- takes an entry
    from diagnosis.get_diagnosis_batch() (title/difficulty/titleSlug/
    frontendId/submissions) and pulls in everything else needed to actually
    diagnose it:
      - the problem's own description + official hints (from merged_problems.json)
      - its named sub-pattern(s) from the 94-pattern sheet, if it's covered
      - their most recent submission's code (just the one, to save on
        LeetCode calls and LLM tokens)
    The closing ask depends on how that submission actually went (see
    _diagnosis_instructions): wrong -> hint toward the fix, right but
    suboptimal -> hint toward the better approach, right and optimal ->
    nitpick code cleanliness. No LLM call happens here -- this only
    assembles the text that would be sent."""
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

    submissions = problem.get("submissions", [])
    lines.append("\nTheir most recent submission for this problem:")
    lines.append(_format_submissions(submissions))

    status = submissions[0]["status"] if submissions else None
    lines.append(_diagnosis_instructions(status))

    return "\n".join(lines)


def parse_verdict(response_text):
    """Splits the required 'VERDICT: X' tag off the front of the LLM's
    response. Returns (verdict, feedback) -- verdict is 'OPTIMAL',
    'SUBOPTIMAL', or 'WRONG' (uppercase), or None if the model didn't
    follow the format. feedback is the rest of the response with the tag
    line removed, ready to show to the student.

    A None verdict is deliberately treated as "not optimal" by whatever
    calls this -- if we can't tell for sure that a problem is done, the
    safe default is to leave it in the backlog, not mark it done."""
    if not response_text:
        return None, response_text

    m = _VERDICT_RE.match(response_text)
    if not m:
        return None, response_text.strip()

    return m.group(1).upper(), response_text[m.end():].strip()


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