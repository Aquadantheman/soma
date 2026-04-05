"""Unit tests for sleep architecture analysis."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from soma.statistics.sleep import (
    NightlySleep,
    SleepArchitectureBaseline,
    analyze_sleep_trend,
    compute_nightly_sleep,
    compute_sleep_baseline,
    compute_sleep_deviation,
    generate_sleep_report,
)


def make_sleep_data(n_nights: int = 30, seed: int = 42) -> pd.DataFrame:
    """Generate realistic sleep stage data for testing."""
    np.random.seed(seed)

    records = []
    base_date = datetime.now() - timedelta(days=n_nights)

    for day in range(n_nights):
        night_date = base_date + timedelta(days=day)

        # Simulate a realistic night of sleep
        # Typical proportions: REM 20-25%, Deep 13-23%, Core 50-60%
        total_sleep = np.random.normal(420, 30)  # ~7 hours, std 30 min

        rem_min = total_sleep * np.random.uniform(0.18, 0.25)
        deep_min = total_sleep * np.random.uniform(0.13, 0.20)
        core_min = total_sleep - rem_min - deep_min
        in_bed_min = total_sleep * np.random.uniform(1.05, 1.15)  # Efficiency 85-95%

        # Create records for each stage
        # Bedtime around 10pm-midnight
        bed_time = night_date.replace(hour=22, minute=0) + timedelta(
            minutes=np.random.randint(0, 120)
        )

        # Sleep stages occur throughout the night
        # For simplicity, we'll just record total durations at bed_time
        stages = [
            ("sleep_rem", rem_min),
            ("sleep_deep", deep_min),
            ("sleep_core", core_min),
            ("sleep_in_bed", in_bed_min),
        ]

        for slug, value in stages:
            records.append({"time": bed_time, "biomarker_slug": slug, "value": value})

    return pd.DataFrame(records)


class TestComputeNightlySleep:
    """Tests for nightly sleep computation."""

    def test_computes_nightly_totals(self):
        """Should compute nightly totals from stage records."""
        df = make_sleep_data(n_nights=10)
        nights = compute_nightly_sleep(df)

        assert len(nights) == 10
        for night in nights:
            assert isinstance(night, NightlySleep)
            assert night.total_sleep_min > 0
            assert night.rem_min >= 0
            assert night.deep_min >= 0
            assert night.core_min >= 0

    def test_computes_percentages(self):
        """Should compute correct percentages."""
        df = make_sleep_data(n_nights=10)
        nights = compute_nightly_sleep(df)

        for night in nights:
            # Percentages should sum to ~100
            total_pct = night.rem_pct + night.deep_pct + night.core_pct
            assert 99 < total_pct < 101

    def test_computes_efficiency(self):
        """Should compute sleep efficiency."""
        df = make_sleep_data(n_nights=10)
        nights = compute_nightly_sleep(df)

        for night in nights:
            # Efficiency should be between 0 and 100
            assert 0 <= night.efficiency <= 100
            # For our test data, efficiency should be reasonable
            assert night.efficiency > 70

    def test_returns_empty_for_no_data(self):
        """Should return empty list for no data."""
        df = pd.DataFrame(columns=["time", "biomarker_slug", "value"])
        nights = compute_nightly_sleep(df)
        assert nights == []


class TestComputeSleepBaseline:
    """Tests for sleep baseline computation."""

    def test_computes_baseline_with_sufficient_data(self):
        """Should compute baseline with 90 days of data."""
        df = make_sleep_data(n_nights=90)
        baseline = compute_sleep_baseline(df, window_days=90)

        assert baseline is not None
        assert isinstance(baseline, SleepArchitectureBaseline)
        assert baseline.n_nights >= 14

    def test_includes_all_metrics(self):
        """Should include all sleep architecture metrics."""
        df = make_sleep_data(n_nights=60)
        baseline = compute_sleep_baseline(df, window_days=60)

        assert baseline is not None
        assert baseline.total_sleep is not None
        assert baseline.rem_pct is not None
        assert baseline.deep_pct is not None
        assert baseline.efficiency is not None

    def test_returns_none_with_insufficient_data(self):
        """Should return None with fewer than min_nights."""
        df = make_sleep_data(n_nights=10)
        baseline = compute_sleep_baseline(df, min_nights=14)
        assert baseline is None

    def test_confidence_intervals_valid(self):
        """Confidence intervals should be valid."""
        df = make_sleep_data(n_nights=60)
        baseline = compute_sleep_baseline(df, window_days=60)

        assert baseline is not None
        # CI lower should be less than mean, mean less than CI upper
        assert baseline.rem_pct.ci_lower < baseline.rem_pct.mean
        assert baseline.rem_pct.mean < baseline.rem_pct.ci_upper

    def test_consistency_score_computed(self):
        """Should compute consistency score."""
        df = make_sleep_data(n_nights=60)
        baseline = compute_sleep_baseline(df, window_days=60)

        assert baseline is not None
        assert 0 <= baseline.consistency_score <= 100


class TestComputeSleepDeviation:
    """Tests for deviation computation."""

    @pytest.fixture
    def baseline_and_night(self):
        """Create a baseline and test night."""
        df = make_sleep_data(n_nights=60)
        baseline = compute_sleep_baseline(df, window_days=60)
        nights = compute_nightly_sleep(df)
        return baseline, nights[-1]

    def test_computes_z_scores(self, baseline_and_night):
        """Should compute z-scores for all metrics."""
        baseline, night = baseline_and_night
        deviation = compute_sleep_deviation(night, baseline)

        assert deviation is not None
        assert isinstance(deviation.total_sleep_z, float)
        assert isinstance(deviation.rem_pct_z, float)
        assert isinstance(deviation.deep_pct_z, float)
        assert isinstance(deviation.efficiency_z, float)

    def test_detects_notable_deviation(self):
        """Should flag notable deviations."""
        df = make_sleep_data(n_nights=60)
        baseline = compute_sleep_baseline(df, window_days=60)

        # Create an abnormal night
        abnormal_night = NightlySleep(
            date=datetime.now().date(),
            rem_min=20,  # Very low REM
            deep_min=10,  # Very low deep
            core_min=200,
            in_bed_min=300,
            total_sleep_min=230,
            rem_pct=8.7,  # Very low
            deep_pct=4.3,  # Very low
            core_pct=87.0,
            efficiency=76.7,
        )

        deviation = compute_sleep_deviation(abnormal_night, baseline)

        assert deviation is not None
        assert deviation.is_notable
        assert deviation.is_rem_low or deviation.is_deep_low


class TestAnalyzeSleepTrend:
    """Tests for sleep trend analysis."""

    def test_analyzes_trend(self):
        """Should analyze trend in sleep metric."""
        df = make_sleep_data(n_nights=60)
        trend = analyze_sleep_trend(df, metric="rem_pct", period_days=30)

        assert trend is not None
        assert trend.metric == "rem_pct"
        assert isinstance(trend.slope, float)
        assert 0 <= trend.p_value <= 1
        assert 0 <= trend.r_squared <= 1

    def test_detects_direction(self):
        """Should detect trend direction."""
        df = make_sleep_data(n_nights=60)
        trend = analyze_sleep_trend(df, metric="efficiency", period_days=30)

        assert trend is not None
        assert trend.direction in [
            "improving",
            "declining",
            "stable",
            "increasing",
            "decreasing",
        ]

    def test_returns_none_with_insufficient_data(self):
        """Should return None with insufficient data."""
        df = make_sleep_data(n_nights=5)
        trend = analyze_sleep_trend(df, metric="rem_pct", period_days=30)
        assert trend is None


class TestGenerateSleepReport:
    """Tests for complete sleep report generation."""

    def test_generates_report(self):
        """Should generate complete report."""
        df = make_sleep_data(n_nights=90)
        report = generate_sleep_report(df)

        assert report is not None
        assert report.baseline is not None
        assert len(report.recent_nights) > 0
        assert len(report.trends) > 0

    def test_includes_concerns_and_insights(self):
        """Should include concerns and insights lists."""
        df = make_sleep_data(n_nights=90)
        report = generate_sleep_report(df)

        assert isinstance(report.concerns, list)
        assert isinstance(report.insights, list)

    def test_computes_30d_averages(self):
        """Should compute 30-day averages."""
        df = make_sleep_data(n_nights=90)
        report = generate_sleep_report(df)

        assert report.avg_rem_pct_30d is not None
        assert report.avg_deep_pct_30d is not None
        assert report.avg_efficiency_30d is not None

    def test_handles_insufficient_data(self):
        """Should handle case with no data gracefully."""
        df = pd.DataFrame(columns=["time", "biomarker_slug", "value"])
        report = generate_sleep_report(df)

        assert report is not None
        assert report.baseline is None
        assert report.recent_nights == []


class TestSleepArchitectureValidation:
    """Tests for clinical validity of sleep architecture."""

    def test_typical_rem_percentage(self):
        """REM should typically be 20-25% of total sleep."""
        # Use seed that produces typical values
        df = make_sleep_data(n_nights=60, seed=42)
        nights = compute_nightly_sleep(df)

        rem_pcts = [n.rem_pct for n in nights]
        avg_rem = np.mean(rem_pcts)

        # Average should be in typical range
        assert 15 < avg_rem < 30

    def test_typical_deep_percentage(self):
        """Deep sleep should typically be 13-23% of total sleep."""
        df = make_sleep_data(n_nights=60, seed=42)
        nights = compute_nightly_sleep(df)

        deep_pcts = [n.deep_pct for n in nights]
        avg_deep = np.mean(deep_pcts)

        # Average should be in typical range
        assert 10 < avg_deep < 30

    def test_efficiency_realistic(self):
        """Sleep efficiency should be realistic (70-100%)."""
        df = make_sleep_data(n_nights=60, seed=42)
        nights = compute_nightly_sleep(df)

        for night in nights:
            assert 70 <= night.efficiency <= 100
