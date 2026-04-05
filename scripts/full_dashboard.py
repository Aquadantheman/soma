#!/usr/bin/env python3
"""
Full Health Dashboard - Comprehensive analysis with computed features.
"""

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
import statistics
import sys
from pathlib import Path

from compute_features import (
    compute_recovery_score,
    compute_circadian_amplitude,
    compute_chronotype,
    compute_sleep_architecture,
    compute_stress_score,
    compute_mobility_score,
    compute_rolling_baseline,
)


def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")
    except:
        return None


def run_dashboard(path: Path):
    # Data collection
    daily = defaultdict(lambda: defaultdict(list))
    hourly = defaultdict(lambda: defaultdict(list))

    TYPE_MAP = {
        "HKQuantityTypeIdentifierHeartRate": ("heart_rate", 1.0),
        "HKQuantityTypeIdentifierRestingHeartRate": ("resting_hr", 1.0),
        "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("hrv", 1.0),
        "HKQuantityTypeIdentifierStepCount": ("steps", 1.0),
        "HKQuantityTypeIdentifierActiveEnergyBurned": ("active_cal", 1.0),
        "HKQuantityTypeIdentifierVO2Max": ("vo2max", 1.0),
        "HKQuantityTypeIdentifierWalkingSpeed": ("walking_speed", 1.0),
        "HKQuantityTypeIdentifierAppleWalkingSteadiness": ("walk_steadiness", 100.0),
        "HKQuantityTypeIdentifierWalkingAsymmetryPercentage": ("walk_asymmetry", 100.0),
        "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage": ("double_support", 100.0),
        "HKQuantityTypeIdentifierTimeInDaylight": ("daylight", 1.0),
        "HKQuantityTypeIdentifierHeadphoneAudioExposure": ("headphone_db", 1.0),
        "HKQuantityTypeIdentifierEnvironmentalAudioExposure": ("env_db", 1.0),
    }

    SLEEP_MAP = {
        "HKCategoryValueSleepAnalysisAsleepREM": "sleep_rem",
        "HKCategoryValueSleepAnalysisAsleepDeep": "sleep_deep",
        "HKCategoryValueSleepAnalysisAsleepCore": "sleep_core",
        "HKCategoryValueSleepAnalysisInBed": "sleep_in_bed",
    }

    print("Loading data...")
    for event, elem in ET.iterparse(str(path), events=("end",)):
        if elem.tag == "Record":
            record_type = elem.get("type")
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
                        # Calculate sleep midpoint for chronotype
                        midpoint = (date.hour * 60 + date.minute + dur / 2)
                        if midpoint >= 1440:
                            midpoint -= 1440
                        daily[day][SLEEP_MAP[value]].append(dur)
                        daily[day]["sleep_midpoint"].append(midpoint)

        elem.clear()

    # =========================================================================
    # COMPUTE DERIVED FEATURES
    # =========================================================================

    print("\n" + "=" * 70)
    print("SOMA HEALTH DASHBOARD")
    print("=" * 70)

    recent_days = sorted(daily.keys())[-90:]
    last_30 = sorted(daily.keys())[-30:]
    last_7 = sorted(daily.keys())[-7:]

    # --- HRV & RHR Baselines ---
    hrv_values = []
    rhr_values = []
    for day in last_30:
        if daily[day]["hrv"]:
            hrv_values.append(statistics.mean(daily[day]["hrv"]))
        if daily[day]["resting_hr"]:
            rhr_values.append(statistics.mean(daily[day]["resting_hr"]))

    hrv_baseline = compute_rolling_baseline(hrv_values, 7) if hrv_values else 50
    rhr_baseline = compute_rolling_baseline(rhr_values, 7) if rhr_values else 65

    # Current values (last 3 days average)
    recent_hrv = []
    recent_rhr = []
    for day in last_7[:3]:
        if daily[day]["hrv"]:
            recent_hrv.extend(daily[day]["hrv"])
        if daily[day]["resting_hr"]:
            recent_rhr.extend(daily[day]["resting_hr"])

    current_hrv = statistics.mean(recent_hrv) if recent_hrv else hrv_baseline
    current_rhr = statistics.mean(recent_rhr) if recent_rhr else rhr_baseline

    # --- RECOVERY SCORE ---
    print("\n" + "-" * 70)
    print("RECOVERY & READINESS")
    print("-" * 70)

    # Get recent sleep data
    sleep_eff = None
    sleep_hrs = None
    for day in last_7[:3]:
        rem = sum(daily[day].get("sleep_rem", []))
        deep = sum(daily[day].get("sleep_deep", []))
        core = sum(daily[day].get("sleep_core", []))
        in_bed = sum(daily[day].get("sleep_in_bed", []))
        total = rem + deep + core
        if total > 0 and in_bed > 0:
            sleep_eff = (total / in_bed) * 100
            sleep_hrs = total / 60
            break

    recovery_score, components = compute_recovery_score(
        current_hrv=current_hrv,
        hrv_baseline=hrv_baseline,
        current_rhr=current_rhr,
        rhr_baseline=rhr_baseline,
        sleep_efficiency=sleep_eff,
        sleep_duration_hrs=sleep_hrs,
    )

    print(f"\n  RECOVERY SCORE: {recovery_score:.0f}/100")
    print(f"  |- HRV Component:   {components['hrv']:.0f}/40  (current: {current_hrv:.1f} ms, baseline: {hrv_baseline:.1f} ms)")
    print(f"  |- RHR Component:   {components['rhr']:.0f}/30  (current: {current_rhr:.1f} bpm, baseline: {rhr_baseline:.1f} bpm)")
    print(f"  `- Sleep Component: {components['sleep']:.0f}/30")

    if recovery_score >= 80:
        rec = "EXCELLENT - Ready for high intensity"
    elif recovery_score >= 60:
        rec = "GOOD - Normal training recommended"
    elif recovery_score >= 40:
        rec = "MODERATE - Consider lighter activity"
    else:
        rec = "LOW - Prioritize rest and recovery"
    print(f"\n  Recommendation: {rec}")

    # --- STRESS SCORE ---
    # Estimate activity from recent steps
    recent_steps = []
    for day in last_7:
        if daily[day]["steps"]:
            recent_steps.append(sum(daily[day]["steps"]))
    activity_level = min(1.0, (statistics.mean(recent_steps) / 10000)) if recent_steps else 0.5

    stress_score, stress_status = compute_stress_score(
        current_hrv=current_hrv,
        hrv_baseline=hrv_baseline,
        current_rhr=current_rhr,
        rhr_baseline=rhr_baseline,
        activity_level=activity_level
    )

    print(f"\n  STRESS SCORE: {stress_score:.0f}/100 ({stress_status})")

    # --- CIRCADIAN RHYTHM ---
    print("\n" + "-" * 70)
    print("CIRCADIAN RHYTHM")
    print("-" * 70)

    # Extract just heart rate by hour
    hr_by_hour = {hour: data.get("heart_rate", []) for hour, data in hourly.items()}
    circadian = compute_circadian_amplitude(hr_by_hour)
    print(f"\n  Circadian Amplitude: {circadian['amplitude']:.1f} bpm ({circadian['status']})")
    print(f"  |- HR Nadir:  {circadian['acrophase_hour']:02d}:00 (lowest - typically deep sleep)")
    print(f"  `- HR Peak:   {circadian['bathyphase_hour']:02d}:00 (highest - peak activity)")

    # Chronotype
    midpoints = []
    for day in recent_days:
        if daily[day]["sleep_midpoint"]:
            midpoints.extend(daily[day]["sleep_midpoint"])

    if midpoints:
        chrono = compute_chronotype(midpoints)
        print(f"\n  Chronotype: {chrono['chronotype'].replace('_', ' ').title()}")
        print(f"  Average sleep midpoint: {chrono['avg_midpoint_time']}")

    # --- SLEEP ARCHITECTURE ---
    print("\n" + "-" * 70)
    print("SLEEP ARCHITECTURE (last 30 days)")
    print("-" * 70)

    total_rem = total_deep = total_core = 0
    for day in last_30:
        total_rem += sum(daily[day].get("sleep_rem", []))
        total_deep += sum(daily[day].get("sleep_deep", []))
        total_core += sum(daily[day].get("sleep_core", []))

    total_sleep = total_rem + total_deep + total_core
    if total_sleep > 0:
        arch = compute_sleep_architecture(total_rem, total_deep, total_core, total_sleep)
        print(f"\n  REM Sleep:   {arch['rem_pct']:5.1f}%  (target: 20-25%)")
        print(f"  Deep Sleep:  {arch['deep_pct']:5.1f}%  (target: 15-20%)")
        print(f"  Light Sleep: {arch['light_pct']:5.1f}%  (target: 50-60%)")

        if arch['issues']:
            print(f"\n  Issues detected:")
            for issue in arch['issues']:
                if issue == "low_rem":
                    print("    - Low REM: May affect memory consolidation")
                elif issue == "low_deep":
                    print("    - Low deep sleep: May affect physical recovery")

    # --- MOBILITY SCORE ---
    print("\n" + "-" * 70)
    print("MOBILITY & GAIT")
    print("-" * 70)

    # Get mobility metrics
    ws_vals = []
    wst_vals = []
    wa_vals = []
    ds_vals = []
    for day in recent_days:
        if daily[day]["walking_speed"]:
            ws_vals.extend(daily[day]["walking_speed"])
        if daily[day]["walk_steadiness"]:
            wst_vals.extend(daily[day]["walk_steadiness"])
        if daily[day]["walk_asymmetry"]:
            wa_vals.extend(daily[day]["walk_asymmetry"])
        if daily[day]["double_support"]:
            ds_vals.extend(daily[day]["double_support"])

    mobility_score, concerns = compute_mobility_score(
        walking_speed=statistics.mean(ws_vals) if ws_vals else None,
        walking_steadiness=statistics.mean(wst_vals) if wst_vals else None,
        walking_asymmetry=statistics.mean(wa_vals) if wa_vals else None,
        double_support=statistics.mean(ds_vals) if ds_vals else None,
    )

    print(f"\n  MOBILITY SCORE: {mobility_score:.0f}/100")
    if ws_vals:
        print(f"  |- Walking Speed: {statistics.mean(ws_vals):.2f} m/s")
    if wst_vals:
        print(f"  |- Steadiness: {statistics.mean(wst_vals):.0f}%")
    if wa_vals:
        print(f"  |- Asymmetry: {statistics.mean(wa_vals):.1f}%")
    if ds_vals:
        print(f"  `- Double Support: {statistics.mean(ds_vals):.1f}%")

    if concerns:
        print(f"\n  Concerns: {', '.join(concerns)}")

    # --- ENVIRONMENT ---
    print("\n" + "-" * 70)
    print("ENVIRONMENT & LIFESTYLE")
    print("-" * 70)

    # Daylight
    daylight_vals = []
    for day in last_30:
        if daily[day]["daylight"]:
            daylight_vals.append(sum(daily[day]["daylight"]))

    if daylight_vals:
        avg_daylight = statistics.mean(daylight_vals)
        print(f"\n  Daily Daylight: {avg_daylight:.0f} min {'(GOOD)' if avg_daylight >= 30 else '(LOW - aim for 30+ min)'}")

    # Audio exposure
    hp_vals = []
    env_vals = []
    for day in recent_days:
        if daily[day]["headphone_db"]:
            hp_vals.extend(daily[day]["headphone_db"])
        if daily[day]["env_db"]:
            env_vals.extend(daily[day]["env_db"])

    if hp_vals:
        avg_hp = statistics.mean(hp_vals)
        max_hp = max(hp_vals)
        status = "SAFE" if max_hp < 85 else "CAUTION" if max_hp < 100 else "WARNING"
        print(f"\n  Headphone Exposure: avg {avg_hp:.0f} dB, peak {max_hp:.0f} dB ({status})")

    # --- ACTIVITY SUMMARY ---
    print("\n" + "-" * 70)
    print("ACTIVITY SUMMARY (last 30 days)")
    print("-" * 70)

    steps_30 = []
    cal_30 = []
    for day in last_30:
        if daily[day]["steps"]:
            steps_30.append(sum(daily[day]["steps"]))
        if daily[day]["active_cal"]:
            cal_30.append(sum(daily[day]["active_cal"]))

    if steps_30:
        print(f"\n  Daily Steps: {statistics.mean(steps_30):,.0f} avg, {max(steps_30):,.0f} best")
    if cal_30:
        print(f"  Active Calories: {statistics.mean(cal_30):,.0f} kcal/day")

    # --- OVERALL HEALTH SCORE ---
    print("\n" + "=" * 70)
    print("OVERALL HEALTH SCORE")
    print("=" * 70)

    # Combine component scores
    scores = {
        "Recovery": recovery_score,
        "Mobility": mobility_score,
        "Stress (inv)": max(0, 100 - stress_score),  # Invert so higher is better
    }

    print("\n  Component Breakdown:")
    total = 0
    for name, score in scores.items():
        filled = int(score / 5)
        bar = "#" * filled + "-" * (20 - filled)
        print(f"    {name:15} [{bar}] {score:.0f}")
        total += score

    overall = total / len(scores)
    print(f"\n  OVERALL: {overall:.0f}/100")

    if overall >= 80:
        print("  Status: EXCELLENT")
    elif overall >= 60:
        print("  Status: GOOD")
    elif overall >= 40:
        print("  Status: FAIR")
    else:
        print("  Status: NEEDS ATTENTION")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    path = Path("apple_health_export/export.xml")
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])

    if not path.exists():
        print(f"Error: {path} not found")
        sys.exit(1)

    run_dashboard(path)
