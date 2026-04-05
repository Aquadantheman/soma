"""VO2 Max analysis schemas.

All schemas correspond to peer-reviewed, validated analyses.
"""

from datetime import date
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field


class VO2MaxMeasurementSchema(BaseModel):
    """Single VO2 Max measurement."""
    date: date
    value: float = Field(description="VO2 Max in mL/kg/min")
    mets: float = Field(description="Metabolic equivalents (VO2/3.5)")


class VO2MaxPercentileSchema(BaseModel):
    """Percentile ranking based on ACSM age/sex norms."""
    percentile: int = Field(description="Percentile rank (0-100)")
    category: str = Field(description="Fitness category (Superior/Excellent/Good/Fair/Poor/Very Poor)")
    comparison_group: str = Field(description="Reference population")
    reference: str = Field(description="Scientific citation")


class FitnessAgeSchema(BaseModel):
    """Fitness age calculation from HUNT Fitness Study."""
    chronological_age: int
    fitness_age: int
    difference: int = Field(description="Positive = younger than chronological age")
    interpretation: str
    reference: str


class VO2MaxTrendSchema(BaseModel):
    """Trend analysis with confidence intervals."""
    period_days: int
    n_measurements: int

    start_value: float
    end_value: float
    change: float
    change_pct: float

    slope: float = Field(description="Change per day (mL/kg/min)")
    slope_annual: float = Field(description="Projected annual change")

    ci_lower: float = Field(description="95% CI lower bound for slope")
    ci_upper: float = Field(description="95% CI upper bound for slope")

    p_value: float
    is_significant: bool

    interpretation: str


class MortalityRiskSchema(BaseModel):
    """Mortality risk from Kodama et al. meta-analysis."""
    mets: float
    risk_category: str = Field(description="Low/Moderate/High")
    relative_risk: float = Field(description="Relative risk compared to lowest fitness")
    interpretation: str
    reference: str


class TrainingResponseSchema(BaseModel):
    """Training response assessment."""
    baseline_vo2: float
    current_vo2: float
    change: float
    change_pct: float

    is_responder: bool = Field(description=">3% improvement indicates response")
    response_category: str = Field(description="High/Moderate/Low/Non-responder")

    interpretation: str
    reference: str


class CorrelationSchema(BaseModel):
    """Validated correlation with other metrics."""
    metric: str
    r: float = Field(description="Pearson correlation coefficient")
    p_value: float
    n: int = Field(description="Sample size")
    is_significant: bool
    literature_expected: str = Field(description="Expected direction from literature")


class VO2MaxReportSchema(BaseModel):
    """Complete VO2 Max analysis report."""
    # Current status
    latest_measurement: VO2MaxMeasurementSchema
    percentile: Optional[VO2MaxPercentileSchema]
    fitness_age: Optional[FitnessAgeSchema]
    mortality_risk: MortalityRiskSchema

    # Longitudinal analysis
    measurements: List[VO2MaxMeasurementSchema]
    trend: Optional[VO2MaxTrendSchema]
    training_response: Optional[TrainingResponseSchema]

    # Validated correlations
    hrv_correlation: Optional[CorrelationSchema]
    rhr_correlation: Optional[CorrelationSchema]

    # Summary
    insights: List[str]
    recommendations: List[str]


class VO2MaxSummarySchema(BaseModel):
    """Quick summary of VO2 Max fitness status."""
    has_sufficient_data: bool
    n_measurements: int
    latest_value: Optional[float]
    latest_mets: Optional[float]
    category: Optional[str]
    mortality_risk: Optional[str]
    trend_direction: Optional[str]
    overall_assessment: str
