"""VO2 Max (Cardiorespiratory Fitness) analysis endpoints.

Provides rigorously validated analysis of VO2 Max:
- Percentile ranking vs age/sex norms (ACSM Guidelines)
- Fitness age calculation (HUNT Fitness Study)
- Mortality risk assessment (Kodama meta-analysis)
- Trend analysis with confidence intervals
- Training response detection

All methods cite peer-reviewed sources.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...database import get_db
from ...auth import require_auth, AuthContext
from ...schemas.vo2max import (
    VO2MaxMeasurementSchema,
    VO2MaxPercentileSchema,
    FitnessAgeSchema,
    VO2MaxTrendSchema,
    MortalityRiskSchema,
    TrainingResponseSchema,
    CorrelationSchema,
    VO2MaxReportSchema,
    VO2MaxSummarySchema,
)
from ._utils import load_signals

router = APIRouter()


def _measurement_to_schema(m) -> VO2MaxMeasurementSchema:
    """Convert VO2MaxMeasurement to schema."""
    return VO2MaxMeasurementSchema(
        date=m.date,
        value=m.value,
        mets=m.mets
    )


def _correlation_to_schema(corr_tuple, metric: str, expected: str) -> Optional[CorrelationSchema]:
    """Convert correlation tuple to schema."""
    if corr_tuple is None:
        return None
    r, p, n = corr_tuple
    return CorrelationSchema(
        metric=metric,
        r=r,
        p_value=p,
        n=n,
        is_significant=p < 0.05,
        literature_expected=expected
    )


@router.get("/vo2max", response_model=VO2MaxReportSchema)
def get_vo2max_analysis(
    age: Optional[int] = Query(None, description="Your age for percentile calculation"),
    sex: Optional[str] = Query(None, description="Your sex (male/female) for percentile calculation"),
    days: int = Query(730, description="Days of history to analyze"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get complete VO2 Max analysis with validated methods.

    All analyses use peer-reviewed sources:
    - Percentiles: ACSM Guidelines for Exercise Testing (11th ed)
    - Fitness Age: Nes et al. (2013), HUNT Fitness Study
    - Mortality Risk: Kodama et al. (2009), JAMA meta-analysis
    - Trend: OLS regression with 95% confidence intervals

    Optional: Provide age and sex for percentile ranking and fitness age.
    """
    from soma.statistics.vo2max import generate_vo2max_report

    df = load_signals(db, biomarker_slugs=["vo2_max"], days=days)

    if df is None or len(df) == 0:
        raise HTTPException(
            status_code=404,
            detail="No VO2 Max data found"
        )

    # Also load HRV and RHR for correlation analysis
    hrv_df = load_signals(db, biomarker_slugs=["hrv_sdnn"], days=days)
    rhr_df = load_signals(db, biomarker_slugs=["heart_rate_resting"], days=days)

    # Combine data for correlation analysis
    import pandas as pd
    all_data = df.copy()
    if hrv_df is not None:
        all_data = pd.concat([all_data, hrv_df], ignore_index=True)
    if rhr_df is not None:
        all_data = pd.concat([all_data, rhr_df], ignore_index=True)

    report = generate_vo2max_report(all_data, age=age, sex=sex)

    if report is None:
        raise HTTPException(status_code=404, detail="Unable to generate VO2 Max report")

    # Convert to schema
    percentile_schema = None
    if report.percentile:
        percentile_schema = VO2MaxPercentileSchema(
            percentile=report.percentile.percentile,
            category=report.percentile.category,
            comparison_group=report.percentile.comparison_group,
            reference=report.percentile.reference
        )

    fitness_age_schema = None
    if report.fitness_age:
        fitness_age_schema = FitnessAgeSchema(
            chronological_age=report.fitness_age.chronological_age,
            fitness_age=report.fitness_age.fitness_age,
            difference=report.fitness_age.difference,
            interpretation=report.fitness_age.interpretation,
            reference=report.fitness_age.reference
        )

    mortality_schema = MortalityRiskSchema(
        mets=report.mortality_risk.mets,
        risk_category=report.mortality_risk.risk_category,
        relative_risk=report.mortality_risk.relative_risk,
        interpretation=report.mortality_risk.interpretation,
        reference=report.mortality_risk.reference
    )

    trend_schema = None
    if report.trend:
        trend_schema = VO2MaxTrendSchema(
            period_days=report.trend.period_days,
            n_measurements=report.trend.n_measurements,
            start_value=report.trend.start_value,
            end_value=report.trend.end_value,
            change=report.trend.change,
            change_pct=report.trend.change_pct,
            slope=report.trend.slope,
            slope_annual=report.trend.slope_annual,
            ci_lower=report.trend.ci_lower,
            ci_upper=report.trend.ci_upper,
            p_value=report.trend.p_value,
            is_significant=report.trend.is_significant,
            interpretation=report.trend.interpretation
        )

    training_response_schema = None
    if report.training_response:
        training_response_schema = TrainingResponseSchema(
            baseline_vo2=report.training_response.baseline_vo2,
            current_vo2=report.training_response.current_vo2,
            change=report.training_response.change,
            change_pct=report.training_response.change_pct,
            is_responder=report.training_response.is_responder,
            response_category=report.training_response.response_category,
            interpretation=report.training_response.interpretation,
            reference=report.training_response.reference
        )

    hrv_corr = _correlation_to_schema(
        report.hrv_correlation, "HRV (SDNN)",
        "Positive correlation expected (r~0.3-0.5)"
    )
    rhr_corr = _correlation_to_schema(
        report.rhr_correlation, "Resting HR",
        "Negative correlation expected (r~-0.3 to -0.5)"
    )

    return VO2MaxReportSchema(
        latest_measurement=_measurement_to_schema(report.latest_measurement),
        percentile=percentile_schema,
        fitness_age=fitness_age_schema,
        mortality_risk=mortality_schema,
        measurements=[_measurement_to_schema(m) for m in report.measurements],
        trend=trend_schema,
        training_response=training_response_schema,
        hrv_correlation=hrv_corr,
        rhr_correlation=rhr_corr,
        insights=report.insights,
        recommendations=report.recommendations
    )


@router.get("/vo2max/summary", response_model=VO2MaxSummarySchema)
def get_vo2max_summary(
    age: Optional[int] = None,
    sex: Optional[str] = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get quick summary of VO2 Max fitness status.
    """
    from soma.statistics.vo2max import (
        compute_percentile, compute_mortality_risk, analyze_trend
    )

    df = load_signals(db, biomarker_slugs=["vo2_max"], days=730)

    if df is None or len(df) == 0:
        return VO2MaxSummarySchema(
            has_sufficient_data=False,
            n_measurements=0,
            latest_value=None,
            latest_mets=None,
            category=None,
            mortality_risk=None,
            trend_direction=None,
            overall_assessment="No VO2 Max data available"
        )

    import pandas as pd
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time')

    n = len(df)
    latest = df.iloc[-1]['value']
    latest_mets = round(latest / 3.5, 1)

    category = None
    if age is not None and sex is not None:
        pct = compute_percentile(latest, age, sex)
        category = pct.category

    risk = compute_mortality_risk(latest)
    mortality_risk = risk.risk_category

    trend_direction = None
    trend = analyze_trend(df)
    if trend and trend.is_significant:
        trend_direction = "Improving" if trend.slope > 0 else "Declining"
    elif trend:
        trend_direction = "Stable"

    if category:
        assessment = f"{category} fitness ({latest:.1f} mL/kg/min, {mortality_risk} mortality risk)"
    else:
        assessment = f"VO2 Max: {latest:.1f} mL/kg/min ({latest_mets} METs), {mortality_risk} mortality risk"

    return VO2MaxSummarySchema(
        has_sufficient_data=n >= 3,
        n_measurements=n,
        latest_value=round(latest, 1),
        latest_mets=latest_mets,
        category=category,
        mortality_risk=mortality_risk,
        trend_direction=trend_direction,
        overall_assessment=assessment
    )


@router.get("/vo2max/percentile", response_model=VO2MaxPercentileSchema)
def get_vo2max_percentile(
    age: int = Query(..., description="Your age"),
    sex: str = Query(..., description="Your sex (male/female)"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get percentile ranking for latest VO2 Max.

    Based on ACSM's Guidelines for Exercise Testing and Prescription (11th ed).
    """
    from soma.statistics.vo2max import compute_percentile

    df = load_signals(db, biomarker_slugs=["vo2_max"], days=365)

    if df is None or len(df) == 0:
        raise HTTPException(status_code=404, detail="No VO2 Max data found")

    import pandas as pd
    df['time'] = pd.to_datetime(df['time'])
    latest = df.sort_values('time').iloc[-1]['value']

    if sex.lower() not in ['male', 'female']:
        raise HTTPException(status_code=400, detail="Sex must be 'male' or 'female'")

    pct = compute_percentile(latest, age, sex)

    return VO2MaxPercentileSchema(
        percentile=pct.percentile,
        category=pct.category,
        comparison_group=pct.comparison_group,
        reference=pct.reference
    )


@router.get("/vo2max/fitness-age", response_model=FitnessAgeSchema)
def get_fitness_age(
    age: int = Query(..., description="Your chronological age"),
    sex: str = Query(..., description="Your sex (male/female)"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Calculate fitness age based on VO2 Max.

    Based on the HUNT Fitness Study (Nes et al., 2013).
    """
    from soma.statistics.vo2max import compute_fitness_age

    df = load_signals(db, biomarker_slugs=["vo2_max"], days=365)

    if df is None or len(df) == 0:
        raise HTTPException(status_code=404, detail="No VO2 Max data found")

    import pandas as pd
    df['time'] = pd.to_datetime(df['time'])
    latest = df.sort_values('time').iloc[-1]['value']

    if sex.lower() not in ['male', 'female']:
        raise HTTPException(status_code=400, detail="Sex must be 'male' or 'female'")

    fa = compute_fitness_age(latest, age, sex)

    return FitnessAgeSchema(
        chronological_age=fa.chronological_age,
        fitness_age=fa.fitness_age,
        difference=fa.difference,
        interpretation=fa.interpretation,
        reference=fa.reference
    )


@router.get("/vo2max/trend", response_model=VO2MaxTrendSchema)
def get_vo2max_trend(
    days: int = Query(365, description="Days to analyze"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get VO2 Max trend analysis with confidence intervals.

    Uses OLS regression with 95% CI for slope.
    """
    from soma.statistics.vo2max import analyze_trend

    df = load_signals(db, biomarker_slugs=["vo2_max"], days=days)

    if df is None or len(df) == 0:
        raise HTTPException(status_code=404, detail="No VO2 Max data found")

    trend = analyze_trend(df, min_measurements=5)

    if trend is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient data for trend analysis (need at least 5 measurements)"
        )

    return VO2MaxTrendSchema(
        period_days=trend.period_days,
        n_measurements=trend.n_measurements,
        start_value=trend.start_value,
        end_value=trend.end_value,
        change=trend.change,
        change_pct=trend.change_pct,
        slope=trend.slope,
        slope_annual=trend.slope_annual,
        ci_lower=trend.ci_lower,
        ci_upper=trend.ci_upper,
        p_value=trend.p_value,
        is_significant=trend.is_significant,
        interpretation=trend.interpretation
    )
