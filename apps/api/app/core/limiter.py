"""Simple in-memory rate limiter for FastAPI."""

import time
from collections import defaultdict
from fastapi import Request, HTTPException


class RateLimiter:
    """Token-bucket style rate limiter keyed by client IP."""

    def __init__(self, requests_per_minute: int = 60) -> None:
        self.rpm = requests_per_minute
        self._buckets: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = now - 60

        # Clean expired entries
        bucket = self._buckets[ip]
        self._buckets[ip] = [t for t in bucket if t > window]

        if len(self._buckets[ip]) >= self.rpm:
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

        self._buckets[ip].append(now)


# Global instance: 120 requests per minute per IP
limiter = RateLimiter(requests_per_minute=120)
