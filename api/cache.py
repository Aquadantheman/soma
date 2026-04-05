"""Redis caching infrastructure for Soma API.

Provides caching for expensive analysis computations.
Cache invalidation occurs when new signals are ingested.
"""

import os
import json
import hashlib
import threading
from typing import Optional, Any, Callable
from functools import wraps
from datetime import timedelta

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from .observability import get_logger

logger = get_logger("cache")


# ─────────────────────────────────────────────────────────────────────────────
# REDIS CONNECTION
# ─────────────────────────────────────────────────────────────────────────────

_redis_client: Optional["redis.Redis"] = None
_redis_lock = threading.Lock()


def get_redis() -> Optional["redis.Redis"]:
    """Get Redis client, lazily initialized (thread-safe).

    Security: Supports password authentication and connection timeouts.
    """
    global _redis_client

    if not REDIS_AVAILABLE:
        return None

    if _redis_client is None:
        with _redis_lock:
            # Double-check after acquiring lock
            if _redis_client is None:
                redis_url = os.getenv("SOMA_REDIS_URL")
                if not redis_url:
                    logger.debug("redis_not_configured")
                    return None

                redis_password = os.getenv("SOMA_REDIS_PASSWORD")

                try:
                    # Security: Use timeouts to prevent hanging connections
                    client = redis.from_url(
                        redis_url,
                        password=redis_password,
                        decode_responses=True,
                        socket_connect_timeout=5,  # 5 second connection timeout
                        socket_timeout=10,  # 10 second operation timeout
                        retry_on_timeout=True,
                    )
                    client.ping()
                    _redis_client = client
                    # Log without exposing password
                    safe_url = redis_url.split("@")[-1] if "@" in redis_url else redis_url
                    logger.info("redis_connected", url=safe_url, has_password=bool(redis_password))
                except redis.ConnectionError as e:
                    logger.warning("redis_unavailable", error=str(e))
                    return None
                except redis.AuthenticationError:
                    logger.error("redis_auth_failed")
                    return None

    return _redis_client


def is_cache_available() -> bool:
    """Check if Redis cache is available."""
    client = get_redis()
    if client is None:
        return False
    try:
        client.ping()
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# CACHE KEYS
# ─────────────────────────────────────────────────────────────────────────────

class CacheKeys:
    """Cache key prefixes and builders."""

    # Prefix for all Soma cache keys
    PREFIX = "soma:"

    # Analysis cache (keyed by analysis type and parameters hash)
    ANALYSIS = f"{PREFIX}analysis:"

    # Baseline cache
    BASELINE = f"{PREFIX}baseline:"

    # Signal count (for cache invalidation)
    SIGNAL_COUNT = f"{PREFIX}signal_count"

    # Last ingest timestamp
    LAST_INGEST = f"{PREFIX}last_ingest"

    @classmethod
    def analysis_key(cls, analysis_type: str, params_hash: str) -> str:
        """Build analysis cache key."""
        return f"{cls.ANALYSIS}{analysis_type}:{params_hash}"

    @classmethod
    def baseline_key(cls, biomarker_slug: str) -> str:
        """Build baseline cache key."""
        return f"{cls.BASELINE}{biomarker_slug}"


# ─────────────────────────────────────────────────────────────────────────────
# CACHE OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────

def cache_get(key: str) -> Optional[Any]:
    """Get value from cache."""
    client = get_redis()
    if client is None:
        return None

    try:
        value = client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.error("cache_get_error", key=key, error=str(e))
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
    """Set value in cache with TTL."""
    client = get_redis()
    if client is None:
        return False

    try:
        client.setex(key, ttl_seconds, json.dumps(value, default=str))
        return True
    except Exception as e:
        logger.error("cache_set_error", key=key, error=str(e))
        return False


def cache_delete(key: str) -> bool:
    """Delete key from cache."""
    client = get_redis()
    if client is None:
        return False

    try:
        client.delete(key)
        return True
    except Exception as e:
        logger.error("cache_delete_error", key=key, error=str(e))
        return False


def cache_invalidate_pattern(pattern: str) -> int:
    """Invalidate all keys matching pattern."""
    client = get_redis()
    if client is None:
        return 0

    try:
        keys = client.keys(pattern)
        if keys:
            deleted = client.delete(*keys)
            logger.info("cache_invalidated", pattern=pattern, count=deleted)
            return deleted
        return 0
    except Exception as e:
        logger.error("cache_invalidate_error", pattern=pattern, error=str(e))
        return 0


def invalidate_analysis_cache() -> int:
    """Invalidate all analysis caches.

    Call this when new signals are ingested.
    """
    return cache_invalidate_pattern(f"{CacheKeys.ANALYSIS}*")


def invalidate_baseline_cache(biomarker_slug: Optional[str] = None) -> int:
    """Invalidate baseline caches.

    Args:
        biomarker_slug: Specific biomarker to invalidate, or None for all.
    """
    if biomarker_slug:
        return cache_invalidate_pattern(f"{CacheKeys.BASELINE}{biomarker_slug}*")
    return cache_invalidate_pattern(f"{CacheKeys.BASELINE}*")


# ─────────────────────────────────────────────────────────────────────────────
# CACHE DECORATOR
# ─────────────────────────────────────────────────────────────────────────────

def cached(
    prefix: str,
    ttl_seconds: int = 3600,
    key_builder: Optional[Callable[..., str]] = None
):
    """Decorator to cache function results.

    Args:
        prefix: Cache key prefix (e.g., "circadian", "correlations")
        ttl_seconds: Cache TTL in seconds (default: 1 hour)
        key_builder: Optional function to build cache key from arguments

    Example:
        @cached("circadian", ttl_seconds=1800)
        def get_circadian_analysis(db):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                params_hash = key_builder(*args, **kwargs)
            else:
                # Hash all kwargs for cache key
                params_str = json.dumps(
                    {k: v for k, v in kwargs.items() if k != "db"},
                    sort_keys=True,
                    default=str
                )
                params_hash = hashlib.md5(params_str.encode()).hexdigest()[:12]

            cache_key = CacheKeys.analysis_key(prefix, params_hash)

            # Try cache first
            cached_value = cache_get(cache_key)
            if cached_value is not None:
                logger.debug("cache_hit", key=cache_key)
                return cached_value

            # Execute function
            result = func(*args, **kwargs)

            # Cache result (convert Pydantic models to dict if needed)
            if result is not None:
                cache_value = result
                if hasattr(result, "model_dump"):
                    cache_value = result.model_dump()
                elif hasattr(result, "dict"):
                    cache_value = result.dict()

                cache_set(cache_key, cache_value, ttl_seconds)
                logger.debug("cache_miss", key=cache_key)

            return result

        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# CACHE STATS
# ─────────────────────────────────────────────────────────────────────────────

def get_cache_stats() -> dict:
    """Get cache statistics."""
    client = get_redis()
    if client is None:
        return {"status": "unavailable"}

    try:
        info = client.info("stats")
        return {
            "status": "connected",
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "keys": client.dbsize(),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
