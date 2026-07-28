import time

import requests

import db

# LeetCode's GraphQL endpoint is unofficial -- there's no published rate
# limit, but hammering it with a burst of requests (which the diagnosis
# pipeline now does: submission list + code pulls across several problems)
# risks getting flagged as bot traffic. A small delay before every request
# spaces things out without being noticeable on single-call endpoints.
_REQUEST_DELAY_SECONDS = 0.3


class LeetCodeAuthError(Exception):
    """Session cookie/csrf was provided but LeetCode rejected it (expired,
    revoked, etc). Callers should treat this as 'ask the user to reconnect',
    not a generic server error."""
    pass


class LeetCodeNotConnectedError(LeetCodeAuthError):
    """No credentials have been provided at all -- e.g. the Chrome extension
    was never installed/connected, so we have nothing to send LeetCode in
    the first place. Distinct from LeetCodeAuthError so the API (and the
    frontend) can tell 'never connected' apart from 'was connected, now
    expired' and show the right prompt for each."""
    pass


class LeetCodeAPIError(Exception):
    """LeetCode reached us fine, but the request itself failed for some
    other reason (network issue, unexpected response shape, GraphQL error
    unrelated to auth)."""
    pass

# Step-by-step instructions surfaced to the frontend whenever a request fails
# because no credentials have ever been provided -- keeps the "how do I fix
# this" copy in one place instead of duplicated in frontend code.
CONNECT_INSTRUCTIONS = [
    "Download the extension folder (ask for the latest copy if you don't have it).",
    "Open Chrome and go to chrome://extensions.",
    "Turn on \"Developer mode\" using the toggle in the top-right corner.",
    "Click \"Load unpacked\" and select the extension folder.",
    "Go to the Account page in this app and generate a sync token.",
    "Click the extension's icon in your toolbar and paste the sync token in.",
    "Make sure you're logged into leetcode.com in this browser -- the extension syncs automatically once you are.",
    "Come back and refresh this page.",
]


def set_credentials(user_id, cookie, csrf):
    """Called by POST /api/credentials whenever the extension sends a fresh
    cookie -- either because the user just connected, or because their
    session was silently renewed while browsing LeetCode. Writes straight
    to the leetcode_credentials table, scoped to whichever account the
    extension's sync token resolved to (see auth.require_sync_token)."""
    db.upsert_credentials(user_id, cookie or "", csrf or "")


def has_credentials(user_id):
    cookie, csrf = db.get_credentials(user_id)
    return bool(cookie and csrf)


def _build_headers(user_id):
    # Read from the DB per-request (not cached) so a credential update from
    # set_credentials() takes effect on the very next call, not just after a
    # server restart -- same reasoning as the old in-memory version had.
    cookie, csrf = db.get_credentials(user_id)
    return {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://leetcode.com",
        "Referer": "https://leetcode.com/progress/?page=1&status=SOLVED",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Cookie": cookie or "",
        "x-csrftoken": csrf or "",
    }

SESSION_CHECK_QUERY = """
query globalData {
  userStatus {
    isSignedIn
    username
  }
}
"""

QUERY = """
query userProgressQuestionList($filters: UserProgressQuestionListInput) {
  userProgressQuestionList(filters: $filters) {
    totalNum
    questions {
      frontendId
      title
      titleSlug
      difficulty
      questionStatus
      lastSubmittedAt
      numSubmitted
      topicTags { name slug }
    }
  }
}
"""

# Step 1 of getting submission history for a problem: list every submission
# (accepted AND failed) filtered to one question via questionSlug. No code
# in this response yet -- just id/status/lang/timestamp, enough to decide
# which submissions are worth pulling code for.
SUBMISSION_LIST_QUERY = """
query submissionList($offset: Int!, $limit: Int!, $slug: String) {
  submissionList(offset: $offset, limit: $limit, questionSlug: $slug) {
    hasNext
    submissions {
      id
      lang
      timestamp
      statusDisplay
      titleSlug
    }
  }
}
"""

# Step 2: given one submission id (from the list above), get its actual code.
# This is a separate request per submission -- there's no bulk "give me the
# code for all of these ids" query, which is exactly why we filter down to
# only the important submissions before calling this.
SUBMISSION_DETAIL_QUERY = """
query submissionDetails($id: Int!) {
  submissionDetails(submissionId: $id) {
    id
    code
    timestamp
    statusCode
    lang { name }
    runtimeError
    compileError
  }
}
"""

NEETCODE_150_URL = "https://raw.githubusercontent.com/krmanik/Anki-NeetCode/main/neetcode-150-list.json"

TOPIC_PRIORITY = [
    ("Arrays & Hashing",          {"Array", "Hash Table", "String"}),
    ("Two Pointers",              {"Two Pointers"}),
    ("Sliding Window",            {"Sliding Window"}),
    ("Stack",                     {"Stack", "Monotonic Stack"}),
    ("Binary Search",             {"Binary Search"}),
    ("Linked List",               {"Linked List", "Doubly-Linked List"}),
    ("Trees",                     {"Tree", "Binary Tree", "Binary Search Tree"}),
    ("Heap / Priority Queue",     {"Heap (Priority Queue)"}),
    ("Backtracking",              {"Backtracking"}),
    ("Tries",                     {"Trie"}),
    ("Graphs",                    {"Graph", "Union Find", "Topological Sort"}),
    ("Advanced Graphs",           {"Shortest Path", "Minimum Spanning Tree", "Strongly Connected Component"}),
    ("1-D Dynamic Programming",   {"Dynamic Programming", "Memoization"}),
    ("2-D Dynamic Programming",   set()),
    ("Greedy",                    {"Greedy"}),
    ("Intervals",                 set()),
    ("Math & Geometry",           {"Math", "Geometry", "Number Theory", "Combinatorics"}),
    ("Bit Manipulation",          {"Bit Manipulation", "Bitmask"}),
]

OTHER = "Other"
TOPIC_ORDER = [name for name, _ in TOPIC_PRIORITY] + [OTHER]

# Simple in-memory cache for the NeetCode 150 map -- it doesn't change between
# requests, no reason to re-fetch it from GitHub on every /api/topics call.
_neetcode_map_cache = None


AUTH_ERROR_HINTS = ("sign in", "log in", "login", "unauthorized", "unauthenticated", "authenticate")


def _post_graphql(user_id, query, variables, operation_name):
    """Shared request wrapper with layered error detection:
    1. missing credentials      -> LeetCodeAuthError (fail fast, no request sent)
    2. network/connection issue -> LeetCodeAPIError
    3. HTTP 401/403             -> LeetCodeAuthError
    4. non-JSON response body   -> LeetCodeAuthError (LeetCode redirects expired
                                    sessions to an HTML login page instead of JSON)
    5. GraphQL "errors" present -> LeetCodeAuthError if it looks auth-related,
                                    else LeetCodeAPIError
    6. anything else unexpected -> LeetCodeAPIError
    """
    if not has_credentials(user_id):
        raise LeetCodeNotConnectedError(
            "No LeetCode credentials on file -- the Chrome extension hasn't been connected yet"
        )

    payload = {"query": query, "variables": variables, "operationName": operation_name}

    time.sleep(_REQUEST_DELAY_SECONDS)

    try:
        r = requests.post("https://leetcode.com/graphql/", headers=_build_headers(user_id), json=payload, timeout=20)
    except requests.exceptions.RequestException as e:
        raise LeetCodeAPIError(f"Could not reach LeetCode: {e}") from e

    if r.status_code in (401, 403):
        raise LeetCodeAuthError(f"LeetCode rejected the request (HTTP {r.status_code}) -- session likely expired")

    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise LeetCodeAPIError(f"LeetCode returned HTTP {r.status_code}: {e}") from e

    try:
        data = r.json()
    except ValueError as e:
        # Expired sessions often get redirected to an HTML login page instead
        # of a JSON error -- that shows up here as a JSON parse failure.
        raise LeetCodeAuthError("LeetCode did not return JSON -- session is likely expired or invalid") from e

    if "errors" in data:
        messages = " ".join(str(err.get("message", "")) for err in data["errors"]).lower()
        if any(hint in messages for hint in AUTH_ERROR_HINTS):
            raise LeetCodeAuthError(f"LeetCode reported an auth error: {data['errors']}")
        raise LeetCodeAPIError(f"LeetCode GraphQL error: {data['errors']}")

    if data.get("data") is None:
        raise LeetCodeAuthError("LeetCode returned no data -- session is likely expired or invalid")

    return data["data"]


def check_session(user_id):
    """Lightweight pre-flight check: is this stored credential still valid?
    Cheap enough to poll from the frontend before attempting a full fetch."""
    if not has_credentials(user_id):
        return {"signedIn": False, "connected": False}

    try:
        result = _post_graphql(user_id, SESSION_CHECK_QUERY, {}, "globalData")
    except LeetCodeAuthError:
        return {"signedIn": False, "connected": True}

    status = result.get("userStatus") or {}
    return {"signedIn": bool(status.get("isSignedIn")), "connected": True, "username": status.get("username")}


def _fetch_by_status(user_id, status, limit=50):
    all_questions = []
    skip = 0
    total = None
    while True:
        result = _post_graphql(
            user_id,
            QUERY,
            {"filters": {"skip": skip, "limit": limit, "questionStatus": status}},
            "userProgressQuestionList",
        )
        block = result["userProgressQuestionList"]
        total = block["totalNum"]
        qs = block["questions"]
        all_questions.extend(qs)
        if len(qs) < limit or len(all_questions) >= total:
            break
        skip += limit
    return all_questions


def fetch_solved(user_id, limit=50):
    return _fetch_by_status(user_id, "SOLVED", limit=limit)


def fetch_attempted(user_id, limit=50):
    # "ATTEMPTED" == tried but never solved -- confirmed against the live API.
    return _fetch_by_status(user_id, "ATTEMPTED", limit=limit)


def fetch_submission_list(user_id, title_slug, limit=20):
    """Every submission (accepted + failed) for one problem, paginated.
    Normalizes id/timestamp from strings (what the raw API returns) to ints
    so callers can compare/sort them without thinking about it."""
    all_submissions = []
    offset = 0
    while True:
        result = _post_graphql(
            user_id,
            SUBMISSION_LIST_QUERY,
            {"offset": offset, "limit": limit, "slug": title_slug},
            "submissionList",
        )
        block = result["submissionList"]
        subs = block["submissions"]
        for s in subs:
            s["id"] = int(s["id"])
            s["timestamp"] = int(s["timestamp"])
        all_submissions.extend(subs)
        if not block.get("hasNext") or not subs:
            break
        offset += limit
    return all_submissions


def fetch_latest_submission(user_id, title_slug):
    """The single most recent submission for one problem, picked by
    comparing timestamps -- NOT by trusting offset=0 to be "the newest."
    (It was assumed newest-first based on how the reference JS client uses
    it, but that assumption was never verified against live data and
    turned out to be wrong: it was returning the *first-ever* attempt,
    which for a solved problem is often a failed one. Two Sum showing as
    "wrong" despite being solved was exactly this bug.)

    fetch_submission_list() already paginates through everything LeetCode
    has on record for this problem, so this just takes the max-timestamp
    entry out of that -- correct regardless of what order the API actually
    returns them in. Returns None if there's no submission on record at all."""
    all_submissions = fetch_submission_list(user_id, title_slug)
    if not all_submissions:
        return None
    return max(all_submissions, key=lambda s: s["timestamp"])


def fetch_submission_code(user_id, submission_id):
    """Code + a bit of metadata for exactly one submission id."""
    result = _post_graphql(
        user_id,
        SUBMISSION_DETAIL_QUERY,
        {"id": int(submission_id)},
        "submissionDetails",
    )
    return result["submissionDetails"]


def load_neetcode_map():
    global _neetcode_map_cache
    if _neetcode_map_cache is not None:
        return _neetcode_map_cache

    try:
        r = requests.get(NEETCODE_150_URL, timeout=20)
        r.raise_for_status()
        data = r.json()
    except (requests.exceptions.RequestException, ValueError) as e:
        raise LeetCodeAPIError(f"Could not load NeetCode 150 reference list: {e}") from e

    slug_to_topic = {}
    for topic, problems in data.items():
        for _, info in problems.items():
            slug = info["url"].rstrip("/").split("/")[-1]
            slug_to_topic[slug] = topic

    _neetcode_map_cache = slug_to_topic
    return slug_to_topic


def primary_topic(problem, neetcode_map):
    topic = neetcode_map.get(problem["titleSlug"])
    if topic:
        return topic

    tags = {t["name"] for t in problem.get("topicTags", [])}
    match = OTHER
    for topic_name, topic_tags in TOPIC_PRIORITY:
        if tags & topic_tags:
            match = topic_name
    return match


def group_by_topic(problems, neetcode_map):
    grouped = {name: [] for name in TOPIC_ORDER}
    for p in problems:
        grouped[primary_topic(p, neetcode_map)].append(p)
    return grouped


def get_topic_summary(user_id):
    """The single entry point the Flask route calls."""
    neetcode_map = load_neetcode_map()
    problems = fetch_solved(user_id)
    grouped = group_by_topic(problems, neetcode_map)

    return [
        {
            "topic": topic_name,
            "solvedCount": len(grouped[topic_name]),
            "problems": grouped[topic_name],
        }
        for topic_name in TOPIC_ORDER
    ]