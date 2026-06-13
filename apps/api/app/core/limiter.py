"""Simple in-memory rate limiter for FastAPI."""

import time
from collections import defaultdict
from fastapi import Request, HTTPException


class RateLimiter:
    """Token-bucket style rate limiter keyed by client IP."""

    def __init__(self, requests_per_minute: int = 60, trusted_proxies: set[str] | None = None) -> None:
        self.rpm = requests_per_minute
        self._buckets: dict[str, list[float]] = defaultdict(list)
        # WARNING: Only trust X-Forwarded-For if the request comes from a known reverse proxy.
        # If you are running behind a reverse proxy (e.g. nginx, traefik), configure the proxy
        # IPs or networks here. When untrusted, the header is ignored and the direct client IP
        # is used instead to prevent spoofing.
        self._trusted_proxies: set[str] = trusted_proxies or set()
        self._request_count = 0

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded and self._trusted_proxies:
            # Only honour X-Forwarded-For from trusted proxies
            client_ip = request.client.host if request.client else None
            if client_ip and client_ip in self._trusted_proxies:
                return forwarded.split(",")[0].strip()
        # Fall back to direct client IP
        return request.client.host if request.client else "unknown"

    async def __call__(self, request: Request) -> None:
        ip = self._get_client_ip(request)
        now = time.time()
        window = now - 60

        # Clean expired entries
        bucket = self._buckets[ip]
        self._buckets[ip] = [t for t in bucket if t > window]

        if len(self._buckets[ip]) >= self.rpm:
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

        self._buckets[ip].append(now)

        # Periodic cleanup of stale IP entries to prevent memory leak.
        # Runs every 1000 requests (approximately).
        self._request_count += 1
        if self._request_count >= 1000:
            self._request_count = 0
            self._cleanup_stale_entries(now)

    def _cleanup_stale_entries(self, now: float) -> None:
        """Remove IP entries that have had no traffic in the last 5 minutes."""
        cutoff = now - 300
        stale_ips = [
            ip for ip, timestamps in self._buckets.items()
            if not timestamps or max(timestamps) < cutoff
        ]
        for ip in stale_ips:
            del self._buckets[ip]


# Global instance: 120 requests per minute per IP
limiter = RateLimiter(requests_per_minute=120)
