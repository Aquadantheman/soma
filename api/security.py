"""Security middleware and utilities for Soma API.

Provides:
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
- Request sanitization
- Audit logging for sensitive operations
"""

import os
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from .observability import get_logger

logger = get_logger("security")


# ─────────────────────────────────────────────────────────────────────────────
# SECURITY HEADERS MIDDLEWARE
# ─────────────────────────────────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses.

    Headers added:
    - X-Content-Type-Options: nosniff (prevent MIME sniffing)
    - X-Frame-Options: DENY (prevent clickjacking)
    - X-XSS-Protection: 0 (disable deprecated XSS filter)
    - Referrer-Policy: strict-origin-when-cross-origin
    - Content-Security-Policy: restrict resource loading
    - Cache-Control: prevent caching of sensitive data

    In production (SOMA_DEBUG=false):
    - Strict-Transport-Security (HSTS)
    """

    def __init__(self, app):
        super().__init__(app)
        self.is_production = os.getenv("SOMA_DEBUG", "false").lower() != "true"
        self.hsts_max_age = int(os.getenv("SOMA_HSTS_MAX_AGE", "31536000"))  # 1 year

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Disable deprecated XSS filter (can cause vulnerabilities)
        response.headers["X-XSS-Protection"] = "0"

        # Control referrer information
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy for API (restrictive since we're an API)
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

        # Prevent caching of API responses (they may contain sensitive data)
        if "Cache-Control" not in response.headers:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"

        # HSTS in production (force HTTPS)
        if self.is_production:
            response.headers["Strict-Transport-Security"] = f"max-age={self.hsts_max_age}; includeSubDomains"

        # Remove server header if present (hide server info)
        if "Server" in response.headers:
            del response.headers["Server"]

        return response


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOGGING
# ─────────────────────────────────────────────────────────────────────────────

def audit_log(
    action: str,
    resource: str,
    details: dict = None,
    request: Request = None,
    success: bool = True
):
    """Log security-relevant actions for audit trail.

    Use this for:
    - Authentication attempts
    - Data modifications (create, update, delete)
    - Configuration changes
    - Access to sensitive endpoints

    Args:
        action: What was done (e.g., "create_signal", "auth_attempt")
        resource: What was affected (e.g., "signal", "annotation")
        details: Additional context (IDs, counts, etc.)
        request: The HTTP request (for IP extraction)
        success: Whether the action succeeded
    """
    log_data = {
        "action": action,
        "resource": resource,
        "success": success,
    }

    if details:
        # Don't log sensitive data
        safe_details = {
            k: v for k, v in details.items()
            if k not in ("password", "api_key", "token", "secret")
        }
        log_data["details"] = safe_details

    if request:
        # Extract client info
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host
        else:
            client_ip = "unknown"

        # Hash IP for privacy in logs
        import hashlib
        log_data["client_ip_hash"] = hashlib.sha256(client_ip.encode()).hexdigest()[:12]
        log_data["path"] = str(request.url.path)
        log_data["method"] = request.method

    if success:
        logger.info("audit_event", **log_data)
    else:
        logger.warning("audit_event_failed", **log_data)


# ─────────────────────────────────────────────────────────────────────────────
# ERROR HANDLING
# ─────────────────────────────────────────────────────────────────────────────

def get_safe_error_message(exc: Exception, is_production: bool = None) -> str:
    """Get a safe error message that doesn't leak internal details.

    In production, returns generic messages.
    In development, returns full details.
    """
    if is_production is None:
        is_production = os.getenv("SOMA_DEBUG", "false").lower() != "true"

    if is_production:
        # Generic messages for common errors
        exc_type = type(exc).__name__

        if "Connection" in exc_type or "Timeout" in exc_type:
            return "Service temporarily unavailable. Please try again."
        elif "Permission" in exc_type or "Forbidden" in exc_type:
            return "Access denied."
        elif "NotFound" in exc_type or "404" in str(exc):
            return "Resource not found."
        elif "Validation" in exc_type or "Value" in exc_type:
            return "Invalid input provided."
        else:
            # Log the actual error internally
            logger.error("unhandled_error", exc_type=exc_type, message=str(exc))
            return "An unexpected error occurred. Please try again later."
    else:
        # Development mode - show full error
        return str(exc)


def create_error_response(
    status_code: int,
    message: str,
    error_type: str = None,
    request_id: str = None
) -> dict:
    """Create a standardized error response.

    Args:
        status_code: HTTP status code
        message: Human-readable error message
        error_type: Machine-readable error type (e.g., "validation_error")
        request_id: Request tracking ID for support
    """
    response = {
        "detail": message,
        "status_code": status_code,
    }

    if error_type:
        response["error_type"] = error_type

    if request_id:
        response["request_id"] = request_id

    return response


# ─────────────────────────────────────────────────────────────────────────────
# SENSITIVE DATA DETECTION
# ─────────────────────────────────────────────────────────────────────────────

SENSITIVE_PATTERNS = [
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "bearer",
    "authorization",
    "credential",
    "private",
]


def contains_sensitive_data(text: str) -> bool:
    """Check if text might contain sensitive data.

    Used to prevent logging sensitive information.
    """
    if not text:
        return False

    text_lower = text.lower()
    return any(pattern in text_lower for pattern in SENSITIVE_PATTERNS)


def redact_sensitive(data: dict) -> dict:
    """Redact sensitive values from a dictionary.

    Replaces sensitive values with "[REDACTED]".
    """
    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        key_lower = key.lower()

        if any(pattern in key_lower for pattern in SENSITIVE_PATTERNS):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = redact_sensitive(value)
        elif isinstance(value, str) and contains_sensitive_data(value):
            result[key] = "[REDACTED]"
        else:
            result[key] = value

    return result
