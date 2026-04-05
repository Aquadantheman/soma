#!/usr/bin/env python3
"""
Analyze Apple Health export without database dependency.

This script samples the export.xml to show:
1. What biomarker types are present
2. Date range of data
3. Sample values with validation checks
4. Statistics by category
"""

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys

# Mapping from Apple Health types to Soma biomarkers
APPLE_TYPE_MAP = {
    # Autonomic
    "HKQuantityTypeIdentifierHeartRate": ("heart_rate", 1.0, "bpm"),
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("hrv_sdnn", 1.0, "ms"),  # Apple stores in ms already
    "HKQuantityTypeIdentifierRestingHeartRate": ("heart_rate_resting", 1.0, "bpm"),
    "HKQuantityTypeIdentifierOxygenSaturation": ("spo2", 100.0, "%"),  # ratio -> pct
    "HKQuantityTypeIdentifierRespiratoryRate": ("respiratory_rate", 1.0, "brpm"),

    # Activity
    "HKQuantityTypeIdentifierStepCount": ("steps", 1.0, "count"),
    "HKQuantityTypeIdentifierActiveEnergyBurned": ("active_energy", 1.0, "kcal"),
    "HKQuantityTypeIdentifierBasalEnergyBurned": ("basal_energy", 1.0, "kcal"),
    "HKQuantityTypeIdentifierAppleExerciseTime": ("exercise_time", 1.0, "min"),
    "HKQuantityTypeIdentifierAppleStandTime": ("stand_time", 1.0, "min"),
    "HKQuantityTypeIdentifierFlightsClimbed": ("flights_climbed", 1.0, "count"),
    "HKQuantityTypeIdentifierDistanceWalkingRunning": ("distance_walking_running", 1000.0, "m"),  # km -> m

    # Mobility
    "HKQuantityTypeIdentifierWalkingSpeed": ("walking_speed", 1.0, "m/s"),
    "HKQuantityTypeIdentifierWalkingStepLength": ("walking_step_length", 1.0, "m"),
    "HKQuantityTypeIdentifierWalkingAsymmetryPercentage": ("walking_asymmetry", 1.0, "%"),
    "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage": ("walking_double_support", 1.0, "%"),

    # Circadian
    "HKQuantityTypeIdentifierTimeInDaylight": ("time_in_daylight", 1.0, "min"),

    # Fitness
    "HKQuantityTypeIdentifierVO2Max": ("vo2_max", 1.0, "mL/kg/min"),

    # Body Composition
    "HKQuantityTypeIdentifierBodyMass": ("body_mass", 0.453592, "kg"),  # lb -> kg
    "HKQuantityTypeIdentifierBodyFatPercentage": ("body_fat_percentage", 100.0, "%"),
    "HKQuantityTypeIdentifierLeanBodyMass": ("lean_body_mass", 0.453592, "kg"),
    "HKQuantityTypeIdentifierBodyMassIndex": ("body_mass_index", 1.0, "kg/m2"),
    "HKQuantityTypeIdentifierHeight": ("height", 0.01, "m"),  # cm -> m

    # Endocrine
    "HKQuantityTypeIdentifierBodyTemperature": ("core_temp", 1.0, "C"),
    "HKQuantityTypeIdentifierBloodGlucose": ("glucose", 1.0, "mg/dL"),

    # Blood Pressure
    "HKQuantityTypeIdentifierBloodPressureSystolic": ("bp_systolic", 1.0, "mmHg"),
    "HKQuantityTypeIdentifierBloodPressureDiastolic": ("bp_diastolic", 1.0, "mmHg"),
}

SLEEP_MAP = {
    "HKCategoryValueSleepAnalysisAsleepREM": "sleep_rem",
    "HKCategoryValueSleepAnalysisAsleepDeep": "sleep_deep",
    "HKCategoryValueSleepAnalysisAsleepCore": "sleep_core",
    "HKCategoryValueSleepAnalysisInBed": "sleep_in_bed",
    "HKCategoryValueSleepAnalysisAwake": "sleep_awake",
    "HKCategoryValueSleepAnalysisAsleepUnspecified": "sleep_unspecified",
}

# Clinical validation ranges (hard_min, soft_min, soft_max, hard_max)
VALIDATION_RANGES = {
    "heart_rate": (20, 40, 200, 250),
    "heart_rate_resting": (25, 35, 100, 140),  # Increased from 120 for sleep disturbance
    "hrv_sdnn": (0, 10, 150, 300),
    "spo2": (70, 90, 100, 100),
    "respiratory_rate": (4, 8, 30, 60),
    "steps": (0, 0, 50000, 150000),
    "active_energy": (0, 0, 5000, 15000),
    "basal_energy": (0, 0, 200, 2000),  # Per-sample values, not daily totals
    "exercise_time": (0, 0, 480, 1440),
    "walking_speed": (0, 0.3, 2.5, 6.0),  # Includes running, max ~5.3 m/s observed
    "vo2_max": (10, 20, 70, 100),
    "body_mass": (20, 30, 200, 400),
    "body_fat_percentage": (2, 5, 50, 70),
    "height": (0.5, 1.2, 2.2, 2.8),
    "bp_systolic": (60, 90, 140, 250),
    "bp_diastolic": (30, 50, 90, 150),
    "glucose": (20, 60, 200, 600),
    "sleep_rem": (0, 0, 240, 720),
    "sleep_deep": (0, 0, 240, 720),
    "sleep_core": (0, 0, 240, 720),
    "sleep_in_bed": (0, 60, 720, 1440),
    "distance_walking_running": (0, 0, 50000, 200000),
}


def validate_value(slug: str, value: float) -> tuple[bool, str]:
    """Validate a value against clinical ranges."""
    if slug not in VALIDATION_RANGES:
        return True, "no_range"

    hard_min, soft_min, soft_max, hard_max = VALIDATION_RANGES[slug]

    if value < hard_min or value > hard_max:
        return False, f"INVALID: {value} outside [{hard_min}, {hard_max}]"
    elif value < soft_min:
        return True, f"WARNING: {value} < soft_min {soft_min}"
    elif value > soft_max:
        return True, f"WARNING: {value} > soft_max {soft_max}"
    else:
        return True, "OK"


def parse_apple_date(s: str) -> datetime:
    """Parse Apple Health date format."""
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        return None


def analyze_export(path: Path, max_records: int = 100000):
    """Analyze Apple Health export file."""

    print(f"\nAnalyzing: {path}")
    print(f"File size: {path.stat().st_size / (1024*1024):.1f} MB")
    print("=" * 60)

    # Statistics
    stats = defaultdict(lambda: {
        "count": 0,
        "min": float("inf"),
        "max": float("-inf"),
        "sum": 0,
        "first_date": None,
        "last_date": None,
        "invalid_count": 0,
        "warning_count": 0,
        "sample_values": [],
    })

    unmapped_types = defaultdict(int)
    record_count = 0

    print("\nParsing XML (this may take a minute for large files)...")

    # Use iterparse for memory efficiency
    context = ET.iterparse(str(path), events=("end",))

    for event, elem in context:
        if record_count >= max_records:
            print(f"\nReached {max_records} record limit, stopping early...")
            break

        if elem.tag == "Record":
            record_type = elem.get("type")

            # Handle sleep analysis (stored as Record, not CategorySample)
            if record_type == "HKCategoryTypeIdentifierSleepAnalysis":
                value = elem.get("value")
                if value in SLEEP_MAP:
                    soma_slug = SLEEP_MAP[value]
                    start_str = elem.get("startDate")
                    end_str = elem.get("endDate")
                    start = parse_apple_date(start_str)
                    end = parse_apple_date(end_str)

                    if start and end:
                        duration_min = (end - start).total_seconds() / 60

                        s = stats[soma_slug]
                        s["count"] += 1
                        s["min"] = min(s["min"], duration_min)
                        s["max"] = max(s["max"], duration_min)
                        s["sum"] += duration_min

                        if s["first_date"] is None or start < s["first_date"]:
                            s["first_date"] = start
                        if s["last_date"] is None or start > s["last_date"]:
                            s["last_date"] = start

                        valid, status = validate_value(soma_slug, duration_min)
                        if not valid:
                            s["invalid_count"] += 1
                        elif "WARNING" in status:
                            s["warning_count"] += 1

                        if len(s["sample_values"]) < 3:
                            s["sample_values"].append((duration_min, start_str, status))

                        record_count += 1

            elif record_type in APPLE_TYPE_MAP:
                soma_slug, conversion, unit = APPLE_TYPE_MAP[record_type]

                try:
                    raw_value = float(elem.get("value", 0))
                    value = raw_value * conversion

                    date_str = elem.get("startDate")
                    date = parse_apple_date(date_str)

                    # Update stats
                    s = stats[soma_slug]
                    s["count"] += 1
                    s["min"] = min(s["min"], value)
                    s["max"] = max(s["max"], value)
                    s["sum"] += value

                    if date:
                        if s["first_date"] is None or date < s["first_date"]:
                            s["first_date"] = date
                        if s["last_date"] is None or date > s["last_date"]:
                            s["last_date"] = date

                    # Validate
                    valid, status = validate_value(soma_slug, value)
                    if not valid:
                        s["invalid_count"] += 1
                    elif "WARNING" in status:
                        s["warning_count"] += 1

                    # Keep some sample values
                    if len(s["sample_values"]) < 5:
                        s["sample_values"].append((value, date_str, status))

                    record_count += 1

                except (ValueError, TypeError):
                    pass
            else:
                unmapped_types[record_type] += 1

        elif elem.tag == "CategorySample":
            cat_type = elem.get("type")
            if cat_type == "HKCategoryTypeIdentifierSleepAnalysis":
                value = elem.get("value")
                if value in SLEEP_MAP:
                    soma_slug = SLEEP_MAP[value]

                    start_str = elem.get("startDate")
                    end_str = elem.get("endDate")
                    start = parse_apple_date(start_str)
                    end = parse_apple_date(end_str)

                    if start and end:
                        duration_min = (end - start).total_seconds() / 60

                        s = stats[soma_slug]
                        s["count"] += 1
                        s["min"] = min(s["min"], duration_min)
                        s["max"] = max(s["max"], duration_min)
                        s["sum"] += duration_min

                        if s["first_date"] is None or start < s["first_date"]:
                            s["first_date"] = start
                        if s["last_date"] is None or start > s["last_date"]:
                            s["last_date"] = start

                        # Validate
                        valid, status = validate_value(soma_slug, duration_min)
                        if not valid:
                            s["invalid_count"] += 1
                        elif "WARNING" in status:
                            s["warning_count"] += 1

                        if len(s["sample_values"]) < 3:
                            s["sample_values"].append((duration_min, start_str, status))

                        record_count += 1

        # Clear element to save memory
        elem.clear()

    # Print results
    print(f"\nTotal records processed: {record_count:,}")
    print("\n" + "=" * 80)
    print("BIOMARKER SUMMARY")
    print("=" * 80)

    # Group by category
    categories = {
        "Autonomic": ["heart_rate", "heart_rate_resting", "hrv_sdnn", "spo2", "respiratory_rate"],
        "Sleep": ["sleep_rem", "sleep_deep", "sleep_core", "sleep_in_bed", "sleep_awake", "sleep_unspecified"],
        "Activity": ["steps", "active_energy", "basal_energy", "exercise_time", "stand_time", "flights_climbed", "distance_walking_running"],
        "Mobility": ["walking_speed", "walking_step_length", "walking_asymmetry", "walking_double_support"],
        "Fitness": ["vo2_max"],
        "Body Composition": ["body_mass", "body_fat_percentage", "height", "body_mass_index", "lean_body_mass"],
        "Cardiovascular": ["bp_systolic", "bp_diastolic"],
        "Circadian": ["time_in_daylight"],
        "Endocrine": ["glucose", "core_temp"],
    }

    for category, slugs in categories.items():
        category_stats = [(slug, stats[slug]) for slug in slugs if stats[slug]["count"] > 0]

        if not category_stats:
            continue

        print(f"\n### {category}")
        print("-" * 80)

        for slug, s in category_stats:
            count = s["count"]
            avg = s["sum"] / count if count > 0 else 0

            date_range = ""
            if s["first_date"] and s["last_date"]:
                date_range = f"{s['first_date'].strftime('%Y-%m-%d')} to {s['last_date'].strftime('%Y-%m-%d')}"

            validation_status = ""
            if s["invalid_count"] > 0:
                validation_status = f" | INVALID: {s['invalid_count']}"
            if s["warning_count"] > 0:
                validation_status += f" | WARNINGS: {s['warning_count']}"

            print(f"  {slug:30} | {count:8,} records | min={s['min']:8.1f} | max={s['max']:8.1f} | avg={avg:8.1f}{validation_status}")
            if date_range:
                print(f"  {'':30} | {date_range}")

            # Show sample values with validation
            if s["sample_values"]:
                print(f"  {'':30} | Samples: ", end="")
                samples = [f"{v:.1f} ({status})" for v, _, status in s["sample_values"][:3]]
                print(", ".join(samples))

    # Show unmapped types
    if unmapped_types:
        print("\n" + "=" * 80)
        print("UNMAPPED APPLE HEALTH TYPES (not imported)")
        print("=" * 80)
        sorted_unmapped = sorted(unmapped_types.items(), key=lambda x: -x[1])[:20]
        for record_type, count in sorted_unmapped:
            short_type = record_type.replace("HKQuantityTypeIdentifier", "")
            print(f"  {short_type:40} | {count:,} records")

    return stats


if __name__ == "__main__":
    export_path = Path("apple_health_export/export.xml")
    max_records = 100000

    if len(sys.argv) > 1:
        export_path = Path(sys.argv[1])
    if len(sys.argv) > 2:
        max_records = int(sys.argv[2])

    if not export_path.exists():
        print(f"Error: {export_path} not found")
        sys.exit(1)

    analyze_export(export_path, max_records)
