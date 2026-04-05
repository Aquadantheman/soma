"""Unit tests for advanced statistical analysis functions."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from soma.statistics.advanced import (
    analyze_correlations,
    analyze_recovery,
    analyze_seasonality,
    build_readiness_model,
    compute_readiness_scores,
)


class TestCorrelationAnalysis:
    """Tests for correlation analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_correlations(minimal_signals_df)
        assert result is None

    def test_computes_correlations_between_biomarkers(self, combined_signals_df):
        """Should compute correlations between all biomarker pairs."""
        result = analyze_correlations(combined_signals_df)

        assert result is not None
        assert len(result.pairs) > 0
        assert len(result.biomarkers_analyzed) >= 2

    def test_includes_bonferroni_correction(self, combined_signals_df):
        """Should apply Bonferroni correction for multiple comparisons."""
        result = analyze_correlations(combined_signals_df)

        assert result is not None
        assert result.bonferroni_alpha < 0.05  # Should be smaller due to correction
        assert "Bonferroni" in result.method_note

    def test_correlation_bounds(self, combined_signals_df):
        """Correlations should be between -1 and 1."""
        result = analyze_correlations(combined_signals_df)

        assert result is not None
        for pair in result.pairs:
            assert -1 <= pair.pearson_r <= 1
            assert -1 <= pair.spearman_rho <= 1
            assert 0 <= pair.pearson_p <= 1

    def test_confidence_intervals(self, combined_signals_df):
        """Should have valid confidence intervals."""
        result = analyze_correlations(combined_signals_df)

        assert result is not None
        for pair in result.pairs:
            # CI bounds should contain the correlation value
            # (with small tolerance for floating point edge cases)
            assert pair.ci_lower <= pair.pearson_r + 0.001
            assert pair.pearson_r <= pair.ci_upper + 0.001


class TestRecoveryAnalysis:
    """Tests for recovery/lagged correlation analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_recovery(minimal_signals_df)
        assert result is None

    def test_analyzes_lagged_correlations(self, combined_signals_df):
        """Should analyze correlations at different time lags."""
        result = analyze_recovery(combined_signals_df, predictor="steps", outcome="hrv_sdnn")

        assert result is not None
        assert len(result.lagged_correlations) >= 1
        assert result.optimal_lag >= 0
        assert result.interpretation is not None

    def test_lagged_correlations_have_stats(self, combined_signals_df):
        """Each lag should have proper statistics."""
        result = analyze_recovery(combined_signals_df, predictor="steps", outcome="hrv_sdnn")

        assert result is not None
        for lag in result.lagged_correlations:
            assert lag.lag_days >= 0
            assert -1 <= lag.correlation <= 1
            assert 0 <= lag.p_value <= 1


class TestSeasonalityAnalysis:
    """Tests for seasonality analysis."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = analyze_seasonality(minimal_signals_df, "heart_rate")
        assert result is None

    def test_detects_seasonal_patterns(self):
        """Should detect seasonal variation in multi-month data."""
        np.random.seed(42)
        # Create 2 years of data with seasonal pattern
        dates = pd.date_range(start="2022-01-01", end="2023-12-31", freq="D")
        months = dates.month

        # Add seasonal variation (higher in summer)
        base = 70
        seasonal = 5 * np.sin((months - 1) * np.pi / 6)  # Peak in July
        noise = np.random.normal(0, 2, len(dates))
        values = base + seasonal + noise

        df = pd.DataFrame({
            "time": dates,
            "biomarker_slug": "heart_rate",
            "value": values
        })

        result = analyze_seasonality(df, "heart_rate")

        assert result is not None
        assert len(result.seasonal_components) >= 6
        assert result.peak_month is not None
        assert result.trough_month is not None
        assert result.seasonal_amplitude > 0


class TestReadinessModel:
    """Tests for readiness score computation."""

    def test_returns_none_with_insufficient_data(self, minimal_signals_df):
        """Should return None when there's not enough data."""
        result = build_readiness_model(minimal_signals_df)
        assert result is None

    def test_builds_model_from_data(self, combined_signals_df):
        """Should build readiness model from HRV and RHR data."""
        result = build_readiness_model(combined_signals_df)

        assert result is not None
        assert result.hrv_baseline_mean > 0
        assert result.hrv_baseline_std > 0
        assert result.rhr_baseline_mean > 0
        assert result.rhr_baseline_std > 0
        assert "hrv" in result.weights
        assert "rhr" in result.weights

    def test_computes_readiness_scores(self, combined_signals_df):
        """Should compute daily readiness scores."""
        model = build_readiness_model(combined_signals_df)
        assert model is not None

        scores = compute_readiness_scores(combined_signals_df, model)

        assert len(scores) > 0
        for score in scores:
            assert 0 <= score.score <= 100
            assert score.interpretation in ["optimal", "good", "moderate", "low", "poor"]
            assert score.hrv_z_score is not None
            assert score.rhr_z_score is not None
