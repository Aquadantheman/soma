"""Advanced analysis schemas.

Cross-correlations, recovery models, seasonality, and readiness scoring.
"""

from pydantic import BaseModel
from typing import Optional


class CorrelationPairSchema(BaseModel):
    """A single correlation between two biomarkers."""

    biomarker_a: str
    biomarker_b: str
    pearson_r: float
    pearson_p: float
    spearman_rho: float
    spearman_p: float
    n_observations: int
    ci_lower: float
    ci_upper: float
    is_significant: bool  # After Bonferroni correction
    effect_size: str  # "negligible", "small", "medium", "large"


class CorrelationMatrixAnalysis(BaseModel):
    """Full correlation analysis between biomarkers."""

    pairs: list[CorrelationPairSchema]
    biomarkers_analyzed: list[str]
    bonferroni_alpha: float
    significant_pairs: list[CorrelationPairSchema]
    method_note: str


class LaggedCorrelationSchema(BaseModel):
    """Correlation at a specific time lag."""

    lag_days: int
    correlation: float
    p_value: float
    ci_lower: float
    ci_upper: float
    n_observations: int
    is_significant: bool


class RecoveryAnalysis(BaseModel):
    """Model of how activity affects next-day recovery metrics."""

    predictor: str
    outcome: str
    lagged_correlations: list[LaggedCorrelationSchema]
    optimal_lag: int
    optimal_correlation: float
    optimal_p_value: float
    interpretation: str
    is_significant: bool
    regression_slope: Optional[float]
    regression_intercept: Optional[float]
    r_squared: Optional[float]


class SeasonalComponentSchema(BaseModel):
    """Decomposed seasonal pattern for a month."""

    month: int
    month_name: str
    mean_value: float
    ci_lower: float
    ci_upper: float
    n_observations: int
    deviation_from_annual: float


class SeasonalAnalysisSchema(BaseModel):
    """Full seasonal decomposition for a biomarker."""

    biomarker_slug: str
    annual_mean: float
    seasonal_components: list[SeasonalComponentSchema]
    peak_month: str
    trough_month: str
    seasonal_amplitude: float
    seasonality_strength: float  # 0-1, variance explained
    f_statistic: float
    p_value: float
    is_significant: bool


class ReadinessScoreSchema(BaseModel):
    """Readiness score for a specific day."""

    date: str
    score: float  # 0-100
    hrv_z_score: Optional[float]
    rhr_z_score: Optional[float]
    components: dict[str, float]
    interpretation: str  # "optimal", "good", "moderate", "low", "poor"


class ReadinessModelSchema(BaseModel):
    """Model parameters for readiness scoring."""

    hrv_baseline_mean: float
    hrv_baseline_std: float
    rhr_baseline_mean: float
    rhr_baseline_std: float
    weights: dict[str, float]
    score_distribution: dict[str, float]
    method_note: str


class ReadinessSummary(BaseModel):
    """Summary of readiness scores."""

    total_days: int
    mean_score: float
    std_score: float
    current_score: Optional[float]
    current_interpretation: Optional[str]
    trend_7d: Optional[str]  # "improving", "stable", "declining"
    trend_p_value: Optional[float]
    interpretation_distribution: dict[str, int]
    recent_scores: list[ReadinessScoreSchema]  # Last 30 days


class AdvancedAnalysisResult(BaseModel):
    """Complete advanced statistical analysis."""

    correlations: Optional[CorrelationMatrixAnalysis] = None
    recovery_hrv: Optional[RecoveryAnalysis] = None
    recovery_rhr: Optional[RecoveryAnalysis] = None
    seasonality_steps: Optional[SeasonalAnalysisSchema] = None
    seasonality_hr: Optional[SeasonalAnalysisSchema] = None
    readiness: Optional[ReadinessSummary] = None
    proven_claims: list[str]
    methodology_notes: list[str]
