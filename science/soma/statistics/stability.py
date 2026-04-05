"""Statistical stability analysis - track how reliable your findings are over time."""

from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np
from scipy import stats


@dataclass
class ConvergencePoint:
    """Estimate at a specific sample size."""

    n: int
    mean: float
    ci_width: float
    ci_pct: float  # CI width as % of mean
    status: str  # "stable", "converging", "unstable"


@dataclass
class ConvergenceAnalysis:
    """How estimates stabilize with increasing sample size."""

    biomarker_slug: str
    current_n: int
    current_mean: float
    current_ci_width: float
    convergence_points: list[ConvergencePoint]
    min_n_for_stability: int  # Samples needed for CI < 2% of mean
    is_stable: bool
    drift_from_initial: float  # % change from first to final estimate


@dataclass
class TemporalStability:
    """Stability of a metric across different time periods."""

    biomarker_slug: str
    metric: str  # e.g., "mean", "correlation"
    periods: list[dict]  # year/period -> value
    mean_value: float
    std_across_periods: float
    is_stable: bool  # std < threshold
    consistency_pct: float  # % of periods with similar values


@dataclass
class DriftResult:
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


@dataclass
class SampleAdequacy:
    """Whether you have enough data for reliable inference."""

    biomarker_slug: str
    current_n: int
    required_n_5pct: int  # For 5% precision
    required_n_2pct: int  # For 2% precision
    is_adequate: bool
    adequacy_ratio: float  # current_n / required_n


@dataclass
class StabilityReport:
    """Complete stability assessment."""

    convergence: list[ConvergenceAnalysis]
    temporal_stability: list[TemporalStability]
    drift: list[DriftResult]
    sample_adequacy: list[SampleAdequacy]
    overall_assessment: str
    recommendations: list[str]


def _compute_ci_width(values: np.ndarray, confidence: float = 0.95) -> float:
    """Compute confidence interval width."""
    if len(values) < 2:
        return float("inf")
    se = stats.sem(values)
    ci = 2 * se * stats.t.ppf((1 + confidence) / 2, len(values) - 1)
    return float(ci)


def analyze_convergence(
    df: pd.DataFrame, biomarker_slug: str, checkpoints: list[int] = None
) -> Optional[ConvergenceAnalysis]:
    """
    Analyze how estimates converge with increasing sample size.

    Shuffles data and tracks running estimates at various sample sizes
    to show how quickly the estimate stabilizes.
    """
    values = df[df["biomarker_slug"] == biomarker_slug]["value"].dropna().values

    if len(values) < 100:
        return None

    if checkpoints is None:
        checkpoints = [50, 100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]

    checkpoints = [c for c in checkpoints if c <= len(values)]

    # Shuffle for random accumulation simulation
    np.random.seed(42)
    shuffled = values.copy()
    np.random.shuffle(shuffled)

    points = []
    min_n_stable = len(values)  # Default to max

    for n in checkpoints:
        sample = shuffled[:n]
        mean = float(np.mean(sample))
        ci_width = _compute_ci_width(sample)
        ci_pct = (ci_width / mean * 100) if mean != 0 else float("inf")

        if ci_pct < 2:
            status = "stable"
            if n < min_n_stable:
                min_n_stable = n
        elif ci_pct < 5:
            status = "converging"
        else:
            status = "unstable"

        points.append(
            ConvergencePoint(
                n=n, mean=mean, ci_width=ci_width, ci_pct=ci_pct, status=status
            )
        )

    current_mean = float(np.mean(values))
    current_ci = _compute_ci_width(values)

    drift = (
        abs(points[-1].mean - points[0].mean) / points[-1].mean * 100 if points else 0
    )

    return ConvergenceAnalysis(
        biomarker_slug=biomarker_slug,
        current_n=len(values),
        current_mean=current_mean,
        current_ci_width=current_ci,
        convergence_points=points,
        min_n_for_stability=min_n_stable,
        is_stable=current_ci / current_mean * 100 < 2 if current_mean != 0 else False,
        drift_from_initial=drift,
    )


def analyze_temporal_stability(
    df: pd.DataFrame, biomarker_slug: str, min_per_period: int = 30
) -> Optional[TemporalStability]:
    """
    Analyze if a biomarker's mean is stable across years.
    """
    data = df[df["biomarker_slug"] == biomarker_slug].copy()
    if len(data) < 100:
        return None

    data["year"] = pd.to_datetime(data["time"], utc=True).dt.year

    periods = []
    for year in sorted(data["year"].unique()):
        year_vals = data[data["year"] == year]["value"].dropna()
        if len(year_vals) >= min_per_period:
            periods.append(
                {
                    "period": int(year),
                    "mean": float(year_vals.mean()),
                    "std": float(year_vals.std()),
                    "n": len(year_vals),
                }
            )

    if len(periods) < 2:
        return None

    means = [p["mean"] for p in periods]
    overall_mean = np.mean(means)
    std_across = np.std(means)

    # Consistency: % of periods within 10% of overall mean
    consistent = sum(1 for m in means if abs(m - overall_mean) / overall_mean < 0.1)
    consistency_pct = consistent / len(periods) * 100

    return TemporalStability(
        biomarker_slug=biomarker_slug,
        metric="mean",
        periods=periods,
        mean_value=float(overall_mean),
        std_across_periods=float(std_across),
        is_stable=std_across / overall_mean < 0.1 if overall_mean != 0 else False,
        consistency_pct=consistency_pct,
    )


def analyze_drift(
    df: pd.DataFrame, biomarker_slug: str, recent_days: int = 365
) -> Optional[DriftResult]:
    """
    Compare recent data to historical data to detect drift.
    """
    data = df[df["biomarker_slug"] == biomarker_slug].copy()
    if len(data) < 100:
        return None

    data["time"] = pd.to_datetime(data["time"], utc=True)
    cutoff = data["time"].max() - pd.Timedelta(days=recent_days)

    recent = data[data["time"] >= cutoff]["value"].dropna()
    historical = data[data["time"] < cutoff]["value"].dropna()

    if len(recent) < 20 or len(historical) < 20:
        return None

    recent_mean = float(recent.mean())
    hist_mean = float(historical.mean())

    change = recent_mean - hist_mean
    pct_change = (change / hist_mean * 100) if hist_mean != 0 else 0

    t_stat, p_val = stats.ttest_ind(recent, historical)

    is_sig = p_val < 0.05
    if is_sig:
        direction = "increasing" if change > 0 else "decreasing"
    else:
        direction = "stable"

    return DriftResult(
        biomarker_slug=biomarker_slug,
        recent_mean=recent_mean,
        recent_n=len(recent),
        historical_mean=hist_mean,
        historical_n=len(historical),
        absolute_change=change,
        pct_change=pct_change,
        t_statistic=float(t_stat),
        p_value=float(p_val),
        is_significant=is_sig,
        direction=direction,
    )


def analyze_sample_adequacy(
    df: pd.DataFrame, biomarker_slug: str
) -> Optional[SampleAdequacy]:
    """
    Determine if sample size is adequate for reliable inference.
    """
    values = df[df["biomarker_slug"] == biomarker_slug]["value"].dropna().values

    if len(values) < 30:
        return None

    mean = np.mean(values)
    std = np.std(values)

    if mean == 0:
        return None

    # Required n for target CI precision
    # CI width = 2 * 1.96 * std / sqrt(n)
    # target = CI width / mean
    # n = (2 * 1.96 * std / (target * mean))^2

    def required_n(target_pct):
        target = target_pct / 100
        return int(np.ceil((2 * 1.96 * std / (target * mean)) ** 2))

    req_5pct = required_n(5)
    req_2pct = required_n(2)

    return SampleAdequacy(
        biomarker_slug=biomarker_slug,
        current_n=len(values),
        required_n_5pct=req_5pct,
        required_n_2pct=req_2pct,
        is_adequate=len(values) >= req_5pct,
        adequacy_ratio=len(values) / req_5pct if req_5pct > 0 else float("inf"),
    )


def generate_stability_report(df: pd.DataFrame) -> StabilityReport:
    """
    Generate a complete stability report for all biomarkers.
    """
    biomarkers = df["biomarker_slug"].unique()

    convergence = []
    temporal = []
    drift = []
    adequacy = []

    for slug in biomarkers:
        conv = analyze_convergence(df, slug)
        if conv:
            convergence.append(conv)

        temp = analyze_temporal_stability(df, slug)
        if temp:
            temporal.append(temp)

        dr = analyze_drift(df, slug)
        if dr:
            drift.append(dr)

        adq = analyze_sample_adequacy(df, slug)
        if adq:
            adequacy.append(adq)

    # Generate recommendations
    recommendations = []

    inadequate = [a for a in adequacy if not a.is_adequate]
    if inadequate:
        for a in inadequate:
            recommendations.append(
                f"Collect more {a.biomarker_slug} data ({a.current_n} < {a.required_n_5pct} required)"
            )

    drifting = [d for d in drift if d.is_significant]
    for d in drifting:
        recommendations.append(
            f"{d.biomarker_slug} is {d.direction} ({d.pct_change:+.1f}% vs historical) - update baseline"
        )

    unstable_temporal = [t for t in temporal if not t.is_stable]
    for t in unstable_temporal:
        recommendations.append(
            f"{t.biomarker_slug} varies significantly across years (std={t.std_across_periods:.2f})"
        )

    # Overall assessment
    all_adequate = all(a.is_adequate for a in adequacy)
    any_drift = any(d.is_significant for d in drift)
    mostly_stable = (
        sum(1 for t in temporal if t.is_stable) / len(temporal) > 0.7
        if temporal
        else True
    )

    if all_adequate and not any_drift and mostly_stable:
        assessment = "EXCELLENT: Data is sufficient, stable, and consistent"
    elif all_adequate and mostly_stable:
        assessment = "GOOD: Data is sufficient and mostly stable, some drift detected"
    elif all_adequate:
        assessment = "ADEQUATE: Sufficient data but patterns vary over time"
    else:
        assessment = "NEEDS MORE DATA: Some biomarkers lack sufficient samples"

    return StabilityReport(
        convergence=convergence,
        temporal_stability=temporal,
        drift=drift,
        sample_adequacy=adequacy,
        overall_assessment=assessment,
        recommendations=recommendations,
    )
