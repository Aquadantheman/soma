"""
Personal Baseline Model
-----------------------
This is the core of what makes Soma different from a fitness tracker.

Instead of comparing you to population norms, Soma builds YOUR baseline —
your personal distribution for each biomarker — and measures everything
as a deviation from that.

Your RMSSD of 28ms might be normal for you even if the population average
is 42ms. What matters is: is 28ms your normal, or is it a 2-sigma drop
from your personal baseline?

The baseline model:
  - Requires minimum N days of data before reporting (configurable)
  - Uses rolling windows to adapt to genuine long-term changes
  - Distinguishes acute deviations from baseline drift
  - Tracks stability of the baseline itself
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional
from scipy import stats


@dataclass
class BiomarkerBaseline:
    """Personal baseline for a single biomarker."""

    biomarker_slug: str
    computed_at: pd.Timestamp
    window_days: int

    # Distribution parameters
    mean: float
    std: float
    median: float
    p10: float
    p25: float
    p75: float
    p90: float

    # Stability
    sample_count: int
    is_stable: bool  # True if baseline has converged
    coefficient_of_variation: float  # std/mean — lower = more stable

    # Trend
    trend_direction: Optional[str] = None  # 'rising', 'falling', 'stable'
    trend_magnitude: Optional[float] = None  # units per day


@dataclass
class DeviationResult:
    """How much a current observation deviates from personal baseline."""

    biomarker_slug: str
    observed_value: float
    baseline_mean: float
    baseline_std: float

    z_score: float  # standard deviations from personal mean
    percentile: float  # where this falls in personal distribution
    deviation_pct: float  # percent change from personal mean

    is_notable: bool  # |z_score| > 1.5
    is_significant: bool  # |z_score| > 2.0
    direction: str  # 'above', 'below', 'within'

    clinical_note: Optional[str] = None


# Minimum days of data required before baseline is considered valid
MIN_BASELINE_DAYS = 14
NOTABLE_Z_THRESHOLD = 1.5
SIGNIFICANT_Z_THRESHOLD = 2.0

# Biomarkers that may need unit correction
HRV_BIOMARKERS = {"hrv_sdnn", "hrv_rmssd"}
HRV_MICROSECOND_THRESHOLD = 1000  # If median > 1000, values are in microseconds


def _apply_unit_corrections(values: np.ndarray, biomarker_slug: str) -> np.ndarray:
    """
    Apply unit corrections for biomarkers that may be stored in non-standard units.

    Apple Health stores HRV in microseconds, but convention is milliseconds.
    """
    if biomarker_slug in HRV_BIOMARKERS:
        median_val = np.median(values)
        if median_val > HRV_MICROSECOND_THRESHOLD:
            # Values are in microseconds, convert to milliseconds
            return values / 1000.0
    return values


def compute_baseline(
    signals_df: pd.DataFrame,
    biomarker_slug: str,
    window_days: int = 90,
    reference_time: Optional[pd.Timestamp] = None,
) -> Optional[BiomarkerBaseline]:
    """
    Compute personal baseline for a biomarker from historical signal data.

    Args:
        signals_df: DataFrame with [time, biomarker_slug, value]
        biomarker_slug: Which biomarker to baseline
        window_days: How many days of history to use
        reference_time: Compute baseline as of this time (default: now)

    Returns:
        BiomarkerBaseline or None if insufficient data
    """
    if reference_time is None:
        reference_time = pd.Timestamp.now()

    # Make reference_time timezone-naive for comparison
    if reference_time.tzinfo is not None:
        reference_time = reference_time.tz_localize(None)

    cutoff = reference_time - pd.Timedelta(days=window_days)

    subset = signals_df[
        (signals_df["biomarker_slug"] == biomarker_slug)
        & (pd.to_datetime(signals_df["time"]) >= cutoff)
        & (pd.to_datetime(signals_df["time"]) < reference_time)
        & signals_df["value"].notna()
    ]["value"].values

    # Apply unit corrections (e.g., HRV microseconds -> milliseconds)
    subset = _apply_unit_corrections(subset, biomarker_slug)

    # Require minimum data
    n_days = (
        signals_df[signals_df["biomarker_slug"] == biomarker_slug]["time"]
        .pipe(pd.to_datetime)
        .dt.date.nunique()
    )

    if n_days < MIN_BASELINE_DAYS or len(subset) < 20:
        return None

    # Compute trend via linear regression
    times_numeric = np.arange(len(subset), dtype=float)
    slope, _, _, p_value, _ = stats.linregress(times_numeric, subset)

    trend_direction = "stable"
    if p_value < 0.05:
        trend_direction = "rising" if slope > 0 else "falling"

    mean = float(np.mean(subset))
    std = float(np.std(subset, ddof=1))
    cv = std / mean if mean != 0 else 0

    return BiomarkerBaseline(
        biomarker_slug=biomarker_slug,
        computed_at=reference_time,
        window_days=window_days,
        mean=mean,
        std=std,
        median=float(np.median(subset)),
        p10=float(np.percentile(subset, 10)),
        p25=float(np.percentile(subset, 25)),
        p75=float(np.percentile(subset, 75)),
        p90=float(np.percentile(subset, 90)),
        sample_count=len(subset),
        is_stable=cv < 0.3 and n_days >= MIN_BASELINE_DAYS,
        coefficient_of_variation=cv,
        trend_direction=trend_direction,
        trend_magnitude=float(slope),
    )


def compute_deviation(
    observed_value: float,
    baseline: BiomarkerBaseline,
) -> DeviationResult:
    """
    Compute how much an observation deviates from personal baseline.
    """
    z_score = (
        (observed_value - baseline.mean) / baseline.std if baseline.std > 0 else 0.0
    )
    percentile = float(stats.norm.cdf(z_score) * 100)
    deviation_pct = (
        (observed_value - baseline.mean) / baseline.mean * 100
        if baseline.mean != 0
        else 0.0
    )

    direction = "within"
    if z_score > NOTABLE_Z_THRESHOLD:
        direction = "above"
    elif z_score < -NOTABLE_Z_THRESHOLD:
        direction = "below"

    clinical_note = _clinical_note(baseline.biomarker_slug, z_score, direction)

    return DeviationResult(
        biomarker_slug=baseline.biomarker_slug,
        observed_value=observed_value,
        baseline_mean=baseline.mean,
        baseline_std=baseline.std,
        z_score=z_score,
        percentile=percentile,
        deviation_pct=deviation_pct,
        is_notable=abs(z_score) >= NOTABLE_Z_THRESHOLD,
        is_significant=abs(z_score) >= SIGNIFICANT_Z_THRESHOLD,
        direction=direction,
        clinical_note=clinical_note,
    )


def _clinical_note(slug: str, z_score: float, direction: str) -> Optional[str]:
    """
    Generate a plain-language clinical note for notable deviations.
    These are observations, not diagnoses.
    """
    notes = {
        "hrv_rmssd": {
            "below": "HRV is significantly below your personal baseline, suggesting elevated sympathetic tone or incomplete recovery.",
            "above": "HRV is elevated above your baseline, suggesting strong parasympathetic recovery.",
        },
        "heart_rate_resting": {
            "above": "Resting heart rate is elevated above your baseline — possible stress, illness, or inadequate recovery.",
            "below": "Resting heart rate is lower than your baseline, consistent with good cardiovascular recovery.",
        },
        "sleep_duration": {
            "below": "Sleep duration is notably below your baseline.",
            "above": "Sleep duration is above your baseline.",
        },
        "sleep_rem_pct": {
            "below": "REM sleep percentage is below your baseline. REM is important for emotional regulation and memory consolidation.",
        },
        "eda_tonic": {
            "above": "Skin conductance (sympathetic arousal) is elevated above your baseline.",
        },
    }

    if abs(z_score) < NOTABLE_Z_THRESHOLD:
        return None

    slug_notes = notes.get(slug, {})
    return slug_notes.get(direction)
