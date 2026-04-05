"""Signal data endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from typing import Optional

from ..database import get_db
from ..schemas import Signal, SignalCreate
from ..auth import require_auth, AuthContext

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[Signal])
def list_signals(
    biomarker_slug: Optional[str] = None,
    source_slug: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> list[Signal]:
    """
    Query signals with optional filters.

    - **biomarker_slug**: Filter by biomarker type (e.g., 'hrv_rmssd')
    - **source_slug**: Filter by data source (e.g., 'apple_health')
    - **start_time**: Only include signals after this time
    - **end_time**: Only include signals before this time
    - **limit**: Maximum number of results (default 100, max 1000)
    - **offset**: Skip this many results for pagination
    """
    conditions = []
    params = {"limit": limit, "offset": offset}

    if biomarker_slug:
        conditions.append("biomarker_slug = :biomarker_slug")
        params["biomarker_slug"] = biomarker_slug

    if source_slug:
        conditions.append("source_slug = :source_slug")
        params["source_slug"] = source_slug

    if start_time:
        conditions.append("time >= :start_time")
        params["start_time"] = start_time

    if end_time:
        conditions.append("time <= :end_time")
        params["end_time"] = end_time

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    query = f"""
        SELECT time, biomarker_slug, value, value_text, source_slug,
               window_seconds, quality, meta
        FROM signals
        WHERE {where_clause}
        ORDER BY time DESC
        LIMIT :limit OFFSET :offset
    """

    result = db.execute(text(query), params)
    rows = result.mappings().all()
    return [Signal(**row) for row in rows]


@router.get("/latest")
def get_latest_signals(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> dict[str, Signal]:
    """Get the most recent signal for each biomarker type."""
    query = """
        SELECT DISTINCT ON (biomarker_slug)
            time, biomarker_slug, value, value_text, source_slug,
            window_seconds, quality, meta
        FROM signals
        ORDER BY biomarker_slug, time DESC
    """
    result = db.execute(text(query))
    rows = result.mappings().all()
    return {row["biomarker_slug"]: Signal(**row) for row in rows}


@router.get("/latest/{biomarker_slug}", response_model=Signal)
def get_latest_signal(
    biomarker_slug: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> Signal:
    """Get the most recent signal for a specific biomarker."""
    result = db.execute(
        text("""
            SELECT time, biomarker_slug, value, value_text, source_slug,
                   window_seconds, quality, meta
            FROM signals
            WHERE biomarker_slug = :slug
            ORDER BY time DESC
            LIMIT 1
        """),
        {"slug": biomarker_slug},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No signals found for biomarker '{biomarker_slug}'",
        )
    return Signal(**row)


@router.get("/daily/{biomarker_slug}")
def get_daily_aggregates(
    biomarker_slug: str,
    days: int = Query(default=30, le=365),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> list[dict]:
    """
    Get daily aggregated statistics for a biomarker.

    Returns mean, min, max, and sample count for each day.
    """
    result = db.execute(
        text("""
            SELECT
                date_trunc('day', time) as date,
                AVG(value) as mean,
                MIN(value) as min,
                MAX(value) as max,
                COUNT(*) as sample_count
            FROM signals
            WHERE biomarker_slug = :slug
              AND time >= :cutoff
              AND value IS NOT NULL
            GROUP BY date_trunc('day', time)
            ORDER BY date DESC
        """),
        {"slug": biomarker_slug, "cutoff": datetime.now() - timedelta(days=days)},
    )
    rows = result.mappings().all()
    return [dict(row) for row in rows]


@router.post("", response_model=Signal)
def create_signal(
    signal: SignalCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> Signal:
    """
    Manually record a signal measurement.

    Useful for subjective ratings (mood, energy, anxiety) or manual data entry.
    """
    db.execute(
        text("""
            INSERT INTO signals (time, biomarker_slug, value, value_text,
                                source_slug, window_seconds, quality, meta)
            VALUES (:time, :biomarker_slug, :value, :value_text,
                   :source_slug, :window_seconds, :quality, :meta)
        """),
        {
            "time": signal.time,
            "biomarker_slug": signal.biomarker_slug,
            "value": signal.value,
            "value_text": signal.value_text,
            "source_slug": signal.source_slug,
            "window_seconds": signal.window_seconds,
            "quality": signal.quality,
            "meta": signal.meta,
        },
    )
    db.commit()

    return Signal(
        time=signal.time,
        biomarker_slug=signal.biomarker_slug,
        value=signal.value,
        value_text=signal.value_text,
        source_slug=signal.source_slug,
        window_seconds=signal.window_seconds,
        quality=signal.quality,
        meta=signal.meta,
    )


@router.get("/range")
def get_signal_range(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> dict:
    """Get the time range of available signal data."""
    result = db.execute(
        text("SELECT MIN(time) as earliest, MAX(time) as latest, COUNT(*) as total FROM signals")
    )
    row = result.mappings().first()
    return dict(row) if row else {"earliest": None, "latest": None, "total": 0}
