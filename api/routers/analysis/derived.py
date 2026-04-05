"""Derived compound metrics endpoints.

Combines multiple biomarkers into clinically meaningful indicators.
Organized into tiers by validation level and clinical utility.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...database import get_db
from ...auth import require_auth, AuthContext
from ...schemas import (
    NocturnalDipSchema,
    TrainingLoadSchema,
    AutonomicBalanceSchema,
    StressIndexSchema,
    BehavioralRegularitySchema,
    CardiovascularEfficiencySchema,
    StrainIndexSchema,
    RecoveryTrendSchema,
    CircadianAmplitudeSchema,
    EnergyDistributionSchema,
    NightRestlessnessSchema,
    PhysiologicalCoherenceSchema,
    DerivedMetricsReportSchema,
)
from ._utils import load_signals
from soma.statistics.derived import (
    analyze_nocturnal_dip,
    analyze_training_load,
    analyze_autonomic_balance,
    analyze_stress_index,
    analyze_behavioral_regularity,
    analyze_cardiovascular_efficiency,
    analyze_strain_index,
    analyze_recovery_trend,
    analyze_circadian_amplitude,
    analyze_energy_distribution,
    analyze_night_restlessness,
    analyze_physiological_coherence,
    generate_derived_metrics_report,
)

router = APIRouter(prefix="/derived", tags=["derived"])


def _nocturnal_dip_to_schema(r) -> NocturnalDipSchema:
    return NocturnalDipSchema(
        day_hr_mean=r.day_hr_mean,
        night_hr_mean=r.night_hr_mean,
        dip_percent=r.dip_percent,
        classification=r.classification,
        n_days=r.n_days,
        is_concerning=r.is_concerning,
        clinical_note=r.clinical_note,
    )


def _training_load_to_schema(r) -> TrainingLoadSchema:
    return TrainingLoadSchema(
        acute_load=r.acute_load,
        chronic_load=r.chronic_load,
        ratio=r.ratio,
        classification=r.classification,
        days_in_risky_zone=r.days_in_risky_zone,
        total_days=r.total_days,
        risk_percent=r.risk_percent,
    )


def _autonomic_balance_to_schema(r) -> AutonomicBalanceSchema:
    return AutonomicBalanceSchema(
        hrv_mean=r.hrv_mean,
        rhr_mean=r.rhr_mean,
        ratio=r.ratio,
        ratio_trend_30d=r.ratio_trend_30d,
        percentile=r.percentile,
        n_days=r.n_days,
        assessment=r.assessment,
    )


def _stress_index_to_schema(r) -> StressIndexSchema:
    return StressIndexSchema(
        score=r.score,
        hrv_component=r.hrv_component,
        rhr_component=r.rhr_component,
        rr_component=r.rr_component,
        classification=r.classification,
        high_stress_days=r.high_stress_days,
        total_days=r.total_days,
        n_metrics_used=r.n_metrics_used,
    )


def _behavioral_regularity_to_schema(r) -> BehavioralRegularitySchema:
    return BehavioralRegularitySchema(
        mean_cv=r.mean_cv,
        current_cv=r.current_cv,
        stability_score=r.stability_score,
        disruption_days=r.disruption_days,
        total_days=r.total_days,
        trend=r.trend,
    )


def _cardiovascular_efficiency_to_schema(r) -> CardiovascularEfficiencySchema:
    return CardiovascularEfficiencySchema(
        efficiency_score=r.efficiency_score,
        efficiency_percentile=r.efficiency_percentile,
        trend_30d=r.trend_30d,
        best_day_score=r.best_day_score,
        worst_day_score=r.worst_day_score,
        n_days=r.n_days,
    )


def _strain_index_to_schema(r) -> StrainIndexSchema:
    return StrainIndexSchema(
        mean_strain=r.mean_strain,
        current_strain=r.current_strain,
        high_strain_days=r.high_strain_days,
        low_strain_days=r.low_strain_days,
        total_days=r.total_days,
        strain_trend_7d=r.strain_trend_7d,
    )


def _recovery_trend_to_schema(r) -> RecoveryTrendSchema:
    return RecoveryTrendSchema(
        hrv_trend=r.hrv_trend,
        rhr_trend=r.rhr_trend,
        recovery_direction=r.recovery_direction,
        days_improving=r.days_improving,
        days_declining=r.days_declining,
        total_days=r.total_days,
        confidence=r.confidence,
    )


def _circadian_amplitude_to_schema(r) -> CircadianAmplitudeSchema:
    return CircadianAmplitudeSchema(
        current_amplitude=r.current_amplitude,
        historical_amplitude=r.historical_amplitude,
        change_percent=r.change_percent,
        trend=r.trend,
        monthly_values=r.monthly_values,
        is_healthy=r.is_healthy,
    )


def _energy_distribution_to_schema(r) -> EnergyDistributionSchema:
    return EnergyDistributionSchema(
        morning_mean=r.morning_mean,
        afternoon_mean=r.afternoon_mean,
        ratio=r.ratio,
        chronotype=r.chronotype,
        consistency=r.consistency,
        n_days=r.n_days,
    )


def _night_restlessness_to_schema(r) -> NightRestlessnessSchema:
    return NightRestlessnessSchema(
        mean_night_activity=r.mean_night_activity,
        restless_nights=r.restless_nights,
        total_nights=r.total_nights,
        restless_percent=r.restless_percent,
        trend=r.trend,
        worst_night=r.worst_night,
    )


def _physiological_coherence_to_schema(r) -> PhysiologicalCoherenceSchema:
    return PhysiologicalCoherenceSchema(
        coherence_score=r.coherence_score,
        hrv_rhr_correlation=r.hrv_rhr_correlation,
        hrv_activity_correlation=r.hrv_activity_correlation,
        is_coherent=r.is_coherent,
        n_days=r.n_days,
    )


@router.get("", response_model=DerivedMetricsReportSchema)
def get_derived_metrics(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> DerivedMetricsReportSchema:
    """
    Generate complete derived compound metrics analysis.

    Combines multiple biomarkers into clinically meaningful indicators:

    **Tier 1 - High Value (clinically validated):**
    - Nocturnal HR dip (cardiovascular risk marker)
    - Training load ratio (injury risk)
    - Autonomic balance (HRV/RHR ratio)
    - Stress index (multi-metric composite)
    - Behavioral regularity (routine stability)

    **Tier 2 - Personal Tracking:**
    - Cardiovascular efficiency
    - Strain index
    - Recovery trend
    - Circadian amplitude
    - Energy distribution (chronotype)

    **Tier 3 - Experimental:**
    - Night restlessness
    - Physiological coherence
    """
    df = load_signals(db)
    result = generate_derived_metrics_report(df)

    return DerivedMetricsReportSchema(
        nocturnal_dip=(
            _nocturnal_dip_to_schema(result.nocturnal_dip)
            if result.nocturnal_dip
            else None
        ),
        training_load=(
            _training_load_to_schema(result.training_load)
            if result.training_load
            else None
        ),
        autonomic_balance=(
            _autonomic_balance_to_schema(result.autonomic_balance)
            if result.autonomic_balance
            else None
        ),
        stress_index=(
            _stress_index_to_schema(result.stress_index)
            if result.stress_index
            else None
        ),
        behavioral_regularity=(
            _behavioral_regularity_to_schema(result.behavioral_regularity)
            if result.behavioral_regularity
            else None
        ),
        cardiovascular_efficiency=(
            _cardiovascular_efficiency_to_schema(result.cardiovascular_efficiency)
            if result.cardiovascular_efficiency
            else None
        ),
        strain_index=(
            _strain_index_to_schema(result.strain_index)
            if result.strain_index
            else None
        ),
        recovery_trend=(
            _recovery_trend_to_schema(result.recovery_trend)
            if result.recovery_trend
            else None
        ),
        circadian_amplitude=(
            _circadian_amplitude_to_schema(result.circadian_amplitude)
            if result.circadian_amplitude
            else None
        ),
        energy_distribution=(
            _energy_distribution_to_schema(result.energy_distribution)
            if result.energy_distribution
            else None
        ),
        night_restlessness=(
            _night_restlessness_to_schema(result.night_restlessness)
            if result.night_restlessness
            else None
        ),
        physiological_coherence=(
            _physiological_coherence_to_schema(result.physiological_coherence)
            if result.physiological_coherence
            else None
        ),
        concerns=result.concerns,
        positive_findings=result.positive_findings,
    )


# ─────────────────────────────────────────────────────────────────────────────
# TIER 1: HIGH VALUE METRICS (Clinically Validated)
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/nocturnal-dip", response_model=NocturnalDipSchema)
def get_nocturnal_dip(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> NocturnalDipSchema:
    """
    Analyze nocturnal heart rate dipping pattern.

    Clinical significance:
    - **Dipper (10-20%)**: Normal, healthy pattern
    - **Non-dipper (<10%)**: Associated with cardiovascular risk
    - **Extreme dipper (>20%)**: May indicate orthostatic issues
    - **Reverse dipper (<0%)**: Night HR higher than day - warrants attention
    """
    df = load_signals(db)
    result = analyze_nocturnal_dip(df)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient heart rate data for nocturnal dip analysis",
        )

    return _nocturnal_dip_to_schema(result)


@router.get("/training-load", response_model=TrainingLoadSchema)
def get_training_load(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> TrainingLoadSchema:
    """
    Analyze acute:chronic workload ratio (ACWR).

    This metric compares your recent 7-day activity load to your 28-day baseline.

    Optimal range: **0.8 - 1.3**
    - Below 0.8: Undertrained / detraining
    - 0.8 - 1.3: Sweet spot for adaptation
    - 1.3 - 1.5: Overreaching (risky)
    - Above 1.5: Dangerous spike (high injury risk)
    """
    df = load_signals(db)
    result = analyze_training_load(df)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient activity data for training load analysis",
        )

    return _training_load_to_schema(result)


@router.get("/autonomic-balance", response_model=AutonomicBalanceSchema)
def get_autonomic_balance(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> AutonomicBalanceSchema:
    """
    Analyze HRV/RHR ratio as an indicator of autonomic balance.

    Higher ratio = better parasympathetic (recovery) tone relative to
    sympathetic (stress) activation.
    """
    df = load_signals(db)
    result = analyze_autonomic_balance(df)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient HRV and RHR data for autonomic balance analysis",
        )

    return _autonomic_balance_to_schema(result)


@router.get("/stress-index", response_model=StressIndexSchema)
def get_stress_index(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> StressIndexSchema:
    """
    Compute composite autonomic stress index.

    Combines multiple metrics into a single stress score:
    - Low HRV (inverted - lower HRV = higher stress)
    - High RHR (higher = more stress)
    - High respiratory rate (if available)

    Score is z-score based (0 = average for you).
    """
    df = load_signals(db)
    result = analyze_stress_index(df)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient HRV/RHR data for stress index calculation",
        )

    return _stress_index_to_schema(result)


@router.get("/behavioral-regularity", response_model=BehavioralRegularitySchema)
def get_behavioral_regularity(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> BehavioralRegularitySchema:
    """
    Analyze consistency of daily activity patterns.

    Uses coefficient of variation (CV) of 7-day rolling activity.
    Lower CV = more regular, predictable routine.

    Mental health relevance: Routine disruption often precedes mood episodes.
    """
    df = load_signals(db)
    result = analyze_behavioral_regularity(df)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient step data for behavioral regularity analysis",
        )

    return _behavioral_regularity_to_schema(result)


# ─────────────────────────────────────────────────────────────────────────────
# TIER 2: PERSONAL TRACKING METRICS
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/cardiovascular-efficiency", response_model=CardiovascularEfficiencySchema)
def get_cardiovascular_efficiency(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> CardiovascularEfficiencySchema:
    """
    Analyze activity output relative to heart rate cost.

    Higher efficiency = more work done per heartbeat.
    Useful for tracking fitness improvements over time.
    """
    df = load_signals(db)
    result = analyze_cardiovascular_efficiency(df)

    if result is None:
        raise HTTPException(
            status_code=404, detail="Insufficient activity and heart rate data"
        )

    return _cardiovascular_efficiency_to_schema(result)


@router.get("/strain-index", response_model=StrainIndexSchema)
def get_strain_index(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> StrainIndexSchema:
    """
    Analyze combined activity and heart rate strain.

    Tracks daily physiological load and identifies high/low strain days.
    """
    df = load_signals(db)
    result = analyze_strain_index(df)

    if result is None:
        raise HTTPException(
            status_code=404, detail="Insufficient activity data for strain analysis"
        )

    return _strain_index_to_schema(result)


@router.get("/recovery-trend", response_model=RecoveryTrendSchema)
def get_recovery_trend(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> RecoveryTrendSchema:
    """
    Analyze 7-day rolling trends in HRV and RHR.

    Recovery improving: HRV trending up AND RHR trending down.
    Recovery declining: HRV trending down AND RHR trending up.
    """
    df = load_signals(db)
    result = analyze_recovery_trend(df)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient HRV/RHR data for recovery trend analysis",
        )

    return _recovery_trend_to_schema(result)


@router.get("/circadian-amplitude", response_model=CircadianAmplitudeSchema)
def get_circadian_amplitude(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> CircadianAmplitudeSchema:
    """
    Analyze circadian rhythm strength over time.

    Healthy circadian rhythms show clear day/night HR differences.
    Weakening amplitude may indicate disrupted sleep patterns.
    """
    df = load_signals(db)
    result = analyze_circadian_amplitude(df)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient heart rate data for circadian amplitude analysis",
        )

    return _circadian_amplitude_to_schema(result)


@router.get("/chronotype", response_model=EnergyDistributionSchema)
def get_chronotype(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> EnergyDistributionSchema:
    """
    Determine your chronotype based on energy expenditure patterns.

    Compares morning (6-12) vs afternoon (12-18) activity.
    - Ratio > 1.3: Morning person
    - Ratio < 0.7: Evening person
    - 0.7 - 1.3: Balanced
    """
    df = load_signals(db)
    result = analyze_energy_distribution(df)

    if result is None:
        raise HTTPException(
            status_code=404, detail="Insufficient activity data for chronotype analysis"
        )

    return _energy_distribution_to_schema(result)


# ─────────────────────────────────────────────────────────────────────────────
# TIER 3: EXPERIMENTAL METRICS
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/night-restlessness", response_model=NightRestlessnessSchema)
def get_night_restlessness(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> NightRestlessnessSchema:
    """
    Analyze activity during expected sleep hours.

    Identifies nights with elevated activity that may indicate
    restless sleep or insomnia patterns.
    """
    df = load_signals(db)
    result = analyze_night_restlessness(df)

    if result is None:
        raise HTTPException(status_code=404, detail="Insufficient night activity data")

    return _night_restlessness_to_schema(result)


@router.get("/physiological-coherence", response_model=PhysiologicalCoherenceSchema)
def get_physiological_coherence(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(require_auth),
) -> PhysiologicalCoherenceSchema:
    """
    Analyze how well metrics move together as expected.

    Coherent physiology: HRV and RHR move inversely,
    activity affects both appropriately.

    Incoherence may indicate measurement issues or unusual states.
    """
    df = load_signals(db)
    result = analyze_physiological_coherence(df)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Insufficient multi-metric data for coherence analysis",
        )

    return _physiological_coherence_to_schema(result)
