import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings

# In-memory sliding-window limiter, keyed by client IP. Fine for a single-node
# local deployment; swap for a shared store (e.g. Redis) behind a load balancer.

_hits: dict[str, deque] = defaultdict(deque)


def _cleanup(now: float) -> None:
    for key in list(_hits):
        dq = _hits[key]
        while dq and now - dq[0] > settings.RATE_LIMIT_WINDOW_SECONDS:
            dq.popleft()
        if not dq:
            _hits.pop(key, None)


def rate_limited(route: str):
    """Return a FastAPI dependency factory limiting `route` per client IP."""

    def dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{route}:{client_ip}"
        now = time.monotonic()

        dq = _hits[key]
        while dq and now - dq[0] > settings.RATE_LIMIT_WINDOW_SECONDS:
            dq.popleft()

        if len(dq) >= settings.RATE_LIMIT_MAX_REQUESTS:
            _cleanup(now)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, please try again later",
            )

        dq.append(now)

    return dependency
