"""
HRV Signal Processing
---------------------
Processes raw heart rate variability data into clinically meaningful features.

Key metrics:
  RMSSD  — parasympathetic tone, short-term HRV, anxiety/recovery indicator
  SDNN   — overall autonomic variability
  LF/HF  — sympathetic/parasympathetic balance (requires RR interval series)
  pNN50  — percentage of successive RR intervals differing by >50ms
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional


@dataclass
class HRVFeatures:
    """Computed HRV features for a measurement window."""

    window_start: pd.Timestamp
    window_end: pd.Timestamp

    # Time domain
    rmssd: Optional[float] = None  # ms — primary parasympathetic marker
    sdnn: Optional[float] = None  # ms — overall variability
    pnn50: Optional[float] = None  # % — high-frequency marker
    mean_hr: Optional[float] = None  # bpm
    mean_rr: Optional[float] = None  # ms

    # Frequency domain (requires RR series, not just RMSSD)
    lf_power: Optional[float] = None  # ms² — sympathetic + parasympathetic
    hf_power: Optional[float] = None  # ms² — parasympathetic
    lf_hf_ratio: Optional[float] = None  # sympathovagal balance

    # Nonlinear
    sd1: Optional[float] = None  # Poincaré plot short-term variability
    sd2: Optional[float] = None  # Poincaré plot long-term variability

    # Quality
    sample_count: int = 0
    quality_score: float = 1.0


def compute_rmssd(rr_intervals_ms: np.ndarray) -> float:
    """
    Compute RMSSD from RR interval series.

    RMSSD is the most clinically relevant HRV metric for mental health:
    - Low RMSSD → high sympathetic tone, stress, anxiety, poor recovery
    - High RMSSD → strong parasympathetic tone, good recovery, resilience

    Args:
        rr_intervals_ms: Array of RR intervals in milliseconds

    Returns:
        RMSSD in milliseconds
    """
    if len(rr_intervals_ms) < 2:
        raise ValueError("Need at least 2 RR intervals to compute RMSSD")

    successive_diffs = np.diff(rr_intervals_ms)
    return float(np.sqrt(np.mean(successive_diffs**2)))


def compute_sdnn(rr_intervals_ms: np.ndarray) -> float:
    """Standard deviation of NN intervals."""
    return float(np.std(rr_intervals_ms, ddof=1))


def compute_pnn50(rr_intervals_ms: np.ndarray) -> float:
    """Percentage of successive RR intervals differing by more than 50ms."""
    successive_diffs = np.abs(np.diff(rr_intervals_ms))
    return float(np.mean(successive_diffs > 50) * 100)


def compute_poincare(rr_intervals_ms: np.ndarray) -> tuple[float, float]:
    """
    Poincaré plot SD1 and SD2.

    SD1 = short-term HRV (beat-to-beat, parasympathetic)
    SD2 = long-term HRV (overall autonomic modulation)
    """
    rr_n = rr_intervals_ms[:-1]
    rr_n1 = rr_intervals_ms[1:]
    sd1 = float(np.std((rr_n1 - rr_n) / np.sqrt(2), ddof=1))
    sd2 = float(np.std((rr_n1 + rr_n) / np.sqrt(2), ddof=1))
    return sd1, sd2


def quality_filter_rr(
    rr_intervals_ms: np.ndarray,
    min_ms: float = 300,
    max_ms: float = 2000,
    max_change_pct: float = 0.20,
) -> tuple[np.ndarray, float]:
    """
    Filter physiologically implausible RR intervals.

    Returns filtered array and quality score (0-1).
    """
    # Range filter
    mask = (rr_intervals_ms >= min_ms) & (rr_intervals_ms <= max_ms)

    # Successive change filter (ectopic beats)
    if len(rr_intervals_ms) > 1:
        changes = np.abs(np.diff(rr_intervals_ms)) / rr_intervals_ms[:-1]
        change_mask = np.concatenate([[True], changes <= max_change_pct])
        mask = mask & change_mask

    filtered = rr_intervals_ms[mask]
    quality = float(mask.mean())

    return filtered, quality


def features_from_rr_series(
    rr_intervals_ms: np.ndarray,
    window_start: pd.Timestamp,
    window_end: pd.Timestamp,
) -> HRVFeatures:
    """
    Compute full HRV feature set from an RR interval series.
    """
    filtered, quality = quality_filter_rr(rr_intervals_ms)

    if len(filtered) < 10:
        return HRVFeatures(
            window_start=window_start,
            window_end=window_end,
            sample_count=len(rr_intervals_ms),
            quality_score=quality,
        )

    sd1, sd2 = compute_poincare(filtered)

    return HRVFeatures(
        window_start=window_start,
        window_end=window_end,
        rmssd=compute_rmssd(filtered),
        sdnn=compute_sdnn(filtered),
        pnn50=compute_pnn50(filtered),
        mean_rr=float(np.mean(filtered)),
        mean_hr=float(60000 / np.mean(filtered)),
        sd1=sd1,
        sd2=sd2,
        sample_count=len(rr_intervals_ms),
        quality_score=quality,
    )


def daily_hrv_summary(signals_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate raw HRV signals to daily summary statistics.

    Args:
        signals_df: DataFrame with columns [time, biomarker_slug, value]
                    filtered to HRV biomarkers

    Returns:
        DataFrame with daily HRV statistics
    """
    hrv_data = signals_df[signals_df["biomarker_slug"] == "hrv_rmssd"].copy()
    hrv_data["date"] = pd.to_datetime(hrv_data["time"]).dt.date

    daily = (
        hrv_data.groupby("date")["value"]
        .agg(
            rmssd_mean="mean",
            rmssd_std="std",
            rmssd_min="min",
            rmssd_max="max",
            sample_count="count",
        )
        .reset_index()
    )

    return daily
