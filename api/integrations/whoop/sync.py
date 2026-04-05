"""Whoop data sync logic.

Fetches data from Whoop API and stores as Soma signals.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from api.config import get_settings
from .client import WhoopClient, WhoopAPIError
from .mapping import transform_whoop_data

logger = logging.getLogger(__name__)


class SyncResult:
    """Result of a sync operation."""

    def __init__(self):
        self.sleep_records = 0
        self.recovery_records = 0
        self.cycle_records = 0
        self.workout_records = 0
        self.signals_created = 0
        self.signals_skipped = 0
        self.errors: list[str] = []

    @property
    def total_records(self) -> int:
        return (
            self.sleep_records
            + self.recovery_records
            + self.cycle_records
            + self.workout_records
        )

    def to_dict(self) -> dict:
        return {
            "sleep_records": self.sleep_records,
            "recovery_records": self.recovery_records,
            "cycle_records": self.cycle_records,
            "workout_records": self.workout_records,
            "signals_created": self.signals_created,
            "signals_skipped": self.signals_skipped,
            "errors": self.errors,
        }


def get_oauth_connection(
    db: Session, user_id: UUID, provider: str = "whoop"
) -> Optional[dict]:
    """Get OAuth connection for user."""
    result = db.execute(
        text("""
            SELECT id, access_token, refresh_token, token_expires_at,
                   external_user_id, last_sync_at
            FROM user_oauth_connections
            WHERE user_id = :user_id AND provider_slug = :provider
        """),
        {"user_id": str(user_id), "provider": provider},
    )
    row = result.fetchone()
    if row:
        return {
            "id": row[0],
            "access_token": row[1],
            "refresh_token": row[2],
            "token_expires_at": row[3],
            "external_user_id": row[4],
            "last_sync_at": row[5],
        }
    return None


def update_oauth_tokens(
    db: Session,
    connection_id: UUID,
    access_token: str,
    refresh_token: Optional[str],
    expires_at: Optional[datetime],
):
    """Update OAuth tokens after refresh."""
    db.execute(
        text("""
            UPDATE user_oauth_connections
            SET access_token = :access_token,
                refresh_token = COALESCE(:refresh_token, refresh_token),
                token_expires_at = :expires_at,
                updated_at = NOW()
            WHERE id = :id
        """),
        {
            "id": str(connection_id),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
        },
    )
    db.commit()


def update_last_sync(db: Session, connection_id: UUID):
    """Update last_sync_at timestamp."""
    db.execute(
        text("""
            UPDATE user_oauth_connections
            SET last_sync_at = NOW(), updated_at = NOW()
            WHERE id = :id
        """),
        {"id": str(connection_id)},
    )
    db.commit()


def insert_signals(db: Session, user_id: UUID, signals: list[dict]) -> tuple[int, int]:
    """Insert signals into database.

    Returns:
        Tuple of (created_count, skipped_count)
    """
    created = 0
    skipped = 0

    for signal in signals:
        try:
            # Use ON CONFLICT to skip duplicates
            # Note: signals table is currently single-user (no user_id column)
            result = db.execute(
                text("""
                    INSERT INTO signals (
                        time, biomarker_slug, value, source_slug,
                        raw_source_id, quality, meta
                    )
                    VALUES (
                        :time, :biomarker_slug, :value, :source_slug,
                        :raw_source_id, :quality, :meta
                    )
                    ON CONFLICT (time, biomarker_slug, source_slug)
                        WHERE raw_source_id IS NOT NULL
                    DO NOTHING
                    RETURNING time
                """),
                {
                    "time": signal["time"],
                    "biomarker_slug": signal["biomarker_slug"],
                    "value": signal["value"],
                    "source_slug": signal["source_slug"],
                    "raw_source_id": signal.get("raw_source_id"),
                    "quality": signal.get("quality", 100),
                    "meta": (
                        json.dumps(signal.get("meta")) if signal.get("meta") else None
                    ),
                },
            )
            if result.fetchone():
                created += 1
            else:
                skipped += 1
        except Exception as e:
            logger.warning(f"Failed to insert signal: {e}")
            skipped += 1

    db.commit()
    return created, skipped


async def sync_whoop_data(
    user_id: UUID,
    db: Session,
    full_sync: bool = False,
    days_back: int = 30,
) -> SyncResult:
    """Sync data from Whoop API for a user.

    Args:
        user_id: User to sync data for
        db: Database session
        full_sync: If True, fetch all historical data. If False, incremental from last sync.
        days_back: For full_sync, how many days of history to fetch

    Returns:
        SyncResult with counts and any errors
    """
    result = SyncResult()
    settings = get_settings()

    # Get OAuth connection
    connection = get_oauth_connection(db, user_id)
    if not connection:
        result.errors.append("No Whoop connection found for user")
        return result

    # Check if we have required credentials
    if not settings.whoop_client_id or not settings.whoop_client_secret:
        result.errors.append("Whoop OAuth credentials not configured")
        return result

    # Determine date range
    end_date = datetime.now(timezone.utc)
    if full_sync:
        start_date = end_date - timedelta(days=days_back)
    elif connection["last_sync_at"]:
        # Overlap by 1 day to catch any late-arriving data
        start_date = connection["last_sync_at"] - timedelta(days=1)
    else:
        # First sync - get last 30 days
        start_date = end_date - timedelta(days=30)

    logger.info(
        f"Syncing Whoop data for user {user_id} from {start_date} to {end_date}"
    )

    try:
        async with WhoopClient(
            client_id=settings.whoop_client_id,
            client_secret=settings.whoop_client_secret,
            redirect_uri=settings.whoop_redirect_uri,
            access_token=connection["access_token"],
            refresh_token=connection["refresh_token"],
        ) as client:
            # Fetch all data types
            try:
                sleep_records = await client.get_all_sleep(start_date, end_date)
                result.sleep_records = len(sleep_records)
            except WhoopAPIError as e:
                result.errors.append(f"Sleep fetch failed: {e.message}")
                sleep_records = []

            try:
                recovery_records = await client.get_all_recovery(start_date, end_date)
                result.recovery_records = len(recovery_records)
            except WhoopAPIError as e:
                result.errors.append(f"Recovery fetch failed: {e.message}")
                recovery_records = []

            try:
                cycle_records = await client.get_all_cycles(start_date, end_date)
                result.cycle_records = len(cycle_records)
            except WhoopAPIError as e:
                result.errors.append(f"Cycle fetch failed: {e.message}")
                cycle_records = []

            try:
                workout_records = await client.get_all_workouts(start_date, end_date)
                result.workout_records = len(workout_records)
            except WhoopAPIError as e:
                result.errors.append(f"Workout fetch failed: {e.message}")
                workout_records = []

            # Get body measurement (not date-ranged)
            try:
                body_measurement = await client.get_body_measurement()
            except WhoopAPIError:
                body_measurement = None

            # Check if tokens were refreshed
            if client.access_token != connection["access_token"]:
                logger.info("Tokens were refreshed during sync, updating database")
                # Calculate new expiry (Whoop tokens last 1 hour typically)
                expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
                update_oauth_tokens(
                    db,
                    connection["id"],
                    client.access_token,
                    client.refresh_token,
                    expires_at,
                )

            # Transform to Soma signals
            signals = transform_whoop_data(
                sleep_records=sleep_records,
                recovery_records=recovery_records,
                cycle_records=cycle_records,
                workout_records=workout_records,
                body_measurement=body_measurement,
            )

            logger.info(f"Transformed {len(signals)} signals from Whoop data")

            # Insert into database
            if signals:
                created, skipped = insert_signals(db, user_id, signals)
                result.signals_created = created
                result.signals_skipped = skipped

            # Update last sync time
            update_last_sync(db, connection["id"])

    except WhoopAPIError as e:
        result.errors.append(f"API error: {e.message}")
    except Exception as e:
        logger.exception("Unexpected error during Whoop sync")
        result.errors.append(f"Unexpected error: {str(e)}")

    return result
