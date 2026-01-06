"""
Rate limiting middleware using in-memory storage.
For production, consider using Redis-based rate limiting.
"""

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Optional, Callable
from functools import wraps

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from llm_app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RateLimitRule:
    requests: int
    window_seconds: int


class InMemoryRateLimiter:
    """Simple in-memory rate limiter using sliding window"""

    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)

    def _clean_old_requests(self, key: str, window_seconds: int) -> None:
        now = time.time()
        cutoff = now - window_seconds
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    def is_rate_limited(self, key: str, limit: int, window_seconds: int) -> bool:
        self._clean_old_requests(key, window_seconds)
        return len(self._requests[key]) >= limit

    def record_request(self, key: str) -> None:
        self._requests[key].append(time.time())

    def get_remaining(self, key: str, limit: int, window_seconds: int) -> int:
        self._clean_old_requests(key, window_seconds)
        return max(0, limit - len(self._requests[key]))

    def get_reset_time(self, key: str, window_seconds: int) -> int:
        if not self._requests[key]:
            return 0
        oldest = min(self._requests[key])
        return int(oldest + window_seconds - time.time())


rate_limiter = InMemoryRateLimiter()

DEFAULT_RATE_LIMITS = {
    "/api/v1/auth/register": RateLimitRule(requests=5, window_seconds=300),
    "/api/v1/auth/login": RateLimitRule(requests=10, window_seconds=60),
    "/api/v1/files/upload": RateLimitRule(requests=20, window_seconds=60),
    "/api/v1/documents": RateLimitRule(requests=30, window_seconds=60),
}

GLOBAL_RATE_LIMIT = RateLimitRule(requests=100, window_seconds=60)


def get_client_identifier(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for FastAPI"""

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        client_id = get_client_identifier(request)
        path = request.url.path

        rule = DEFAULT_RATE_LIMITS.get(path, GLOBAL_RATE_LIMIT)
        rate_key = f"{client_id}:{path}"

        if rate_limiter.is_rate_limited(rate_key, rule.requests, rule.window_seconds):
            remaining = rate_limiter.get_remaining(
                rate_key, rule.requests, rule.window_seconds
            )
            reset_time = rate_limiter.get_reset_time(rate_key, rule.window_seconds)

            logger.warning(
                f"Rate limit exceeded for {client_id} on {path}",
                extra={"client": client_id, "path": path},
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please try again later.",
                    "details": {"retry_after": reset_time},
                },
                headers={
                    "X-RateLimit-Limit": str(rule.requests),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time),
                },
            )

        rate_limiter.record_request(rate_key)

        response = await call_next(request)

        remaining = rate_limiter.get_remaining(
            rate_key, rule.requests, rule.window_seconds
        )
        response.headers["X-RateLimit-Limit"] = str(rule.requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response


def rate_limit(requests: int = 10, window_seconds: int = 60):
    """Decorator for endpoint-specific rate limiting"""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, request: Request = None, **kwargs):
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request:
                client_id = get_client_identifier(request)
                rate_key = f"{client_id}:{func.__name__}"

                if rate_limiter.is_rate_limited(rate_key, requests, window_seconds):
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail={
                            "error": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests",
                        },
                    )
                rate_limiter.record_request(rate_key)

            return await func(*args, **kwargs)

        return wrapper

    return decorator
