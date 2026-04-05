#!/usr/bin/env python3
"""Comprehensive health analysis from Apple Health data."""

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
import statistics
import sys
from pathlib import Path

def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")
    except:
        return None

def analyze(path: Path):
    # Data structures
    daily_data = defaultdict(lambda: defaultdict(list))
    monthly_data = defaultdict(lambda: defaultdict(list))
    yearly_data = defaultdict(lambda: defaultdict(list))

    TYPE_MAP = {
        "HKQuantityTypeIdentifierHeartRate": ("heart_rate", 1.0),
        "HKQuantityTypeIdentifierRestingHeartRate": ("resting_hr", 1.0),
        "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("hrv", 1.0),
        "HKQuantityTypeIdentifierStepCount": ("steps", 1.0),
        "HKQuantityTypeIdentifierActiveEnergyBurned": ("active_cal", 1.0),
        "HKQuantityTypeIdentifierVO2Max": ("vo2max", 1.0),
        "HKQuantityTypeIdentifierBodyMass": ("weight", 0.453592),
        "HKQuantityTypeIdentifierOxygenSaturation": ("spo2", 100.0),
        "HKQuantityTypeIdentifierWalkingSpeed": ("walking_speed", 1.0),
        "HKQuantityTypeIdentifierBloodPressureSystolic": ("bp_sys", 1.0),
        "HKQuantityTypeIdentifierBloodPressureDiastolic": ("bp_dia", 1.0),
    }

    SLEEP_MAP = {
        "HKCategoryValueSleepAnalysisAsleepREM": "rem",
        "HKCategoryValueSleepAnalysisAsleepDeep": "deep",
        "HKCategoryValueSleepAnalysisAsleepCore": "core",
        "HKCategoryValueSleepAnalysisInBed": "in_bed",
    }

    print("Parsing data...")
    for event, elem in ET.iterparse(str(path), events=("end",)):
        if elem.tag == "Record":
            record_type = elem.get("type")
            date = parse_date(elem.get("startDate"))

            if date and record_type in TYPE_MAP:
                slug, conv = TYPE_MAP[record_type]
                try:
                    value = float(elem.get("value", 0)) * conv
                    day = date.strftime("%Y-%m-%d")
                    month = date.strftime("%Y-%m")
                    year = date.strftime("%Y")
                    daily_data[day][slug].append(value)
                    monthly_data[month][slug].append(value)
                    yearly_data[year][slug].append(value)
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
                        month = date.strftime("%Y-%m")
                        daily_data[day][f"sleep_{SLEEP_MAP[value]}"].append(dur)
                        monthly_data[month][f"sleep_{SLEEP_MAP[value]}"].append(dur)

        elem.clear()

    print("=" * 70)
    print("COMPREHENSIVE HEALTH ANALYSIS")
    print("=" * 70)

    # Recent trends (last 90 days)
    recent_days = sorted(daily_data.keys())[-90:]
    print(f"\nData range: {min(daily_data.keys())} to {max(daily_data.keys())} ({len(daily_data)} days)")

    # === CARDIOVASCULAR ===
    print("\n" + "=" * 70)
    print("CARDIOVASCULAR HEALTH")
    print("=" * 70)

    recent_rhr = []
    for day in recent_days:
        if daily_data[day]["resting_hr"]:
            recent_rhr.extend(daily_data[day]["resting_hr"])

    if recent_rhr:
        avg_rhr = statistics.mean(recent_rhr)
        print(f"\nResting Heart Rate (last 90 days):")
        print(f"  Current avg: {avg_rhr:.1f} bpm")
        print(f"  Range: {min(recent_rhr):.0f} - {max(recent_rhr):.0f} bpm")

        if avg_rhr < 50:
            status = "ATHLETIC (excellent cardiovascular conditioning)"
        elif avg_rhr < 60:
            status = "EXCELLENT"
        elif avg_rhr < 70:
            status = "GOOD"
        elif avg_rhr < 80:
            status = "AVERAGE"
        else:
            status = "ELEVATED (consider lifestyle factors)"
        print(f"  Status: {status}")

    # HRV Analysis
    recent_hrv = []
    for day in recent_days:
        if daily_data[day]["hrv"]:
            recent_hrv.extend(daily_data[day]["hrv"])

    if recent_hrv:
        avg_hrv = statistics.mean(recent_hrv)
        print(f"\nHeart Rate Variability (SDNN):")
        print(f"  Current avg: {avg_hrv:.1f} ms")
        print(f"  Range: {min(recent_hrv):.1f} - {max(recent_hrv):.1f} ms")

        if avg_hrv > 100:
            status = "EXCELLENT (high parasympathetic tone)"
        elif avg_hrv > 50:
            status = "GOOD (healthy autonomic balance)"
        elif avg_hrv > 30:
            status = "MODERATE (some stress adaptation)"
        else:
            status = "LOW (chronic stress/recovery needed)"
        print(f"  Status: {status}")

    # Blood Pressure
    recent_bp_sys = []
    recent_bp_dia = []
    for day in recent_days:
        if daily_data[day]["bp_sys"]:
            recent_bp_sys.extend(daily_data[day]["bp_sys"])
        if daily_data[day]["bp_dia"]:
            recent_bp_dia.extend(daily_data[day]["bp_dia"])

    if recent_bp_sys and recent_bp_dia:
        avg_sys = statistics.mean(recent_bp_sys)
        avg_dia = statistics.mean(recent_bp_dia)
        print(f"\nBlood Pressure:")
        print(f"  Average: {avg_sys:.0f}/{avg_dia:.0f} mmHg")

        if avg_sys < 120 and avg_dia < 80:
            status = "NORMAL"
        elif avg_sys < 130 and avg_dia < 80:
            status = "ELEVATED"
        elif avg_sys < 140 or avg_dia < 90:
            status = "STAGE 1 HYPERTENSION"
        else:
            status = "STAGE 2 HYPERTENSION"
        print(f"  Classification: {status}")

    # === VO2 MAX ===
    print("\n" + "=" * 70)
    print("CARDIORESPIRATORY FITNESS")
    print("=" * 70)

    vo2_by_year = {}
    for year, data in sorted(yearly_data.items()):
        if data["vo2max"]:
            vo2_by_year[year] = statistics.mean(data["vo2max"])

    if vo2_by_year:
        print("\nVO2 Max Trend:")
        for year, val in vo2_by_year.items():
            bar = "#" * int(val / 2)
            print(f"  {year}: {val:.1f} mL/kg/min {bar}")

        latest = list(vo2_by_year.values())[-1]
        if latest >= 50:
            status = "SUPERIOR (top 5%)"
        elif latest >= 42:
            status = "EXCELLENT (top 20%)"
        elif latest >= 35:
            status = "GOOD (above average)"
        elif latest >= 30:
            status = "FAIR"
        else:
            status = "NEEDS IMPROVEMENT"
        print(f"  Status: {status}")

    # === ACTIVITY ===
    print("\n" + "=" * 70)
    print("ACTIVITY LEVELS")
    print("=" * 70)

    recent_steps = []
    recent_cal = []
    for day in recent_days:
        if daily_data[day]["steps"]:
            recent_steps.append(sum(daily_data[day]["steps"]))
        if daily_data[day]["active_cal"]:
            recent_cal.append(sum(daily_data[day]["active_cal"]))

    if recent_steps:
        avg_steps = statistics.mean(recent_steps)
        print(f"\nDaily Steps (last 90 days):")
        print(f"  Average: {avg_steps:,.0f} steps/day")
        print(f"  Best day: {max(recent_steps):,.0f} steps")

        if avg_steps >= 10000:
            status = "VERY ACTIVE (exceeds 10k target)"
        elif avg_steps >= 7500:
            status = "ACTIVE"
        elif avg_steps >= 5000:
            status = "MODERATE"
        else:
            status = "SEDENTARY (aim for 7,500+ steps)"
        print(f"  Status: {status}")

    if recent_cal:
        print(f"\nActive Calories:")
        print(f"  Average: {statistics.mean(recent_cal):,.0f} kcal/day")

    # === SLEEP ===
    print("\n" + "=" * 70)
    print("SLEEP ARCHITECTURE")
    print("=" * 70)

    recent_months = sorted(monthly_data.keys())[-6:]
    sleep_totals = {"rem": [], "deep": [], "core": [], "in_bed": []}

    for month in recent_months:
        for stage in sleep_totals:
            if monthly_data[month][f"sleep_{stage}"]:
                sleep_totals[stage].extend(monthly_data[month][f"sleep_{stage}"])

    if any(sleep_totals.values()):
        print("\nSleep Stage Distribution (last 6 months):")

        total_rem = sum(sleep_totals["rem"]) if sleep_totals["rem"] else 0
        total_deep = sum(sleep_totals["deep"]) if sleep_totals["deep"] else 0
        total_core = sum(sleep_totals["core"]) if sleep_totals["core"] else 0
        total_sleep = total_rem + total_deep + total_core

        if total_sleep > 0:
            rem_pct = (total_rem / total_sleep) * 100
            deep_pct = (total_deep / total_sleep) * 100
            core_pct = (total_core / total_sleep) * 100

            print(f"  REM Sleep:   {rem_pct:5.1f}% (target: 20-25%)")
            print(f"  Deep Sleep:  {deep_pct:5.1f}% (target: 15-20%)")
            print(f"  Light Sleep: {core_pct:5.1f}% (target: 50-60%)")

            issues = []
            if rem_pct < 15:
                issues.append("Low REM (affects memory consolidation)")
            if deep_pct < 10:
                issues.append("Low Deep sleep (affects physical recovery)")

            if issues:
                print(f"\n  Concerns:")
                for issue in issues:
                    print(f"    - {issue}")
            else:
                print(f"\n  Status: HEALTHY sleep architecture")

    # === BODY COMPOSITION ===
    print("\n" + "=" * 70)
    print("BODY COMPOSITION")
    print("=" * 70)

    weight_by_month = {}
    for month, data in sorted(monthly_data.items())[-24:]:
        if data["weight"]:
            weight_by_month[month] = statistics.mean(data["weight"])

    if weight_by_month:
        months = list(weight_by_month.keys())
        weights = list(weight_by_month.values())

        print(f"\nWeight Trend (last 2 years):")
        print(f"  Current: {weights[-1]:.1f} kg ({weights[-1] * 2.205:.1f} lbs)")

        if len(weights) >= 12:
            print(f"  12 months ago: {weights[-12]:.1f} kg")
            change = weights[-1] - weights[-12]
            direction = "+" if change > 0 else "" if change < 0 else ""
            print(f"  Change: {direction}{change:.1f} kg")

    # === TRENDS ANALYSIS ===
    print("\n" + "=" * 70)
    print("TRENDS ANALYSIS")
    print("=" * 70)

    # RHR trend over years
    rhr_by_year = {}
    for year, data in sorted(yearly_data.items()):
        if data["resting_hr"]:
            rhr_by_year[year] = statistics.mean(data["resting_hr"])

    if len(rhr_by_year) >= 2:
        print("\nResting HR by Year:")
        for year, val in rhr_by_year.items():
            print(f"  {year}: {val:.1f} bpm")

        years = list(rhr_by_year.keys())
        first_val = rhr_by_year[years[0]]
        last_val = rhr_by_year[years[-1]]
        if last_val < first_val:
            print(f"  Trend: IMPROVING (down {first_val - last_val:.1f} bpm)")
        elif last_val > first_val:
            print(f"  Trend: DECLINING (up {last_val - first_val:.1f} bpm)")

    # === OVERALL SCORE ===
    print("\n" + "=" * 70)
    print("OVERALL ASSESSMENT")
    print("=" * 70)

    scores = []
    if recent_rhr:
        rhr_score = max(0, min(100, 100 - (statistics.mean(recent_rhr) - 50) * 2))
        scores.append(("Resting HR", rhr_score))

    if recent_hrv:
        hrv_score = max(0, min(100, statistics.mean(recent_hrv) * 1.5))
        scores.append(("HRV", hrv_score))

    if vo2_by_year:
        vo2_score = max(0, min(100, (list(vo2_by_year.values())[-1] - 20) * 2.5))
        scores.append(("VO2 Max", vo2_score))

    if recent_steps:
        steps_score = max(0, min(100, statistics.mean(recent_steps) / 100))
        scores.append(("Activity", steps_score))

    if scores:
        print("\nComponent Scores:")
        for name, score in scores:
            filled = int(score / 5)
            empty = 20 - filled
            bar = "#" * filled + "-" * empty
            print(f"  {name:12} [{bar}] {score:.0f}/100")

        overall = statistics.mean([s for _, s in scores])
        print(f"\n  OVERALL HEALTH SCORE: {overall:.0f}/100")

        if overall >= 80:
            assessment = "EXCELLENT - Maintain current habits"
        elif overall >= 60:
            assessment = "GOOD - Minor improvements possible"
        elif overall >= 40:
            assessment = "FAIR - Focus on weak areas"
        else:
            assessment = "NEEDS ATTENTION"
        print(f"  Assessment: {assessment}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    path = Path("apple_health_export/export.xml")
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])

    if not path.exists():
        print(f"Error: {path} not found")
        sys.exit(1)

    analyze(path)
