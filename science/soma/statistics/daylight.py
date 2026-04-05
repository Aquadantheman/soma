"""Daylight Exposure Analysis.

Analyzes time spent in daylight for circadian rhythm health:
- Daily daylight totals
- Personal baseline with confidence intervals
- Correlation with sleep architecture
- Seasonal patterns

Research Context:
- Morning light exposure (before 10am) most impactful for circadian rhythm
- ~30 min morning light helps regulate sleep-wake cycle
- Daylight exposure correlates with:
  - Earlier sleep onset
  - Better sleep quality
  - Improved mood
  - Reduced depression symptoms

Reference: Blume, C., Garbazza, C., & Spitschan, M. (2019). Effects of light on human
circadian rhythms, sleep and mood. Somnologie, 23(3), 147-156.
"""

from dataclasses import dataclass
from datetime import date, timedelta
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
class DailyDaylight:
    """Daylight metrics for a single day."""

    date: date
    total_min: float  # Total minutes of daylight exposure
    morning_min: float  # Minutes before 10am
    midday_min: float  # Minutes 10am-2pm
    afternoon_min: float  # Minutes after 2pm
    has_morning_exposure: bool  # Got meaningful morning light


@dataclass
class DaylightBaseline:
    """Personal baseline for daylight exposure."""

    computed_at: pd.Timestamp
    n_days: int

    # Duration baselines (minutes)
    total_daylight: ConfidenceInterval
    morning_daylight: ConfidenceInterval
    midday_daylight: ConfidenceInterval
    afternoon_daylight: ConfidenceInterval

    # Derived metrics
    pct_days_with_morning_light: float  # % of days with >= 20 min morning light
    morning_light_mean: float  # Average morning light
    variability_score: float  # Coefficient of variation (lower = more consistent)

    # Health assessment
    is_sufficient: bool  # Meeting minimum recommendations
    consistency_score: float  # 0-100


@dataclass
class DaylightDeviation:
    """How a day's daylight deviates from personal baseline."""

    date: date
    total_z: float
    morning_z: float

    is_low: bool  # Significantly below baseline
    is_no_morning_light: bool  # No meaningful morning exposure
    is_notable: bool

    interpretation: str


@dataclass
class DaylightTrend:
    """Trend analysis for daylight exposure."""

    period_days: int
    slope: float  # Change per day in minutes
    slope_pct: float  # Percent change over period
    p_value: float
    r_squared: float
    is_significant: bool
    direction: str  # 'increasing', 'decreasing', 'stable'
    interpretation: str


@dataclass
class DaylightSleepCorrelation:
    """Correlation between daylight and sleep metrics."""

    sleep_metric: str  # 'sleep_duration', 'rem_pct', 'deep_pct', 'efficiency'
    lag_days: int  # 0 = same night, 1 = next night
    correlation: float
    p_value: float
    n_pairs: int
    is_significant: bool
    interpretation: str


@dataclass
class DaylightReport:
    """Complete daylight analysis report."""

    baseline: Optional[DaylightBaseline]
    recent_days: List[DailyDaylight]
    current_deviation: Optional[DaylightDeviation]
    trend: Optional[DaylightTrend]
    sleep_correlations: List[DaylightSleepCorrelation]

    # Summary statistics
    avg_daily_min_30d: Optional[float]
    avg_morning_min_30d: Optional[float]
    pct_days_morning_light_30d: Optional[float]

    # Flags
    concerns: List[str]
    insights: List[str]


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


def _aggregate_daily_daylight(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate daylight records into daily totals.

    Args:
        df: DataFrame with columns [time, biomarker_slug, value]
            where biomarker_slug == 'time_in_daylight'
            and value is duration in minutes

    Returns:
        DataFrame with one row per day, columns for each time segment
    """
    daylight_data = df[df["biomarker_slug"] == "time_in_daylight"].copy()

    if len(daylight_data) == 0:
        return pd.DataFrame()

    daylight_data["time"] = pd.to_datetime(daylight_data["time"], utc=True)
    daylight_data["date"] = daylight_data["time"].dt.date
    daylight_data["hour"] = daylight_data["time"].dt.hour

    # Categorize by time of day
    daylight_data["segment"] = "afternoon"
    daylight_data.loc[daylight_data["hour"] < 10, "segment"] = "morning"
    daylight_data.loc[
        (daylight_data["hour"] >= 10) & (daylight_data["hour"] < 14), "segment"
    ] = "midday"

    # Aggregate by date and segment
    daily_segments = daylight_data.pivot_table(
        index="date", columns="segment", values="value", aggfunc="sum", fill_value=0
    )

    # Ensure all columns exist
    for seg in ["morning", "midday", "afternoon"]:
        if seg not in daily_segments.columns:
            daily_segments[seg] = 0.0

    daily_segments = daily_segments.reset_index()

    # Rename columns to add _min suffix
    daily_segments = daily_segments.rename(
        columns={
            "morning": "morning_min",
            "midday": "midday_min",
            "afternoon": "afternoon_min",
        }
    )

    # Ensure columns are in correct order
    daily_segments = daily_segments[
        ["date", "morning_min", "midday_min", "afternoon_min"]
    ]

    # Total
    daily_segments["total_min"] = (
        daily_segments["morning_min"]
        + daily_segments["midday_min"]
        + daily_segments["afternoon_min"]
    )

    # Meaningful morning exposure (>=20 min)
    daily_segments["has_morning_exposure"] = daily_segments["morning_min"] >= 20

    return daily_segments.sort_values("date")


# ============================================
# MAIN ANALYSIS FUNCTIONS
# ============================================


def compute_daily_daylight(df: pd.DataFrame) -> List[DailyDaylight]:
    """
    Compute daily daylight metrics from raw records.

    Args:
        df: DataFrame with [time, biomarker_slug, value]

    Returns:
        List of DailyDaylight objects, one per day
    """
    daily = _aggregate_daily_daylight(df)

    if len(daily) == 0:
        return []

    results = []
    for _, row in daily.iterrows():
        results.append(
            DailyDaylight(
                date=row["date"],
                total_min=float(row["total_min"]),
                morning_min=float(row["morning_min"]),
                midday_min=float(row["midday_min"]),
                afternoon_min=float(row["afternoon_min"]),
                has_morning_exposure=bool(row["has_morning_exposure"]),
            )
        )

    return results


def compute_daylight_baseline(
    df: pd.DataFrame, window_days: int = 90, min_days: int = 14
) -> Optional[DaylightBaseline]:
    """
    Compute personal baseline for daylight exposure.

    Args:
        df: DataFrame with daylight records
        window_days: Number of days to include in baseline
        min_days: Minimum days required

    Returns:
        DaylightBaseline or None if insufficient data
    """
    daily = _aggregate_daily_daylight(df)

    if len(daily) == 0:
        return None

    # Filter to window
    cutoff = pd.Timestamp.now(tz="UTC").date() - timedelta(days=window_days)
    daily = daily[daily["date"] >= cutoff]

    if len(daily) < min_days:
        return None

    # Compute baselines
    total_ci = _confidence_interval(daily["total_min"].values)
    morning_ci = _confidence_interval(daily["morning_min"].values)
    midday_ci = _confidence_interval(daily["midday_min"].values)
    afternoon_ci = _confidence_interval(daily["afternoon_min"].values)

    if not all([total_ci, morning_ci, midday_ci, afternoon_ci]):
        return None

    # Percentage of days with morning light
    pct_morning = float(daily["has_morning_exposure"].mean() * 100)

    # Variability (coefficient of variation)
    cv = daily["total_min"].std() / (daily["total_min"].mean() + 0.01)

    # Consistency score (inverse of CV)
    consistency = max(0, min(100, 100 * (1 - cv)))

    # Sufficiency: at least 30 min/day average and 50% days with morning light
    is_sufficient = total_ci.mean >= 30 and pct_morning >= 50

    return DaylightBaseline(
        computed_at=pd.Timestamp.now(tz="UTC"),
        n_days=len(daily),
        total_daylight=total_ci,
        morning_daylight=morning_ci,
        midday_daylight=midday_ci,
        afternoon_daylight=afternoon_ci,
        pct_days_with_morning_light=pct_morning,
        morning_light_mean=morning_ci.mean,
        variability_score=float(cv),
        is_sufficient=is_sufficient,
        consistency_score=float(consistency),
    )


def compute_daylight_deviation(
    day: DailyDaylight, baseline: DaylightBaseline
) -> DaylightDeviation:
    """
    Compute how a day's daylight deviates from personal baseline.
    """

    def z_score(value: float, ci: ConfidenceInterval) -> float:
        std = (ci.ci_upper - ci.ci_lower) / (2 * 1.96) * np.sqrt(ci.n)
        return (value - ci.mean) / std if std > 0 else 0.0

    total_z = z_score(day.total_min, baseline.total_daylight)
    morning_z = z_score(day.morning_min, baseline.morning_daylight)

    is_low = total_z < -1.5
    is_no_morning = not day.has_morning_exposure and baseline.morning_light_mean >= 20
    is_notable = is_low or is_no_morning

    # Interpretation
    issues = []
    if is_no_morning:
        issues.append("No morning daylight exposure today")
    if is_low:
        issues.append(
            f"Total daylight ({day.total_min:.0f} min) well below your average"
        )

    if not issues:
        interpretation = "Daylight exposure within your normal range"
    else:
        interpretation = "; ".join(issues)

    return DaylightDeviation(
        date=day.date,
        total_z=float(total_z),
        morning_z=float(morning_z),
        is_low=is_low,
        is_no_morning_light=is_no_morning,
        is_notable=is_notable,
        interpretation=interpretation,
    )


def analyze_daylight_trend(
    df: pd.DataFrame, period_days: int = 30
) -> Optional[DaylightTrend]:
    """
    Analyze trend in daylight exposure.

    Args:
        df: DataFrame with daylight records
        period_days: Number of days to analyze

    Returns:
        DaylightTrend or None if insufficient data
    """
    daily = _aggregate_daily_daylight(df)

    if len(daily) == 0:
        return None

    cutoff = pd.Timestamp.now(tz="UTC").date() - timedelta(days=period_days)
    daily = daily[daily["date"] >= cutoff]

    if len(daily) < 7:
        return None

    # Linear regression
    x = np.arange(len(daily))
    y = daily["total_min"].values

    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

    is_significant = p_value < 0.05

    if not is_significant:
        direction = "stable"
        interpretation = f"Daylight exposure stable over past {period_days} days"
    elif slope > 0:
        direction = "increasing"
        interpretation = (
            f"Getting more daylight (+{slope:.1f} min/day, p={p_value:.3f})"
        )
    else:
        direction = "decreasing"
        interpretation = f"Getting less daylight ({slope:.1f} min/day, p={p_value:.3f})"

    # Percentage change
    start_val = intercept
    end_val = intercept + slope * len(daily)
    pct_change = (end_val - start_val) / start_val * 100 if start_val != 0 else 0

    return DaylightTrend(
        period_days=period_days,
        slope=float(slope),
        slope_pct=float(pct_change),
        p_value=float(p_value),
        r_squared=float(r_value**2),
        is_significant=is_significant,
        direction=direction,
        interpretation=interpretation,
    )


def compute_daylight_sleep_correlation(
    daylight_df: pd.DataFrame,
    sleep_df: pd.DataFrame,
    sleep_metric: str = "total_sleep_min",
    lag_days: int = 0,
) -> Optional[DaylightSleepCorrelation]:
    """
    Compute correlation between daylight exposure and sleep metric.

    Args:
        daylight_df: DataFrame with daylight records
        sleep_df: DataFrame with sleep stage records
        sleep_metric: Which sleep metric to correlate
        lag_days: 0 = same night, 1 = next night

    Returns:
        DaylightSleepCorrelation or None
    """
    # Import sleep aggregation
    from .sleep import _aggregate_nightly_sleep

    daily_daylight = _aggregate_daily_daylight(daylight_df)
    nightly_sleep = _aggregate_nightly_sleep(sleep_df)

    if len(daily_daylight) == 0 or len(nightly_sleep) == 0:
        return None

    if sleep_metric not in nightly_sleep.columns:
        return None

    # Align dates
    daily_daylight = daily_daylight.set_index("date")
    nightly_sleep = nightly_sleep.set_index("sleep_date")

    # Apply lag (daylight on day N affects sleep on night N+lag)
    if lag_days > 0:
        nightly_sleep.index = nightly_sleep.index - pd.Timedelta(days=lag_days)

    # Find common dates
    common_dates = daily_daylight.index.intersection(nightly_sleep.index)

    if len(common_dates) < 10:
        return None

    daylight_values = daily_daylight.loc[common_dates, "total_min"].values
    sleep_values = nightly_sleep.loc[common_dates, sleep_metric].values

    # Remove NaN
    mask = ~(np.isnan(daylight_values) | np.isnan(sleep_values))
    daylight_values = daylight_values[mask]
    sleep_values = sleep_values[mask]

    if len(daylight_values) < 10:
        return None

    # Pearson correlation
    corr, p_value = stats.pearsonr(daylight_values, sleep_values)

    is_significant = p_value < 0.05

    # Interpretation
    metric_nice = sleep_metric.replace("_", " ").title()
    lag_text = "same night" if lag_days == 0 else f"next {lag_days} night(s)"

    if not is_significant:
        interpretation = (
            f"No significant relationship between daylight and {metric_nice}"
        )
    elif corr > 0:
        interpretation = (
            f"More daylight associated with higher {metric_nice} ({lag_text})"
        )
    else:
        interpretation = (
            f"More daylight associated with lower {metric_nice} ({lag_text})"
        )

    return DaylightSleepCorrelation(
        sleep_metric=sleep_metric,
        lag_days=lag_days,
        correlation=float(corr),
        p_value=float(p_value),
        n_pairs=len(daylight_values),
        is_significant=is_significant,
        interpretation=interpretation,
    )


def generate_daylight_report(
    daylight_df: pd.DataFrame,
    sleep_df: Optional[pd.DataFrame] = None,
    baseline_days: int = 90,
    trend_days: int = 30,
) -> DaylightReport:
    """
    Generate complete daylight analysis report.

    Args:
        daylight_df: DataFrame with daylight records
        sleep_df: Optional DataFrame with sleep records for correlation
        baseline_days: Days for baseline computation
        trend_days: Days for trend analysis

    Returns:
        DaylightReport with all analyses
    """
    # Compute baseline
    baseline = compute_daylight_baseline(daylight_df, window_days=baseline_days)

    # Get recent days
    daily = _aggregate_daily_daylight(daylight_df)
    recent_cutoff = pd.Timestamp.now(tz="UTC").date() - timedelta(days=trend_days)

    recent_days = []
    if len(daily) > 0:
        recent_data = daily[daily["date"] >= recent_cutoff]

        for _, row in recent_data.iterrows():
            recent_days.append(
                DailyDaylight(
                    date=row["date"],
                    total_min=float(row["total_min"]),
                    morning_min=float(row["morning_min"]),
                    midday_min=float(row["midday_min"]),
                    afternoon_min=float(row["afternoon_min"]),
                    has_morning_exposure=bool(row["has_morning_exposure"]),
                )
            )

    # Current deviation
    current_deviation = None
    if baseline and recent_days:
        current_deviation = compute_daylight_deviation(recent_days[-1], baseline)

    # Trend
    trend = analyze_daylight_trend(daylight_df, trend_days)

    # Sleep correlations
    sleep_correlations = []
    if sleep_df is not None and len(sleep_df) > 0:
        for metric in ["total_sleep_min", "rem_pct", "deep_pct", "efficiency"]:
            for lag in [0, 1]:
                corr = compute_daylight_sleep_correlation(
                    daylight_df, sleep_df, metric, lag
                )
                if corr and corr.is_significant:
                    sleep_correlations.append(corr)

    # Summary stats
    avg_daily = avg_morning = pct_morning = None
    if recent_days:
        avg_daily = float(np.mean([d.total_min for d in recent_days]))
        avg_morning = float(np.mean([d.morning_min for d in recent_days]))
        pct_morning = float(
            np.mean([d.has_morning_exposure for d in recent_days]) * 100
        )

    # Generate concerns and insights
    concerns = []
    insights = []

    if baseline:
        if baseline.total_daylight.mean < 30:
            concerns.append(
                f"Average daylight ({baseline.total_daylight.mean:.0f} min/day) "
                "is below recommended 30 min"
            )

        if baseline.pct_days_with_morning_light < 50:
            concerns.append(
                f"Only {baseline.pct_days_with_morning_light:.0f}% of days have morning light exposure"
            )
        elif baseline.pct_days_with_morning_light >= 70:
            insights.append(
                f"Good morning light routine ({baseline.pct_days_with_morning_light:.0f}% of days)"
            )

        if baseline.is_sufficient:
            insights.append("Meeting daylight exposure recommendations")

        if baseline.consistency_score >= 70:
            insights.append(
                f"Consistent daylight patterns (score: {baseline.consistency_score:.0f}/100)"
            )
        elif baseline.consistency_score < 50:
            concerns.append("Highly variable daylight exposure day-to-day")

    if trend and trend.is_significant and trend.direction == "decreasing":
        concerns.append(trend.interpretation)
    elif trend and trend.is_significant and trend.direction == "increasing":
        insights.append(trend.interpretation)

    # Sleep correlation insights
    for corr in sleep_correlations:
        if corr.correlation > 0.3:
            insights.append(corr.interpretation)
        elif corr.correlation < -0.3:
            concerns.append(corr.interpretation)

    return DaylightReport(
        baseline=baseline,
        recent_days=recent_days,
        current_deviation=current_deviation,
        trend=trend,
        sleep_correlations=sleep_correlations,
        avg_daily_min_30d=avg_daily,
        avg_morning_min_30d=avg_morning,
        pct_days_morning_light_30d=pct_morning,
        concerns=concerns,
        insights=insights,
    )
