"""Data sync endpoints for external integrations.

Provides manual sync triggers and status checks for connected services.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth import require_auth, optional_auth, AuthContext
from ..database import get_db
from ..integrations.whoop.sync import sync_whoop_data

router = APIRouter(prefix="/sync", tags=["sync"])

# Default user ID for development (single-user mode)
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────


class SyncStatus(BaseModel):
    """Status of a provider sync."""

    provider: str
    connected: bool
    last_sync_at: Optional[datetime] = None
    external_user_id: Optional[str] = None


class SyncResponse(BaseModel):
    """Response from a sync operation."""

    provider: str
    status: str  # "success", "partial", "failed"
    sleep_records: int
    recovery_records: int
    cycle_records: int
    workout_records: int
    signals_created: int
    signals_skipped: int
    errors: list[str]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/{provider}/status", response_model=SyncStatus)
async def get_sync_status(
    provider: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """Get sync status for a provider."""
    result = db.execute(
        text("""
            SELECT external_user_id, last_sync_at
            FROM user_oauth_connections
            WHERE user_id = :user_id AND provider_slug = :provider
        """),
        {"user_id": str(auth.user_id), "provider": provider},
    )
    row = result.fetchone()

    if not row:
        return SyncStatus(provider=provider, connected=False)

    return SyncStatus(
        provider=provider,
        connected=True,
        external_user_id=row[0],
        last_sync_at=row[1],
    )


@router.post("/{provider}", response_model=SyncResponse)
async def trigger_sync(
    provider: str,
    full_sync: bool = Query(False, description="Fetch all historical data"),
    days_back: int = Query(
        30, description="Days of history for full sync", ge=1, le=365
    ),
    db: Session = Depends(get_db),
    auth: Optional[AuthContext] = Depends(optional_auth),
):
    """Trigger a data sync from a provider.

    - **full_sync**: If true, fetches all historical data (up to days_back).
                    If false, only fetches data since last sync.
    - **days_back**: For full sync, how many days of history to fetch (max 365).
    """
    # Use default user if no auth provided (development mode)
    user_id = auth.user_id if (auth and auth.user_id) else DEFAULT_USER_ID

    if provider == "whoop":
        # Check if connected
        result = db.execute(
            text("""
                SELECT id FROM user_oauth_connections
                WHERE user_id = :user_id AND provider_slug = :provider
            """),
            {"user_id": str(user_id), "provider": provider},
        )
        if not result.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Whoop not connected. Visit /v1/oauth/authorize/whoop to connect.",
            )

        # Run sync
        sync_result = await sync_whoop_data(
            user_id=user_id,
            db=db,
            full_sync=full_sync,
            days_back=days_back,
        )

        # Determine status
        if not sync_result.errors:
            status = "success"
        elif sync_result.signals_created > 0:
            status = "partial"
        else:
            status = "failed"

        return SyncResponse(
            provider=provider,
            status=status,
            sleep_records=sync_result.sleep_records,
            recovery_records=sync_result.recovery_records,
            cycle_records=sync_result.cycle_records,
            workout_records=sync_result.workout_records,
            signals_created=sync_result.signals_created,
            signals_skipped=sync_result.signals_skipped,
            errors=sync_result.errors,
        )

    raise HTTPException(status_code=400, detail=f"Unknown sync provider: {provider}")


@router.post("/{provider}/full", response_model=SyncResponse)
async def trigger_full_sync(
    provider: str,
    days_back: int = Query(90, description="Days of history to fetch", ge=1, le=365),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """Trigger a full historical sync from a provider.

    Fetches all data from the specified number of days back, regardless of
    previous sync state. Use this for initial setup or to backfill missing data.
    """
    return await trigger_sync(
        provider=provider,
        full_sync=True,
        days_back=days_back,
        db=db,
        auth=auth,
    )
