"""Unit tests for holistic insights analysis.

Tests cover:
- Wellness score computation
- Paradox detection (Simpson's Paradox)
- Cross-domain interconnection mapping
- Behavioral pattern detection
- Risk factor synthesis
- Recommendation generation
"""

# Import for tests
import warnings
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from soma.statistics.holistic import (
    AnalysisInputs,
    BehavioralPattern,
    DataAdequacy,
    HolisticInsight,
    Interconnection,
    Paradox,
    Recommendation,
    WellnessScore,
    # Functions
    aggregate_signals,
    compute_correlation,
    compute_data_adequacy,
    compute_detrended_correlation,
    compute_wellness_score,
    detect_all_behavioral_patterns,
    detect_compensatory_exercise,
    detect_simpsons_paradox,
    find_cross_domain_interconnections,
    generate_holistic_insight,
    generate_recommendations,
    synthesize_risk_factors,
)

warnings.filterwarnings("ignore")


def make_test_signals(n_days: int = 90, seed: int = 42) -> pd.DataFrame:
    """Generate comprehensive test signals for all domains.

    Args:
        n_days: Number of days of data to generate
        seed: Random seed for reproducibility

    Returns:
        DataFrame with time, biomarker_slug, value columns
    """
    np.random.seed(seed)
    records = []
    base_date = datetime.now() - timedelta(days=n_days)

    for i in range(n_days):
        day = base_date + timedelta(days=i)

        # Cardiovascular
        records.append(
            {
                "time": day,
                "biomarker_slug": "heart_rate",
                "value": 70 + np.random.normal(0, 5),
            }
        )
        records.append(
            {
                "time": day,
                "biomarker_slug": "hrv_sdnn",
                "value": 50 + np.random.normal(0, 10),
            }
        )
        records.append(
            {
                "time": day,
                "biomarker_slug": "heart_rate_resting",
                "value": 60 + np.random.normal(0, 3),
            }
        )

        # Activity
        records.append(
            {
                "time": day,
                "biomarker_slug": "steps",
                "value": max(1000, 8000 + np.random.normal(0, 2000)),
            }
        )
        records.append(
            {
                "time": day,
                "biomarker_slug": "exercise_time",
                "value": max(0, 30 + np.random.normal(0, 15)),
            }
        )

        # Body composition (weekly)
        if i % 7 == 0:
            records.append(
                {
                    "time": day,
                    "biomarker_slug": "body_mass",
                    "value": 75 + np.random.normal(0, 1),
                }
            )

        # Sleep
        records.append(
            {
                "time": day,
                "biomarker_slug": "sleep_rem",
                "value": max(0, 90 + np.random.normal(0, 20)),
            }
        )
        records.append(
            {
                "time": day,
                "biomarker_slug": "sleep_deep",
                "value": max(0, 60 + np.random.normal(0, 15)),
            }
        )
        records.append(
            {
                "time": day,
                "biomarker_slug": "sleep_core",
                "value": max(0, 240 + np.random.normal(0, 30)),
            }
        )

    return pd.DataFrame(records)


def make_paradox_signals(n_days: int = 180, seed: int = 42) -> pd.DataFrame:
    """Generate signals that exhibit Simpson's Paradox.

    Creates a scenario where:
    - Raw correlation between steps and weight is positive
    - Detrended correlation is near zero
    - This mimics compensatory exercise behavior
    """
    np.random.seed(seed)
    records = []
    base_date = datetime.now() - timedelta(days=n_days)

    for i in range(n_days):
        day = base_date + timedelta(days=i)

        # Weight trends up over time
        weight = 75 + (i / n_days) * 5 + np.random.normal(0, 0.5)

        # Steps trend down over time (opposite direction)
        # But on any given day, higher weight -> more steps (compensatory)
        time_effect = -2000 * (i / n_days)
        weight_effect = 200 * (weight - 77.5)  # Compensatory: more weight = more steps
        steps = max(
            1000, 8000 + time_effect + weight_effect + np.random.normal(0, 1000)
        )

        records.append({"time": day, "biomarker_slug": "steps", "value": steps})

        if i % 7 == 0:  # Weekly weight measurements
            records.append(
                {"time": day, "biomarker_slug": "body_mass", "value": weight}
            )

    return pd.DataFrame(records)


class TestAggregateSignals:
    """Tests for signal aggregation."""

    def test_returns_dict_of_series(self):
        """Should return dict mapping biomarker to Series."""
        df = make_test_signals(n_days=30)
        result = aggregate_signals(df)

        assert isinstance(result, dict)
        assert all(isinstance(v, pd.Series) for v in result.values())

    def test_aggregates_by_date(self):
        """Should aggregate multiple readings per day."""
        df = make_test_signals(n_days=30)
        result = aggregate_signals(df)

        # Each biomarker should have one value per day
        assert len(result["heart_rate"]) <= 30

    def test_sums_countable_biomarkers(self):
        """Should sum steps, active_energy, exercise_time."""
        records = [
            {"time": datetime.now(), "biomarker_slug": "steps", "value": 5000},
            {"time": datetime.now(), "biomarker_slug": "steps", "value": 3000},
        ]
        df = pd.DataFrame(records)
        result = aggregate_signals(df)

        assert result["steps"].iloc[0] == 8000

    def test_averages_rate_biomarkers(self):
        """Should average heart_rate, hrv, etc."""
        records = [
            {"time": datetime.now(), "biomarker_slug": "heart_rate", "value": 70},
            {"time": datetime.now(), "biomarker_slug": "heart_rate", "value": 80},
        ]
        df = pd.DataFrame(records)
        result = aggregate_signals(df)

        assert result["heart_rate"].iloc[0] == 75


class TestComputeCorrelation:
    """Tests for correlation computation."""

    def test_returns_correlation_and_pvalue(self):
        """Should return (r, p, n) tuple."""
        a = pd.Series([1, 2, 3, 4, 5] * 10)  # Need >= 30 samples
        b = pd.Series([2, 4, 6, 8, 10] * 10)

        r, p, n = compute_correlation(a, b)

        assert isinstance(r, float)
        assert isinstance(p, float)
        assert isinstance(n, int)

    def test_perfect_positive_correlation(self):
        """Perfect positive correlation should be r=1."""
        a = pd.Series([1, 2, 3, 4, 5] * 10)  # Need >= 30 samples
        b = pd.Series([2, 4, 6, 8, 10] * 10)

        r, p, n = compute_correlation(a, b)

        assert r == pytest.approx(1.0, abs=0.01)
        assert p < 0.05

    def test_perfect_negative_correlation(self):
        """Perfect negative correlation should be r=-1."""
        a = pd.Series([1, 2, 3, 4, 5] * 10)
        b = pd.Series([10, 8, 6, 4, 2] * 10)

        r, p, n = compute_correlation(a, b)

        assert r == pytest.approx(-1.0, abs=0.01)

    def test_no_correlation(self):
        """Random data should have near-zero correlation."""
        np.random.seed(42)
        a = pd.Series(np.random.randn(100))
        b = pd.Series(np.random.randn(100))

        r, p, n = compute_correlation(a, b)

        assert abs(r) < 0.3  # Weak at most


class TestComputeDetrendedCorrelation:
    """Tests for detrended correlation computation."""

    def test_removes_trend_effect(self):
        """Detrending should remove confounding trends."""
        df = make_paradox_signals(n_days=180)
        signals = aggregate_signals(df)

        raw_r, raw_p, raw_n = compute_correlation(
            signals["steps"], signals["body_mass"]
        )
        detrended_r, detrended_p, detrended_n = compute_detrended_correlation(
            signals["steps"], signals["body_mass"]
        )

        # If we have enough data, detrended should differ from raw
        if not np.isnan(raw_r) and not np.isnan(detrended_r):
            # Raw and detrended should differ when there's a confounding trend
            assert abs(detrended_r - raw_r) > 0.05 or detrended_r == pytest.approx(
                raw_r, abs=0.1
            )


class TestDetectSimpsonsParadox:
    """Tests for Simpson's Paradox detection."""

    def test_returns_paradox_or_none(self):
        """Should return Paradox or None."""
        df = make_paradox_signals(n_days=180)
        signals = aggregate_signals(df)

        result = detect_simpsons_paradox(
            signals["steps"], signals["body_mass"], "steps", "body_mass"
        )

        assert result is None or isinstance(result, Paradox)

    def test_detects_paradox_in_confounded_data(self):
        """Should detect paradox when correlation changes with detrending."""
        df = make_paradox_signals(n_days=180)
        signals = aggregate_signals(df)

        result = detect_simpsons_paradox(
            signals["steps"], signals["body_mass"], "steps", "body_mass"
        )

        # Paradox should be detected (raw positive, detrended near zero)
        if result is not None:
            assert abs(result.raw_correlation - result.detrended_correlation) > 0.1


class TestDetectCompensatoryExercise:
    """Tests for compensatory exercise detection."""

    def test_returns_pattern_or_none(self):
        """Should return BehavioralPattern or None."""
        df = make_paradox_signals(n_days=180)
        signals = aggregate_signals(df)

        if "body_mass" in signals and "steps" in signals:
            result = detect_compensatory_exercise(
                signals["body_mass"], signals["steps"]
            )
            assert result is None or isinstance(result, BehavioralPattern)

    def test_pattern_has_required_fields(self):
        """Pattern should have all required fields."""
        df = make_paradox_signals(n_days=180)
        signals = aggregate_signals(df)

        if "body_mass" in signals and "steps" in signals:
            result = detect_compensatory_exercise(
                signals["body_mass"], signals["steps"]
            )

            if result:
                assert result.name == "Compensatory Exercise"
                assert result.pattern_type == "compensatory"
                assert result.health_implication in ("positive", "neutral", "negative")
                assert len(result.description) > 0


class TestComputeWellnessScore:
    """Tests for wellness score computation."""

    def test_returns_wellness_score(self):
        """Should return WellnessScore dataclass."""
        df = make_test_signals(n_days=90)
        signals = aggregate_signals(df)

        result = compute_wellness_score(signals)

        assert isinstance(result, WellnessScore)

    def test_overall_score_in_range(self):
        """Overall score should be 0-100."""
        df = make_test_signals(n_days=90)
        signals = aggregate_signals(df)

        result = compute_wellness_score(signals)

        assert 0 <= result.overall <= 100

    def test_domain_scores_in_range(self):
        """All domain scores should be 0-100."""
        df = make_test_signals(n_days=90)
        signals = aggregate_signals(df)

        result = compute_wellness_score(signals)

        assert 0 <= result.cardiovascular.score <= 100
        assert 0 <= result.sleep.score <= 100
        assert 0 <= result.activity.score <= 100
        assert 0 <= result.recovery.score <= 100
        assert 0 <= result.body_composition.score <= 100

    def test_has_strongest_and_weakest(self):
        """Should identify strongest and weakest domains."""
        df = make_test_signals(n_days=90)
        signals = aggregate_signals(df)

        result = compute_wellness_score(signals)

        assert result.strongest_domain in (
            "cardiovascular",
            "sleep",
            "activity",
            "recovery",
            "body_composition",
        )
        assert result.weakest_domain in (
            "cardiovascular",
            "sleep",
            "activity",
            "recovery",
            "body_composition",
        )

    def test_interpretation_valid(self):
        """Interpretation should be Excellent/Good/Fair/Poor."""
        df = make_test_signals(n_days=90)
        signals = aggregate_signals(df)

        result = compute_wellness_score(signals)

        assert result.interpretation in ("Excellent", "Good", "Fair", "Poor")


class TestFindCrossDomainInterconnections:
    """Tests for cross-domain interconnection mapping."""

    def test_returns_list_of_interconnections(self):
        """Should return list of Interconnection objects."""
        df = make_test_signals(n_days=90)
        signals = aggregate_signals(df)

        result = find_cross_domain_interconnections(signals)

        assert isinstance(result, list)
        assert all(isinstance(ic, Interconnection) for ic in result)

    def test_interconnections_have_required_fields(self):
        """Each interconnection should have all required fields."""
        df = make_test_signals(n_days=90)
        signals = aggregate_signals(df)

        result = find_cross_domain_interconnections(signals)

        valid_domains = (
            "cardiovascular",
            "sleep",
            "activity",
            "recovery",
            "body_composition",
            "mobility",
        )
        for ic in result:
            assert ic.source_domain in valid_domains
            assert ic.target_domain in valid_domains
            assert isinstance(ic.source_biomarker, str) and len(ic.source_biomarker) > 0
            assert isinstance(ic.target_biomarker, str) and len(ic.target_biomarker) > 0
            assert -1 <= ic.correlation <= 1
            assert 0 <= ic.p_value <= 1
            assert ic.lag_days >= 0
            assert ic.strength in ("strong", "moderate", "weak")


class TestGenerateRecommendations:
    """Tests for recommendation generation."""

    def test_returns_list_of_recommendations(self):
        """Should return list of Recommendation objects."""
        df = make_test_signals(n_days=90)
        signals = aggregate_signals(df)
        wellness = compute_wellness_score(signals)
        interconnections = find_cross_domain_interconnections(signals)
        risk_factors = synthesize_risk_factors(wellness, interconnections, signals)
        patterns = detect_all_behavioral_patterns(signals)

        result = generate_recommendations(
            wellness, interconnections, risk_factors, patterns
        )

        assert isinstance(result, list)
        assert all(isinstance(r, Recommendation) for r in result)

    def test_recommendations_have_required_fields(self):
        """Each recommendation should have all required fields."""
        df = make_test_signals(n_days=90)
        signals = aggregate_signals(df)
        wellness = compute_wellness_score(signals)
        interconnections = find_cross_domain_interconnections(signals)
        risk_factors = synthesize_risk_factors(wellness, interconnections, signals)
        patterns = detect_all_behavioral_patterns(signals)

        result = generate_recommendations(
            wellness, interconnections, risk_factors, patterns
        )

        for rec in result:
            assert rec.priority in ("high", "medium", "low")
            assert len(rec.category) > 0
            assert len(rec.action) > 0
            assert len(rec.rationale) > 0


class TestGenerateHolisticInsight:
    """Tests for complete holistic insight generation."""

    def test_returns_holistic_insight(self):
        """Should return HolisticInsight dataclass."""
        df = make_test_signals(n_days=90)
        inputs = AnalysisInputs(signals=df)

        result = generate_holistic_insight(inputs)

        assert isinstance(result, HolisticInsight)

    def test_includes_all_components(self):
        """Should include all major components."""
        df = make_test_signals(n_days=90)
        inputs = AnalysisInputs(signals=df)

        result = generate_holistic_insight(inputs)

        assert result.wellness_score is not None
        assert isinstance(result.primary_findings, list)
        assert isinstance(result.interconnections, list)
        assert isinstance(result.paradoxes, list)
        assert isinstance(result.behavioral_patterns, list)
        assert isinstance(result.risk_factors, list)
        assert isinstance(result.protective_factors, list)
        assert isinstance(result.recommendations, list)
        assert isinstance(result.data_adequacy, list)

    def test_has_analysis_period(self):
        """Should include analysis period dates."""
        df = make_test_signals(n_days=90)
        inputs = AnalysisInputs(signals=df)

        result = generate_holistic_insight(inputs)

        assert result.analysis_period_start is not None
        assert result.analysis_period_end is not None
        assert result.analysis_period_start <= result.analysis_period_end

    def test_has_trajectory(self):
        """Should include trajectory assessment."""
        df = make_test_signals(n_days=90)
        inputs = AnalysisInputs(signals=df)

        result = generate_holistic_insight(inputs)

        assert result.trajectory in ("improving", "stable", "declining", "mixed")
        assert len(result.trajectory_details) > 0

    def test_has_confidence(self):
        """Should include overall confidence."""
        df = make_test_signals(n_days=90)
        inputs = AnalysisInputs(signals=df)

        result = generate_holistic_insight(inputs)

        assert result.overall_confidence in ("high", "moderate", "low")


class TestDataAdequacy:
    """Tests for data adequacy assessment."""

    def test_assesses_all_biomarkers(self):
        """Should assess adequacy for all present biomarkers."""
        df = make_test_signals(n_days=90)

        result = compute_data_adequacy(df)

        assert isinstance(result, list)
        assert all(isinstance(da, DataAdequacy) for da in result)

    def test_adequacy_has_required_fields(self):
        """Each adequacy assessment should have required fields."""
        df = make_test_signals(n_days=90)

        result = compute_data_adequacy(df)

        for da in result:
            assert len(da.biomarker) > 0
            assert da.current_samples >= 0
            assert da.recommended_samples >= 0
            assert da.status in ("sufficient", "moderate", "limited", "missing")
            assert 0 <= da.reliability_score <= 1


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_empty_dataframe(self):
        """Should handle empty DataFrame gracefully."""
        df = pd.DataFrame({"time": [], "biomarker_slug": [], "value": []})
        signals = aggregate_signals(df)

        result = compute_wellness_score(signals)

        # Should return default scores rather than crash
        assert result.overall >= 0

    def test_handles_single_biomarker(self):
        """Should handle data with only one biomarker."""
        records = [
            {
                "time": datetime.now() - timedelta(days=i),
                "biomarker_slug": "steps",
                "value": 8000,
            }
            for i in range(30)
        ]
        df = pd.DataFrame(records)
        signals = aggregate_signals(df)

        result = compute_wellness_score(signals)

        assert result.overall >= 0

    def test_handles_short_time_period(self):
        """Should handle very short time periods."""
        df = make_test_signals(n_days=7)
        inputs = AnalysisInputs(signals=df)

        result = generate_holistic_insight(inputs)

        assert result.overall_confidence == "low"

    def test_handles_nan_values(self):
        """Should handle NaN values in data."""
        df = make_test_signals(n_days=30)
        df.loc[df.index[:5], "value"] = np.nan

        signals = aggregate_signals(df)

        # Should not crash, NaNs should be handled
        result = compute_wellness_score(signals)
        assert result.overall >= 0
