"""Body Composition analysis endpoints.

Provides rigorously validated analysis of body composition:
- BMI with WHO classification
- Body fat percentile vs ACSM age/sex norms
- Weight trend analysis with confidence intervals
- Body composition change assessment
- Validated fitness correlations

All methods cite peer-reviewed sources.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...database import get_db
from ...auth import require_auth, AuthContext
from ...schemas.body_composition import (
    BMISchema,
    BodyFatPercentileSchema,
    WeightMeasurementSchema,
    WeightTrendSchema,
    BodyCompositionChangeSchema,
    FitnessCorrelationSchema,
    BodyCompositionReportSchema,
    BodyCompositionSummarySchema,
)
from ._utils import load_signals

router = APIRouter()


def _measurement_to_schema(m) -> WeightMeasurementSchema:
    """Convert WeightMeasurement to schema."""
    return WeightMeasurementSchema(
        date=m.date,
        weight_kg=m.weight_kg,
        weight_lb=m.weight_lb,
        bmi=m.bmi,
        body_fat_pct=m.body_fat_pct,
        lean_mass_kg=m.lean_mass_kg,
        fat_mass_kg=m.fat_mass_kg
    )


@router.get("/body-composition", response_model=BodyCompositionReportSchema)
def get_body_composition_analysis(
    height_m: Optional[float] = Query(None, description="Your height in meters for BMI calculation"),
    age: Optional[int] = Query(None, description="Your age for body fat percentile"),
    sex: Optional[str] = Query(None, description="Your sex (male/female) for body fat percentile"),
    days: int = Query(730, description="Days of history to analyze"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get complete body composition analysis with validated methods.

    All analyses use peer-reviewed sources:
    - BMI: WHO Technical Report Series 894 (2000)
    - Body Fat Percentile: ACSM Guidelines (11th ed, 2022)
    - Trend: OLS regression with 95% confidence intervals

    Optional: Provide height for BMI, age and sex for body fat percentile.
    """
    from soma.statistics.body_composition import generate_body_composition_report

    # Load body composition data
    df = load_signals(
        db,
        biomarker_slugs=["body_mass", "body_fat_percentage", "lean_body_mass"],
        days=days
    )

    if df is None or len(df) == 0:
        raise HTTPException(
            status_code=404,
            detail="No body composition data found"
        )

    # Also load fitness metrics for correlation analysis
    import pandas as pd
    vo2_df = load_signals(db, biomarker_slugs=["vo2_max"], days=days)
    rhr_df = load_signals(db, biomarker_slugs=["heart_rate_resting"], days=days)

    all_data = df.copy()
    if vo2_df is not None:
        all_data = pd.concat([all_data, vo2_df], ignore_index=True)
    if rhr_df is not None:
        all_data = pd.concat([all_data, rhr_df], ignore_index=True)

    report = generate_body_composition_report(
        all_data,
        height_m=height_m,
        age=age,
        sex=sex
    )

    if report is None:
        raise HTTPException(status_code=404, detail="Unable to generate body composition report")

    # Convert to schema
    bmi_schema = None
    if report.bmi:
        bmi_schema = BMISchema(
            bmi=report.bmi.bmi,
            category=report.bmi.category,
            health_risk=report.bmi.health_risk,
            reference=report.bmi.reference
        )

    bf_percentile_schema = None
    if report.body_fat_percentile:
        bf_percentile_schema = BodyFatPercentileSchema(
            body_fat_pct=report.body_fat_percentile.body_fat_pct,
            percentile=report.body_fat_percentile.percentile,
            category=report.body_fat_percentile.category,
            comparison_group=report.body_fat_percentile.comparison_group,
            is_healthy=report.body_fat_percentile.is_healthy,
            healthy_range=list(report.body_fat_percentile.healthy_range),
            reference=report.body_fat_percentile.reference
        )

    trend_schema = None
    if report.weight_trend:
        trend_schema = WeightTrendSchema(
            period_days=report.weight_trend.period_days,
            n_measurements=report.weight_trend.n_measurements,
            start_weight=report.weight_trend.start_weight,
            end_weight=report.weight_trend.end_weight,
            change_kg=report.weight_trend.change_kg,
            change_pct=report.weight_trend.change_pct,
            slope_daily=report.weight_trend.slope_daily,
            slope_weekly=report.weight_trend.slope_weekly,
            ci_lower=report.weight_trend.ci_lower,
            ci_upper=report.weight_trend.ci_upper,
            p_value=report.weight_trend.p_value,
            is_significant=report.weight_trend.is_significant,
            direction=report.weight_trend.direction,
            interpretation=report.weight_trend.interpretation
        )

    change_schema = None
    if report.composition_change:
        change_schema = BodyCompositionChangeSchema(
            period_days=report.composition_change.period_days,
            n_measurements=report.composition_change.n_measurements,
            weight_change_kg=report.composition_change.weight_change_kg,
            body_fat_change_pct=report.composition_change.body_fat_change_pct,
            lean_mass_change_kg=report.composition_change.lean_mass_change_kg,
            fat_mass_change_kg=report.composition_change.fat_mass_change_kg,
            composition_quality=report.composition_change.composition_quality,
            interpretation=report.composition_change.interpretation
        )

    vo2_corr_schema = None
    if report.vo2max_correlation:
        vo2_corr_schema = FitnessCorrelationSchema(
            metric=report.vo2max_correlation.metric,
            r=report.vo2max_correlation.r,
            p_value=report.vo2max_correlation.p_value,
            n=report.vo2max_correlation.n,
            is_significant=report.vo2max_correlation.is_significant,
            direction=report.vo2max_correlation.direction,
            interpretation=report.vo2max_correlation.interpretation
        )

    rhr_corr_schema = None
    if report.rhr_correlation:
        rhr_corr_schema = FitnessCorrelationSchema(
            metric=report.rhr_correlation.metric,
            r=report.rhr_correlation.r,
            p_value=report.rhr_correlation.p_value,
            n=report.rhr_correlation.n,
            is_significant=report.rhr_correlation.is_significant,
            direction=report.rhr_correlation.direction,
            interpretation=report.rhr_correlation.interpretation
        )

    return BodyCompositionReportSchema(
        latest_measurement=_measurement_to_schema(report.latest_measurement),
        bmi=bmi_schema,
        body_fat_percentile=bf_percentile_schema,
        measurements=[_measurement_to_schema(m) for m in report.measurements],
        weight_trend=trend_schema,
        composition_change=change_schema,
        vo2max_correlation=vo2_corr_schema,
        rhr_correlation=rhr_corr_schema,
        insights=report.insights,
        recommendations=report.recommendations
    )


@router.get("/body-composition/summary", response_model=BodyCompositionSummarySchema)
def get_body_composition_summary(
    height_m: Optional[float] = None,
    age: Optional[int] = None,
    sex: Optional[str] = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get quick summary of body composition status.
    """
    from soma.statistics.body_composition import get_body_composition_summary

    df = load_signals(
        db,
        biomarker_slugs=["body_mass", "body_fat_percentage", "lean_body_mass"],
        days=730
    )

    if df is None:
        import pandas as pd
        df = pd.DataFrame(columns=['time', 'biomarker_slug', 'value'])

    summary = get_body_composition_summary(df, height_m=height_m, age=age, sex=sex)

    return BodyCompositionSummarySchema(
        has_sufficient_data=summary.has_sufficient_data,
        n_weight_measurements=summary.n_weight_measurements,
        n_body_fat_measurements=summary.n_body_fat_measurements,
        latest_weight_kg=summary.latest_weight_kg,
        latest_bmi=summary.latest_bmi,
        bmi_category=summary.bmi_category,
        latest_body_fat_pct=summary.latest_body_fat_pct,
        body_fat_category=summary.body_fat_category,
        weight_trend_direction=summary.weight_trend_direction,
        overall_assessment=summary.overall_assessment
    )


@router.get("/body-composition/bmi", response_model=BMISchema)
def get_bmi_analysis(
    height_m: float = Query(..., description="Your height in meters"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get BMI calculation with WHO classification.

    Reference: WHO Technical Report Series 894 (2000)
    """
    from soma.statistics.body_composition import compute_bmi

    df = load_signals(db, biomarker_slugs=["body_mass"], days=365)

    if df is None or len(df) == 0:
        raise HTTPException(status_code=404, detail="No weight data found")

    import pandas as pd
    df['time'] = pd.to_datetime(df['time'])
    latest_weight = df.sort_values('time').iloc[-1]['value']

    bmi_result = compute_bmi(latest_weight, height_m)

    return BMISchema(
        bmi=bmi_result.bmi,
        category=bmi_result.category,
        health_risk=bmi_result.health_risk,
        reference=bmi_result.reference
    )


@router.get("/body-composition/body-fat", response_model=BodyFatPercentileSchema)
def get_body_fat_percentile(
    age: int = Query(..., description="Your age"),
    sex: str = Query(..., description="Your sex (male/female)"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get body fat percentile ranking vs ACSM norms.

    Reference: ACSM's Guidelines for Exercise Testing and Prescription, 11th ed.
    """
    from soma.statistics.body_composition import compute_body_fat_percentile

    df = load_signals(db, biomarker_slugs=["body_fat_percentage"], days=365)

    if df is None or len(df) == 0:
        raise HTTPException(status_code=404, detail="No body fat data found")

    import pandas as pd
    df['time'] = pd.to_datetime(df['time'])
    latest_bf = df.sort_values('time').iloc[-1]['value']

    if sex.lower() not in ['male', 'female']:
        raise HTTPException(status_code=400, detail="Sex must be 'male' or 'female'")

    result = compute_body_fat_percentile(latest_bf, age, sex)

    return BodyFatPercentileSchema(
        body_fat_pct=result.body_fat_pct,
        percentile=result.percentile,
        category=result.category,
        comparison_group=result.comparison_group,
        is_healthy=result.is_healthy,
        healthy_range=list(result.healthy_range),
        reference=result.reference
    )


@router.get("/body-composition/trend", response_model=WeightTrendSchema)
def get_weight_trend(
    days: int = Query(180, description="Days to analyze"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get weight trend analysis with confidence intervals.

    Uses OLS regression with 95% CI for slope.
    """
    from soma.statistics.body_composition import analyze_weight_trend

    df = load_signals(db, biomarker_slugs=["body_mass"], days=days)

    if df is None or len(df) == 0:
        raise HTTPException(status_code=404, detail="No weight data found")

    trend = analyze_weight_trend(df, min_measurements=5)

    if trend is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient data for trend analysis (need at least 5 measurements)"
        )

    return WeightTrendSchema(
        period_days=trend.period_days,
        n_measurements=trend.n_measurements,
        start_weight=trend.start_weight,
        end_weight=trend.end_weight,
        change_kg=trend.change_kg,
        change_pct=trend.change_pct,
        slope_daily=trend.slope_daily,
        slope_weekly=trend.slope_weekly,
        ci_lower=trend.ci_lower,
        ci_upper=trend.ci_upper,
        p_value=trend.p_value,
        is_significant=trend.is_significant,
        direction=trend.direction,
        interpretation=trend.interpretation
    )
