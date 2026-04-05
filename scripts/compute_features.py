#!/usr/bin/env python3
"""
Computed Health Features Module

Derives higher-order health metrics from raw biomarker data.
All algorithms are based on peer-reviewed literature.
"""

import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class DailyMetrics:
    """Aggregated daily health metrics."""
    date: str
    resting_hr: Optional[float] = None
    hrv_sdnn: Optional[float] = None
    steps: Optional[int] = None
    active_cal: Optional[float] = None
    sleep_total: Optional[float] = None  # minutes
    sleep_deep_pct: Optional[float] = None
    sleep_rem_pct: Optional[float] = None
    sleep_efficiency: Optional[float] = None
    daylight_min: Optional[float] = None


# ============================================================================
# RECOVERY SCORE (Whoop/Oura-style)
# ============================================================================

def compute_recovery_score(
    current_hrv: float,
    hrv_baseline: float,
    current_rhr: float,
    rhr_baseline: float,
    sleep_efficiency: Optional[float] = None,
    sleep_duration_hrs: Optional[float] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    Compute a recovery score (0-100) based on HRV, RHR, and sleep.

    Algorithm:
    - HRV component (40%): Current HRV vs 7-day baseline
    - RHR component (30%): Current RHR vs 7-day baseline (lower is better)
    - Sleep component (30%): Efficiency and duration

    Returns:
        Tuple of (score, component_breakdown)
    """
    components = {}

    # HRV component (40 points max)
    # >110% of baseline = 40 pts, 100% = 30 pts, <70% = 0 pts
    if hrv_baseline > 0:
        hrv_ratio = current_hrv / hrv_baseline
        hrv_score = min(40, max(0, (hrv_ratio - 0.7) * 100))
        components["hrv"] = hrv_score
    else:
        hrv_score = 20  # Default if no baseline
        components["hrv"] = hrv_score

    # RHR component (30 points max)
    # Lower than baseline = good, higher = bad
    if rhr_baseline > 0:
        rhr_diff = current_rhr - rhr_baseline
        # -5 bpm below baseline = 30 pts, at baseline = 20 pts, +10 above = 0 pts
        rhr_score = min(30, max(0, 20 - (rhr_diff * 2)))
        components["rhr"] = rhr_score
    else:
        rhr_score = 15
        components["rhr"] = rhr_score

    # Sleep component (30 points max)
    sleep_score = 0
    if sleep_efficiency is not None:
        # 95% efficiency = 15 pts, 85% = 10 pts, 75% = 5 pts
        sleep_score += min(15, max(0, (sleep_efficiency - 70) / 2))
    else:
        sleep_score += 7.5

    if sleep_duration_hrs is not None:
        # 8 hrs = 15 pts, 7 hrs = 12 pts, 6 hrs = 8 pts, 5 hrs = 4 pts
        sleep_score += min(15, max(0, (sleep_duration_hrs - 4) * 3.75))
    else:
        sleep_score += 7.5

    components["sleep"] = sleep_score

    total = hrv_score + rhr_score + sleep_score
    return (total, components)


# ============================================================================
# TRAINING LOAD (TRIMP-based)
# ============================================================================

def compute_trimp(
    duration_min: float,
    avg_hr: float,
    resting_hr: float,
    max_hr: float,
    gender: str = "male"
) -> float:
    """
    Compute Training Impulse (TRIMP) for a workout session.

    Based on: Banister (1991) TRIMP formula

    TRIMP = Duration * HRR * 0.64 * e^(1.92 * HRR)  [male]
    TRIMP = Duration * HRR * 0.86 * e^(1.67 * HRR)  [female]

    Where HRR = (HR - HRrest) / (HRmax - HRrest)
    """
    import math

    if max_hr <= resting_hr:
        return 0.0

    hrr = (avg_hr - resting_hr) / (max_hr - resting_hr)
    hrr = max(0, min(1, hrr))  # Clamp to 0-1

    if gender.lower() == "female":
        trimp = duration_min * hrr * 0.86 * math.exp(1.67 * hrr)
    else:
        trimp = duration_min * hrr * 0.64 * math.exp(1.92 * hrr)

    return trimp


def compute_training_load(daily_trimp: List[float]) -> Dict[str, float]:
    """
    Compute acute and chronic training load from daily TRIMP values.

    Based on: Gabbett (2016) Acute:Chronic Workload Ratio

    - Acute load: 7-day sum
    - Chronic load: 28-day average
    - ACWR: Acute / Chronic ratio (optimal: 0.8-1.3, injury risk: >1.5)
    """
    if len(daily_trimp) < 7:
        return {"acute": 0, "chronic": 0, "acwr": 0, "status": "insufficient_data"}

    acute = sum(daily_trimp[-7:])

    if len(daily_trimp) >= 28:
        chronic = statistics.mean(daily_trimp[-28:])
    else:
        chronic = statistics.mean(daily_trimp)

    acwr = acute / chronic if chronic > 0 else 0

    if acwr < 0.8:
        status = "undertrained"
    elif acwr <= 1.3:
        status = "optimal"
    elif acwr <= 1.5:
        status = "elevated_risk"
    else:
        status = "high_injury_risk"

    return {
        "acute": round(acute, 1),
        "chronic": round(chronic, 1),
        "acwr": round(acwr, 2),
        "status": status
    }


# ============================================================================
# CIRCADIAN RHYTHM ANALYSIS
# ============================================================================

def compute_circadian_amplitude(hourly_hr: Dict[int, List[float]]) -> Dict[str, float]:
    """
    Compute circadian rhythm metrics from hourly heart rate data.

    Returns:
        - amplitude: Peak-to-trough HR difference (higher = stronger rhythm)
        - acrophase: Hour of minimum HR (typically during deep sleep)
        - bathyphase: Hour of maximum HR (typically mid-day)
    """
    hourly_avg = {}
    for hour, values in hourly_hr.items():
        if values:
            hourly_avg[hour] = statistics.mean(values)

    if len(hourly_avg) < 12:  # Need at least half the day
        return {"amplitude": 0, "acrophase": 0, "bathyphase": 0, "status": "insufficient_data"}

    min_hr = min(hourly_avg.values())
    max_hr = max(hourly_avg.values())
    amplitude = max_hr - min_hr

    acrophase = min(hourly_avg, key=hourly_avg.get)  # Hour of minimum
    bathyphase = max(hourly_avg, key=hourly_avg.get)  # Hour of maximum

    # Quality assessment
    if amplitude >= 35:
        status = "strong"
    elif amplitude >= 25:
        status = "normal"
    elif amplitude >= 15:
        status = "weak"
    else:
        status = "blunted"

    return {
        "amplitude": round(amplitude, 1),
        "acrophase_hour": acrophase,
        "bathyphase_hour": bathyphase,
        "status": status
    }


def compute_chronotype(sleep_midpoints: List[float]) -> Dict[str, any]:
    """
    Determine chronotype from sleep midpoint times.

    Based on: Roenneberg (2004) Munich Chronotype Questionnaire

    Sleep midpoint (MSF): Middle time between sleep onset and wake

    Chronotypes:
    - Extreme early: <2:30 AM (150 min)
    - Moderate early: 2:30-3:30 AM
    - Intermediate: 3:30-5:00 AM
    - Moderate late: 5:00-6:30 AM
    - Extreme late: >6:30 AM (390 min)
    """
    if not sleep_midpoints:
        return {"chronotype": "unknown", "avg_midpoint": None}

    avg_midpoint = statistics.mean(sleep_midpoints)

    # Convert to hours for classification
    hours = avg_midpoint / 60

    if hours < 2.5:
        chronotype = "extreme_early"
    elif hours < 3.5:
        chronotype = "moderate_early"
    elif hours < 5.0:
        chronotype = "intermediate"
    elif hours < 6.5:
        chronotype = "moderate_late"
    else:
        chronotype = "extreme_late"

    # Format as time string
    h = int(avg_midpoint // 60)
    m = int(avg_midpoint % 60)
    time_str = f"{h:02d}:{m:02d}"

    return {
        "chronotype": chronotype,
        "avg_midpoint_min": round(avg_midpoint, 0),
        "avg_midpoint_time": time_str,
        "consistency": statistics.stdev(sleep_midpoints) if len(sleep_midpoints) > 1 else 0
    }


# ============================================================================
# SLEEP QUALITY METRICS
# ============================================================================

def compute_sleep_efficiency(time_in_bed_min: float, total_sleep_min: float) -> float:
    """
    Compute sleep efficiency percentage.

    Sleep Efficiency = (Total Sleep Time / Time in Bed) * 100

    Thresholds:
    - >90%: Excellent
    - 85-90%: Good
    - 75-85%: Fair
    - <75%: Poor
    """
    if time_in_bed_min <= 0:
        return 0.0

    efficiency = (total_sleep_min / time_in_bed_min) * 100
    return min(100, max(0, efficiency))


def compute_sleep_architecture(
    rem_min: float,
    deep_min: float,
    light_min: float,
    total_sleep_min: float
) -> Dict[str, float]:
    """
    Analyze sleep stage distribution vs healthy targets.

    Healthy adult targets (AASM):
    - REM: 20-25%
    - Deep (N3): 15-20%
    - Light (N1+N2): 50-60%
    """
    if total_sleep_min <= 0:
        return {"status": "no_data"}

    rem_pct = (rem_min / total_sleep_min) * 100
    deep_pct = (deep_min / total_sleep_min) * 100
    light_pct = (light_min / total_sleep_min) * 100

    issues = []
    if rem_pct < 15:
        issues.append("low_rem")
    if deep_pct < 10:
        issues.append("low_deep")
    if rem_pct > 30:
        issues.append("excessive_rem")  # May indicate sleep deprivation recovery

    return {
        "rem_pct": round(rem_pct, 1),
        "deep_pct": round(deep_pct, 1),
        "light_pct": round(light_pct, 1),
        "issues": issues,
        "status": "healthy" if not issues else "suboptimal"
    }


# ============================================================================
# STRESS & AUTONOMIC BALANCE
# ============================================================================

def compute_stress_score(
    current_hrv: float,
    hrv_baseline: float,
    current_rhr: float,
    rhr_baseline: float,
    activity_level: float = 0.5  # 0-1 scale
) -> Tuple[float, str]:
    """
    Estimate stress level from autonomic markers.

    Lower HRV + Higher RHR = Higher stress (sympathetic dominance)

    Returns score 0-100 where:
    - 0-30: Low stress (parasympathetic dominant)
    - 30-60: Moderate stress
    - 60-80: Elevated stress
    - 80-100: High stress
    """
    # HRV component (inverted - lower HRV = higher stress)
    if hrv_baseline > 0:
        hrv_ratio = current_hrv / hrv_baseline
        hrv_stress = max(0, min(50, (1.5 - hrv_ratio) * 50))
    else:
        hrv_stress = 25

    # RHR component (higher RHR = higher stress)
    if rhr_baseline > 0:
        rhr_diff = current_rhr - rhr_baseline
        rhr_stress = max(0, min(50, (rhr_diff + 5) * 5))
    else:
        rhr_stress = 25

    # Adjust for known activity (exercise elevates both legitimately)
    activity_adjustment = activity_level * 20  # Up to 20 point reduction

    total = max(0, hrv_stress + rhr_stress - activity_adjustment)

    if total < 30:
        status = "low"
    elif total < 60:
        status = "moderate"
    elif total < 80:
        status = "elevated"
    else:
        status = "high"

    return (round(total, 0), status)


# ============================================================================
# MOBILITY & FALL RISK
# ============================================================================

def compute_mobility_score(
    walking_speed: Optional[float] = None,
    walking_steadiness: Optional[float] = None,
    walking_asymmetry: Optional[float] = None,
    double_support: Optional[float] = None
) -> Tuple[float, List[str]]:
    """
    Compute composite mobility score from gait metrics.

    Based on: Studenski (2011) gait speed as vital sign

    Returns:
        Tuple of (score 0-100, list of concerns)
    """
    score = 0
    max_score = 0
    concerns = []

    if walking_speed is not None:
        max_score += 40
        # >1.2 m/s = 40 pts, 1.0 = 30 pts, 0.8 = 20 pts, <0.6 = 0 pts
        if walking_speed >= 1.2:
            score += 40
        elif walking_speed >= 1.0:
            score += 30
        elif walking_speed >= 0.8:
            score += 20
            concerns.append("reduced_gait_speed")
        elif walking_speed >= 0.6:
            score += 10
            concerns.append("slow_gait")
        else:
            concerns.append("very_slow_gait")

    if walking_steadiness is not None:
        max_score += 30
        if walking_steadiness >= 90:
            score += 30
        elif walking_steadiness >= 70:
            score += 20
        else:
            score += 10
            concerns.append("fall_risk")

    if walking_asymmetry is not None:
        max_score += 15
        if walking_asymmetry < 5:
            score += 15
        elif walking_asymmetry < 10:
            score += 10
        else:
            score += 5
            concerns.append("gait_asymmetry")

    if double_support is not None:
        max_score += 15
        if double_support < 25:
            score += 15
        elif double_support < 35:
            score += 10
        else:
            score += 5
            concerns.append("balance_issue")

    # Normalize to 0-100
    if max_score > 0:
        normalized = (score / max_score) * 100
    else:
        normalized = 0

    return (round(normalized, 0), concerns)


# ============================================================================
# BASELINE COMPUTATION
# ============================================================================

def compute_rolling_baseline(
    values: List[float],
    window_days: int = 7,
    method: str = "median"
) -> float:
    """
    Compute a rolling baseline from recent values.

    Uses median by default as it's more robust to outliers than mean.
    """
    if not values:
        return 0.0

    recent = values[-window_days:] if len(values) >= window_days else values

    if method == "median":
        return statistics.median(recent)
    elif method == "mean":
        return statistics.mean(recent)
    elif method == "trimmed_mean":
        # Remove top/bottom 10%
        sorted_vals = sorted(recent)
        trim = max(1, len(sorted_vals) // 10)
        return statistics.mean(sorted_vals[trim:-trim]) if len(sorted_vals) > 2 * trim else statistics.mean(sorted_vals)
    else:
        return statistics.median(recent)


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example: Compute recovery score
    recovery, components = compute_recovery_score(
        current_hrv=55,
        hrv_baseline=50,
        current_rhr=62,
        rhr_baseline=65,
        sleep_efficiency=88,
        sleep_duration_hrs=7.5
    )
    print(f"Recovery Score: {recovery:.0f}/100")
    print(f"Components: {components}")

    # Example: Training load
    daily_trimp = [50, 80, 0, 120, 60, 0, 90, 100, 0, 150, 80, 0, 60, 70]
    load = compute_training_load(daily_trimp)
    print(f"\nTraining Load: {load}")

    # Example: Circadian analysis
    hourly_hr = {
        0: [75], 1: [72], 2: [68], 3: [65], 4: [66], 5: [68],
        6: [75], 7: [85], 8: [95], 9: [90], 10: [92], 11: [100],
        12: [105], 13: [98], 14: [95], 15: [93], 16: [96], 17: [94],
        18: [90], 19: [88], 20: [85], 21: [82], 22: [80], 23: [77]
    }
    circadian = compute_circadian_amplitude(hourly_hr)
    print(f"\nCircadian Rhythm: {circadian}")

    # Example: Mobility score
    mobility, concerns = compute_mobility_score(
        walking_speed=1.15,
        walking_steadiness=92,
        walking_asymmetry=4,
        double_support=28
    )
    print(f"\nMobility Score: {mobility}/100")
    if concerns:
        print(f"Concerns: {concerns}")
