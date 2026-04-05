"""Body Composition analysis schemas.

All schemas correspond to peer-reviewed, validated analyses:
- BMI: WHO classification
- Body Fat %: ACSM age/sex norms
- Trend analysis: OLS regression with confidence intervals
"""

from datetime import date
from typing import Optional, List
from pydantic import BaseModel, Field


class BMISchema(BaseModel):
    """BMI calculation with WHO classification."""

    bmi: float = Field(description="Body Mass Index (kg/m^2)")
    category: str = Field(
        description="WHO category: Underweight/Normal/Overweight/Obese I-III"
    )
    health_risk: str = Field(description="Associated health risk level")
    reference: str = Field(description="Scientific citation")


class BodyFatPercentileSchema(BaseModel):
    """Body fat percentage with ACSM percentile ranking."""

    body_fat_pct: float = Field(description="Body fat percentage")
    percentile: int = Field(description="Percentile rank (0-100)")
    category: str = Field(
        description="Category: Essential/Athletes/Fitness/Average/Obese"
    )
    comparison_group: str = Field(description="Reference population")
    is_healthy: bool = Field(description="Within healthy range for age/sex")
    healthy_range: List[float] = Field(description="Healthy body fat range [min, max]")
    reference: str = Field(description="Scientific citation")


class WeightMeasurementSchema(BaseModel):
    """Single weight measurement with derived metrics."""

    date: date
    weight_kg: float
    weight_lb: float
    bmi: Optional[float] = None
    body_fat_pct: Optional[float] = None
    lean_mass_kg: Optional[float] = None
    fat_mass_kg: Optional[float] = None


class WeightTrendSchema(BaseModel):
    """Weight trend analysis with confidence intervals."""

    period_days: int
    n_measurements: int

    start_weight: float
    end_weight: float
    change_kg: float
    change_pct: float

    slope_daily: float = Field(description="Weight change per day (kg)")
    slope_weekly: float = Field(description="Weight change per week (kg)")

    ci_lower: float = Field(description="95% CI lower bound for weekly slope")
    ci_upper: float = Field(description="95% CI upper bound for weekly slope")

    p_value: float
    is_significant: bool

    direction: str = Field(description="'gaining', 'losing', or 'stable'")
    interpretation: str


class BodyCompositionChangeSchema(BaseModel):
    """Body composition change assessment."""

    period_days: int
    n_measurements: int

    weight_change_kg: float
    body_fat_change_pct: Optional[float] = Field(
        None, description="Change in body fat percentage points"
    )
    lean_mass_change_kg: Optional[float] = None
    fat_mass_change_kg: Optional[float] = None

    composition_quality: str = Field(
        description="'Favorable', 'Neutral', or 'Unfavorable'"
    )
    interpretation: str


class FitnessCorrelationSchema(BaseModel):
    """Correlation between body composition and fitness metrics."""

    metric: str
    r: float = Field(description="Pearson correlation coefficient")
    p_value: float
    n: int = Field(description="Sample size")
    is_significant: bool
    direction: str = Field(description="'positive' or 'negative'")
    interpretation: str


class BodyCompositionReportSchema(BaseModel):
    """Complete body composition analysis report."""

    # Current status
    latest_measurement: WeightMeasurementSchema
    bmi: Optional[BMISchema] = None
    body_fat_percentile: Optional[BodyFatPercentileSchema] = None

    # Historical data
    measurements: List[WeightMeasurementSchema]
    weight_trend: Optional[WeightTrendSchema] = None
    composition_change: Optional[BodyCompositionChangeSchema] = None

    # Fitness correlations
    vo2max_correlation: Optional[FitnessCorrelationSchema] = None
    rhr_correlation: Optional[FitnessCorrelationSchema] = None

    # Summary
    insights: List[str]
    recommendations: List[str]


class BodyCompositionSummarySchema(BaseModel):
    """Quick summary of body composition status."""

    has_sufficient_data: bool
    n_weight_measurements: int
    n_body_fat_measurements: int

    latest_weight_kg: Optional[float] = None
    latest_bmi: Optional[float] = None
    bmi_category: Optional[str] = None

    latest_body_fat_pct: Optional[float] = None
    body_fat_category: Optional[str] = None

    weight_trend_direction: Optional[str] = None
    overall_assessment: str
