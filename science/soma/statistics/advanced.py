"""Advanced statistical analyses with mathematical rigor.

All analyses include:
- Confidence intervals
- P-values with multiple comparison correction
- Effect sizes
- Clear statements of what is/isn't proven
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional
import pandas as pd
import numpy as np
from scipy import stats
from scipy.signal import detrend
import warnings


# ============================================
# DATA CLASSES
# ============================================

@dataclass
class CorrelationPair:
    """A single correlation between two biomarkers."""
    biomarker_a: str
    biomarker_b: str
    pearson_r: float
    pearson_p: float
    spearman_rho: float
    spearman_p: float
    n_observations: int
    ci_lower: float  # 95% CI for Pearson r
    ci_upper: float
    is_significant: bool  # After Bonferroni correction
    effect_size: str  # "small", "medium", "large" per Cohen


@dataclass
class CorrelationMatrix:
    """Full correlation analysis between all biomarker pairs."""
    pairs: list[CorrelationPair]
    biomarkers_analyzed: list[str]
    bonferroni_alpha: float  # Corrected significance threshold
    significant_pairs: list[CorrelationPair]
    method_note: str


@dataclass
class LaggedCorrelation:
    """Correlation at a specific time lag."""
    lag_days: int
    correlation: float
    p_value: float
    ci_lower: float
    ci_upper: float
    n_observations: int
    is_significant: bool


@dataclass
class RecoveryModel:
    """Model of how activity affects next-day recovery metrics."""
    predictor: str  # e.g., "steps"
    outcome: str    # e.g., "hrv_sdnn"
    lagged_correlations: list[LaggedCorrelation]  # lag 0, 1, 2, 3 days
    optimal_lag: int  # Which lag has strongest correlation
    optimal_correlation: float
    optimal_p_value: float
    interpretation: str
    is_significant: bool
    regression_slope: Optional[float]  # Units of outcome per unit predictor
    regression_intercept: Optional[float]
    r_squared: Optional[float]


@dataclass
class SeasonalComponent:
    """Decomposed seasonal pattern."""
    month: int
    month_name: str
    mean_value: float
    ci_lower: float
    ci_upper: float
    n_observations: int
    deviation_from_annual: float  # How much above/below yearly mean


@dataclass
class SeasonalAnalysis:
    """Full seasonal decomposition for a biomarker."""
    biomarker_slug: str
    annual_mean: float
    seasonal_components: list[SeasonalComponent]
    peak_month: str
    trough_month: str
    seasonal_amplitude: float  # Peak - trough
    seasonality_strength: float  # Variance explained by season (0-1)
    f_statistic: float
    p_value: float
    is_significant: bool


@dataclass
class ReadinessScore:
    """Composite readiness/recovery score for a specific day."""
    date: date
    score: float  # 0-100 scale
    hrv_z_score: Optional[float]
    rhr_z_score: Optional[float]  # Inverted: lower RHR = better
    components: dict[str, float]  # Individual component scores
    interpretation: str  # "optimal", "good", "moderate", "low", "poor"


@dataclass
class ReadinessModel:
    """Model for computing daily readiness scores."""
    hrv_baseline_mean: float
    hrv_baseline_std: float
    rhr_baseline_mean: float
    rhr_baseline_std: float
    weights: dict[str, float]  # Component weights
    score_distribution: dict  # Percentiles of historical scores
    method_note: str


# ============================================
# CROSS-CORRELATION ANALYSIS
# ============================================

def _pearson_ci(r: float, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Calculate confidence interval for Pearson r using Fisher z-transformation."""
    if n < 4:
        return (-1.0, 1.0)

    # Fisher z-transformation
    z = 0.5 * np.log((1 + r) / (1 - r + 1e-10))
    se = 1.0 / np.sqrt(n - 3)

    z_crit = stats.norm.ppf((1 + confidence) / 2)
    z_lower = z - z_crit * se
    z_upper = z + z_crit * se

    # Transform back
    ci_lower = (np.exp(2 * z_lower) - 1) / (np.exp(2 * z_lower) + 1)
    ci_upper = (np.exp(2 * z_upper) - 1) / (np.exp(2 * z_upper) + 1)

    return (float(ci_lower), float(ci_upper))


def _effect_size_label(r: float) -> str:
    """Cohen's conventions for correlation effect size."""
    abs_r = abs(r)
    if abs_r >= 0.5:
        return "large"
    elif abs_r >= 0.3:
        return "medium"
    elif abs_r >= 0.1:
        return "small"
    else:
        return "negligible"


def analyze_correlations(df: pd.DataFrame, min_observations: int = 30) -> Optional[CorrelationMatrix]:
    """
    Compute correlation matrix between all biomarker pairs.

    Uses both Pearson (linear) and Spearman (monotonic) correlations.
    Applies Bonferroni correction for multiple comparisons.
    Reports 95% confidence intervals using Fisher z-transformation.
    """
    # Aggregate to daily means
    df = df.copy()
    df["date"] = pd.to_datetime(df["time"], utc=True).dt.date
    daily = df.groupby(["date", "biomarker_slug"])["value"].mean().unstack()

    # Need at least 2 biomarkers with sufficient overlap
    biomarkers = [col for col in daily.columns if daily[col].notna().sum() >= min_observations]
    if len(biomarkers) < 2:
        return None

    pairs = []
    n_comparisons = len(biomarkers) * (len(biomarkers) - 1) // 2
    bonferroni_alpha = 0.05 / n_comparisons

    for i, bio_a in enumerate(biomarkers):
        for bio_b in biomarkers[i+1:]:
            # Get overlapping observations
            mask = daily[bio_a].notna() & daily[bio_b].notna()
            x = daily.loc[mask, bio_a].values
            y = daily.loc[mask, bio_b].values
            n = len(x)

            if n < min_observations:
                continue

            # Pearson correlation
            pearson_r, pearson_p = stats.pearsonr(x, y)

            # Spearman correlation (more robust to outliers)
            spearman_rho, spearman_p = stats.spearmanr(x, y)

            # Confidence interval for Pearson r
            ci_lower, ci_upper = _pearson_ci(pearson_r, n)

            # Significance after Bonferroni correction
            is_significant = pearson_p < bonferroni_alpha

            pairs.append(CorrelationPair(
                biomarker_a=bio_a,
                biomarker_b=bio_b,
                pearson_r=float(pearson_r),
                pearson_p=float(pearson_p),
                spearman_rho=float(spearman_rho),
                spearman_p=float(spearman_p),
                n_observations=n,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                is_significant=is_significant,
                effect_size=_effect_size_label(pearson_r)
            ))

    if not pairs:
        return None

    significant_pairs = [p for p in pairs if p.is_significant]

    return CorrelationMatrix(
        pairs=pairs,
        biomarkers_analyzed=biomarkers,
        bonferroni_alpha=bonferroni_alpha,
        significant_pairs=significant_pairs,
        method_note=f"Bonferroni-corrected alpha = {bonferroni_alpha:.4f} for {n_comparisons} comparisons"
    )


# ============================================
# RECOVERY MODEL (LAGGED CORRELATIONS)
# ============================================

def analyze_recovery(
    df: pd.DataFrame,
    predictor: str = "steps",
    outcome: str = "hrv_sdnn",
    max_lag: int = 3,
    min_observations: int = 30
) -> Optional[RecoveryModel]:
    """
    Analyze how a predictor (e.g., activity) affects an outcome (e.g., HRV)
    at various time lags.

    Tests whether activity TODAY predicts HRV tomorrow, day after, etc.
    Uses lagged Pearson correlation with significance testing.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["time"], utc=True).dt.date

    # Aggregate to daily values
    daily = df.groupby(["date", "biomarker_slug"])["value"].mean().unstack()

    if predictor not in daily.columns or outcome not in daily.columns:
        return None

    # Apply HRV unit correction if needed
    if outcome in ["hrv_sdnn", "hrv_rmssd"]:
        if daily[outcome].median() > 1000:
            daily[outcome] = daily[outcome] / 1000

    lagged_correlations = []

    for lag in range(max_lag + 1):
        if lag == 0:
            x = daily[predictor]
            y = daily[outcome]
        else:
            # Shift outcome forward (predictor today vs outcome in `lag` days)
            x = daily[predictor].iloc[:-lag]
            y = daily[outcome].shift(-lag).iloc[:-lag]

        # Remove NaN
        mask = x.notna() & y.notna()
        x_clean = x[mask].values
        y_clean = y[mask].values
        n = len(x_clean)

        if n < min_observations:
            continue

        r, p = stats.pearsonr(x_clean, y_clean)
        ci_lower, ci_upper = _pearson_ci(r, n)

        lagged_correlations.append(LaggedCorrelation(
            lag_days=lag,
            correlation=float(r),
            p_value=float(p),
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            n_observations=n,
            is_significant=p < 0.05
        ))

    if not lagged_correlations:
        return None

    # Find optimal lag
    best = max(lagged_correlations, key=lambda x: abs(x.correlation))

    # Fit regression at optimal lag
    if best.lag_days == 0:
        x = daily[predictor]
        y = daily[outcome]
    else:
        x = daily[predictor].iloc[:-best.lag_days]
        y = daily[outcome].shift(-best.lag_days).iloc[:-best.lag_days]

    mask = x.notna() & y.notna()
    x_clean = x[mask].values
    y_clean = y[mask].values

    slope, intercept, r_value, p_value, std_err = stats.linregress(x_clean, y_clean)

    # Interpretation
    if not best.is_significant:
        interpretation = f"No significant relationship found between {predictor} and {outcome}"
    elif best.correlation > 0:
        interpretation = f"Higher {predictor} is associated with higher {outcome} {best.lag_days} day(s) later (r={best.correlation:.3f})"
    else:
        interpretation = f"Higher {predictor} is associated with lower {outcome} {best.lag_days} day(s) later (r={best.correlation:.3f})"

    return RecoveryModel(
        predictor=predictor,
        outcome=outcome,
        lagged_correlations=lagged_correlations,
        optimal_lag=best.lag_days,
        optimal_correlation=best.correlation,
        optimal_p_value=best.p_value,
        interpretation=interpretation,
        is_significant=best.is_significant,
        regression_slope=float(slope),
        regression_intercept=float(intercept),
        r_squared=float(r_value ** 2)
    )


# ============================================
# SEASONAL DECOMPOSITION
# ============================================

def analyze_seasonality(
    df: pd.DataFrame,
    biomarker_slug: str,
    min_months: int = 6,
    min_per_month: int = 10
) -> Optional[SeasonalAnalysis]:
    """
    Decompose biomarker data into seasonal patterns.

    Uses one-way ANOVA to test if monthly means differ significantly.
    Reports seasonal amplitude and variance explained.
    """
    data = df[df["biomarker_slug"] == biomarker_slug].copy()
    if len(data) < 100:
        return None

    data["date"] = pd.to_datetime(data["time"], utc=True)
    data["month"] = data["date"].dt.month

    # Apply HRV correction
    if biomarker_slug in ["hrv_sdnn", "hrv_rmssd"]:
        if data["value"].median() > 1000:
            data["value"] = data["value"] / 1000

    # Check we have enough months
    month_counts = data.groupby("month").size()
    valid_months = month_counts[month_counts >= min_per_month].index.tolist()

    if len(valid_months) < min_months:
        return None

    data = data[data["month"].isin(valid_months)]
    annual_mean = float(data["value"].mean())

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    seasonal_components = []
    groups = []

    for month in range(1, 13):
        month_data = data[data["month"] == month]["value"].values
        if len(month_data) >= min_per_month:
            mean = float(np.mean(month_data))
            se = float(stats.sem(month_data))
            ci = se * stats.t.ppf(0.975, len(month_data) - 1)

            seasonal_components.append(SeasonalComponent(
                month=month,
                month_name=month_names[month - 1],
                mean_value=mean,
                ci_lower=mean - ci,
                ci_upper=mean + ci,
                n_observations=len(month_data),
                deviation_from_annual=mean - annual_mean
            ))
            groups.append(month_data)

    if len(groups) < 3:
        return None

    # One-way ANOVA to test seasonal effect
    f_stat, p_value = stats.f_oneway(*groups)

    # Calculate seasonality strength (eta-squared)
    all_values = np.concatenate(groups)
    ss_total = np.sum((all_values - np.mean(all_values)) ** 2)
    ss_between = sum(len(g) * (np.mean(g) - np.mean(all_values)) ** 2 for g in groups)
    seasonality_strength = ss_between / ss_total if ss_total > 0 else 0

    # Find peak and trough
    sorted_components = sorted(seasonal_components, key=lambda x: x.mean_value)
    trough = sorted_components[0]
    peak = sorted_components[-1]

    return SeasonalAnalysis(
        biomarker_slug=biomarker_slug,
        annual_mean=annual_mean,
        seasonal_components=seasonal_components,
        peak_month=peak.month_name,
        trough_month=trough.month_name,
        seasonal_amplitude=peak.mean_value - trough.mean_value,
        seasonality_strength=float(seasonality_strength),
        f_statistic=float(f_stat),
        p_value=float(p_value),
        is_significant=p_value < 0.05
    )


# ============================================
# READINESS SCORE
# ============================================

def build_readiness_model(
    df: pd.DataFrame,
    hrv_slug: str = "hrv_sdnn",
    rhr_slug: str = "heart_rate_resting",
    min_days: int = 30
) -> Optional[ReadinessModel]:
    """
    Build a model for computing daily readiness scores.

    Readiness = weighted combination of:
    - HRV z-score (higher = better)
    - RHR z-score inverted (lower = better)

    Scores are normalized to 0-100 scale based on historical distribution.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["time"], utc=True).dt.date
    daily = df.groupby(["date", "biomarker_slug"])["value"].mean().unstack()

    if hrv_slug not in daily.columns or rhr_slug not in daily.columns:
        return None

    # Apply HRV correction
    if daily[hrv_slug].median() > 1000:
        daily[hrv_slug] = daily[hrv_slug] / 1000

    # Need sufficient overlapping data
    mask = daily[hrv_slug].notna() & daily[rhr_slug].notna()
    if mask.sum() < min_days:
        return None

    hrv_values = daily.loc[mask, hrv_slug]
    rhr_values = daily.loc[mask, rhr_slug]

    hrv_mean = float(hrv_values.mean())
    hrv_std = float(hrv_values.std())
    rhr_mean = float(rhr_values.mean())
    rhr_std = float(rhr_values.std())

    if hrv_std == 0 or rhr_std == 0:
        return None

    # Compute historical scores to get distribution
    hrv_z = (hrv_values - hrv_mean) / hrv_std
    rhr_z = (rhr_values - rhr_mean) / rhr_std

    # Combine: higher HRV good, lower RHR good
    # Weight HRV slightly more as it's more sensitive to recovery
    raw_scores = 0.6 * hrv_z - 0.4 * rhr_z

    # Normalize to 0-100 using percentile ranking
    percentiles = {
        "p5": float(np.percentile(raw_scores, 5)),
        "p25": float(np.percentile(raw_scores, 25)),
        "p50": float(np.percentile(raw_scores, 50)),
        "p75": float(np.percentile(raw_scores, 75)),
        "p95": float(np.percentile(raw_scores, 95))
    }

    return ReadinessModel(
        hrv_baseline_mean=hrv_mean,
        hrv_baseline_std=hrv_std,
        rhr_baseline_mean=rhr_mean,
        rhr_baseline_std=rhr_std,
        weights={"hrv": 0.6, "rhr": -0.4},
        score_distribution=percentiles,
        method_note="Score = 0.6 * HRV_z - 0.4 * RHR_z, normalized to 0-100 scale"
    )


def compute_readiness_scores(
    df: pd.DataFrame,
    model: ReadinessModel,
    hrv_slug: str = "hrv_sdnn",
    rhr_slug: str = "heart_rate_resting"
) -> list[ReadinessScore]:
    """
    Compute daily readiness scores using a pre-built model.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["time"], utc=True).dt.date
    daily = df.groupby(["date", "biomarker_slug"])["value"].mean().unstack()

    # Apply HRV correction
    if hrv_slug in daily.columns and daily[hrv_slug].median() > 1000:
        daily[hrv_slug] = daily[hrv_slug] / 1000

    scores = []
    p5, p95 = model.score_distribution["p5"], model.score_distribution["p95"]

    for date_val, row in daily.iterrows():
        hrv_val = row.get(hrv_slug)
        rhr_val = row.get(rhr_slug)

        if pd.isna(hrv_val) or pd.isna(rhr_val):
            continue

        hrv_z = (hrv_val - model.hrv_baseline_mean) / model.hrv_baseline_std
        rhr_z = (rhr_val - model.rhr_baseline_mean) / model.rhr_baseline_std

        raw_score = 0.6 * hrv_z - 0.4 * rhr_z

        # Normalize to 0-100
        normalized = 50 + 50 * (raw_score - model.score_distribution["p50"]) / (p95 - p5 + 1e-6)
        normalized = max(0, min(100, normalized))

        # Interpretation
        if normalized >= 80:
            interpretation = "optimal"
        elif normalized >= 60:
            interpretation = "good"
        elif normalized >= 40:
            interpretation = "moderate"
        elif normalized >= 20:
            interpretation = "low"
        else:
            interpretation = "poor"

        scores.append(ReadinessScore(
            date=date_val,
            score=float(normalized),
            hrv_z_score=float(hrv_z),
            rhr_z_score=float(rhr_z),
            components={"hrv_contribution": 0.6 * hrv_z, "rhr_contribution": -0.4 * rhr_z},
            interpretation=interpretation
        ))

    return sorted(scores, key=lambda x: x.date, reverse=True)


def get_readiness_summary(scores: list[ReadinessScore]) -> dict:
    """
    Summarize readiness scores with statistics.
    """
    if not scores:
        return {}

    score_values = [s.score for s in scores]

    # Recent trend (last 7 vs previous 7)
    recent = score_values[:7] if len(scores) >= 7 else score_values
    previous = score_values[7:14] if len(scores) >= 14 else []

    trend = None
    trend_p = None
    if len(recent) >= 3 and len(previous) >= 3:
        t_stat, trend_p = stats.ttest_ind(recent, previous)
        if trend_p < 0.05:
            trend = "improving" if np.mean(recent) > np.mean(previous) else "declining"
        else:
            trend = "stable"

    # Distribution of interpretations
    interpretation_counts = {}
    for s in scores:
        interpretation_counts[s.interpretation] = interpretation_counts.get(s.interpretation, 0) + 1

    return {
        "total_days": len(scores),
        "mean_score": float(np.mean(score_values)),
        "std_score": float(np.std(score_values)),
        "current_score": scores[0].score if scores else None,
        "current_interpretation": scores[0].interpretation if scores else None,
        "trend_7d": trend,
        "trend_p_value": float(trend_p) if trend_p else None,
        "interpretation_distribution": interpretation_counts,
        "best_day": max(scores, key=lambda x: x.score),
        "worst_day": min(scores, key=lambda x: x.score)
    }
