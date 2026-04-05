"""Authentication and authorization for Soma API.

Designed for extensibility:
- API Key authentication (current)
- JWT tokens (future)
- OAuth2 (future)
- Session-based (future)

For a personal health data system, security is paramount.
Even for local deployments, authentication prevents accidental exposure.
"""

import os
import secrets
import hashlib
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from fastapi import Request, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from starlette.status import HTTP_401_UNAUTHORIZED

from .observability import get_logger

logger = get_logger("auth")


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────


class AuthMode(str, Enum):
    """Authentication mode."""

    DISABLED = "disabled"  # No auth (development only)
    API_KEY = "api_key"  # Simple API key
    JWT = "jwt"  # JWT tokens (future)
    OAUTH2 = "oauth2"  # OAuth2 (future)


@dataclass
class AuthConfig:
    """Authentication configuration."""

    mode: AuthMode = AuthMode.API_KEY
    api_key: Optional[str] = None
    api_key_header: str = "X-API-Key"
    api_key_query: str = "api_key"
    allow_query_param: bool = (
        False  # Query string API keys are insecure (logged, cached)
    )

    @classmethod
    def from_env(cls) -> "AuthConfig":
        """Load configuration from environment variables."""
        mode_str = os.getenv("SOMA_AUTH_MODE", "api_key").lower()

        try:
            mode = AuthMode(mode_str)
        except ValueError:
            logger.warning("invalid_auth_mode", mode=mode_str, fallback="api_key")
            mode = AuthMode.API_KEY

        api_key = os.getenv("SOMA_API_KEY")

        # Generate a random key if not set and auth is enabled
        if mode == AuthMode.API_KEY and not api_key:
            api_key = generate_api_key()
            logger.warning(
                "generated_api_key",
                message="No SOMA_API_KEY set, generated random key",
                key_preview=api_key[:8] + "...",
            )
            # Store it so it's consistent for this session
            os.environ["SOMA_API_KEY"] = api_key

        return cls(
            mode=mode,
            api_key=api_key,
            api_key_header=os.getenv("SOMA_API_KEY_HEADER", "X-API-Key"),
            allow_query_param=os.getenv("SOMA_ALLOW_API_KEY_QUERY", "false").lower()
            == "true",
        )


# Global config instance
_auth_config: Optional[AuthConfig] = None


def get_auth_config() -> AuthConfig:
    """Get the authentication configuration."""
    global _auth_config
    if _auth_config is None:
        _auth_config = AuthConfig.from_env()
    return _auth_config


# ─────────────────────────────────────────────────────────────────────────────
# API KEY UTILITIES
# ─────────────────────────────────────────────────────────────────────────────


def generate_api_key(length: int = 32) -> str:
    """Generate a secure random API key."""
    return secrets.token_urlsafe(length)


def hash_api_key(key: str) -> str:
    """Hash an API key for secure storage/comparison."""
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(provided: str, stored: str) -> bool:
    """Securely compare API keys (constant-time comparison)."""
    return secrets.compare_digest(provided, stored)


# ─────────────────────────────────────────────────────────────────────────────
# FASTAPI SECURITY SCHEMES
# ─────────────────────────────────────────────────────────────────────────────

# API Key in header
api_key_header = APIKeyHeader(
    name="X-API-Key", auto_error=False, description="API key for authentication"
)

# API Key in query parameter
api_key_query = APIKeyQuery(
    name="api_key",
    auto_error=False,
    description="API key in query string (not recommended for production)",
)


async def get_api_key(
    header_key: Optional[str] = Security(api_key_header),
    query_key: Optional[str] = Security(api_key_query),
) -> Optional[str]:
    """Extract API key from request."""
    config = get_auth_config()

    # Prefer header over query
    if header_key:
        return header_key

    if query_key and config.allow_query_param:
        return query_key

    return None


# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTICATION DEPENDENCY
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class AuthContext:
    """Authentication context passed to endpoints."""

    authenticated: bool
    method: str
    user_id: Optional[str] = None  # For future multi-user support


async def require_auth(
    request: Request,
    api_key: Optional[str] = Depends(get_api_key),
) -> AuthContext:
    """Dependency that requires authentication.

    Use this for protected endpoints:

        @router.get("/protected")
        async def protected(auth: AuthContext = Depends(require_auth)):
            ...
    """
    config = get_auth_config()

    # Auth disabled - allow everything
    if config.mode == AuthMode.DISABLED:
        logger.debug("auth_disabled_allowing_request")
        return AuthContext(authenticated=True, method="disabled")

    # API Key authentication
    if config.mode == AuthMode.API_KEY:
        if not api_key:
            logger.warning("auth_missing_api_key", path=request.url.path)
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="API key required. Provide via X-API-Key header.",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        if not verify_api_key(api_key, config.api_key):
            logger.warning("auth_invalid_api_key", path=request.url.path)
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )

        logger.debug("auth_success", method="api_key")
        return AuthContext(authenticated=True, method="api_key")

    # JWT (future)
    if config.mode == AuthMode.JWT:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="JWT authentication not yet implemented",
        )

    # OAuth2 (future)
    if config.mode == AuthMode.OAUTH2:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="OAuth2 authentication not yet implemented",
        )

    # Unknown mode
    raise HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


async def optional_auth(
    request: Request,
    api_key: Optional[str] = Depends(get_api_key),
) -> AuthContext:
    """Optional authentication - doesn't fail if not provided.

    Use this for endpoints that work differently when authenticated:

        @router.get("/data")
        async def get_data(auth: AuthContext = Depends(optional_auth)):
            if auth.authenticated:
                # Return full data
            else:
                # Return limited data
    """
    config = get_auth_config()

    if config.mode == AuthMode.DISABLED:
        return AuthContext(authenticated=True, method="disabled")

    if config.mode == AuthMode.API_KEY and api_key:
        if verify_api_key(api_key, config.api_key):
            return AuthContext(authenticated=True, method="api_key")

    return AuthContext(authenticated=False, method="none")


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE PROTECTION HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def public_routes() -> set[str]:
    """Routes that don't require authentication."""
    return {
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
    }


def is_public_route(path: str) -> bool:
    """Check if a route is public."""
    return path in public_routes()


# ─────────────────────────────────────────────────────────────────────────────
# CLI HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def print_auth_info():
    """Print authentication info for CLI startup."""
    config = get_auth_config()

    if config.mode == AuthMode.DISABLED:
        print("\n⚠️  Authentication DISABLED - all endpoints are public")
        print("   Set SOMA_AUTH_MODE=api_key to enable authentication\n")

    elif config.mode == AuthMode.API_KEY:
        print("\n🔐 API Key Authentication enabled")
        print(f"   Header: {config.api_key_header}")
        if config.allow_query_param:
            print(f"   Query param: {config.api_key_query} (enabled)")
        print(f"   Key: {config.api_key[:8]}...{config.api_key[-4:]}")
        print(
            f"\n   Example: curl -H 'X-API-Key: {config.api_key}' http://localhost:8000/v1/status\n"
        )
