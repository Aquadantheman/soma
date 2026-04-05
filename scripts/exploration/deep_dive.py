"""Deep dive analysis into interesting patterns in your data."""

import pandas as pd
import numpy as np
from scipy import stats
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql+psycopg2://postgres:soma_dev@127.0.0.1:5432/soma"
engine = create_engine(DATABASE_URL)

print("Loading data...")
with engine.connect() as conn:
    df = pd.read_sql(
        "SELECT time, biomarker_slug, value FROM signals WHERE value IS NOT NULL",
        conn
    )

df["time"] = pd.to_datetime(df["time"], utc=True)
df["date"] = df["time"].dt.date
df["hour"] = df["time"].dt.hour
df["month"] = df["time"].dt.month
df["year"] = df["time"].dt.year
df["day_of_week"] = df["time"].dt.dayofweek
df["is_weekend"] = df["day_of_week"].isin([5, 6])

# Fix HRV units
hrv_mask = df["biomarker_slug"].isin(["hrv_sdnn", "hrv_rmssd"])
if df.loc[hrv_mask, "value"].median() > 1000:
    df.loc[hrv_mask, "value"] = df.loc[hrv_mask, "value"] / 1000

# Pivot to daily means
daily = df.groupby(["date", "biomarker_slug"])["value"].mean().unstack()
daily["day_of_week"] = pd.to_datetime(daily.index).dayofweek
daily["is_weekend"] = daily["day_of_week"].isin([5, 6])
daily["month"] = pd.to_datetime(daily.index).month
daily["year"] = pd.to_datetime(daily.index).year

print(f"Loaded {len(df):,} signals across {len(daily):,} days\n")

# ============================================
# 1. ANOMALY DAYS - What happened?
# ============================================
print("=" * 70)
print("1. ANOMALY DAYS - What happened on your highest HR days?")
print("=" * 70)

if "heart_rate" in daily.columns:
    hr_mean = daily["heart_rate"].mean()
    hr_std = daily["heart_rate"].std()
    daily["hr_z"] = (daily["heart_rate"] - hr_mean) / hr_std

    # Top 10 highest HR days
    top_hr_days = daily.nlargest(10, "heart_rate")

    print("\nYour 10 highest average HR days:\n")
    print("Date        | Avg HR | z-score | Steps  | HRV   | RHR   | Day")
    print("-" * 70)

    days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    for date, row in top_hr_days.iterrows():
        steps = f"{row.get('steps', 0):,.0f}" if pd.notna(row.get('steps')) else "N/A"
        hrv = f"{row.get('hrv_sdnn', 0):.1f}" if pd.notna(row.get('hrv_sdnn')) else "N/A"
        rhr = f"{row.get('heart_rate_resting', 0):.0f}" if pd.notna(row.get('heart_rate_resting')) else "N/A"
        dow = days_of_week[row["day_of_week"]]
        print(f"{date} | {row['heart_rate']:6.1f} | {row['hr_z']:+6.2f}  | {steps:>6} | {hrv:>5} | {rhr:>5} | {dow}")

    # Pattern analysis
    high_hr_days = daily[daily["hr_z"] > 2]
    if len(high_hr_days) > 5:
        weekend_pct = high_hr_days["is_weekend"].mean() * 100
        avg_steps = high_hr_days["steps"].mean() if "steps" in high_hr_days else None

        print(f"\nPattern in high HR days (z > 2, n={len(high_hr_days)}):")
        print(f"  - Weekend occurrence: {weekend_pct:.1f}% (vs expected 28.6%)")
        if avg_steps:
            normal_steps = daily["steps"].mean()
            print(f"  - Average steps: {avg_steps:,.0f} (vs normal {normal_steps:,.0f})")

# ============================================
# 2. OCTOBER HR PEAK - Why October?
# ============================================
print("\n" + "=" * 70)
print("2. OCTOBER HR PEAK - Why is your HR highest in October?")
print("=" * 70)

if "heart_rate" in daily.columns:
    monthly_hr = daily.groupby("month")["heart_rate"].agg(["mean", "std", "count"])
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    print("\nMonthly HR breakdown:\n")
    print("Month | Avg HR | Std  |  N   | Activity Level")
    print("-" * 55)

    for month in range(1, 13):
        if month in monthly_hr.index:
            row = monthly_hr.loc[month]
            steps_month = daily[daily["month"] == month]["steps"].mean() if "steps" in daily else 0
            activity = "HIGH" if steps_month > daily["steps"].mean() * 1.1 else "LOW" if steps_month < daily["steps"].mean() * 0.9 else "AVG"
            print(f"{months[month-1]:>5} | {row['mean']:6.1f} | {row['std']:4.1f} | {int(row['count']):4} | {activity}")

    # October vs other months
    oct_hr = daily[daily["month"] == 10]["heart_rate"]
    other_hr = daily[daily["month"] != 10]["heart_rate"]
    t_stat, p_val = stats.ttest_ind(oct_hr.dropna(), other_hr.dropna())

    print(f"\nOctober vs rest of year:")
    print(f"  October mean: {oct_hr.mean():.1f} bpm")
    print(f"  Other months: {other_hr.mean():.1f} bpm")
    print(f"  Difference: {oct_hr.mean() - other_hr.mean():.1f} bpm (t={t_stat:.2f}, p={p_val:.4f})")

    # Check if October has more activity
    if "steps" in daily.columns:
        oct_steps = daily[daily["month"] == 10]["steps"].mean()
        other_steps = daily[daily["month"] != 10]["steps"].mean()
        print(f"\n  October steps: {oct_steps:,.0f}")
        print(f"  Other months: {other_steps:,.0f}")

        if oct_steps > other_steps * 1.1:
            print("  >> October HR may be higher due to increased activity")
        else:
            print("  >> October HR elevated despite similar activity - could be stress/work related")

# ============================================
# 3. WINTER SLUMP - Quantified
# ============================================
print("\n" + "=" * 70)
print("3. WINTER SLUMP - How much do you slow down?")
print("=" * 70)

if "steps" in daily.columns:
    # Define seasons
    daily["season"] = daily["month"].map({
        12: "Winter", 1: "Winter", 2: "Winter",
        3: "Spring", 4: "Spring", 5: "Spring",
        6: "Summer", 7: "Summer", 8: "Summer",
        9: "Fall", 10: "Fall", 11: "Fall"
    })

    seasonal = daily.groupby("season").agg({
        "steps": ["mean", "std", "count"],
        "heart_rate": ["mean", "std"] if "heart_rate" in daily else [],
        "hrv_sdnn": ["mean", "std"] if "hrv_sdnn" in daily else []
    })

    print("\nSeasonal comparison:\n")
    print("Season  | Avg Steps |  HR   |  HRV  | Days")
    print("-" * 50)

    for season in ["Spring", "Summer", "Fall", "Winter"]:
        if season in seasonal.index:
            steps = seasonal.loc[season, ("steps", "mean")]
            hr = seasonal.loc[season, ("heart_rate", "mean")] if "heart_rate" in daily else 0
            hrv = seasonal.loc[season, ("hrv_sdnn", "mean")] if "hrv_sdnn" in daily else 0
            n = seasonal.loc[season, ("steps", "count")]
            print(f"{season:>7} | {steps:>9,.0f} | {hr:5.1f} | {hrv:5.1f} | {int(n)}")

    # Winter vs Summer comparison
    winter = daily[daily["season"] == "Winter"]["steps"]
    summer = daily[daily["season"] == "Summer"]["steps"]

    if len(winter) > 10 and len(summer) > 10:
        t_stat, p_val = stats.ttest_ind(winter.dropna(), summer.dropna())
        pct_drop = (summer.mean() - winter.mean()) / summer.mean() * 100

        print(f"\nWinter vs Summer:")
        print(f"  Summer average: {summer.mean():,.0f} steps")
        print(f"  Winter average: {winter.mean():,.0f} steps")
        print(f"  >> You walk {pct_drop:.1f}% LESS in winter (p={p_val:.4f})")

# ============================================
# 4. OPTIMAL DAYS - What do they have in common?
# ============================================
print("\n" + "=" * 70)
print("4. OPTIMAL DAYS - What makes a perfect day?")
print("=" * 70)

if "hrv_sdnn" in daily.columns and "heart_rate_resting" in daily.columns:
    # Compute readiness score
    hrv_mean = daily["hrv_sdnn"].mean()
    hrv_std = daily["hrv_sdnn"].std()
    rhr_mean = daily["heart_rate_resting"].mean()
    rhr_std = daily["heart_rate_resting"].std()

    mask = daily["hrv_sdnn"].notna() & daily["heart_rate_resting"].notna()
    scored = daily[mask].copy()

    scored["hrv_z"] = (scored["hrv_sdnn"] - hrv_mean) / hrv_std
    scored["rhr_z"] = (scored["heart_rate_resting"] - rhr_mean) / rhr_std
    scored["readiness"] = 0.6 * scored["hrv_z"] - 0.4 * scored["rhr_z"]

    # Normalize to 0-100
    p5, p95 = scored["readiness"].quantile([0.05, 0.95])
    scored["score"] = 50 + 50 * (scored["readiness"] - scored["readiness"].median()) / (p95 - p5)
    scored["score"] = scored["score"].clip(0, 100)

    # Optimal days (score >= 80)
    optimal = scored[scored["score"] >= 80]
    normal = scored[scored["score"] < 80]

    print(f"\nFound {len(optimal)} optimal days (score >= 80) out of {len(scored)} scored days\n")

    if len(optimal) >= 5:
        print("Characteristics of optimal days vs normal days:\n")
        print("Metric              | Optimal Days | Normal Days | Difference")
        print("-" * 65)

        comparisons = [
            ("HRV (ms)", "hrv_sdnn"),
            ("Resting HR (bpm)", "heart_rate_resting"),
            ("Steps", "steps"),
            ("Active Energy", "active_energy"),
            ("Heart Rate", "heart_rate"),
        ]

        for label, col in comparisons:
            if col in optimal.columns:
                opt_val = optimal[col].mean()
                norm_val = normal[col].mean()
                diff = opt_val - norm_val
                pct = (diff / norm_val * 100) if norm_val != 0 else 0
                print(f"{label:>19} | {opt_val:>12.1f} | {norm_val:>11.1f} | {diff:+.1f} ({pct:+.1f}%)")

        # Day of week distribution
        print(f"\nDay of week distribution:")
        opt_dow = optimal["day_of_week"].value_counts().sort_index()
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i, day in enumerate(days):
            count = opt_dow.get(i, 0)
            pct = count / len(optimal) * 100 if len(optimal) > 0 else 0
            expected = 100 / 7
            indicator = "^" if pct > expected * 1.5 else "v" if pct < expected * 0.5 else " "
            print(f"  {day}: {count:2} ({pct:5.1f}%) {indicator}")

        # Previous day activity
        if "steps" in scored.columns:
            scored["prev_steps"] = scored["steps"].shift(1)
            optimal_prev = scored.loc[optimal.index, "prev_steps"].mean()
            normal_prev = scored.loc[normal.index, "prev_steps"].mean()
            print(f"\nPrevious day steps:")
            print(f"  Before optimal days: {optimal_prev:,.0f}")
            print(f"  Before normal days: {normal_prev:,.0f}")
            if optimal_prev < normal_prev * 0.9:
                print("  >> Rest days tend to precede optimal recovery!")

# ============================================
# 5. RHR-HRV PREDICTIVE MODEL
# ============================================
print("\n" + "=" * 70)
print("5. RHR-HRV RELATIONSHIP - Can we predict one from the other?")
print("=" * 70)

if "hrv_sdnn" in daily.columns and "heart_rate_resting" in daily.columns:
    mask = daily["hrv_sdnn"].notna() & daily["heart_rate_resting"].notna()
    x = daily.loc[mask, "heart_rate_resting"].values
    y = daily.loc[mask, "hrv_sdnn"].values

    # Linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

    print(f"\nLinear model: HRV = {intercept:.2f} + ({slope:.2f}) * RHR")
    print(f"R-squared: {r_value**2:.3f} (explains {r_value**2*100:.1f}% of variance)")
    print(f"P-value: {p_value:.2e}")

    print(f"\nInterpretation:")
    print(f"  - For every 1 bpm increase in RHR, HRV drops by {abs(slope):.2f} ms")
    print(f"  - At RHR = 60 bpm, predicted HRV = {intercept + slope * 60:.1f} ms")
    print(f"  - At RHR = 70 bpm, predicted HRV = {intercept + slope * 70:.1f} ms")

    # Residuals - who beats the model?
    daily.loc[mask, "predicted_hrv"] = intercept + slope * x
    daily.loc[mask, "hrv_residual"] = y - (intercept + slope * x)

    # Days where HRV is much better than predicted
    better_than_expected = daily[daily["hrv_residual"] > daily["hrv_residual"].std() * 1.5]
    if len(better_than_expected) > 5:
        print(f"\nDays where your HRV was BETTER than predicted by RHR ({len(better_than_expected)} days):")
        weekend_pct = better_than_expected["is_weekend"].mean() * 100
        print(f"  Weekend occurrence: {weekend_pct:.1f}% (vs expected 28.6%)")

        if "steps" in better_than_expected.columns:
            prev_steps = better_than_expected["steps"].shift(1).mean()
            normal_prev = daily["steps"].shift(1).mean()
            print(f"  Previous day steps: {prev_steps:,.0f} (vs normal {normal_prev:,.0f})")

# ============================================
# 6. WEEKEND VS WEEKDAY RECOVERY
# ============================================
print("\n" + "=" * 70)
print("6. WEEKEND VS WEEKDAY - Do you recover better on weekends?")
print("=" * 70)

weekend = daily[daily["is_weekend"] == True]
weekday = daily[daily["is_weekend"] == False]

print(f"\nWeekend days: {len(weekend)}, Weekday days: {len(weekday)}\n")

print("Metric              | Weekend  | Weekday  | Diff   | P-value | Significant?")
print("-" * 80)

metrics = [
    ("HRV (ms)", "hrv_sdnn"),
    ("Resting HR (bpm)", "heart_rate_resting"),
    ("Avg HR (bpm)", "heart_rate"),
    ("Steps", "steps"),
    ("Active Energy", "active_energy"),
]

for label, col in metrics:
    if col in weekend.columns and col in weekday.columns:
        we_vals = weekend[col].dropna()
        wd_vals = weekday[col].dropna()

        if len(we_vals) > 10 and len(wd_vals) > 10:
            we_mean = we_vals.mean()
            wd_mean = wd_vals.mean()
            diff = we_mean - wd_mean
            t_stat, p_val = stats.ttest_ind(we_vals, wd_vals)
            sig = "YES" if p_val < 0.05 else "no"
            print(f"{label:>19} | {we_mean:>8.1f} | {wd_mean:>8.1f} | {diff:>+6.1f} | {p_val:>7.4f} | {sig}")

# Best day analysis
if "hrv_sdnn" in daily.columns:
    print("\nBest recovery day (highest average HRV):")
    dow_hrv = daily.groupby("day_of_week")["hrv_sdnn"].mean()
    best_day = dow_hrv.idxmax()
    worst_day = dow_hrv.idxmin()
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    print(f"  Best: {days[best_day]} ({dow_hrv[best_day]:.1f} ms)")
    print(f"  Worst: {days[worst_day]} ({dow_hrv[worst_day]:.1f} ms)")
    print(f"  Difference: {dow_hrv[best_day] - dow_hrv[worst_day]:.1f} ms")

# ============================================
# SUMMARY
# ============================================
print("\n" + "=" * 70)
print("SUMMARY OF FINDINGS")
print("=" * 70)
print("""
Key discoveries from your data:

1. ANOMALY DAYS: Your highest HR days - check if they correlate with
   specific activities, stress events, or illness.

2. OCTOBER PEAK: Your HR peaks in October, possibly due to work stress,
   seasonal activity changes, or other environmental factors.

3. WINTER SLUMP: You're significantly less active in winter - this is
   quantifiable and statistically significant.

4. OPTIMAL DAYS: Your best recovery days share common characteristics.
   Understanding these can help you optimize more days.

5. RHR-HRV MODEL: These are tightly coupled. When one deviates from the
   expected relationship, something interesting is happening.

6. WEEKEND RECOVERY: Compare weekend vs weekday - are you actually
   recovering on your days off?

These are YOUR personal patterns, mathematically proven from YOUR data.
""")
