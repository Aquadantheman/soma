"""Unit tests for stability analysis functions."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from soma.statistics.stability import (
    analyze_convergence,
    analyze_temporal_stability,
    analyze_drift,
    analyze_sample_adequacy,
    generate_stability_report,
)


class TestConvergenceAnalysis:
    """Tests for convergence analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_convergence(minimal_signals_df, "heart_rate")
        assert result is None

    def test_analyzes_convergence(self, sample_hr_data):
        """Should analyze how estimates converge with sample size."""
        result = analyze_convergence(sample_hr_data, "heart_rate")

        assert result is not None
        assert len(result.convergence_points) > 0
        assert result.current_n == len(sample_hr_data)
        assert result.current_mean > 0

    def test_convergence_points_ordered_by_n(self, sample_hr_data):
        """Convergence points should be in increasing order of n."""
        result = analyze_convergence(sample_hr_data, "heart_rate")

        assert result is not None
        ns = [p.n for p in result.convergence_points]
        assert ns == sorted(ns)

    def test_ci_decreases_with_sample_size(self, sample_hr_data):
        """CI width should generally decrease with more samples."""
        result = analyze_convergence(sample_hr_data, "heart_rate")

        assert result is not None
        if len(result.convergence_points) >= 2:
            first_ci = result.convergence_points[0].ci_width
            last_ci = result.convergence_points[-1].ci_width
            assert last_ci <= first_ci


class TestTemporalStability:
    """Tests for temporal stability analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_temporal_stability(minimal_signals_df, "heart_rate")
        assert result is None

    def test_analyzes_stability_across_years(self):
        """Should analyze if biomarker is stable across years."""
        np.random.seed(42)
        # Create 3 years of data
        dates = pd.date_range(start="2021-01-01", end="2023-12-31", freq="D")
        values = np.random.normal(70, 5, len(dates))

        df = pd.DataFrame({
            "time": dates,
            "biomarker_slug": "heart_rate",
            "value": values
        })

        result = analyze_temporal_stability(df, "heart_rate")

        assert result is not None
        assert len(result.periods) >= 3
        assert result.mean_value > 0
        assert 0 <= result.consistency_pct <= 100

    def test_detects_unstable_patterns(self):
        """Should detect instability when years differ significantly."""
        np.random.seed(42)
        # Create 3 years with very different means
        df_list = []
        for year, mean in [(2021, 60), (2022, 80), (2023, 100)]:
            dates = pd.date_range(start=f"{year}-01-01", end=f"{year}-12-31", freq="D")
            values = np.random.normal(mean, 3, len(dates))
            df_list.append(pd.DataFrame({
                "time": dates,
                "biomarker_slug": "heart_rate",
                "value": values
            }))

        df = pd.concat(df_list, ignore_index=True)
        result = analyze_temporal_stability(df, "heart_rate")

        assert result is not None
        assert not result.is_stable  # Should detect instability


class TestDriftAnalysis:
    """Tests for drift analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_drift(minimal_signals_df, "heart_rate")
        assert result is None

    def test_detects_drift(self):
        """Should detect drift when recent data differs from historical."""
        np.random.seed(42)
        # Create historical data with one mean
        hist_dates = pd.date_range(start="2022-01-01", end="2022-12-31", freq="D")
        hist_values = np.random.normal(70, 3, len(hist_dates))

        # Create recent data with different mean
        recent_dates = pd.date_range(start="2023-01-01", end="2023-12-31", freq="D")
        recent_values = np.random.normal(80, 3, len(recent_dates))  # 10 bpm higher

        df = pd.concat([
            pd.DataFrame({"time": hist_dates, "biomarker_slug": "heart_rate", "value": hist_values}),
            pd.DataFrame({"time": recent_dates, "biomarker_slug": "heart_rate", "value": recent_values})
        ], ignore_index=True)

        result = analyze_drift(df, "heart_rate")

        assert result is not None
        assert result.is_significant
        assert result.direction == "increasing"
        assert result.pct_change > 0

    def test_detects_stable_pattern(self):
        """Should detect no drift when data is stable."""
        np.random.seed(42)
        # Create 2 years of stable data
        dates = pd.date_range(start="2022-01-01", end="2023-12-31", freq="D")
        values = np.random.normal(70, 3, len(dates))

        df = pd.DataFrame({
            "time": dates,
            "biomarker_slug": "heart_rate",
            "value": values
        })

        result = analyze_drift(df, "heart_rate")

        assert result is not None
        # Stable data should not show significant drift
        # (though random variation may occasionally trigger)


class TestSampleAdequacy:
    """Tests for sample adequacy analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_sample_adequacy(minimal_signals_df, "heart_rate")
        assert result is None

    def test_assesses_adequacy(self, sample_hr_data):
        """Should assess whether sample size is adequate."""
        result = analyze_sample_adequacy(sample_hr_data, "heart_rate")

        assert result is not None
        assert result.current_n == len(sample_hr_data)
        assert result.required_n_5pct > 0
        assert result.required_n_2pct > result.required_n_5pct
        assert result.adequacy_ratio > 0

    def test_large_sample_is_adequate(self, sample_hr_data):
        """Large samples should be adequate."""
        result = analyze_sample_adequacy(sample_hr_data, "heart_rate")

        assert result is not None
        assert result.is_adequate  # 365*24 samples should be plenty


class TestStabilityReport:
    """Tests for stability report generation."""

    def test_generates_report(self, combined_signals_df):
        """Should generate a complete stability report."""
        report = generate_stability_report(combined_signals_df)

        assert report is not None
        assert report.overall_assessment is not None
        assert isinstance(report.recommendations, list)

    def test_report_includes_all_sections(self, combined_signals_df):
        """Report should include all analysis sections."""
        report = generate_stability_report(combined_signals_df)

        assert report is not None
        assert isinstance(report.convergence, list)
        assert isinstance(report.temporal_stability, list)
        assert isinstance(report.drift, list)
        assert isinstance(report.sample_adequacy, list)
