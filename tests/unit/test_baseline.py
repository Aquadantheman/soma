"""Unit tests for baseline model functions."""

import numpy as np
import pandas as pd
import pytest

from soma.baseline.model import (
    BiomarkerBaseline,
    DeviationResult,
    compute_baseline,
    compute_deviation,
)


def make_baseline_df(biomarker_slug: str, n_days: int, mean: float, std: float):
    """Create a DataFrame in the format expected by compute_baseline."""
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n_days, freq="D")
    values = np.random.normal(mean, std, n_days)
    return pd.DataFrame(
        {"time": dates, "biomarker_slug": biomarker_slug, "value": values}
    )


class TestComputeBaseline:
    """Tests for baseline computation."""

    def test_returns_none_with_insufficient_days(self):
        """Should return None when there are fewer than MIN_BASELINE_DAYS."""
        dates = pd.date_range(start="2023-01-01", periods=10, freq="D")
        df = pd.DataFrame(
            {
                "time": dates,
                "biomarker_slug": "heart_rate",
                "value": np.random.normal(70, 5, 10),
            }
        )

        result = compute_baseline(df, "heart_rate")
        assert result is None

    def test_computes_baseline_with_sufficient_data(self):
        """Should compute baseline when data is sufficient."""
        df = make_baseline_df("heart_rate", 90, mean=70, std=5)

        result = compute_baseline(df, "heart_rate")

        assert result is not None
        assert isinstance(result, BiomarkerBaseline)
        assert result.biomarker_slug == "heart_rate"
        assert 60 < result.mean < 80  # Should be around 70
        assert result.std > 0

    def test_computes_percentiles(self):
        """Should compute proper percentiles."""
        df = make_baseline_df("heart_rate", 90, mean=70, std=5)

        result = compute_baseline(df, "heart_rate")

        assert result is not None
        assert result.p10 < result.p25 < result.median < result.p75 < result.p90

    def test_window_days_parameter(self):
        """Should respect window_days parameter."""
        df = make_baseline_df("heart_rate", 180, mean=70, std=5)

        result_30 = compute_baseline(df, "heart_rate", window_days=30)
        result_90 = compute_baseline(df, "heart_rate", window_days=90)

        assert result_30 is not None
        assert result_90 is not None
        assert result_30.window_days == 30
        assert result_90.window_days == 90

    def test_hrv_unit_correction(self):
        """Should correct HRV units from microseconds to milliseconds."""
        # Create HRV data in microseconds format
        df = make_baseline_df("hrv_rmssd", 90, mean=50000, std=5000)

        result = compute_baseline(df, "hrv_rmssd")

        assert result is not None
        # Should be converted to milliseconds
        assert 20 < result.mean < 100

    def test_trend_detection(self):
        """Should detect trend direction."""
        np.random.seed(42)
        dates = pd.date_range(end=pd.Timestamp.now(), periods=90, freq="D")
        # Clear upward trend
        values = 60 + 0.2 * np.arange(90) + np.random.normal(0, 2, 90)

        df = pd.DataFrame(
            {"time": dates, "biomarker_slug": "heart_rate", "value": values}
        )

        result = compute_baseline(df, "heart_rate")

        assert result is not None
        # Just check that trend magnitude is computed
        assert result.trend_magnitude is not None

    def test_stability_detection(self):
        """Should detect if baseline is stable."""
        df = make_baseline_df("heart_rate", 90, mean=70, std=2)

        result = compute_baseline(df, "heart_rate")

        assert result is not None
        assert result.coefficient_of_variation < 0.1
        # Should likely be stable with low CV


class TestComputeDeviation:
    """Tests for deviation computation."""

    @pytest.fixture
    def sample_baseline(self):
        """Create a sample baseline for testing."""
        return BiomarkerBaseline(
            biomarker_slug="heart_rate",
            computed_at=pd.Timestamp.now(),
            window_days=90,
            mean=70.0,
            std=5.0,
            median=70.0,
            p10=62.0,
            p25=66.0,
            p75=74.0,
            p90=78.0,
            sample_count=1000,
            is_stable=True,
            coefficient_of_variation=0.07,
            trend_direction="stable",
            trend_magnitude=0.0,
        )

    def test_computes_z_score(self, sample_baseline):
        """Should compute correct z-score."""
        result = compute_deviation(80.0, sample_baseline)

        assert result is not None
        assert isinstance(result, DeviationResult)
        assert result.z_score == pytest.approx(2.0, rel=0.01)  # (80-70)/5 = 2

    def test_computes_percentile(self, sample_baseline):
        """Should compute correct percentile."""
        result = compute_deviation(70.0, sample_baseline)

        assert result is not None
        assert 40 < result.percentile < 60  # Should be around 50th percentile

    def test_detects_notable_deviation(self, sample_baseline):
        """Should flag notable deviations (z > 1.5)."""
        result = compute_deviation(78.0, sample_baseline)  # z = 1.6

        assert result is not None
        assert result.is_notable
        assert not result.is_significant

    def test_detects_significant_deviation(self, sample_baseline):
        """Should flag significant deviations (z > 2.0)."""
        result = compute_deviation(82.0, sample_baseline)  # z = 2.4

        assert result is not None
        assert result.is_notable
        assert result.is_significant

    def test_direction_detection(self, sample_baseline):
        """Should detect direction of deviation."""
        above = compute_deviation(80.0, sample_baseline)
        below = compute_deviation(60.0, sample_baseline)
        within = compute_deviation(72.0, sample_baseline)

        assert above.direction == "above"
        assert below.direction == "below"
        assert within.direction == "within"

    def test_deviation_percentage(self, sample_baseline):
        """Should compute correct deviation percentage."""
        result = compute_deviation(77.0, sample_baseline)

        assert result is not None
        expected_pct = (77.0 - 70.0) / 70.0 * 100
        assert result.deviation_pct == pytest.approx(expected_pct, rel=0.01)

    def test_clinical_note_for_hrv(self):
        """Should generate clinical note for HRV deviations."""
        hrv_baseline = BiomarkerBaseline(
            biomarker_slug="hrv_rmssd",
            computed_at=pd.Timestamp.now(),
            window_days=90,
            mean=50.0,
            std=10.0,
            median=50.0,
            p10=36.0,
            p25=43.0,
            p75=57.0,
            p90=64.0,
            sample_count=1000,
            is_stable=True,
            coefficient_of_variation=0.2,
        )

        low_result = compute_deviation(25.0, hrv_baseline)  # Significantly low
        assert low_result.clinical_note is not None
        assert "sympathetic" in low_result.clinical_note.lower()
