"""Signed, expiring demo state that survives a serverless cold start.

Tokens authenticate public observation/mission data; they are not encrypted and
are not user authentication. Application always rechecks the current catalog.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import zlib

LOCAL_KEY = secrets.token_bytes(32)
MAX_TOKEN_SIZE = 2_000_000
MAX_PAYLOAD_SIZE = 3_000_000
SESSION_SECONDS = 3600


class SessionError(ValueError):
    def __init__(self, message, status_code=401):
        super().__init__(message)
        self.status_code = status_code


def signing_key():
    configured = os.environ.get("AGRIFORGE_SIGNING_KEY")
    if configured:
        if len(configured.encode()) < 32:
            raise SessionError("AGRIFORGE_SIGNING_KEY must contain at least 32 bytes.", 503)
        return configured.encode()
    if os.environ.get("VERCEL"):
        raise SessionError("Set AGRIFORGE_SIGNING_KEY in Vercel before running the demo. See docs/vercel.md.", 503)
    return LOCAL_KEY


def b64encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64decode(value):
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def seal(kind, payload, ttl=SESSION_SECONDS):
    data = json.dumps({"v": 1, "kind": kind, "exp": int(time.time()) + ttl, "data": payload},
                      separators=(",", ":"), allow_nan=False).encode()
    if len(data) > MAX_PAYLOAD_SIZE:
        raise SessionError("This mission exceeds the demo session size limit.", 413)
    body = b64encode(zlib.compress(data, 6))
    signature = b64encode(hmac.new(signing_key(), body.encode(), hashlib.sha256).digest())
    return body + "." + signature


def unseal(token, kind):
    key = signing_key()
    if not isinstance(token, str) or len(token) > MAX_TOKEN_SIZE:
        raise SessionError("Invalid demo session. Refresh observations and dispatch again.")
    try:
        body, signature = token.split(".")
        expected = hmac.new(key, body.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, b64decode(signature)):
            raise ValueError("signature")
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(b64decode(body), MAX_PAYLOAD_SIZE + 1)
        if len(raw) > MAX_PAYLOAD_SIZE or decompressor.unconsumed_tail or not decompressor.eof:
            raise ValueError("payload size")
        envelope = json.loads(raw)
        if envelope["v"] != 1 or envelope["kind"] != kind or not isinstance(envelope["data"], dict):
            raise ValueError("purpose")
        if envelope["exp"] <= time.time():
            raise SessionError("Demo session expired. Refresh observations and dispatch again.")
        return envelope["data"]
    except SessionError:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError, zlib.error):
        raise SessionError("Invalid demo session. Refresh observations and dispatch again.") from None
