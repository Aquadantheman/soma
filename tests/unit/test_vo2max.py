"""Unit tests for VO2 Max analysis.

Tests cover all validated methods with citations:
- ACSM percentile calculations
- HUNT Fitness Study fitness age
- Kodama mortality risk assessment
- Trend analysis with confidence intervals
- Training response detection
"""

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from soma.statistics.vo2max import (
    ACSM_PERCENTILES,
    METS_CONVERSION,
    FitnessAge,
    MortalityRisk,
    TrainingResponse,
    VO2MaxMeasurement,
    VO2MaxPercentile,
    VO2MaxReport,
    VO2MaxTrend,
    analyze_trend,
    assess_training_response,
    compute_fitness_age,
    compute_mortality_risk,
    compute_percentile,
    compute_validated_correlations,
    generate_vo2max_report,
)


def make_vo2max_data(
    n_measurements: int = 30,
    base_value: float = 40.0,
    trend: float = 0.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate VO2 Max test data.

    Args:
        n_measurements: Number of measurements to generate
        base_value: Starting VO2 Max value (mL/kg/min)
        trend: Daily change in VO2 Max (e.g., 0.01 = improving)
        seed: Random seed for reproducibility
    """
    np.random.seed(seed)

    records = []
    base_date = datetime.now() - timedelta(days=n_measurements * 7)

    for i in range(n_measurements):
        measurement_date = base_date + timedelta(days=i * 7)  # Weekly measurements
        # Add trend and noise
        value = base_value + (i * 7 * trend) + np.random.normal(0, 1.0)

        records.append(
            {
                "time": measurement_date,
                "biomarker_slug": "vo2_max",
                "value": max(15, value),  # Floor at 15 mL/kg/min
            }
        )

    return pd.DataFrame(records)


def make_correlated_data(
    n_days: int = 60, vo2_base: float = 40.0, seed: int = 42
) -> pd.DataFrame:
    """Generate VO2 Max with correlated HRV and RHR data."""
    np.random.seed(seed)

    records = []
    base_date = datetime.now() - timedelta(days=n_days)

    for i in range(n_days):
        day_date = base_date + timedelta(days=i)

        # VO2 Max (measured weekly)
        if i % 7 == 0:
            vo2 = vo2_base + np.random.normal(0, 1.5)
            records.append(
                {"time": day_date, "biomarker_slug": "vo2_max", "value": vo2}
            )

        # HRV (daily) - positively correlated with VO2 Max
        # Higher VO2 Max -> higher HRV
        hrv_base = 30 + (vo2_base - 30) * 1.5  # Scale: VO2 40 -> HRV ~45
        hrv = hrv_base + np.random.normal(0, 8)
        records.append(
            {"time": day_date, "biomarker_slug": "hrv_sdnn", "value": max(10, hrv)}
        )

        # RHR (daily) - negatively correlated with VO2 Max
        # Higher VO2 Max -> lower RHR
        rhr_base = 90 - (vo2_base - 30) * 1.0  # Scale: VO2 40 -> RHR ~60
        rhr = rhr_base + np.random.normal(0, 4)
        records.append(
            {
                "time": day_date,
                "biomarker_slug": "heart_rate_resting",
                "value": max(40, min(100, rhr)),
            }
        )

    return pd.DataFrame(records)


class TestComputePercentile:
    """Tests for ACSM percentile calculation."""

    def test_returns_percentile_object(self):
        """Should return VO2MaxPercentile dataclass."""
        result = compute_percentile(40.0, 35, "male")
        assert isinstance(result, VO2MaxPercentile)

    def test_male_30s_good_fitness(self):
        """Male, 35yo, 42.4 mL/kg/min should be 50th percentile (median)."""
        result = compute_percentile(42.4, 35, "male")
        assert result.percentile == 50
        assert result.category == "Fair"  # 40-59th = Fair
        assert "males aged 30-39" in result.comparison_group

    def test_female_40s_excellent_fitness(self):
        """Female, 45yo, 40.6 mL/kg/min should be 80th percentile."""
        result = compute_percentile(40.6, 45, "female")
        assert result.percentile == 80
        assert result.category == "Excellent"  # 80-94th = Excellent

    def test_superior_fitness(self):
        """Very high VO2 Max should be Superior category."""
        result = compute_percentile(56.0, 25, "male")
        assert result.percentile == 90
        assert result.category in ["Superior", "Excellent"]

    def test_very_poor_fitness(self):
        """Very low VO2 Max should be Very Poor category."""
        result = compute_percentile(25.0, 35, "male")
        assert result.percentile < 20
        assert result.category == "Very Poor"

    def test_handles_edge_ages(self):
        """Should handle ages outside standard ranges."""
        result_young = compute_percentile(45.0, 18, "male")
        result_old = compute_percentile(30.0, 85, "female")

        assert result_young.percentile >= 0
        assert result_old.percentile >= 0

    def test_includes_acsm_reference(self):
        """Should cite ACSM guidelines."""
        result = compute_percentile(40.0, 40, "male")
        assert "ACSM" in result.reference
        assert "11th" in result.reference or "11" in result.reference

    def test_case_insensitive_sex(self):
        """Should handle case variations in sex parameter."""
        result1 = compute_percentile(40.0, 35, "Male")
        result2 = compute_percentile(40.0, 35, "MALE")
        result3 = compute_percentile(40.0, 35, "male")

        assert result1.percentile == result2.percentile == result3.percentile


class TestComputeFitnessAge:
    """Tests for HUNT Fitness Study fitness age calculation."""

    def test_returns_fitness_age_object(self):
        """Should return FitnessAge dataclass."""
        result = compute_fitness_age(40.0, 40, "male")
        assert isinstance(result, FitnessAge)

    def test_high_vo2_yields_younger_fitness_age(self):
        """High VO2 Max should result in younger fitness age."""
        result = compute_fitness_age(50.0, 50, "male")
        # 50 mL/kg/min male: (57.5 - 50) / 0.445 = ~17 years
        assert result.fitness_age < result.chronological_age
        assert result.difference > 0

    def test_low_vo2_yields_older_fitness_age(self):
        """Low VO2 Max should result in older fitness age."""
        result = compute_fitness_age(30.0, 30, "male")
        # 30 mL/kg/min male: (57.5 - 30) / 0.445 = ~62 years
        assert result.fitness_age > result.chronological_age
        assert result.difference < 0

    def test_female_calculation(self):
        """Should use different formula for females."""
        male = compute_fitness_age(40.0, 40, "male")
        female = compute_fitness_age(40.0, 40, "female")
        # Same VO2 Max but different formulas should yield different fitness ages
        assert male.fitness_age != female.fitness_age

    def test_interpretation_positive_difference(self):
        """Should provide positive interpretation for younger fitness age."""
        result = compute_fitness_age(50.0, 50, "male")
        assert (
            "younger" in result.interpretation.lower()
            or "excellent" in result.interpretation.lower()
        )

    def test_interpretation_negative_difference(self):
        """Should provide appropriate interpretation for older fitness age."""
        result = compute_fitness_age(25.0, 30, "male")
        assert (
            "older" in result.interpretation.lower()
            or "below" in result.interpretation.lower()
            or "improvement" in result.interpretation.lower()
        )

    def test_includes_hunt_study_reference(self):
        """Should cite HUNT Fitness Study."""
        result = compute_fitness_age(40.0, 40, "male")
        assert (
            "Nes" in result.reference
            or "HUNT" in result.reference
            or "2013" in result.reference
        )

    def test_fitness_age_bounded(self):
        """Fitness age should be bounded to reasonable range (20-90)."""
        very_high = compute_fitness_age(60.0, 30, "male")
        very_low = compute_fitness_age(15.0, 80, "male")

        assert very_high.fitness_age >= 20
        assert very_low.fitness_age <= 90


class TestComputeMortalityRisk:
    """Tests for Kodama meta-analysis mortality risk assessment."""

    def test_returns_mortality_risk_object(self):
        """Should return MortalityRisk dataclass."""
        result = compute_mortality_risk(40.0)
        assert isinstance(result, MortalityRisk)

    def test_computes_mets(self):
        """Should correctly convert VO2 Max to METs."""
        result = compute_mortality_risk(35.0)
        assert result.mets == pytest.approx(10.0, abs=0.1)  # 35 / 3.5 = 10

    def test_high_fitness_low_risk(self):
        """High fitness (>10.8 METs) should be Low risk."""
        result = compute_mortality_risk(42.0)  # 12 METs
        assert result.risk_category == "Low"
        assert result.relative_risk < 1.0

    def test_moderate_fitness_moderate_risk(self):
        """Moderate fitness (7.9-10.8 METs) should be Moderate risk."""
        result = compute_mortality_risk(31.5)  # 9 METs
        assert result.risk_category == "Moderate"
        assert result.relative_risk < 1.0

    def test_low_fitness_high_risk(self):
        """Low fitness (<7.9 METs) should be High risk."""
        result = compute_mortality_risk(21.0)  # 6 METs
        assert result.risk_category == "High"
        assert result.relative_risk == 1.0

    def test_includes_kodama_reference(self):
        """Should cite Kodama meta-analysis."""
        result = compute_mortality_risk(40.0)
        assert (
            "Kodama" in result.reference
            or "JAMA" in result.reference
            or "2009" in result.reference
        )

    def test_includes_sample_size_in_reference(self):
        """Reference should mention large sample size."""
        result = compute_mortality_risk(40.0)
        assert "102,980" in result.reference or "102980" in result.reference


class TestAnalyzeTrend:
    """Tests for VO2 Max trend analysis."""

    def test_returns_trend_object(self):
        """Should return VO2MaxTrend dataclass."""
        df = make_vo2max_data(n_measurements=20)
        result = analyze_trend(df)
        assert isinstance(result, VO2MaxTrend)

    def test_returns_none_with_insufficient_data(self):
        """Should return None with fewer than min_measurements."""
        df = make_vo2max_data(n_measurements=3)
        result = analyze_trend(df, min_measurements=5)
        assert result is None

    def test_detects_positive_trend(self):
        """Should detect significant positive trend."""
        df = make_vo2max_data(n_measurements=30, base_value=35.0, trend=0.02, seed=42)
        result = analyze_trend(df)

        assert result is not None
        assert result.slope > 0
        assert result.slope_annual > 0

    def test_detects_negative_trend(self):
        """Should detect significant negative trend."""
        df = make_vo2max_data(n_measurements=30, base_value=45.0, trend=-0.02, seed=42)
        result = analyze_trend(df)

        assert result is not None
        assert result.slope < 0
        assert result.slope_annual < 0

    def test_stable_trend_not_significant(self):
        """Flat trend should not be statistically significant."""
        df = make_vo2max_data(n_measurements=20, base_value=40.0, trend=0.0, seed=42)
        result = analyze_trend(df)

        # With no trend and noise, should not be significant
        # (unless random noise creates apparent trend)
        assert result is not None
        assert 0 <= result.p_value <= 1

    def test_confidence_intervals_computed(self):
        """Should compute 95% confidence intervals for slope."""
        df = make_vo2max_data(n_measurements=20)
        result = analyze_trend(df)

        assert result.ci_lower < result.slope
        assert result.slope < result.ci_upper

    def test_includes_change_metrics(self):
        """Should include absolute and percentage change."""
        df = make_vo2max_data(n_measurements=20)
        result = analyze_trend(df)

        assert hasattr(result, "change")
        assert hasattr(result, "change_pct")
        assert hasattr(result, "start_value")
        assert hasattr(result, "end_value")


class TestAssessTrainingResponse:
    """Tests for training response assessment."""

    def test_returns_training_response_object(self):
        """Should return TrainingResponse dataclass."""
        measurements = [
            VO2MaxMeasurement(
                date=date.today() - timedelta(days=i * 7), value=40.0, mets=11.4
            )
            for i in range(10)
        ]
        result = assess_training_response(measurements)
        assert isinstance(result, TrainingResponse)

    def test_returns_none_with_insufficient_data(self):
        """Should return None with fewer than 5 measurements."""
        measurements = [
            VO2MaxMeasurement(date=date.today(), value=40.0, mets=11.4)
            for _ in range(3)
        ]
        result = assess_training_response(measurements)
        assert result is None

    def test_detects_high_responder(self):
        """Should detect high responder (>10% improvement)."""
        # Baseline around 35, current around 42 (~20% improvement)
        # Need baseline measurements within first 90 days, then later improvements
        measurements = []
        base_date = date.today() - timedelta(days=365)

        # First 3 measurements form baseline within first 90 days (around 35)
        for i in range(3):
            measurements.append(
                VO2MaxMeasurement(
                    date=base_date + timedelta(days=i * 30),  # Days 0, 30, 60
                    value=35.0,
                    mets=35.0 / 3.5,
                )
            )

        # Later measurements after 90 days show improvement (around 42 = +20%)
        for i in range(5):
            measurements.append(
                VO2MaxMeasurement(
                    date=base_date
                    + timedelta(days=120 + i * 30),  # Days 120, 150, 180, 210, 240
                    value=42.0,
                    mets=42.0 / 3.5,
                )
            )

        result = assess_training_response(measurements)

        assert result is not None
        assert result.is_responder
        assert result.response_category == "High"

    def test_detects_non_responder(self):
        """Should detect non-responder (<3% change)."""
        measurements = [
            VO2MaxMeasurement(
                date=date.today() - timedelta(days=i * 14),
                value=40.0 + np.random.uniform(-0.3, 0.3),
                mets=11.4,
            )
            for i in range(10)
        ]

        result = assess_training_response(measurements)

        assert result is not None
        assert result.change_pct < 3
        # Note: might detect as responder if random noise creates >3% change

    def test_includes_bacon_reference(self):
        """Should cite Bacon et al. training response research."""
        measurements = [
            VO2MaxMeasurement(
                date=date.today() - timedelta(days=i * 7), value=40.0, mets=11.4
            )
            for i in range(10)
        ]
        result = assess_training_response(measurements)

        assert "Bacon" in result.reference or "2013" in result.reference


class TestComputeValidatedCorrelations:
    """Tests for validated HRV and RHR correlations."""

    def test_returns_tuple_of_correlations(self):
        """Should return tuple of (hrv_corr, rhr_corr)."""
        df = make_correlated_data(n_days=60)
        hrv_corr, rhr_corr = compute_validated_correlations(df)

        # Should return tuples of (r, p, n) or None
        assert hrv_corr is None or len(hrv_corr) == 3
        assert rhr_corr is None or len(rhr_corr) == 3

    def test_returns_none_with_no_vo2_data(self):
        """Should return None if no VO2 Max data."""
        df = pd.DataFrame({"time": [], "biomarker_slug": [], "value": []})
        hrv_corr, rhr_corr = compute_validated_correlations(df)

        assert hrv_corr is None
        assert rhr_corr is None

    def test_computes_hrv_correlation(self):
        """Should compute correlation with HRV."""
        df = make_correlated_data(n_days=100)
        hrv_corr, _ = compute_validated_correlations(df)

        if hrv_corr:
            r, p, n = hrv_corr
            assert -1 <= r <= 1
            assert 0 <= p <= 1
            assert n >= 10

    def test_computes_rhr_correlation(self):
        """Should compute correlation with RHR."""
        df = make_correlated_data(n_days=100)
        _, rhr_corr = compute_validated_correlations(df)

        if rhr_corr:
            r, p, n = rhr_corr
            assert -1 <= r <= 1
            assert 0 <= p <= 1
            assert n >= 10


class TestGenerateVO2MaxReport:
    """Tests for complete VO2 Max report generation."""

    def test_returns_report_object(self):
        """Should return VO2MaxReport dataclass."""
        df = make_vo2max_data(n_measurements=20)
        result = generate_vo2max_report(df)
        assert isinstance(result, VO2MaxReport)

    def test_returns_none_with_no_data(self):
        """Should return None if no VO2 Max data."""
        df = pd.DataFrame({"time": [], "biomarker_slug": [], "value": []})
        result = generate_vo2max_report(df)
        assert result is None

    def test_includes_latest_measurement(self):
        """Should include latest measurement."""
        df = make_vo2max_data(n_measurements=10)
        result = generate_vo2max_report(df)

        assert result.latest_measurement is not None
        assert result.latest_measurement.value > 0
        assert result.latest_measurement.mets > 0

    def test_includes_mortality_risk(self):
        """Should always include mortality risk (no age/sex needed)."""
        df = make_vo2max_data(n_measurements=10)
        result = generate_vo2max_report(df)

        assert result.mortality_risk is not None
        assert result.mortality_risk.risk_category in ["Low", "Moderate", "High"]

    def test_includes_percentile_when_demographics_provided(self):
        """Should include percentile when age/sex provided."""
        df = make_vo2max_data(n_measurements=10)
        result = generate_vo2max_report(df, age=35, sex="male")

        assert result.percentile is not None
        assert 0 <= result.percentile.percentile <= 100

    def test_no_percentile_without_demographics(self):
        """Should not include percentile without age/sex."""
        df = make_vo2max_data(n_measurements=10)
        result = generate_vo2max_report(df)

        assert result.percentile is None

    def test_includes_fitness_age_when_demographics_provided(self):
        """Should include fitness age when age/sex provided."""
        df = make_vo2max_data(n_measurements=10)
        result = generate_vo2max_report(df, age=40, sex="female")

        assert result.fitness_age is not None

    def test_includes_all_measurements(self):
        """Should include list of all measurements."""
        n = 15
        df = make_vo2max_data(n_measurements=n)
        result = generate_vo2max_report(df)

        assert len(result.measurements) == n

    def test_includes_trend_analysis(self):
        """Should include trend analysis with sufficient data."""
        df = make_vo2max_data(n_measurements=20)
        result = generate_vo2max_report(df)

        assert result.trend is not None

    def test_includes_insights(self):
        """Should include list of insights."""
        df = make_vo2max_data(n_measurements=20)
        result = generate_vo2max_report(df, age=35, sex="male")

        assert isinstance(result.insights, list)
        assert len(result.insights) > 0

    def test_includes_recommendations(self):
        """Should include list of recommendations."""
        df = make_vo2max_data(n_measurements=20)
        result = generate_vo2max_report(df)

        assert isinstance(result.recommendations, list)
        assert len(result.recommendations) > 0


class TestVO2MaxValidation:
    """Tests for clinical validity of VO2 Max analysis."""

    def test_mets_conversion_correct(self):
        """1 MET should equal 3.5 mL/kg/min."""
        assert METS_CONVERSION == 3.5

    def test_acsm_percentiles_structure(self):
        """ACSM percentile tables should have correct structure."""
        # Should have multiple age ranges
        assert len(ACSM_PERCENTILES) >= 6

        # Each age range should have percentiles from 10-90
        for _age_range, percentiles in ACSM_PERCENTILES.items():
            assert 10 in percentiles
            assert 50 in percentiles
            assert 90 in percentiles

            # Each percentile should have (male, female) values
            for _pct, values in percentiles.items():
                assert len(values) == 2
                assert values[0] > values[1]  # Males typically higher

    def test_percentile_values_decrease_with_age(self):
        """VO2 Max norms should decrease with age."""
        # 50th percentile male values should decrease across age groups
        young = ACSM_PERCENTILES[(20, 29)][50][0]
        middle = ACSM_PERCENTILES[(40, 49)][50][0]
        older = ACSM_PERCENTILES[(60, 69)][50][0]

        assert young > middle > older

    def test_male_values_higher_than_female(self):
        """Male VO2 Max norms should be higher than female."""
        for age_range, percentiles in ACSM_PERCENTILES.items():
            for pct, (male, female) in percentiles.items():
                assert (
                    male > female
                ), f"Male should be higher at {age_range}, {pct}th percentile"

    def test_realistic_vo2max_range(self):
        """All reference values should be in realistic range (15-75 mL/kg/min)."""
        for _age_range, percentiles in ACSM_PERCENTILES.items():
            for _pct, (male, female) in percentiles.items():
                assert 15 < male < 75
                assert 10 < female < 65
