"""OAuth2 endpoints for external service integrations.

Handles OAuth2 authorization flows for connecting external data sources
like Whoop, Oura, Garmin, etc.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth import require_auth, optional_auth, AuthContext
from ..config import get_settings
from ..database import get_db
from ..integrations.whoop.client import WhoopClient, WhoopAPIError

router = APIRouter(prefix="/oauth", tags=["oauth"])

# Default user ID for development (single-user mode)
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────


class OAuthConnection(BaseModel):
    """OAuth connection info for a user."""

    id: UUID
    provider_slug: str
    external_user_id: Optional[str] = None
    scopes: Optional[list[str]] = None
    connected_at: datetime
    last_sync_at: Optional[datetime] = None


class OAuthConnectionList(BaseModel):
    """List of user's OAuth connections."""

    connections: list[OAuthConnection]


# ─────────────────────────────────────────────────────────────────────────────
# State Management (in-memory for simplicity, use Redis in production)
# ─────────────────────────────────────────────────────────────────────────────

# Maps state token -> (user_id, provider, expires_at)
_oauth_states: dict[str, tuple[UUID, str, datetime]] = {}


def create_oauth_state(user_id: UUID, provider: str) -> str:
    """Create a state token for OAuth CSRF protection."""
    state = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    _oauth_states[state] = (user_id, provider, expires_at)
    return state


def validate_oauth_state(state: str) -> Optional[tuple[UUID, str]]:
    """Validate state token and return (user_id, provider) if valid."""
    if state not in _oauth_states:
        return None

    user_id, provider, expires_at = _oauth_states[state]

    # Remove used state
    del _oauth_states[state]

    # Check expiry
    if datetime.now(timezone.utc) > expires_at:
        return None

    return user_id, provider


def cleanup_expired_states():
    """Remove expired state tokens."""
    now = datetime.now(timezone.utc)
    expired = [s for s, (_, _, exp) in _oauth_states.items() if now > exp]
    for s in expired:
        del _oauth_states[s]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/authorize/{provider}")
async def authorize(
    provider: str,
    db: Session = Depends(get_db),
    auth: Optional[AuthContext] = Depends(optional_auth),
):
    """Start OAuth2 authorization flow for a provider.

    Redirects the user to the provider's authorization page.
    For development without auth, uses the default user.
    """
    settings = get_settings()

    # Use default user if no auth provided (development mode)
    user_id = auth.user_id if auth else DEFAULT_USER_ID

    if provider == "whoop":
        if not settings.whoop_client_id:
            raise HTTPException(
                status_code=500,
                detail="Whoop OAuth not configured. Set SOMA_WHOOP_CLIENT_ID and SOMA_WHOOP_CLIENT_SECRET.",
            )

        # Create state for CSRF protection
        state = create_oauth_state(user_id, provider)

        # Build authorization URL
        client = WhoopClient(
            client_id=settings.whoop_client_id,
            client_secret=settings.whoop_client_secret,
            redirect_uri=settings.whoop_redirect_uri,
        )
        auth_url = client.get_authorization_url(state=state)

        return RedirectResponse(url=auth_url)

    raise HTTPException(status_code=400, detail=f"Unknown OAuth provider: {provider}")


@router.get("/callback/{provider}")
async def oauth_callback(
    provider: str,
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="State parameter for CSRF validation"),
    error: Optional[str] = Query(None, description="Error from provider"),
    error_description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Handle OAuth2 callback from provider.

    Exchanges authorization code for tokens and stores the connection.
    """
    # Check for error from provider
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error: {error}. {error_description or ''}",
        )

    # Validate state (CSRF protection)
    state_data = validate_oauth_state(state)
    if not state_data:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state parameter. Please try connecting again.",
        )

    user_id, expected_provider = state_data

    # Fallback to default user if state has None user_id (development mode)
    if user_id is None:
        user_id = DEFAULT_USER_ID

    if provider != expected_provider:
        raise HTTPException(status_code=400, detail="Provider mismatch")

    settings = get_settings()

    if provider == "whoop":
        if not settings.whoop_client_id or not settings.whoop_client_secret:
            raise HTTPException(status_code=500, detail="Whoop OAuth not configured")

        try:
            async with WhoopClient(
                client_id=settings.whoop_client_id,
                client_secret=settings.whoop_client_secret,
                redirect_uri=settings.whoop_redirect_uri,
            ) as client:
                # Exchange code for tokens
                token_response = await client.exchange_code(code)

                # Get user profile for external_user_id
                try:
                    profile = await client.get_profile()
                    external_user_id = str(profile.user_id)
                except WhoopAPIError:
                    external_user_id = None

                # Calculate token expiry
                expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=token_response.expires_in
                )

                # Parse scopes
                scopes = token_response.scope.split() if token_response.scope else []

                # Upsert connection
                db.execute(
                    text("""
                        INSERT INTO user_oauth_connections (
                            user_id, provider_slug, access_token, refresh_token,
                            token_expires_at, external_user_id, scopes, created_at, updated_at
                        )
                        VALUES (
                            :user_id, :provider, :access_token, :refresh_token,
                            :expires_at, :external_user_id, :scopes, NOW(), NOW()
                        )
                        ON CONFLICT (user_id, provider_slug) DO UPDATE SET
                            access_token = EXCLUDED.access_token,
                            refresh_token = EXCLUDED.refresh_token,
                            token_expires_at = EXCLUDED.token_expires_at,
                            external_user_id = EXCLUDED.external_user_id,
                            scopes = EXCLUDED.scopes,
                            updated_at = NOW()
                    """),
                    {
                        "user_id": str(user_id),
                        "provider": provider,
                        "access_token": token_response.access_token,
                        "refresh_token": token_response.refresh_token,
                        "expires_at": expires_at,
                        "external_user_id": external_user_id,
                        "scopes": scopes,
                    },
                )
                db.commit()

                # Return success (in a real app, redirect to frontend)
                return {
                    "status": "connected",
                    "provider": provider,
                    "external_user_id": external_user_id,
                    "message": "Whoop connected successfully! You can now sync your data.",
                }

        except WhoopAPIError as e:
            raise HTTPException(
                status_code=400, detail=f"Failed to connect Whoop: {e.message}"
            )

    raise HTTPException(status_code=400, detail=f"Unknown OAuth provider: {provider}")


@router.get("/connections", response_model=OAuthConnectionList)
async def list_connections(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """List user's OAuth connections."""
    result = db.execute(
        text("""
            SELECT id, provider_slug, external_user_id, scopes,
                   created_at, last_sync_at
            FROM user_oauth_connections
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """),
        {"user_id": str(auth.user_id)},
    )

    connections = []
    for row in result.fetchall():
        connections.append(
            OAuthConnection(
                id=row[0],
                provider_slug=row[1],
                external_user_id=row[2],
                scopes=row[3],
                connected_at=row[4],
                last_sync_at=row[5],
            )
        )

    return OAuthConnectionList(connections=connections)


@router.delete("/connections/{provider}")
async def disconnect(
    provider: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """Disconnect an OAuth provider.

    Removes stored tokens. Does not revoke access at the provider level.
    """
    result = db.execute(
        text("""
            DELETE FROM user_oauth_connections
            WHERE user_id = :user_id AND provider_slug = :provider
            RETURNING id
        """),
        {"user_id": str(auth.user_id), "provider": provider},
    )
    db.commit()

    if not result.fetchone():
        raise HTTPException(
            status_code=404, detail=f"No connection found for provider: {provider}"
        )

    return {"status": "disconnected", "provider": provider}
