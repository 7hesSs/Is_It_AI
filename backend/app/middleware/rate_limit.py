"""
Lightweight rate limiter - no external dependencies.

In-memory, per-process, keyed by client IP. Fine for a single-instance
demo deployment (which is what you'd run on Azure App Service anyway).
If you ever run multiple backend workers behind a load balancer, each
worker gets its own counters, so the effective limit multiplies - move
to a shared store (Redis) at that point.
"""
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

RATE_LIMITED_PATH_PREFIX = "/analyze"
MAX_REQUESTS = 100  # edit this directly if you need a different cap
WINDOW_SECONDS = 60

# client_ip -> deque of request timestamps within the current window
_request_log: dict[str, deque] = defaultdict(deque)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(RATE_LIMITED_PATH_PREFIX):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        log = _request_log[client_ip]

        while log and now - log[0] > WINDOW_SECONDS:
            log.popleft()

        if len(log) >= MAX_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded: max {MAX_REQUESTS} requests "
                    f"per {WINDOW_SECONDS}s. Try again shortly."
                },
            )

        log.append(now)
        return await call_next(request)
