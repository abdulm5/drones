"""Vercel ASGI entrypoint with an explicit project path and startup diagnostics."""
from importlib import import_module
import json
from pathlib import Path
import sys
import traceback

# Vercel loads this file from api/. The sibling backend/ package must also be
# importable when the function's working directory differs from the repo root.
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

_backend = None


async def app(scope, receive, send):
    global _backend
    try:
        if _backend is None:
            _backend = import_module("backend.main").app
    except Exception as error:
        traceback.print_exc()  # Full traceback goes to Vercel runtime logs.
        if scope["type"] == "lifespan":
            while True:
                event = await receive()
                if event["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif event["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] == "http":
            body = json.dumps({"detail": f"Python API startup failed: {type(error).__name__}: {error}",
                               "code": "API_STARTUP_FAILED"}).encode()
            await send({"type": "http.response.start", "status": 503,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"cache-control", b"no-store")]})
            await send({"type": "http.response.body", "body": body})
        return
    await _backend(scope, receive, send)
