"""Real per-request identity, replacing Phase 1's single hardcoded default
user. db.py's get_default_user_id() docstring said from the start that
"when real multi-user auth exists, only this one function's caller needs
to change" -- this file is that change.

Two separate authentication schemes live here, because they're answering
two different questions:

1. require_auth -- "is this a logged-in user of the web app?" Verifies a
   Supabase-issued JWT (the frontend gets one automatically from
   supabase-js on login/signup). Supabase handles password hashing, email
   verification, and session refresh entirely on its own end; this module's
   only job is confirming a token is genuine and pulling the user's id
   (the `sub` claim) out of it.

2. require_sync_token -- "is this our own Chrome extension, and which
   account does it belong to?" The extension never logs into Supabase
   directly (browser extensions don't share your web app's login session),
   so it authenticates with a separate opaque token instead -- generated
   from the Account page once you're logged in, pasted into the extension
   once. Deliberately NOT the same as your login JWT: if this token leaks
   (it lives in extension storage, a more exposed spot than a browser
   session), the blast radius is capped at "someone can push a fake
   LeetCode cookie to my account," not "someone can act as me everywhere."
"""
import os
import uuid
from functools import wraps

import jwt
from jwt import PyJWKClient
from flask import g, jsonify, request

import db

# Supabase has two generations of token signing:
#   - legacy: one shared secret, tokens signed HS256
#   - current: a real public/private key pair per project, tokens signed
#     ES256 -- verified against the project's *public* keys, published at
#     a JWKS endpoint, no secret involved at all
# Which one a given project uses depends on whether it's rotated to the
# newer "JWT Signing Keys" system (Settings -> API -> JWT Keys). Rather
# than assume, _decode_token looks at the token's own header and verifies
# it the way it says it was signed -- this project's tokens were confirmed
# (by decoding a real one) to be ES256, but supporting both means this
# doesn't silently break again if that ever changes.
_jwks_client = None


def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        if not supabase_url:
            raise RuntimeError(
                "SUPABASE_URL is not set -- needed to fetch your project's "
                "public signing keys to verify ES256 tokens. Copy it from "
                "Supabase's Project Settings -> API -> Project URL (same "
                "value as the frontend's VITE_SUPABASE_URL)."
            )
        # PyJWKClient fetches and caches this by itself (Supabase's edge
        # layer caches the response ~10 min too), so one client instance
        # reused across requests avoids a network round trip per login.
        _jwks_client = PyJWKClient(f"{supabase_url}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def _get_jwt_secret():
    secret = os.environ.get("SUPABASE_JWT_SECRET", "")
    if not secret:
        raise RuntimeError(
            "SUPABASE_JWT_SECRET is not set -- copy it from Supabase's "
            "Project Settings -> API -> JWT Settings -> JWT Secret (legacy "
            "HS256 secret, not the publishable/anon key)."
        )
    return secret


def _decode_token(token):
    """Verifies a Supabase-issued JWT, branching on how it's actually
    signed rather than assuming. ES256 is the modern default (verified
    against the project's public JWKS, no shared secret needed); HS256 is
    the legacy path, kept as a fallback for projects that haven't rotated
    to the newer signing keys."""
    header = jwt.get_unverified_header(token)

    if header.get("alg") == "ES256":
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )

    return jwt.decode(
        token,
        _get_jwt_secret(),
        algorithms=["HS256"],
        audience="authenticated",
    )


def require_auth(fn):
    """Verifies Authorization: Bearer <supabase-jwt> on every request.
    Rejects with 401 if it's missing, malformed, expired, or signed with
    the wrong key -- there's no fallback to a default user anymore, an
    unauthenticated request simply doesn't reach the route at all.

    On success, stashes the verified user id on flask.g for the duration
    of this request (get_current_user_id() reads it back out) and makes
    sure a matching row exists in our own `users` table -- Supabase Auth
    manages its own auth.users table separately from this app's schema,
    so the first time a given account is ever seen here, its id gets
    mirrored into users.id so every existing foreign key keeps working
    unmodified."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({
                "error": "unauthorized",
                "message": "Missing Authorization header -- please log in.",
            }), 401

        token = auth_header[len("Bearer "):]
        try:
            payload = _decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({
                "error": "token_expired",
                "message": "Your session has expired -- please log in again.",
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "error": "unauthorized",
                "message": "Invalid authentication token.",
            }), 401
        except jwt.PyJWKClientError:
            # Couldn't fetch/find a matching public key from Supabase's
            # JWKS endpoint -- most likely SUPABASE_URL is wrong, or a
            # transient network issue reaching Supabase. Distinct from "the
            # token itself is bad," but a request without a verifiable
            # signature is unauthenticated either way.
            return jsonify({
                "error": "unauthorized",
                "message": "Could not verify token signature -- check the backend's SUPABASE_URL.",
            }), 401

        try:
            user_id = uuid.UUID(payload["sub"])
        except (KeyError, ValueError):
            return jsonify({
                "error": "unauthorized",
                "message": "Token did not contain a valid user id.",
            }), 401

        db.ensure_user_exists(user_id)
        g.user_id = user_id
        return fn(*args, **kwargs)
    return wrapper


def get_current_user_id():
    """Reads back the user id require_auth stashed on this request. Only
    ever called from inside a route already wrapped with require_auth (or
    require_sync_token, which sets the same attribute), so g.user_id is
    always present by the time this runs."""
    return g.user_id


def require_sync_token(fn):
    """Verifies X-Sync-Token against the extension_tokens table instead of
    a Supabase JWT -- this is the header the Chrome extension sends on
    every /api/credentials POST. Looks up which user the token belongs to
    (db.get_user_for_sync_token() compares a hash, not the raw token, the
    same reasoning a password table never stores plaintext) and stashes it
    on g.user_id exactly like require_auth does, so downstream code
    doesn't need to know which of the two schemes authenticated this
    particular request."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = request.headers.get("X-Sync-Token", "")
        if not token:
            return jsonify({
                "error": "unauthorized",
                "message": "Missing X-Sync-Token header -- generate one from the Account page and paste it into the extension.",
            }), 401

        user_id = db.get_user_for_sync_token(token)
        if user_id is None:
            return jsonify({
                "error": "unauthorized",
                "message": "Invalid or revoked sync token -- generate a new one from the Account page.",
            }), 401

        g.user_id = user_id
        return fn(*args, **kwargs)
    return wrapper