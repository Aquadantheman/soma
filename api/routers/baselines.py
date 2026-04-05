"""Baseline computation and deviation analysis endpoints."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd

from ..database import get_db, get_db_session
from ..schemas import Baseline, BaselineCompute, DeviationCheck, DeviationResult
from ..auth import require_auth, AuthContext

# Science layer imports (requires: pip install -e science/)
from soma.baseline.model import (
    compute_baseline as compute_baseline_internal,
    compute_deviation as compute_deviation_internal,
    BiomarkerBaseline,
)

router = APIRouter(prefix="/baselines", tags=["baselines"])


@router.get("", response_model=list[Baseline])
def list_baselines(
    biomarker_slug: str | None = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> list[Baseline]:
    """List all computed baselines, optionally filtered by biomarker."""
    query = """
        SELECT id, biomarker_slug, computed_at, window_days,
               mean, std_dev, p10, p25, p50, p75, p90, sample_count
        FROM baselines
    """
    params = {}

    if biomarker_slug:
        query += " WHERE biomarker_slug = :slug"
        params["slug"] = biomarker_slug

    query += " ORDER BY computed_at DESC"

    result = db.execute(text(query), params)
    rows = result.mappings().all()
    return [Baseline(**row) for row in rows]


@router.get("/latest")
def get_latest_baselines(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> dict[str, Baseline]:
    """Get the most recently computed baseline for each biomarker."""
    query = """
        SELECT DISTINCT ON (biomarker_slug)
            id, biomarker_slug, computed_at, window_days,
            mean, std_dev, p10, p25, p50, p75, p90, sample_count
        FROM baselines
        ORDER BY biomarker_slug, computed_at DESC
    """
    result = db.execute(text(query))
    rows = result.mappings().all()
    return {row["biomarker_slug"]: Baseline(**row) for row in rows}


@router.get("/{biomarker_slug}", response_model=Baseline)
def get_baseline(
    biomarker_slug: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> Baseline:
    """Get the latest baseline for a specific biomarker."""
    result = db.execute(
        text("""
            SELECT id, biomarker_slug, computed_at, window_days,
                   mean, std_dev, p10, p25, p50, p75, p90, sample_count
            FROM baselines
            WHERE biomarker_slug = :slug
            ORDER BY computed_at DESC
            LIMIT 1
        """),
        {"slug": biomarker_slug},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No baseline found for '{biomarker_slug}'. Run POST /baselines/compute first.",
        )
    return Baseline(**row)


def _compute_and_store_baselines(
    biomarker_slugs: list[str] | None,
    window_days: int,
):
    """Background task to compute and store baselines."""
    with get_db_session() as db:
        # Get signals data using parameterized query
        if biomarker_slugs:
            result = db.execute(
                text("""
                    SELECT time, biomarker_slug, value
                    FROM signals
                    WHERE biomarker_slug = ANY(:slugs)
                    ORDER BY time
                """),
                {"slugs": biomarker_slugs},
            )
        else:
            result = db.execute(text("""
                    SELECT time, biomarker_slug, value
                    FROM signals
                    ORDER BY time
                """))
        rows = result.fetchall()

        if not rows:
            return

        df = pd.DataFrame(rows, columns=["time", "biomarker_slug", "value"])

        # Get unique biomarkers
        slugs = biomarker_slugs or df["biomarker_slug"].unique().tolist()

        for slug in slugs:
            baseline = compute_baseline_internal(df, slug, window_days=window_days)

            if baseline is None:
                continue

            # Store in database
            db.execute(
                text("""
                    INSERT INTO baselines
                        (biomarker_slug, computed_at, window_days, mean, std_dev,
                         p10, p25, p50, p75, p90, sample_count)
                    VALUES
                        (:slug, :computed_at, :window_days, :mean, :std_dev,
                         :p10, :p25, :p50, :p75, :p90, :sample_count)
                """),
                {
                    "slug": baseline.biomarker_slug,
                    "computed_at": baseline.computed_at,
                    "window_days": baseline.window_days,
                    "mean": baseline.mean,
                    "std_dev": baseline.std,
                    "p10": baseline.p10,
                    "p25": baseline.p25,
                    "p50": baseline.median,
                    "p75": baseline.p75,
                    "p90": baseline.p90,
                    "sample_count": baseline.sample_count,
                },
            )

        db.commit()


@router.post("/compute")
def compute_baselines(
    request: BaselineCompute,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> dict:
    """
    Trigger baseline computation for specified biomarkers.

    If no biomarker_slugs provided, computes for all biomarkers with data.
    Computation runs in background.
    """
    # Validate biomarker slugs if provided
    if request.biomarker_slugs:
        result = db.execute(
            text("SELECT slug FROM biomarker_types WHERE slug = ANY(:slugs)"),
            {"slugs": request.biomarker_slugs},
        )
        valid_slugs = {row[0] for row in result}
        invalid = set(request.biomarker_slugs) - valid_slugs
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown biomarker slugs: {invalid}",
            )

    background_tasks.add_task(
        _compute_and_store_baselines,
        request.biomarker_slugs,
        request.window_days,
    )

    return {
        "status": "computing",
        "biomarkers": request.biomarker_slugs or "all",
        "window_days": request.window_days,
    }


@router.post("/deviation", response_model=DeviationResult)
def check_deviation(
    request: DeviationCheck,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> DeviationResult:
    """
    Check how much a value deviates from personal baseline.

    Returns z-score, percentile, and clinical interpretation.
    """
    # Get latest baseline
    result = db.execute(
        text("""
            SELECT mean, std_dev as std, p10, p25, p50 as median, p75, p90,
                   sample_count, window_days, computed_at
            FROM baselines
            WHERE biomarker_slug = :slug
            ORDER BY computed_at DESC
            LIMIT 1
        """),
        {"slug": request.biomarker_slug},
    )
    row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No baseline found for '{request.biomarker_slug}'",
        )

    # Build baseline object for the science layer
    baseline = BiomarkerBaseline(
        biomarker_slug=request.biomarker_slug,
        computed_at=row["computed_at"],
        window_days=row["window_days"],
        mean=row["mean"],
        std=row["std"],
        median=row["median"],
        p10=row["p10"],
        p25=row["p25"],
        p75=row["p75"],
        p90=row["p90"],
        sample_count=row["sample_count"],
        is_stable=True,
        coefficient_of_variation=row["std"] / row["mean"] if row["mean"] else 0,
    )

    deviation = compute_deviation_internal(request.value, baseline)

    return DeviationResult(
        biomarker_slug=deviation.biomarker_slug,
        observed_value=deviation.observed_value,
        baseline_mean=deviation.baseline_mean,
        baseline_std=deviation.baseline_std,
        z_score=deviation.z_score,
        percentile=deviation.percentile,
        deviation_pct=deviation.deviation_pct,
        is_notable=deviation.is_notable,
        is_significant=deviation.is_significant,
        direction=deviation.direction,
        clinical_note=deviation.clinical_note,
    )
