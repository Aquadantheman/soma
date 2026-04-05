"""System status and statistics endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..database import get_db
from ..schemas import SystemStatus, IngestRun
from ..auth import require_auth, AuthContext

router = APIRouter(prefix="/status", tags=["status"])


@router.get("", response_model=SystemStatus)
def get_status(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> SystemStatus:
    """
    Get system health and statistics.

    Returns counts of signals, active biomarkers, sources, and baselines.
    """
    # Total signals
    total_signals = db.execute(text("SELECT COUNT(*) FROM signals")).scalar() or 0

    # Biomarkers with data
    biomarkers_tracked = db.execute(
        text("SELECT COUNT(DISTINCT biomarker_slug) FROM signals")
    ).scalar() or 0

    # Sources with data
    sources_active = db.execute(
        text("SELECT COUNT(DISTINCT source_slug) FROM signals")
    ).scalar() or 0

    # Baselines computed
    baselines_computed = db.execute(
        text("SELECT COUNT(DISTINCT biomarker_slug) FROM baselines")
    ).scalar() or 0

    # Latest ingest run
    latest_ingest_result = db.execute(
        text("""
            SELECT id, started_at, completed_at, source_slug, file_path,
                   records_parsed, records_written, records_skipped, errors, status
            FROM ingest_log
            ORDER BY started_at DESC
            LIMIT 1
        """)
    )
    latest_row = latest_ingest_result.mappings().first()
    latest_ingest = IngestRun(**latest_row) if latest_row else None

    # Date range
    range_result = db.execute(
        text("SELECT MIN(time), MAX(time) FROM signals")
    )
    range_row = range_result.first()
    date_range = None
    if range_row and range_row[0]:
        date_range = {"earliest": range_row[0], "latest": range_row[1]}

    return SystemStatus(
        status="healthy",
        total_signals=total_signals,
        biomarkers_tracked=biomarkers_tracked,
        sources_active=sources_active,
        baselines_computed=baselines_computed,
        latest_ingest=latest_ingest,
        date_range=date_range,
    )


@router.get("/ingest-history", response_model=list[IngestRun])
def get_ingest_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> list[IngestRun]:
    """Get history of data ingest runs."""
    result = db.execute(
        text("""
            SELECT id, started_at, completed_at, source_slug, file_path,
                   records_parsed, records_written, records_skipped, errors, status
            FROM ingest_log
            ORDER BY started_at DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    rows = result.mappings().all()
    return [IngestRun(**row) for row in rows]


@router.get("/biomarker-coverage")
def get_biomarker_coverage(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> list[dict]:
    """
    Get data coverage for each biomarker.

    Shows how many signals, date range, and sources for each biomarker.
    """
    result = db.execute(
        text("""
            SELECT
                s.biomarker_slug,
                bt.name,
                bt.category,
                bt.unit,
                COUNT(*) as signal_count,
                MIN(s.time) as earliest,
                MAX(s.time) as latest,
                COUNT(DISTINCT s.source_slug) as source_count,
                ARRAY_AGG(DISTINCT s.source_slug) as sources
            FROM signals s
            JOIN biomarker_types bt ON s.biomarker_slug = bt.slug
            GROUP BY s.biomarker_slug, bt.name, bt.category, bt.unit
            ORDER BY signal_count DESC
        """)
    )
    rows = result.mappings().all()
    return [dict(row) for row in rows]
