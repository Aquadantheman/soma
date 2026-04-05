"""Rigorous statistical analyses that produce mathematically provable results.

All functions in this module return results with confidence intervals and
p-values where applicable. Claims are only made when statistically justified.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional
import pandas as pd
import numpy as np
from scipy import stats


@dataclass
class ConfidenceInterval:
    """A value with its confidence interval."""

    mean: float
    ci_lower: float
    ci_upper: float
    n: int
    confidence: float = 0.95

    @property
    def ci_width(self) -> float:
        return self.ci_upper - self.ci_lower

    @property
    def is_reliable(self) -> bool:
        """High reliability if n > 100."""
        return self.n >= 100


@dataclass
class HourlyPattern:
    """Heart rate pattern for a specific hour."""

    hour: int
    stats: ConfidenceInterval


@dataclass
class CircadianResult:
    """Result of circadian rhythm analysis."""

    hourly_patterns: list[HourlyPattern]
    lowest_hour: int
    lowest_hr: ConfidenceInterval
    highest_hour: int
    highest_hr: ConfidenceInterval
    is_significant: bool
    amplitude: float  # Difference between highest and lowest
    total_samples: int


@dataclass
class DayOfWeekPattern:
    """Activity pattern for a specific day."""

    day_name: str
    day_number: int  # 0=Monday, 6=Sunday
    stats: ConfidenceInterval


@dataclass
class WeeklyActivityResult:
    """Result of weekly activity pattern analysis."""

    daily_patterns: list[DayOfWeekPattern]
    most_active_day: str
    least_active_day: str
    f_statistic: float
    p_value: float
    is_significant: bool
    total_days: int


@dataclass
class TrendResult:
    """Result of long-term trend analysis."""

    yearly_stats: list[dict]  # year, mean, ci_lower, ci_upper, n
    slope: float  # change per year
    slope_ci_lower: float
    slope_ci_upper: float
    r_squared: float
    p_value: float
    is_significant: bool
    direction: Optional[str]  # "increasing", "decreasing", or None


@dataclass
class AnomalyDay:
    """A statistically anomalous day."""

    date: date
    value: float
    z_score: float
    direction: str  # "high" or "low"


@dataclass
class AnomalyResult:
    """Result of anomaly detection."""

    mean: float
    std: float
    median: float
    iqr: float
    threshold_low: float
    threshold_high: float
    anomalies: list[AnomalyDay]
    total_days: int
    anomaly_rate: float


@dataclass
class HRVResult:
    """Result of HRV analysis with corrected units."""

    mean_ms: ConfidenceInterval
    assessment: str  # "above_average", "normal", "below_average"
    unit_correction_applied: bool


@dataclass
class SpO2Result:
    """Result of SpO2 analysis."""

    mean: ConfidenceInterval
    pct_below_95: float
    pct_below_95_ci: tuple[float, float]
    pct_below_90: float
    count_below_90: int
    assessment: str


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


def analyze_circadian_rhythm(
    df: pd.DataFrame, biomarker_slug: str = "heart_rate"
) -> Optional[CircadianResult]:
    """
    Analyze circadian rhythm patterns with statistical rigor.

    Returns hourly patterns with confidence intervals.
    Only claims significance when CIs don't overlap.
    """
    data = df[df["biomarker_slug"] == biomarker_slug].copy()
    if len(data) < 100:
        return None

    data["hour"] = pd.to_datetime(data["time"], utc=True).dt.hour

    hourly_patterns = []
    for hour in range(24):
        hour_data = data[data["hour"] == hour]["value"].values
        if len(hour_data) >= 30:
            ci = _confidence_interval(hour_data)
            if ci:
                hourly_patterns.append(HourlyPattern(hour=hour, stats=ci))

    if len(hourly_patterns) < 12:
        return None

    # Find lowest and highest
    sorted_by_mean = sorted(hourly_patterns, key=lambda x: x.stats.mean)
    lowest = sorted_by_mean[0]
    highest = sorted_by_mean[-1]

    # Check if CIs overlap
    is_significant = lowest.stats.ci_upper < highest.stats.ci_lower
    amplitude = highest.stats.mean - lowest.stats.mean

    return CircadianResult(
        hourly_patterns=hourly_patterns,
        lowest_hour=lowest.hour,
        lowest_hr=lowest.stats,
        highest_hour=highest.hour,
        highest_hr=highest.stats,
        is_significant=is_significant,
        amplitude=amplitude,
        total_samples=len(data),
    )


def analyze_weekly_activity(
    df: pd.DataFrame, biomarker_slug: str = "steps"
) -> Optional[WeeklyActivityResult]:
    """
    Analyze weekly activity patterns with ANOVA test.

    Returns daily patterns with confidence intervals and ANOVA significance.
    """
    data = df[df["biomarker_slug"] == biomarker_slug].copy()
    if len(data) < 100:
        return None

    data["date"] = pd.to_datetime(data["time"], utc=True).dt.date
    data["day_of_week"] = pd.to_datetime(data["time"], utc=True).dt.dayofweek

    # Aggregate to daily totals
    daily = data.groupby(["date", "day_of_week"])["value"].sum().reset_index()

    days = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    daily_patterns = []
    groups = []

    for i, day_name in enumerate(days):
        day_data = daily[daily["day_of_week"] == i]["value"].values
        if len(day_data) >= 10:
            ci = _confidence_interval(day_data)
            if ci:
                daily_patterns.append(
                    DayOfWeekPattern(day_name=day_name, day_number=i, stats=ci)
                )
                groups.append(day_data)

    if len(groups) < 3:
        return None

    # ANOVA test
    f_stat, p_value = stats.f_oneway(*groups)

    sorted_by_mean = sorted(daily_patterns, key=lambda x: x.stats.mean)

    return WeeklyActivityResult(
        daily_patterns=daily_patterns,
        most_active_day=sorted_by_mean[-1].day_name,
        least_active_day=sorted_by_mean[0].day_name,
        f_statistic=float(f_stat),
        p_value=float(p_value),
        is_significant=p_value < 0.05,
        total_days=len(daily),
    )


def analyze_long_term_trend(
    df: pd.DataFrame, biomarker_slug: str = "heart_rate_resting"
) -> Optional[TrendResult]:
    """
    Analyze long-term trends with linear regression.

    Only claims trend if statistically significant.
    """
    data = df[df["biomarker_slug"] == biomarker_slug].copy()
    if len(data) < 50:
        return None

    data["year"] = pd.to_datetime(data["time"], utc=True).dt.year

    yearly_stats = []
    for year in sorted(data["year"].unique()):
        year_data = data[data["year"] == year]["value"].values
        if len(year_data) >= 10:
            ci = _confidence_interval(year_data)
            if ci:
                yearly_stats.append(
                    {
                        "year": int(year),
                        "mean": ci.mean,
                        "ci_lower": ci.ci_lower,
                        "ci_upper": ci.ci_upper,
                        "n": ci.n,
                    }
                )

    if len(yearly_stats) < 2:
        return None

    # Linear regression
    years = [s["year"] for s in yearly_stats]
    means = [s["mean"] for s in yearly_stats]

    slope, intercept, r_value, p_value, std_err = stats.linregress(years, means)

    is_significant = p_value < 0.05
    direction = None
    if is_significant:
        direction = "decreasing" if slope < 0 else "increasing"

    return TrendResult(
        yearly_stats=yearly_stats,
        slope=float(slope),
        slope_ci_lower=float(slope - 1.96 * std_err),
        slope_ci_upper=float(slope + 1.96 * std_err),
        r_squared=float(r_value**2),
        p_value=float(p_value),
        is_significant=is_significant,
        direction=direction,
    )


def detect_anomalies(
    df: pd.DataFrame, biomarker_slug: str = "heart_rate"
) -> Optional[AnomalyResult]:
    """
    Detect anomalous days using robust statistics (IQR method).

    Uses non-parametric method which is more robust to outliers.
    """
    data = df[df["biomarker_slug"] == biomarker_slug].copy()
    if len(data) < 100:
        return None

    data["date"] = pd.to_datetime(data["time"], utc=True).dt.date
    daily = data.groupby("date")["value"].mean().reset_index()
    daily.columns = ["date", "value"]

    if len(daily) < 30:
        return None

    mean = float(daily["value"].mean())
    std = float(daily["value"].std())
    median = float(daily["value"].median())
    q1, q3 = daily["value"].quantile([0.25, 0.75])
    iqr = float(q3 - q1)

    threshold_low = float(q1 - 1.5 * iqr)
    threshold_high = float(q3 + 1.5 * iqr)

    daily["is_anomaly"] = (daily["value"] < threshold_low) | (
        daily["value"] > threshold_high
    )
    daily["z_score"] = (daily["value"] - mean) / std

    anomalies = []
    for _, row in daily[daily["is_anomaly"]].iterrows():
        anomalies.append(
            AnomalyDay(
                date=row["date"],
                value=float(row["value"]),
                z_score=float(row["z_score"]),
                direction="high" if row["value"] > threshold_high else "low",
            )
        )

    # Sort by absolute z-score
    anomalies.sort(key=lambda x: abs(x.z_score), reverse=True)

    return AnomalyResult(
        mean=mean,
        std=std,
        median=median,
        iqr=iqr,
        threshold_low=threshold_low,
        threshold_high=threshold_high,
        anomalies=anomalies,
        total_days=len(daily),
        anomaly_rate=len(anomalies) / len(daily),
    )


def analyze_hrv(
    df: pd.DataFrame, biomarker_slug: str = "hrv_sdnn"
) -> Optional[HRVResult]:
    """
    Analyze HRV with unit correction.

    Apple Health stores HRV in microseconds; this converts to milliseconds.
    """
    data = df[df["biomarker_slug"] == biomarker_slug].copy()
    if len(data) < 30:
        return None

    # Check if values are in microseconds (>1000 suggests microseconds)
    median_val = data["value"].median()
    unit_correction = median_val > 1000

    if unit_correction:
        values = data["value"].values / 1000
    else:
        values = data["value"].values

    ci = _confidence_interval(values)
    if not ci:
        return None

    # Assessment based on typical ranges
    if ci.mean > 50:
        assessment = "above_average"
    elif ci.mean > 30:
        assessment = "normal"
    else:
        assessment = "below_average"

    return HRVResult(
        mean_ms=ci, assessment=assessment, unit_correction_applied=unit_correction
    )


def analyze_spo2(
    df: pd.DataFrame, biomarker_slug: str = "spo2"
) -> Optional[SpO2Result]:
    """
    Analyze SpO2 with clinical thresholds.
    """
    data = df[df["biomarker_slug"] == biomarker_slug].copy()
    if len(data) < 30:
        return None

    values = data["value"].values
    ci = _confidence_interval(values)
    if not ci:
        return None

    n = len(values)
    below_95 = int(np.sum(values < 95))
    below_90 = int(np.sum(values < 90))

    pct_below_95 = below_95 / n
    se_p = np.sqrt(pct_below_95 * (1 - pct_below_95) / n)

    # Assessment
    if ci.mean >= 96 and pct_below_95 < 0.1:
        assessment = "healthy"
    elif ci.mean >= 94:
        assessment = "normal"
    else:
        assessment = "low"

    return SpO2Result(
        mean=ci,
        pct_below_95=pct_below_95,
        pct_below_95_ci=(pct_below_95 - 1.96 * se_p, pct_below_95 + 1.96 * se_p),
        pct_below_90=below_90 / n,
        count_below_90=below_90,
        assessment=assessment,
    )
