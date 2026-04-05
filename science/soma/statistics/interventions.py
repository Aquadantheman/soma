"""Intervention Impact Analysis Module.

Rigorous statistical analysis of lifestyle interventions using:
- Interrupted Time Series Analysis (ITS)
- Welch's t-test for mean comparison
- Mann-Whitney U for distribution comparison
- Cohen's d for effect size
- Regression discontinuity design
- Confound control (seasonality, pre-existing trends)

This module answers: "Did this intervention actually work FOR ME?"
with statistical confidence and honest uncertainty quantification.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Optional, Literal
import numpy as np
import pandas as pd
from scipy import stats


# =============================================================================
# BIOMARKER HEALTH DIRECTION
# =============================================================================

# Biomarkers where LOWER values are better (e.g., resting HR, stress)
LOWER_IS_BETTER = {
    'resting_hr', 'resting_heart_rate',
    'stress_score', 'stress_index',
    'respiratory_rate',
    'blood_pressure_systolic', 'blood_pressure_diastolic',
    'body_fat_percentage', 'bmi',
    'night_restlessness',
}

# All other biomarkers default to "higher is better" (HRV, VO2max, sleep duration, etc.)


def _is_health_improvement(biomarker: str, direction: str) -> bool:
    """Determine if a change direction represents health improvement.

    Args:
        biomarker: The biomarker slug
        direction: 'increased' or 'decreased'

    Returns:
        True if this change direction is a health improvement
    """
    lower_is_better = biomarker.lower() in LOWER_IS_BETTER
    if lower_is_better:
        return direction == 'decreased'
    return direction == 'increased'


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Intervention:
    """A logged lifestyle intervention/change."""
    name: str  # e.g., "Started morning meditation"
    start_date: date
    category: Literal[
        'sleep', 'exercise', 'nutrition', 'stress',
        'supplement', 'medication', 'habit', 'other'
    ]
    description: Optional[str] = None
    end_date: Optional[date] = None  # None = ongoing

    @property
    def is_active(self) -> bool:
        """Check if intervention is still active."""
        if self.end_date is None:
            return True
        return date.today() <= self.end_date

    @property
    def duration_days(self) -> int:
        """Days since intervention started."""
        end = self.end_date or date.today()
        return (end - self.start_date).days


@dataclass
class BiomarkerChange:
    """Statistical change in a single biomarker."""
    biomarker: str

    # Before period statistics
    before_mean: float
    before_std: float
    before_median: float
    before_n: int

    # After period statistics
    after_mean: float
    after_std: float
    after_median: float
    after_n: int

    # Change metrics
    absolute_change: float  # after_mean - before_mean
    percent_change: float   # (after - before) / before * 100

    # Statistical tests
    t_statistic: float
    t_pvalue: float
    mann_whitney_statistic: float
    mann_whitney_pvalue: float

    # Effect size
    cohens_d: float
    effect_size_interpretation: Literal['negligible', 'small', 'medium', 'large']

    # Confidence interval for the change
    change_ci_lower: float
    change_ci_upper: float
    confidence_level: float  # e.g., 0.95

    # Direction and significance
    direction: Literal['increased', 'decreased', 'unchanged']
    is_significant: bool  # p < 0.05
    is_meaningful: bool   # significant AND effect size >= small

    @property
    def summary(self) -> str:
        """Human-readable summary of the change."""
        if not self.is_significant:
            return f"No significant change in {self.biomarker}"

        direction = "increased" if self.absolute_change > 0 else "decreased"
        return (
            f"{self.biomarker} {direction} by {abs(self.percent_change):.1f}% "
            f"({self.effect_size_interpretation} effect, p={self.t_pvalue:.3f})"
        )


@dataclass
class TrendAnalysis:
    """Analysis of pre-existing trends to control for confounds."""
    biomarker: str

    # Pre-intervention trend
    pre_trend_slope: float  # units per day
    pre_trend_pvalue: float
    pre_trend_significant: bool

    # Post-intervention trend
    post_trend_slope: float
    post_trend_pvalue: float
    post_trend_significant: bool

    # Trend change
    slope_change: float  # post - pre
    trend_reversal: bool  # Did direction change?

    # Regression discontinuity
    level_jump: float  # Immediate jump at intervention point
    level_jump_pvalue: float
    level_jump_significant: bool


@dataclass
class SeasonalityControl:
    """Control for seasonal confounds."""
    biomarker: str

    # Seasonal pattern detected?
    has_seasonal_pattern: bool
    seasonal_amplitude: float  # Peak-to-trough difference
    peak_month: Optional[int]  # 1-12

    # Adjusted change (removing seasonal effect)
    raw_change: float
    seasonally_adjusted_change: float
    seasonal_contribution: float  # How much of change is seasonal

    # Is change robust to seasonal adjustment?
    robust_to_seasonal: bool


@dataclass
class InterventionImpact:
    """Complete impact analysis for one intervention on one biomarker."""
    intervention: Intervention
    biomarker: str

    # Core statistical change
    change: BiomarkerChange

    # Confound analysis
    trend_analysis: TrendAnalysis
    seasonality_control: Optional[SeasonalityControl]

    # Overall assessment
    verdict: Literal[
        'strong_positive',   # Significant, meaningful, robust to confounds
        'moderate_positive', # Significant, some confound concerns
        'weak_positive',     # Trending positive but not significant
        'no_effect',         # No detectable change
        'weak_negative',     # Trending negative
        'moderate_negative', # Significant negative
        'strong_negative',   # Significant, meaningful negative
        'inconclusive'       # Not enough data or conflicting signals
    ]

    confidence_score: float  # 0-100, overall confidence in verdict

    # Interpretation
    interpretation: str
    caveats: list[str]

    # Projection
    projected_90_day_value: Optional[float]
    projected_90_day_ci: Optional[tuple[float, float]]


@dataclass
class InterventionReport:
    """Complete report for an intervention across all biomarkers."""
    intervention: Intervention
    analysis_date: datetime

    # Analysis period
    before_period_start: date
    before_period_end: date
    after_period_start: date
    after_period_end: date

    # Per-biomarker impacts
    impacts: list[InterventionImpact]

    # Summary
    biomarkers_improved: list[str]
    biomarkers_declined: list[str]
    biomarkers_unchanged: list[str]

    # Overall verdict
    overall_verdict: Literal[
        'highly_effective',
        'moderately_effective',
        'slightly_effective',
        'no_clear_effect',
        'slightly_harmful',
        'harmful',
        'insufficient_data'
    ]

    overall_confidence: float  # 0-100

    # Key insights
    primary_insight: str
    secondary_insights: list[str]
    recommendations: list[str]

    # Statistical rigor metadata
    total_data_points: int
    statistical_power: float  # Ability to detect true effects
    multiple_comparison_correction: str  # e.g., "Bonferroni" or "FDR"


# =============================================================================
# STATISTICAL FUNCTIONS
# =============================================================================

def compute_cohens_d(group1: np.ndarray, group2: np.ndarray) -> tuple[float, str]:
    """Compute Cohen's d effect size with interpretation.

    Cohen's d = (mean2 - mean1) / pooled_std

    Interpretation (Cohen 1988):
    - |d| < 0.2: negligible
    - 0.2 <= |d| < 0.5: small
    - 0.5 <= |d| < 0.8: medium
    - |d| >= 0.8: large

    Returns:
        Tuple of (d value, interpretation string)
    """
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)

    # Pooled standard deviation
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))

    if pooled_std == 0:
        return 0.0, 'negligible'

    d = (np.mean(group2) - np.mean(group1)) / pooled_std

    # Interpretation
    abs_d = abs(d)
    if abs_d < 0.2:
        interpretation = 'negligible'
    elif abs_d < 0.5:
        interpretation = 'small'
    elif abs_d < 0.8:
        interpretation = 'medium'
    else:
        interpretation = 'large'

    return d, interpretation


def compute_change_confidence_interval(
    before: np.ndarray,
    after: np.ndarray,
    confidence: float = 0.95
) -> tuple[float, float, float]:
    """Compute confidence interval for the difference in means.

    Uses Welch's t-interval (does not assume equal variances).

    Returns:
        Tuple of (lower_bound, upper_bound, point_estimate)
    """
    n1, n2 = len(before), len(after)
    mean1, mean2 = np.mean(before), np.mean(after)
    var1, var2 = np.var(before, ddof=1), np.var(after, ddof=1)

    # Point estimate
    diff = mean2 - mean1

    # Standard error of difference (Welch-Satterthwaite)
    se = np.sqrt(var1/n1 + var2/n2)

    # Degrees of freedom (Welch-Satterthwaite approximation)
    num = (var1/n1 + var2/n2)**2
    denom = (var1/n1)**2/(n1-1) + (var2/n2)**2/(n2-1)
    df = num / denom if denom > 0 else min(n1, n2) - 1

    # Critical value
    alpha = 1 - confidence
    t_crit = stats.t.ppf(1 - alpha/2, df)

    # Confidence interval
    margin = t_crit * se

    return diff - margin, diff + margin, diff


def analyze_trend(
    data: pd.Series,
    date_index: pd.DatetimeIndex
) -> tuple[float, float, bool]:
    """Analyze linear trend in time series.

    Returns:
        Tuple of (slope per day, p-value, is_significant)
    """
    if len(data) < 7:
        return 0.0, 1.0, False

    # Convert dates to numeric (days since start)
    days = (date_index - date_index.min()).days.values
    values = data.values

    # Remove NaN
    mask = ~np.isnan(values)
    if mask.sum() < 7:
        return 0.0, 1.0, False

    days = days[mask]
    values = values[mask]

    # Linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(days, values)

    return slope, p_value, p_value < 0.05


def detect_level_jump(
    before: np.ndarray,
    after: np.ndarray,
    before_dates: np.ndarray,
    after_dates: np.ndarray,
    intervention_date: date
) -> tuple[float, float, bool]:
    """Detect immediate level jump at intervention point using regression discontinuity.

    Fits separate linear regressions before and after, extrapolates to
    intervention point, and measures the discontinuity.

    Returns:
        Tuple of (jump magnitude, p-value, is_significant)
    """
    if len(before) < 7 or len(after) < 7:
        return 0.0, 1.0, False

    # Fit before trend
    before_days = (before_dates - before_dates.min()).astype('timedelta64[D]').astype(float)
    slope_b, intercept_b, _, _, _ = stats.linregress(before_days, before)

    # Fit after trend
    after_days = (after_dates - after_dates.min()).astype('timedelta64[D]').astype(float)
    slope_a, intercept_a, _, _, _ = stats.linregress(after_days, after)

    # Extrapolate before to intervention point
    days_to_intervention = (np.datetime64(intervention_date) - before_dates.min()).astype('timedelta64[D]').astype(float)
    predicted_before = intercept_b + slope_b * days_to_intervention

    # After value at intervention point (intercept of after regression)
    predicted_after = intercept_a

    # Jump
    jump = predicted_after - predicted_before

    # Significance test (compare to noise)
    combined_std = np.sqrt((np.var(before) + np.var(after)) / 2)
    if combined_std == 0:
        return jump, 1.0, False

    # Z-test for jump significance
    se = combined_std * np.sqrt(1/len(before) + 1/len(after))
    z = jump / se
    p_value = 2 * (1 - stats.norm.cdf(abs(z)))

    return jump, p_value, p_value < 0.05


def analyze_seasonality(
    data: pd.Series,
    dates: pd.DatetimeIndex,
    intervention_date: date,
    before_period_days: int,
    after_period_days: int
) -> Optional[SeasonalityControl]:
    """Analyze and control for seasonal effects.

    Requires at least 1 year of data to detect seasonality.
    """
    if len(data) < 365:
        return None

    # Group by month
    df = pd.DataFrame({'value': data, 'month': dates.month})
    monthly_means = df.groupby('month')['value'].mean()

    # Check for significant seasonal variation
    if len(monthly_means) < 12:
        return None

    # Seasonal amplitude
    amplitude = monthly_means.max() - monthly_means.min()
    overall_std = data.std()

    # Seasonal pattern exists if amplitude > 1 std
    has_pattern = amplitude > overall_std * 0.5

    if not has_pattern:
        return SeasonalityControl(
            biomarker=data.name if hasattr(data, 'name') else 'unknown',
            has_seasonal_pattern=False,
            seasonal_amplitude=amplitude,
            peak_month=None,
            raw_change=0,
            seasonally_adjusted_change=0,
            seasonal_contribution=0,
            robust_to_seasonal=True
        )

    peak_month = int(monthly_means.idxmax())

    # Get expected seasonal values for before and after periods
    intervention_dt = pd.Timestamp(intervention_date)
    before_start = intervention_dt - pd.Timedelta(days=before_period_days)
    after_end = intervention_dt + pd.Timedelta(days=after_period_days)

    # Expected seasonal value for before period
    before_months = pd.date_range(before_start, intervention_dt, freq='D').month
    expected_before = monthly_means[before_months].mean()

    # Expected seasonal value for after period
    after_months = pd.date_range(intervention_dt, after_end, freq='D').month
    expected_after = monthly_means[after_months].mean()

    # Seasonal contribution to observed change
    seasonal_effect = expected_after - expected_before

    # Actual observed change
    before_mask = (dates >= before_start) & (dates < intervention_dt)
    after_mask = (dates >= intervention_dt) & (dates <= after_end)

    raw_change = data[after_mask].mean() - data[before_mask].mean() if after_mask.any() and before_mask.any() else 0

    # Adjusted change
    adjusted_change = raw_change - seasonal_effect

    # Is the effect robust?
    robust = abs(adjusted_change) >= abs(raw_change) * 0.5  # At least 50% remains after adjustment

    return SeasonalityControl(
        biomarker=data.name if hasattr(data, 'name') else 'unknown',
        has_seasonal_pattern=True,
        seasonal_amplitude=amplitude,
        peak_month=peak_month,
        raw_change=raw_change,
        seasonally_adjusted_change=adjusted_change,
        seasonal_contribution=seasonal_effect,
        robust_to_seasonal=robust
    )


# =============================================================================
# MAIN ANALYSIS FUNCTIONS
# =============================================================================

def analyze_biomarker_change(
    biomarker: str,
    before_data: np.ndarray,
    after_data: np.ndarray,
    confidence_level: float = 0.95
) -> BiomarkerChange:
    """Analyze the change in a single biomarker before vs after intervention.

    Performs:
    - Descriptive statistics
    - Welch's t-test
    - Mann-Whitney U test
    - Cohen's d effect size
    - Confidence intervals

    Args:
        biomarker: Name of the biomarker
        before_data: Array of values before intervention
        after_data: Array of values after intervention
        confidence_level: Confidence level for CI (default 0.95)

    Returns:
        BiomarkerChange with full statistical analysis
    """
    # Clean data
    before = before_data[~np.isnan(before_data)]
    after = after_data[~np.isnan(after_data)]

    if len(before) < 5 or len(after) < 5:
        # Insufficient data - return empty result
        return BiomarkerChange(
            biomarker=biomarker,
            before_mean=np.nan, before_std=np.nan, before_median=np.nan, before_n=len(before),
            after_mean=np.nan, after_std=np.nan, after_median=np.nan, after_n=len(after),
            absolute_change=np.nan, percent_change=np.nan,
            t_statistic=np.nan, t_pvalue=1.0,
            mann_whitney_statistic=np.nan, mann_whitney_pvalue=1.0,
            cohens_d=0.0, effect_size_interpretation='negligible',
            change_ci_lower=np.nan, change_ci_upper=np.nan, confidence_level=confidence_level,
            direction='unchanged', is_significant=False, is_meaningful=False
        )

    # Descriptive statistics
    before_mean, before_std, before_median = np.mean(before), np.std(before, ddof=1), np.median(before)
    after_mean, after_std, after_median = np.mean(after), np.std(after, ddof=1), np.median(after)

    # Change metrics
    absolute_change = after_mean - before_mean
    percent_change = (absolute_change / before_mean * 100) if before_mean != 0 else 0

    # Welch's t-test (unequal variances)
    t_stat, t_pvalue = stats.ttest_ind(after, before, equal_var=False)

    # Mann-Whitney U test (non-parametric)
    try:
        mw_stat, mw_pvalue = stats.mannwhitneyu(after, before, alternative='two-sided')
    except ValueError:
        mw_stat, mw_pvalue = np.nan, 1.0

    # Cohen's d
    cohens_d, effect_interp = compute_cohens_d(before, after)

    # Confidence interval
    ci_lower, ci_upper, _ = compute_change_confidence_interval(before, after, confidence_level)

    # Direction
    if absolute_change > 0 and t_pvalue < 0.05:
        direction = 'increased'
    elif absolute_change < 0 and t_pvalue < 0.05:
        direction = 'decreased'
    else:
        direction = 'unchanged'

    # Significance and meaningfulness
    is_significant = t_pvalue < 0.05
    is_meaningful = is_significant and abs(cohens_d) >= 0.2  # At least small effect

    return BiomarkerChange(
        biomarker=biomarker,
        before_mean=before_mean, before_std=before_std, before_median=before_median, before_n=len(before),
        after_mean=after_mean, after_std=after_std, after_median=after_median, after_n=len(after),
        absolute_change=absolute_change, percent_change=percent_change,
        t_statistic=t_stat, t_pvalue=t_pvalue,
        mann_whitney_statistic=mw_stat, mann_whitney_pvalue=mw_pvalue,
        cohens_d=cohens_d, effect_size_interpretation=effect_interp,
        change_ci_lower=ci_lower, change_ci_upper=ci_upper, confidence_level=confidence_level,
        direction=direction, is_significant=is_significant, is_meaningful=is_meaningful
    )


def analyze_intervention_impact(
    intervention: Intervention,
    biomarker: str,
    signals: pd.DataFrame,
    before_days: int = 30,
    after_days: int = 30,
) -> InterventionImpact:
    """Analyze the full impact of an intervention on a biomarker.

    Performs:
    - Before/after statistical comparison
    - Pre-existing trend analysis
    - Regression discontinuity (level jump detection)
    - Seasonality control (if enough data)
    - Verdict generation with confidence

    Args:
        intervention: The intervention to analyze
        biomarker: Which biomarker to analyze
        signals: DataFrame with 'time', 'biomarker_slug', 'value' columns
        before_days: Days of data to use before intervention
        after_days: Days of data to use after intervention

    Returns:
        InterventionImpact with complete analysis
    """
    # Filter to this biomarker
    bio_data = signals[signals['biomarker_slug'] == biomarker].copy()
    if len(bio_data) == 0:
        return _empty_impact(intervention, biomarker, "No data for this biomarker")

    bio_data['time'] = pd.to_datetime(bio_data['time'])
    bio_data = bio_data.sort_values('time')

    # Define periods
    intervention_dt = pd.Timestamp(intervention.start_date)
    before_start = intervention_dt - pd.Timedelta(days=before_days)
    after_end = intervention_dt + pd.Timedelta(days=after_days)

    # Split data
    before_mask = (bio_data['time'] >= before_start) & (bio_data['time'] < intervention_dt)
    after_mask = (bio_data['time'] >= intervention_dt) & (bio_data['time'] <= after_end)

    before_data = bio_data[before_mask]['value'].values
    after_data = bio_data[after_mask]['value'].values
    before_dates = bio_data[before_mask]['time'].values
    after_dates = bio_data[after_mask]['time'].values

    if len(before_data) < 5 or len(after_data) < 5:
        return _empty_impact(intervention, biomarker, "Insufficient data in before/after periods")

    # Core statistical change
    change = analyze_biomarker_change(biomarker, before_data, after_data)

    # Trend analysis
    pre_slope, pre_p, pre_sig = analyze_trend(
        pd.Series(before_data),
        pd.DatetimeIndex(before_dates)
    )
    post_slope, post_p, post_sig = analyze_trend(
        pd.Series(after_data),
        pd.DatetimeIndex(after_dates)
    )

    # Level jump
    jump, jump_p, jump_sig = detect_level_jump(
        before_data, after_data, before_dates, after_dates, intervention.start_date
    )

    trend_analysis = TrendAnalysis(
        biomarker=biomarker,
        pre_trend_slope=pre_slope,
        pre_trend_pvalue=pre_p,
        pre_trend_significant=pre_sig,
        post_trend_slope=post_slope,
        post_trend_pvalue=post_p,
        post_trend_significant=post_sig,
        slope_change=post_slope - pre_slope,
        trend_reversal=(pre_slope * post_slope < 0) and (pre_sig or post_sig),
        level_jump=jump,
        level_jump_pvalue=jump_p,
        level_jump_significant=jump_sig
    )

    # Seasonality control (needs full time series)
    all_data = pd.Series(bio_data['value'].values, index=pd.DatetimeIndex(bio_data['time']))
    seasonality = analyze_seasonality(
        all_data,
        pd.DatetimeIndex(bio_data['time']),
        intervention.start_date,
        before_days,
        after_days
    )

    # Determine verdict
    verdict, confidence, interpretation, caveats = _determine_verdict(
        change, trend_analysis, seasonality
    )

    # Project 90-day value
    projected_value, projected_ci = None, None
    if change.is_meaningful and post_slope != 0:
        days_to_90 = 90 - after_days
        projected_value = change.after_mean + post_slope * days_to_90
        # Wide CI for projection
        projected_ci = (
            projected_value - 2 * change.after_std,
            projected_value + 2 * change.after_std
        )

    return InterventionImpact(
        intervention=intervention,
        biomarker=biomarker,
        change=change,
        trend_analysis=trend_analysis,
        seasonality_control=seasonality,
        verdict=verdict,
        confidence_score=confidence,
        interpretation=interpretation,
        caveats=caveats,
        projected_90_day_value=projected_value,
        projected_90_day_ci=projected_ci
    )


def _empty_impact(intervention: Intervention, biomarker: str, reason: str) -> InterventionImpact:
    """Create an empty impact result for missing/insufficient data."""
    empty_change = BiomarkerChange(
        biomarker=biomarker,
        before_mean=np.nan, before_std=np.nan, before_median=np.nan, before_n=0,
        after_mean=np.nan, after_std=np.nan, after_median=np.nan, after_n=0,
        absolute_change=np.nan, percent_change=np.nan,
        t_statistic=np.nan, t_pvalue=1.0,
        mann_whitney_statistic=np.nan, mann_whitney_pvalue=1.0,
        cohens_d=0.0, effect_size_interpretation='negligible',
        change_ci_lower=np.nan, change_ci_upper=np.nan, confidence_level=0.95,
        direction='unchanged', is_significant=False, is_meaningful=False
    )

    empty_trend = TrendAnalysis(
        biomarker=biomarker,
        pre_trend_slope=0, pre_trend_pvalue=1.0, pre_trend_significant=False,
        post_trend_slope=0, post_trend_pvalue=1.0, post_trend_significant=False,
        slope_change=0, trend_reversal=False,
        level_jump=0, level_jump_pvalue=1.0, level_jump_significant=False
    )

    return InterventionImpact(
        intervention=intervention,
        biomarker=biomarker,
        change=empty_change,
        trend_analysis=empty_trend,
        seasonality_control=None,
        verdict='inconclusive',
        confidence_score=0,
        interpretation=reason,
        caveats=[reason],
        projected_90_day_value=None,
        projected_90_day_ci=None
    )


def _determine_verdict(
    change: BiomarkerChange,
    trend: TrendAnalysis,
    seasonality: Optional[SeasonalityControl]
) -> tuple[str, float, str, list[str]]:
    """Determine overall verdict with confidence and interpretation."""
    caveats = []
    confidence = 100.0

    # Check for confounds
    if trend.pre_trend_significant:
        caveats.append(f"Pre-existing trend detected (slope={trend.pre_trend_slope:.4f}/day)")
        confidence -= 15

    if seasonality and seasonality.has_seasonal_pattern:
        if not seasonality.robust_to_seasonal:
            caveats.append(f"Seasonal effects may explain {abs(seasonality.seasonal_contribution):.1f} of the change")
            confidence -= 20

    # Small sample penalty
    if change.before_n < 14 or change.after_n < 14:
        caveats.append(f"Limited data (n={change.before_n}/{change.after_n} before/after)")
        confidence -= 10

    # Determine verdict
    if not change.is_significant:
        if abs(change.cohens_d) >= 0.2:
            # Trending but not significant
            if change.absolute_change > 0:
                verdict = 'weak_positive'
                interpretation = f"{change.biomarker} shows a positive trend (+{change.percent_change:.1f}%) but not statistically significant (p={change.t_pvalue:.3f})"
            else:
                verdict = 'weak_negative'
                interpretation = f"{change.biomarker} shows a negative trend ({change.percent_change:.1f}%) but not statistically significant (p={change.t_pvalue:.3f})"
        else:
            verdict = 'no_effect'
            interpretation = f"No detectable change in {change.biomarker} (change: {change.percent_change:+.1f}%, p={change.t_pvalue:.3f})"
    else:
        # Significant
        effect = change.effect_size_interpretation
        robust = len(caveats) == 0 or (seasonality and seasonality.robust_to_seasonal)

        if change.absolute_change > 0:
            if effect in ('medium', 'large') and robust:
                verdict = 'strong_positive'
                interpretation = f"{change.biomarker} significantly increased by {change.percent_change:.1f}% ({effect} effect, p={change.t_pvalue:.3f}). Effect is robust to confound analysis."
            elif effect in ('medium', 'large'):
                verdict = 'moderate_positive'
                interpretation = f"{change.biomarker} increased by {change.percent_change:.1f}% ({effect} effect, p={change.t_pvalue:.3f}), but some confounds detected."
            else:
                verdict = 'weak_positive'
                interpretation = f"{change.biomarker} increased by {change.percent_change:.1f}% (small effect, p={change.t_pvalue:.3f})."
        else:
            if effect in ('medium', 'large') and robust:
                verdict = 'strong_negative'
                interpretation = f"{change.biomarker} significantly decreased by {abs(change.percent_change):.1f}% ({effect} effect, p={change.t_pvalue:.3f}). Effect is robust."
            elif effect in ('medium', 'large'):
                verdict = 'moderate_negative'
                interpretation = f"{change.biomarker} decreased by {abs(change.percent_change):.1f}% ({effect} effect, p={change.t_pvalue:.3f}), but some confounds detected."
            else:
                verdict = 'weak_negative'
                interpretation = f"{change.biomarker} decreased by {abs(change.percent_change):.1f}% (small effect, p={change.t_pvalue:.3f})."

    # Floor confidence
    confidence = max(0, min(100, confidence))

    return verdict, confidence, interpretation, caveats


def generate_intervention_report(
    intervention: Intervention,
    signals: pd.DataFrame,
    biomarkers: Optional[list[str]] = None,
    before_days: int = 30,
    after_days: int = 30,
) -> InterventionReport:
    """Generate a complete intervention impact report.

    Args:
        intervention: The intervention to analyze
        signals: DataFrame with 'time', 'biomarker_slug', 'value' columns
        biomarkers: List of biomarkers to analyze. If None, analyzes all available.
        before_days: Days of data to use before intervention
        after_days: Days of data to use after intervention

    Returns:
        Complete InterventionReport with all impacts and insights
    """
    # Get available biomarkers if not specified
    if biomarkers is None:
        biomarkers = signals['biomarker_slug'].unique().tolist()

    # Analyze each biomarker
    impacts = []
    for bio in biomarkers:
        impact = analyze_intervention_impact(
            intervention, bio, signals, before_days, after_days
        )
        impacts.append(impact)

    # Categorize results using health-aware direction
    # "positive" in verdict = value increased; "negative" = value decreased
    # But health impact depends on the biomarker (lower resting HR is good)
    improved = []
    declined = []
    unchanged = []

    for impact in impacts:
        if impact.verdict in ('no_effect', 'inconclusive'):
            unchanged.append(impact.biomarker)
        else:
            # Check if the change direction is a health improvement
            direction = 'increased' if 'positive' in impact.verdict else 'decreased'
            is_improvement = _is_health_improvement(impact.biomarker, direction)
            is_strong_or_moderate = impact.verdict.startswith(('strong', 'moderate'))

            if is_strong_or_moderate:
                if is_improvement:
                    improved.append(impact.biomarker)
                else:
                    declined.append(impact.biomarker)
            else:
                unchanged.append(impact.biomarker)

    # Determine overall verdict using health-aware counts
    n_improved = len(improved)
    n_declined = len(declined)
    n_strong = len([i for i in impacts if i.verdict.startswith('strong')])
    n_meaningful = len([i for i in impacts if i.change.is_meaningful])

    if n_meaningful == 0:
        overall_verdict = 'no_clear_effect'
    elif n_improved > n_declined * 2 and n_strong > 0:
        overall_verdict = 'highly_effective'
    elif n_improved > n_declined:
        overall_verdict = 'moderately_effective' if n_meaningful > 1 else 'slightly_effective'
    elif n_declined > n_improved * 2:
        overall_verdict = 'harmful'
    elif n_declined > n_improved:
        overall_verdict = 'slightly_harmful'
    else:
        overall_verdict = 'no_clear_effect'

    # Compute overall confidence
    valid_impacts = [i for i in impacts if i.verdict != 'inconclusive']
    overall_confidence = np.mean([i.confidence_score for i in valid_impacts]) if valid_impacts else 0

    # Generate insights
    primary_insight = _generate_primary_insight(intervention, impacts, overall_verdict, after_days)
    secondary_insights = _generate_secondary_insights(impacts)
    recommendations = _generate_recommendations(intervention, impacts, overall_verdict, after_days)

    # Calculate analysis periods
    intervention_date = pd.Timestamp(intervention.start_date)

    return InterventionReport(
        intervention=intervention,
        analysis_date=datetime.now(),
        before_period_start=(intervention_date - pd.Timedelta(days=before_days)).date(),
        before_period_end=(intervention_date - pd.Timedelta(days=1)).date(),
        after_period_start=intervention.start_date,
        after_period_end=(intervention_date + pd.Timedelta(days=after_days)).date(),
        impacts=impacts,
        biomarkers_improved=improved,
        biomarkers_declined=declined,
        biomarkers_unchanged=unchanged,
        overall_verdict=overall_verdict,
        overall_confidence=overall_confidence,
        primary_insight=primary_insight,
        secondary_insights=secondary_insights,
        recommendations=recommendations,
        total_data_points=sum(i.change.before_n + i.change.after_n for i in impacts),
        statistical_power=_estimate_power(impacts),
        multiple_comparison_correction="Reported per-test; interpret with caution for multiple biomarkers"
    )


def _generate_primary_insight(
    intervention: Intervention,
    impacts: list[InterventionImpact],
    verdict: str,
    analysis_days: int
) -> str:
    """Generate the main takeaway insight."""
    meaningful = [i for i in impacts if i.change.is_meaningful]

    if verdict == 'highly_effective':
        # Find the top health-improving impact
        improved_impacts = [
            i for i in meaningful
            if _is_health_improvement(
                i.biomarker,
                'increased' if 'positive' in i.verdict else 'decreased'
            )
        ]
        if improved_impacts:
            top_impact = max(improved_impacts, key=lambda x: abs(x.change.cohens_d))
            change_word = "improved" if 'positive' in top_impact.verdict else "decreased"
            return (
                f"Strong evidence that '{intervention.name}' is working. "
                f"Most notably, {top_impact.biomarker} {change_word} by {abs(top_impact.change.percent_change):.1f}% "
                f"with {top_impact.confidence_score:.0f}% confidence."
            )
        return f"Strong evidence that '{intervention.name}' is working."
    elif verdict == 'moderately_effective':
        return (
            f"'{intervention.name}' shows positive effects. "
            f"{len(meaningful)} biomarker(s) improved significantly."
        )
    elif verdict == 'slightly_effective':
        return (
            f"'{intervention.name}' may be helping, but effects are small. "
            f"Consider continuing for more data."
        )
    elif verdict == 'no_clear_effect':
        return (
            f"No clear effect detected from '{intervention.name}' after "
            f"{analysis_days} days of observation. This could mean: (1) no real effect, "
            f"(2) effect too small to detect, or (3) more time needed."
        )
    elif verdict in ('slightly_harmful', 'harmful'):
        # Count health-negative changes
        harmful_impacts = [
            i for i in impacts
            if i.change.is_meaningful and not _is_health_improvement(
                i.biomarker,
                'increased' if 'positive' in i.verdict else 'decreased'
            )
        ]
        return (
            f"Caution: '{intervention.name}' may be having negative effects. "
            f"{len(harmful_impacts)} biomarker(s) declined. Review the data carefully."
        )
    else:
        return f"Insufficient data to assess '{intervention.name}'."


def _generate_secondary_insights(impacts: list[InterventionImpact]) -> list[str]:
    """Generate supporting insights."""
    insights = []

    # Trend reversals
    reversals = [i for i in impacts if i.trend_analysis.trend_reversal]
    if reversals:
        for r in reversals[:2]:
            insights.append(
                f"Trend reversal in {r.biomarker}: was trending "
                f"{'up' if r.trend_analysis.pre_trend_slope > 0 else 'down'}, "
                f"now trending {'up' if r.trend_analysis.post_trend_slope > 0 else 'down'}."
            )

    # Level jumps
    jumps = [i for i in impacts if i.trend_analysis.level_jump_significant]
    if jumps:
        for j in jumps[:2]:
            insights.append(
                f"Immediate effect on {j.biomarker}: {j.trend_analysis.level_jump:+.2f} "
                f"at intervention start."
            )

    # Seasonal concerns
    seasonal_concerns = [
        i for i in impacts
        if i.seasonality_control and not i.seasonality_control.robust_to_seasonal
    ]
    if seasonal_concerns:
        insights.append(
            f"Note: Seasonal effects may explain some changes in "
            f"{', '.join(s.biomarker for s in seasonal_concerns[:2])}."
        )

    return insights[:5]  # Max 5 secondary insights


def _generate_recommendations(
    intervention: Intervention,
    impacts: list[InterventionImpact],
    verdict: str,
    analysis_days: int
) -> list[str]:
    """Generate actionable recommendations."""
    recs = []

    if verdict in ('highly_effective', 'moderately_effective'):
        recs.append(f"Continue '{intervention.name}' - data supports its effectiveness.")

        # Suggest optimization
        weak_areas = [i for i in impacts if i.verdict == 'no_effect' and i.change.before_n > 10]
        if weak_areas:
            recs.append(
                f"Consider: {intervention.name} isn't affecting {weak_areas[0].biomarker}. "
                f"A complementary intervention might help."
            )

    elif verdict == 'no_clear_effect':
        if analysis_days < 21:
            recs.append(
                f"Consider continuing for at least 3 weeks total. "
                f"Current observation period ({analysis_days} days) may be too short."
            )
        else:
            recs.append(
                f"After {analysis_days} days with no clear effect, consider: "
                f"(1) modifying the approach, (2) trying something different, or "
                f"(3) accepting this may not work for you."
            )

    elif verdict in ('slightly_harmful', 'harmful'):
        recs.append(
            f"Consider stopping or modifying '{intervention.name}'. "
            f"Consult a professional if health concerns."
        )

    # Data quality recommendations
    low_data = [i for i in impacts if i.change.before_n < 14 or i.change.after_n < 14]
    if len(low_data) > len(impacts) // 2:
        recs.append(
            "More data would increase confidence. Ensure consistent tracking."
        )

    return recs[:4]  # Max 4 recommendations


def _estimate_power(impacts: list[InterventionImpact]) -> float:
    """Estimate statistical power to detect effects."""
    # Simple heuristic based on sample sizes
    n_values = [(i.change.before_n + i.change.after_n) / 2 for i in impacts if i.change.before_n > 0]

    if not n_values:
        return 0.0

    avg_n = np.mean(n_values)

    # Power approximation (very rough)
    # n=30 per group gives ~80% power for medium effect
    if avg_n >= 30:
        return 0.80
    elif avg_n >= 20:
        return 0.65
    elif avg_n >= 10:
        return 0.45
    else:
        return 0.25
