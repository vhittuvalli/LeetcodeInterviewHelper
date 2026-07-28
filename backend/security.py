"""Lightweight abuse protection for the routes that actually cost money --
anything that calls the DeepSeek LLM. Two independent layers, meant to be
stacked on a route together:

1. require_api_secret -- a shared-secret header check. Stops a stranger
   who finds the deployed backend's URL directly (not through your
   frontend at all) from hitting these routes and draining your DeepSeek
   credits. Only enforced if API_SHARED_SECRET is actually set in the
   environment -- local development without it configured isn't broken;
   set it before deploying anywhere public and enforcement turns on
   automatically, no code changes needed.

2. rate_limit -- a simple in-memory per-IP cap. Catches abuse even from
   someone who does have the secret (your own frontend misbehaving, a
   leaked secret, etc). Always active regardless of whether the secret is
   configured, since it's a useful safety net either way.

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

from flask import jsonify, request

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
    """Caps a route at max_requests per window_seconds, per client IP.
    Checked BEFORE the wrapped function ever runs, so a request that gets
    rate-limited never reaches the LLM call it would have made."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr or "unknown"
            now = time.time()
            recent = [t for t in _request_log[ip] if now - t < window_seconds]

            if len(recent) >= max_requests:
                retry_after = max(1, int(window_seconds - (now - recent[0])))
                return jsonify({
                    "error": "rate_limited",
                    "message": f"Too many requests -- try again in about {retry_after}s.",
                }), 429

            recent.append(now)
            _request_log[ip] = recent
            return fn(*args, **kwargs)
        return wrapper
    return decorator