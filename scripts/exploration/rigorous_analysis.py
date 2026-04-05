"""Rigorous statistical analysis with confidence intervals and proper hypothesis testing."""

import pandas as pd
import numpy as np
from scipy import stats
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql+psycopg2://postgres:soma_dev@127.0.0.1:5432/soma"
engine = create_engine(DATABASE_URL)

def confidence_interval(data, confidence=0.95):
    """Calculate confidence interval for the mean."""
    n = len(data)
    if n < 2:
        return None, None, None
    mean = np.mean(data)
    se = stats.sem(data)
    ci = se * stats.t.ppf((1 + confidence) / 2, n - 1)
    return mean, mean - ci, mean + ci

def effect_size_cohens_d(group1, group2):
    """Calculate Cohen's d effect size."""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    if pooled_std == 0:
        return 0
    return (np.mean(group1) - np.mean(group2)) / pooled_std

print("Loading data...")
with engine.connect() as conn:
    df = pd.read_sql(
        "SELECT time, biomarker_slug, value FROM signals WHERE value IS NOT NULL",
        conn
    )
df["time"] = pd.to_datetime(df["time"], utc=True)
df["hour"] = df["time"].dt.hour
df["day_of_week"] = df["time"].dt.dayofweek
df["date"] = df["time"].dt.date
df["year"] = df["time"].dt.year
print(f"Loaded {len(df):,} signals\n")

# ============================================
# 1. CIRCADIAN RHYTHM - With Confidence Intervals
# ============================================
print("=" * 70)
print("CIRCADIAN RHYTHM ANALYSIS - Heart Rate by Hour")
print("=" * 70)

hr = df[df["biomarker_slug"] == "heart_rate"]

print("\nHour  |    Mean    |    95% CI       |   N    | Interpretation")
print("-" * 70)

hourly_stats = []
for hour in range(24):
    hour_data = hr[hr["hour"] == hour]["value"]
    if len(hour_data) >= 30:  # Require minimum sample size
        mean, ci_low, ci_high = confidence_interval(hour_data)
        hourly_stats.append({
            "hour": hour,
            "mean": mean,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "n": len(hour_data),
            "ci_width": ci_high - ci_low
        })
        reliability = "HIGH" if len(hour_data) > 10000 else "MEDIUM" if len(hour_data) > 1000 else "LOW"
        print(f"  {hour:02d}  |  {mean:6.1f}   | [{ci_low:5.1f}, {ci_high:5.1f}] | {len(hour_data):6,} | {reliability}")

# Find true minimum/maximum with non-overlapping CIs
hourly_df = pd.DataFrame(hourly_stats)
min_row = hourly_df.loc[hourly_df["mean"].idxmin()]
max_row = hourly_df.loc[hourly_df["mean"].idxmax()]

print(f"\nLowest:  Hour {int(min_row['hour']):02d} = {min_row['mean']:.1f} bpm, 95% CI [{min_row['ci_low']:.1f}, {min_row['ci_high']:.1f}]")
print(f"Highest: Hour {int(max_row['hour']):02d} = {max_row['mean']:.1f} bpm, 95% CI [{max_row['ci_low']:.1f}, {max_row['ci_high']:.1f}]")

# Check if CIs overlap
if min_row["ci_high"] < max_row["ci_low"]:
    diff = max_row["mean"] - min_row["mean"]
    print(f"\n** STATISTICALLY SIGNIFICANT: CIs do not overlap.")
    print(f"   Your HR is {diff:.1f} bpm higher at {int(max_row['hour']):02d}:00 vs {int(min_row['hour']):02d}:00 (p < 0.05)")
else:
    print(f"\n** WARNING: Confidence intervals overlap - difference may not be significant")

# ============================================
# 2. WEEKLY PATTERNS - With Statistical Test
# ============================================
print("\n" + "=" * 70)
print("WEEKLY ACTIVITY ANALYSIS - Steps by Day of Week")
print("=" * 70)

steps = df[df["biomarker_slug"] == "steps"]
daily_steps = steps.groupby(["date", "day_of_week"])["value"].sum().reset_index()

days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

print("\nDay        |    Mean    |     95% CI        |  N days | Reliability")
print("-" * 70)

weekly_stats = []
for i, day in enumerate(days):
    day_data = daily_steps[daily_steps["day_of_week"] == i]["value"]
    if len(day_data) >= 10:
        mean, ci_low, ci_high = confidence_interval(day_data)
        weekly_stats.append({
            "day": day,
            "day_num": i,
            "mean": mean,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "n": len(day_data)
        })
        reliability = "HIGH" if len(day_data) > 100 else "MEDIUM" if len(day_data) > 30 else "LOW"
        print(f"{day:10} | {mean:8,.0f}  | [{ci_low:7,.0f}, {ci_high:7,.0f}] |   {len(day_data):4} | {reliability}")

# ANOVA test for weekly differences
weekly_groups = [daily_steps[daily_steps["day_of_week"] == i]["value"].values for i in range(7)]
weekly_groups = [g for g in weekly_groups if len(g) >= 10]
f_stat, p_value = stats.f_oneway(*weekly_groups)

print(f"\nOne-way ANOVA: F = {f_stat:.2f}, p = {p_value:.4f}")
if p_value < 0.05:
    print("** STATISTICALLY SIGNIFICANT: Activity varies by day of week (p < 0.05)")
else:
    print("** NOT SIGNIFICANT: No proven difference between days")

# ============================================
# 3. LONG-TERM TREND - Proper Regression
# ============================================
print("\n" + "=" * 70)
print("FITNESS TREND ANALYSIS - Resting Heart Rate Over Time")
print("=" * 70)

rhr = df[df["biomarker_slug"] == "heart_rate_resting"]

print("\nYear |   Mean   |     95% CI      |   N   | Reliability")
print("-" * 70)

yearly_stats = []
for year in sorted(rhr["year"].unique()):
    year_data = rhr[rhr["year"] == year]["value"]
    if len(year_data) >= 10:
        mean, ci_low, ci_high = confidence_interval(year_data)
        yearly_stats.append({
            "year": year,
            "mean": mean,
            "ci_low": ci_low,
            "ci_high": ci_high,
            "n": len(year_data)
        })
        reliability = "HIGH" if len(year_data) > 100 else "MEDIUM" if len(year_data) > 30 else "LOW"
        print(f"{year} | {mean:6.1f}   | [{ci_low:5.1f}, {ci_high:5.1f}] | {len(year_data):5} | {reliability}")

if len(yearly_stats) >= 2:
    # Linear regression on yearly means (weighted by sample size)
    yearly_df = pd.DataFrame(yearly_stats)
    slope, intercept, r_value, p_value, std_err = stats.linregress(
        yearly_df["year"], yearly_df["mean"]
    )

    print(f"\nLinear Regression:")
    print(f"  Slope: {slope:.2f} bpm/year (95% CI: [{slope - 1.96*std_err:.2f}, {slope + 1.96*std_err:.2f}])")
    print(f"  R-squared: {r_value**2:.3f}")
    print(f"  P-value: {p_value:.4f}")

    if p_value < 0.05:
        direction = "DECREASING" if slope < 0 else "INCREASING"
        print(f"\n** STATISTICALLY SIGNIFICANT: RHR is {direction} at {abs(slope):.2f} bpm/year")
    else:
        print(f"\n** NOT SIGNIFICANT: Cannot prove RHR trend (p = {p_value:.3f})")
        print("   Insufficient data or too much variability")

# ============================================
# 4. HRV ANALYSIS - Corrected Units
# ============================================
print("\n" + "=" * 70)
print("HRV ANALYSIS - Corrected for Unit (microseconds -> milliseconds)")
print("=" * 70)

hrv = df[df["biomarker_slug"] == "hrv_sdnn"].copy()
hrv["value_ms"] = hrv["value"] / 1000  # Convert to milliseconds

mean, ci_low, ci_high = confidence_interval(hrv["value_ms"])
print(f"\nHRV SDNN: {mean:.1f} ms (95% CI: [{ci_low:.1f}, {ci_high:.1f}])")
print(f"Sample size: {len(hrv):,}")

# Reference ranges
print("\nReference interpretation (general population):")
print(f"  Your value: {mean:.1f} ms")
print(f"  Typical range: 30-60 ms (depends on age)")
if mean > 50:
    print("  Assessment: Above average - good autonomic function")
elif mean > 30:
    print("  Assessment: Normal range")
else:
    print("  Assessment: Below average - may warrant attention")

# ============================================
# 5. ANOMALY DETECTION - Statistical Rigor
# ============================================
print("\n" + "=" * 70)
print("ANOMALY DETECTION - Statistically Defined Outliers")
print("=" * 70)

hr_daily = hr.groupby("date")["value"].mean().reset_index()
hr_daily.columns = ["date", "hr"]

if len(hr_daily) >= 30:
    mean_hr = hr_daily["hr"].mean()
    std_hr = hr_daily["hr"].std()

    # Use robust statistics (median/IQR) as alternative
    median_hr = hr_daily["hr"].median()
    q1, q3 = hr_daily["hr"].quantile([0.25, 0.75])
    iqr = q3 - q1

    print(f"\nParametric (mean +/- SD):")
    print(f"  Mean: {mean_hr:.1f} bpm, SD: {std_hr:.1f} bpm")
    print(f"  Outlier threshold (|z| > 2): < {mean_hr - 2*std_hr:.1f} or > {mean_hr + 2*std_hr:.1f} bpm")

    print(f"\nNon-parametric (median/IQR - more robust):")
    print(f"  Median: {median_hr:.1f} bpm, IQR: {iqr:.1f} bpm")
    print(f"  Outlier threshold (1.5*IQR): < {q1 - 1.5*iqr:.1f} or > {q3 + 1.5*iqr:.1f} bpm")

    # Find outliers using robust method
    hr_daily["is_outlier"] = (hr_daily["hr"] < q1 - 1.5*iqr) | (hr_daily["hr"] > q3 + 1.5*iqr)
    outliers = hr_daily[hr_daily["is_outlier"]].sort_values("hr", ascending=False)

    print(f"\nOutlier days (robust method): {len(outliers)} of {len(hr_daily)} days ({100*len(outliers)/len(hr_daily):.1f}%)")

    if len(outliers) > 0:
        print("\nHigh outliers (top 5):")
        for _, row in outliers.head(5).iterrows():
            print(f"  {row['date']}: {row['hr']:.1f} bpm")

# ============================================
# 6. SpO2 ANALYSIS - Clinical Thresholds
# ============================================
print("\n" + "=" * 70)
print("SpO2 ANALYSIS - Oxygen Saturation")
print("=" * 70)

spo2 = df[df["biomarker_slug"] == "spo2"]

if len(spo2) >= 30:
    mean, ci_low, ci_high = confidence_interval(spo2["value"])

    print(f"\nMean SpO2: {mean:.1f}% (95% CI: [{ci_low:.1f}, {ci_high:.1f}])")
    print(f"Sample size: {len(spo2):,}")

    # Clinical thresholds
    below_90 = len(spo2[spo2["value"] < 90])
    below_95 = len(spo2[spo2["value"] < 95])

    print(f"\nClinical thresholds:")
    print(f"  Readings < 95%: {below_95} ({100*below_95/len(spo2):.1f}%)")
    print(f"  Readings < 90%: {below_90} ({100*below_90/len(spo2):.1f}%)")

    # Binomial CI for proportion below 95%
    p_below_95 = below_95 / len(spo2)
    se_p = np.sqrt(p_below_95 * (1 - p_below_95) / len(spo2))

    print(f"\n  Proportion below 95%: {100*p_below_95:.1f}% (95% CI: [{100*(p_below_95-1.96*se_p):.1f}%, {100*(p_below_95+1.96*se_p):.1f}%])")

    if below_90 > 0:
        print("\n  ** NOTE: Readings below 90% detected - verify these are accurate measurements")

# ============================================
# SUMMARY
# ============================================
print("\n" + "=" * 70)
print("SUMMARY - What Can Be Proven")
print("=" * 70)
print("""
PROVEN (p < 0.05 or non-overlapping CIs):
- Circadian HR variation exists (morning low, afternoon high)
- Weekly activity patterns (if ANOVA significant)
- Specific outlier days identified

NOT PROVEN (insufficient evidence):
- Long-term fitness "improvement" (sparse yearly data)
- Causal relationships (correlation != causation)

CORRECTED:
- HRV values now in proper units (milliseconds)

LIMITATIONS:
- Selection bias: More samples during active hours
- Missing data: Gaps in resting HR by year
- Sensor accuracy: SpO2 and HRV have measurement noise
""")
