"""Biomarker mapping from Whoop API to Soma.

Maps Whoop's data fields to Soma's canonical biomarker slugs with unit conversions.
"""

from datetime import datetime
from typing import Any
from .schemas import Sleep, Recovery, Cycle, Workout, BodyMeasurement


# Mapping format: whoop_field -> (soma_biomarker_slug, conversion_factor)
# Conversion factor is multiplied by the Whoop value to get Soma units

WHOOP_TO_SOMA: dict[str, tuple[str, float]] = {
    # ─────────────────────────────────────────────────────────────────────────
    # Recovery metrics
    # ─────────────────────────────────────────────────────────────────────────
    "recovery.recovery_score": ("recovery_score", 1.0),  # 0-100 scale
    "recovery.resting_heart_rate": ("heart_rate_resting", 1.0),  # bpm
    "recovery.hrv_rmssd_milli": ("hrv_rmssd", 1.0),  # already in ms
    "recovery.spo2_percentage": ("spo2", 1.0),  # percentage
    "recovery.skin_temp_celsius": ("skin_temp_delta", 1.0),  # celsius delta

    # ─────────────────────────────────────────────────────────────────────────
    # Sleep metrics (Whoop stores durations in milliseconds)
    # ─────────────────────────────────────────────────────────────────────────
    "sleep.total_in_bed_time_milli": ("sleep_in_bed", 1 / 60000),  # ms -> min
    "sleep.total_awake_time_milli": ("sleep_awakenings", 1 / 60000),  # ms -> min
    "sleep.total_light_sleep_time_milli": ("sleep_core", 1 / 60000),  # ms -> min
    "sleep.total_slow_wave_sleep_time_milli": ("sleep_deep", 1 / 60000),  # ms -> min
    "sleep.total_rem_sleep_time_milli": ("sleep_rem", 1 / 60000),  # ms -> min
    "sleep.sleep_efficiency_percentage": ("sleep_efficiency", 1.0),  # percentage
    "sleep.respiratory_rate": ("respiratory_rate", 1.0),  # breaths/min
    "sleep.sleep_consistency_percentage": ("sleep_regularity_index", 1.0),  # percentage
    "sleep.sleep_performance_percentage": ("sleep_performance", 1.0),  # percentage

    # ─────────────────────────────────────────────────────────────────────────
    # Cycle (daily strain) metrics
    # ─────────────────────────────────────────────────────────────────────────
    "cycle.strain": ("training_load_acute", 1.0),  # 0-21 Whoop scale
    "cycle.kilojoules": ("active_energy", 0.239006),  # kJ -> kcal
    "cycle.average_heart_rate": ("heart_rate", 1.0),  # bpm
    "cycle.max_heart_rate": ("heart_rate_max", 1.0),  # bpm

    # ─────────────────────────────────────────────────────────────────────────
    # Workout metrics
    # ─────────────────────────────────────────────────────────────────────────
    "workout.strain": ("workout_strain", 1.0),  # 0-21 Whoop scale
    "workout.average_heart_rate": ("heart_rate", 1.0),  # bpm
    "workout.max_heart_rate": ("heart_rate_max", 1.0),  # bpm
    "workout.kilojoules": ("active_energy", 0.239006),  # kJ -> kcal
    "workout.distance_meter": ("distance_walking_running", 1.0),  # meters
    "workout.altitude_gain_meter": ("elevation_gain", 1.0),  # meters

    # ─────────────────────────────────────────────────────────────────────────
    # Body measurements
    # ─────────────────────────────────────────────────────────────────────────
    "body.height_meter": ("height", 1.0),  # meters
    "body.weight_kilogram": ("body_mass", 1.0),  # kg
    "body.max_heart_rate": ("heart_rate_max_measured", 1.0),  # bpm
}


def transform_recovery(recovery: Recovery, timestamp: datetime) -> list[dict[str, Any]]:
    """Transform Whoop recovery data to Soma signals."""
    signals = []

    if recovery.score is None or recovery.score.user_calibrating:
        return signals

    score = recovery.score
    mappings = [
        ("recovery.recovery_score", score.recovery_score),
        ("recovery.resting_heart_rate", score.resting_heart_rate),
        ("recovery.hrv_rmssd_milli", score.hrv_rmssd_milli),
        ("recovery.spo2_percentage", score.spo2_percentage),
        ("recovery.skin_temp_celsius", score.skin_temp_celsius),
    ]

    for whoop_key, value in mappings:
        if value is not None and whoop_key in WHOOP_TO_SOMA:
            soma_slug, factor = WHOOP_TO_SOMA[whoop_key]
            signals.append({
                "time": timestamp,
                "biomarker_slug": soma_slug,
                "value": value * factor,
                "source_slug": "whoop",
                "raw_source_id": f"recovery_{recovery.cycle_id}",
                "quality": 100,
            })

    return signals


def transform_sleep(sleep: Sleep) -> list[dict[str, Any]]:
    """Transform Whoop sleep data to Soma signals."""
    signals = []

    if sleep.score is None or sleep.score_state != "SCORED":
        return signals

    score = sleep.score
    timestamp = sleep.end  # Use sleep end time as the measurement time

    # Extract stage durations from stage_summary
    stage_summary = score.stage_summary or {}

    # Map stage summary fields
    stage_mappings = [
        ("sleep.total_in_bed_time_milli", stage_summary.get("total_in_bed_time_milli")),
        ("sleep.total_awake_time_milli", stage_summary.get("total_awake_time_milli")),
        ("sleep.total_light_sleep_time_milli", stage_summary.get("total_light_sleep_time_milli")),
        ("sleep.total_slow_wave_sleep_time_milli", stage_summary.get("total_slow_wave_sleep_time_milli")),
        ("sleep.total_rem_sleep_time_milli", stage_summary.get("total_rem_sleep_time_milli")),
    ]

    # Map score fields
    score_mappings = [
        ("sleep.sleep_efficiency_percentage", score.sleep_efficiency_percentage),
        ("sleep.respiratory_rate", score.respiratory_rate),
        ("sleep.sleep_consistency_percentage", score.sleep_consistency_percentage),
        ("sleep.sleep_performance_percentage", score.sleep_performance_percentage),
    ]

    for whoop_key, value in stage_mappings + score_mappings:
        if value is not None and whoop_key in WHOOP_TO_SOMA:
            soma_slug, factor = WHOOP_TO_SOMA[whoop_key]
            signals.append({
                "time": timestamp,
                "biomarker_slug": soma_slug,
                "value": value * factor,
                "source_slug": "whoop",
                "raw_source_id": f"sleep_{sleep.id}",
                "quality": 100,
                "meta": {"nap": sleep.nap},
            })

    # Also record total sleep duration
    if "total_in_bed_time_milli" in stage_summary:
        total_in_bed = stage_summary["total_in_bed_time_milli"]
        awake = stage_summary.get("total_awake_time_milli", 0)
        if total_in_bed and awake is not None:
            sleep_duration_min = (total_in_bed - awake) / 60000
            signals.append({
                "time": timestamp,
                "biomarker_slug": "sleep_duration",
                "value": sleep_duration_min,
                "source_slug": "whoop",
                "raw_source_id": f"sleep_{sleep.id}",
                "quality": 100,
                "meta": {"nap": sleep.nap},
            })

    return signals


def transform_cycle(cycle: Cycle) -> list[dict[str, Any]]:
    """Transform Whoop cycle (strain) data to Soma signals."""
    signals = []

    if cycle.score is None or cycle.score_state != "SCORED":
        return signals

    score = cycle.score
    timestamp = cycle.end or cycle.start  # Use end time if available

    mappings = [
        ("cycle.strain", score.strain),
        ("cycle.kilojoules", score.kilojoules),
        ("cycle.average_heart_rate", score.average_heart_rate),
        ("cycle.max_heart_rate", score.max_heart_rate),
    ]

    for whoop_key, value in mappings:
        if value is not None and whoop_key in WHOOP_TO_SOMA:
            soma_slug, factor = WHOOP_TO_SOMA[whoop_key]
            signals.append({
                "time": timestamp,
                "biomarker_slug": soma_slug,
                "value": value * factor,
                "source_slug": "whoop",
                "raw_source_id": f"cycle_{cycle.id}",
                "quality": 100,
            })

    return signals


def transform_workout(workout: Workout) -> list[dict[str, Any]]:
    """Transform Whoop workout data to Soma signals."""
    signals = []

    if workout.score is None or workout.score_state != "SCORED":
        return signals

    score = workout.score
    timestamp = workout.end

    mappings = [
        ("workout.strain", score.strain),
        ("workout.average_heart_rate", score.average_heart_rate),
        ("workout.max_heart_rate", score.max_heart_rate),
        ("workout.kilojoules", score.kilojoules),
        ("workout.distance_meter", score.distance_meter),
        ("workout.altitude_gain_meter", score.altitude_gain_meter),
    ]

    for whoop_key, value in mappings:
        if value is not None and whoop_key in WHOOP_TO_SOMA:
            soma_slug, factor = WHOOP_TO_SOMA[whoop_key]
            signals.append({
                "time": timestamp,
                "biomarker_slug": soma_slug,
                "value": value * factor,
                "source_slug": "whoop",
                "raw_source_id": f"workout_{workout.id}",
                "quality": 100,
                "meta": {"sport_id": workout.sport_id},
            })

    return signals


def transform_body_measurement(body: BodyMeasurement, timestamp: datetime) -> list[dict[str, Any]]:
    """Transform Whoop body measurements to Soma signals."""
    signals = []

    mappings = [
        ("body.height_meter", body.height_meter),
        ("body.weight_kilogram", body.weight_kilogram),
        ("body.max_heart_rate", body.max_heart_rate),
    ]

    for whoop_key, value in mappings:
        if value is not None and whoop_key in WHOOP_TO_SOMA:
            soma_slug, factor = WHOOP_TO_SOMA[whoop_key]
            signals.append({
                "time": timestamp,
                "biomarker_slug": soma_slug,
                "value": value * factor,
                "source_slug": "whoop",
                "raw_source_id": "body_measurement",
                "quality": 100,
            })

    return signals


def transform_whoop_data(
    sleep_records: list[Sleep],
    recovery_records: list[Recovery],
    cycle_records: list[Cycle],
    workout_records: list[Workout],
    body_measurement: BodyMeasurement | None = None,
) -> list[dict[str, Any]]:
    """Transform all Whoop data to Soma signals.

    Args:
        sleep_records: List of sleep records from Whoop
        recovery_records: List of recovery records from Whoop
        cycle_records: List of cycle (strain) records from Whoop
        workout_records: List of workout records from Whoop
        body_measurement: Optional body measurement data

    Returns:
        List of signal dictionaries ready for database insertion
    """
    signals = []

    # Build a map of cycle_id -> cycle end time for recovery timestamps
    cycle_times = {c.id: c.end or c.start for c in cycle_records}

    for sleep in sleep_records:
        signals.extend(transform_sleep(sleep))

    for recovery in recovery_records:
        # Use cycle end time for recovery timestamp
        timestamp = cycle_times.get(recovery.cycle_id, recovery.created_at)
        signals.extend(transform_recovery(recovery, timestamp))

    for cycle in cycle_records:
        signals.extend(transform_cycle(cycle))

    for workout in workout_records:
        signals.extend(transform_workout(workout))

    if body_measurement:
        from datetime import datetime, timezone
        signals.extend(transform_body_measurement(
            body_measurement,
            datetime.now(timezone.utc)
        ))

    return signals
