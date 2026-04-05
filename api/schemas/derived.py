"""Derived compound metrics schemas.

Metrics computed by combining multiple biomarkers.
Organized into tiers by validation level and clinical utility.
"""

from pydantic import BaseModel
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# TIER 1: HIGH VALUE METRICS (Clinically Validated)
# ─────────────────────────────────────────────────────────────────────────────

class NocturnalDipSchema(BaseModel):
    """Nocturnal heart rate dip analysis."""

    day_hr_mean: float
    night_hr_mean: float
    dip_percent: float
    classification: str  # "extreme-dipper", "dipper", "non-dipper", "reverse-dipper"
    n_days: int
    is_concerning: bool
    clinical_note: str


class TrainingLoadSchema(BaseModel):
    """Acute:Chronic workload ratio analysis."""

    acute_load: float
    chronic_load: float
    ratio: float
    classification: str  # "undertrained", "optimal", "overreaching", "dangerous"
    days_in_risky_zone: int
    total_days: int
    risk_percent: float


class AutonomicBalanceSchema(BaseModel):
    """HRV/RHR ratio - autonomic balance indicator."""

    hrv_mean: float
    rhr_mean: float
    ratio: float
    ratio_trend_30d: Optional[float]
    percentile: float
    n_days: int
    assessment: str


class StressIndexSchema(BaseModel):
    """Composite autonomic stress index."""

    score: float
    hrv_component: float
    rhr_component: float
    rr_component: Optional[float]
    classification: str  # "low", "moderate", "high", "very_high"
    high_stress_days: int
    total_days: int
    n_metrics_used: int


class BehavioralRegularitySchema(BaseModel):
    """Activity pattern regularity index."""

    mean_cv: float
    current_cv: float
    stability_score: float
    disruption_days: int
    total_days: int
    trend: str  # "stabilizing", "stable", "destabilizing"


# ─────────────────────────────────────────────────────────────────────────────
# TIER 2: PERSONAL TRACKING METRICS
# ─────────────────────────────────────────────────────────────────────────────

class CardiovascularEfficiencySchema(BaseModel):
    """Activity output relative to heart rate cost."""

    efficiency_score: float
    efficiency_percentile: float
    trend_30d: Optional[float]
    best_day_score: float
    worst_day_score: float
    n_days: int


class StrainIndexSchema(BaseModel):
    """Combined activity and heart rate strain."""

    mean_strain: float
    current_strain: float
    high_strain_days: int
    low_strain_days: int
    total_days: int
    strain_trend_7d: str  # "increasing", "stable", "decreasing"


class RecoveryTrendSchema(BaseModel):
    """7-day rolling HRV and RHR trends."""

    hrv_trend: float
    rhr_trend: float
    recovery_direction: str  # "improving", "stable", "declining"
    days_improving: int
    days_declining: int
    total_days: int
    confidence: float


class CircadianAmplitudeSchema(BaseModel):
    """Circadian rhythm strength over time."""

    current_amplitude: float
    historical_amplitude: float
    change_percent: float
    trend: str  # "strengthening", "stable", "weakening"
    monthly_values: list[dict]
    is_healthy: bool


class EnergyDistributionSchema(BaseModel):
    """Morning vs afternoon energy expenditure."""

    morning_mean: float
    afternoon_mean: float
    ratio: float
    chronotype: str  # "morning", "balanced", "evening"
    consistency: float
    n_days: int


# ─────────────────────────────────────────────────────────────────────────────
# TIER 3: EXPERIMENTAL METRICS
# ─────────────────────────────────────────────────────────────────────────────

class NightRestlessnessSchema(BaseModel):
    """Activity during expected sleep hours."""

    mean_night_activity: float
    restless_nights: int
    total_nights: int
    restless_percent: float
    trend: str
    worst_night: float


class PhysiologicalCoherenceSchema(BaseModel):
    """How well metrics move together as expected."""

    coherence_score: float
    hrv_rhr_correlation: float
    hrv_activity_correlation: float
    is_coherent: bool
    n_days: int


# ─────────────────────────────────────────────────────────────────────────────
# COMPLETE REPORT
# ─────────────────────────────────────────────────────────────────────────────

class DerivedMetricsReportSchema(BaseModel):
    """Complete derived metrics analysis."""

    # Tier 1
    nocturnal_dip: Optional[NocturnalDipSchema] = None
    training_load: Optional[TrainingLoadSchema] = None
    autonomic_balance: Optional[AutonomicBalanceSchema] = None
    stress_index: Optional[StressIndexSchema] = None
    behavioral_regularity: Optional[BehavioralRegularitySchema] = None
    # Tier 2
    cardiovascular_efficiency: Optional[CardiovascularEfficiencySchema] = None
    strain_index: Optional[StrainIndexSchema] = None
    recovery_trend: Optional[RecoveryTrendSchema] = None
    circadian_amplitude: Optional[CircadianAmplitudeSchema] = None
    energy_distribution: Optional[EnergyDistributionSchema] = None
    # Tier 3
    night_restlessness: Optional[NightRestlessnessSchema] = None
    physiological_coherence: Optional[PhysiologicalCoherenceSchema] = None
    # Summary
    concerns: list[str]
    positive_findings: list[str]
