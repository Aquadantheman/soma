"""Stability analysis endpoints.

Assesses data quality, convergence, temporal stability, and drift detection.
Critical for understanding the reliability of statistical inferences.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...auth import require_auth, AuthContext
from ...schemas import (
    ConvergencePointSchema,
    ConvergenceAnalysisSchema,
    TemporalStabilitySchema,
    DriftResultSchema,
    SampleAdequacySchema,
    StabilityReportSchema,
)
from ._utils import load_signals
from soma.statistics.stability import (
    analyze_convergence,
    analyze_drift,
    analyze_sample_adequacy,
    generate_stability_report,
)

router = APIRouter(prefix="/stability", tags=["stability"])


def _convergence_to_schema(c) -> ConvergenceAnalysisSchema:
    """Convert convergence result to schema."""
    return ConvergenceAnalysisSchema(
        biomarker_slug=c.biomarker_slug,
        current_n=c.current_n,
        current_mean=c.current_mean,
        current_ci_width=c.current_ci_width,
        convergence_points=[
            ConvergencePointSchema(
                n=p.n,
                mean=p.mean,
                ci_width=p.ci_width,
                ci_pct=p.ci_pct,
                status=p.status,
            )
            for p in c.convergence_points
        ],
        min_n_for_stability=c.min_n_for_stability,
        is_stable=c.is_stable,
        drift_from_initial=c.drift_from_initial,
    )


def _temporal_to_schema(t) -> TemporalStabilitySchema:
    """Convert temporal stability result to schema."""
    return TemporalStabilitySchema(
        biomarker_slug=t.biomarker_slug,
        metric=t.metric,
        periods=t.periods,
        mean_value=t.mean_value,
        std_across_periods=t.std_across_periods,
        is_stable=t.is_stable,
        consistency_pct=t.consistency_pct,
    )


def _drift_to_schema(d) -> DriftResultSchema:
    """Convert drift result to schema."""
    return DriftResultSchema(
        biomarker_slug=d.biomarker_slug,
        recent_mean=d.recent_mean,
        recent_n=d.recent_n,
        historical_mean=d.historical_mean,
        historical_n=d.historical_n,
        absolute_change=d.absolute_change,
        pct_change=d.pct_change,
        t_statistic=d.t_statistic,
        p_value=d.p_value,
        is_significant=d.is_significant,
        direction=d.direction,
    )


def _adequacy_to_schema(s) -> SampleAdequacySchema:
    """Convert sample adequacy result to schema."""
    return SampleAdequacySchema(
        biomarker_slug=s.biomarker_slug,
        current_n=s.current_n,
        required_n_5pct=s.required_n_5pct,
        required_n_2pct=s.required_n_2pct,
        is_adequate=s.is_adequate,
        adequacy_ratio=s.adequacy_ratio,
    )


@router.get("", response_model=StabilityReportSchema)
def get_stability_report(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> StabilityReportSchema:
    """
    Generate a complete stability assessment of your data.

    Analyzes:
    - Convergence: How estimates stabilize with increasing sample size
    - Temporal stability: Whether patterns hold across different years
    - Drift: Recent vs historical data comparison
    - Sample adequacy: Whether you have enough data for reliable inference

    Returns recommendations for improving data quality.
    """
    df = load_signals(db)
    result = generate_stability_report(df)

    return StabilityReportSchema(
        convergence=[_convergence_to_schema(c) for c in result.convergence],
        temporal_stability=[_temporal_to_schema(t) for t in result.temporal_stability],
        drift=[_drift_to_schema(d) for d in result.drift],
        sample_adequacy=[_adequacy_to_schema(s) for s in result.sample_adequacy],
        overall_assessment=result.overall_assessment,
        recommendations=result.recommendations,
    )


@router.get("/convergence/{biomarker_slug}", response_model=ConvergenceAnalysisSchema)
def get_convergence_analysis(
    biomarker_slug: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> ConvergenceAnalysisSchema:
    """
    Analyze how estimates converge for a specific biomarker.

    Shows how the mean estimate and confidence interval width change
    as sample size increases. Useful for determining if you have
    enough data for reliable inference.
    """
    df = load_signals(db)
    result = analyze_convergence(df, biomarker_slug)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient data for convergence analysis on '{biomarker_slug}' (need 100+ samples)",
        )

    return _convergence_to_schema(result)


@router.get("/drift/{biomarker_slug}", response_model=DriftResultSchema)
def get_drift_analysis(
    biomarker_slug: str,
    recent_days: int = 365,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> DriftResultSchema:
    """
    Compare recent data to historical data for a specific biomarker.

    Detects if your baseline is shifting over time using
    two-sample t-test.

    Parameters:
    - biomarker_slug: The biomarker to analyze
    - recent_days: Number of days to consider as "recent" (default: 365)
    """
    df = load_signals(db)
    result = analyze_drift(df, biomarker_slug, recent_days=recent_days)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient data for drift analysis on '{biomarker_slug}'",
        )

    return _drift_to_schema(result)


@router.get("/adequacy/{biomarker_slug}", response_model=SampleAdequacySchema)
def get_sample_adequacy(
    biomarker_slug: str,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> SampleAdequacySchema:
    """
    Determine if sample size is adequate for reliable inference.

    Calculates the minimum number of samples needed for:
    - 5% precision (CI width < 5% of mean)
    - 2% precision (CI width < 2% of mean)

    Compares to your current sample count.
    """
    df = load_signals(db)
    result = analyze_sample_adequacy(df, biomarker_slug)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient data for adequacy analysis on '{biomarker_slug}'",
        )

    return _adequacy_to_schema(result)
