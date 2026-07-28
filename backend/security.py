"""Lightweight abuse protection for the routes that actually cost money --
anything that calls the DeepSeek LLM. Layers, meant to be stacked on a
route together:

1. require_api_secret -- a shared-secret header check. Stops a stranger
   who finds the deployed backend's URL directly (not through your
   frontend at all) from hitting these routes and draining your DeepSeek
   credits. Only enforced if API_SHARED_SECRET is actually set in the
   environment -- local development without it configured isn't broken;
   set it before deploying anywhere public and enforcement turns on
   automatically, no code changes needed. Now that real accounts exist,
   this is a secondary layer, not the primary gate -- require_auth (see
   auth.py) is what actually stops a stranger with no account at all.

2. rate_limit -- a simple in-memory cap, keyed per-user when the route is
   already behind @require_auth (so one abusive or compromised account
   can't just rotate IPs to get around its own limit), falling back to
   per-IP for any route that isn't authenticated. Always active
   regardless of whether the shared secret is configured, since it's a
   useful safety net either way -- and matters more with multiple real
   users, since normal simultaneous usage (not just abuse) can now burn
   through a shared DeepSeek budget faster than one person alone ever
   would have.

Both are appropriately scoped for this project (a single Flask process) --
the rate limit state is a plain in-memory dict, so it resets on restart
and isn't shared across multiple worker processes if this ever runs behind
more than one. That's a real limitation, not an oversight: fixing it would
mean a shared store (Redis, or a DB table), which is more infrastructure
than a personal project like this needs right now.
"""
import os
import time
from collections import defaultdict
from functools import wraps

from flask import g, jsonify, request

_request_log = defaultdict(list)


def require_api_secret(fn):
    """Checks the X-API-Key header against API_SHARED_SECRET. A no-op
    (request always allowed through) if that env var isn't set at all --
    this is what keeps local dev working without any extra setup."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = os.environ.get("API_SHARED_SECRET", "")
        if not expected:
            return fn(*args, **kwargs)

        provided = request.headers.get("X-API-Key", "")
        if provided != expected:
            return jsonify({
                "error": "unauthorized",
                "message": "Missing or invalid API key.",
            }), 401

        return fn(*args, **kwargs)
    return wrapper


def rate_limit(max_requests, window_seconds):
    """Caps a route at max_requests per window_seconds, keyed per-user if
    this request already passed through @require_auth or
    @require_sync_token (both stash the resolved user id on flask.g),
    otherwise per client IP. Checked BEFORE the wrapped function ever
    runs, so a request that gets rate-limited never reaches the LLM call
    it would have made.

    Per-user keying matters once there's more than one real account: two
    people rate-limited by IP alone would actually share one combined
    budget if they're ever behind the same IP (a school/office network,
    a VPN), and -- the bigger reason -- keying by IP alone means a
    misbehaving or compromised single account could dodge its own limit
    just by switching networks."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = str(getattr(g, "user_id", None) or request.remote_addr or "unknown")
            now = time.time()
            recent = [t for t in _request_log[key] if now - t < window_seconds]

            if len(recent) >= max_requests:
                retry_after = max(1, int(window_seconds - (now - recent[0])))
                return jsonify({
                    "error": "rate_limited",
                    "message": f"Too many requests -- try again in about {retry_after}s.",
                }), 429

            recent.append(now)
            _request_log[key] = recent
            return fn(*args, **kwargs)
        return wrapper
    return decorator