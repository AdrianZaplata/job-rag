"""API authentication and rate limiting."""

import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from job_rag.config import settings

_bearer = HTTPBearer(auto_error=False)


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """Validate Bearer token against the configured API key.

    Auth is skipped when ``settings.api_key`` is empty (local development).
    """
    if not settings.api_key:
        return
    if not credentials or credentials.credentials != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


class RateLimiter:
    """Simple in-memory sliding-window rate limiter (no external deps)."""

    def __init__(self, calls: int, period: int) -> None:
        self.calls = calls
        self.period = period
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = [t for t in self._requests[client_ip] if now - t < self.period]
        if len(window) >= self.calls:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        window.append(now)
        self._requests[client_ip] = window


# Pre-configured limiters
standard_limit = RateLimiter(calls=30, period=60)   # 30 req/min
agent_limit = RateLimiter(calls=10, period=60)       # 10 req/min
ingest_limit = RateLimiter(calls=5, period=60)       #  5 req/min
