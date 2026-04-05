"""Derived compound metrics - combining multiple biomarkers for deeper insights.

These metrics are derived from combinations of raw biomarkers to provide
clinically relevant indicators that can't be directly measured.
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np
from scipy import stats

# ============================================
# TIER 1: HIGH VALUE METRICS
# ============================================


@dataclass
class NocturnalDipResult:
    """Nocturnal heart rate dip analysis.

    Non-dipping (<10%) is associated with cardiovascular risk.
    Normal dipping is 10-20%.
    """

    day_hr_mean: float
    night_hr_mean: float
    dip_percent: float
    classification: str  # "extreme-dipper", "dipper", "non-dipper", "reverse-dipper"
    n_days: int
    is_concerning: bool
    clinical_note: str


@dataclass
class TrainingLoadResult:
    """Acute:Chronic workload ratio (ACWR).

    Sweet spot is 0.8-1.3. Outside this range increases injury risk.
    """

    acute_load: float  # 7-day EWMA
    chronic_load: float  # 28-day EWMA
    ratio: float
    classification: str  # "undertrained", "optimal", "overreaching", "dangerous"
    days_in_risky_zone: int
    total_days: int
    risk_percent: float


@dataclass
class AutonomicBalanceResult:
    """HRV/RHR ratio - autonomic nervous system balance.

    Higher values indicate better parasympathetic (rest/recovery) tone.
    """

    hrv_mean: float
    rhr_mean: float
    ratio: float
    ratio_trend_30d: Optional[float]  # Change over last 30 days
    percentile: float  # Where you fall in your own distribution
    n_days: int
    assessment: str


@dataclass
class StressIndexResult:
    """Composite autonomic stress index.

    Combines HRV (inverted), RHR, and respiratory rate into single score.
    Higher = more stress.
    """

    score: float  # Z-score based
    hrv_component: float
    rhr_component: float
    rr_component: Optional[float]
    classification: str  # "low", "moderate", "high", "very_high"
    high_stress_days: int
    total_days: int
    n_metrics_used: int


@dataclass
class BehavioralRegularityResult:
    """Activity pattern regularity index.

    Lower coefficient of variation = more regular routine.
    Routine disruption often precedes mood episodes.
    """

    mean_cv: float  # 7-day rolling coefficient of variation
    current_cv: float  # Most recent 7 days
    stability_score: float  # 0-100, higher = more stable
    disruption_days: int  # Days with CV > 1.5
    total_days: int
    trend: str  # "stabilizing", "stable", "destabilizing"


# ============================================
# TIER 2: PERSONAL TRACKING METRICS
# ============================================


@dataclass
class CardiovascularEfficiencyResult:
    """Activity output relative to heart rate cost.

    Higher efficiency = more activity for less cardiac effort.
    """

    efficiency_score: float  # Z-score based
    efficiency_percentile: float
    trend_30d: Optional[float]
    best_day_score: float
    worst_day_score: float
    n_days: int


@dataclass
class StrainIndexResult:
    """Combined activity and heart rate load.

    High activity + high HR = high strain day.
    """

    mean_strain: float
    current_strain: float
    high_strain_days: int
    low_strain_days: int
    total_days: int
    strain_trend_7d: str  # "increasing", "stable", "decreasing"


@dataclass
class RecoveryTrendResult:
    """7-day rolling trend in HRV vs RHR.

    Improving: HRV going up, RHR going down.
    """

    hrv_trend: float  # 7-day slope
    rhr_trend: float  # 7-day slope
    recovery_direction: str  # "improving", "stable", "declining"
    days_improving: int
    days_declining: int
    total_days: int
    confidence: float  # Based on trend strength


@dataclass
class CircadianAmplitudeResult:
    """Strength of daily heart rate rhythm.

    Higher amplitude = stronger circadian rhythm.
    """

    current_amplitude: float  # Recent month
    historical_amplitude: float  # First available data
    change_percent: float
    trend: str  # "strengthening", "stable", "weakening"
    monthly_values: list[dict]
    is_healthy: bool


@dataclass
class EnergyDistributionResult:
    """Morning vs afternoon energy expenditure pattern."""

    morning_mean: float
    afternoon_mean: float
    ratio: float  # >1 = morning person
    chronotype: str  # "morning", "balanced", "evening"
    consistency: float  # How stable is this pattern
    n_days: int


# ============================================
# TIER 3: EXPERIMENTAL METRICS
# ============================================


@dataclass
class NightRestlessnessResult:
    """Activity during expected sleep hours (0-5 AM)."""

    mean_night_activity: float
    restless_nights: int  # >100 cal
    total_nights: int
    restless_percent: float
    trend: str
    worst_night: float


@dataclass
class PhysiologicalCoherenceResult:
    """How well do HRV, RHR, and activity move together as expected."""

    coherence_score: float  # -1 to 1
    hrv_rhr_correlation: float  # Should be negative
    hrv_activity_correlation: float  # Should be positive
    is_coherent: bool
    n_days: int


@dataclass
class DerivedMetricsReport:
    """Complete derived metrics analysis."""

    # Tier 1
    nocturnal_dip: Optional[NocturnalDipResult]
    training_load: Optional[TrainingLoadResult]
    autonomic_balance: Optional[AutonomicBalanceResult]
    stress_index: Optional[StressIndexResult]
    behavioral_regularity: Optional[BehavioralRegularityResult]
    # Tier 2
    cardiovascular_efficiency: Optional[CardiovascularEfficiencyResult]
    strain_index: Optional[StrainIndexResult]
    recovery_trend: Optional[RecoveryTrendResult]
    circadian_amplitude: Optional[CircadianAmplitudeResult]
    energy_distribution: Optional[EnergyDistributionResult]
    # Tier 3
    night_restlessness: Optional[NightRestlessnessResult]
    physiological_coherence: Optional[PhysiologicalCoherenceResult]
    # Summary
    concerns: list[str]
    positive_findings: list[str]


def _fix_hrv_units(df: pd.DataFrame) -> pd.DataFrame:
    """Convert HRV from microseconds to milliseconds if needed."""
    df = df.copy()
    hrv_mask = df["biomarker_slug"].isin(["hrv_sdnn", "hrv_rmssd"])
    if hrv_mask.any() and df.loc[hrv_mask, "value"].median() > 1000:
        df.loc[hrv_mask, "value"] = df.loc[hrv_mask, "value"] / 1000
    return df


def analyze_nocturnal_dip(df: pd.DataFrame) -> Optional[NocturnalDipResult]:
    """Analyze nocturnal heart rate dipping pattern."""
    df = _fix_hrv_units(df)
    hr_data = df[df["biomarker_slug"] == "heart_rate"].copy()

    if len(hr_data) < 1000:
        return None

    hr_data["time"] = pd.to_datetime(hr_data["time"], utc=True)
    hr_data["date"] = hr_data["time"].dt.date
    hr_data["hour"] = hr_data["time"].dt.hour

    # Night: 0-5 AM, Day: 10-18
    hr_data["period"] = hr_data["hour"].apply(
        lambda h: "night" if h < 6 else ("day" if 10 <= h <= 18 else "transition")
    )

    period_means = hr_data.groupby(["date", "period"])["value"].mean().unstack()

    if "night" not in period_means.columns or "day" not in period_means.columns:
        return None

    mask = period_means["night"].notna() & period_means["day"].notna()
    if mask.sum() < 30:
        return None

    day_mean = float(period_means.loc[mask, "day"].mean())
    night_mean = float(period_means.loc[mask, "night"].mean())
    dip_pct = (day_mean - night_mean) / day_mean * 100

    # Classification based on clinical thresholds
    if dip_pct > 20:
        classification = "extreme-dipper"
        clinical_note = "Extreme dipping (>20%) may indicate orthostatic issues"
    elif dip_pct >= 10:
        classification = "dipper"
        clinical_note = "Normal dipping pattern - healthy cardiovascular sign"
    elif dip_pct >= 0:
        classification = "non-dipper"
        clinical_note = (
            "Non-dipping (<10%) is associated with increased cardiovascular risk"
        )
    else:
        classification = "reverse-dipper"
        clinical_note = "Reverse dipping (night HR > day HR) warrants medical attention"

    return NocturnalDipResult(
        day_hr_mean=day_mean,
        night_hr_mean=night_mean,
        dip_percent=dip_pct,
        classification=classification,
        n_days=int(mask.sum()),
        is_concerning=dip_pct < 10,
        clinical_note=clinical_note,
    )


def analyze_training_load(df: pd.DataFrame) -> Optional[TrainingLoadResult]:
    """Analyze acute:chronic workload ratio."""
    ae_data = df[df["biomarker_slug"] == "active_energy"].copy()

    if len(ae_data) < 500:
        return None

    ae_data["time"] = pd.to_datetime(ae_data["time"], utc=True)
    ae_data["date"] = ae_data["time"].dt.date

    daily = ae_data.groupby("date")["value"].sum().sort_index()

    if len(daily) < 35:  # Need at least 35 days for 28-day chronic
        return None

    acute = daily.ewm(span=7).mean()
    chronic = daily.ewm(span=28).mean()
    ratio = acute / chronic
    ratio = ratio.replace([np.inf, -np.inf], np.nan).dropna()

    if len(ratio) < 30:
        return None

    current_ratio = float(ratio.iloc[-1])

    # Classification
    if current_ratio < 0.8:
        classification = "undertrained"
    elif current_ratio <= 1.3:
        classification = "optimal"
    elif current_ratio <= 1.5:
        classification = "overreaching"
    else:
        classification = "dangerous"

    risky = ((ratio < 0.8) | (ratio > 1.3)).sum()

    return TrainingLoadResult(
        acute_load=float(acute.iloc[-1]),
        chronic_load=float(chronic.iloc[-1]),
        ratio=current_ratio,
        classification=classification,
        days_in_risky_zone=int(risky),
        total_days=len(ratio),
        risk_percent=float(risky / len(ratio) * 100),
    )


def analyze_autonomic_balance(df: pd.DataFrame) -> Optional[AutonomicBalanceResult]:
    """Analyze HRV/RHR ratio as autonomic balance indicator."""
    df = _fix_hrv_units(df)

    hrv_data = df[df["biomarker_slug"] == "hrv_sdnn"].copy()
    rhr_data = df[df["biomarker_slug"] == "heart_rate_resting"].copy()

    if len(hrv_data) < 30 or len(rhr_data) < 30:
        return None

    hrv_data["time"] = pd.to_datetime(hrv_data["time"], utc=True)
    rhr_data["time"] = pd.to_datetime(rhr_data["time"], utc=True)
    hrv_data["date"] = hrv_data["time"].dt.date
    rhr_data["date"] = rhr_data["time"].dt.date

    daily_hrv = hrv_data.groupby("date")["value"].mean()
    daily_rhr = rhr_data.groupby("date")["value"].mean()

    combined = pd.DataFrame({"hrv": daily_hrv, "rhr": daily_rhr}).dropna()

    if len(combined) < 30:
        return None

    combined["ratio"] = combined["hrv"] / combined["rhr"]

    current_ratio = float(combined["ratio"].iloc[-1])
    mean_ratio = float(combined["ratio"].mean())
    percentile = float(stats.percentileofscore(combined["ratio"], current_ratio))

    # 30-day trend
    trend_30d = None
    if len(combined) >= 30:
        recent = combined["ratio"].iloc[-30:]
        if len(recent) >= 30:
            x = np.arange(len(recent))
            slope, _, _, _, _ = stats.linregress(x, recent.values)
            trend_30d = float(slope * 30)  # Change over 30 days

    # Assessment
    if percentile >= 75:
        assessment = "excellent"
    elif percentile >= 50:
        assessment = "good"
    elif percentile >= 25:
        assessment = "moderate"
    else:
        assessment = "low"

    return AutonomicBalanceResult(
        hrv_mean=float(combined["hrv"].mean()),
        rhr_mean=float(combined["rhr"].mean()),
        ratio=mean_ratio,
        ratio_trend_30d=trend_30d,
        percentile=percentile,
        n_days=len(combined),
        assessment=assessment,
    )


def analyze_stress_index(df: pd.DataFrame) -> Optional[StressIndexResult]:
    """Compute composite autonomic stress index."""
    df = _fix_hrv_units(df)

    # Get daily means for each metric
    hrv_data = df[df["biomarker_slug"] == "hrv_sdnn"].copy()
    rhr_data = df[df["biomarker_slug"] == "heart_rate_resting"].copy()
    rr_data = df[df["biomarker_slug"] == "respiratory_rate"].copy()

    for d in [hrv_data, rhr_data, rr_data]:
        if len(d) > 0:
            d["time"] = pd.to_datetime(d["time"], utc=True)
            d["date"] = d["time"].dt.date

    daily_hrv = (
        hrv_data.groupby("date")["value"].mean() if len(hrv_data) > 0 else pd.Series()
    )
    daily_rhr = (
        rhr_data.groupby("date")["value"].mean() if len(rhr_data) > 0 else pd.Series()
    )
    daily_rr = (
        rr_data.groupby("date")["value"].mean() if len(rr_data) > 0 else pd.Series()
    )

    combined = pd.DataFrame({"hrv": daily_hrv, "rhr": daily_rhr, "rr": daily_rr})

    # Need at least HRV and RHR
    mask = combined["hrv"].notna() & combined["rhr"].notna()
    if mask.sum() < 20:
        return None

    combined = combined[mask]

    # Z-score each component
    # Invert HRV (low HRV = high stress)
    hrv_z = -(combined["hrv"] - combined["hrv"].mean()) / combined["hrv"].std()
    rhr_z = (combined["rhr"] - combined["rhr"].mean()) / combined["rhr"].std()

    n_metrics = 2
    if combined["rr"].notna().sum() > 10:
        rr_z = (combined["rr"] - combined["rr"].mean()) / combined["rr"].std()
        stress = (hrv_z + rhr_z + rr_z.fillna(0)) / 3
        n_metrics = 3
        rr_component = float(rr_z.iloc[-1]) if not pd.isna(rr_z.iloc[-1]) else None
    else:
        stress = (hrv_z + rhr_z) / 2
        rr_component = None

    current_stress = float(stress.iloc[-1])

    # Classification
    if current_stress < -0.5:
        classification = "low"
    elif current_stress < 0.5:
        classification = "moderate"
    elif current_stress < 1.5:
        classification = "high"
    else:
        classification = "very_high"

    high_stress_days = int((stress > 1).sum())

    return StressIndexResult(
        score=current_stress,
        hrv_component=float(hrv_z.iloc[-1]),
        rhr_component=float(rhr_z.iloc[-1]),
        rr_component=rr_component,
        classification=classification,
        high_stress_days=high_stress_days,
        total_days=len(stress),
        n_metrics_used=n_metrics,
    )


def analyze_behavioral_regularity(
    df: pd.DataFrame,
) -> Optional[BehavioralRegularityResult]:
    """Analyze consistency of daily activity patterns."""
    steps_data = df[df["biomarker_slug"] == "steps"].copy()

    if len(steps_data) < 100:
        return None

    steps_data["time"] = pd.to_datetime(steps_data["time"], utc=True)
    steps_data["date"] = steps_data["time"].dt.date

    daily = steps_data.groupby("date")["value"].sum().sort_index()

    if len(daily) < 30:
        return None

    # 7-day rolling coefficient of variation
    rolling_mean = daily.rolling(7).mean()
    rolling_std = daily.rolling(7).std()
    cv = (rolling_std / rolling_mean).replace([np.inf, -np.inf], np.nan).dropna()

    if len(cv) < 14:
        return None

    mean_cv = float(cv.mean())
    current_cv = float(cv.iloc[-1])

    # Stability score: 100 - (CV * 50), capped at 0-100
    stability = max(0, min(100, 100 - mean_cv * 50))

    # Disruption days (CV > 1.5)
    disruption_days = int((cv > 1.5).sum())

    # Trend: compare recent 14 days to previous 14 days
    if len(cv) >= 28:
        recent = cv.iloc[-14:].mean()
        previous = cv.iloc[-28:-14].mean()
        if recent < previous - 0.1:
            trend = "stabilizing"
        elif recent > previous + 0.1:
            trend = "destabilizing"
        else:
            trend = "stable"
    else:
        trend = "stable"

    return BehavioralRegularityResult(
        mean_cv=mean_cv,
        current_cv=current_cv,
        stability_score=stability,
        disruption_days=disruption_days,
        total_days=len(cv),
        trend=trend,
    )


def analyze_cardiovascular_efficiency(
    df: pd.DataFrame,
) -> Optional[CardiovascularEfficiencyResult]:
    """Analyze activity output relative to heart rate cost."""
    ae_data = df[df["biomarker_slug"] == "active_energy"].copy()
    hr_data = df[df["biomarker_slug"] == "heart_rate"].copy()

    if len(ae_data) < 100 or len(hr_data) < 100:
        return None

    ae_data["time"] = pd.to_datetime(ae_data["time"], utc=True)
    hr_data["time"] = pd.to_datetime(hr_data["time"], utc=True)
    ae_data["date"] = ae_data["time"].dt.date
    hr_data["date"] = hr_data["time"].dt.date

    daily_ae = ae_data.groupby("date")["value"].sum()
    daily_hr = hr_data.groupby("date")["value"].mean()

    combined = pd.DataFrame({"ae": daily_ae, "hr": daily_hr}).dropna()

    if len(combined) < 30:
        return None

    # Z-score normalization
    ae_z = (combined["ae"] - combined["ae"].mean()) / combined["ae"].std()
    hr_z = (combined["hr"] - combined["hr"].mean()) / combined["hr"].std()

    # Efficiency = high activity, low HR
    efficiency = ae_z - hr_z

    current = float(efficiency.iloc[-1])
    percentile = float(stats.percentileofscore(efficiency, current))

    # 30-day trend
    trend_30d = None
    if len(efficiency) >= 30:
        recent = efficiency.iloc[-30:]
        x = np.arange(len(recent))
        slope, _, _, _, _ = stats.linregress(x, recent.values)
        trend_30d = float(slope * 30)

    return CardiovascularEfficiencyResult(
        efficiency_score=float(efficiency.mean()),
        efficiency_percentile=percentile,
        trend_30d=trend_30d,
        best_day_score=float(efficiency.max()),
        worst_day_score=float(efficiency.min()),
        n_days=len(efficiency),
    )


def analyze_strain_index(df: pd.DataFrame) -> Optional[StrainIndexResult]:
    """Analyze combined activity and HR strain."""
    ae_data = df[df["biomarker_slug"] == "active_energy"].copy()
    hr_data = df[df["biomarker_slug"] == "heart_rate"].copy()

    if len(ae_data) < 100 or len(hr_data) < 100:
        return None

    ae_data["time"] = pd.to_datetime(ae_data["time"], utc=True)
    hr_data["time"] = pd.to_datetime(hr_data["time"], utc=True)
    ae_data["date"] = ae_data["time"].dt.date
    hr_data["date"] = hr_data["time"].dt.date

    daily_ae = ae_data.groupby("date")["value"].sum()
    daily_hr = hr_data.groupby("date")["value"].mean()

    combined = pd.DataFrame({"ae": daily_ae, "hr": daily_hr}).dropna()

    if len(combined) < 30:
        return None

    ae_z = (combined["ae"] - combined["ae"].mean()) / combined["ae"].std()
    hr_z = (combined["hr"] - combined["hr"].mean()) / combined["hr"].std()

    # Strain = high activity AND high HR
    strain = ae_z * hr_z

    current = float(strain.iloc[-1])
    high_strain = int((strain > 1.5).sum())
    low_strain = int((strain < -1).sum())

    # 7-day trend
    if len(strain) >= 14:
        recent_7 = strain.iloc[-7:].mean()
        prev_7 = strain.iloc[-14:-7].mean()
        if recent_7 > prev_7 + 0.3:
            trend = "increasing"
        elif recent_7 < prev_7 - 0.3:
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "stable"

    return StrainIndexResult(
        mean_strain=float(strain.mean()),
        current_strain=current,
        high_strain_days=high_strain,
        low_strain_days=low_strain,
        total_days=len(strain),
        strain_trend_7d=trend,
    )


def analyze_recovery_trend(df: pd.DataFrame) -> Optional[RecoveryTrendResult]:
    """Analyze 7-day rolling HRV and RHR trends."""
    df = _fix_hrv_units(df)

    hrv_data = df[df["biomarker_slug"] == "hrv_sdnn"].copy()
    rhr_data = df[df["biomarker_slug"] == "heart_rate_resting"].copy()

    if len(hrv_data) < 30 or len(rhr_data) < 30:
        return None

    hrv_data["time"] = pd.to_datetime(hrv_data["time"], utc=True)
    rhr_data["time"] = pd.to_datetime(rhr_data["time"], utc=True)
    hrv_data["date"] = hrv_data["time"].dt.date
    rhr_data["date"] = rhr_data["time"].dt.date

    daily_hrv = hrv_data.groupby("date")["value"].mean()
    daily_rhr = rhr_data.groupby("date")["value"].mean()

    combined = pd.DataFrame({"hrv": daily_hrv, "rhr": daily_rhr}).dropna().sort_index()

    if len(combined) < 14:
        return None

    # 7-day rolling means
    combined["hrv_7d"] = combined["hrv"].rolling(7).mean()
    combined["rhr_7d"] = combined["rhr"].rolling(7).mean()

    # Daily changes
    combined["hrv_change"] = combined["hrv_7d"].diff()
    combined["rhr_change"] = combined["rhr_7d"].diff()

    # Recovery direction: HRV up, RHR down = improving
    combined["recovery"] = combined["hrv_change"] - combined["rhr_change"]
    combined = combined.dropna()

    if len(combined) < 7:
        return None

    # Current trends (last 7 days)
    recent_hrv = combined["hrv"].iloc[-7:]
    recent_rhr = combined["rhr"].iloc[-7:]

    x = np.arange(7)
    hrv_slope, _, _, _, _ = stats.linregress(x, recent_hrv.values)
    rhr_slope, _, _, _, _ = stats.linregress(x, recent_rhr.values)

    # Direction based on combined signal
    if hrv_slope > 0.5 and rhr_slope < -0.1:
        direction = "improving"
        confidence = 0.9
    elif hrv_slope < -0.5 and rhr_slope > 0.1:
        direction = "declining"
        confidence = 0.9
    elif hrv_slope > 0 or rhr_slope < 0:
        direction = "improving"
        confidence = 0.6
    elif hrv_slope < 0 or rhr_slope > 0:
        direction = "declining"
        confidence = 0.6
    else:
        direction = "stable"
        confidence = 0.5

    improving = int((combined["recovery"] > 0).sum())
    declining = int((combined["recovery"] < 0).sum())

    return RecoveryTrendResult(
        hrv_trend=float(hrv_slope),
        rhr_trend=float(rhr_slope),
        recovery_direction=direction,
        days_improving=improving,
        days_declining=declining,
        total_days=len(combined),
        confidence=confidence,
    )


def analyze_circadian_amplitude(df: pd.DataFrame) -> Optional[CircadianAmplitudeResult]:
    """Analyze strength of daily heart rate rhythm over time."""
    hr_data = df[df["biomarker_slug"] == "heart_rate"].copy()

    if len(hr_data) < 1000:
        return None

    hr_data["time"] = pd.to_datetime(hr_data["time"], utc=True)
    hr_data["hour"] = hr_data["time"].dt.hour
    hr_data["month_year"] = hr_data["time"].dt.to_period("M")

    monthly = []
    for period in sorted(hr_data["month_year"].unique()):
        period_data = hr_data[hr_data["month_year"] == period]
        hourly = period_data.groupby("hour")["value"].mean()
        if len(hourly) >= 18:
            amplitude = float(hourly.max() - hourly.min())
            monthly.append({"period": str(period), "amplitude": amplitude})

    if len(monthly) < 3:
        return None

    monthly_df = pd.DataFrame(monthly)

    current = monthly_df.iloc[-1]["amplitude"]
    historical = monthly_df.iloc[0]["amplitude"]
    change_pct = (current - historical) / historical * 100

    # Trend
    if len(monthly_df) >= 6:
        recent_3 = monthly_df.iloc[-3:]["amplitude"].mean()
        older_3 = monthly_df.iloc[:3]["amplitude"].mean()
        if recent_3 > older_3 * 1.1:
            trend = "strengthening"
        elif recent_3 < older_3 * 0.9:
            trend = "weakening"
        else:
            trend = "stable"
    else:
        trend = "stable"

    # Healthy amplitude is typically 20-40 bpm
    is_healthy = 20 <= current <= 60

    return CircadianAmplitudeResult(
        current_amplitude=current,
        historical_amplitude=historical,
        change_percent=change_pct,
        trend=trend,
        monthly_values=monthly,
        is_healthy=is_healthy,
    )


def analyze_energy_distribution(df: pd.DataFrame) -> Optional[EnergyDistributionResult]:
    """Analyze morning vs afternoon energy expenditure."""
    ae_data = df[df["biomarker_slug"] == "active_energy"].copy()

    if len(ae_data) < 500:
        return None

    ae_data["time"] = pd.to_datetime(ae_data["time"], utc=True)
    ae_data["date"] = ae_data["time"].dt.date
    ae_data["hour"] = ae_data["time"].dt.hour
    ae_data["period"] = ae_data["hour"].apply(
        lambda h: (
            "morning" if 6 <= h < 12 else ("afternoon" if 12 <= h < 18 else "other")
        )
    )

    period_sums = ae_data.groupby(["date", "period"])["value"].sum().unstack()

    if "morning" not in period_sums.columns or "afternoon" not in period_sums.columns:
        return None

    mask = period_sums["morning"].notna() & period_sums["afternoon"].notna()
    if mask.sum() < 30:
        return None

    morning_mean = float(period_sums.loc[mask, "morning"].mean())
    afternoon_mean = float(period_sums.loc[mask, "afternoon"].mean())

    if afternoon_mean == 0:
        return None

    ratio = morning_mean / afternoon_mean

    # Chronotype
    if ratio > 1.3:
        chronotype = "morning"
    elif ratio < 0.7:
        chronotype = "evening"
    else:
        chronotype = "balanced"

    # Consistency: std of ratio
    daily_ratio = period_sums.loc[mask, "morning"] / period_sums.loc[mask, "afternoon"]
    daily_ratio = daily_ratio.replace([np.inf, -np.inf], np.nan).dropna()
    consistency = float(1 / (1 + daily_ratio.std()))  # Higher = more consistent

    return EnergyDistributionResult(
        morning_mean=morning_mean,
        afternoon_mean=afternoon_mean,
        ratio=ratio,
        chronotype=chronotype,
        consistency=consistency,
        n_days=int(mask.sum()),
    )


def analyze_night_restlessness(df: pd.DataFrame) -> Optional[NightRestlessnessResult]:
    """Analyze activity during expected sleep hours."""
    ae_data = df[df["biomarker_slug"] == "active_energy"].copy()

    if len(ae_data) < 200:
        return None

    ae_data["time"] = pd.to_datetime(ae_data["time"], utc=True)
    ae_data["date"] = ae_data["time"].dt.date
    ae_data["hour"] = ae_data["time"].dt.hour

    night_data = ae_data[(ae_data["hour"] >= 0) & (ae_data["hour"] < 5)]
    daily_night = night_data.groupby("date")["value"].sum().sort_index()

    if len(daily_night) < 30:
        return None

    mean_activity = float(daily_night.mean())
    restless = int((daily_night > 100).sum())

    # Trend
    if len(daily_night) >= 14:
        recent = daily_night.iloc[-7:].mean()
        prev = daily_night.iloc[-14:-7].mean()
        if recent > prev * 1.2:
            trend = "worsening"
        elif recent < prev * 0.8:
            trend = "improving"
        else:
            trend = "stable"
    else:
        trend = "stable"

    return NightRestlessnessResult(
        mean_night_activity=mean_activity,
        restless_nights=restless,
        total_nights=len(daily_night),
        restless_percent=float(restless / len(daily_night) * 100),
        trend=trend,
        worst_night=float(daily_night.max()),
    )


def analyze_physiological_coherence(
    df: pd.DataFrame,
) -> Optional[PhysiologicalCoherenceResult]:
    """Analyze how well HRV, RHR, and activity move together as expected."""
    df = _fix_hrv_units(df)

    hrv_data = df[df["biomarker_slug"] == "hrv_sdnn"].copy()
    rhr_data = df[df["biomarker_slug"] == "heart_rate_resting"].copy()
    steps_data = df[df["biomarker_slug"] == "steps"].copy()

    for d in [hrv_data, rhr_data, steps_data]:
        if len(d) > 0:
            d["time"] = pd.to_datetime(d["time"], utc=True)
            d["date"] = d["time"].dt.date

    daily_hrv = hrv_data.groupby("date")["value"].mean()
    daily_rhr = rhr_data.groupby("date")["value"].mean()
    daily_steps = steps_data.groupby("date")["value"].sum()

    combined = pd.DataFrame(
        {"hrv": daily_hrv, "rhr": daily_rhr, "steps": daily_steps}
    ).dropna()

    if len(combined) < 50:
        return None

    # Expected: HRV negatively correlated with RHR
    hrv_rhr_corr, _ = stats.pearsonr(combined["hrv"], combined["rhr"])

    # Expected: HRV positively correlated with activity (to a point)
    hrv_steps_corr, _ = stats.pearsonr(combined["hrv"], combined["steps"])

    # Coherence: negative HRV-RHR + positive HRV-steps
    coherence = (-hrv_rhr_corr + hrv_steps_corr) / 2

    # Is coherent if correlations are in expected directions
    is_coherent = hrv_rhr_corr < -0.1 and hrv_steps_corr > -0.1

    return PhysiologicalCoherenceResult(
        coherence_score=float(coherence),
        hrv_rhr_correlation=float(hrv_rhr_corr),
        hrv_activity_correlation=float(hrv_steps_corr),
        is_coherent=is_coherent,
        n_days=len(combined),
    )


def generate_derived_metrics_report(df: pd.DataFrame) -> DerivedMetricsReport:
    """Generate complete derived metrics analysis."""

    # Run all analyses
    nocturnal = analyze_nocturnal_dip(df)
    training = analyze_training_load(df)
    autonomic = analyze_autonomic_balance(df)
    stress = analyze_stress_index(df)
    regularity = analyze_behavioral_regularity(df)
    efficiency = analyze_cardiovascular_efficiency(df)
    strain = analyze_strain_index(df)
    recovery = analyze_recovery_trend(df)
    circadian = analyze_circadian_amplitude(df)
    energy = analyze_energy_distribution(df)
    night = analyze_night_restlessness(df)
    coherence = analyze_physiological_coherence(df)

    # Compile concerns
    concerns = []
    positives = []

    if nocturnal:
        if nocturnal.is_concerning:
            concerns.append(
                f"Low nocturnal HR dip ({nocturnal.dip_percent:.1f}%) - {nocturnal.clinical_note}"
            )
        else:
            positives.append(f"Healthy nocturnal HR dip ({nocturnal.dip_percent:.1f}%)")

    if training:
        if training.classification in ["overreaching", "dangerous"]:
            concerns.append(
                f"Training load {training.classification} (ratio: {training.ratio:.2f})"
            )
        elif training.classification == "optimal":
            positives.append(f"Optimal training load (ratio: {training.ratio:.2f})")

    if stress:
        if stress.classification in ["high", "very_high"]:
            concerns.append(f"Elevated stress index ({stress.classification})")
        elif stress.classification == "low":
            positives.append("Low stress index")

    if regularity:
        if regularity.trend == "destabilizing":
            concerns.append("Behavioral patterns destabilizing")
        elif regularity.stability_score >= 70:
            positives.append(
                f"Good behavioral regularity (score: {regularity.stability_score:.0f})"
            )

    if night:
        if night.restless_percent > 30:
            concerns.append(
                f"Frequent night restlessness ({night.restless_percent:.0f}% of nights)"
            )

    if recovery:
        if recovery.recovery_direction == "declining":
            concerns.append("Recovery metrics declining")
        elif recovery.recovery_direction == "improving":
            positives.append("Recovery metrics improving")

    if circadian:
        if circadian.trend == "strengthening":
            positives.append(
                f"Circadian amplitude strengthening (+{circadian.change_percent:.0f}%)"
            )
        elif circadian.trend == "weakening":
            concerns.append("Circadian rhythm weakening")

    if coherence:
        if coherence.is_coherent:
            positives.append("Good physiological coherence")

    return DerivedMetricsReport(
        nocturnal_dip=nocturnal,
        training_load=training,
        autonomic_balance=autonomic,
        stress_index=stress,
        behavioral_regularity=regularity,
        cardiovascular_efficiency=efficiency,
        strain_index=strain,
        recovery_trend=recovery,
        circadian_amplitude=circadian,
        energy_distribution=energy,
        night_restlessness=night,
        physiological_coherence=coherence,
        concerns=concerns,
        positive_findings=positives,
    )
