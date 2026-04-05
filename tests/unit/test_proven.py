"""Unit tests for proven statistical analysis functions."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from soma.statistics.proven import (
    analyze_circadian_rhythm,
    analyze_weekly_activity,
    analyze_long_term_trend,
    detect_anomalies,
    analyze_hrv,
    analyze_spo2,
)


class TestCircadianRhythm:
    """Tests for circadian rhythm analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_circadian_rhythm(minimal_signals_df)
        assert result is None

    def test_returns_none_with_empty_data(self, empty_signals_df):
        """Should return None for empty DataFrame."""
        result = analyze_circadian_rhythm(empty_signals_df)
        assert result is None

    def test_detects_circadian_pattern(self, sample_hr_data):
        """Should detect a clear circadian pattern in simulated data."""
        result = analyze_circadian_rhythm(sample_hr_data)

        assert result is not None
        assert len(result.hourly_patterns) == 24
        # The simulated data uses sine wave, so just verify pattern exists
        assert result.lowest_hour != result.highest_hour
        assert result.amplitude > 10  # Should have meaningful amplitude
        assert result.total_samples == len(sample_hr_data)

    def test_hourly_patterns_have_confidence_intervals(self, sample_hr_data):
        """Each hour should have proper CI bounds."""
        result = analyze_circadian_rhythm(sample_hr_data)

        for pattern in result.hourly_patterns:
            assert pattern.stats.ci_lower <= pattern.stats.mean
            assert pattern.stats.mean <= pattern.stats.ci_upper
            assert pattern.stats.n > 0


class TestWeeklyActivity:
    """Tests for weekly activity analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_weekly_activity(minimal_signals_df)
        assert result is None

    def test_detects_weekly_pattern(self, sample_steps_data):
        """Should detect weekly activity pattern."""
        result = analyze_weekly_activity(sample_steps_data)

        assert result is not None
        assert len(result.daily_patterns) == 7
        assert result.most_active_day is not None
        assert result.least_active_day is not None
        assert result.f_statistic > 0
        assert 0 <= result.p_value <= 1

    def test_weekday_vs_weekend_difference(self, sample_steps_data):
        """Should show difference between weekday and weekend activity."""
        result = analyze_weekly_activity(sample_steps_data)

        # Our fixture simulates higher weekday activity
        weekday_means = [p.stats.mean for p in result.daily_patterns if p.day_number < 5]
        weekend_means = [p.stats.mean for p in result.daily_patterns if p.day_number >= 5]

        avg_weekday = np.mean(weekday_means)
        avg_weekend = np.mean(weekend_means)

        # Weekdays should be more active in our simulation
        assert avg_weekday > avg_weekend


class TestLongTermTrend:
    """Tests for long-term trend analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_long_term_trend(minimal_signals_df)
        assert result is None

    def test_analyzes_multi_year_data(self):
        """Should analyze trend across multiple years."""
        # Create 3 years of data with slight upward trend
        np.random.seed(42)
        dates = pd.date_range(start="2021-01-01", end="2023-12-31", freq="D")
        values = 60 + 0.01 * np.arange(len(dates)) + np.random.normal(0, 2, len(dates))

        df = pd.DataFrame({
            "time": dates,
            "biomarker_slug": "heart_rate_resting",
            "value": values
        })

        result = analyze_long_term_trend(df)

        assert result is not None
        assert len(result.yearly_stats) >= 3
        assert result.slope is not None
        assert 0 <= result.p_value <= 1
        assert 0 <= result.r_squared <= 1


class TestAnomalyDetection:
    """Tests for anomaly detection."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = detect_anomalies(minimal_signals_df)
        assert result is None

    def test_detects_anomalies_in_data_with_outliers(self):
        """Should detect clear outliers."""
        np.random.seed(42)
        dates = pd.date_range(start="2023-01-01", periods=100, freq="D")
        values = np.random.normal(70, 5, 100)

        # Add some clear anomalies
        values[10] = 120  # High outlier
        values[50] = 40   # Low outlier

        df = pd.DataFrame({
            "time": dates,
            "biomarker_slug": "heart_rate",
            "value": values
        })

        result = detect_anomalies(df)

        assert result is not None
        assert len(result.anomalies) >= 2
        assert result.anomaly_rate > 0

    def test_anomaly_statistics(self, sample_hr_data):
        """Should compute proper statistics."""
        # Aggregate to daily for anomaly detection
        df = sample_hr_data.copy()
        df["date"] = pd.to_datetime(df["time"]).dt.date
        daily = df.groupby("date").agg({"value": "mean", "biomarker_slug": "first"}).reset_index()
        daily["time"] = pd.to_datetime(daily["date"])

        result = detect_anomalies(daily)

        assert result is not None
        assert result.median is not None
        assert result.iqr >= 0
        assert result.threshold_low < result.threshold_high


class TestHRVAnalysis:
    """Tests for HRV analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_hrv(minimal_signals_df)
        assert result is None

    def test_analyzes_hrv_data(self, sample_hrv_data):
        """Should analyze HRV data properly."""
        result = analyze_hrv(sample_hrv_data)

        assert result is not None
        assert result.mean_ms.mean > 0
        assert result.mean_ms.ci_lower < result.mean_ms.mean
        assert result.mean_ms.mean < result.mean_ms.ci_upper
        assert result.assessment in ["above_average", "normal", "below_average"]

    def test_unit_correction_for_microseconds(self):
        """Should correct units when HRV appears to be in microseconds."""
        dates = pd.date_range(start="2023-01-01", periods=100, freq="D")

        # HRV values that look like microseconds (should be ~50ms but stored as 50000)
        df = pd.DataFrame({
            "time": dates,
            "biomarker_slug": "hrv_sdnn",
            "value": np.random.normal(50000, 5000, 100)
        })

        result = analyze_hrv(df)

        assert result is not None
        assert result.unit_correction_applied
        assert 10 < result.mean_ms.mean < 200  # Reasonable ms range after correction


class TestSpO2Analysis:
    """Tests for SpO2 analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_spo2(minimal_signals_df)
        assert result is None

    def test_analyzes_spo2_data(self):
        """Should analyze SpO2 data properly."""
        np.random.seed(42)
        dates = pd.date_range(start="2023-01-01", periods=1000, freq="H")

        # Normal SpO2 values (96-99%)
        df = pd.DataFrame({
            "time": dates,
            "biomarker_slug": "spo2",
            "value": np.random.normal(97, 1, len(dates)).clip(90, 100)
        })

        result = analyze_spo2(df)

        assert result is not None
        assert 90 < result.mean.mean < 100
        assert 0 <= result.pct_below_95 <= 1
        assert result.assessment in ["healthy", "normal", "low"]

    def test_flags_low_spo2_readings(self):
        """Should track percentage of low readings."""
        np.random.seed(42)
        dates = pd.date_range(start="2023-01-01", periods=100, freq="H")

        # Mix of normal and low values
        values = np.concatenate([
            np.random.normal(97, 0.5, 80),  # Normal
            np.random.normal(93, 1, 20)     # Low
        ])
        np.random.shuffle(values)

        df = pd.DataFrame({
            "time": dates,
            "biomarker_slug": "spo2",
            "value": values
        })

        result = analyze_spo2(df)

        assert result is not None
        assert result.pct_below_95 > 0
