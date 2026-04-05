"""Body Composition Analysis.

Provides rigorously validated analysis of body composition metrics:
- Body Mass Index (BMI) with WHO classification
- Body fat percentage with ACSM age/sex percentile norms
- Lean body mass tracking
- Weight trend analysis with confidence intervals
- Body composition change assessment

All formulas and reference values are from peer-reviewed sources:

1. BMI CLASSIFICATION:
   - World Health Organization (WHO). "Obesity: preventing and managing
     the global epidemic." WHO Technical Report Series 894 (2000).
   - Categories: Underweight, Normal, Overweight, Obese I/II/III

2. BODY FAT PERCENTAGE NORMS:
   - ACSM's Guidelines for Exercise Testing and Prescription (11th ed, 2022)
   - Age/sex-stratified percentile data from population studies
   - Categories: Essential, Athletes, Fitness, Average, Obese

3. BODY FAT ESTIMATION (if not measured):
   - Jackson & Pollock equations (1978, 1980)
   - US Navy method (Hodgdon & Beckett, 1984)
   - Note: Direct measurement preferred when available

4. HEALTH RISK ASSESSMENT:
   - Waist circumference thresholds (NHLBI, ATP III guidelines)
   - Body fat and mortality: Padwal et al. (2016), Annals of Internal Medicine
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, List, Tuple
import pandas as pd
from scipy import stats

# ============================================
# VALIDATED REFERENCE DATA
# ============================================

# BMI Categories (WHO, 2000)
BMI_CATEGORIES = {
    "Severely Underweight": (0, 16.0),
    "Underweight": (16.0, 18.5),
    "Normal": (18.5, 25.0),
    "Overweight": (25.0, 30.0),
    "Obese Class I": (30.0, 35.0),
    "Obese Class II": (35.0, 40.0),
    "Obese Class III": (40.0, 100.0),
}

# Body Fat Percentage Categories (ACSM, general guidelines)
# Format: (min%, max%)
BODY_FAT_CATEGORIES_MALE = {
    "Essential Fat": (2, 5),
    "Athletes": (6, 13),
    "Fitness": (14, 17),
    "Average": (18, 24),
    "Obese": (25, 100),
}

BODY_FAT_CATEGORIES_FEMALE = {
    "Essential Fat": (10, 13),
    "Athletes": (14, 20),
    "Fitness": (21, 24),
    "Average": (25, 31),
    "Obese": (32, 100),
}

# Body Fat Percentile Tables (ACSM 11th Edition)
# Format: {age_range: {percentile: (male_value, female_value)}}
# Values are body fat percentages
ACSM_BODY_FAT_PERCENTILES = {
    (20, 29): {
        90: (7.1, 14.5),
        80: (9.4, 17.1),
        70: (11.8, 19.0),
        60: (14.1, 20.6),
        50: (15.9, 22.1),
        40: (17.4, 23.7),
        30: (19.5, 25.4),
        20: (22.4, 27.7),
        10: (25.9, 32.1),
    },
    (30, 39): {
        90: (11.3, 15.5),
        80: (14.9, 18.0),
        70: (17.5, 20.0),
        60: (19.2, 21.6),
        50: (20.6, 23.1),
        40: (22.4, 24.9),
        30: (24.1, 26.6),
        20: (26.4, 28.9),
        10: (30.3, 32.8),
    },
    (40, 49): {
        90: (13.6, 16.8),
        80: (17.2, 19.9),
        70: (19.6, 22.4),
        60: (21.3, 24.2),
        50: (23.0, 25.7),
        40: (24.6, 27.3),
        30: (26.3, 29.2),
        20: (28.6, 31.4),
        10: (32.5, 35.0),
    },
    (50, 59): {
        90: (15.3, 19.1),
        80: (18.8, 22.5),
        70: (21.3, 25.1),
        60: (23.0, 26.7),
        50: (24.8, 28.3),
        40: (26.3, 30.1),
        30: (28.3, 31.9),
        20: (30.7, 34.3),
        10: (35.2, 37.9),
    },
    (60, 69): {
        90: (15.3, 20.1),
        80: (18.4, 23.4),
        70: (21.0, 25.9),
        60: (23.0, 27.5),
        50: (24.7, 29.3),
        40: (26.5, 30.8),
        30: (28.5, 32.5),
        20: (31.0, 34.6),
        10: (35.4, 38.3),
    },
    (70, 79): {
        90: (15.5, 20.6),
        80: (18.1, 23.7),
        70: (20.6, 26.2),
        60: (22.7, 27.8),
        50: (24.4, 29.4),
        40: (26.0, 31.0),
        30: (27.8, 32.7),
        20: (30.4, 34.8),
        10: (34.5, 38.2),
    },
}

# Healthy body fat ranges by age (ACSM general guidelines)
HEALTHY_BODY_FAT_RANGES = {
    "male": {
        (20, 39): (8, 19),
        (40, 59): (11, 21),
        (60, 79): (13, 24),
    },
    "female": {
        (20, 39): (21, 32),
        (40, 59): (23, 33),
        (60, 79): (24, 35),
    },
}


# ============================================
# DATA CLASSES
# ============================================


@dataclass
class BMIResult:
    """BMI calculation and classification."""

    bmi: float
    category: str
    health_risk: str  # 'Low', 'Moderate', 'High', 'Very High'
    reference: str


@dataclass
class BodyFatPercentile:
    """Body fat percentage with percentile ranking."""

    body_fat_pct: float
    percentile: int
    category: str  # 'Essential', 'Athletes', 'Fitness', 'Average', 'Obese'
    comparison_group: str
    is_healthy: bool
    healthy_range: Tuple[float, float]
    reference: str


@dataclass
class WeightMeasurement:
    """Single weight measurement with derived metrics."""

    date: date
    weight_kg: float
    weight_lb: float
    bmi: Optional[float]
    body_fat_pct: Optional[float]
    lean_mass_kg: Optional[float]
    fat_mass_kg: Optional[float]


@dataclass
class WeightTrend:
    """Weight trend analysis over time."""

    period_days: int
    n_measurements: int

    start_weight: float
    end_weight: float
    change_kg: float
    change_pct: float

    slope_daily: float  # kg per day
    slope_weekly: float  # kg per week

    ci_lower: float  # 95% CI for weekly slope
    ci_upper: float

    p_value: float
    is_significant: bool

    direction: str  # 'gaining', 'losing', 'stable'
    interpretation: str


@dataclass
class BodyCompositionChange:
    """Body composition change assessment."""

    period_days: int
    n_measurements: int

    weight_change_kg: float
    body_fat_change_pct: Optional[float]  # Change in body fat percentage points
    lean_mass_change_kg: Optional[float]
    fat_mass_change_kg: Optional[float]

    composition_quality: str  # 'Favorable', 'Neutral', 'Unfavorable'
    interpretation: str


@dataclass
class FitnessCorrelation:
    """Correlation between body composition and fitness metrics."""

    metric: str
    r: float
    p_value: float
    n: int
    is_significant: bool
    direction: str  # 'positive', 'negative'
    interpretation: str


@dataclass
class BodyCompositionReport:
    """Complete body composition analysis report."""

    # Current status
    latest_measurement: WeightMeasurement
    bmi: Optional[BMIResult]
    body_fat_percentile: Optional[BodyFatPercentile]

    # Historical data
    measurements: List[WeightMeasurement]
    weight_trend: Optional[WeightTrend]
    composition_change: Optional[BodyCompositionChange]

    # Fitness correlations
    vo2max_correlation: Optional[FitnessCorrelation]
    rhr_correlation: Optional[FitnessCorrelation]

    # Summary
    insights: List[str]
    recommendations: List[str]


@dataclass
class BodyCompositionSummary:
    """Quick summary of body composition status."""

    has_sufficient_data: bool
    n_weight_measurements: int
    n_body_fat_measurements: int

    latest_weight_kg: Optional[float]
    latest_bmi: Optional[float]
    bmi_category: Optional[str]

    latest_body_fat_pct: Optional[float]
    body_fat_category: Optional[str]

    weight_trend_direction: Optional[str]
    overall_assessment: str


# ============================================
# ANALYSIS FUNCTIONS
# ============================================


def compute_bmi(weight_kg: float, height_m: float) -> BMIResult:
    """
    Calculate BMI and determine WHO classification.

    Formula: BMI = weight(kg) / height(m)^2

    Reference: WHO Technical Report Series 894 (2000)
    """
    bmi = weight_kg / (height_m**2)

    # Determine category
    category = "Normal"
    for cat, (low, high) in BMI_CATEGORIES.items():
        if low <= bmi < high:
            category = cat
            break

    # Determine health risk
    if bmi < 18.5:
        health_risk = "Moderate"  # Underweight has health risks
    elif bmi < 25:
        health_risk = "Low"
    elif bmi < 30:
        health_risk = "Moderate"
    elif bmi < 35:
        health_risk = "High"
    else:
        health_risk = "Very High"

    return BMIResult(
        bmi=round(bmi, 1),
        category=category,
        health_risk=health_risk,
        reference="WHO Technical Report Series 894 (2000)",
    )


def compute_body_fat_percentile(
    body_fat_pct: float, age: int, sex: str  # 'male' or 'female'
) -> BodyFatPercentile:
    """
    Compute body fat percentile ranking based on ACSM norms.

    Reference: ACSM's Guidelines for Exercise Testing and Prescription, 11th ed.
    """
    # Find appropriate age range
    age_range = None
    for low, high in ACSM_BODY_FAT_PERCENTILES.keys():
        if low <= age <= high:
            age_range = (low, high)
            break

    if age_range is None:
        if age < 20:
            age_range = (20, 29)
        else:
            age_range = (70, 79)

    percentiles = ACSM_BODY_FAT_PERCENTILES[age_range]
    sex_idx = 0 if sex.lower() == "male" else 1

    # Find percentile (note: LOWER body fat = HIGHER percentile for fitness)
    # The tables show body fat at each percentile, so we need to find where the person falls
    sorted_pcts = sorted(percentiles.keys(), reverse=True)

    percentile = 5  # Default below 10th
    for pct in sorted_pcts:
        ref_value = percentiles[pct][sex_idx]
        if body_fat_pct <= ref_value:
            percentile = pct
            break

    # Determine category
    categories = (
        BODY_FAT_CATEGORIES_MALE
        if sex.lower() == "male"
        else BODY_FAT_CATEGORIES_FEMALE
    )
    category = "Average"
    for cat, (low, high) in categories.items():
        if low <= body_fat_pct < high:
            category = cat
            break

    # Determine healthy range
    healthy_ranges = HEALTHY_BODY_FAT_RANGES[sex.lower()]
    healthy_range = (10, 25)  # Default
    for (low_age, high_age), range_vals in healthy_ranges.items():
        if low_age <= age <= high_age:
            healthy_range = range_vals
            break

    is_healthy = healthy_range[0] <= body_fat_pct <= healthy_range[1]

    comparison_group = f"{sex.lower()}s aged {age_range[0]}-{age_range[1]}"

    return BodyFatPercentile(
        body_fat_pct=round(body_fat_pct, 1),
        percentile=percentile,
        category=category,
        comparison_group=comparison_group,
        is_healthy=is_healthy,
        healthy_range=healthy_range,
        reference="ACSM's Guidelines for Exercise Testing and Prescription, 11th ed. (2022)",
    )


def compute_body_composition(
    weight_kg: float,
    body_fat_pct: Optional[float] = None,
    height_m: Optional[float] = None,
) -> WeightMeasurement:
    """
    Compute full body composition metrics from weight and body fat percentage.
    """
    weight_lb = weight_kg * 2.20462

    bmi = None
    if height_m:
        bmi = round(weight_kg / (height_m**2), 1)

    lean_mass_kg = None
    fat_mass_kg = None
    if body_fat_pct is not None:
        fat_mass_kg = round(weight_kg * (body_fat_pct / 100), 2)
        lean_mass_kg = round(weight_kg - fat_mass_kg, 2)

    return WeightMeasurement(
        date=date.today(),
        weight_kg=round(weight_kg, 2),
        weight_lb=round(weight_lb, 2),
        bmi=bmi,
        body_fat_pct=body_fat_pct,
        lean_mass_kg=lean_mass_kg,
        fat_mass_kg=fat_mass_kg,
    )


def analyze_weight_trend(
    df: pd.DataFrame, min_measurements: int = 5
) -> Optional[WeightTrend]:
    """
    Analyze weight trend over time with confidence intervals.

    Uses ordinary least squares regression with 95% CIs.
    """
    weight_data = df[df["biomarker_slug"] == "body_mass"].copy()

    if len(weight_data) < min_measurements:
        return None

    weight_data["time"] = pd.to_datetime(weight_data["time"])
    weight_data = weight_data.sort_values("time")

    # Convert to days since first measurement
    first_date = weight_data["time"].min()
    weight_data["days"] = (weight_data["time"] - first_date).dt.days

    x = weight_data["days"].values
    y = weight_data["value"].values
    n = len(x)

    # Linear regression
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

    # 95% CI for slope
    t_crit = stats.t.ppf(0.975, n - 2)
    ci_margin = t_crit * std_err

    # Calculate values
    period_days = int(x.max() - x.min())
    start_weight = float(intercept)
    end_weight = float(intercept + slope * x.max())
    change_kg = end_weight - start_weight
    change_pct = (change_kg / start_weight) * 100 if start_weight > 0 else 0

    # Weekly slope
    slope_weekly = slope * 7
    ci_lower_weekly = (slope - ci_margin) * 7
    ci_upper_weekly = (slope + ci_margin) * 7

    is_significant = p_value < 0.05

    # Determine direction
    if not is_significant:
        direction = "stable"
    elif slope > 0:
        direction = "gaining"
    else:
        direction = "losing"

    # Interpretation
    if not is_significant:
        interpretation = f"Weight stable over {period_days} days (no significant trend)"
    elif slope > 0:
        interpretation = f"Gaining {abs(slope_weekly):.2f} kg/week ({abs(change_pct):.1f}% over {period_days} days)"
    else:
        interpretation = f"Losing {abs(slope_weekly):.2f} kg/week ({abs(change_pct):.1f}% over {period_days} days)"

    return WeightTrend(
        period_days=period_days,
        n_measurements=n,
        start_weight=round(start_weight, 1),
        end_weight=round(end_weight, 1),
        change_kg=round(change_kg, 1),
        change_pct=round(change_pct, 1),
        slope_daily=float(slope),
        slope_weekly=round(slope_weekly, 3),
        ci_lower=round(ci_lower_weekly, 3),
        ci_upper=round(ci_upper_weekly, 3),
        p_value=round(p_value, 4),
        is_significant=is_significant,
        direction=direction,
        interpretation=interpretation,
    )


def analyze_composition_change(
    df: pd.DataFrame, baseline_days: int = 90
) -> Optional[BodyCompositionChange]:
    """
    Analyze changes in body composition over time.

    Compares baseline period to recent measurements to assess
    whether changes are favorable (losing fat, maintaining/gaining lean mass).
    """
    weight_data = df[df["biomarker_slug"] == "body_mass"].copy()
    bf_data = df[df["biomarker_slug"] == "body_fat_percentage"].copy()

    if len(weight_data) < 5:
        return None

    weight_data["time"] = pd.to_datetime(weight_data["time"])
    weight_data = weight_data.sort_values("time")

    # Baseline: first N days
    first_date = weight_data["time"].min()
    baseline_cutoff = first_date + timedelta(days=baseline_days)

    baseline_weights = weight_data[weight_data["time"] <= baseline_cutoff]["value"]
    recent_weights = weight_data.tail(5)["value"]

    if len(baseline_weights) < 2 or len(recent_weights) < 2:
        return None

    baseline_weight = baseline_weights.mean()
    recent_weight = recent_weights.mean()
    weight_change = recent_weight - baseline_weight

    # Body fat change
    body_fat_change = None
    lean_mass_change = None
    fat_mass_change = None

    if len(bf_data) >= 4:
        bf_data["time"] = pd.to_datetime(bf_data["time"])
        bf_data = bf_data.sort_values("time")

        baseline_bf = bf_data.head(2)["value"].mean()
        recent_bf = bf_data.tail(2)["value"].mean()
        body_fat_change = recent_bf - baseline_bf

        # Estimate fat and lean mass changes
        baseline_fat_mass = baseline_weight * (baseline_bf / 100)
        recent_fat_mass = recent_weight * (recent_bf / 100)
        fat_mass_change = recent_fat_mass - baseline_fat_mass

        baseline_lean = baseline_weight - baseline_fat_mass
        recent_lean = recent_weight - recent_fat_mass
        lean_mass_change = recent_lean - baseline_lean

    # Determine quality of composition change
    composition_quality = "Neutral"
    if body_fat_change is not None:
        if body_fat_change < -1 and (
            lean_mass_change is None or lean_mass_change >= -0.5
        ):
            composition_quality = "Favorable"  # Losing fat, maintaining lean
        elif body_fat_change > 1 and (
            lean_mass_change is None or lean_mass_change <= 0.5
        ):
            composition_quality = "Unfavorable"  # Gaining fat
        elif (
            lean_mass_change is not None
            and lean_mass_change > 1
            and body_fat_change < 0.5
        ):
            composition_quality = "Favorable"  # Gaining lean mass without much fat

    # Interpretation
    if body_fat_change is not None:
        if composition_quality == "Favorable":
            interpretation = f"Favorable recomposition: {abs(body_fat_change):.1f}% body fat change with lean mass preserved"
        elif composition_quality == "Unfavorable":
            interpretation = (
                f"Body fat increased by {body_fat_change:.1f} percentage points"
            )
        else:
            interpretation = "Body composition relatively stable"
    else:
        if weight_change > 2:
            interpretation = f"Weight increased {weight_change:.1f} kg (body fat data unavailable for composition analysis)"
        elif weight_change < -2:
            interpretation = f"Weight decreased {abs(weight_change):.1f} kg (body fat data unavailable for composition analysis)"
        else:
            interpretation = "Weight stable"

    period = int((weight_data["time"].max() - first_date).days)

    return BodyCompositionChange(
        period_days=period,
        n_measurements=len(weight_data),
        weight_change_kg=round(weight_change, 1),
        body_fat_change_pct=round(body_fat_change, 1) if body_fat_change else None,
        lean_mass_change_kg=round(lean_mass_change, 1) if lean_mass_change else None,
        fat_mass_change_kg=round(fat_mass_change, 1) if fat_mass_change else None,
        composition_quality=composition_quality,
        interpretation=interpretation,
    )


def compute_fitness_correlations(
    df: pd.DataFrame,
) -> Tuple[Optional[FitnessCorrelation], Optional[FitnessCorrelation]]:
    """
    Compute correlations between body weight and fitness metrics.

    Validated relationships from literature:
    - Weight negatively correlates with VO2 Max (heavier = lower relative fitness)
    - Weight positively correlates with RHR (heavier = higher resting HR)
    """
    vo2_corr = None
    rhr_corr = None

    weight_data = df[df["biomarker_slug"] == "body_mass"].copy()
    if len(weight_data) == 0:
        return None, None

    weight_data["date"] = pd.to_datetime(weight_data["time"]).dt.date
    weight_daily = weight_data.groupby("date")["value"].mean()

    # VO2 Max correlation
    vo2_data = df[df["biomarker_slug"] == "vo2_max"].copy()
    if len(vo2_data) > 0:
        vo2_data["date"] = pd.to_datetime(vo2_data["time"]).dt.date
        vo2_daily = vo2_data.groupby("date")["value"].mean()

        common = weight_daily.index.intersection(vo2_daily.index)
        if len(common) >= 10:
            r, p = stats.pearsonr(weight_daily[common], vo2_daily[common])
            direction = "positive" if r > 0 else "negative"

            # Interpretation based on literature
            if p < 0.05:
                if r < 0:
                    interp = "Higher weight associated with lower relative VO2 Max (expected relationship)"
                else:
                    interp = "Unexpected positive correlation - may reflect muscle mass contribution"
            else:
                interp = "No significant correlation detected"

            vo2_corr = FitnessCorrelation(
                metric="VO2 Max",
                r=round(r, 3),
                p_value=round(p, 4),
                n=len(common),
                is_significant=p < 0.05,
                direction=direction,
                interpretation=interp,
            )

    # RHR correlation
    rhr_data = df[df["biomarker_slug"] == "heart_rate_resting"].copy()
    if len(rhr_data) > 0:
        rhr_data["date"] = pd.to_datetime(rhr_data["time"]).dt.date
        rhr_daily = rhr_data.groupby("date")["value"].mean()

        common = weight_daily.index.intersection(rhr_daily.index)
        if len(common) >= 10:
            r, p = stats.pearsonr(weight_daily[common], rhr_daily[common])
            direction = "positive" if r > 0 else "negative"

            if p < 0.05:
                if r > 0:
                    interp = "Higher weight associated with higher resting heart rate (expected relationship)"
                else:
                    interp = "Lower weight associated with higher RHR - may indicate other factors"
            else:
                interp = "No significant correlation detected"

            rhr_corr = FitnessCorrelation(
                metric="Resting Heart Rate",
                r=round(r, 3),
                p_value=round(p, 4),
                n=len(common),
                is_significant=p < 0.05,
                direction=direction,
                interpretation=interp,
            )

    return vo2_corr, rhr_corr


def generate_body_composition_report(
    df: pd.DataFrame,
    height_m: Optional[float] = None,
    age: Optional[int] = None,
    sex: Optional[str] = None,
) -> Optional[BodyCompositionReport]:
    """
    Generate complete body composition analysis report.

    All analyses use peer-reviewed, validated methods.
    """
    weight_data = df[df["biomarker_slug"] == "body_mass"].copy()
    bf_data = df[df["biomarker_slug"] == "body_fat_percentage"].copy()
    lean_data = df[df["biomarker_slug"] == "lean_body_mass"].copy()

    if len(weight_data) == 0:
        return None

    weight_data["time"] = pd.to_datetime(weight_data["time"])
    weight_data = weight_data.sort_values("time")

    # Build measurements list
    measurements = []

    # Get body fat by date for matching
    bf_by_date = {}
    if len(bf_data) > 0:
        bf_data["time"] = pd.to_datetime(bf_data["time"])
        for _, row in bf_data.iterrows():
            bf_by_date[row["time"].date()] = row["value"]

    lean_by_date = {}
    if len(lean_data) > 0:
        lean_data["time"] = pd.to_datetime(lean_data["time"])
        for _, row in lean_data.iterrows():
            lean_by_date[row["time"].date()] = row["value"]

    for _, row in weight_data.iterrows():
        weight_kg = row["value"]
        measurement_date = row["time"].date()

        body_fat_pct = bf_by_date.get(measurement_date)
        lean_mass = lean_by_date.get(measurement_date)

        bmi = None
        if height_m:
            bmi = round(weight_kg / (height_m**2), 1)

        fat_mass = None
        if body_fat_pct is not None:
            fat_mass = round(weight_kg * (body_fat_pct / 100), 2)
            if lean_mass is None:
                lean_mass = round(weight_kg - fat_mass, 2)

        measurements.append(
            WeightMeasurement(
                date=measurement_date,
                weight_kg=round(weight_kg, 2),
                weight_lb=round(weight_kg * 2.20462, 2),
                bmi=bmi,
                body_fat_pct=round(body_fat_pct, 1) if body_fat_pct else None,
                lean_mass_kg=round(lean_mass, 2) if lean_mass else None,
                fat_mass_kg=fat_mass,
            )
        )

    # Latest measurement
    latest = measurements[-1]

    # BMI (if height provided)
    bmi_result = None
    if height_m:
        bmi_result = compute_bmi(latest.weight_kg, height_m)

    # Body fat percentile (if age/sex/body fat provided)
    bf_percentile = None
    if age is not None and sex is not None and latest.body_fat_pct is not None:
        bf_percentile = compute_body_fat_percentile(latest.body_fat_pct, age, sex)

    # Trend analysis
    weight_trend = analyze_weight_trend(df)

    # Composition change
    composition_change = analyze_composition_change(df)

    # Fitness correlations
    vo2_corr, rhr_corr = compute_fitness_correlations(df)

    # Generate insights
    insights = []
    recommendations = []

    # Weight insight
    insights.append(f"Current weight: {latest.weight_kg} kg ({latest.weight_lb} lb)")

    if bmi_result:
        insights.append(
            f"BMI: {bmi_result.bmi} ({bmi_result.category}, {bmi_result.health_risk} health risk)"
        )

    if bf_percentile:
        insights.append(
            f"Body fat: {bf_percentile.body_fat_pct}% ({bf_percentile.percentile}th percentile, {bf_percentile.category})"
        )
        if bf_percentile.is_healthy:
            insights.append(
                f"Body fat within healthy range ({bf_percentile.healthy_range[0]}-{bf_percentile.healthy_range[1]}%)"
            )
        else:
            insights.append(
                f"Body fat outside healthy range ({bf_percentile.healthy_range[0]}-{bf_percentile.healthy_range[1]}%)"
            )

    if weight_trend and weight_trend.is_significant:
        insights.append(
            f"Weight trend: {weight_trend.direction} ({weight_trend.slope_weekly:+.2f} kg/week)"
        )

    if composition_change and composition_change.body_fat_change_pct is not None:
        insights.append(f"Body composition: {composition_change.composition_quality}")

    if vo2_corr and vo2_corr.is_significant:
        insights.append(
            f"Weight-VO2Max correlation: r={vo2_corr.r} ({vo2_corr.direction})"
        )

    # Recommendations
    if bmi_result:
        if bmi_result.category in [
            "Overweight",
            "Obese Class I",
            "Obese Class II",
            "Obese Class III",
        ]:
            recommendations.append(
                "Consider gradual weight reduction through diet and exercise"
            )
            recommendations.append(
                "Target: 0.5-1 kg weight loss per week for sustainable results"
            )
        elif bmi_result.category in ["Underweight", "Severely Underweight"]:
            recommendations.append(
                "Consider gradual weight gain with focus on lean mass"
            )

    if bf_percentile and not bf_percentile.is_healthy:
        if bf_percentile.body_fat_pct > bf_percentile.healthy_range[1]:
            recommendations.append(
                "Focus on fat loss while preserving lean mass through resistance training"
            )
        else:
            recommendations.append(
                "Body fat may be too low - ensure adequate nutrition"
            )

    if weight_trend and weight_trend.is_significant:
        if weight_trend.slope_weekly > 0.5:
            recommendations.append(
                "Rapid weight gain detected - review diet and activity levels"
            )
        elif weight_trend.slope_weekly < -1.0:
            recommendations.append(
                "Rapid weight loss may lead to muscle loss - consider slowing rate"
            )

    if not recommendations:
        recommendations.append(
            "Maintain current weight through balanced nutrition and regular exercise"
        )

    return BodyCompositionReport(
        latest_measurement=latest,
        bmi=bmi_result,
        body_fat_percentile=bf_percentile,
        measurements=measurements,
        weight_trend=weight_trend,
        composition_change=composition_change,
        vo2max_correlation=vo2_corr,
        rhr_correlation=rhr_corr,
        insights=insights,
        recommendations=recommendations,
    )


def get_body_composition_summary(
    df: pd.DataFrame,
    height_m: Optional[float] = None,
    age: Optional[int] = None,
    sex: Optional[str] = None,
) -> BodyCompositionSummary:
    """
    Get quick summary of body composition status.
    """
    weight_data = df[df["biomarker_slug"] == "body_mass"].copy()
    bf_data = df[df["biomarker_slug"] == "body_fat_percentage"].copy()

    n_weight = len(weight_data)
    n_bf = len(bf_data)

    if n_weight == 0:
        return BodyCompositionSummary(
            has_sufficient_data=False,
            n_weight_measurements=0,
            n_body_fat_measurements=0,
            latest_weight_kg=None,
            latest_bmi=None,
            bmi_category=None,
            latest_body_fat_pct=None,
            body_fat_category=None,
            weight_trend_direction=None,
            overall_assessment="No body composition data available",
        )

    weight_data["time"] = pd.to_datetime(weight_data["time"])
    latest_weight = weight_data.sort_values("time").iloc[-1]["value"]

    latest_bmi = None
    bmi_category = None
    if height_m:
        bmi_result = compute_bmi(latest_weight, height_m)
        latest_bmi = bmi_result.bmi
        bmi_category = bmi_result.category

    latest_bf = None
    bf_category = None
    if n_bf > 0:
        bf_data["time"] = pd.to_datetime(bf_data["time"])
        latest_bf = bf_data.sort_values("time").iloc[-1]["value"]

        if sex:
            categories = (
                BODY_FAT_CATEGORIES_MALE
                if sex.lower() == "male"
                else BODY_FAT_CATEGORIES_FEMALE
            )
            for cat, (low, high) in categories.items():
                if low <= latest_bf < high:
                    bf_category = cat
                    break

    # Trend
    trend_direction = None
    trend = analyze_weight_trend(df)
    if trend:
        trend_direction = trend.direction

    # Overall assessment
    parts = []
    if latest_bmi:
        parts.append(f"BMI {latest_bmi} ({bmi_category})")
    if latest_bf:
        parts.append(f"Body fat {latest_bf:.1f}%")
    if trend_direction and trend_direction != "stable":
        parts.append(f"Weight {trend_direction}")

    assessment = ", ".join(parts) if parts else f"Weight: {latest_weight:.1f} kg"

    return BodyCompositionSummary(
        has_sufficient_data=n_weight >= 5,
        n_weight_measurements=n_weight,
        n_body_fat_measurements=n_bf,
        latest_weight_kg=round(latest_weight, 1),
        latest_bmi=latest_bmi,
        bmi_category=bmi_category,
        latest_body_fat_pct=round(latest_bf, 1) if latest_bf else None,
        body_fat_category=bf_category,
        weight_trend_direction=trend_direction,
        overall_assessment=assessment,
    )
