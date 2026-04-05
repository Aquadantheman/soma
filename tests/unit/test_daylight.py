"""Unit tests for daylight exposure analysis."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from soma.statistics.daylight import (
    DailyDaylight,
    DaylightBaseline,
    analyze_daylight_trend,
    compute_daily_daylight,
    compute_daylight_baseline,
    compute_daylight_deviation,
    compute_daylight_sleep_correlation,
    generate_daylight_report,
)


def make_daylight_data(n_days: int = 30, seed: int = 42) -> pd.DataFrame:
    """Generate realistic daylight exposure data for testing."""
    np.random.seed(seed)

    records = []
    base_date = datetime.now() - timedelta(days=n_days)

    for day in range(n_days):
        day_date = base_date + timedelta(days=day)

        # Morning exposure (6am-10am): 0-60 min
        morning_min = np.random.exponential(20)  # Most days some, few days lots
        if np.random.random() < 0.7:  # 70% chance of morning exposure
            for chunk in range(int(morning_min // 10) + 1):
                records.append(
                    {
                        "time": day_date.replace(hour=7 + chunk % 3),
                        "biomarker_slug": "time_in_daylight",
                        "value": min(10, morning_min - chunk * 10),
                    }
                )

        # Midday exposure (10am-2pm): 0-45 min
        midday_min = np.random.normal(25, 15)
        midday_min = max(0, midday_min)
        if midday_min > 0:
            records.append(
                {
                    "time": day_date.replace(hour=12),
                    "biomarker_slug": "time_in_daylight",
                    "value": midday_min,
                }
            )

        # Afternoon exposure (2pm+): 0-30 min
        afternoon_min = np.random.normal(15, 10)
        afternoon_min = max(0, afternoon_min)
        if afternoon_min > 0:
            records.append(
                {
                    "time": day_date.replace(hour=15),
                    "biomarker_slug": "time_in_daylight",
                    "value": afternoon_min,
                }
            )

    return pd.DataFrame(records)


def make_sleep_data(n_nights: int = 30, seed: int = 42) -> pd.DataFrame:
    """Generate sleep data that correlates with daylight."""
    np.random.seed(seed)

    records = []
    base_date = datetime.now() - timedelta(days=n_nights)

    for day in range(n_nights):
        night_date = base_date + timedelta(days=day)
        bed_time = night_date.replace(hour=22)

        # Simulate sleep stages
        total_sleep = np.random.normal(420, 30)
        rem_min = total_sleep * np.random.uniform(0.18, 0.25)
        deep_min = total_sleep * np.random.uniform(0.13, 0.20)
        core_min = total_sleep - rem_min - deep_min
        in_bed_min = total_sleep * np.random.uniform(1.05, 1.15)

        for slug, value in [
            ("sleep_rem", rem_min),
            ("sleep_deep", deep_min),
            ("sleep_core", core_min),
            ("sleep_in_bed", in_bed_min),
        ]:
            records.append({"time": bed_time, "biomarker_slug": slug, "value": value})

    return pd.DataFrame(records)


class TestComputeDailyDaylight:
    """Tests for daily daylight computation."""

    def test_computes_daily_totals(self):
        """Should compute daily totals from records."""
        df = make_daylight_data(n_days=10)
        daily = compute_daily_daylight(df)

        assert len(daily) <= 10  # May have fewer if no exposure some days
        for day in daily:
            assert isinstance(day, DailyDaylight)
            assert day.total_min >= 0

    def test_segments_by_time_of_day(self):
        """Should separate morning, midday, afternoon."""
        df = make_daylight_data(n_days=30)
        daily = compute_daily_daylight(df)

        for day in daily:
            # Total should equal sum of segments
            segment_sum = day.morning_min + day.midday_min + day.afternoon_min
            assert abs(day.total_min - segment_sum) < 0.01

    def test_morning_exposure_flag(self):
        """Should flag days with >=20 min morning light."""
        df = make_daylight_data(n_days=30, seed=123)
        daily = compute_daily_daylight(df)

        for day in daily:
            if day.morning_min >= 20:
                assert day.has_morning_exposure
            else:
                assert not day.has_morning_exposure

    def test_returns_empty_for_no_data(self):
        """Should return empty list for no data."""
        df = pd.DataFrame(columns=["time", "biomarker_slug", "value"])
        daily = compute_daily_daylight(df)
        assert daily == []


class TestComputeDaylightBaseline:
    """Tests for daylight baseline computation."""

    def test_computes_baseline_with_sufficient_data(self):
        """Should compute baseline with enough days."""
        df = make_daylight_data(n_days=60)
        baseline = compute_daylight_baseline(df, window_days=60)

        assert baseline is not None
        assert isinstance(baseline, DaylightBaseline)
        assert baseline.n_days >= 14

    def test_includes_all_metrics(self):
        """Should include all daylight metrics."""
        df = make_daylight_data(n_days=60)
        baseline = compute_daylight_baseline(df, window_days=60)

        assert baseline is not None
        assert baseline.total_daylight is not None
        assert baseline.morning_daylight is not None
        assert baseline.midday_daylight is not None
        assert baseline.afternoon_daylight is not None

    def test_returns_none_with_insufficient_data(self):
        """Should return None with fewer than min_days."""
        df = make_daylight_data(n_days=5)
        baseline = compute_daylight_baseline(df, min_days=14)
        assert baseline is None

    def test_confidence_intervals_valid(self):
        """Confidence intervals should be valid."""
        df = make_daylight_data(n_days=60)
        baseline = compute_daylight_baseline(df, window_days=60)

        assert baseline is not None
        # CI lower should be less than mean, mean less than CI upper
        ci = baseline.total_daylight
        assert ci.ci_lower <= ci.mean <= ci.ci_upper

    def test_consistency_score_computed(self):
        """Should compute consistency score."""
        df = make_daylight_data(n_days=60)
        baseline = compute_daylight_baseline(df, window_days=60)

        assert baseline is not None
        assert 0 <= baseline.consistency_score <= 100

    def test_morning_light_percentage(self):
        """Should compute percentage of days with morning light."""
        df = make_daylight_data(n_days=60)
        baseline = compute_daylight_baseline(df, window_days=60)

        assert baseline is not None
        assert 0 <= baseline.pct_days_with_morning_light <= 100


class TestComputeDaylightDeviation:
    """Tests for deviation computation."""

    @pytest.fixture
    def baseline_and_day(self):
        """Create a baseline and test day."""
        df = make_daylight_data(n_days=60)
        baseline = compute_daylight_baseline(df, window_days=60)
        days = compute_daily_daylight(df)
        return baseline, days[-1]

    def test_computes_z_scores(self, baseline_and_day):
        """Should compute z-scores."""
        baseline, day = baseline_and_day
        deviation = compute_daylight_deviation(day, baseline)

        assert deviation is not None
        assert isinstance(deviation.total_z, float)
        assert isinstance(deviation.morning_z, float)

    def test_detects_low_exposure(self):
        """Should flag low exposure days."""
        df = make_daylight_data(n_days=60)
        baseline = compute_daylight_baseline(df, window_days=60)

        # Create a low-exposure day
        low_day = DailyDaylight(
            date=datetime.now().date(),
            total_min=5,  # Very low
            morning_min=0,
            midday_min=3,
            afternoon_min=2,
            has_morning_exposure=False,
        )

        deviation = compute_daylight_deviation(low_day, baseline)

        assert deviation is not None
        assert deviation.is_low or deviation.is_no_morning_light
        assert deviation.is_notable


class TestAnalyzeDaylightTrend:
    """Tests for daylight trend analysis."""

    def test_analyzes_trend(self):
        """Should analyze trend in daylight exposure."""
        df = make_daylight_data(n_days=60)
        trend = analyze_daylight_trend(df, period_days=30)

        assert trend is not None
        assert isinstance(trend.slope, float)
        assert 0 <= trend.p_value <= 1
        assert 0 <= trend.r_squared <= 1

    def test_detects_direction(self):
        """Should detect trend direction."""
        df = make_daylight_data(n_days=60)
        trend = analyze_daylight_trend(df, period_days=30)

        assert trend is not None
        assert trend.direction in ["increasing", "decreasing", "stable"]

    def test_returns_none_with_insufficient_data(self):
        """Should return None with insufficient data."""
        df = make_daylight_data(n_days=5)
        trend = analyze_daylight_trend(df, period_days=30)
        assert trend is None


class TestComputeDaylightSleepCorrelation:
    """Tests for daylight-sleep correlation."""

    def test_computes_correlation(self):
        """Should compute correlation between daylight and sleep."""
        daylight_df = make_daylight_data(n_days=60)
        sleep_df = make_sleep_data(n_nights=60)

        corr = compute_daylight_sleep_correlation(
            daylight_df, sleep_df, sleep_metric="total_sleep_min", lag_days=0
        )

        assert corr is not None
        assert -1 <= corr.correlation <= 1
        assert 0 <= corr.p_value <= 1
        assert corr.n_pairs >= 10

    def test_handles_lag(self):
        """Should handle lagged correlations."""
        daylight_df = make_daylight_data(n_days=60)
        sleep_df = make_sleep_data(n_nights=60)

        corr_same = compute_daylight_sleep_correlation(
            daylight_df, sleep_df, sleep_metric="total_sleep_min", lag_days=0
        )

        corr_next = compute_daylight_sleep_correlation(
            daylight_df, sleep_df, sleep_metric="total_sleep_min", lag_days=1
        )

        assert corr_same is not None
        assert corr_next is not None
        # Correlations can be different
        assert corr_same.lag_days == 0
        assert corr_next.lag_days == 1

    def test_returns_none_with_insufficient_data(self):
        """Should return None with insufficient overlapping data."""
        daylight_df = make_daylight_data(n_days=5)
        sleep_df = make_sleep_data(n_nights=5)

        corr = compute_daylight_sleep_correlation(
            daylight_df, sleep_df, sleep_metric="total_sleep_min", lag_days=0
        )

        assert corr is None


class TestGenerateDaylightReport:
    """Tests for complete daylight report generation."""

    def test_generates_report(self):
        """Should generate complete report."""
        df = make_daylight_data(n_days=90)
        report = generate_daylight_report(df)

        assert report is not None
        assert report.baseline is not None
        assert len(report.recent_days) > 0
        assert report.trend is not None

    def test_includes_sleep_correlations(self):
        """Should include sleep correlations when sleep data provided."""
        daylight_df = make_daylight_data(n_days=90)
        sleep_df = make_sleep_data(n_nights=90)

        report = generate_daylight_report(daylight_df, sleep_df=sleep_df)

        assert report is not None
        # May or may not have significant correlations, but list should exist
        assert isinstance(report.sleep_correlations, list)

    def test_includes_concerns_and_insights(self):
        """Should include concerns and insights lists."""
        df = make_daylight_data(n_days=90)
        report = generate_daylight_report(df)

        assert isinstance(report.concerns, list)
        assert isinstance(report.insights, list)

    def test_computes_30d_averages(self):
        """Should compute 30-day averages."""
        df = make_daylight_data(n_days=90)
        report = generate_daylight_report(df)

        assert report.avg_daily_min_30d is not None
        assert report.avg_morning_min_30d is not None
        assert report.pct_days_morning_light_30d is not None

    def test_handles_no_data(self):
        """Should handle empty data gracefully."""
        df = pd.DataFrame(columns=["time", "biomarker_slug", "value"])
        report = generate_daylight_report(df)

        assert report is not None
        assert report.baseline is None
        assert report.recent_days == []


class TestDaylightRecommendations:
    """Tests for clinical validity of daylight recommendations."""

    def test_flags_low_daily_exposure(self):
        """Should flag average daily exposure below 30 min."""
        # Create data with very low exposure
        np.random.seed(42)
        records = []
        base_date = datetime.now() - timedelta(days=60)

        for day in range(60):
            day_date = base_date + timedelta(days=day)
            records.append(
                {
                    "time": day_date.replace(hour=12),
                    "biomarker_slug": "time_in_daylight",
                    "value": np.random.uniform(5, 15),  # Very low
                }
            )

        df = pd.DataFrame(records)
        report = generate_daylight_report(df)

        assert report is not None
        assert report.baseline is not None
        assert report.baseline.total_daylight.mean < 30
        # Should have a concern about low exposure
        assert any(
            "daylight" in c.lower() or "low" in c.lower() for c in report.concerns
        )

    def test_flags_low_morning_light(self):
        """Should flag when less than 50% of days have morning light."""
        # Create data with no morning exposure
        np.random.seed(42)
        records = []
        base_date = datetime.now() - timedelta(days=60)

        for day in range(60):
            day_date = base_date + timedelta(days=day)
            # Only afternoon exposure
            records.append(
                {
                    "time": day_date.replace(hour=15),
                    "biomarker_slug": "time_in_daylight",
                    "value": np.random.uniform(30, 60),
                }
            )

        df = pd.DataFrame(records)
        report = generate_daylight_report(df)

        assert report is not None
        assert report.baseline is not None
        assert report.baseline.pct_days_with_morning_light < 50
        # Should have a concern about morning light
        assert any("morning" in c.lower() for c in report.concerns)

    def test_recognizes_good_patterns(self):
        """Should recognize healthy daylight patterns."""
        # Create data with good exposure
        np.random.seed(42)
        records = []
        base_date = datetime.now() - timedelta(days=60)

        for day in range(60):
            day_date = base_date + timedelta(days=day)
            # Good morning exposure
            records.append(
                {
                    "time": day_date.replace(hour=8),
                    "biomarker_slug": "time_in_daylight",
                    "value": np.random.uniform(25, 40),
                }
            )
            # Midday exposure
            records.append(
                {
                    "time": day_date.replace(hour=12),
                    "biomarker_slug": "time_in_daylight",
                    "value": np.random.uniform(20, 35),
                }
            )

        df = pd.DataFrame(records)
        report = generate_daylight_report(df)

        assert report is not None
        assert report.baseline is not None
        assert report.baseline.is_sufficient
        # Should have insights about good patterns
        assert len(report.insights) > 0
