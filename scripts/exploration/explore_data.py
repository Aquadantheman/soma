"""Explore what insights we can derive from the data."""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

DATABASE_URL = "postgresql+psycopg2://postgres:soma_dev@127.0.0.1:5432/soma"
engine = create_engine(DATABASE_URL)

def load_signals():
    """Load all signals into a DataFrame."""
    with engine.connect() as conn:
        df = pd.read_sql(
            "SELECT time, biomarker_slug, value FROM signals WHERE value IS NOT NULL",
            conn
        )
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df["date"] = df["time"].dt.date
    df["hour"] = df["time"].dt.hour
    df["day_of_week"] = df["time"].dt.dayofweek  # 0=Monday, 6=Sunday
    df["year"] = df["time"].dt.year
    df["month"] = df["time"].dt.month
    return df

print("Loading your data...")
df = load_signals()
print(f"Loaded {len(df):,} signals\n")

# ============================================
# 1. CIRCADIAN RHYTHM - Heart Rate by Hour
# ============================================
print("=" * 60)
print("CIRCADIAN RHYTHM - Your Heart Rate by Hour of Day")
print("=" * 60)
hr = df[df["biomarker_slug"] == "heart_rate"]
if len(hr) > 0:
    hourly_hr = hr.groupby("hour")["value"].agg(["mean", "std", "count"])
    print("\nHour  |  Avg HR  |  Samples")
    print("-" * 35)
    for hour in range(24):
        if hour in hourly_hr.index:
            row = hourly_hr.loc[hour]
            bar = "#" * int(row["mean"] / 5)
            print(f" {hour:02d}   |  {row['mean']:5.1f}   |  {int(row['count']):,}  {bar}")

    lowest_hr_hour = hourly_hr["mean"].idxmin()
    highest_hr_hour = hourly_hr["mean"].idxmax()
    print(f"\n>> Your heart rate is LOWEST at {lowest_hr_hour}:00 ({hourly_hr.loc[lowest_hr_hour, 'mean']:.1f} bpm)")
    print(f">> Your heart rate is HIGHEST at {highest_hr_hour}:00 ({hourly_hr.loc[highest_hr_hour, 'mean']:.1f} bpm)")

# ============================================
# 2. WEEKLY PATTERNS - Activity by Day
# ============================================
print("\n" + "=" * 60)
print("WEEKLY PATTERNS - Your Activity by Day of Week")
print("=" * 60)
steps = df[df["biomarker_slug"] == "steps"]
if len(steps) > 0:
    daily_steps = steps.groupby(["date", "day_of_week"])["value"].sum().reset_index()
    weekly_avg = daily_steps.groupby("day_of_week")["value"].mean()
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    print("\nDay        |  Avg Steps")
    print("-" * 35)
    for i, day in enumerate(days):
        if i in weekly_avg.index:
            bar = "#" * int(weekly_avg[i] / 500)
            print(f"{day:10} |  {weekly_avg[i]:,.0f}  {bar}")

    most_active_day = days[weekly_avg.idxmax()]
    least_active_day = days[weekly_avg.idxmin()]
    print(f"\n>> You're MOST active on {most_active_day}s ({weekly_avg.max():,.0f} steps)")
    print(f">> You're LEAST active on {least_active_day}s ({weekly_avg.min():,.0f} steps)")

# ============================================
# 3. LONG-TERM TRENDS - Resting HR Over Years
# ============================================
print("\n" + "=" * 60)
print("FITNESS TREND - Your Resting Heart Rate Over Time")
print("=" * 60)
rhr = df[df["biomarker_slug"] == "heart_rate_resting"]
if len(rhr) > 100:
    yearly_rhr = rhr.groupby("year")["value"].agg(["mean", "count"])
    print("\nYear  |  Avg RHR  |  Samples")
    print("-" * 35)
    for year in sorted(yearly_rhr.index):
        row = yearly_rhr.loc[year]
        if row["count"] > 10:
            print(f"{year}  |  {row['mean']:5.1f}    |  {int(row['count'])}")

    if len(yearly_rhr) > 1:
        first_year = yearly_rhr.index.min()
        last_year = yearly_rhr.index.max()
        change = yearly_rhr.loc[last_year, "mean"] - yearly_rhr.loc[first_year, "mean"]
        if change < -2:
            print(f"\n>> Your resting HR has DECREASED by {abs(change):.1f} bpm - sign of improved fitness!")
        elif change > 2:
            print(f"\n>> Your resting HR has INCREASED by {change:.1f} bpm over the years")
        else:
            print(f"\n>> Your resting HR has remained stable over the years")
else:
    print("Not enough resting heart rate data for trend analysis")

# ============================================
# 4. HRV ANALYSIS - Autonomic Health
# ============================================
print("\n" + "=" * 60)
print("AUTONOMIC HEALTH - Your HRV (SDNN) Analysis")
print("=" * 60)
hrv = df[df["biomarker_slug"] == "hrv_sdnn"]
if len(hrv) > 50:
    avg_hrv = hrv["value"].mean()
    std_hrv = hrv["value"].std()

    # HRV by hour (when is autonomic recovery best?)
    hourly_hrv = hrv.groupby("hour")["value"].mean()
    best_hrv_hour = hourly_hrv.idxmax()

    print(f"\nYour average HRV (SDNN): {avg_hrv:.1f} ± {std_hrv:.1f} ms")
    print(f"Your HRV is highest at {best_hrv_hour}:00 - this is when your body recovers best")

    # HRV trend over time
    monthly_hrv = hrv.groupby([hrv["time"].dt.to_period("M")])["value"].mean()
    if len(monthly_hrv) > 3:
        recent = monthly_hrv.tail(3).mean()
        older = monthly_hrv.head(3).mean()
        if recent > older * 1.1:
            print(">> Your HRV has been IMPROVING recently - good autonomic health!")
        elif recent < older * 0.9:
            print(">> Your HRV has been DECLINING recently - may indicate stress or fatigue")
else:
    print("Not enough HRV data for detailed analysis")

# ============================================
# 5. CORRELATION: Activity → Recovery
# ============================================
print("\n" + "=" * 60)
print("RECOVERY ANALYSIS - Does Activity Affect Your Recovery?")
print("=" * 60)

# Get daily totals
daily_steps_df = steps.groupby("date")["value"].sum().reset_index()
daily_steps_df.columns = ["date", "steps"]

daily_rhr = rhr.groupby("date")["value"].mean().reset_index()
daily_rhr.columns = ["date", "rhr"]

# Merge and shift to see next-day effect
merged = pd.merge(daily_steps_df, daily_rhr, on="date")
merged["next_day_rhr"] = merged["rhr"].shift(-1)

if len(merged) > 30:
    # Correlation between steps today and resting HR tomorrow
    corr = merged["steps"].corr(merged["next_day_rhr"])
    print(f"\nCorrelation between activity and next-day resting HR: {corr:.3f}")

    if corr < -0.1:
        print(">> More activity tends to LOWER your resting HR the next day (good recovery!)")
    elif corr > 0.1:
        print(">> More activity tends to RAISE your resting HR the next day (may indicate overtraining)")
    else:
        print(">> No strong relationship found between activity and next-day recovery")

# ============================================
# 6. ANOMALY DAYS
# ============================================
print("\n" + "=" * 60)
print("ANOMALY DETECTION - Your Unusual Days")
print("=" * 60)

hr_daily = hr.groupby("date")["value"].mean().reset_index()
hr_daily.columns = ["date", "hr"]

if len(hr_daily) > 30:
    mean_hr = hr_daily["hr"].mean()
    std_hr = hr_daily["hr"].std()
    hr_daily["z_score"] = (hr_daily["hr"] - mean_hr) / std_hr

    anomalies = hr_daily[abs(hr_daily["z_score"]) > 2].sort_values("z_score")

    print("\nDays with unusually LOW heart rate (possible rest/relaxation):")
    for _, row in anomalies[anomalies["z_score"] < -2].head(5).iterrows():
        print(f"  {row['date']}: {row['hr']:.1f} bpm (z={row['z_score']:.2f})")

    print("\nDays with unusually HIGH heart rate (possible stress/illness/intense exercise):")
    for _, row in anomalies[anomalies["z_score"] > 2].tail(5).iterrows():
        print(f"  {row['date']}: {row['hr']:.1f} bpm (z={row['z_score']:.2f})")

# ============================================
# 7. OXYGEN SATURATION PATTERNS
# ============================================
print("\n" + "=" * 60)
print("OXYGEN SATURATION - SpO2 Analysis")
print("=" * 60)
spo2 = df[df["biomarker_slug"] == "spo2"]
if len(spo2) > 50:
    avg_spo2 = spo2["value"].mean()
    min_spo2 = spo2["value"].min()
    low_readings = len(spo2[spo2["value"] < 95])

    print(f"\nYour average SpO2: {avg_spo2:.1f}%")
    print(f"Lowest recorded: {min_spo2:.1f}%")
    print(f"Readings below 95%: {low_readings} ({100*low_readings/len(spo2):.1f}%)")

    if avg_spo2 >= 96:
        print(">> Your oxygen saturation is in the healthy range")
else:
    print("Not enough SpO2 data for analysis")

print("\n" + "=" * 60)
print("SUMMARY - What We Can Derive From Your Data")
print("=" * 60)
print("""
With certainty, your data reveals:
1. Your personal circadian rhythm (peak/trough HR times)
2. Your weekly activity patterns
3. Long-term fitness trends (resting HR over years)
4. Autonomic health indicators (HRV patterns)
5. Recovery patterns (how activity affects next-day metrics)
6. Anomaly days worth investigating
7. Respiratory health indicators (SpO2)

These are YOUR patterns, not population averages.
""")
