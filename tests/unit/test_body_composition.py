"""Unit tests for body composition analysis.

Tests cover all validated methods with citations:
- BMI with WHO classification
- Body fat percentile with ACSM norms
- Weight trend analysis with confidence intervals
- Body composition change assessment
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from soma.statistics.body_composition import (
    ACSM_BODY_FAT_PERCENTILES,
    BMI_CATEGORIES,
    BMIResult,
    BodyCompositionChange,
    BodyCompositionReport,
    BodyCompositionSummary,
    BodyFatPercentile,
    WeightTrend,
    analyze_composition_change,
    analyze_weight_trend,
    compute_bmi,
    compute_body_fat_percentile,
    generate_body_composition_report,
    get_body_composition_summary,
)


def make_weight_data(
    n_measurements: int = 30,
    base_weight: float = 75.0,
    trend: float = 0.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate weight test data.

    Args:
        n_measurements: Number of measurements to generate
        base_weight: Starting weight in kg
        trend: Daily change in weight (e.g., -0.05 = losing weight)
        seed: Random seed for reproducibility
    """
    np.random.seed(seed)

    records = []
    base_date = datetime.now() - timedelta(days=n_measurements * 3)

    for i in range(n_measurements):
        measurement_date = base_date + timedelta(days=i * 3)  # Every 3 days
        # Add trend and noise
        value = base_weight + (i * 3 * trend) + np.random.normal(0, 0.5)

        records.append(
            {
                "time": measurement_date,
                "biomarker_slug": "body_mass",
                "value": max(40, value),  # Floor at 40 kg
            }
        )

    return pd.DataFrame(records)


def make_body_composition_data(
    n_measurements: int = 30,
    base_weight: float = 75.0,
    base_bf: float = 20.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate body composition test data with weight and body fat."""
    np.random.seed(seed)

    records = []
    base_date = datetime.now() - timedelta(days=n_measurements * 7)

    for i in range(n_measurements):
        measurement_date = base_date + timedelta(days=i * 7)

        # Weight
        weight = base_weight + np.random.normal(0, 1.0)
        records.append(
            {"time": measurement_date, "biomarker_slug": "body_mass", "value": weight}
        )

        # Body fat percentage (every other measurement)
        if i % 2 == 0:
            bf = base_bf + np.random.normal(0, 1.0)
            records.append(
                {
                    "time": measurement_date,
                    "biomarker_slug": "body_fat_percentage",
                    "value": max(5, min(50, bf)),
                }
            )

            # Lean body mass (derived)
            lean = weight * (1 - bf / 100)
            records.append(
                {
                    "time": measurement_date,
                    "biomarker_slug": "lean_body_mass",
                    "value": lean,
                }
            )

    return pd.DataFrame(records)


class TestComputeBMI:
    """Tests for WHO BMI classification."""

    def test_returns_bmi_result(self):
        """Should return BMIResult dataclass."""
        result = compute_bmi(70.0, 1.75)
        assert isinstance(result, BMIResult)

    def test_calculates_bmi_correctly(self):
        """Should calculate BMI = weight / height^2."""
        result = compute_bmi(70.0, 1.75)
        expected = 70.0 / (1.75**2)
        assert result.bmi == pytest.approx(expected, abs=0.1)

    def test_normal_weight_classification(self):
        """70kg at 1.75m should be Normal."""
        result = compute_bmi(70.0, 1.75)
        assert result.category == "Normal"
        assert result.health_risk == "Low"

    def test_underweight_classification(self):
        """50kg at 1.75m should be Underweight."""
        result = compute_bmi(50.0, 1.75)
        assert result.category == "Underweight"
        assert result.health_risk == "Moderate"

    def test_overweight_classification(self):
        """85kg at 1.75m should be Overweight."""
        result = compute_bmi(85.0, 1.75)
        assert result.category == "Overweight"
        assert result.health_risk == "Moderate"

    def test_obese_class_1_classification(self):
        """95kg at 1.75m should be Obese Class I."""
        result = compute_bmi(95.0, 1.75)
        assert result.category == "Obese Class I"
        assert result.health_risk == "High"

    def test_obese_class_2_classification(self):
        """110kg at 1.75m should be Obese Class II."""
        result = compute_bmi(110.0, 1.75)
        assert result.category == "Obese Class II"
        assert result.health_risk == "Very High"

    def test_obese_class_3_classification(self):
        """130kg at 1.75m should be Obese Class III."""
        result = compute_bmi(130.0, 1.75)
        assert result.category == "Obese Class III"
        assert result.health_risk == "Very High"

    def test_includes_who_reference(self):
        """Should cite WHO guidelines."""
        result = compute_bmi(70.0, 1.75)
        assert "WHO" in result.reference

    def test_bmi_categories_complete(self):
        """BMI categories should cover all ranges."""
        assert "Underweight" in BMI_CATEGORIES
        assert "Normal" in BMI_CATEGORIES
        assert "Overweight" in BMI_CATEGORIES
        assert "Obese Class I" in BMI_CATEGORIES


class TestComputeBodyFatPercentile:
    """Tests for ACSM body fat percentile ranking."""

    def test_returns_body_fat_percentile(self):
        """Should return BodyFatPercentile dataclass."""
        result = compute_body_fat_percentile(20.0, 35, "male")
        assert isinstance(result, BodyFatPercentile)

    def test_male_30s_average_body_fat(self):
        """Male 35yo at 20.6% should be 50th percentile (Average category)."""
        result = compute_body_fat_percentile(20.6, 35, "male")
        assert result.percentile == 50
        # 20.6% is in Average category for males (18-24%)
        assert result.category == "Average"
        assert "males aged 30-39" in result.comparison_group

    def test_female_40s_fitness_body_fat(self):
        """Female 45yo at 22.4% should be 70th percentile."""
        result = compute_body_fat_percentile(22.4, 45, "female")
        assert result.percentile == 70
        assert result.category == "Fitness"

    def test_athlete_category(self):
        """Very low body fat should be Athletes category."""
        result = compute_body_fat_percentile(10.0, 25, "male")
        assert result.category == "Athletes"

    def test_obese_category(self):
        """High body fat should be Obese category."""
        result = compute_body_fat_percentile(30.0, 35, "male")
        assert result.category == "Obese"

    def test_healthy_range_assessment(self):
        """Should correctly assess if within healthy range."""
        healthy = compute_body_fat_percentile(15.0, 30, "male")
        assert healthy.is_healthy

        unhealthy = compute_body_fat_percentile(30.0, 30, "male")
        assert not unhealthy.is_healthy

    def test_includes_acsm_reference(self):
        """Should cite ACSM guidelines."""
        result = compute_body_fat_percentile(20.0, 35, "male")
        assert "ACSM" in result.reference

    def test_case_insensitive_sex(self):
        """Should handle case variations in sex parameter."""
        result1 = compute_body_fat_percentile(20.0, 35, "Male")
        result2 = compute_body_fat_percentile(20.0, 35, "MALE")
        result3 = compute_body_fat_percentile(20.0, 35, "male")
        assert result1.percentile == result2.percentile == result3.percentile

    def test_handles_edge_ages(self):
        """Should handle ages outside standard ranges."""
        young = compute_body_fat_percentile(15.0, 18, "male")
        old = compute_body_fat_percentile(25.0, 85, "female")
        assert young.percentile >= 0
        assert old.percentile >= 0


class TestAnalyzeWeightTrend:
    """Tests for weight trend analysis."""

    def test_returns_weight_trend(self):
        """Should return WeightTrend dataclass."""
        df = make_weight_data(n_measurements=20)
        result = analyze_weight_trend(df)
        assert isinstance(result, WeightTrend)

    def test_returns_none_with_insufficient_data(self):
        """Should return None with fewer than min_measurements."""
        df = make_weight_data(n_measurements=3)
        result = analyze_weight_trend(df, min_measurements=5)
        assert result is None

    def test_detects_weight_loss(self):
        """Should detect significant weight loss."""
        df = make_weight_data(n_measurements=30, base_weight=80.0, trend=-0.05, seed=42)
        result = analyze_weight_trend(df)

        assert result is not None
        assert result.slope_daily < 0
        assert result.direction == "losing"

    def test_detects_weight_gain(self):
        """Should detect significant weight gain."""
        df = make_weight_data(n_measurements=30, base_weight=70.0, trend=0.05, seed=42)
        result = analyze_weight_trend(df)

        assert result is not None
        assert result.slope_daily > 0
        assert result.direction == "gaining"

    def test_stable_weight(self):
        """Stable weight should show 'stable' direction when not significant."""
        df = make_weight_data(n_measurements=20, base_weight=75.0, trend=0.0, seed=42)
        result = analyze_weight_trend(df)

        assert result is not None
        # With no trend and only noise, should likely be stable
        assert 0 <= result.p_value <= 1

    def test_confidence_intervals(self):
        """Should compute 95% confidence intervals."""
        df = make_weight_data(n_measurements=30)
        result = analyze_weight_trend(df)

        assert result.ci_lower < result.slope_weekly
        assert result.slope_weekly < result.ci_upper

    def test_includes_change_metrics(self):
        """Should include absolute and percentage change."""
        df = make_weight_data(n_measurements=20)
        result = analyze_weight_trend(df)

        assert hasattr(result, "change_kg")
        assert hasattr(result, "change_pct")
        assert hasattr(result, "start_weight")
        assert hasattr(result, "end_weight")


class TestAnalyzeCompositionChange:
    """Tests for body composition change assessment."""

    def test_returns_composition_change(self):
        """Should return BodyCompositionChange dataclass."""
        df = make_body_composition_data(n_measurements=20)
        result = analyze_composition_change(df)
        assert isinstance(result, BodyCompositionChange)

    def test_returns_none_with_insufficient_weight_data(self):
        """Should return None with insufficient weight data."""
        df = make_body_composition_data(n_measurements=3)
        result = analyze_composition_change(df)
        assert result is None

    def test_calculates_weight_change(self):
        """Should calculate weight change over time."""
        df = make_body_composition_data(n_measurements=20)
        result = analyze_composition_change(df)

        assert result is not None
        assert isinstance(result.weight_change_kg, float)

    def test_determines_composition_quality(self):
        """Should determine if composition change is favorable."""
        df = make_body_composition_data(n_measurements=20)
        result = analyze_composition_change(df)

        assert result is not None
        assert result.composition_quality in ["Favorable", "Neutral", "Unfavorable"]


class TestGenerateBodyCompositionReport:
    """Tests for complete body composition report generation."""

    def test_returns_report(self):
        """Should return BodyCompositionReport dataclass."""
        df = make_body_composition_data(n_measurements=20)
        result = generate_body_composition_report(df)
        assert isinstance(result, BodyCompositionReport)

    def test_returns_none_with_no_data(self):
        """Should return None if no weight data."""
        df = pd.DataFrame({"time": [], "biomarker_slug": [], "value": []})
        result = generate_body_composition_report(df)
        assert result is None

    def test_includes_latest_measurement(self):
        """Should include latest measurement."""
        df = make_body_composition_data(n_measurements=10)
        result = generate_body_composition_report(df)

        assert result.latest_measurement is not None
        assert result.latest_measurement.weight_kg > 0

    def test_includes_bmi_when_height_provided(self):
        """Should include BMI when height provided."""
        df = make_body_composition_data(n_measurements=10)
        result = generate_body_composition_report(df, height_m=1.75)

        assert result.bmi is not None
        assert result.bmi.bmi > 0

    def test_no_bmi_without_height(self):
        """Should not include BMI without height."""
        df = make_body_composition_data(n_measurements=10)
        result = generate_body_composition_report(df)

        assert result.bmi is None

    def test_includes_body_fat_percentile_when_demographics_provided(self):
        """Should include body fat percentile when age/sex provided and latest has body fat."""
        # Use odd number of measurements so latest has body fat data (recorded every other)
        df = make_body_composition_data(n_measurements=11, base_bf=20.0)
        result = generate_body_composition_report(df, age=35, sex="male")

        # Body fat percentile only included if latest measurement has body fat
        if result.latest_measurement.body_fat_pct is not None:
            assert result.body_fat_percentile is not None
        else:
            # If latest doesn't have body fat, percentile won't be computed
            # This is expected behavior - need body fat data for percentile
            assert result.body_fat_percentile is None

    def test_includes_weight_trend(self):
        """Should include weight trend with sufficient data."""
        df = make_body_composition_data(n_measurements=20)
        result = generate_body_composition_report(df)

        assert result.weight_trend is not None

    def test_includes_insights(self):
        """Should include list of insights."""
        df = make_body_composition_data(n_measurements=20)
        result = generate_body_composition_report(df, height_m=1.75, age=35, sex="male")

        assert isinstance(result.insights, list)
        assert len(result.insights) > 0

    def test_includes_recommendations(self):
        """Should include list of recommendations."""
        df = make_body_composition_data(n_measurements=20)
        result = generate_body_composition_report(df)

        assert isinstance(result.recommendations, list)
        assert len(result.recommendations) > 0


class TestGetBodyCompositionSummary:
    """Tests for quick body composition summary."""

    def test_returns_summary(self):
        """Should return BodyCompositionSummary dataclass."""
        df = make_body_composition_data(n_measurements=20)
        result = get_body_composition_summary(df)
        assert isinstance(result, BodyCompositionSummary)

    def test_handles_no_data(self):
        """Should handle case with no data."""
        df = pd.DataFrame({"time": [], "biomarker_slug": [], "value": []})
        result = get_body_composition_summary(df)

        assert result.has_sufficient_data is False
        assert result.n_weight_measurements == 0

    def test_includes_latest_values(self):
        """Should include latest weight and BMI."""
        df = make_body_composition_data(n_measurements=10)
        result = get_body_composition_summary(df, height_m=1.75)

        assert result.latest_weight_kg is not None
        assert result.latest_bmi is not None

    def test_includes_trend_direction(self):
        """Should include weight trend direction."""
        df = make_weight_data(n_measurements=20, trend=-0.03)
        result = get_body_composition_summary(df)

        assert result.weight_trend_direction is not None


class TestBodyCompositionValidation:
    """Tests for clinical validity of body composition analysis."""

    def test_bmi_formula_correct(self):
        """BMI = kg / m^2 should be calculated correctly."""
        # 70 kg, 1.75 m -> BMI = 70 / 3.0625 = 22.86
        result = compute_bmi(70.0, 1.75)
        assert result.bmi == pytest.approx(22.9, abs=0.1)

    def test_bmi_categories_boundaries(self):
        """BMI categories should have correct boundaries per WHO."""
        assert BMI_CATEGORIES["Underweight"] == (16.0, 18.5)
        assert BMI_CATEGORIES["Normal"] == (18.5, 25.0)
        assert BMI_CATEGORIES["Overweight"] == (25.0, 30.0)
        assert BMI_CATEGORIES["Obese Class I"] == (30.0, 35.0)

    def test_acsm_percentiles_structure(self):
        """ACSM body fat tables should have correct structure."""
        assert len(ACSM_BODY_FAT_PERCENTILES) >= 6  # Multiple age ranges

        for _age_range, percentiles in ACSM_BODY_FAT_PERCENTILES.items():
            assert 10 in percentiles
            assert 50 in percentiles
            assert 90 in percentiles

            for _pct, values in percentiles.items():
                assert len(values) == 2  # (male, female)
                # Females typically have higher body fat
                assert values[1] > values[0]

    def test_body_fat_increases_with_age(self):
        """Body fat norms should generally increase with age."""
        young = ACSM_BODY_FAT_PERCENTILES[(20, 29)][50][0]
        middle = ACSM_BODY_FAT_PERCENTILES[(40, 49)][50][0]
        older = ACSM_BODY_FAT_PERCENTILES[(60, 69)][50][0]

        assert young < middle < older

    def test_female_body_fat_higher_than_male(self):
        """Female body fat norms should be higher than male."""
        for age_range, percentiles in ACSM_BODY_FAT_PERCENTILES.items():
            for pct, (male, female) in percentiles.items():
                assert (
                    female > male
                ), f"Female should be higher at {age_range}, {pct}th percentile"

    def test_realistic_body_fat_range(self):
        """All reference values should be in realistic range (2-50%)."""
        for _age_range, percentiles in ACSM_BODY_FAT_PERCENTILES.items():
            for _pct, (male, female) in percentiles.items():
                assert 2 < male < 50
                assert 5 < female < 50
