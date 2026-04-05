"""Daylight exposure analysis endpoints.

Provides API access to daylight exposure analysis:
- Daily daylight metrics
- Personal baselines with confidence intervals
- Deviation detection from your baseline
- Trend analysis over time
- Correlation with sleep metrics

Research Context:
- Morning light exposure (before 10am) most impactful for circadian rhythm
- ~30 min morning light helps regulate sleep-wake cycle
- Daylight exposure correlates with sleep quality, mood, and energy
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...auth import require_auth, AuthContext
from ...schemas.daylight import (
    DailyDaylightSchema,
    DaylightBaselineSchema,
    DaylightDeviationSchema,
    DaylightTrendSchema,
    DaylightSleepCorrelationSchema,
    DaylightReportSchema,
    DaylightSummary,
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


def _daily_to_schema(day) -> DailyDaylightSchema:
    """Convert DailyDaylight dataclass to schema."""
    return DailyDaylightSchema(
        date=day.date,
        total_min=day.total_min,
        morning_min=day.morning_min,
        midday_min=day.midday_min,
        afternoon_min=day.afternoon_min,
        has_morning_exposure=day.has_morning_exposure,
    )


@router.get("/daylight", response_model=DaylightReportSchema)
def get_daylight_analysis(
    days: int = 90,
    include_sleep_correlations: bool = True,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get complete daylight exposure analysis.

    Analyzes your daylight exposure data to provide:
    - Personal baseline for total and morning daylight
    - Recent daily breakdowns
    - Deviations from YOUR baseline
    - Trend analysis
    - Correlations with sleep metrics (if sleep data available)

    Research context:
    - 30+ min/day of daylight is beneficial
    - Morning light (before 10am) most impactful for circadian rhythm
    - Consistent exposure patterns support sleep-wake cycle
    """
    from soma.statistics.daylight import generate_daylight_report

    # Load daylight signals
    daylight_df = load_signals(db, biomarker_slugs=["time_in_daylight"], days=days)

    if daylight_df is None or len(daylight_df) < 7:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient daylight data. Need at least 7 days, found {len(daylight_df) if daylight_df is not None else 0} records.",
        )

    # Load sleep data for correlations (optional)
    sleep_df = None
    if include_sleep_correlations:
        sleep_df = load_signals(
            db,
            biomarker_slugs=["sleep_rem", "sleep_deep", "sleep_core", "sleep_in_bed"],
            days=days,
        )

    report = generate_daylight_report(
        daylight_df, sleep_df=sleep_df, baseline_days=days, trend_days=min(30, days)
    )

    # Convert to schema
    baseline_schema = None
    if report.baseline:
        baseline_schema = DaylightBaselineSchema(
            computed_at=report.baseline.computed_at.isoformat(),
            n_days=report.baseline.n_days,
            total_daylight=_ci_to_dict(report.baseline.total_daylight),
            morning_daylight=_ci_to_dict(report.baseline.morning_daylight),
            midday_daylight=_ci_to_dict(report.baseline.midday_daylight),
            afternoon_daylight=_ci_to_dict(report.baseline.afternoon_daylight),
            pct_days_with_morning_light=report.baseline.pct_days_with_morning_light,
            morning_light_mean=report.baseline.morning_light_mean,
            variability_score=report.baseline.variability_score,
            is_sufficient=report.baseline.is_sufficient,
            consistency_score=report.baseline.consistency_score,
        )

    recent_days_schema = [_daily_to_schema(d) for d in report.recent_days]

    deviation_schema = None
    if report.current_deviation:
        d = report.current_deviation
        deviation_schema = DaylightDeviationSchema(
            date=d.date,
            total_z=d.total_z,
            morning_z=d.morning_z,
            is_low=d.is_low,
            is_no_morning_light=d.is_no_morning_light,
            is_notable=d.is_notable,
            interpretation=d.interpretation,
        )

    trend_schema = None
    if report.trend:
        t = report.trend
        trend_schema = DaylightTrendSchema(
            period_days=t.period_days,
            slope=t.slope,
            slope_pct=t.slope_pct,
            p_value=t.p_value,
            r_squared=t.r_squared,
            is_significant=t.is_significant,
            direction=t.direction,
            interpretation=t.interpretation,
        )

    correlations_schema = [
        DaylightSleepCorrelationSchema(
            sleep_metric=c.sleep_metric,
            lag_days=c.lag_days,
            correlation=c.correlation,
            p_value=c.p_value,
            n_pairs=c.n_pairs,
            is_significant=c.is_significant,
            interpretation=c.interpretation,
        )
        for c in report.sleep_correlations
    ]

    return DaylightReportSchema(
        baseline=baseline_schema,
        recent_days=recent_days_schema,
        current_deviation=deviation_schema,
        trend=trend_schema,
        sleep_correlations=correlations_schema,
        avg_daily_min_30d=report.avg_daily_min_30d,
        avg_morning_min_30d=report.avg_morning_min_30d,
        pct_days_morning_light_30d=report.pct_days_morning_light_30d,
        concerns=report.concerns,
        insights=report.insights,
    )


@router.get("/daylight/daily", response_model=List[DailyDaylightSchema])
def get_daily_daylight(
    days: int = 30,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get daily daylight breakdown.

    Returns individual days with:
    - Total daylight minutes
    - Morning, midday, afternoon breakdown
    - Whether meaningful morning exposure occurred
    """
    from soma.statistics.daylight import compute_daily_daylight

    df = load_signals(db, biomarker_slugs=["time_in_daylight"], days=days)

    if df is None or len(df) == 0:
        return []

    daily = compute_daily_daylight(df)
    return [_daily_to_schema(d) for d in daily]


@router.get("/daylight/summary", response_model=DaylightSummary)
def get_daylight_summary(
    days: int = 30,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get quick daylight health summary.

    Returns a brief overview of your daylight exposure patterns.
    """
    from soma.statistics.daylight import (
        compute_daylight_baseline,
        compute_daily_daylight,
    )
    import numpy as np

    df = load_signals(db, biomarker_slugs=["time_in_daylight"], days=days)

    if df is None or len(df) == 0:
        return DaylightSummary(
            has_sufficient_data=False,
            n_days_analyzed=0,
            avg_daily_min=None,
            avg_morning_min=None,
            pct_days_morning_light=None,
            is_sufficient=None,
            consistency_score=None,
            top_concern=None,
            overall_assessment="Insufficient daylight exposure data",
        )

    daily = compute_daily_daylight(df)
    baseline = compute_daylight_baseline(df, window_days=days, min_days=7)

    if len(daily) < 7:
        return DaylightSummary(
            has_sufficient_data=False,
            n_days_analyzed=len(daily),
            avg_daily_min=None,
            avg_morning_min=None,
            pct_days_morning_light=None,
            is_sufficient=None,
            consistency_score=None,
            top_concern=None,
            overall_assessment=f"Need at least 7 days, found {len(daily)}",
        )

    avg_daily = float(np.mean([d.total_min for d in daily]))
    avg_morning = float(np.mean([d.morning_min for d in daily]))
    pct_morning = float(np.mean([d.has_morning_exposure for d in daily]) * 100)

    # Generate assessment
    concerns = []
    if avg_daily < 30:
        concerns.append(f"Low average daylight ({avg_daily:.0f} min/day)")
    if pct_morning < 50:
        concerns.append(f"Low morning light ({pct_morning:.0f}% of days)")

    if not concerns:
        assessment = "Healthy daylight exposure patterns"
    elif len(concerns) == 1:
        assessment = f"One area to watch: {concerns[0]}"
    else:
        assessment = f"Multiple concerns: {', '.join(concerns)}"

    return DaylightSummary(
        has_sufficient_data=True,
        n_days_analyzed=len(daily),
        avg_daily_min=avg_daily,
        avg_morning_min=avg_morning,
        pct_days_morning_light=pct_morning,
        is_sufficient=baseline.is_sufficient if baseline else None,
        consistency_score=baseline.consistency_score if baseline else None,
        top_concern=concerns[0] if concerns else None,
        overall_assessment=assessment,
    )


@router.get("/daylight/trend", response_model=DaylightTrendSchema)
def get_daylight_trend(
    days: int = 30,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get trend analysis for daylight exposure.

    Analyzes whether your daylight exposure is increasing,
    decreasing, or stable over the specified period.
    """
    from soma.statistics.daylight import analyze_daylight_trend

    df = load_signals(db, biomarker_slugs=["time_in_daylight"], days=days)

    if df is None or len(df) == 0:
        raise HTTPException(status_code=404, detail="No daylight data found")

    trend = analyze_daylight_trend(df, period_days=days)

    if trend is None:
        raise HTTPException(
            status_code=404, detail="Insufficient data for trend analysis"
        )

    return DaylightTrendSchema(
        period_days=trend.period_days,
        slope=trend.slope,
        slope_pct=trend.slope_pct,
        p_value=trend.p_value,
        r_squared=trend.r_squared,
        is_significant=trend.is_significant,
        direction=trend.direction,
        interpretation=trend.interpretation,
    )


@router.get(
    "/daylight/sleep-correlation", response_model=List[DaylightSleepCorrelationSchema]
)
def get_daylight_sleep_correlations(
    days: int = 90,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get correlations between daylight exposure and sleep metrics.

    Analyzes how your daylight exposure relates to:
    - Total sleep duration
    - REM sleep percentage
    - Deep sleep percentage
    - Sleep efficiency

    Tests both same-night and next-night relationships.
    """
    from soma.statistics.daylight import compute_daylight_sleep_correlation

    daylight_df = load_signals(db, biomarker_slugs=["time_in_daylight"], days=days)

    sleep_df = load_signals(
        db,
        biomarker_slugs=["sleep_rem", "sleep_deep", "sleep_core", "sleep_in_bed"],
        days=days,
    )

    if daylight_df is None or len(daylight_df) == 0:
        raise HTTPException(status_code=404, detail="No daylight data found")

    if sleep_df is None or len(sleep_df) == 0:
        raise HTTPException(status_code=404, detail="No sleep data found")

    correlations = []
    for metric in ["total_sleep_min", "rem_pct", "deep_pct", "efficiency"]:
        for lag in [0, 1]:
            corr = compute_daylight_sleep_correlation(
                daylight_df, sleep_df, metric, lag
            )
            if corr:
                correlations.append(
                    DaylightSleepCorrelationSchema(
                        sleep_metric=corr.sleep_metric,
                        lag_days=corr.lag_days,
                        correlation=corr.correlation,
                        p_value=corr.p_value,
                        n_pairs=corr.n_pairs,
                        is_significant=corr.is_significant,
                        interpretation=corr.interpretation,
                    )
                )

    return correlations
