"""
Soma API
========
REST API for biosignal data and personal baselines.

Run with:
    uvicorn api.main:app --reload

Or:
    python -m api.main
"""

import os
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .auth import (
    get_auth_config,
    print_auth_info,
)
from .observability import (
    configure_logging,
    get_logger,
    get_metrics,
    get_metrics_content_type,
    RequestTracingMiddleware,
)
from .rate_limit import RateLimitMiddleware, get_rate_limit_config
from .security import SecurityHeadersMiddleware
from .routers.v1 import router as v1_router
from .routers import (
    biomarkers_router,
    signals_router,
    baselines_router,
    annotations_router,
    status_router,
    analysis_router,
)
from .routers.biomarkers import sources_router

settings = get_settings()

# Configure structured logging
json_logs = os.getenv("SOMA_JSON_LOGS", "false").lower() == "true"
log_level = os.getenv("SOMA_LOG_LEVEL", "INFO")
configure_logging(json_logs=json_logs, log_level=log_level)

logger = get_logger("api")
logger.info("starting_api", version=settings.api_version)

# Initialize auth config
auth_config = get_auth_config()
logger.info("auth_configured", mode=auth_config.mode.value)

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="""
## Soma API

Personal biosignal integration for mental health baselines.

### API Versioning

All endpoints are available under `/v1/` prefix (recommended).
Legacy endpoints at root level are deprecated and will be removed in v2.

### Key Concepts

- **Signals**: Raw biosignal measurements (HRV, heart rate, sleep, etc.)
- **Baselines**: Your personal norms computed from historical data
- **Deviations**: How current measurements compare to YOUR baseline
- **Annotations**: Life events to correlate with signal changes

### Philosophy

Unlike fitness trackers that compare you to population averages,
Soma builds YOUR personal distribution for each biomarker.
What matters is not whether your HRV is "good" — it's whether
it's normal *for you*.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration from environment
cors_origins = os.getenv(
    "SOMA_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
).split(",")

# Allowed methods - be explicit instead of wildcard
cors_methods = os.getenv("SOMA_CORS_METHODS", "GET,POST,PUT,DELETE,OPTIONS").split(",")

# Allowed headers - include auth header
cors_headers = os.getenv(
    "SOMA_CORS_HEADERS", "Content-Type,Authorization,X-API-Key"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=cors_methods,
    allow_headers=cors_headers,
)

# Request tracing middleware (must be added after CORS)
app.add_middleware(RequestTracingMiddleware)

# Security headers middleware (adds HSTS, CSP, X-Frame-Options, etc.)
app.add_middleware(SecurityHeadersMiddleware)
logger.info("security_headers_enabled")

# Rate limiting middleware
rate_limit_config = get_rate_limit_config()
if rate_limit_config.enabled:
    app.add_middleware(RateLimitMiddleware)
    logger.info(
        "rate_limiting_enabled",
        default_limit=rate_limit_config.default_limit,
        window_seconds=rate_limit_config.default_window_seconds,
    )
else:
    logger.warning("rate_limiting_disabled")

# ─────────────────────────────────────────────────────────────────────────────
# VERSIONED API (Recommended)
# ─────────────────────────────────────────────────────────────────────────────
app.include_router(v1_router)

# ─────────────────────────────────────────────────────────────────────────────
# LEGACY ENDPOINTS (Deprecated - use /v1/ prefix instead)
# These maintain backward compatibility but will be removed in v2
# ─────────────────────────────────────────────────────────────────────────────
app.include_router(status_router, deprecated=True)
app.include_router(biomarkers_router, deprecated=True)
app.include_router(sources_router, deprecated=True)
app.include_router(signals_router, deprecated=True)
app.include_router(baselines_router, deprecated=True)
app.include_router(annotations_router, deprecated=True)
app.include_router(analysis_router, deprecated=True)


@app.get("/", tags=["root"])
def root():
    """API root - returns API information."""
    return {
        "name": "Soma API",
        "version": settings.api_version,
        "docs": "/docs",
        "v1": "/v1/status",
        "deprecated_notice": "Root-level endpoints are deprecated. Use /v1/ prefix.",
    }


@app.get("/health", tags=["root"])
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/metrics", tags=["observability"], include_in_schema=False)
def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=get_metrics(), media_type=get_metrics_content_type())


if __name__ == "__main__":
    import uvicorn

    # Print auth info on startup
    print_auth_info()

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
    )
