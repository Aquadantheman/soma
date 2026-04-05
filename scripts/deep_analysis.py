#!/usr/bin/env python3
"""Deep health analysis with correlations and patterns."""

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
import statistics
import sys
from pathlib import Path

def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")
    except:
        return None

def analyze_deep(path: Path):
    # Expanded data collection
    daily = defaultdict(lambda: defaultdict(list))
    hourly = defaultdict(lambda: defaultdict(list))

    # Expanded type map - capture everything useful
    TYPE_MAP = {
        # Cardiovascular
        "HKQuantityTypeIdentifierHeartRate": ("heart_rate", 1.0),
        "HKQuantityTypeIdentifierRestingHeartRate": ("resting_hr", 1.0),
        "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("hrv", 1.0),
        "HKQuantityTypeIdentifierWalkingHeartRateAverage": ("walking_hr", 1.0),
        "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute": ("hr_recovery", 1.0),
        "HKQuantityTypeIdentifierBloodPressureSystolic": ("bp_sys", 1.0),
        "HKQuantityTypeIdentifierBloodPressureDiastolic": ("bp_dia", 1.0),

        # Respiratory
        "HKQuantityTypeIdentifierOxygenSaturation": ("spo2", 100.0),
        "HKQuantityTypeIdentifierRespiratoryRate": ("resp_rate", 1.0),
        "HKQuantityTypeIdentifierVO2Max": ("vo2max", 1.0),

        # Activity
        "HKQuantityTypeIdentifierStepCount": ("steps", 1.0),
        "HKQuantityTypeIdentifierDistanceWalkingRunning": ("distance", 1.0),
        "HKQuantityTypeIdentifierDistanceCycling": ("cycling_dist", 1.0),
        "HKQuantityTypeIdentifierActiveEnergyBurned": ("active_cal", 1.0),
        "HKQuantityTypeIdentifierBasalEnergyBurned": ("basal_cal", 1.0),
        "HKQuantityTypeIdentifierAppleExerciseTime": ("exercise_min", 1.0),
        "HKQuantityTypeIdentifierAppleStandTime": ("stand_min", 1.0),
        "HKQuantityTypeIdentifierFlightsClimbed": ("flights", 1.0),

        # Mobility
        "HKQuantityTypeIdentifierWalkingSpeed": ("walking_speed", 1.0),
        "HKQuantityTypeIdentifierWalkingStepLength": ("step_length", 1.0),
        "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage": ("double_support", 100.0),
        "HKQuantityTypeIdentifierWalkingAsymmetryPercentage": ("walk_asymmetry", 100.0),
        "HKQuantityTypeIdentifierStairAscentSpeed": ("stair_up_speed", 1.0),
        "HKQuantityTypeIdentifierStairDescentSpeed": ("stair_down_speed", 1.0),
        "HKQuantityTypeIdentifierAppleWalkingSteadiness": ("walk_steadiness", 100.0),

        # Running
        "HKQuantityTypeIdentifierRunningSpeed": ("running_speed", 1.0),
        "HKQuantityTypeIdentifierRunningPower": ("running_power", 1.0),
        "HKQuantityTypeIdentifierRunningStrideLength": ("running_stride", 1.0),
        "HKQuantityTypeIdentifierRunningVerticalOscillation": ("running_bounce", 1.0),
        "HKQuantityTypeIdentifierRunningGroundContactTime": ("ground_contact", 1.0),

        # Body
        "HKQuantityTypeIdentifierBodyMass": ("weight", 0.453592),
        "HKQuantityTypeIdentifierBodyFatPercentage": ("body_fat", 100.0),
        "HKQuantityTypeIdentifierLeanBodyMass": ("lean_mass", 0.453592),
        "HKQuantityTypeIdentifierBodyMassIndex": ("bmi", 1.0),

        # Environment
        "HKQuantityTypeIdentifierTimeInDaylight": ("daylight_min", 1.0),
        "HKQuantityTypeIdentifierHeadphoneAudioExposure": ("headphone_db", 1.0),
        "HKQuantityTypeIdentifierEnvironmentalAudioExposure": ("env_noise_db", 1.0),

        # Nutrition (if available)
        "HKQuantityTypeIdentifierDietaryEnergyConsumed": ("calories_in", 1.0),
        "HKQuantityTypeIdentifierDietaryProtein": ("protein_g", 1.0),
        "HKQuantityTypeIdentifierDietaryCarbohydrates": ("carbs_g", 1.0),
        "HKQuantityTypeIdentifierDietaryFatTotal": ("fat_g", 1.0),
        "HKQuantityTypeIdentifierDietaryWater": ("water_ml", 1.0),
    }

    SLEEP_MAP = {
        "HKCategoryValueSleepAnalysisAsleepREM": "sleep_rem",
        "HKCategoryValueSleepAnalysisAsleepDeep": "sleep_deep",
        "HKCategoryValueSleepAnalysisAsleepCore": "sleep_core",
        "HKCategoryValueSleepAnalysisInBed": "sleep_in_bed",
        "HKCategoryValueSleepAnalysisAwake": "sleep_awake",
    }

    # Track all types seen
    all_types = defaultdict(int)

    print("Parsing all data (this takes a minute)...")
    for event, elem in ET.iterparse(str(path), events=("end",)):
        if elem.tag == "Record":
            record_type = elem.get("type")
            all_types[record_type] += 1
            date = parse_date(elem.get("startDate"))

            if date and record_type in TYPE_MAP:
                slug, conv = TYPE_MAP[record_type]
                try:
                    value = float(elem.get("value", 0)) * conv
                    day = date.strftime("%Y-%m-%d")
                    hour = date.hour
                    daily[day][slug].append(value)
                    hourly[hour][slug].append(value)
                except:
                    pass

            # Sleep
            if record_type == "HKCategoryTypeIdentifierSleepAnalysis":
                value = elem.get("value")
                if value in SLEEP_MAP and date:
                    end = parse_date(elem.get("endDate"))
                    if end:
                        dur = (end - date).total_seconds() / 60
                        day = date.strftime("%Y-%m-%d")
                        daily[day][SLEEP_MAP[value]].append(dur)

        elem.clear()

    # === CIRCADIAN ANALYSIS ===
    print("\n" + "=" * 70)
    print("CIRCADIAN RHYTHM ANALYSIS")
    print("=" * 70)

    print("\nHeart Rate by Hour of Day:")
    hr_by_hour = []
    for hour in range(24):
        if hourly[hour]["heart_rate"]:
            avg = statistics.mean(hourly[hour]["heart_rate"])
            hr_by_hour.append((hour, avg))
            bar = "#" * int((avg - 50) / 2)
            print(f"  {hour:02d}:00  {avg:5.1f} bpm {bar}")

    if hr_by_hour:
        min_hr = min(hr_by_hour, key=lambda x: x[1])
        max_hr = max(hr_by_hour, key=lambda x: x[1])
        print(f"\n  Lowest: {min_hr[0]:02d}:00 ({min_hr[1]:.1f} bpm) - likely deep sleep")
        print(f"  Highest: {max_hr[0]:02d}:00 ({max_hr[1]:.1f} bpm) - peak activity")
        print(f"  Circadian amplitude: {max_hr[1] - min_hr[1]:.1f} bpm")

    # HRV by hour
    print("\nHRV by Hour of Day:")
    for hour in range(24):
        if hourly[hour]["hrv"]:
            avg = statistics.mean(hourly[hour]["hrv"])
            bar = "#" * int(avg / 3)
            print(f"  {hour:02d}:00  {avg:5.1f} ms {bar}")

    # === WEEKLY PATTERNS ===
    print("\n" + "=" * 70)
    print("WEEKLY PATTERNS")
    print("=" * 70)

    weekday_data = defaultdict(lambda: defaultdict(list))
    for day_str, data in daily.items():
        try:
            dt = datetime.strptime(day_str, "%Y-%m-%d")
            weekday = dt.strftime("%A")
            for metric, values in data.items():
                weekday_data[weekday][metric].extend(values)
        except:
            pass

    days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    print("\nSteps by Day of Week:")
    for day in days_order:
        if weekday_data[day]["steps"]:
            # Sum steps per day, then average
            total = sum(weekday_data[day]["steps"])
            count = len([d for d, data in daily.items()
                        if datetime.strptime(d, "%Y-%m-%d").strftime("%A") == day
                        and data["steps"]])
            if count > 0:
                avg = total / count
                bar = "#" * int(avg / 500)
                print(f"  {day:9} {avg:8,.0f} {bar}")

    print("\nResting HR by Day of Week:")
    for day in days_order:
        if weekday_data[day]["resting_hr"]:
            avg = statistics.mean(weekday_data[day]["resting_hr"])
            print(f"  {day:9} {avg:5.1f} bpm")

    # === CORRELATIONS ===
    print("\n" + "=" * 70)
    print("CORRELATION ANALYSIS")
    print("=" * 70)

    def pearson(x, y):
        if len(x) < 10 or len(x) != len(y):
            return None
        n = len(x)
        mx, my = sum(x)/n, sum(y)/n
        sx = (sum((xi-mx)**2 for xi in x) / n) ** 0.5
        sy = (sum((yi-my)**2 for yi in y) / n) ** 0.5
        if sx == 0 or sy == 0:
            return None
        return sum((xi-mx)*(yi-my) for xi, yi in zip(x, y)) / (n * sx * sy)

    # Build daily aggregates
    days_list = sorted(daily.keys())[-365:]  # Last year

    metrics_daily = defaultdict(list)
    valid_days = []
    for day in days_list:
        has_data = False
        day_vals = {}

        for metric in ["steps", "resting_hr", "hrv", "active_cal", "sleep_deep", "sleep_rem"]:
            if daily[day][metric]:
                if metric == "steps":
                    day_vals[metric] = sum(daily[day][metric])
                else:
                    day_vals[metric] = statistics.mean(daily[day][metric])
                has_data = True
            else:
                day_vals[metric] = None

        if has_data:
            valid_days.append(day)
            for k, v in day_vals.items():
                metrics_daily[k].append(v)

    # Calculate correlations
    correlations = []
    pairs = [
        ("steps", "resting_hr", "Steps vs Resting HR"),
        ("steps", "hrv", "Steps vs HRV"),
        ("sleep_deep", "resting_hr", "Deep Sleep vs Resting HR"),
        ("sleep_deep", "hrv", "Deep Sleep vs HRV"),
        ("active_cal", "hrv", "Active Calories vs HRV"),
    ]

    print("\nKey Correlations (last 365 days):")
    for m1, m2, label in pairs:
        x = [v for v in metrics_daily[m1] if v is not None]
        y = [metrics_daily[m2][i] for i, v in enumerate(metrics_daily[m1]) if v is not None and metrics_daily[m2][i] is not None]
        x = [metrics_daily[m1][i] for i, v in enumerate(metrics_daily[m1]) if v is not None and metrics_daily[m2][i] is not None]

        if len(x) >= 10:
            r = pearson(x, y)
            if r is not None:
                direction = "+" if r > 0 else ""
                strength = "strong" if abs(r) > 0.5 else "moderate" if abs(r) > 0.3 else "weak"
                print(f"  {label:30} r = {direction}{r:.3f} ({strength})")

    # === MOBILITY ANALYSIS ===
    print("\n" + "=" * 70)
    print("MOBILITY & GAIT ANALYSIS")
    print("=" * 70)

    recent = sorted(daily.keys())[-90:]

    mobility_metrics = ["walking_speed", "step_length", "double_support", "walk_asymmetry", "walk_steadiness"]

    for metric in mobility_metrics:
        values = []
        for day in recent:
            if daily[day][metric]:
                values.extend(daily[day][metric])

        if values:
            avg = statistics.mean(values)

            if metric == "walking_speed":
                print(f"\nWalking Speed: {avg:.2f} m/s ({avg * 2.237:.1f} mph)")
                if avg > 1.2:
                    print("  Status: EXCELLENT (associated with longevity)")
                elif avg > 1.0:
                    print("  Status: GOOD")
                elif avg > 0.8:
                    print("  Status: FAIR")
                else:
                    print("  Status: SLOW (mobility concern)")

            elif metric == "step_length":
                print(f"\nStep Length: {avg:.1f} cm")
                # Typical is 60-80cm
                if avg > 70:
                    print("  Status: GOOD stride length")
                elif avg > 50:
                    print("  Status: NORMAL")
                else:
                    print("  Status: SHORT (may indicate mobility issues)")

            elif metric == "double_support":
                print(f"\nDouble Support Time: {avg:.1f}%")
                # Lower is better, typical 20-40%
                if avg < 25:
                    print("  Status: EXCELLENT balance")
                elif avg < 35:
                    print("  Status: GOOD")
                else:
                    print("  Status: ELEVATED (balance/stability concern)")

            elif metric == "walk_asymmetry":
                print(f"\nWalking Asymmetry: {avg:.1f}%")
                if avg < 5:
                    print("  Status: SYMMETRIC gait")
                elif avg < 10:
                    print("  Status: MILD asymmetry")
                else:
                    print("  Status: NOTABLE asymmetry (injury risk)")

            elif metric == "walk_steadiness":
                print(f"\nWalking Steadiness: {avg:.0f}%")
                if avg > 90:
                    print("  Status: VERY STABLE")
                elif avg > 70:
                    print("  Status: STABLE")
                else:
                    print("  Status: LOW (fall risk)")

    # === RUNNING METRICS ===
    print("\n" + "=" * 70)
    print("RUNNING BIOMECHANICS")
    print("=" * 70)

    running_metrics = {
        "running_speed": ("Running Speed", "m/s"),
        "running_power": ("Running Power", "W"),
        "running_stride": ("Stride Length", "m"),
        "running_bounce": ("Vertical Oscillation", "cm"),
        "ground_contact": ("Ground Contact Time", "ms"),
    }

    for metric, (label, unit) in running_metrics.items():
        values = []
        for day in recent:
            if daily[day][metric]:
                values.extend(daily[day][metric])

        if values:
            avg = statistics.mean(values)
            print(f"  {label}: {avg:.2f} {unit}")

    # === ENVIRONMENT & LIFESTYLE ===
    print("\n" + "=" * 70)
    print("ENVIRONMENT & LIFESTYLE")
    print("=" * 70)

    # Daylight exposure
    daylight_vals = []
    for day in recent:
        if daily[day]["daylight_min"]:
            daylight_vals.append(sum(daily[day]["daylight_min"]))

    if daylight_vals:
        avg = statistics.mean(daylight_vals)
        print(f"\nDaily Daylight Exposure: {avg:.0f} minutes")
        if avg >= 30:
            print("  Status: GOOD (supports circadian rhythm)")
        else:
            print("  Status: LOW (aim for 30+ min outdoor light)")

    # Audio exposure
    headphone_vals = []
    for day in recent:
        if daily[day]["headphone_db"]:
            headphone_vals.extend(daily[day]["headphone_db"])

    if headphone_vals:
        avg = statistics.mean(headphone_vals)
        max_db = max(headphone_vals)
        print(f"\nHeadphone Audio Exposure:")
        print(f"  Average: {avg:.0f} dB")
        print(f"  Peak: {max_db:.0f} dB")
        if max_db > 85:
            print("  WARNING: Prolonged exposure >85dB risks hearing damage")

    # === NUTRITION (if available) ===
    nutrition_metrics = ["calories_in", "protein_g", "carbs_g", "fat_g", "water_ml"]
    has_nutrition = any(daily[day][m] for day in recent for m in nutrition_metrics)

    if has_nutrition:
        print("\n" + "=" * 70)
        print("NUTRITION TRACKING")
        print("=" * 70)

        for metric in nutrition_metrics:
            values = []
            for day in recent:
                if daily[day][metric]:
                    values.append(sum(daily[day][metric]))

            if values:
                avg = statistics.mean(values)
                label = metric.replace("_", " ").title()
                print(f"  {label}: {avg:.0f}")

    # === UNMAPPED TYPES ANALYSIS ===
    print("\n" + "=" * 70)
    print("ADDITIONAL DATA SOURCES AVAILABLE")
    print("=" * 70)

    # Filter to types not in our map
    unmapped = {k: v for k, v in all_types.items()
                if k not in TYPE_MAP
                and not k.startswith("HKCategoryType")
                and v > 100}

    print("\nUnmapped Apple Health types with significant data:")
    for t, count in sorted(unmapped.items(), key=lambda x: -x[1])[:15]:
        short = t.replace("HKQuantityTypeIdentifier", "")
        print(f"  {short:45} {count:>8,} records")

    # === RECOMMENDATIONS ===
    print("\n" + "=" * 70)
    print("RECOMMENDED NEW BIOMARKERS TO ADD")
    print("=" * 70)

    recommendations = [
        ("HeartRateRecoveryOneMinute", "HR Recovery", "Cardiac fitness - how fast HR drops after exercise"),
        ("WalkingHeartRateAverage", "Walking HR", "Cardiovascular efficiency during light activity"),
        ("AppleSleepingBreathingDisturbances", "Breathing Disturbances", "Proxy for sleep apnea (AHI)"),
        ("RunningPower", "Running Power", "Metabolic efficiency while running"),
        ("PhysicalEffort", "Physical Effort", "Apple's activity intensity metric"),
        ("EnvironmentalAudioExposure", "Noise Exposure", "Environmental stressor tracking"),
        ("AppleWalkingSteadiness", "Walking Steadiness", "Fall risk assessment"),
    ]

    print("\nHigh-value biomarkers to add:")
    for apple_type, name, reason in recommendations:
        if f"HKQuantityTypeIdentifier{apple_type}" in all_types or apple_type in str(all_types):
            count = all_types.get(f"HKQuantityTypeIdentifier{apple_type}",
                                  all_types.get(f"HKCategoryTypeIdentifier{apple_type}", 0))
            if count > 0:
                print(f"\n  {name}")
                print(f"    Apple type: {apple_type}")
                print(f"    Records: {count:,}")
                print(f"    Value: {reason}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    path = Path("apple_health_export/export.xml")
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])

    analyze_deep(path)
