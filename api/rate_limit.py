"""Rate limiting middleware for Soma API.

Provides protection against abuse and DoS attacks.
Uses Redis for distributed rate limiting, with in-memory fallback.

Security features:
- Per-IP rate limiting (prevents single-source abuse)
- Configurable limits for different endpoints
- Redis-backed for distributed deployments
- Graceful degradation when Redis unavailable
"""

import os
import time
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional, Callable
from functools import wraps

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .observability import get_logger
from .cache import get_redis

logger = get_logger("rate_limit")


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""

    # Enabled flag
    enabled: bool = True

    # Default limits (requests per window)
    default_limit: int = 100
    default_window_seconds: int = 60

    # Stricter limits for write operations
    write_limit: int = 20
    write_window_seconds: int = 60

    # Burst limit (short window)
    burst_limit: int = 10
    burst_window_seconds: int = 1

    # Authentication endpoint limits (stricter to prevent brute force)
    auth_limit: int = 5
    auth_window_seconds: int = 60

    @classmethod
    def from_env(cls) -> "RateLimitConfig":
        """Load configuration from environment."""
        return cls(
            enabled=os.getenv("SOMA_RATE_LIMIT_ENABLED", "true").lower() == "true",
            default_limit=int(os.getenv("SOMA_RATE_LIMIT_DEFAULT", "100")),
            default_window_seconds=int(os.getenv("SOMA_RATE_LIMIT_WINDOW", "60")),
            write_limit=int(os.getenv("SOMA_RATE_LIMIT_WRITE", "20")),
            auth_limit=int(os.getenv("SOMA_RATE_LIMIT_AUTH", "5")),
        )


_config: Optional[RateLimitConfig] = None


def get_rate_limit_config() -> RateLimitConfig:
    """Get rate limit configuration."""
    global _config
    if _config is None:
        _config = RateLimitConfig.from_env()
    return _config


# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY FALLBACK (when Redis unavailable)
# ─────────────────────────────────────────────────────────────────────────────


class InMemoryRateLimiter:
    """Simple in-memory rate limiter for single-instance deployments."""

    def __init__(self):
        # Dict of {key: [(timestamp, count), ...]}
        self._requests: dict = defaultdict(list)
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Cleanup every minute

    def _cleanup_old_entries(self, window_seconds: int):
        """Remove entries older than the window."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        cutoff = now - (window_seconds * 2)  # Keep 2x window for safety
        for key in list(self._requests.keys()):
            self._requests[key] = [
                (ts, count) for ts, count in self._requests[key] if ts > cutoff
            ]
            if not self._requests[key]:
                del self._requests[key]

        self._last_cleanup = now

    def is_allowed(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Check if request is allowed and return remaining quota.

        Returns:
            (allowed, remaining) - Whether allowed and remaining requests
        """
        self._cleanup_old_entries(window_seconds)

        now = time.time()
        window_start = now - window_seconds

        # Count requests in window
        count = sum(c for ts, c in self._requests[key] if ts > window_start)

        remaining = max(0, limit - count - 1)

        if count >= limit:
            return False, 0

        # Record this request
        self._requests[key].append((now, 1))
        return True, remaining


# Global in-memory limiter
_memory_limiter = InMemoryRateLimiter()


# ─────────────────────────────────────────────────────────────────────────────
# REDIS RATE LIMITER
# ─────────────────────────────────────────────────────────────────────────────


def _redis_check_rate_limit(
    key: str, limit: int, window_seconds: int
) -> tuple[bool, int]:
    """Check rate limit using Redis sliding window.

    Uses Redis sorted sets for accurate sliding window rate limiting.

    Returns:
        (allowed, remaining) - Whether allowed and remaining requests
    """
    redis_client = get_redis()
    if redis_client is None:
        # Fallback to in-memory
        return _memory_limiter.is_allowed(key, limit, window_seconds)

    try:
        now = time.time()
        window_start = now - window_seconds
        redis_key = f"soma:ratelimit:{key}"

        pipe = redis_client.pipeline()

        # Remove old entries
        pipe.zremrangebyscore(redis_key, 0, window_start)

        # Count current entries
        pipe.zcard(redis_key)

        # Add current request (score = timestamp, member = unique id)
        request_id = f"{now}:{hash(str(now))}"
        pipe.zadd(redis_key, {request_id: now})

        # Set expiry on the key
        pipe.expire(redis_key, window_seconds + 1)

        results = pipe.execute()
        current_count = results[1]

        remaining = max(0, limit - current_count - 1)

        if current_count >= limit:
            return False, 0

        return True, remaining

    except Exception as e:
        logger.warning("rate_limit_redis_error", error=str(e))
        # Fallback to in-memory on error
        return _memory_limiter.is_allowed(key, limit, window_seconds)


# ─────────────────────────────────────────────────────────────────────────────
# RATE LIMIT MIDDLEWARE
# ─────────────────────────────────────────────────────────────────────────────


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check for forwarded header (behind proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP (original client)
        return forwarded.split(",")[0].strip()

    # Check for real IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct connection
    if request.client:
        return request.client.host

    return "unknown"


def get_rate_limit_key(request: Request) -> str:
    """Generate rate limit key for a request."""
    ip = get_client_ip(request)
    # Hash the IP for privacy in logs
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
    return f"{ip_hash}:{request.url.path}"


def is_write_operation(request: Request) -> bool:
    """Check if request is a write operation."""
    return request.method in ("POST", "PUT", "PATCH", "DELETE")


def get_limits_for_request(request: Request) -> tuple[int, int]:
    """Get rate limit and window for a request.

    Returns:
        (limit, window_seconds)
    """
    config = get_rate_limit_config()
    path = request.url.path

    # Authentication endpoints - strictest limits
    if "/auth" in path or path.endswith("/login"):
        return config.auth_limit, config.auth_window_seconds

    # Write operations
    if is_write_operation(request):
        return config.write_limit, config.write_window_seconds

    # Default
    return config.default_limit, config.default_window_seconds


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for FastAPI."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        config = get_rate_limit_config()

        # Skip if disabled
        if not config.enabled:
            return await call_next(request)

        # Skip health checks and public routes
        path = request.url.path
        if path in ("/", "/health", "/docs", "/redoc", "/openapi.json", "/metrics"):
            return await call_next(request)

        # Get rate limit key and limits
        key = get_rate_limit_key(request)
        limit, window = get_limits_for_request(request)

        # Check rate limit
        allowed, remaining = _redis_check_rate_limit(key, limit, window)

        if not allowed:
            ip = get_client_ip(request)
            logger.warning(
                "rate_limit_exceeded",
                path=path,
                ip_hash=hashlib.sha256(ip.encode()).hexdigest()[:8],
                limit=limit,
                window=window,
            )
            return Response(
                content='{"detail": "Rate limit exceeded. Please slow down."}',
                status_code=429,
                headers={
                    "Content-Type": "application/json",
                    "Retry-After": str(window),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + window),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + window)

        return response


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT DECORATOR (for fine-grained control)
# ─────────────────────────────────────────────────────────────────────────────


def rate_limit(limit: int = 10, window_seconds: int = 60):
    """Decorator for endpoint-specific rate limiting.

    Use when you need different limits than the middleware defaults.

    Example:
        @router.post("/expensive-operation")
        @rate_limit(limit=5, window_seconds=300)
        async def expensive_operation():
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, request: Request = None, **kwargs):
            config = get_rate_limit_config()

            if config.enabled and request:
                key = f"endpoint:{func.__name__}:{get_rate_limit_key(request)}"
                allowed, _ = _redis_check_rate_limit(key, limit, window_seconds)

                if not allowed:
                    raise HTTPException(
                        status_code=429,
                        detail="Rate limit exceeded for this operation",
                        headers={"Retry-After": str(window_seconds)},
                    )

            return await func(*args, request=request, **kwargs)

        return wrapper

    return decorator
