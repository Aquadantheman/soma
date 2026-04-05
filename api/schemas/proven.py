"""Proven statistical analysis schemas.

These analyses are well-established statistical methods with clear interpretations.
"""

from pydantic import BaseModel
from typing import Optional


class HourlyPatternSchema(BaseModel):
    """Heart rate pattern for a specific hour."""

    hour: int
    mean: float
    ci_lower: float
    ci_upper: float
    n: int


class CircadianAnalysis(BaseModel):
    """Circadian rhythm analysis with statistical proof."""

    hourly_patterns: list[HourlyPatternSchema]
    lowest_hour: int
    lowest_hr_mean: float
    lowest_hr_ci: tuple[float, float]
    highest_hour: int
    highest_hr_mean: float
    highest_hr_ci: tuple[float, float]
    amplitude: float
    is_significant: bool  # True if CIs don't overlap
    total_samples: int


class DayPatternSchema(BaseModel):
    """Activity pattern for a day of week."""

    day_name: str
    day_number: int
    mean: float
    ci_lower: float
    ci_upper: float
    n: int


class WeeklyActivityAnalysis(BaseModel):
    """Weekly activity analysis with ANOVA test."""

    daily_patterns: list[DayPatternSchema]
    most_active_day: str
    least_active_day: str
    f_statistic: float
    p_value: float
    is_significant: bool  # True if p < 0.05
    total_days: int


class YearlyStatSchema(BaseModel):
    """Yearly statistics for trend analysis."""

    year: int
    mean: float
    ci_lower: float
    ci_upper: float
    n: int


class TrendAnalysis(BaseModel):
    """Long-term trend analysis with regression."""

    yearly_stats: list[YearlyStatSchema]
    slope: float  # Change per year
    slope_ci: tuple[float, float]
    r_squared: float
    p_value: float
    is_significant: bool
    direction: Optional[str]  # "increasing", "decreasing", or None


class AnomalyDaySchema(BaseModel):
    """A statistically anomalous day."""

    date: str  # ISO format
    value: float
    z_score: float
    direction: str  # "high" or "low"


class AnomalyAnalysis(BaseModel):
    """Anomaly detection results using robust IQR method."""

    mean: float
    std: float
    median: float
    iqr: float
    threshold_low: float
    threshold_high: float
    anomalies: list[AnomalyDaySchema]
    total_days: int
    anomaly_rate: float


class HRVAnalysis(BaseModel):
    """HRV analysis with unit correction."""

    mean_ms: float
    ci_lower_ms: float
    ci_upper_ms: float
    n: int
    assessment: str  # "above_average", "normal", "below_average"
    unit_correction_applied: bool


class SpO2Analysis(BaseModel):
    """SpO2 analysis with clinical thresholds."""

    mean_pct: float
    ci_lower_pct: float
    ci_upper_pct: float
    n: int
    pct_below_95: float
    pct_below_95_ci: tuple[float, float]
    pct_below_90: float
    count_below_90: int
    assessment: str  # "healthy", "normal", "low"


class FullAnalysisResult(BaseModel):
    """Complete statistical analysis of all biomarkers."""

    circadian: Optional[CircadianAnalysis] = None
    weekly_activity: Optional[WeeklyActivityAnalysis] = None
    rhr_trend: Optional[TrendAnalysis] = None
    anomalies: Optional[AnomalyAnalysis] = None
    hrv: Optional[HRVAnalysis] = None
    spo2: Optional[SpO2Analysis] = None
    proven_claims: list[str]  # List of statistically proven findings
    unproven_claims: list[str]  # Things we cannot prove
