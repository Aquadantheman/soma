"""Sleep Architecture Analysis.

Computes sleep structure metrics from individual sleep stage records:
- Nightly totals (REM, Deep, Core, In Bed)
- Sleep architecture percentages (REM%, Deep%, Core%)
- Sleep efficiency (time asleep / time in bed)
- Sleep latency estimation
- Personal baselines with confidence intervals

Clinical Context:
- Normal REM%: 20-25% of total sleep
- Normal Deep%: 13-23% (decreases with age)
- Normal Efficiency: >85%
- Changes in architecture correlate with depression, anxiety, cognitive function

All analyses use YOUR personal distribution, not population norms.
"""

from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Optional, List
import pandas as pd
import numpy as np
from scipy import stats

# ============================================
# DATA CLASSES
# ============================================


@dataclass
class ConfidenceInterval:
    """Value with confidence interval."""

    mean: float
    ci_lower: float
    ci_upper: float
    n: int
    confidence: float = 0.95


@dataclass
class NightlySleep:
    """Sleep metrics for a single night."""

    date: date
    rem_min: float
    deep_min: float
    core_min: float
    in_bed_min: float
    total_sleep_min: float  # rem + deep + core
    rem_pct: float
    deep_pct: float
    core_pct: float
    efficiency: float  # total_sleep / in_bed (as percentage)
    bed_time: Optional[time] = None
    wake_time: Optional[time] = None


@dataclass
class SleepArchitectureBaseline:
    """Personal baseline for sleep architecture metrics."""

    computed_at: pd.Timestamp
    n_nights: int

    # Duration baselines (minutes)
    total_sleep: ConfidenceInterval
    rem_duration: ConfidenceInterval
    deep_duration: ConfidenceInterval
    core_duration: ConfidenceInterval
    in_bed_duration: ConfidenceInterval

    # Percentage baselines
    rem_pct: ConfidenceInterval
    deep_pct: ConfidenceInterval
    core_pct: ConfidenceInterval
    efficiency: ConfidenceInterval

    # Stability metrics
    is_stable: bool
    consistency_score: float  # 0-100, how consistent is sleep architecture


@dataclass
class SleepArchitectureDeviation:
    """How a night's sleep deviates from personal baseline."""

    date: date

    # Z-scores from personal baseline
    total_sleep_z: float
    rem_pct_z: float
    deep_pct_z: float
    efficiency_z: float

    # Notable deviations
    is_rem_low: bool  # REM < personal p10
    is_deep_low: bool
    is_efficiency_low: bool
    is_notable: bool  # Any significant deviation

    interpretation: str


@dataclass
class SleepArchitectureTrend:
    """Trend analysis for sleep architecture over time."""

    metric: str  # 'rem_pct', 'deep_pct', 'efficiency', etc.
    period_days: int

    slope: float  # Change per day
    slope_pct: float  # Percent change over period
    p_value: float
    r_squared: float

    is_significant: bool
    direction: Optional[str]  # 'improving', 'declining', 'stable'
    interpretation: str


@dataclass
class SleepArchitectureReport:
    """Complete sleep architecture analysis."""

    baseline: Optional[SleepArchitectureBaseline]
    recent_nights: List[NightlySleep]
    current_deviation: Optional[SleepArchitectureDeviation]

    trends: List[SleepArchitectureTrend]

    # Flags for clinical relevance
    concerns: List[str]
    insights: List[str]

    # Summary statistics
    avg_rem_pct_30d: Optional[float]
    avg_deep_pct_30d: Optional[float]
    avg_efficiency_30d: Optional[float]


# ============================================
# HELPER FUNCTIONS
# ============================================


def _confidence_interval(
    data: np.ndarray, confidence: float = 0.95
) -> Optional[ConfidenceInterval]:
    """Calculate confidence interval for the mean."""
    n = len(data)
    if n < 2:
        return None
    mean = float(np.mean(data))
    se = float(stats.sem(data))
    ci = se * stats.t.ppf((1 + confidence) / 2, n - 1)
    return ConfidenceInterval(
        mean=mean, ci_lower=mean - ci, ci_upper=mean + ci, n=n, confidence=confidence
    )


def _aggregate_nightly_sleep(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate individual sleep stage records into nightly totals.

    Args:
        df: DataFrame with columns [time, biomarker_slug, value]
            where biomarker_slug in ['sleep_rem', 'sleep_deep', 'sleep_core', 'sleep_in_bed']
            and value is duration in minutes

    Returns:
        DataFrame with one row per night, columns for each stage total
    """
    # Filter to sleep stage records
    sleep_slugs = ["sleep_rem", "sleep_deep", "sleep_core", "sleep_in_bed"]
    sleep_data = df[df["biomarker_slug"].isin(sleep_slugs)].copy()

    if len(sleep_data) == 0:
        return pd.DataFrame()

    sleep_data["time"] = pd.to_datetime(sleep_data["time"], utc=True)

    # Assign sleep records to their "sleep night" date
    # Records between 6pm and 6am belong to the night starting on that date
    # Records between midnight and 6am belong to previous night's date
    sleep_data["hour"] = sleep_data["time"].dt.hour
    sleep_data["sleep_date"] = sleep_data["time"].dt.date

    # Adjust for records after midnight but before 6am -> previous night
    mask = sleep_data["hour"] < 6
    sleep_data.loc[mask, "sleep_date"] = (
        pd.to_datetime(sleep_data.loc[mask, "sleep_date"]) - pd.Timedelta(days=1)
    ).dt.date

    # Pivot to get stage totals per night
    nightly = sleep_data.pivot_table(
        index="sleep_date",
        columns="biomarker_slug",
        values="value",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    # Ensure all columns exist
    for col in sleep_slugs:
        if col not in nightly.columns:
            nightly[col] = 0.0

    # Rename for clarity
    nightly = nightly.rename(
        columns={
            "sleep_rem": "rem_min",
            "sleep_deep": "deep_min",
            "sleep_core": "core_min",
            "sleep_in_bed": "in_bed_min",
        }
    )

    # Compute derived metrics
    nightly["total_sleep_min"] = (
        nightly["rem_min"] + nightly["deep_min"] + nightly["core_min"]
    )

    # Percentages (avoid division by zero)
    nightly["rem_pct"] = np.where(
        nightly["total_sleep_min"] > 0,
        nightly["rem_min"] / nightly["total_sleep_min"] * 100,
        0,
    )
    nightly["deep_pct"] = np.where(
        nightly["total_sleep_min"] > 0,
        nightly["deep_min"] / nightly["total_sleep_min"] * 100,
        0,
    )
    nightly["core_pct"] = np.where(
        nightly["total_sleep_min"] > 0,
        nightly["core_min"] / nightly["total_sleep_min"] * 100,
        0,
    )

    # Efficiency: total sleep / time in bed
    # If in_bed_min is 0 but we have sleep data, use total_sleep as proxy
    nightly["efficiency"] = np.where(
        nightly["in_bed_min"] > 0,
        nightly["total_sleep_min"] / nightly["in_bed_min"] * 100,
        np.where(nightly["total_sleep_min"] > 0, 100.0, 0.0),
    )
    # Cap efficiency at 100%
    nightly["efficiency"] = nightly["efficiency"].clip(0, 100)

    return nightly.sort_values("sleep_date")


# ============================================
# MAIN ANALYSIS FUNCTIONS
# ============================================


def compute_nightly_sleep(df: pd.DataFrame) -> List[NightlySleep]:
    """
    Compute nightly sleep metrics from raw sleep stage records.

    Args:
        df: DataFrame with [time, biomarker_slug, value]

    Returns:
        List of NightlySleep objects, one per night
    """
    nightly = _aggregate_nightly_sleep(df)

    if len(nightly) == 0:
        return []

    results = []
    for _, row in nightly.iterrows():
        results.append(
            NightlySleep(
                date=row["sleep_date"],
                rem_min=float(row["rem_min"]),
                deep_min=float(row["deep_min"]),
                core_min=float(row["core_min"]),
                in_bed_min=float(row["in_bed_min"]),
                total_sleep_min=float(row["total_sleep_min"]),
                rem_pct=float(row["rem_pct"]),
                deep_pct=float(row["deep_pct"]),
                core_pct=float(row["core_pct"]),
                efficiency=float(row["efficiency"]),
            )
        )

    return results


def compute_sleep_baseline(
    df: pd.DataFrame, window_days: int = 90, min_nights: int = 14
) -> Optional[SleepArchitectureBaseline]:
    """
    Compute personal baseline for sleep architecture.

    Args:
        df: DataFrame with sleep stage records
        window_days: Number of days to include in baseline
        min_nights: Minimum nights required

    Returns:
        SleepArchitectureBaseline or None if insufficient data
    """
    nightly = _aggregate_nightly_sleep(df)

    if len(nightly) == 0:
        return None

    # Filter to window
    cutoff = pd.Timestamp.now(tz="UTC").date() - timedelta(days=window_days)
    nightly = nightly[nightly["sleep_date"] >= cutoff]

    # Filter out nights with no meaningful sleep data
    nightly = nightly[nightly["total_sleep_min"] > 60]  # At least 1 hour

    if len(nightly) < min_nights:
        return None

    # Compute baselines for each metric
    total_ci = _confidence_interval(nightly["total_sleep_min"].values)
    rem_dur_ci = _confidence_interval(nightly["rem_min"].values)
    deep_dur_ci = _confidence_interval(nightly["deep_min"].values)
    core_dur_ci = _confidence_interval(nightly["core_min"].values)
    in_bed_ci = _confidence_interval(nightly["in_bed_min"].values)

    rem_pct_ci = _confidence_interval(nightly["rem_pct"].values)
    deep_pct_ci = _confidence_interval(nightly["deep_pct"].values)
    core_pct_ci = _confidence_interval(nightly["core_pct"].values)
    efficiency_ci = _confidence_interval(nightly["efficiency"].values)

    if not all([total_ci, rem_pct_ci, deep_pct_ci, efficiency_ci]):
        return None

    # Consistency score based on coefficient of variation
    cv_total = nightly["total_sleep_min"].std() / nightly["total_sleep_min"].mean()
    cv_rem = nightly["rem_pct"].std() / (nightly["rem_pct"].mean() + 0.01)
    cv_deep = nightly["deep_pct"].std() / (nightly["deep_pct"].mean() + 0.01)

    avg_cv = (cv_total + cv_rem + cv_deep) / 3
    consistency_score = max(0, min(100, 100 * (1 - avg_cv)))

    return SleepArchitectureBaseline(
        computed_at=pd.Timestamp.now(tz="UTC"),
        n_nights=len(nightly),
        total_sleep=total_ci,
        rem_duration=rem_dur_ci,
        deep_duration=deep_dur_ci,
        core_duration=core_dur_ci,
        in_bed_duration=in_bed_ci,
        rem_pct=rem_pct_ci,
        deep_pct=deep_pct_ci,
        core_pct=core_pct_ci,
        efficiency=efficiency_ci,
        is_stable=consistency_score >= 60,
        consistency_score=float(consistency_score),
    )


def compute_sleep_deviation(
    night: NightlySleep, baseline: SleepArchitectureBaseline
) -> SleepArchitectureDeviation:
    """
    Compute how a night's sleep deviates from personal baseline.
    """

    def z_score(value: float, ci: ConfidenceInterval) -> float:
        std = (ci.ci_upper - ci.ci_lower) / (2 * 1.96) * np.sqrt(ci.n)
        return (value - ci.mean) / std if std > 0 else 0.0

    total_z = z_score(night.total_sleep_min, baseline.total_sleep)
    rem_z = z_score(night.rem_pct, baseline.rem_pct)
    deep_z = z_score(night.deep_pct, baseline.deep_pct)
    eff_z = z_score(night.efficiency, baseline.efficiency)

    # Notable if |z| > 1.5
    is_rem_low = rem_z < -1.5
    is_deep_low = deep_z < -1.5
    is_eff_low = eff_z < -1.5
    is_notable = abs(total_z) > 1.5 or is_rem_low or is_deep_low or is_eff_low

    # Generate interpretation
    issues = []
    if is_rem_low:
        issues.append("REM sleep notably below your baseline")
    if is_deep_low:
        issues.append("Deep sleep notably below your baseline")
    if is_eff_low:
        issues.append("Sleep efficiency below your baseline")
    if total_z < -1.5:
        issues.append("Total sleep duration below your baseline")

    if not issues:
        interpretation = "Sleep architecture within your normal range"
    else:
        interpretation = "; ".join(issues)

    return SleepArchitectureDeviation(
        date=night.date,
        total_sleep_z=float(total_z),
        rem_pct_z=float(rem_z),
        deep_pct_z=float(deep_z),
        efficiency_z=float(eff_z),
        is_rem_low=is_rem_low,
        is_deep_low=is_deep_low,
        is_efficiency_low=is_eff_low,
        is_notable=is_notable,
        interpretation=interpretation,
    )


def analyze_sleep_trend(
    df: pd.DataFrame, metric: str = "rem_pct", period_days: int = 30
) -> Optional[SleepArchitectureTrend]:
    """
    Analyze trend in a sleep architecture metric.

    Args:
        df: DataFrame with sleep stage records
        metric: Which metric to analyze ('rem_pct', 'deep_pct', 'efficiency', 'total_sleep_min')
        period_days: Number of days to analyze

    Returns:
        SleepArchitectureTrend or None if insufficient data
    """
    nightly = _aggregate_nightly_sleep(df)

    if len(nightly) == 0 or metric not in nightly.columns:
        return None

    cutoff = pd.Timestamp.now(tz="UTC").date() - timedelta(days=period_days)
    nightly = nightly[nightly["sleep_date"] >= cutoff]
    nightly = nightly[nightly["total_sleep_min"] > 60]

    if len(nightly) < 7:
        return None

    # Linear regression
    x = np.arange(len(nightly))
    y = nightly[metric].values

    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

    is_significant = p_value < 0.05

    # Direction interpretation
    if not is_significant:
        direction = "stable"
        interpretation = (
            f"{metric} has remained stable over the past {period_days} days"
        )
    elif slope > 0:
        direction = (
            "improving"
            if metric in ["rem_pct", "deep_pct", "efficiency"]
            else "increasing"
        )
        interpretation = (
            f"{metric} is {direction} ({slope:.2f} per day, p={p_value:.3f})"
        )
    else:
        direction = (
            "declining"
            if metric in ["rem_pct", "deep_pct", "efficiency"]
            else "decreasing"
        )
        interpretation = (
            f"{metric} is {direction} ({slope:.2f} per day, p={p_value:.3f})"
        )

    # Percentage change over period
    start_val = intercept
    end_val = intercept + slope * len(nightly)
    pct_change = (end_val - start_val) / start_val * 100 if start_val != 0 else 0

    return SleepArchitectureTrend(
        metric=metric,
        period_days=period_days,
        slope=float(slope),
        slope_pct=float(pct_change),
        p_value=float(p_value),
        r_squared=float(r_value**2),
        is_significant=is_significant,
        direction=direction,
        interpretation=interpretation,
    )


def generate_sleep_report(
    df: pd.DataFrame, baseline_days: int = 90, trend_days: int = 30
) -> SleepArchitectureReport:
    """
    Generate a complete sleep architecture analysis report.

    Args:
        df: DataFrame with sleep stage records
        baseline_days: Days for baseline computation
        trend_days: Days for trend analysis

    Returns:
        SleepArchitectureReport with all analyses
    """
    # Compute baseline
    baseline = compute_sleep_baseline(df, window_days=baseline_days)

    # Get recent nights
    nightly = _aggregate_nightly_sleep(df)
    recent_cutoff = pd.Timestamp.now(tz="UTC").date() - timedelta(days=trend_days)

    recent_nights = []
    if len(nightly) > 0:
        recent_data = nightly[nightly["sleep_date"] >= recent_cutoff]
        recent_data = recent_data[recent_data["total_sleep_min"] > 60]

        for _, row in recent_data.iterrows():
            recent_nights.append(
                NightlySleep(
                    date=row["sleep_date"],
                    rem_min=float(row["rem_min"]),
                    deep_min=float(row["deep_min"]),
                    core_min=float(row["core_min"]),
                    in_bed_min=float(row["in_bed_min"]),
                    total_sleep_min=float(row["total_sleep_min"]),
                    rem_pct=float(row["rem_pct"]),
                    deep_pct=float(row["deep_pct"]),
                    core_pct=float(row["core_pct"]),
                    efficiency=float(row["efficiency"]),
                )
            )

    # Current deviation (most recent night)
    current_deviation = None
    if baseline and recent_nights:
        current_deviation = compute_sleep_deviation(recent_nights[-1], baseline)

    # Trends
    trends = []
    for metric in ["rem_pct", "deep_pct", "efficiency", "total_sleep_min"]:
        trend = analyze_sleep_trend(df, metric, trend_days)
        if trend:
            trends.append(trend)

    # Generate concerns and insights
    concerns = []
    insights = []

    if baseline:
        # Check clinical thresholds
        if baseline.rem_pct.mean < 15:
            concerns.append(
                f"Average REM% ({baseline.rem_pct.mean:.1f}%) is below typical range (20-25%)"
            )
        elif baseline.rem_pct.mean >= 20:
            insights.append(f"Healthy REM% ({baseline.rem_pct.mean:.1f}%)")

        if baseline.deep_pct.mean < 10:
            concerns.append(
                f"Average deep sleep ({baseline.deep_pct.mean:.1f}%) is below typical range (13-23%)"
            )
        elif baseline.deep_pct.mean >= 13:
            insights.append(f"Healthy deep sleep ({baseline.deep_pct.mean:.1f}%)")

        if baseline.efficiency.mean < 85:
            concerns.append(
                f"Sleep efficiency ({baseline.efficiency.mean:.1f}%) is below 85% threshold"
            )
        elif baseline.efficiency.mean >= 90:
            insights.append(
                f"Excellent sleep efficiency ({baseline.efficiency.mean:.1f}%)"
            )

        if not baseline.is_stable:
            concerns.append(
                "Sleep patterns are inconsistent (high night-to-night variability)"
            )
        else:
            insights.append(
                f"Consistent sleep patterns (stability score: {baseline.consistency_score:.0f}/100)"
            )

    # Check trends
    for trend in trends:
        if trend.is_significant and trend.direction == "declining":
            concerns.append(trend.interpretation)
        elif trend.is_significant and trend.direction == "improving":
            insights.append(trend.interpretation)

    # Compute 30-day averages
    avg_rem = avg_deep = avg_eff = None
    if recent_nights:
        avg_rem = float(np.mean([n.rem_pct for n in recent_nights]))
        avg_deep = float(np.mean([n.deep_pct for n in recent_nights]))
        avg_eff = float(np.mean([n.efficiency for n in recent_nights]))

    return SleepArchitectureReport(
        baseline=baseline,
        recent_nights=recent_nights,
        current_deviation=current_deviation,
        trends=trends,
        concerns=concerns,
        insights=insights,
        avg_rem_pct_30d=avg_rem,
        avg_deep_pct_30d=avg_deep,
        avg_efficiency_30d=avg_eff,
    )
