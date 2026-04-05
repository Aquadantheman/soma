"""Daylight exposure analysis schemas."""

from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field


class ConfidenceIntervalSchema(BaseModel):
    """Value with confidence interval."""
    mean: float
    ci_lower: float
    ci_upper: float
    n: int
    confidence: float = 0.95


class DailyDaylightSchema(BaseModel):
    """Daylight metrics for a single day."""
    date: date
    total_min: float = Field(description="Total minutes of daylight exposure")
    morning_min: float = Field(description="Minutes before 10am")
    midday_min: float = Field(description="Minutes 10am-2pm")
    afternoon_min: float = Field(description="Minutes after 2pm")
    has_morning_exposure: bool = Field(description="Had >=20 min morning light")


class DaylightBaselineSchema(BaseModel):
    """Personal baseline for daylight exposure."""
    computed_at: str
    n_days: int = Field(description="Number of days in baseline")

    total_daylight: ConfidenceIntervalSchema
    morning_daylight: ConfidenceIntervalSchema
    midday_daylight: ConfidenceIntervalSchema
    afternoon_daylight: ConfidenceIntervalSchema

    pct_days_with_morning_light: float = Field(
        description="Percentage of days with >=20 min morning light"
    )
    morning_light_mean: float = Field(description="Average morning light (minutes)")
    variability_score: float = Field(
        description="Coefficient of variation (lower = more consistent)"
    )

    is_sufficient: bool = Field(description="Meeting minimum recommendations")
    consistency_score: float = Field(description="Consistency score (0-100)")


class DaylightDeviationSchema(BaseModel):
    """How a day's daylight deviates from personal baseline."""
    date: date
    total_z: float = Field(description="Z-score for total daylight")
    morning_z: float = Field(description="Z-score for morning daylight")

    is_low: bool = Field(description="Significantly below baseline")
    is_no_morning_light: bool = Field(description="No meaningful morning exposure")
    is_notable: bool

    interpretation: str


class DaylightTrendSchema(BaseModel):
    """Trend analysis for daylight exposure."""
    period_days: int
    slope: float = Field(description="Change per day (minutes)")
    slope_pct: float = Field(description="Percent change over period")
    p_value: float
    r_squared: float
    is_significant: bool
    direction: str = Field(description="increasing, decreasing, or stable")
    interpretation: str


class DaylightSleepCorrelationSchema(BaseModel):
    """Correlation between daylight and a sleep metric."""
    sleep_metric: str = Field(description="Which sleep metric")
    lag_days: int = Field(description="0 = same night, 1 = next night")
    correlation: float = Field(description="Pearson correlation coefficient")
    p_value: float
    n_pairs: int = Field(description="Number of day-night pairs analyzed")
    is_significant: bool
    interpretation: str


class DaylightReportSchema(BaseModel):
    """Complete daylight analysis report."""
    baseline: Optional[DaylightBaselineSchema]
    recent_days: List[DailyDaylightSchema]
    current_deviation: Optional[DaylightDeviationSchema]
    trend: Optional[DaylightTrendSchema]
    sleep_correlations: List[DaylightSleepCorrelationSchema]

    avg_daily_min_30d: Optional[float]
    avg_morning_min_30d: Optional[float]
    pct_days_morning_light_30d: Optional[float]

    concerns: List[str] = Field(description="Issues requiring attention")
    insights: List[str] = Field(description="Positive findings")


class DaylightSummary(BaseModel):
    """Quick summary of daylight exposure health."""
    has_sufficient_data: bool
    n_days_analyzed: int
    avg_daily_min: Optional[float]
    avg_morning_min: Optional[float]
    pct_days_morning_light: Optional[float]
    is_sufficient: Optional[bool]
    consistency_score: Optional[float]
    top_concern: Optional[str]
    overall_assessment: str
