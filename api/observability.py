"""Observability infrastructure for Soma API.

Provides:
- Structured logging via structlog
- Prometheus metrics
- Request tracing middleware
"""

import time
import structlog
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# ─────────────────────────────────────────────────────────────────────────────
# STRUCTURED LOGGING
# ─────────────────────────────────────────────────────────────────────────────

import logging

# Log level mapping
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def configure_logging(json_logs: bool = False, log_level: str = "INFO"):
    """Configure structured logging.

    Args:
        json_logs: If True, output JSON logs (for production). If False, use console format.
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
    """
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    level = LOG_LEVELS.get(log_level.upper(), logging.INFO)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "soma"):
    """Get a structured logger."""
    return structlog.get_logger(name)


# ─────────────────────────────────────────────────────────────────────────────
# PROMETHEUS METRICS
# ─────────────────────────────────────────────────────────────────────────────

# Request metrics
REQUEST_COUNT = Counter(
    "soma_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "soma_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Analysis metrics
ANALYSIS_COUNT = Counter(
    "soma_analysis_requests_total", "Total analysis requests by type", ["analysis_type"]
)

ANALYSIS_LATENCY = Histogram(
    "soma_analysis_duration_seconds",
    "Analysis computation latency",
    ["analysis_type"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

# Data metrics
SIGNALS_LOADED = Counter(
    "soma_signals_loaded_total", "Total signals loaded for analysis"
)

BASELINE_COMPUTATIONS = Counter(
    "soma_baseline_computations_total", "Total baseline computations", ["biomarker"]
)


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Get content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST TRACING MIDDLEWARE
# ─────────────────────────────────────────────────────────────────────────────


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Middleware for request tracing and metrics collection."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Start timing
        start_time = time.perf_counter()

        # Extract endpoint path (normalize to avoid high cardinality)
        path = request.url.path
        # Normalize path parameters (e.g., /biomarkers/heart_rate -> /biomarkers/{slug})
        endpoint = self._normalize_path(path)

        # Get logger with request context
        logger = get_logger("request")

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            logger.error(
                "request_error", method=request.method, endpoint=endpoint, error=str(e)
            )
            raise
        finally:
            # Calculate duration
            duration = time.perf_counter() - start_time

            # Record metrics
            REQUEST_COUNT.labels(
                method=request.method, endpoint=endpoint, status_code=status_code
            ).inc()

            REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(
                duration
            )

            # Log request
            logger.info(
                "request_completed",
                method=request.method,
                endpoint=endpoint,
                status_code=status_code,
                duration_ms=round(duration * 1000, 2),
            )

        return response

    def _normalize_path(self, path: str) -> str:
        """Normalize path to reduce cardinality.

        Replaces dynamic segments with placeholders.
        """
        parts = path.split("/")
        normalized = []

        skip_next = False
        for i, part in enumerate(parts):
            if skip_next:
                normalized.append("{param}")
                skip_next = False
                continue

            # Check for known dynamic segments
            if part in ("biomarkers", "signals", "baselines", "annotations"):
                normalized.append(part)
                if i + 1 < len(parts) and parts[i + 1] not in (
                    "",
                    "compute",
                    "deviation",
                    "latest",
                ):
                    skip_next = True
            elif part in ("convergence", "drift", "adequacy"):
                normalized.append(part)
                skip_next = True
            else:
                normalized.append(part)

        return "/".join(normalized)


# ─────────────────────────────────────────────────────────────────────────────
# ANALYSIS INSTRUMENTATION
# ─────────────────────────────────────────────────────────────────────────────


def track_analysis(analysis_type: str):
    """Decorator to track analysis execution metrics."""

    def decorator(func: Callable):
        async def async_wrapper(*args, **kwargs):
            ANALYSIS_COUNT.labels(analysis_type=analysis_type).inc()
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                ANALYSIS_LATENCY.labels(analysis_type=analysis_type).observe(duration)

        def sync_wrapper(*args, **kwargs):
            ANALYSIS_COUNT.labels(analysis_type=analysis_type).inc()
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                duration = time.perf_counter() - start
                ANALYSIS_LATENCY.labels(analysis_type=analysis_type).observe(duration)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
