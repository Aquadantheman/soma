"""Proven statistical analysis endpoints.

Includes circadian rhythm, weekly activity, trends, anomalies, HRV, and SpO2.
All endpoints return results with confidence intervals and p-values.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...schemas import (
    CircadianAnalysis,
    WeeklyActivityAnalysis,
    TrendAnalysis,
    AnomalyAnalysis,
    HRVAnalysis,
    SpO2Analysis,
    FullAnalysisResult,
    HourlyPatternSchema,
    DayPatternSchema,
    YearlyStatSchema,
    AnomalyDaySchema,
)
from ._utils import load_signals
from ...auth import require_auth, AuthContext
from soma.statistics.proven import (
    analyze_circadian_rhythm,
    analyze_weekly_activity,
    analyze_long_term_trend,
    detect_anomalies,
    analyze_hrv,
    analyze_spo2,
)

router = APIRouter(tags=["proven"])


@router.get("/circadian", response_model=CircadianAnalysis)
def get_circadian_analysis(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> CircadianAnalysis:
    """
    Analyze circadian heart rate rhythm.

    Returns hourly patterns with 95% confidence intervals.
    Only marks as significant if CIs don't overlap.
    """
    df = load_signals(db)
    result = analyze_circadian_rhythm(df)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient heart rate data for circadian analysis (need 100+ samples)"
        )

    return CircadianAnalysis(
        hourly_patterns=[
            HourlyPatternSchema(
                hour=p.hour,
                mean=p.stats.mean,
                ci_lower=p.stats.ci_lower,
                ci_upper=p.stats.ci_upper,
                n=p.stats.n
            )
            for p in result.hourly_patterns
        ],
        lowest_hour=result.lowest_hour,
        lowest_hr_mean=result.lowest_hr.mean,
        lowest_hr_ci=(result.lowest_hr.ci_lower, result.lowest_hr.ci_upper),
        highest_hour=result.highest_hour,
        highest_hr_mean=result.highest_hr.mean,
        highest_hr_ci=(result.highest_hr.ci_lower, result.highest_hr.ci_upper),
        amplitude=result.amplitude,
        is_significant=result.is_significant,
        total_samples=result.total_samples
    )


@router.get("/weekly", response_model=WeeklyActivityAnalysis)
def get_weekly_analysis(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> WeeklyActivityAnalysis:
    """
    Analyze weekly activity patterns.

    Uses one-way ANOVA to test if activity differs by day.
    Returns p-value for statistical significance.
    """
    df = load_signals(db)
    result = analyze_weekly_activity(df)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient step data for weekly analysis"
        )

    return WeeklyActivityAnalysis(
        daily_patterns=[
            DayPatternSchema(
                day_name=p.day_name,
                day_number=p.day_number,
                mean=p.stats.mean,
                ci_lower=p.stats.ci_lower,
                ci_upper=p.stats.ci_upper,
                n=p.stats.n
            )
            for p in result.daily_patterns
        ],
        most_active_day=result.most_active_day,
        least_active_day=result.least_active_day,
        f_statistic=result.f_statistic,
        p_value=result.p_value,
        is_significant=result.is_significant,
        total_days=result.total_days
    )


@router.get("/trend", response_model=TrendAnalysis)
def get_trend_analysis(
    biomarker_slug: str = "heart_rate_resting",
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> TrendAnalysis:
    """
    Analyze long-term trend for a biomarker.

    Uses linear regression with significance testing.
    Only claims a trend if p < 0.05.
    """
    df = load_signals(db)
    result = analyze_long_term_trend(df, biomarker_slug)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient data for trend analysis on '{biomarker_slug}'"
        )

    return TrendAnalysis(
        yearly_stats=[
            YearlyStatSchema(
                year=s["year"],
                mean=s["mean"],
                ci_lower=s["ci_lower"],
                ci_upper=s["ci_upper"],
                n=s["n"]
            )
            for s in result.yearly_stats
        ],
        slope=result.slope,
        slope_ci=(result.slope_ci_lower, result.slope_ci_upper),
        r_squared=result.r_squared,
        p_value=result.p_value,
        is_significant=result.is_significant,
        direction=result.direction
    )


@router.get("/anomalies", response_model=AnomalyAnalysis)
def get_anomaly_analysis(
    biomarker_slug: str = "heart_rate",
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> AnomalyAnalysis:
    """
    Detect anomalous days using robust IQR method.

    Uses non-parametric statistics (median, IQR) which are
    more robust to outliers than mean/std.
    """
    df = load_signals(db)
    result = detect_anomalies(df, biomarker_slug)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient data for anomaly detection on '{biomarker_slug}'"
        )

    return AnomalyAnalysis(
        mean=result.mean,
        std=result.std,
        median=result.median,
        iqr=result.iqr,
        threshold_low=result.threshold_low,
        threshold_high=result.threshold_high,
        anomalies=[
            AnomalyDaySchema(
                date=str(a.date),
                value=a.value,
                z_score=a.z_score,
                direction=a.direction
            )
            for a in result.anomalies[:20]  # Limit to top 20
        ],
        total_days=result.total_days,
        anomaly_rate=result.anomaly_rate
    )


@router.get("/hrv", response_model=HRVAnalysis)
def get_hrv_analysis(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> HRVAnalysis:
    """
    Analyze HRV with automatic unit correction.

    Detects if HRV is stored in microseconds and converts to milliseconds.
    """
    df = load_signals(db)
    result = analyze_hrv(df)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient HRV data for analysis"
        )

    return HRVAnalysis(
        mean_ms=result.mean_ms.mean,
        ci_lower_ms=result.mean_ms.ci_lower,
        ci_upper_ms=result.mean_ms.ci_upper,
        n=result.mean_ms.n,
        assessment=result.assessment,
        unit_correction_applied=result.unit_correction_applied
    )


@router.get("/spo2", response_model=SpO2Analysis)
def get_spo2_analysis(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> SpO2Analysis:
    """
    Analyze SpO2 with clinical thresholds.

    Reports proportion below clinical thresholds (95%, 90%)
    with confidence intervals.
    """
    df = load_signals(db)
    result = analyze_spo2(df)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient SpO2 data for analysis"
        )

    return SpO2Analysis(
        mean_pct=result.mean.mean,
        ci_lower_pct=result.mean.ci_lower,
        ci_upper_pct=result.mean.ci_upper,
        n=result.mean.n,
        pct_below_95=result.pct_below_95,
        pct_below_95_ci=result.pct_below_95_ci,
        pct_below_90=result.pct_below_90,
        count_below_90=result.count_below_90,
        assessment=result.assessment
    )


@router.get("/full", response_model=FullAnalysisResult)
def get_full_analysis(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> FullAnalysisResult:
    """
    Run all statistical analyses and return proven/unproven claims.

    This is the main endpoint for getting a complete picture
    of what can be statistically proven from your data.
    """
    df = load_signals(db)

    proven = []
    unproven = []

    # Circadian
    circadian_result = None
    circadian = analyze_circadian_rhythm(df)
    if circadian:
        circadian_result = CircadianAnalysis(
            hourly_patterns=[
                HourlyPatternSchema(
                    hour=p.hour,
                    mean=p.stats.mean,
                    ci_lower=p.stats.ci_lower,
                    ci_upper=p.stats.ci_upper,
                    n=p.stats.n
                )
                for p in circadian.hourly_patterns
            ],
            lowest_hour=circadian.lowest_hour,
            lowest_hr_mean=circadian.lowest_hr.mean,
            lowest_hr_ci=(circadian.lowest_hr.ci_lower, circadian.lowest_hr.ci_upper),
            highest_hour=circadian.highest_hour,
            highest_hr_mean=circadian.highest_hr.mean,
            highest_hr_ci=(circadian.highest_hr.ci_lower, circadian.highest_hr.ci_upper),
            amplitude=circadian.amplitude,
            is_significant=circadian.is_significant,
            total_samples=circadian.total_samples
        )
        if circadian.is_significant:
            proven.append(
                f"Circadian HR variation: {circadian.amplitude:.1f} bpm swing "
                f"(lowest {circadian.lowest_hour}:00, highest {circadian.highest_hour}:00)"
            )

    # Weekly
    weekly_result = None
    weekly = analyze_weekly_activity(df)
    if weekly:
        weekly_result = WeeklyActivityAnalysis(
            daily_patterns=[
                DayPatternSchema(
                    day_name=p.day_name,
                    day_number=p.day_number,
                    mean=p.stats.mean,
                    ci_lower=p.stats.ci_lower,
                    ci_upper=p.stats.ci_upper,
                    n=p.stats.n
                )
                for p in weekly.daily_patterns
            ],
            most_active_day=weekly.most_active_day,
            least_active_day=weekly.least_active_day,
            f_statistic=weekly.f_statistic,
            p_value=weekly.p_value,
            is_significant=weekly.is_significant,
            total_days=weekly.total_days
        )
        if weekly.is_significant:
            proven.append(
                f"Weekly activity varies by day (ANOVA p={weekly.p_value:.4f}): "
                f"most active {weekly.most_active_day}, least active {weekly.least_active_day}"
            )

    # RHR Trend
    trend_result = None
    trend = analyze_long_term_trend(df)
    if trend:
        trend_result = TrendAnalysis(
            yearly_stats=[
                YearlyStatSchema(
                    year=s["year"],
                    mean=s["mean"],
                    ci_lower=s["ci_lower"],
                    ci_upper=s["ci_upper"],
                    n=s["n"]
                )
                for s in trend.yearly_stats
            ],
            slope=trend.slope,
            slope_ci=(trend.slope_ci_lower, trend.slope_ci_upper),
            r_squared=trend.r_squared,
            p_value=trend.p_value,
            is_significant=trend.is_significant,
            direction=trend.direction
        )
        if trend.is_significant:
            proven.append(
                f"RHR trend: {trend.direction} at {abs(trend.slope):.2f} bpm/year (p={trend.p_value:.4f})"
            )
        else:
            unproven.append(
                f"RHR trend: no significant change detected (p={trend.p_value:.3f})"
            )

    # Anomalies
    anomaly_result = None
    anomalies = detect_anomalies(df)
    if anomalies:
        anomaly_result = AnomalyAnalysis(
            mean=anomalies.mean,
            std=anomalies.std,
            median=anomalies.median,
            iqr=anomalies.iqr,
            threshold_low=anomalies.threshold_low,
            threshold_high=anomalies.threshold_high,
            anomalies=[
                AnomalyDaySchema(
                    date=str(a.date),
                    value=a.value,
                    z_score=a.z_score,
                    direction=a.direction
                )
                for a in anomalies.anomalies[:20]
            ],
            total_days=anomalies.total_days,
            anomaly_rate=anomalies.anomaly_rate
        )
        if anomalies.anomalies:
            proven.append(
                f"Anomaly detection: {len(anomalies.anomalies)} outlier days "
                f"({100*anomalies.anomaly_rate:.1f}% of days)"
            )

    # HRV
    hrv_result = None
    hrv = analyze_hrv(df)
    if hrv:
        hrv_result = HRVAnalysis(
            mean_ms=hrv.mean_ms.mean,
            ci_lower_ms=hrv.mean_ms.ci_lower,
            ci_upper_ms=hrv.mean_ms.ci_upper,
            n=hrv.mean_ms.n,
            assessment=hrv.assessment,
            unit_correction_applied=hrv.unit_correction_applied
        )
        proven.append(
            f"HRV SDNN: {hrv.mean_ms.mean:.1f} ms "
            f"(95% CI: [{hrv.mean_ms.ci_lower:.1f}, {hrv.mean_ms.ci_upper:.1f}]), "
            f"assessment: {hrv.assessment}"
        )

    # SpO2
    spo2_result = None
    spo2 = analyze_spo2(df)
    if spo2:
        spo2_result = SpO2Analysis(
            mean_pct=spo2.mean.mean,
            ci_lower_pct=spo2.mean.ci_lower,
            ci_upper_pct=spo2.mean.ci_upper,
            n=spo2.mean.n,
            pct_below_95=spo2.pct_below_95,
            pct_below_95_ci=spo2.pct_below_95_ci,
            pct_below_90=spo2.pct_below_90,
            count_below_90=spo2.count_below_90,
            assessment=spo2.assessment
        )
        proven.append(
            f"SpO2: {spo2.mean.mean:.1f}% mean, "
            f"{100*spo2.pct_below_95:.1f}% of readings below 95%"
        )

    # Standard unproven claims
    unproven.extend([
        "Causal relationships (correlation does not imply causation)",
        "Fitness 'improvement' claims (would need controlled study)",
        "Health predictions (this is descriptive, not predictive)"
    ])

    return FullAnalysisResult(
        circadian=circadian_result,
        weekly_activity=weekly_result,
        rhr_trend=trend_result,
        anomalies=anomaly_result,
        hrv=hrv_result,
        spo2=spo2_result,
        proven_claims=proven,
        unproven_claims=unproven
    )
