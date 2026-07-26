from flask import Flask, jsonify, request
from flask_cors import CORS

import leetcode_service

app = Flask(__name__)
# Dev-mode CORS: allow your React dev server (e.g. Vite on :5173) AND the
# Chrome extension (which sends requests from a chrome-extension:// origin)
# to call this API. Tighten this to specific origins before deploying anywhere real.
CORS(app)


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


if __name__ == "__main__":
    app.run(debug=True, port=5000)