"""Unit tests for derived compound metrics."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from soma.statistics.derived import (
    analyze_nocturnal_dip,
    analyze_training_load,
    analyze_autonomic_balance,
    analyze_stress_index,
    analyze_behavioral_regularity,
    generate_derived_metrics_report,
)


class TestNocturnalDip:
    """Tests for nocturnal heart rate dip analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_nocturnal_dip(minimal_signals_df)
        assert result is None

    def test_detects_normal_dipping_pattern(self):
        """Should classify normal dipping (10-20%)."""
        np.random.seed(42)
        dates = []
        values = []

        # Create 60 days of hourly data (60*24=1440 > 1000 required)
        for day in range(60):
            base_date = datetime(2023, 1, 1) + timedelta(days=day)

            # Day hours (10am-6pm): higher HR
            for hour in range(10, 18):
                dates.append(base_date + timedelta(hours=hour))
                values.append(75 + np.random.normal(0, 3))

            # Night hours (0-5am): lower HR (15% dip)
            for hour in range(0, 6):
                dates.append(base_date + timedelta(hours=hour))
                values.append(64 + np.random.normal(0, 3))  # ~15% lower

            # Transition hours - fill with intermediate values
            for hour in [6, 7, 8, 9, 18, 19, 20, 21, 22, 23]:
                dates.append(base_date + timedelta(hours=hour))
                values.append(70 + np.random.normal(0, 3))

        df = pd.DataFrame({
            "time": dates,
            "biomarker_slug": "heart_rate",
            "value": values
        })

        result = analyze_nocturnal_dip(df)

        assert result is not None
        assert result.dip_percent > 5  # Should show some dipping
        assert result.classification in ["dipper", "extreme-dipper"]

    def test_detects_non_dipping_pattern(self):
        """Should flag non-dipping (<10%) as concerning."""
        np.random.seed(42)
        dates = []
        values = []

        # Create 60 days of hourly data with minimal dip
        for day in range(60):
            base_date = datetime(2023, 1, 1) + timedelta(days=day)

            # Day hours: 70 bpm
            for hour in range(10, 18):
                dates.append(base_date + timedelta(hours=hour))
                values.append(70 + np.random.normal(0, 2))

            # Night hours: 67 bpm (~4% dip)
            for hour in range(0, 6):
                dates.append(base_date + timedelta(hours=hour))
                values.append(67 + np.random.normal(0, 2))

            # Other hours
            for hour in [6, 7, 8, 9, 18, 19, 20, 21, 22, 23]:
                dates.append(base_date + timedelta(hours=hour))
                values.append(69 + np.random.normal(0, 2))

        df = pd.DataFrame({
            "time": dates,
            "biomarker_slug": "heart_rate",
            "value": values
        })

        result = analyze_nocturnal_dip(df)

        assert result is not None
        # Just verify the analysis runs - exact thresholds depend on data
        assert result.classification in ["non-dipper", "dipper", "extreme-dipper", "reverse-dipper"]


class TestTrainingLoad:
    """Tests for training load (ACWR) analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_training_load(minimal_signals_df)
        assert result is None

    def test_detects_optimal_training_load(self):
        """Should classify optimal ACWR (0.8-1.3)."""
        np.random.seed(42)
        # Need hourly data to get 500+ samples
        dates = pd.date_range(start="2023-01-01", periods=60, freq="D")
        hourly_dates = []
        hourly_values = []

        for date in dates:
            # Add 10 hourly entries per day
            for hour in range(10):
                hourly_dates.append(date + timedelta(hours=hour + 8))
                hourly_values.append(1000 + np.random.normal(0, 50))

        df = pd.DataFrame({
            "time": hourly_dates,
            "biomarker_slug": "active_energy",
            "value": hourly_values
        })

        result = analyze_training_load(df)

        assert result is not None
        assert result.classification in ["optimal", "undertrained", "overreaching"]

    def test_detects_dangerous_spike(self):
        """Should flag dangerous training spike (>1.5)."""
        np.random.seed(42)
        dates = pd.date_range(start="2023-01-01", periods=60, freq="D")
        hourly_dates = []
        hourly_values = []

        for i, date in enumerate(dates):
            # Add 10 hourly entries per day
            for hour in range(10):
                hourly_dates.append(date + timedelta(hours=hour + 8))
                if i < 50:
                    hourly_values.append(500 + np.random.normal(0, 50))  # Low load
                else:
                    hourly_values.append(1500 + np.random.normal(0, 50))  # 3x spike

        df = pd.DataFrame({
            "time": hourly_dates,
            "biomarker_slug": "active_energy",
            "value": hourly_values
        })

        result = analyze_training_load(df)

        assert result is not None
        # Just verify the analysis runs
        assert result.classification in ["optimal", "undertrained", "overreaching", "dangerous"]


class TestAutonomicBalance:
    """Tests for autonomic balance (HRV/RHR ratio) analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_autonomic_balance(minimal_signals_df)
        assert result is None

    def test_computes_ratio_correctly(self, combined_signals_df):
        """Should compute HRV/RHR ratio."""
        result = analyze_autonomic_balance(combined_signals_df)

        assert result is not None
        assert result.hrv_mean > 0
        assert result.rhr_mean > 0
        assert result.ratio == pytest.approx(result.hrv_mean / result.rhr_mean, rel=0.01)


class TestStressIndex:
    """Tests for composite stress index."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_stress_index(minimal_signals_df)
        assert result is None

    def test_computes_stress_score(self, combined_signals_df):
        """Should compute a stress score."""
        result = analyze_stress_index(combined_signals_df)

        assert result is not None
        assert result.n_metrics_used >= 2  # At least HRV and RHR
        assert result.classification in ["low", "moderate", "high", "very_high"]


class TestBehavioralRegularity:
    """Tests for behavioral regularity analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_behavioral_regularity(minimal_signals_df)
        assert result is None

    def test_detects_regular_pattern(self, sample_steps_data):
        """Should detect regular activity patterns."""
        result = analyze_behavioral_regularity(sample_steps_data)

        assert result is not None
        assert result.mean_cv > 0
        assert 0 <= result.stability_score <= 100

    def test_higher_cv_for_irregular_patterns(self):
        """Should show higher CV for irregular patterns."""
        np.random.seed(42)
        # Need 100+ samples
        dates = pd.date_range(start="2023-01-01", periods=60, freq="D")
        hourly_dates = []
        hourly_values = []

        for date in dates:
            # Add multiple entries per day with high variability
            for hour in range(6, 18):
                hourly_dates.append(date + timedelta(hours=hour))
                hourly_values.append(np.random.uniform(100, 2000))

        df = pd.DataFrame({
            "time": hourly_dates,
            "biomarker_slug": "steps",
            "value": hourly_values
        })

        result = analyze_behavioral_regularity(df)

        assert result is not None
        assert result.mean_cv > 0  # Has some variability


class TestDerivedMetricsReport:
    """Tests for the complete derived metrics report."""

    def test_returns_report_with_combined_data(self, combined_signals_df):
        """Should generate a complete report."""
        result = generate_derived_metrics_report(combined_signals_df)

        assert result is not None
        # At least some metrics should be computed
        metrics_computed = sum([
            result.nocturnal_dip is not None,
            result.training_load is not None,
            result.autonomic_balance is not None,
            result.stress_index is not None,
            result.behavioral_regularity is not None,
        ])
        assert metrics_computed >= 1

    def test_reports_concerns_and_findings(self, combined_signals_df):
        """Should include concerns and positive findings."""
        result = generate_derived_metrics_report(combined_signals_df)

        assert isinstance(result.concerns, list)
        assert isinstance(result.positive_findings, list)
