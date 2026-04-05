"""Sleep architecture analysis schemas."""

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


class NightlySleepSchema(BaseModel):
    """Sleep metrics for a single night."""
    date: date
    rem_min: float = Field(description="Minutes in REM sleep")
    deep_min: float = Field(description="Minutes in deep sleep")
    core_min: float = Field(description="Minutes in core/light sleep")
    in_bed_min: float = Field(description="Total minutes in bed")
    total_sleep_min: float = Field(description="Total sleep (REM + Deep + Core)")
    rem_pct: float = Field(description="REM as percentage of total sleep")
    deep_pct: float = Field(description="Deep as percentage of total sleep")
    core_pct: float = Field(description="Core as percentage of total sleep")
    efficiency: float = Field(description="Sleep efficiency (total sleep / in bed)")


class SleepArchitectureBaselineSchema(BaseModel):
    """Personal baseline for sleep architecture."""
    computed_at: str
    n_nights: int = Field(description="Number of nights in baseline")

    total_sleep: ConfidenceIntervalSchema
    rem_duration: ConfidenceIntervalSchema
    deep_duration: ConfidenceIntervalSchema
    core_duration: ConfidenceIntervalSchema
    in_bed_duration: ConfidenceIntervalSchema

    rem_pct: ConfidenceIntervalSchema
    deep_pct: ConfidenceIntervalSchema
    core_pct: ConfidenceIntervalSchema
    efficiency: ConfidenceIntervalSchema

    is_stable: bool = Field(description="Whether sleep patterns are consistent")
    consistency_score: float = Field(description="Sleep consistency score (0-100)")


class SleepArchitectureDeviationSchema(BaseModel):
    """How a night's sleep deviates from personal baseline."""
    date: date

    total_sleep_z: float = Field(description="Z-score for total sleep duration")
    rem_pct_z: float = Field(description="Z-score for REM percentage")
    deep_pct_z: float = Field(description="Z-score for deep sleep percentage")
    efficiency_z: float = Field(description="Z-score for sleep efficiency")

    is_rem_low: bool
    is_deep_low: bool
    is_efficiency_low: bool
    is_notable: bool = Field(description="Whether any deviation is significant")

    interpretation: str


class SleepArchitectureTrendSchema(BaseModel):
    """Trend analysis for a sleep metric."""
    metric: str = Field(description="Which metric (rem_pct, deep_pct, etc.)")
    period_days: int

    slope: float = Field(description="Change per day")
    slope_pct: float = Field(description="Percent change over period")
    p_value: float
    r_squared: float

    is_significant: bool
    direction: Optional[str] = Field(description="improving, declining, or stable")
    interpretation: str


class SleepArchitectureReportSchema(BaseModel):
    """Complete sleep architecture analysis report."""
    baseline: Optional[SleepArchitectureBaselineSchema]
    recent_nights: List[NightlySleepSchema]
    current_deviation: Optional[SleepArchitectureDeviationSchema]

    trends: List[SleepArchitectureTrendSchema]

    concerns: List[str] = Field(description="Issues requiring attention")
    insights: List[str] = Field(description="Positive findings")

    avg_rem_pct_30d: Optional[float]
    avg_deep_pct_30d: Optional[float]
    avg_efficiency_30d: Optional[float]


class SleepSummary(BaseModel):
    """Quick summary of sleep health."""
    has_sufficient_data: bool
    n_nights_analyzed: int
    avg_total_sleep_min: Optional[float]
    avg_rem_pct: Optional[float]
    avg_deep_pct: Optional[float]
    avg_efficiency: Optional[float]
    consistency_score: Optional[float]
    top_concern: Optional[str]
    overall_assessment: str
