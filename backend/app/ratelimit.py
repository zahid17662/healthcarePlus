"""Tiny per-process sliding-window limiter for credential endpoints.

Good enough for a single instance; behind several workers/instances use a shared store (Redis).
"""
import time
from collections import defaultdict, deque

from fastapi import Request

from .errors import AppError


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self._window:
            hits.popleft()
        if len(hits) >= self._max:
            raise AppError(429, "Too many attempts. Please wait a minute and try again.")
        hits.append(now)


auth_limiter = RateLimiter(max_requests=10, window_seconds=60)
