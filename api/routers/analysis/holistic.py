"""Holistic Insights analysis endpoints.

Provides integrated health analysis across all biomarker domains:
- Multi-domain wellness scoring
- Cross-domain interconnection mapping
- Paradox detection (e.g., Simpson's Paradox)
- Behavioral pattern recognition
- Risk factor synthesis
- Actionable recommendations

This module synthesizes findings from all other analysis modules
to provide a comprehensive view of health status and trends.
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...database import get_db
from ...auth import require_auth, AuthContext
from ...schemas.holistic import (
    DomainScoreSchema,
    WellnessScoreSchema,
    FindingSchema,
    InterconnectionSchema,
    ParadoxSchema,
    BehavioralPatternSchema,
    RiskFactorSchema,
    RecommendationSchema,
    DataAdequacySchema,
    HolisticInsightSchema,
    HolisticInsightSummarySchema,
)
from ._utils import load_signals

router = APIRouter()


def _domain_score_to_schema(ds) -> DomainScoreSchema:
    """Convert DomainScore to schema."""
    return DomainScoreSchema(
        score=ds.score,
        confidence=ds.confidence,
        trend=ds.trend,
        key_contributors=ds.key_contributors,
        limiting_factors=ds.limiting_factors,
        data_points=ds.data_points
    )


def _wellness_score_to_schema(ws) -> WellnessScoreSchema:
    """Convert WellnessScore to schema."""
    return WellnessScoreSchema(
        overall=ws.overall,
        interpretation=ws.interpretation,
        cardiovascular=_domain_score_to_schema(ws.cardiovascular),
        sleep=_domain_score_to_schema(ws.sleep),
        activity=_domain_score_to_schema(ws.activity),
        recovery=_domain_score_to_schema(ws.recovery),
        body_composition=_domain_score_to_schema(ws.body_composition),
        mobility=_domain_score_to_schema(ws.mobility) if ws.mobility else None,
        # Explainability metrics (Harmonic Mean)
        arithmetic_mean=ws.arithmetic_mean,
        imbalance_penalty=ws.imbalance_penalty,
        bottleneck_domain=ws.bottleneck_domain,
        bottleneck_impact=ws.bottleneck_impact,
        # Summary
        strongest_domain=ws.strongest_domain,
        weakest_domain=ws.weakest_domain
    )


def _finding_to_schema(f) -> FindingSchema:
    """Convert Finding to schema."""
    return FindingSchema(
        category=f.category,
        severity=f.severity,
        title=f.title,
        description=f.description,
        evidence=f.evidence,
        confidence=f.confidence,
        actionable=f.actionable,
        related_biomarkers=f.related_biomarkers
    )


def _interconnection_to_schema(ic) -> InterconnectionSchema:
    """Convert Interconnection to schema."""
    return InterconnectionSchema(
        source_domain=ic.source_domain,
        target_domain=ic.target_domain,
        source_biomarker=ic.source_biomarker,
        target_biomarker=ic.target_biomarker,
        correlation=ic.correlation,
        p_value=ic.p_value,
        lag_days=ic.lag_days,
        strength=ic.strength,
        sample_size=ic.sample_size,
        pathway=ic.pathway,
        interpretation=ic.interpretation
    )


def _paradox_to_schema(p) -> ParadoxSchema:
    """Convert Paradox to schema."""
    return ParadoxSchema(
        name=p.name,
        biomarker_a=p.biomarker_a,
        biomarker_b=p.biomarker_b,
        raw_correlation=p.raw_correlation,
        raw_p_value=p.raw_p_value,
        detrended_correlation=p.detrended_correlation,
        detrended_p_value=p.detrended_p_value,
        confounding_factor=p.confounding_factor,
        explanation=p.explanation,
        behavioral_insight=p.behavioral_insight
    )


def _behavioral_pattern_to_schema(bp) -> BehavioralPatternSchema:
    """Convert BehavioralPattern to schema."""
    return BehavioralPatternSchema(
        name=bp.name,
        pattern_type=bp.pattern_type,
        description=bp.description,
        evidence=bp.evidence,
        health_implication=bp.health_implication,
        recommendation=bp.recommendation
    )


def _risk_factor_to_schema(rf) -> RiskFactorSchema:
    """Convert RiskFactor to schema."""
    return RiskFactorSchema(
        name=rf.name,
        level=rf.level,
        description=rf.description,
        contributing_factors=rf.contributing_factors,
        mitigation_suggestions=rf.mitigation_suggestions
    )


def _recommendation_to_schema(r) -> RecommendationSchema:
    """Convert Recommendation to schema."""
    return RecommendationSchema(
        priority=r.priority,
        category=r.category,
        action=r.action,
        rationale=r.rationale,
        expected_impact=r.expected_impact,
        timeline=r.timeline
    )


def _data_adequacy_to_schema(da) -> DataAdequacySchema:
    """Convert DataAdequacy to schema."""
    return DataAdequacySchema(
        biomarker=da.biomarker,
        current_samples=da.current_samples,
        minimum_recommended=da.minimum_recommended,
        status=da.status,
        reliability_score=da.reliability_score,
        suggestion=da.suggestion
    )


@router.get("/holistic", response_model=HolisticInsightSchema)
def get_holistic_insight(
    age: Optional[int] = Query(None, description="User age for context"),
    sex: Optional[str] = Query(None, description="User sex (male/female) for context"),
    days: int = Query(365, description="Days of history to analyze"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get comprehensive holistic health analysis.

    This endpoint synthesizes findings across all biomarker domains:
    - Cardiovascular health (HR, HRV, resting HR)
    - Sleep quality and patterns
    - Activity levels and consistency
    - Recovery capacity
    - Body composition trends

    Advanced features include:
    - Paradox detection (identifying misleading correlations)
    - Cross-domain interconnection mapping
    - Behavioral pattern recognition
    - Risk factor synthesis
    - Personalized recommendations

    Provide age and sex for more accurate context-aware analysis.
    """
    from soma.statistics.holistic import (
        AnalysisInputs,
        generate_holistic_insight,
    )
    import pandas as pd

    # Load all relevant biomarkers
    all_biomarkers = [
        # Cardiovascular (including SpO2 - high reliability: CV=2.2%)
        "heart_rate", "hrv_sdnn", "heart_rate_resting", "vo2_max", "spo2",
        # Sleep
        "sleep_duration", "sleep_rem", "sleep_deep", "sleep_core", "sleep_efficiency",
        # Activity
        "steps", "active_energy", "exercise_time", "flights_climbed",
        # Body composition
        "body_mass", "body_fat_percentage", "lean_body_mass",
        # Mobility (confound-controlled, 97% real signal - "sixth vital sign")
        "walking_speed", "walking_steadiness", "walking_asymmetry",
        # Other
        "time_in_daylight", "respiratory_rate",
    ]

    df = load_signals(db, biomarker_slugs=all_biomarkers, days=days)

    if df is None or len(df) == 0:
        raise HTTPException(
            status_code=404,
            detail="No health data found. Please ensure you have imported data."
        )

    # Ensure time is datetime
    df['time'] = pd.to_datetime(df['time'])

    # Create analysis inputs
    inputs = AnalysisInputs(
        signals=df,
        user_age=age,
        user_sex=sex,
    )

    # Generate holistic insight
    insight = generate_holistic_insight(inputs)

    # Convert to schema
    return HolisticInsightSchema(
        generated_at=insight.generated_at,
        analysis_period_start=insight.analysis_period_start,
        analysis_period_end=insight.analysis_period_end,
        overall_confidence=insight.overall_confidence,
        wellness_score=_wellness_score_to_schema(insight.wellness_score),
        primary_findings=[_finding_to_schema(f) for f in insight.primary_findings],
        interconnections=[_interconnection_to_schema(ic) for ic in insight.interconnections],
        paradoxes=[_paradox_to_schema(p) for p in insight.paradoxes],
        behavioral_patterns=[_behavioral_pattern_to_schema(bp) for bp in insight.behavioral_patterns],
        risk_factors=[_risk_factor_to_schema(rf) for rf in insight.risk_factors],
        protective_factors=insight.protective_factors,
        recommendations=[_recommendation_to_schema(r) for r in insight.recommendations],
        trajectory=insight.trajectory,
        trajectory_details=insight.trajectory_details,
        data_adequacy=[_data_adequacy_to_schema(da) for da in insight.data_adequacy]
    )


@router.get("/holistic/summary", response_model=HolisticInsightSummarySchema)
def get_holistic_summary(
    age: Optional[int] = None,
    sex: Optional[str] = None,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get quick summary of holistic health status.

    Returns overall score, trajectory, top strength/concern,
    and key recommendations without the full detailed analysis.
    """
    from soma.statistics.holistic import (
        AnalysisInputs,
        generate_holistic_insight,
    )
    import pandas as pd

    all_biomarkers = [
        "heart_rate", "hrv_sdnn", "heart_rate_resting", "vo2_max", "spo2",
        "sleep_duration", "sleep_rem", "sleep_deep", "sleep_core",
        "steps", "active_energy", "exercise_time",
        "body_mass", "body_fat_percentage",
        "walking_speed", "walking_steadiness", "walking_asymmetry",
    ]

    df = load_signals(db, biomarker_slugs=all_biomarkers, days=365)

    if df is None:
        df = pd.DataFrame(columns=['time', 'biomarker_slug', 'value'])

    df['time'] = pd.to_datetime(df['time'])

    inputs = AnalysisInputs(
        signals=df,
        user_age=age,
        user_sex=sex,
    )

    insight = generate_holistic_insight(inputs)

    # Extract top strength and concern
    top_strength = "Cardiovascular health" if insight.wellness_score.cardiovascular.score >= 75 else "Recovery capacity"
    top_concern = "Sleep quality" if insight.wellness_score.sleep.score < 60 else "Body composition"

    # If we have more specific findings, use those
    if insight.wellness_score.strongest_domain:
        top_strength = insight.wellness_score.strongest_domain.replace('_', ' ').title()
    if insight.wellness_score.weakest_domain:
        top_concern = insight.wellness_score.weakest_domain.replace('_', ' ').title()

    # Get top recommendations
    key_recs = [r.action for r in insight.recommendations[:3]]

    return HolisticInsightSummarySchema(
        overall_score=insight.wellness_score.overall,
        interpretation=insight.wellness_score.interpretation,
        trajectory=insight.trajectory,
        top_strength=top_strength,
        top_concern=top_concern,
        key_recommendations=key_recs,
        has_sufficient_data=insight.overall_confidence in ('high', 'moderate')
    )


@router.get("/holistic/wellness-score", response_model=WellnessScoreSchema)
def get_wellness_score(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get multi-domain wellness score breakdown.

    Returns overall score and individual domain scores
    (cardiovascular, sleep, activity, recovery, body composition)
    with confidence levels and trends.
    """
    from soma.statistics.holistic import (
        aggregate_signals,
        compute_wellness_score,
    )
    import pandas as pd

    all_biomarkers = [
        "heart_rate", "hrv_sdnn", "heart_rate_resting", "vo2_max", "spo2",
        "sleep_duration", "sleep_rem", "sleep_deep", "sleep_core",
        "steps", "active_energy", "exercise_time",
        "body_mass", "body_fat_percentage",
        "walking_speed", "walking_steadiness", "walking_asymmetry",
    ]

    df = load_signals(db, biomarker_slugs=all_biomarkers, days=365)

    if df is None or len(df) == 0:
        raise HTTPException(
            status_code=404,
            detail="No health data found for wellness score calculation"
        )

    df['time'] = pd.to_datetime(df['time'])
    signals_by_biomarker = aggregate_signals(df)

    wellness = compute_wellness_score(signals_by_biomarker)

    return _wellness_score_to_schema(wellness)


@router.get("/holistic/interconnections", response_model=List[InterconnectionSchema])
def get_interconnections(
    min_correlation: float = Query(0.2, description="Minimum correlation strength"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get cross-domain interconnections.

    Returns relationships between biomarkers from different domains,
    including lagged correlations (e.g., how today's activity
    affects tomorrow's sleep).
    """
    from soma.statistics.holistic import (
        aggregate_signals,
        find_cross_domain_interconnections,
    )
    import pandas as pd

    all_biomarkers = [
        "heart_rate", "hrv_sdnn", "heart_rate_resting", "vo2_max", "spo2",
        "sleep_duration", "sleep_rem", "sleep_deep", "sleep_core",
        "steps", "active_energy", "exercise_time",
        "body_mass", "body_fat_percentage",
        "walking_speed", "walking_steadiness", "walking_asymmetry",
    ]

    df = load_signals(db, biomarker_slugs=all_biomarkers, days=365)

    if df is None or len(df) == 0:
        raise HTTPException(
            status_code=404,
            detail="No health data found for interconnection analysis"
        )

    df['time'] = pd.to_datetime(df['time'])
    signals_by_biomarker = aggregate_signals(df)

    interconnections = find_cross_domain_interconnections(signals_by_biomarker)

    # Filter by minimum correlation
    filtered = [ic for ic in interconnections if abs(ic.correlation) >= min_correlation]

    return [_interconnection_to_schema(ic) for ic in filtered]


@router.get("/holistic/paradoxes", response_model=List[ParadoxSchema])
def get_paradoxes(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get detected statistical paradoxes.

    Identifies cases where raw correlations may be misleading
    (e.g., Simpson's Paradox), providing the detrended correlation
    and explanation of the confounding factor.
    """
    from soma.statistics.holistic import (
        aggregate_signals,
        detect_all_paradoxes,
    )
    import pandas as pd

    all_biomarkers = [
        "steps", "active_energy", "exercise_time",
        "body_mass", "body_fat_percentage",
        "hrv_sdnn", "heart_rate_resting",
    ]

    df = load_signals(db, biomarker_slugs=all_biomarkers, days=730)

    if df is None or len(df) == 0:
        return []

    df['time'] = pd.to_datetime(df['time'])
    signals_by_biomarker = aggregate_signals(df)

    paradoxes = detect_all_paradoxes(signals_by_biomarker)

    return [_paradox_to_schema(p) for p in paradoxes]


@router.get("/holistic/behavioral-patterns", response_model=List[BehavioralPatternSchema])
def get_behavioral_patterns(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
):
    """
    Get detected behavioral patterns.

    Identifies patterns such as:
    - Compensatory exercise (more activity when weight is higher)
    - Weekend warrior (activity concentrated on weekends)
    - Seasonal activity variations
    """
    from soma.statistics.holistic import (
        aggregate_signals,
        detect_all_behavioral_patterns,
    )
    import pandas as pd

    all_biomarkers = [
        "steps", "active_energy", "exercise_time",
        "body_mass",
    ]

    df = load_signals(db, biomarker_slugs=all_biomarkers, days=730)

    if df is None or len(df) == 0:
        return []

    df['time'] = pd.to_datetime(df['time'])
    signals_by_biomarker = aggregate_signals(df)

    patterns = detect_all_behavioral_patterns(signals_by_biomarker)

    return [_behavioral_pattern_to_schema(p) for p in patterns]
