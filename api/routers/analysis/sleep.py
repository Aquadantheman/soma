"""Sleep architecture analysis endpoints.

Provides API access to sleep architecture analysis:
- Nightly sleep metrics (REM%, Deep%, Efficiency)
- Personal baselines with confidence intervals
- Deviation detection from your baseline
- Trend analysis over time
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...auth import require_auth, AuthContext
from ...schemas.sleep import (
    NightlySleepSchema,
    SleepArchitectureBaselineSchema,
    SleepArchitectureDeviationSchema,
    SleepArchitectureTrendSchema,
    SleepArchitectureReportSchema,
    SleepSummary,
)
from ._utils import load_signals

router = APIRouter()


def _ci_to_dict(ci) -> dict:
    """Convert ConfidenceInterval to dict."""
    return {
        "mean": ci.mean,
        "ci_lower": ci.ci_lower,
        "ci_upper": ci.ci_upper,
        "n": ci.n,
        "confidence": ci.confidence,
    }


def _nightly_to_schema(night) -> NightlySleepSchema:
    """Convert NightlySleep dataclass to schema."""
    return NightlySleepSchema(
        date=night.date,
        rem_min=night.rem_min,
        deep_min=night.deep_min,
        core_min=night.core_min,
        in_bed_min=night.in_bed_min,
        total_sleep_min=night.total_sleep_min,
        rem_pct=night.rem_pct,
        deep_pct=night.deep_pct,
        core_pct=night.core_pct,
        efficiency=night.efficiency,
    )


@router.get("/sleep", response_model=SleepArchitectureReportSchema)
def get_sleep_architecture(
    days: int = 90,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get complete sleep architecture analysis.

    Analyzes your sleep stage data to provide:
    - Personal baseline for REM%, Deep%, Efficiency
    - Recent nightly breakdowns
    - Deviations from YOUR baseline
    - Trend analysis

    Clinical context:
    - Normal REM%: 20-25% of total sleep
    - Normal Deep%: 13-23% (decreases with age)
    - Normal Efficiency: >85%

    But what matters is YOUR personal distribution.
    """
    from soma.statistics.sleep import generate_sleep_report

    # Load sleep stage signals
    df = load_signals(
        db,
        biomarker_slugs=["sleep_rem", "sleep_deep", "sleep_core", "sleep_in_bed"],
        days=days,
    )

    if df is None or len(df) < 14:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient sleep data. Need at least 14 nights, found {len(df) if df is not None else 0} records.",
        )

    report = generate_sleep_report(df, baseline_days=days, trend_days=min(30, days))

    # Convert to schema
    baseline_schema = None
    if report.baseline:
        baseline_schema = SleepArchitectureBaselineSchema(
            computed_at=report.baseline.computed_at.isoformat(),
            n_nights=report.baseline.n_nights,
            total_sleep=_ci_to_dict(report.baseline.total_sleep),
            rem_duration=_ci_to_dict(report.baseline.rem_duration),
            deep_duration=_ci_to_dict(report.baseline.deep_duration),
            core_duration=_ci_to_dict(report.baseline.core_duration),
            in_bed_duration=_ci_to_dict(report.baseline.in_bed_duration),
            rem_pct=_ci_to_dict(report.baseline.rem_pct),
            deep_pct=_ci_to_dict(report.baseline.deep_pct),
            core_pct=_ci_to_dict(report.baseline.core_pct),
            efficiency=_ci_to_dict(report.baseline.efficiency),
            is_stable=report.baseline.is_stable,
            consistency_score=report.baseline.consistency_score,
        )

    recent_nights_schema = [_nightly_to_schema(n) for n in report.recent_nights]

    deviation_schema = None
    if report.current_deviation:
        d = report.current_deviation
        deviation_schema = SleepArchitectureDeviationSchema(
            date=d.date,
            total_sleep_z=d.total_sleep_z,
            rem_pct_z=d.rem_pct_z,
            deep_pct_z=d.deep_pct_z,
            efficiency_z=d.efficiency_z,
            is_rem_low=d.is_rem_low,
            is_deep_low=d.is_deep_low,
            is_efficiency_low=d.is_efficiency_low,
            is_notable=d.is_notable,
            interpretation=d.interpretation,
        )

    trends_schema = [
        SleepArchitectureTrendSchema(
            metric=t.metric,
            period_days=t.period_days,
            slope=t.slope,
            slope_pct=t.slope_pct,
            p_value=t.p_value,
            r_squared=t.r_squared,
            is_significant=t.is_significant,
            direction=t.direction,
            interpretation=t.interpretation,
        )
        for t in report.trends
    ]

    return SleepArchitectureReportSchema(
        baseline=baseline_schema,
        recent_nights=recent_nights_schema,
        current_deviation=deviation_schema,
        trends=trends_schema,
        concerns=report.concerns,
        insights=report.insights,
        avg_rem_pct_30d=report.avg_rem_pct_30d,
        avg_deep_pct_30d=report.avg_deep_pct_30d,
        avg_efficiency_30d=report.avg_efficiency_30d,
    )


@router.get("/sleep/nights", response_model=List[NightlySleepSchema])
def get_nightly_sleep(
    days: int = 30,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get nightly sleep breakdown.

    Returns individual nights with:
    - Duration in each sleep stage (REM, Deep, Core)
    - Percentages of total sleep
    - Sleep efficiency
    """
    from soma.statistics.sleep import compute_nightly_sleep

    df = load_signals(
        db,
        biomarker_slugs=["sleep_rem", "sleep_deep", "sleep_core", "sleep_in_bed"],
        days=days,
    )

    if df is None or len(df) == 0:
        return []

    nights = compute_nightly_sleep(df)
    return [_nightly_to_schema(n) for n in nights]


@router.get("/sleep/summary", response_model=SleepSummary)
def get_sleep_summary(
    days: int = 30,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get quick sleep health summary.

    Returns a brief overview of your sleep architecture health.
    """
    from soma.statistics.sleep import compute_sleep_baseline, compute_nightly_sleep

    df = load_signals(
        db,
        biomarker_slugs=["sleep_rem", "sleep_deep", "sleep_core", "sleep_in_bed"],
        days=days,
    )

    if df is None or len(df) == 0:
        return SleepSummary(
            has_sufficient_data=False,
            n_nights_analyzed=0,
            avg_total_sleep_min=None,
            avg_rem_pct=None,
            avg_deep_pct=None,
            avg_efficiency=None,
            consistency_score=None,
            top_concern=None,
            overall_assessment="Insufficient sleep stage data",
        )

    nights = compute_nightly_sleep(df)
    baseline = compute_sleep_baseline(df, window_days=days, min_nights=7)

    if len(nights) < 7:
        return SleepSummary(
            has_sufficient_data=False,
            n_nights_analyzed=len(nights),
            avg_total_sleep_min=None,
            avg_rem_pct=None,
            avg_deep_pct=None,
            avg_efficiency=None,
            consistency_score=None,
            top_concern=None,
            overall_assessment=f"Need at least 7 nights, found {len(nights)}",
        )

    import numpy as np

    avg_total = float(np.mean([n.total_sleep_min for n in nights]))
    avg_rem = float(np.mean([n.rem_pct for n in nights]))
    avg_deep = float(np.mean([n.deep_pct for n in nights]))
    avg_eff = float(np.mean([n.efficiency for n in nights]))

    # Generate assessment
    concerns = []
    if avg_rem < 15:
        concerns.append(f"Low REM% ({avg_rem:.1f}%)")
    if avg_deep < 10:
        concerns.append(f"Low deep sleep ({avg_deep:.1f}%)")
    if avg_eff < 85:
        concerns.append(f"Low efficiency ({avg_eff:.1f}%)")

    if not concerns:
        assessment = "Healthy sleep architecture"
    elif len(concerns) == 1:
        assessment = f"One area to watch: {concerns[0]}"
    else:
        assessment = f"Multiple concerns: {', '.join(concerns)}"

    return SleepSummary(
        has_sufficient_data=True,
        n_nights_analyzed=len(nights),
        avg_total_sleep_min=avg_total,
        avg_rem_pct=avg_rem,
        avg_deep_pct=avg_deep,
        avg_efficiency=avg_eff,
        consistency_score=baseline.consistency_score if baseline else None,
        top_concern=concerns[0] if concerns else None,
        overall_assessment=assessment,
    )


@router.get("/sleep/trend/{metric}", response_model=SleepArchitectureTrendSchema)
def get_sleep_trend(
    metric: str,
    days: int = 30,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get trend analysis for a specific sleep metric.

    Valid metrics: rem_pct, deep_pct, core_pct, efficiency, total_sleep_min
    """
    from soma.statistics.sleep import analyze_sleep_trend

    valid_metrics = ["rem_pct", "deep_pct", "core_pct", "efficiency", "total_sleep_min"]
    if metric not in valid_metrics:
        raise HTTPException(
            status_code=400, detail=f"Invalid metric. Must be one of: {valid_metrics}"
        )

    df = load_signals(
        db,
        biomarker_slugs=["sleep_rem", "sleep_deep", "sleep_core", "sleep_in_bed"],
        days=days,
    )

    if df is None or len(df) == 0:
        raise HTTPException(status_code=404, detail="No sleep data found")

    trend = analyze_sleep_trend(df, metric=metric, period_days=days)

    if trend is None:
        raise HTTPException(
            status_code=404, detail="Insufficient data for trend analysis"
        )

    return SleepArchitectureTrendSchema(
        metric=trend.metric,
        period_days=trend.period_days,
        slope=trend.slope,
        slope_pct=trend.slope_pct,
        p_value=trend.p_value,
        r_squared=trend.r_squared,
        is_significant=trend.is_significant,
        direction=trend.direction,
        interpretation=trend.interpretation,
    )
