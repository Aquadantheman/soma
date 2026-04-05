"""Stability analysis schemas.

Data quality assessment, convergence, temporal stability, and drift detection.
"""

from pydantic import BaseModel


class ConvergencePointSchema(BaseModel):
    """Estimate at a specific sample size checkpoint."""

    n: int
    mean: float
    ci_width: float
    ci_pct: float  # CI width as % of mean
    status: str  # "stable", "converging", "unstable"


class ConvergenceAnalysisSchema(BaseModel):
    """How estimates stabilize with increasing sample size."""

    biomarker_slug: str
    current_n: int
    current_mean: float
    current_ci_width: float
    convergence_points: list[ConvergencePointSchema]
    min_n_for_stability: int  # Samples needed for CI < 2% of mean
    is_stable: bool
    drift_from_initial: float  # % change from first to final estimate


class TemporalStabilitySchema(BaseModel):
    """Stability of a metric across different time periods."""

    biomarker_slug: str
    metric: str  # e.g., "mean"
    periods: list[dict]  # year/period -> value
    mean_value: float
    std_across_periods: float
    is_stable: bool  # std < threshold
    consistency_pct: float  # % of periods with similar values


class DriftResultSchema(BaseModel):
    """Comparison of recent vs historical data."""

    biomarker_slug: str
    recent_mean: float
    recent_n: int
    historical_mean: float
    historical_n: int
    absolute_change: float
    pct_change: float
    t_statistic: float
    p_value: float
    is_significant: bool
    direction: str  # "increasing", "decreasing", "stable"


class SampleAdequacySchema(BaseModel):
    """Whether you have enough data for reliable inference."""

    biomarker_slug: str
    current_n: int
    required_n_5pct: int  # For 5% precision
    required_n_2pct: int  # For 2% precision
    is_adequate: bool
    adequacy_ratio: float  # current_n / required_n


class StabilityReportSchema(BaseModel):
    """Complete stability assessment."""

    convergence: list[ConvergenceAnalysisSchema]
    temporal_stability: list[TemporalStabilitySchema]
    drift: list[DriftResultSchema]
    sample_adequacy: list[SampleAdequacySchema]
    overall_assessment: str
    recommendations: list[str]
