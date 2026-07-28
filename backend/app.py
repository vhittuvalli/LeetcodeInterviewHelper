from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

# Loads backend/.env into the environment (DEEPSEEK_API_KEY, etc.) before
# anything else runs -- must happen before llm_client is imported below so
# its lazy client init sees the key when it's actually needed.
load_dotenv()

import leetcode_service
import spaced_repetition
import recommendations
import diagnosis
import submission_history
import llm_diagnosis
import llm_client
import company_bank
import mock_interview
import db
from security import require_api_secret, rate_limit

app = Flask(__name__)
# Dev-mode CORS: allow your React dev server (e.g. Vite on :5173) AND the
# Chrome extension (which sends requests from a chrome-extension:// origin)
# to call this API. Tighten this to specific origins before deploying anywhere real.
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://leetcode-interview-helper.vercel.app",
]
CORS(
    app,
    origins=ALLOWED_ORIGINS + [r"chrome-extension://.*"],
)
 

def _auth_error_response(e):
    """Shared handler for both /api/topics and /api/credentials so the two
    error cases -- 'never connected' vs 'was connected, now rejected' --
    always come back with the same shape and the same instructions."""
    if isinstance(e, leetcode_service.LeetCodeNotConnectedError):
        return jsonify({
            "error": "not_connected",
            "message": str(e),
            "instructions": leetcode_service.CONNECT_INSTRUCTIONS,
        }), 401
    return jsonify({"error": "session_expired", "message": str(e)}), 401


@app.route("/api/session-status", methods=["GET"])
def session_status():
    """Cheap check the frontend can poll to know whether to show a
    'reconnect your account' prompt before attempting a real fetch."""
    return jsonify(leetcode_service.check_session())


@app.route("/api/credentials", methods=["POST"])
def receive_credentials():
    """The Chrome extension POSTs here whenever it sees LEETCODE_SESSION
    change -- on install (syncing whatever's already there), on login, or
    when LeetCode silently renews the session during normal browsing."""
    body = request.get_json(silent=True) or {}
    cookie = body.get("cookie")
    csrf = body.get("csrf")

    if not cookie or not csrf:
        return jsonify({"error": "bad_request", "message": "Expected JSON body with 'cookie' and 'csrf'"}), 400

    leetcode_service.set_credentials(cookie, csrf)
    return jsonify({"status": "ok", "connected": True})


@app.route("/api/topics", methods=["GET"])
def get_topics():
    try:
        summary = leetcode_service.get_topic_summary()
        return jsonify(summary)
    except leetcode_service.LeetCodeAuthError as e:
        # Covers both LeetCodeNotConnectedError and plain LeetCodeAuthError --
        # _auth_error_response picks the right code/instructions for each.
        return _auth_error_response(e)
    except leetcode_service.LeetCodeAPIError as e:
        return jsonify({"error": "leetcode_api_error", "message": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "server_error", "message": str(e)}), 500


@app.route("/api/spaced-repetition/today", methods=["GET"])
def spaced_repetition_today():
    """Today's review problem -- favors NeetCode 150 problems first, only
    falling back to the rest of your solved list once those are exhausted."""
    try:
        problems = leetcode_service.fetch_solved()
        neetcode_map = leetcode_service.load_neetcode_map()
        result = spaced_repetition.get_todays_problem(problems, set(neetcode_map.keys()))

        if result is None:
            return jsonify({"error": "no_solved_problems", "message": "Solve something on LeetCode first!"}), 404

        return jsonify(result)
    except leetcode_service.LeetCodeAuthError as e:
        return _auth_error_response(e)
    except leetcode_service.LeetCodeAPIError as e:
        return jsonify({"error": "leetcode_api_error", "message": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "server_error", "message": str(e)}), 500


@app.route("/api/spaced-repetition/complete", methods=["POST"])
def spaced_repetition_complete():
    """Mark today's problem reviewed -- moves it off the 'up next' pool and
    clears the day's pick so a new one can be selected if requested again."""
    body = request.get_json(silent=True) or {}
    slug = body.get("titleSlug")

    if not slug:
        return jsonify({"error": "bad_request", "message": "Expected JSON body with 'titleSlug'"}), 400

    return jsonify(spaced_repetition.mark_reviewed(slug))


@app.route("/api/recommendations", methods=["GET"])
def get_recommendations_route():
    """Ranks topics by weakness (avg submissions-to-solve + missing harder
    difficulties among what you've reached), then recommends unsolved,
    non-NeetCode-150 problems from the weakest ones first."""
    try:
        limit = int(request.args.get("limit", 5))
        return jsonify(recommendations.get_recommendations(limit=limit))
    except leetcode_service.LeetCodeAuthError as e:
        return _auth_error_response(e)
    except leetcode_service.LeetCodeAPIError as e:
        return jsonify({"error": "leetcode_api_error", "message": str(e)}), 502
    except FileNotFoundError:
        return jsonify({
            "error": "missing_dataset",
            "message": "backend/data/merged_problems.json not found -- copy it in from your uploads.",
        }), 500
    except Exception as e:
        return jsonify({"error": "server_error", "message": str(e)}), 500


@app.route("/api/diagnosis/pending", methods=["GET"])
def diagnosis_pending():
    """The full pipeline: auto-picks which solved problems are worth
    diagnosing (weak-topic-weighted, capped per topic) AND auto-fetches each
    one's most recent submission code -- nothing to type in, everything is
    driven from your solved-problems list. No LLM call yet, this just
    assembles what would be sent to it."""
    try:
        limit = int(request.args.get("limit", diagnosis.BATCH_SIZE))
        batch = diagnosis.get_diagnosis_batch(limit=limit)
        return jsonify(batch)
    except leetcode_service.LeetCodeAuthError as e:
        return _auth_error_response(e)
    except leetcode_service.LeetCodeAPIError as e:
        return jsonify({"error": "leetcode_api_error", "message": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "server_error", "message": str(e)}), 500


@app.route("/api/submission-history/<title_slug>", methods=["GET"])
def submission_history_route(title_slug):
    """The most recent submission for one problem, with code -- cached
    after the first call. Pass ?refresh=true to bypass the cache."""
    try:
        force_refresh = request.args.get("refresh") == "true"
        history = submission_history.get_submission_history(title_slug, force_refresh=force_refresh)
        return jsonify(history)
    except leetcode_service.LeetCodeAuthError as e:
        return _auth_error_response(e)
    except leetcode_service.LeetCodeAPIError as e:
        return jsonify({"error": "leetcode_api_error", "message": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "server_error", "message": str(e)}), 500


@app.route("/api/diagnosis/prompt-preview", methods=["GET"])
def diagnosis_prompt_preview():
    """Same auto-selection + auto-fetched code as /api/diagnosis/pending,
    but also runs create_prompt() so you can see the actual text that would
    be sent to an LLM. No LLM call yet -- just the prompt-building step."""
    try:
        limit = int(request.args.get("limit", diagnosis.BATCH_SIZE))
        batch = diagnosis.get_diagnosis_batch(limit=limit)
        return jsonify(llm_diagnosis.build_prompts(batch))
    except leetcode_service.LeetCodeAuthError as e:
        return _auth_error_response(e)
    except leetcode_service.LeetCodeAPIError as e:
        return jsonify({"error": "leetcode_api_error", "message": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "server_error", "message": str(e)}), 500


@app.route("/api/diagnosis/run", methods=["POST"])
@require_api_secret
@rate_limit(max_requests=5, window_seconds=600)
def diagnosis_run():
    """Actually runs the LLM diagnosis pipeline: auto-selects weak problems,
    fetches their code, builds prompts, and calls DeepSeek. Only a verdict
    of OPTIMAL marks a problem permanently done -- WRONG/SUBOPTIMAL leave
    it in the backlog for next time, and unchanged submissions since the
    last diagnosis get skipped (no LLM call, no charge) instead of
    re-diagnosing identical code. Costs real API credits for the calls
    that do happen -- POST on purpose so it can't fire from just visiting
    a URL. Also gated by require_api_secret + rate_limit (see security.py)
    since this is one of the two routes that actually spends money."""
    try:
        limit = int(request.args.get("limit", diagnosis.BATCH_SIZE))
        results = llm_client.diagnose_batch(limit=limit)
        return jsonify(results)
    except RuntimeError as e:
        return jsonify({"error": "missing_api_key", "message": str(e)}), 500
    except leetcode_service.LeetCodeAuthError as e:
        return _auth_error_response(e)
    except leetcode_service.LeetCodeAPIError as e:
        return jsonify({"error": "leetcode_api_error", "message": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "server_error", "message": str(e)}), 500


@app.route("/api/mock-interview/companies", methods=["GET"])
def mock_interview_companies():
    """Every company the problem bank has data for, straight from GitHub
    (cached after the first call). Falls back to a short known-good list
    if GitHub can't be reached, rather than erroring the whole picker out."""
    try:
        return jsonify(company_bank.list_companies())
    except Exception as e:
        return jsonify({"error": "server_error", "message": str(e)}), 500


@app.route("/api/mock-interview/difficulty-mix", methods=["GET"])
def mock_interview_difficulty_mix():
    """This company's real Easy/Medium/Hard split (frequency-weighted from
    its actual tagged problems) -- lets the picker show what a round will
    skew toward before you commit to starting one."""
    company = request.args.get("company")
    if not company:
        return jsonify({"error": "bad_request", "message": "Expected a 'company' query param"}), 400

    window = request.args.get("window", "all")
    try:
        return jsonify(mock_interview.difficulty_mix(company, window=window))
    except company_bank.CompanyBankError as e:
        return jsonify({"error": "company_bank_error", "message": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "server_error", "message": str(e)}), 500


@app.route("/api/mock-interview/start", methods=["GET"])
def mock_interview_start():
    """Picks one problem for this company (difficulty sampled from its
    real distribution, best-effort excluding what you've already solved)
    and starts the clock. Free -- no LLM call happens until the round is
    actually submitted for evaluation."""
    company = request.args.get("company")
    if not company:
        return jsonify({"error": "bad_request", "message": "Expected a 'company' query param"}), 400

    window = request.args.get("window", "all")
    try:
        return jsonify(mock_interview.start_round(company, window=window))
    except mock_interview.MockInterviewError as e:
        return jsonify({"error": "no_problems_available", "message": str(e)}), 404
    except company_bank.CompanyBankError as e:
        return jsonify({"error": "company_bank_error", "message": str(e)}), 502
    except leetcode_service.LeetCodeAuthError as e:
        return _auth_error_response(e)
    except leetcode_service.LeetCodeAPIError as e:
        return jsonify({"error": "leetcode_api_error", "message": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "server_error", "message": str(e)}), 500


@app.route("/api/mock-interview/start-loop", methods=["GET"])
def mock_interview_start_loop():
    """Multi-round mode: picks the whole loop's problems upfront (no
    repeats), but doesn't start any clock -- the frontend starts each
    round's timer only once that round is actually shown, then evaluates
    it through the same /api/mock-interview/evaluate route single-round
    mode uses."""
    company = request.args.get("company")
    if not company:
        return jsonify({"error": "bad_request", "message": "Expected a 'company' query param"}), 400

    window = request.args.get("window", "all")
    rounds = request.args.get("rounds", 3)
    try:
        rounds = int(rounds)
    except (TypeError, ValueError):
        return jsonify({"error": "bad_request", "message": "'rounds' must be an integer"}), 400

    try:
        return jsonify(mock_interview.start_loop(company, rounds, window=window))
    except mock_interview.MockInterviewError as e:
        return jsonify({"error": "no_problems_available", "message": str(e)}), 404
    except company_bank.CompanyBankError as e:
        return jsonify({"error": "company_bank_error", "message": str(e)}), 502
    except leetcode_service.LeetCodeAuthError as e:
        return _auth_error_response(e)
    except leetcode_service.LeetCodeAPIError as e:
        return jsonify({"error": "leetcode_api_error", "message": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "server_error", "message": str(e)}), 500


@app.route("/api/mock-interview/evaluate", methods=["POST"])
@require_api_secret
@rate_limit(max_requests=10, window_seconds=600)
def mock_interview_evaluate():
    """Grades a finished (or timed-out) round -- re-fetches your latest
    submission fresh from LeetCode, checks it against the round's actual
    start time and time limit, and (only if there's something to grade)
    makes one LLM call for the optimal/suboptimal judgment. Costs real API
    credits when it does call the LLM -- POST on purpose, same reasoning
    as /api/diagnosis/run. Also gated by require_api_secret + rate_limit
    (see security.py) for the same reason."""
    body = request.get_json(silent=True) or {}
    problem = body.get("problem")
    started_at = body.get("startedAt")
    time_limit = body.get("timeLimitSeconds", mock_interview.ROUND_TIME_SECONDS)
    company = body.get("company")

    if not problem or not problem.get("titleSlug") or started_at is None:
        return jsonify({
            "error": "bad_request",
            "message": "Expected JSON body with 'problem' (from /start) and 'startedAt'",
        }), 400

    try:
        return jsonify(mock_interview.evaluate_round(problem, int(started_at), int(time_limit), company=company))
    except RuntimeError as e:
        return jsonify({"error": "missing_api_key", "message": str(e)}), 500
    except leetcode_service.LeetCodeAuthError as e:
        return _auth_error_response(e)
    except leetcode_service.LeetCodeAPIError as e:
        return jsonify({"error": "leetcode_api_error", "message": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "server_error", "message": str(e)}), 500


@app.route("/api/mock-interview/history", methods=["GET"])
def mock_interview_history():
    """Every past graded round, most recent first -- the raw material for
    a future performance-over-time view. Pass ?limit=N to cap it (default
    50). Purely a read -- no LLM call, no LeetCode call, just the log."""
    limit = int(request.args.get("limit", 50))
    try:
        return jsonify(db.get_mock_interview_history(db.get_default_user_id(), limit=limit))
    except Exception as e:
        return jsonify({"error": "server_error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)