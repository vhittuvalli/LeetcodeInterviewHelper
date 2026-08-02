"""Company-tagged problem bank for the mock interview feature -- sourced
from liquidslr/leetcode-company-wise-problems on GitHub, a community-
maintained dataset of which problems each company has actually asked,
grouped by how recently and how often (a 'frequency' score, not a strict
percentage -- higher means it's shown up in more reports for that company).

Nothing here is vendored locally: every call fetches from GitHub at
request time (same pattern leetcode_service.load_neetcode_map() already
uses for the NeetCode 150 list) and caches in memory afterward, so a
freshly-added company on GitHub shows up here without a code change.
"""
import csv
import io
from urllib.parse import quote

import requests

REPO = "liquidslr/leetcode-company-wise-problems"
CONTENTS_API = f"https://api.github.com/repos/{REPO}/contents/"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/main"

# Recency windows the dataset actually ships, in the exact filenames used
# in each company's folder. "all" is the default -- widest pool, best for
# picking a realistic problem instead of only the last 30 days' worth.
WINDOW_FILES = {
    "thirty_days": "1. Thirty Days.csv",
    "three_months": "2. Three Months.csv",
    "six_months": "3. Six Months.csv",
    "more_than_six_months": "4. More Than Six Months.csv",
    "all": "5. All.csv",
}

# If the GitHub directory listing can't be reached (rate-limited, network
# hiccup, API shape changes), fall back to a short list of companies that
# are almost certainly still present -- keeps the feature usable in a
# degraded state instead of failing outright.
_FALLBACK_COMPANIES = [
    "Amazon", "Google", "Meta", "Microsoft", "Apple", "Netflix",
    "Bloomberg", "LinkedIn", "Uber", "Adobe",
]


class CompanyBankError(Exception):
    """Wraps any failure talking to GitHub (network, rate limit, unexpected
    response shape) so callers get one error type to handle instead of
    requests' assorted exceptions."""
    pass


_company_list_cache = None
_csv_cache = {}  # (company, window) -> parsed problem list


def list_companies():
    """Every company folder in the repo, alphabetically. Cached for the
    life of the process -- this basically never changes mid-session, no
    reason to hit GitHub's API (and its unauthenticated rate limit) more
    than once."""
    global _company_list_cache
    if _company_list_cache is not None:
        return _company_list_cache

    try:
        r = requests.get(CONTENTS_API, timeout=20, headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        entries = r.json()
        companies = sorted(e["name"] for e in entries if e.get("type") == "dir")
        if not companies:
            raise CompanyBankError("GitHub returned no company directories")
    except (requests.exceptions.RequestException, ValueError, KeyError, CompanyBankError) as e:
        # Degraded but usable -- better than a broken company picker. Printed
        # (not swallowed silently) so Render's logs actually show *why* --
        # e.g. a 403 here almost always means GitHub's unauthenticated rate
        # limit (60 requests/hour per source IP) got hit, which is a very
        # different fix than a real network failure would be.
        status = getattr(getattr(e, "response", None), "status_code", None)
        print(f"company_bank.list_companies: falling back to hardcoded list -- {type(e).__name__}: {e} (status={status})")
        companies = list(_FALLBACK_COMPANIES)

    _company_list_cache = companies
    return companies


def _fetch_csv(company, window):
    filename = WINDOW_FILES.get(window, WINDOW_FILES["all"])
    url = f"{RAW_BASE}/{quote(company)}/{quote(filename)}"

    try:
        r = requests.get(url, timeout=20)
    except requests.exceptions.RequestException as e:
        raise CompanyBankError(f"Could not reach GitHub: {e}") from e

    if r.status_code == 404:
        return None  # this company doesn't have that particular window file
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise CompanyBankError(f"GitHub returned HTTP {r.status_code} for {company}: {e}") from e

    return r.text


def _parse_csv(text):
    """Turns the raw 'Difficulty,Title,Frequency,Acceptance Rate,Link,Topics'
    CSV text into problem dicts the rest of the app can use directly --
    titleSlug pulled out of the Link column (LeetCode's GraphQL API wants
    the slug, not the full URL), difficulty normalized to Title Case to
    match every other difficulty string already used across the app."""
    reader = csv.DictReader(io.StringIO(text))
    problems = []
    for row in reader:
        link = (row.get("Link") or "").strip().rstrip("/")
        title_slug = link.rsplit("/", 1)[-1] if link else None
        if not title_slug:
            continue  # malformed row -- skip rather than fail the whole batch

        try:
            frequency = float(row.get("Frequency") or 0)
        except ValueError:
            frequency = 0.0

        problems.append({
            "titleSlug": title_slug,
            "title": (row.get("Title") or "").strip(),
            "difficulty": (row.get("Difficulty") or "").strip().capitalize(),
            "frequency": frequency,
            "topics": [t.strip() for t in (row.get("Topics") or "").split(",") if t.strip()],
        })
    return problems


def get_company_problems(company, window="all"):
    """The full parsed problem list for one company/window, e.g. for
    Amazon's 'all time' tagged problems. Falls back to the 'all' window if
    the requested one doesn't exist for this company (smaller companies
    often only have the all-time file, not the recency-windowed ones).
    Returns [] if the company has no data at all rather than raising --
    callers can decide how to handle an empty bank."""
    cache_key = (company, window)
    if cache_key in _csv_cache:
        return _csv_cache[cache_key]

    text = _fetch_csv(company, window)
    if text is None and window != "all":
        text = _fetch_csv(company, "all")

    problems = _parse_csv(text) if text else []
    _csv_cache[cache_key] = problems
    return problems