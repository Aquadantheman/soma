"""Advanced analysis endpoints.

Includes cross-correlations, recovery models, seasonality, and readiness scoring.
All results include confidence intervals and proper statistical testing.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...auth import require_auth, AuthContext
from ...schemas import (
    CorrelationPairSchema,
    CorrelationMatrixAnalysis,
    LaggedCorrelationSchema,
    RecoveryAnalysis,
    SeasonalComponentSchema,
    SeasonalAnalysisSchema,
    ReadinessScoreSchema,
    ReadinessSummary,
    AdvancedAnalysisResult,
)
from ._utils import load_signals
from soma.statistics.advanced import (
    analyze_correlations,
    analyze_recovery,
    analyze_seasonality,
    build_readiness_model,
    compute_readiness_scores,
    get_readiness_summary,
)

router = APIRouter(tags=["advanced"])


def _pair_to_schema(p) -> CorrelationPairSchema:
    """Convert correlation pair to schema."""
    return CorrelationPairSchema(
        biomarker_a=p.biomarker_a,
        biomarker_b=p.biomarker_b,
        pearson_r=p.pearson_r,
        pearson_p=p.pearson_p,
        spearman_rho=p.spearman_rho,
        spearman_p=p.spearman_p,
        n_observations=p.n_observations,
        ci_lower=p.ci_lower,
        ci_upper=p.ci_upper,
        is_significant=p.is_significant,
        effect_size=p.effect_size,
    )


def _lagged_to_schema(lc) -> LaggedCorrelationSchema:
    """Convert lagged correlation to schema."""
    return LaggedCorrelationSchema(
        lag_days=lc.lag_days,
        correlation=lc.correlation,
        p_value=lc.p_value,
        ci_lower=lc.ci_lower,
        ci_upper=lc.ci_upper,
        n_observations=lc.n_observations,
        is_significant=lc.is_significant,
    )


def _seasonal_to_schema(sc) -> SeasonalComponentSchema:
    """Convert seasonal component to schema."""
    return SeasonalComponentSchema(
        month=sc.month,
        month_name=sc.month_name,
        mean_value=sc.mean_value,
        ci_lower=sc.ci_lower,
        ci_upper=sc.ci_upper,
        n_observations=sc.n_observations,
        deviation_from_annual=sc.deviation_from_annual,
    )


def _recovery_to_schema(result) -> RecoveryAnalysis:
    """Convert recovery result to schema."""
    return RecoveryAnalysis(
        predictor=result.predictor,
        outcome=result.outcome,
        lagged_correlations=[
            _lagged_to_schema(lc) for lc in result.lagged_correlations
        ],
        optimal_lag=result.optimal_lag,
        optimal_correlation=result.optimal_correlation,
        optimal_p_value=result.optimal_p_value,
        interpretation=result.interpretation,
        is_significant=result.is_significant,
        regression_slope=result.regression_slope,
        regression_intercept=result.regression_intercept,
        r_squared=result.r_squared,
    )


def _seasonality_to_schema(result) -> SeasonalAnalysisSchema:
    """Convert seasonality result to schema."""
    return SeasonalAnalysisSchema(
        biomarker_slug=result.biomarker_slug,
        annual_mean=result.annual_mean,
        seasonal_components=[
            _seasonal_to_schema(sc) for sc in result.seasonal_components
        ],
        peak_month=result.peak_month,
        trough_month=result.trough_month,
        seasonal_amplitude=result.seasonal_amplitude,
        seasonality_strength=result.seasonality_strength,
        f_statistic=result.f_statistic,
        p_value=result.p_value,
        is_significant=result.is_significant,
    )


@router.get("/correlations", response_model=CorrelationMatrixAnalysis)
def get_correlations(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> CorrelationMatrixAnalysis:
    """
    Compute correlation matrix between all biomarker pairs.

    Uses both Pearson (linear) and Spearman (monotonic) correlations.
    Applies Bonferroni correction for multiple comparisons.
    Reports 95% confidence intervals using Fisher z-transformation.
    """
    df = load_signals(db)
    result = analyze_correlations(df)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient overlapping data for correlation analysis",
        )

    return CorrelationMatrixAnalysis(
        pairs=[_pair_to_schema(p) for p in result.pairs],
        biomarkers_analyzed=result.biomarkers_analyzed,
        bonferroni_alpha=result.bonferroni_alpha,
        significant_pairs=[_pair_to_schema(p) for p in result.significant_pairs],
        method_note=result.method_note,
    )


@router.get("/recovery", response_model=RecoveryAnalysis)
def get_recovery_analysis(
    predictor: str = "steps",
    outcome: str = "hrv_sdnn",
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> RecoveryAnalysis:
    """
    Analyze how a predictor affects an outcome at various time lags.

    Tests whether activity TODAY predicts HRV/RHR tomorrow, day after, etc.
    Uses lagged Pearson correlation with significance testing.

    Common combinations:
    - predictor=steps, outcome=hrv_sdnn (activity -> HRV)
    - predictor=steps, outcome=heart_rate_resting (activity -> RHR)
    - predictor=active_energy, outcome=hrv_sdnn
    """
    df = load_signals(db)
    result = analyze_recovery(df, predictor=predictor, outcome=outcome)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient data for recovery analysis ({predictor} -> {outcome})",
        )

    return _recovery_to_schema(result)


@router.get("/seasonality", response_model=SeasonalAnalysisSchema)
def get_seasonality_analysis(
    biomarker_slug: str = "steps",
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> SeasonalAnalysisSchema:
    """
    Decompose biomarker data into seasonal patterns.

    Uses one-way ANOVA to test if monthly means differ significantly.
    Reports seasonal amplitude and variance explained.
    """
    df = load_signals(db)
    result = analyze_seasonality(df, biomarker_slug=biomarker_slug)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient data for seasonal analysis on '{biomarker_slug}'",
        )

    return _seasonality_to_schema(result)


@router.get("/readiness", response_model=ReadinessSummary)
def get_readiness_analysis(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> ReadinessSummary:
    """
    Compute daily readiness scores based on HRV and RHR.

    Readiness = weighted combination of:
    - HRV z-score (higher = better)
    - RHR z-score inverted (lower = better)

    Scores are normalized to 0-100 scale based on your historical distribution.
    """
    df = load_signals(db)

    model = build_readiness_model(df)
    if model is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient HRV and RHR data for readiness scoring",
        )

    scores = compute_readiness_scores(df, model)
    if not scores:
        raise HTTPException(
            status_code=404, detail="Could not compute readiness scores"
        )

    summary = get_readiness_summary(scores)

    return ReadinessSummary(
        total_days=summary["total_days"],
        mean_score=summary["mean_score"],
        std_score=summary["std_score"],
        current_score=summary["current_score"],
        current_interpretation=summary["current_interpretation"],
        trend_7d=summary["trend_7d"],
        trend_p_value=summary["trend_p_value"],
        interpretation_distribution=summary["interpretation_distribution"],
        recent_scores=[
            ReadinessScoreSchema(
                date=str(s.date),
                score=s.score,
                hrv_z_score=s.hrv_z_score,
                rhr_z_score=s.rhr_z_score,
                components=s.components,
                interpretation=s.interpretation,
            )
            for s in scores[:30]  # Last 30 days
        ],
    )


@router.get("/summary", response_model=AdvancedAnalysisResult)
def get_advanced_summary(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> AdvancedAnalysisResult:
    """
    Run all advanced statistical analyses.

    Includes:
    - Cross-biomarker correlations with Bonferroni correction
    - Recovery models (activity -> next-day HRV/RHR)
    - Seasonal decomposition
    - Composite readiness scores

    All results include confidence intervals and p-values.
    """
    df = load_signals(db)

    proven = []
    methodology = [
        "Correlations: Bonferroni-corrected for multiple comparisons",
        "Recovery: Lagged Pearson correlations (0-3 days)",
        "Seasonality: One-way ANOVA across months",
        "Readiness: z-score weighted composite (60% HRV, 40% RHR)",
    ]

    # Correlations
    corr_result = None
    corr = analyze_correlations(df)
    if corr:
        corr_result = CorrelationMatrixAnalysis(
            pairs=[_pair_to_schema(p) for p in corr.pairs],
            biomarkers_analyzed=corr.biomarkers_analyzed,
            bonferroni_alpha=corr.bonferroni_alpha,
            significant_pairs=[_pair_to_schema(p) for p in corr.significant_pairs],
            method_note=corr.method_note,
        )
        for p in corr.significant_pairs:
            proven.append(
                f"Correlation: {p.biomarker_a} <-> {p.biomarker_b}: "
                f"r={p.pearson_r:.3f} (p={p.pearson_p:.4f}, {p.effect_size} effect)"
            )

    # Recovery - HRV
    recovery_hrv_result = None
    recovery_hrv = analyze_recovery(df, predictor="steps", outcome="hrv_sdnn")
    if recovery_hrv:
        recovery_hrv_result = _recovery_to_schema(recovery_hrv)
        if recovery_hrv.is_significant:
            proven.append(f"Recovery (steps->HRV): {recovery_hrv.interpretation}")

    # Recovery - RHR
    recovery_rhr_result = None
    recovery_rhr = analyze_recovery(df, predictor="steps", outcome="heart_rate_resting")
    if recovery_rhr:
        recovery_rhr_result = _recovery_to_schema(recovery_rhr)
        if recovery_rhr.is_significant:
            proven.append(f"Recovery (steps->RHR): {recovery_rhr.interpretation}")

    # Seasonality - Steps
    season_steps_result = None
    season_steps = analyze_seasonality(df, biomarker_slug="steps")
    if season_steps:
        season_steps_result = _seasonality_to_schema(season_steps)
        if season_steps.is_significant:
            proven.append(
                f"Seasonal steps: peak in {season_steps.peak_month}, "
                f"trough in {season_steps.trough_month} "
                f"(amplitude: {season_steps.seasonal_amplitude:,.0f} steps, p={season_steps.p_value:.4f})"
            )

    # Seasonality - HR
    season_hr_result = None
    season_hr = analyze_seasonality(df, biomarker_slug="heart_rate")
    if season_hr:
        season_hr_result = _seasonality_to_schema(season_hr)
        if season_hr.is_significant:
            proven.append(
                f"Seasonal HR: peak in {season_hr.peak_month}, "
                f"trough in {season_hr.trough_month} "
                f"(amplitude: {season_hr.seasonal_amplitude:.1f} bpm, p={season_hr.p_value:.4f})"
            )

    # Readiness
    readiness_result = None
    model = build_readiness_model(df)
    if model:
        scores = compute_readiness_scores(df, model)
        if scores:
            summary = get_readiness_summary(scores)
            readiness_result = ReadinessSummary(
                total_days=summary["total_days"],
                mean_score=summary["mean_score"],
                std_score=summary["std_score"],
                current_score=summary["current_score"],
                current_interpretation=summary["current_interpretation"],
                trend_7d=summary["trend_7d"],
                trend_p_value=summary["trend_p_value"],
                interpretation_distribution=summary["interpretation_distribution"],
                recent_scores=[
                    ReadinessScoreSchema(
                        date=str(s.date),
                        score=s.score,
                        hrv_z_score=s.hrv_z_score,
                        rhr_z_score=s.rhr_z_score,
                        components=s.components,
                        interpretation=s.interpretation,
                    )
                    for s in scores[:30]
                ],
            )
            proven.append(
                f"Readiness model: {summary['total_days']} days scored, "
                f"mean={summary['mean_score']:.1f}, current={summary['current_score']:.1f} ({summary['current_interpretation']})"
            )

    return AdvancedAnalysisResult(
        correlations=corr_result,
        recovery_hrv=recovery_hrv_result,
        recovery_rhr=recovery_rhr_result,
        seasonality_steps=season_steps_result,
        seasonality_hr=season_hr_result,
        readiness=readiness_result,
        proven_claims=proven,
        methodology_notes=methodology,
    )
