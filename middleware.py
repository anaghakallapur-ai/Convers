"""
Custom FastAPI middleware for the Convers backend.

- Request logging (method, path, duration, status code)
- X-Session-ID response header injection
"""

from __future__ import annotations

import json
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("convers.middleware")
logging.basicConfig(level=logging.INFO)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every request with method, path, response status code, and
    wall-clock duration in milliseconds.

    If the request body contains a ``session_id`` field the value is
    echoed back as an ``X-Session-ID`` response header for easy
    client-side correlation.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()

        # ── Try to extract session_id from body ──────────────────────────
        session_id: str | None = None
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body = json.loads(body_bytes)
                    session_id = body.get("session_id")
            except Exception:
                pass

        # ── Forward to the actual route handler ──────────────────────────
        response: Response = await call_next(request)

        # ── Compute duration ─────────────────────────────────────────────
        duration_ms = (time.perf_counter() - start) * 1000

        # ── Log ──────────────────────────────────────────────────────────
        logger.info(
            "%s %s → %d  (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        # ── Inject X-Session-ID header ───────────────────────────────────
        if session_id:
            response.headers["X-Session-ID"] = session_id

        return response
