"""Holistic Insights Module - Cross-domain synthesis and actionable insights.

This module synthesizes findings across all biomarker domains to provide:
1. Multi-dimensional wellness scoring
2. Cross-domain pattern detection (including paradoxes)
3. Behavioral pattern identification
4. Risk factor synthesis
5. Evidence-based, personalized recommendations

Philosophy: Transform raw biomarker data into actionable personal insights
by connecting dots that individual analyses miss.

References:
- Simpson's Paradox detection methodology
- Cross-domain lagged correlation analysis
- Composite wellness scoring with confidence weighting
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Literal
import numpy as np
import pandas as pd
from scipy import stats

# Import existing analysis types
from .proven import (
    CircadianResult,
    WeeklyActivityResult,
    TrendResult,
    AnomalyResult,
    HRVResult,
    SpO2Result,
    ConfidenceInterval,
)
from .advanced import (
    CorrelationMatrix,
    CorrelationPair,
    RecoveryModel,
    SeasonalAnalysis,
    ReadinessModel,
)
from .stability import StabilityReport
from .derived import DerivedMetricsReport
from .sleep import SleepArchitectureReport
from .daylight import DaylightReport
from .vo2max import VO2MaxReport
from .body_composition import BodyCompositionReport


# =============================================================================
# CORE RESULT TYPES
# =============================================================================

@dataclass
class Finding:
    """A single insight from the analysis.

    Findings are the atomic unit of insight - each represents one
    discovered pattern or observation with its supporting evidence.
    """
    category: str  # 'cardiovascular', 'sleep', 'activity', 'recovery', 'body_composition', 'circadian'
    severity: Literal['positive', 'neutral', 'concern', 'warning']
    title: str  # Brief headline (e.g., "Excellent cardiovascular fitness")
    description: str  # Detailed explanation
    evidence: str  # Statistical backing (e.g., "VO2 Max 48 mL/kg/min, 85th percentile")
    confidence: Literal['high', 'moderate', 'low']
    actionable: bool  # Can user do something about this?
    related_biomarkers: list[str] = field(default_factory=list)

    def __post_init__(self):
        valid_categories = {
            'cardiovascular', 'sleep', 'activity', 'recovery',
            'body_composition', 'circadian', 'behavioral', 'metabolic', 'mobility'
        }
        if self.category not in valid_categories:
            raise ValueError(f"Invalid category: {self.category}. Must be one of {valid_categories}")


@dataclass
class Interconnection:
    """A detected relationship between biomarker domains.

    Interconnections reveal how different health domains affect each other,
    enabling identification of root causes and downstream effects.
    """
    source_domain: str  # e.g., 'sleep'
    target_domain: str  # e.g., 'cardiovascular'
    source_biomarker: str  # e.g., 'sleep_duration'
    target_biomarker: str  # e.g., 'hrv_sdnn'
    relationship: Literal['positive', 'negative', 'complex']
    strength: Literal['strong', 'moderate', 'weak']
    pathway: str  # e.g., "Poor sleep → Lower HRV → Elevated RHR"
    correlation: float  # Pearson r
    p_value: float
    lag_days: int  # 0 = same day, 1 = next day effect, etc.
    sample_size: int
    interpretation: str  # Human-readable explanation

    @property
    def is_significant(self) -> bool:
        """Check if relationship is statistically significant at p < 0.05."""
        return self.p_value < 0.05

    @property
    def effect_size(self) -> str:
        """Categorize effect size using Cohen's conventions."""
        r_abs = abs(self.correlation)
        if r_abs >= 0.5:
            return 'large'
        elif r_abs >= 0.3:
            return 'medium'
        elif r_abs >= 0.1:
            return 'small'
        return 'negligible'


@dataclass
class Paradox:
    """A detected statistical paradox (e.g., Simpson's Paradox).

    Paradoxes occur when raw correlations tell a different story than
    the true causal relationship. Detecting these prevents misinterpretation.
    """
    name: str  # e.g., "Simpson's Paradox"
    biomarker_a: str
    biomarker_b: str
    raw_correlation: float
    raw_p_value: float
    detrended_correlation: float
    detrended_p_value: float
    confounding_factor: str  # What's causing the paradox (e.g., "time trend")
    explanation: str  # Full explanation for user
    behavioral_insight: Optional[str] = None  # e.g., "This is compensatory behavior"


@dataclass
class BehavioralPattern:
    """A detected behavioral pattern from the data.

    These patterns reveal HOW the user responds to health changes,
    which is often more actionable than the raw metrics themselves.
    """
    name: str  # e.g., "Compensatory Exercise"
    description: str
    evidence: str  # Statistical backing
    pattern_type: Literal['compensatory', 'cyclical', 'reactive', 'habitual']
    health_implication: Literal['positive', 'neutral', 'negative']
    recommendation: Optional[str] = None


@dataclass
class RiskFactor:
    """An identified health risk from combined signals.

    Risk factors synthesize multiple biomarkers into clinically meaningful
    risk assessments that are more actionable than individual metrics.
    """
    name: str  # e.g., "Cardiovascular strain"
    level: Literal['low', 'moderate', 'elevated', 'high']
    contributing_factors: list[str]  # What's driving this?
    trend: Literal['improving', 'stable', 'worsening']
    modifiable: bool  # Can user change this?
    evidence: str  # Statistical backing
    clinical_context: Optional[str] = None  # Reference to literature


@dataclass
class Recommendation:
    """An actionable, evidence-based suggestion.

    Recommendations are prioritized by impact and personalized based on
    the user's specific data patterns, not generic advice.
    """
    priority: Literal['high', 'medium', 'low']
    category: str  # 'sleep', 'activity', 'recovery', 'nutrition', etc.
    action: str  # Specific action to take
    rationale: str  # Why this will help (personalized)
    expected_impact: str  # What improvement to expect
    timeline: str  # When to expect results (e.g., "3-4 weeks")
    evidence_strength: Literal['strong', 'moderate', 'emerging']
    based_on: list[str] = field(default_factory=list)  # Which findings support this


@dataclass
class DomainScore:
    """Score for a single wellness domain."""
    score: float  # 0-100
    confidence: Literal['high', 'moderate', 'low']
    trend: Literal['improving', 'stable', 'declining']
    key_contributors: list[str]  # What's driving this score
    limiting_factors: list[str]  # What's holding it back
    data_points: int  # How much data backs this


@dataclass
class WellnessScore:
    """Multi-dimensional wellness assessment using Harmonic Mean.

    The overall score uses weighted harmonic mean of domain scores,
    which naturally penalizes imbalance - weak domains pull the score
    down more than strong domains pull it up.

    Mathematical basis: Adapted from V-Clock biological age research
    showing vector (domain-specific) approaches capture 1.78x more
    predictive information than scalar (simple average) approaches.

    Harmonic Mean properties:
    - H <= Geometric <= Arithmetic (always)
    - Naturally emphasizes lowest values
    - Incentivizes fixing weaknesses over boosting strengths
    - Validated on mortality prediction research
    """
    overall: float  # 0-100, Harmonic mean of domain scores

    # Domain scores
    cardiovascular: DomainScore
    sleep: DomainScore
    activity: DomainScore
    recovery: DomainScore
    body_composition: DomainScore
    mobility: Optional[DomainScore] = None  # Optional - requires mobility data

    # Explainability fields (for user understanding)
    arithmetic_mean: float = 0.0  # What simple average would give
    imbalance_penalty: float = 0.0  # How much imbalance costs (arithmetic - harmonic)
    bottleneck_domain: str = ""  # Which domain is holding score back most
    bottleneck_impact: float = 0.0  # How much that domain pulls down the score

    # Metadata
    computed_at: datetime = field(default_factory=datetime.now)
    analysis_period_days: int = 90

    @property
    def interpretation(self) -> str:
        """Human-readable interpretation of overall score."""
        if self.overall >= 85:
            return "Excellent"
        elif self.overall >= 70:
            return "Good"
        elif self.overall >= 55:
            return "Fair"
        elif self.overall >= 40:
            return "Needs Attention"
        return "Concerning"

    @property
    def strongest_domain(self) -> str:
        """Identify the highest-scoring domain."""
        domains = {
            'cardiovascular': self.cardiovascular.score,
            'sleep': self.sleep.score,
            'activity': self.activity.score,
            'recovery': self.recovery.score,
            'body_composition': self.body_composition.score,
        }
        if self.mobility is not None:
            domains['mobility'] = self.mobility.score
        return max(domains, key=domains.get)

    @property
    def weakest_domain(self) -> str:
        """Identify the lowest-scoring domain."""
        domains = {
            'cardiovascular': self.cardiovascular.score,
            'sleep': self.sleep.score,
            'activity': self.activity.score,
            'recovery': self.recovery.score,
            'body_composition': self.body_composition.score,
        }
        if self.mobility is not None:
            domains['mobility'] = self.mobility.score
        return min(domains, key=domains.get)


@dataclass
class DataAdequacy:
    """Assessment of data sufficiency for a biomarker."""
    biomarker: str
    status: Literal['sufficient', 'moderate', 'limited', 'missing']
    current_samples: int
    recommended_samples: int
    days_of_data: int
    reliability_score: float  # 0-1

    @property
    def adequacy_percentage(self) -> float:
        """Percentage of recommended samples collected."""
        if self.recommended_samples == 0:
            return 100.0
        return min(100.0, (self.current_samples / self.recommended_samples) * 100)


@dataclass
class HolisticInsight:
    """Complete holistic analysis result.

    This is the top-level result type that synthesizes all findings
    into a comprehensive, actionable health assessment.
    """
    # Timestamp and period
    generated_at: datetime
    analysis_period_start: date
    analysis_period_end: date

    # Overall assessment
    wellness_score: WellnessScore

    # Findings (prioritized)
    primary_findings: list[Finding]  # Top 5 most important
    secondary_findings: list[Finding]  # Supporting insights

    # Patterns
    interconnections: list[Interconnection]
    paradoxes: list[Paradox]
    behavioral_patterns: list[BehavioralPattern]

    # Risk assessment
    risk_factors: list[RiskFactor]
    protective_factors: list[str]

    # Recommendations
    recommendations: list[Recommendation]

    # Data quality
    data_adequacy: list[DataAdequacy]
    overall_confidence: Literal['high', 'moderate', 'low']

    # Trajectory
    trajectory: Literal['improving', 'stable', 'declining']
    trajectory_details: str

    @property
    def has_concerns(self) -> bool:
        """Check if any findings are concerning."""
        all_findings = self.primary_findings + self.secondary_findings
        return any(f.severity in ('concern', 'warning') for f in all_findings)

    @property
    def action_required(self) -> bool:
        """Check if high-priority recommendations exist."""
        return any(r.priority == 'high' for r in self.recommendations)


# =============================================================================
# SpO2 (BLOOD OXYGEN) ANALYSIS
# =============================================================================

@dataclass
class SpO2Analysis:
    """Analysis of blood oxygen saturation patterns.

    SpO2 is a highly reliable biomarker (CV=2.2%, stability=98.9%) that
    provides direct insight into respiratory efficiency. Night-time dips
    can indicate sleep-disordered breathing.

    Clinical thresholds:
    - Normal: 95-100%
    - Mild hypoxemia: 91-94%
    - Moderate hypoxemia: 86-90%
    - Severe hypoxemia: <86%
    """
    # Overall statistics
    mean: float
    std: float
    min_value: float
    max_value: float
    n_samples: int

    # Diurnal pattern
    night_mean: float  # 10pm - 6am
    day_mean: float    # 6am - 10pm
    night_day_difference: float  # day - night (positive = normal dip at night)
    diurnal_t_statistic: float
    diurnal_p_value: float
    diurnal_effect_size: float  # Cohen's d

    # Clinical flags
    pct_below_95: float  # Percentage of readings below 95%
    pct_below_90: float  # Percentage of readings below 90%
    night_pct_below_95: float  # Night-specific low readings
    has_concerning_pattern: bool

    # Interpretation
    overall_status: Literal['normal', 'borderline', 'concerning']
    interpretation: str
    recommendation: Optional[str] = None


def analyze_spo2(
    spo2_series: pd.Series,
    timestamps: pd.Series,
) -> Optional[SpO2Analysis]:
    """Analyze SpO2 patterns including diurnal variation.

    This analysis is based on statistical validation showing:
    - CV = 2.2% (highly consistent measurements)
    - Temporal stability = 98.9%
    - Significant diurnal pattern (t=-13.79, d=0.60)

    Args:
        spo2_series: SpO2 values (as percentages, 0-100)
        timestamps: Corresponding timestamps

    Returns:
        SpO2Analysis object or None if insufficient data
    """
    if len(spo2_series) < 30:
        return None

    values = spo2_series.dropna().values
    times = timestamps.loc[spo2_series.dropna().index]

    if len(values) < 30:
        return None

    # Convert timestamps to hours
    hours = pd.to_datetime(times).dt.hour

    # Separate night (10pm-6am) and day (6am-10pm)
    night_mask = (hours >= 22) | (hours < 6)
    day_mask = ~night_mask

    night_values = values[night_mask]
    day_values = values[day_mask]

    # Overall statistics
    mean_val = float(np.mean(values))
    std_val = float(np.std(values))
    min_val = float(np.min(values))
    max_val = float(np.max(values))

    # Diurnal pattern analysis
    if len(night_values) >= 10 and len(day_values) >= 10:
        night_mean = float(np.mean(night_values))
        day_mean = float(np.mean(day_values))
        diff = day_mean - night_mean

        # Two-sample t-test
        t_stat, p_value = stats.ttest_ind(day_values, night_values)

        # Cohen's d effect size
        pooled_std = np.sqrt((np.std(night_values)**2 + np.std(day_values)**2) / 2)
        cohens_d = diff / pooled_std if pooled_std > 0 else 0
    else:
        night_mean = mean_val
        day_mean = mean_val
        diff = 0
        t_stat = 0
        p_value = 1.0
        cohens_d = 0

    # Clinical thresholds
    pct_below_95 = float(np.sum(values < 95) / len(values) * 100)
    pct_below_90 = float(np.sum(values < 90) / len(values) * 100)
    night_pct_below_95 = float(np.sum(night_values < 95) / len(night_values) * 100) if len(night_values) > 0 else 0

    # Determine status
    has_concerning = (
        pct_below_95 > 20 or
        pct_below_90 > 5 or
        night_pct_below_95 > 30 or
        (diff > 1.5 and abs(cohens_d) > 0.5)  # Significant night dip
    )

    if pct_below_90 > 10 or night_pct_below_95 > 40:
        status = 'concerning'
    elif pct_below_95 > 15 or night_pct_below_95 > 25:
        status = 'borderline'
    else:
        status = 'normal'

    # Generate interpretation
    if status == 'normal':
        interpretation = f"Blood oxygen levels are healthy (mean {mean_val:.1f}%)."
        recommendation = None
    elif status == 'borderline':
        interpretation = (
            f"Blood oxygen shows some variability. "
            f"{night_pct_below_95:.0f}% of night readings are below 95%. "
            f"Night average ({night_mean:.1f}%) is {diff:.1f}% lower than day ({day_mean:.1f}%)."
        )
        recommendation = "Consider discussing with a healthcare provider if you experience daytime fatigue or snoring."
    else:
        interpretation = (
            f"Blood oxygen pattern warrants attention. "
            f"{night_pct_below_95:.0f}% of night readings below 95% (mean {night_mean:.1f}%). "
            f"This pattern may indicate sleep-disordered breathing."
        )
        recommendation = "Recommend consultation with a healthcare provider to evaluate for sleep apnea or other respiratory conditions."

    return SpO2Analysis(
        mean=mean_val,
        std=std_val,
        min_value=min_val,
        max_value=max_val,
        n_samples=len(values),
        night_mean=night_mean,
        day_mean=day_mean,
        night_day_difference=diff,
        diurnal_t_statistic=float(t_stat),
        diurnal_p_value=float(p_value),
        diurnal_effect_size=float(cohens_d),
        pct_below_95=pct_below_95,
        pct_below_90=pct_below_90,
        night_pct_below_95=night_pct_below_95,
        has_concerning_pattern=has_concerning,
        overall_status=status,
        interpretation=interpretation,
        recommendation=recommendation,
    )


# =============================================================================
# MOBILITY ANALYSIS
# =============================================================================

@dataclass
class MobilityAnalysis:
    """Analysis of mobility/gait metrics.

    Mobility metrics are clinically validated predictors of health and aging:
    - Walking speed is the "sixth vital sign" in geriatric medicine
    - Walking steadiness is FDA-validated for fall risk assessment

    Confound analysis confirmed:
    - Walking speed decline is 97% real (only 3% confounded by activity/season)
    - Step length and double_support are redundant with walking speed (r > 0.87)
    - Asymmetry is too variable for routine scoring (CV=305%)

    Integration approach:
    - Walking speed: Primary metric (70% weight in composite)
    - Walking steadiness: Secondary metric (30% weight, fall risk)
    - Asymmetry: Alert-only (flag sustained >10%)
    """
    # Walking speed statistics
    walking_speed_mean: float  # m/s
    walking_speed_std: float
    walking_speed_min: float
    walking_speed_max: float
    walking_speed_n: int

    # Walking speed clinical assessment
    walking_speed_status: Literal['excellent', 'normal', 'reduced', 'impaired']
    walking_speed_percentile: float  # Relative to historical data

    # Walking speed trend (confound-controlled)
    walking_speed_annual_change: float  # m/s per year
    walking_speed_trend_p_value: float
    walking_speed_trend_significant: bool

    # Walking steadiness (Apple/FDA validated)
    steadiness_mean: Optional[float]  # Percentage (0-100)
    steadiness_n: Optional[int]
    steadiness_status: Literal['ok', 'low', 'very_low', 'unknown']
    steadiness_pct_below_90: Optional[float]  # Fall risk threshold

    # Asymmetry (alert only)
    asymmetry_mean: Optional[float]  # Percentage
    asymmetry_alert: bool  # True if sustained >10%

    # Composite mobility score
    mobility_score: float  # 0-100
    mobility_trend: Literal['improving', 'stable', 'declining']

    # Clinical interpretation
    overall_status: Literal['excellent', 'good', 'fair', 'concerning']
    interpretation: str
    recommendation: Optional[str] = None

    # Activity-adjusted metrics (controlling for confound)
    activity_adjusted_speed: Optional[float] = None


def analyze_mobility(
    walking_speed_series: pd.Series,
    walking_speed_timestamps: pd.Series,
    steps_series: Optional[pd.Series] = None,
    steadiness_series: Optional[pd.Series] = None,
    asymmetry_series: Optional[pd.Series] = None,
) -> Optional[MobilityAnalysis]:
    """Analyze mobility metrics with confound control.

    This analysis is based on rigorous statistical validation:
    - Walking speed decline is 97% real after controlling for confounds
    - Steadiness has CV=4% (highly reliable)
    - Step length/double_support excluded due to r>0.87 redundancy

    Args:
        walking_speed_series: Walking speed values (m/s)
        walking_speed_timestamps: Corresponding timestamps
        steps_series: Optional daily step counts (for confound control)
        steadiness_series: Optional walking steadiness values (%)
        asymmetry_series: Optional walking asymmetry values (%)

    Returns:
        MobilityAnalysis object or None if insufficient data
    """
    if len(walking_speed_series) < 30:
        return None

    ws_values = walking_speed_series.dropna().values
    ws_times = walking_speed_timestamps.loc[walking_speed_series.dropna().index]

    if len(ws_values) < 30:
        return None

    # =========================================================================
    # WALKING SPEED ANALYSIS
    # =========================================================================

    # Basic statistics
    ws_mean = float(np.mean(ws_values))
    ws_std = float(np.std(ws_values))
    ws_min = float(np.min(ws_values))
    ws_max = float(np.max(ws_values))

    # Clinical status (thresholds from geriatric literature)
    # >1.2 m/s = excellent, >1.0 = normal, >0.8 = reduced, <0.8 = impaired
    if ws_mean >= 1.2:
        ws_status = 'excellent'
    elif ws_mean >= 1.0:
        ws_status = 'normal'
    elif ws_mean >= 0.8:
        ws_status = 'reduced'
    else:
        ws_status = 'impaired'

    # Percentile (relative to own history)
    ws_percentile = float(stats.percentileofscore(ws_values, ws_mean))

    # Trend analysis with confound control
    ws_df = pd.DataFrame({
        'time': pd.to_datetime(ws_times),
        'value': ws_values
    })
    ws_df['date'] = ws_df['time'].dt.date
    ws_daily = ws_df.groupby('date')['value'].mean()
    ws_daily.index = pd.to_datetime(ws_daily.index)

    # Time index for regression
    time_idx = (ws_daily.index - ws_daily.index.min()).days.values.astype(float)

    if len(time_idx) >= 30:
        # Raw trend
        slope, intercept, r, p, se = stats.linregress(time_idx, ws_daily.values)
        annual_change_raw = slope * 365

        # If steps available, compute activity-controlled trend
        if steps_series is not None and len(steps_series) >= 30:
            steps_daily = steps_series.copy()
            steps_daily.index = pd.to_datetime(steps_daily.index)

            # Align indices
            common_idx = ws_daily.index.intersection(steps_daily.index)
            if len(common_idx) >= 30:
                ws_aligned = ws_daily.loc[common_idx].values
                steps_aligned = steps_daily.loc[common_idx].values
                time_aligned = (common_idx - common_idx.min()).days.values.astype(float)

                # Residualize walking speed on steps
                slope_s, int_s, _, _, _ = stats.linregress(steps_aligned, ws_aligned)
                ws_resid = ws_aligned - (slope_s * steps_aligned + int_s)

                # Trend on residualized values
                slope_adj, _, _, p_adj, _ = stats.linregress(time_aligned, ws_resid)
                annual_change = slope_adj * 365
                trend_p = p_adj

                # Activity-adjusted mean
                activity_adj_speed = float(np.mean(ws_resid) + ws_mean)
            else:
                annual_change = annual_change_raw
                trend_p = p
                activity_adj_speed = None
        else:
            annual_change = annual_change_raw
            trend_p = p
            activity_adj_speed = None

        trend_significant = trend_p < 0.05
    else:
        annual_change = 0.0
        trend_p = 1.0
        trend_significant = False
        activity_adj_speed = None

    # =========================================================================
    # WALKING STEADINESS ANALYSIS (Apple/FDA validated)
    # =========================================================================

    if steadiness_series is not None and len(steadiness_series.dropna()) >= 10:
        st_values = steadiness_series.dropna().values
        st_mean = float(np.mean(st_values))
        st_n = len(st_values)
        st_pct_below_90 = float(np.sum(st_values < 90) / len(st_values) * 100)

        # Apple's clinical thresholds
        if st_mean >= 90:
            st_status = 'ok'  # Low fall risk
        elif st_mean >= 80:
            st_status = 'low'  # Moderate fall risk
        else:
            st_status = 'very_low'  # High fall risk
    else:
        st_mean = None
        st_n = None
        st_pct_below_90 = None
        st_status = 'unknown'

    # =========================================================================
    # ASYMMETRY ANALYSIS (Alert only)
    # =========================================================================

    if asymmetry_series is not None and len(asymmetry_series.dropna()) >= 10:
        asym_values = asymmetry_series.dropna().values
        asym_mean = float(np.mean(asym_values))

        # Alert if sustained asymmetry >10%
        # Check last 30 days or all data if less
        recent_asym = asymmetry_series.dropna().tail(30).values
        asym_alert = float(np.mean(recent_asym)) > 10 if len(recent_asym) >= 5 else False
    else:
        asym_mean = None
        asym_alert = False

    # =========================================================================
    # COMPOSITE MOBILITY SCORE
    # =========================================================================

    # Walking speed component (0-100, 70% weight)
    # Score based on clinical thresholds
    if ws_mean >= 1.4:
        ws_score = 100
    elif ws_mean >= 1.2:
        ws_score = 90
    elif ws_mean >= 1.0:
        ws_score = 75
    elif ws_mean >= 0.8:
        ws_score = 55
    elif ws_mean >= 0.6:
        ws_score = 35
    else:
        ws_score = 20

    # Steadiness component (0-100, 30% weight)
    if st_mean is not None:
        if st_mean >= 95:
            st_score = 100
        elif st_mean >= 90:
            st_score = 85
        elif st_mean >= 85:
            st_score = 65
        elif st_mean >= 80:
            st_score = 45
        else:
            st_score = 25

        # Composite score
        mobility_score = 0.7 * ws_score + 0.3 * st_score
    else:
        # No steadiness data - use walking speed only
        mobility_score = ws_score

    # Determine trend
    if annual_change > 0.02 and trend_significant:
        mobility_trend = 'improving'
    elif annual_change < -0.02 and trend_significant:
        mobility_trend = 'declining'
    else:
        mobility_trend = 'stable'

    # =========================================================================
    # CLINICAL INTERPRETATION
    # =========================================================================

    # Overall status
    if mobility_score >= 85:
        overall_status = 'excellent'
    elif mobility_score >= 70:
        overall_status = 'good'
    elif mobility_score >= 55:
        overall_status = 'fair'
    else:
        overall_status = 'concerning'

    # Generate interpretation
    interpretation_parts = []

    # Walking speed interpretation
    interpretation_parts.append(
        f"Walking speed ({ws_mean:.2f} m/s) is {ws_status}."
    )

    # Trend interpretation
    if trend_significant and abs(annual_change) > 0.01:
        direction = "declining" if annual_change < 0 else "improving"
        interpretation_parts.append(
            f"Mobility is {direction} at {abs(annual_change):.3f} m/s per year "
            f"(statistically significant, confound-controlled)."
        )

    # Steadiness interpretation
    if st_status != 'unknown':
        risk_level = {
            'ok': 'low',
            'low': 'moderate',
            'very_low': 'elevated'
        }.get(st_status, 'unknown')
        interpretation_parts.append(
            f"Walking steadiness ({st_mean:.1f}%) indicates {risk_level} fall risk."
        )

    # Asymmetry alert
    if asym_alert:
        interpretation_parts.append(
            f"ALERT: Sustained walking asymmetry ({asym_mean:.1f}%) may indicate "
            f"injury, weakness, or other gait abnormality."
        )

    interpretation = " ".join(interpretation_parts)

    # Generate recommendation
    recommendation = None
    if overall_status == 'concerning':
        recommendation = (
            "Consider discussing mobility concerns with a healthcare provider. "
            "Walking speed below 0.8 m/s is associated with increased health risks."
        )
    elif st_status in ('low', 'very_low'):
        recommendation = (
            "Walking steadiness indicates increased fall risk. "
            "Consider balance exercises and discussing with a healthcare provider."
        )
    elif mobility_trend == 'declining' and trend_significant:
        recommendation = (
            "Mobility is showing a declining trend. Consider regular walking exercise "
            "and strength training to maintain gait health."
        )
    elif asym_alert:
        recommendation = (
            "Sustained walking asymmetry detected. Consider evaluation by a "
            "physical therapist to identify and address any underlying issues."
        )

    return MobilityAnalysis(
        walking_speed_mean=ws_mean,
        walking_speed_std=ws_std,
        walking_speed_min=ws_min,
        walking_speed_max=ws_max,
        walking_speed_n=len(ws_values),
        walking_speed_status=ws_status,
        walking_speed_percentile=ws_percentile,
        walking_speed_annual_change=annual_change,
        walking_speed_trend_p_value=trend_p,
        walking_speed_trend_significant=trend_significant,
        steadiness_mean=st_mean,
        steadiness_n=st_n,
        steadiness_status=st_status,
        steadiness_pct_below_90=st_pct_below_90,
        asymmetry_mean=asym_mean,
        asymmetry_alert=asym_alert,
        mobility_score=mobility_score,
        mobility_trend=mobility_trend,
        overall_status=overall_status,
        interpretation=interpretation,
        recommendation=recommendation,
        activity_adjusted_speed=activity_adj_speed,
    )


# =============================================================================
# DATA AGGREGATION
# =============================================================================

@dataclass
class AnalysisInputs:
    """Aggregated inputs for holistic analysis.

    Collects all existing analysis results and raw signals needed
    for cross-domain synthesis.
    """
    # Raw time-series data
    signals: pd.DataFrame  # columns: time, biomarker_slug, value

    # Pre-computed analyses (will compute if None)
    circadian: Optional[CircadianResult] = None
    weekly_activity: Optional[WeeklyActivityResult] = None
    correlations: Optional[CorrelationMatrix] = None
    recovery: Optional[RecoveryModel] = None
    seasonality: Optional[SeasonalAnalysis] = None
    readiness: Optional[ReadinessModel] = None
    stability: Optional[StabilityReport] = None
    derived: Optional[DerivedMetricsReport] = None
    sleep: Optional[SleepArchitectureReport] = None
    daylight: Optional[DaylightReport] = None
    vo2max: Optional[VO2MaxReport] = None
    body_composition: Optional[BodyCompositionReport] = None

    # Trend analyses by biomarker
    trends: dict[str, TrendResult] = field(default_factory=dict)

    # User context
    user_age: Optional[int] = None
    user_sex: Optional[Literal['male', 'female']] = None

    # Analysis parameters
    analysis_window_days: int = 90


def aggregate_signals(signals: pd.DataFrame) -> dict[str, pd.Series]:
    """Aggregate signals by biomarker for analysis.

    Args:
        signals: DataFrame with columns [time, biomarker_slug, value]

    Returns:
        Dictionary mapping biomarker slug to Series indexed by date
    """
    result = {}

    for biomarker in signals['biomarker_slug'].unique():
        biomarker_data = signals[signals['biomarker_slug'] == biomarker].copy()
        biomarker_data['date'] = pd.to_datetime(biomarker_data['time']).dt.date

        # Aggregate to daily (mean for most, sum for counts/durations like steps and sleep)
        sum_biomarkers = (
            'steps', 'active_energy', 'flights_climbed', 'exercise_time',
            'sleep_rem', 'sleep_deep', 'sleep_core', 'sleep_duration',
        )
        if biomarker in sum_biomarkers:
            daily = biomarker_data.groupby('date')['value'].sum()
        else:
            daily = biomarker_data.groupby('date')['value'].mean()

        result[biomarker] = daily

    return result


def compute_data_adequacy(
    signals: pd.DataFrame,
    min_samples: dict[str, int] = None
) -> list[DataAdequacy]:
    """Assess data adequacy for each biomarker.

    Args:
        signals: DataFrame with columns [time, biomarker_slug, value]
        min_samples: Optional dict of biomarker -> minimum recommended samples

    Returns:
        List of DataAdequacy assessments
    """
    if min_samples is None:
        min_samples = {
            'heart_rate': 100,
            'hrv_sdnn': 30,
            'hrv_rmssd': 30,
            'heart_rate_resting': 30,
            'spo2': 30,  # Blood oxygen - highly reliable (CV=2.2%)
            'steps': 30,
            'sleep_duration': 14,
            'sleep_rem': 14,
            'sleep_deep': 14,
            'vo2_max': 5,
            'body_mass': 10,
            'body_fat_percentage': 5,
            'time_in_daylight': 14,
        }

    default_min = 30
    results = []

    for biomarker in signals['biomarker_slug'].unique():
        biomarker_data = signals[signals['biomarker_slug'] == biomarker]
        n_samples = len(biomarker_data)

        # Calculate days of data
        if len(biomarker_data) > 0:
            dates = pd.to_datetime(biomarker_data['time']).dt.date
            days_of_data = (dates.max() - dates.min()).days + 1
        else:
            days_of_data = 0

        recommended = min_samples.get(biomarker, default_min)

        # Determine status
        ratio = n_samples / recommended if recommended > 0 else 1.0
        if ratio >= 1.0:
            status = 'sufficient'
            reliability = min(1.0, ratio)
        elif ratio >= 0.5:
            status = 'moderate'
            reliability = ratio
        elif ratio > 0:
            status = 'limited'
            reliability = ratio
        else:
            status = 'missing'
            reliability = 0.0

        results.append(DataAdequacy(
            biomarker=biomarker,
            status=status,
            current_samples=n_samples,
            recommended_samples=recommended,
            days_of_data=days_of_data,
            reliability_score=reliability,
        ))

    return results


# =============================================================================
# CORRELATION UTILITIES
# =============================================================================

def compute_correlation(
    x: pd.Series,
    y: pd.Series,
    min_samples: int = 30
) -> tuple[float, float, int]:
    """Compute Pearson correlation with p-value.

    Args:
        x: First series
        y: Second series
        min_samples: Minimum overlapping samples required

    Returns:
        Tuple of (correlation, p_value, sample_size)
    """
    # Align by index
    common_idx = x.index.intersection(y.index)

    if len(common_idx) < min_samples:
        return (np.nan, np.nan, len(common_idx))

    x_aligned = x.loc[common_idx].dropna()
    y_aligned = y.loc[common_idx].dropna()

    # Re-align after dropping NaN
    common_idx = x_aligned.index.intersection(y_aligned.index)

    if len(common_idx) < min_samples:
        return (np.nan, np.nan, len(common_idx))

    x_final = x_aligned.loc[common_idx]
    y_final = y_aligned.loc[common_idx]

    r, p = stats.pearsonr(x_final, y_final)

    return (r, p, len(common_idx))


def compute_detrended_correlation(
    x: pd.Series,
    y: pd.Series,
    window: int = 30,
    min_samples: int = 30
) -> tuple[float, float, int]:
    """Compute correlation after removing rolling mean trend.

    This helps detect Simpson's paradox by removing time-based confounds.

    Args:
        x: First series (indexed by date)
        y: Second series (indexed by date)
        window: Rolling window size for detrending
        min_samples: Minimum samples required

    Returns:
        Tuple of (correlation, p_value, sample_size)
    """
    # Ensure sorted by index
    x = x.sort_index()
    y = y.sort_index()

    # Compute rolling means
    x_rolling = x.rolling(window=window, min_periods=window//2).mean()
    y_rolling = y.rolling(window=window, min_periods=window//2).mean()

    # Compute deviations from rolling mean
    x_detrended = x - x_rolling
    y_detrended = y - y_rolling

    # Drop NaN from detrending
    x_detrended = x_detrended.dropna()
    y_detrended = y_detrended.dropna()

    return compute_correlation(x_detrended, y_detrended, min_samples)


def compute_lagged_correlation(
    x: pd.Series,
    y: pd.Series,
    lag_days: int,
    min_samples: int = 30
) -> tuple[float, float, int]:
    """Compute correlation with time lag.

    Positive lag means x predicts future y.

    Args:
        x: Predictor series (indexed by date)
        y: Outcome series (indexed by date)
        lag_days: Number of days to shift y (positive = x predicts future y)
        min_samples: Minimum samples required

    Returns:
        Tuple of (correlation, p_value, sample_size)
    """
    # Shift y back by lag_days (so we're comparing x[t] with y[t+lag])
    y_shifted = y.copy()
    y_shifted.index = pd.to_datetime(y_shifted.index) - pd.Timedelta(days=lag_days)
    y_shifted.index = y_shifted.index.date

    return compute_correlation(x, y_shifted, min_samples)


# =============================================================================
# PARADOX DETECTION
# =============================================================================

def detect_simpsons_paradox(
    x: pd.Series,
    y: pd.Series,
    x_name: str,
    y_name: str,
    threshold: float = 0.15,
    min_samples: int = 30
) -> Optional[Paradox]:
    """Detect Simpson's Paradox between two variables.

    Simpson's Paradox occurs when the raw correlation has a different
    sign or magnitude than the detrended correlation, indicating a
    confounding time trend.

    Args:
        x: First variable series
        y: Second variable series
        x_name: Name of first variable
        y_name: Name of second variable
        threshold: Minimum difference to flag as paradox
        min_samples: Minimum samples required

    Returns:
        Paradox object if detected, None otherwise
    """
    raw_r, raw_p, raw_n = compute_correlation(x, y, min_samples)
    detrended_r, detrended_p, detrended_n = compute_detrended_correlation(
        x, y, window=30, min_samples=min_samples
    )

    if np.isnan(raw_r) or np.isnan(detrended_r):
        return None

    # Check for paradox conditions:
    # 1. Signs differ
    # 2. OR magnitude differs significantly
    sign_differs = (raw_r > 0) != (detrended_r > 0) and abs(raw_r) > 0.1
    magnitude_differs = abs(raw_r - detrended_r) > threshold

    if not (sign_differs or magnitude_differs):
        return None

    # Determine the confounding explanation
    if sign_differs:
        if raw_r > 0 and detrended_r <= 0:
            explanation = (
                f"Raw correlation between {x_name} and {y_name} appears positive "
                f"(r={raw_r:.3f}), but after removing time trends, the relationship "
                f"is near zero or negative (r={detrended_r:.3f}). This suggests "
                f"both variables are trending in the same direction over time, "
                f"creating a spurious positive correlation."
            )
            behavioral = (
                "This pattern often indicates compensatory behavior - you may "
                f"increase {x_name} when {y_name} is higher."
            )
        else:
            explanation = (
                f"Raw correlation between {x_name} and {y_name} appears negative "
                f"(r={raw_r:.3f}), but after removing time trends, the relationship "
                f"differs (r={detrended_r:.3f}). A time-based confound is present."
            )
            behavioral = None
    else:
        explanation = (
            f"The relationship between {x_name} and {y_name} changes significantly "
            f"when time trends are removed (raw r={raw_r:.3f}, detrended r={detrended_r:.3f}). "
            f"This suggests a temporal confound is affecting the correlation."
        )
        behavioral = None

    return Paradox(
        name="Simpson's Paradox",
        biomarker_a=x_name,
        biomarker_b=y_name,
        raw_correlation=raw_r,
        raw_p_value=raw_p,
        detrended_correlation=detrended_r,
        detrended_p_value=detrended_p,
        confounding_factor="time trend",
        explanation=explanation,
        behavioral_insight=behavioral,
    )


def detect_all_paradoxes(
    signals_by_biomarker: dict[str, pd.Series],
    biomarker_pairs: Optional[list[tuple[str, str]]] = None,
    min_samples: int = 30
) -> list[Paradox]:
    """Detect paradoxes across multiple biomarker pairs.

    Args:
        signals_by_biomarker: Dict mapping biomarker slug to daily series
        biomarker_pairs: Optional list of pairs to check. If None, checks common pairs.
        min_samples: Minimum samples required

    Returns:
        List of detected Paradox objects
    """
    if biomarker_pairs is None:
        # Default pairs known to sometimes exhibit paradoxes
        biomarker_pairs = [
            ('steps', 'body_mass'),
            ('active_energy', 'body_mass'),
            ('exercise_time', 'body_mass'),
            ('steps', 'heart_rate_resting'),
            ('sleep_duration', 'body_mass'),
        ]

    paradoxes = []

    for x_name, y_name in biomarker_pairs:
        if x_name not in signals_by_biomarker or y_name not in signals_by_biomarker:
            continue

        paradox = detect_simpsons_paradox(
            signals_by_biomarker[x_name],
            signals_by_biomarker[y_name],
            x_name,
            y_name,
            min_samples=min_samples,
        )

        if paradox is not None:
            paradoxes.append(paradox)

    return paradoxes


# =============================================================================
# BEHAVIORAL PATTERN DETECTION
# =============================================================================

def detect_compensatory_exercise(
    weight: pd.Series,
    activity: pd.Series,
    min_samples: int = 30
) -> Optional[BehavioralPattern]:
    """Detect if user exercises more when weight is higher.

    This is a healthy compensatory behavior where increased weight
    triggers increased activity.

    Args:
        weight: Weight series indexed by date
        activity: Activity measure (steps, active_energy) indexed by date
        min_samples: Minimum samples required

    Returns:
        BehavioralPattern if detected, None otherwise
    """
    # Align data
    common_idx = weight.index.intersection(activity.index)
    if len(common_idx) < min_samples:
        return None

    weight_aligned = weight.loc[common_idx]
    activity_aligned = activity.loc[common_idx]

    # Split into weight quartiles
    weight_quartiles = pd.qcut(weight_aligned, 4, labels=['Q1', 'Q2', 'Q3', 'Q4'])

    # Calculate mean activity per quartile
    activity_by_quartile = {}
    for q in ['Q1', 'Q2', 'Q3', 'Q4']:
        mask = weight_quartiles == q
        if mask.sum() >= 5:
            activity_by_quartile[q] = activity_aligned[mask].mean()

    if len(activity_by_quartile) < 4:
        return None

    # Check if higher weight quartiles have higher activity
    q1_activity = activity_by_quartile.get('Q1', 0)
    q4_activity = activity_by_quartile.get('Q4', 0)

    # Compensatory pattern: Q4 (highest weight) has more activity than Q1 (lowest)
    if q4_activity > q1_activity * 1.1:  # At least 10% more
        pct_increase = ((q4_activity - q1_activity) / q1_activity) * 100

        return BehavioralPattern(
            name="Compensatory Exercise",
            description=(
                f"You exercise more when your weight is higher. "
                f"At your highest weight quartile, activity is {pct_increase:.0f}% higher "
                f"than at your lowest weight quartile."
            ),
            evidence=(
                f"Q1 (lowest weight): {q1_activity:.0f} avg activity, "
                f"Q4 (highest weight): {q4_activity:.0f} avg activity"
            ),
            pattern_type='compensatory',
            health_implication='positive',
            recommendation=(
                "This is a healthy adaptive response. Your body naturally "
                "drives you to move more when weight increases. Trust this instinct."
            ),
        )

    return None


def detect_weekend_warrior(
    activity: pd.Series,
    min_weeks: int = 4
) -> Optional[BehavioralPattern]:
    """Detect if activity is concentrated on weekends.

    Args:
        activity: Daily activity series indexed by date
        min_weeks: Minimum weeks of data required

    Returns:
        BehavioralPattern if pattern detected, None otherwise
    """
    if len(activity) < min_weeks * 7:
        return None

    # Convert index to datetime and get day of week
    activity_df = pd.DataFrame({'activity': activity})
    activity_df.index = pd.to_datetime(activity_df.index)
    activity_df['dow'] = activity_df.index.dayofweek  # 0=Mon, 6=Sun
    activity_df['is_weekend'] = activity_df['dow'].isin([5, 6])

    weekend_mean = activity_df[activity_df['is_weekend']]['activity'].mean()
    weekday_mean = activity_df[~activity_df['is_weekend']]['activity'].mean()

    if weekday_mean == 0:
        return None

    ratio = weekend_mean / weekday_mean

    if ratio > 1.5:  # Weekend activity is 50%+ higher
        return BehavioralPattern(
            name="Weekend Warrior",
            description=(
                f"Your activity is concentrated on weekends. "
                f"Weekend activity is {(ratio-1)*100:.0f}% higher than weekdays."
            ),
            evidence=(
                f"Weekend avg: {weekend_mean:.0f}, Weekday avg: {weekday_mean:.0f}"
            ),
            pattern_type='cyclical',
            health_implication='neutral',
            recommendation=(
                "Consider distributing activity more evenly across the week. "
                "Consistency provides better cardiovascular benefits than sporadic bursts."
            ),
        )

    return None


def detect_seasonal_activity_pattern(
    activity: pd.Series,
    min_months: int = 6
) -> Optional[BehavioralPattern]:
    """Detect seasonal variation in activity levels.

    Args:
        activity: Daily activity series indexed by date
        min_months: Minimum months of data required

    Returns:
        BehavioralPattern if seasonal pattern detected, None otherwise
    """
    activity_df = pd.DataFrame({'activity': activity})
    activity_df.index = pd.to_datetime(activity_df.index)

    # Need at least min_months of data
    date_range = (activity_df.index.max() - activity_df.index.min()).days
    if date_range < min_months * 30:
        return None

    # Group by season
    def get_season(month):
        if month in [12, 1, 2]:
            return 'Winter'
        elif month in [3, 4, 5]:
            return 'Spring'
        elif month in [6, 7, 8]:
            return 'Summer'
        return 'Fall'

    activity_df['season'] = activity_df.index.month.map(get_season)

    season_means = activity_df.groupby('season')['activity'].mean()

    if len(season_means) < 3:
        return None

    max_season = season_means.idxmax()
    min_season = season_means.idxmin()
    max_val = season_means[max_season]
    min_val = season_means[min_season]

    if min_val == 0:
        return None

    variation = (max_val - min_val) / min_val

    if variation > 0.3:  # 30% seasonal variation
        return BehavioralPattern(
            name="Seasonal Activity Pattern",
            description=(
                f"Your activity varies by season. "
                f"Most active in {max_season}, least active in {min_season}. "
                f"Variation of {variation*100:.0f}% between seasons."
            ),
            evidence=(
                f"{max_season}: {max_val:.0f} avg, {min_season}: {min_val:.0f} avg"
            ),
            pattern_type='cyclical',
            health_implication='neutral',
            recommendation=(
                f"Plan ahead for {min_season} by scheduling indoor activities "
                f"or finding weather-appropriate exercise options to maintain consistency."
            ),
        )

    return None


def detect_all_behavioral_patterns(
    signals_by_biomarker: dict[str, pd.Series],
    min_samples: int = 30
) -> list[BehavioralPattern]:
    """Detect all behavioral patterns from the data.

    Args:
        signals_by_biomarker: Dict mapping biomarker slug to daily series
        min_samples: Minimum samples required

    Returns:
        List of detected BehavioralPattern objects
    """
    patterns = []

    # Check for compensatory exercise
    if 'body_mass' in signals_by_biomarker:
        for activity_biomarker in ['steps', 'active_energy', 'exercise_time']:
            if activity_biomarker in signals_by_biomarker:
                pattern = detect_compensatory_exercise(
                    signals_by_biomarker['body_mass'],
                    signals_by_biomarker[activity_biomarker],
                    min_samples,
                )
                if pattern:
                    patterns.append(pattern)
                    break  # Only report once

    # Check for weekend warrior
    for activity_biomarker in ['steps', 'active_energy']:
        if activity_biomarker in signals_by_biomarker:
            pattern = detect_weekend_warrior(
                signals_by_biomarker[activity_biomarker],
            )
            if pattern:
                patterns.append(pattern)
                break

    # Check for seasonal pattern
    for activity_biomarker in ['steps', 'active_energy']:
        if activity_biomarker in signals_by_biomarker:
            pattern = detect_seasonal_activity_pattern(
                signals_by_biomarker[activity_biomarker],
            )
            if pattern:
                patterns.append(pattern)
                break

    return patterns


# =============================================================================
# CROSS-DOMAIN INTERCONNECTIONS
# =============================================================================

# Domain definitions
DOMAIN_BIOMARKERS = {
    'cardiovascular': ['heart_rate', 'heart_rate_resting', 'hrv_sdnn', 'hrv_rmssd', 'vo2_max', 'spo2'],
    'sleep': ['sleep_duration', 'sleep_rem', 'sleep_deep', 'sleep_core', 'sleep_efficiency'],
    'activity': ['steps', 'active_energy', 'exercise_time', 'stand_time'],
    'body_composition': ['body_mass', 'body_fat_percentage', 'lean_body_mass', 'body_mass_index'],
    'circadian': ['time_in_daylight'],
    'respiratory': ['respiratory_rate'],
    'mobility': ['walking_speed', 'walking_steadiness', 'walking_asymmetry'],
}


def get_domain_for_biomarker(biomarker: str) -> Optional[str]:
    """Get the domain a biomarker belongs to."""
    for domain, biomarkers in DOMAIN_BIOMARKERS.items():
        if biomarker in biomarkers:
            return domain
    return None


def find_cross_domain_interconnections(
    signals_by_biomarker: dict[str, pd.Series],
    max_lag: int = 3,
    min_samples: int = 30,
    min_correlation: float = 0.2
) -> list[Interconnection]:
    """Find significant relationships between different domains.

    Args:
        signals_by_biomarker: Dict mapping biomarker slug to daily series
        max_lag: Maximum lag days to test
        min_samples: Minimum samples required
        min_correlation: Minimum absolute correlation to report

    Returns:
        List of Interconnection objects
    """
    interconnections = []

    # Define key cross-domain relationships to test
    relationships_to_test = [
        # Sleep -> Cardiovascular
        ('sleep_duration', 'hrv_sdnn', 'sleep', 'cardiovascular'),
        ('sleep_duration', 'heart_rate_resting', 'sleep', 'cardiovascular'),
        ('sleep_deep', 'hrv_sdnn', 'sleep', 'cardiovascular'),
        ('sleep_efficiency', 'hrv_sdnn', 'sleep', 'cardiovascular'),

        # Activity -> Cardiovascular
        ('steps', 'heart_rate_resting', 'activity', 'cardiovascular'),
        ('steps', 'hrv_sdnn', 'activity', 'cardiovascular'),
        ('exercise_time', 'vo2_max', 'activity', 'cardiovascular'),

        # Daylight -> Sleep
        ('time_in_daylight', 'sleep_duration', 'circadian', 'sleep'),
        ('time_in_daylight', 'sleep_efficiency', 'circadian', 'sleep'),

        # Activity -> Body Composition
        ('steps', 'body_mass', 'activity', 'body_composition'),
        ('active_energy', 'body_mass', 'activity', 'body_composition'),

        # Body Composition -> Cardiovascular
        ('body_mass', 'vo2_max', 'body_composition', 'cardiovascular'),
        ('body_mass', 'heart_rate_resting', 'body_composition', 'cardiovascular'),
        ('body_fat_percentage', 'vo2_max', 'body_composition', 'cardiovascular'),

        # Sleep -> Body Composition
        ('sleep_duration', 'body_mass', 'sleep', 'body_composition'),

        # SpO2 relationships (high reliability: CV=2.2%)
        # Sleep quality -> SpO2 (poor sleep may affect blood oxygen)
        ('sleep_duration', 'spo2', 'sleep', 'cardiovascular'),
        ('sleep_efficiency', 'spo2', 'sleep', 'cardiovascular'),
        # SpO2 -> Recovery (blood oxygen affects recovery capacity)
        ('spo2', 'hrv_sdnn', 'cardiovascular', 'cardiovascular'),
        # Body composition -> SpO2 (higher weight may affect breathing)
        ('body_mass', 'spo2', 'body_composition', 'cardiovascular'),

        # Mobility relationships (confound-controlled, 97% real signal)
        # Activity -> Mobility (higher activity = better gait metrics)
        ('steps', 'walking_speed', 'activity', 'mobility'),
        ('exercise_time', 'walking_speed', 'activity', 'mobility'),
        # Mobility -> Cardiovascular (gait reflects fitness)
        ('walking_speed', 'vo2_max', 'mobility', 'cardiovascular'),
        ('walking_speed', 'heart_rate_resting', 'mobility', 'cardiovascular'),
        # Body composition -> Mobility (weight affects gait)
        ('body_mass', 'walking_speed', 'body_composition', 'mobility'),
        ('body_fat_percentage', 'walking_speed', 'body_composition', 'mobility'),
        # Sleep -> Mobility (fatigue affects gait)
        ('sleep_duration', 'walking_speed', 'sleep', 'mobility'),
    ]

    for source_bio, target_bio, source_domain, target_domain in relationships_to_test:
        if source_bio not in signals_by_biomarker or target_bio not in signals_by_biomarker:
            continue

        source_data = signals_by_biomarker[source_bio]
        target_data = signals_by_biomarker[target_bio]

        # Test multiple lags
        best_r = 0
        best_lag = 0
        best_p = 1.0
        best_n = 0

        for lag in range(0, max_lag + 1):
            r, p, n = compute_lagged_correlation(source_data, target_data, lag, min_samples)

            if not np.isnan(r) and abs(r) > abs(best_r):
                best_r = r
                best_lag = lag
                best_p = p
                best_n = n

        # Only report if correlation is meaningful
        if abs(best_r) >= min_correlation and best_p < 0.05:
            # Determine relationship type
            if best_r > 0:
                relationship = 'positive'
            else:
                relationship = 'negative'

            # Determine strength
            if abs(best_r) >= 0.5:
                strength = 'strong'
            elif abs(best_r) >= 0.3:
                strength = 'moderate'
            else:
                strength = 'weak'

            # Build pathway description
            if best_lag == 0:
                lag_desc = "same day"
            elif best_lag == 1:
                lag_desc = "next day"
            else:
                lag_desc = f"{best_lag} days later"

            if relationship == 'positive':
                direction = "higher"
            else:
                direction = "lower"

            pathway = f"Higher {source_bio.replace('_', ' ')} -> {direction} {target_bio.replace('_', ' ')} ({lag_desc})"

            interpretation = (
                f"When {source_bio.replace('_', ' ')} is higher, "
                f"{target_bio.replace('_', ' ')} tends to be {direction} "
                f"{'on the same day' if best_lag == 0 else f'{best_lag} day(s) later'}. "
                f"This {'moderate' if strength == 'moderate' else strength} relationship "
                f"(r={best_r:.2f}) suggests {source_domain} influences {target_domain}."
            )

            interconnections.append(Interconnection(
                source_domain=source_domain,
                target_domain=target_domain,
                source_biomarker=source_bio,
                target_biomarker=target_bio,
                relationship=relationship,
                strength=strength,
                pathway=pathway,
                correlation=best_r,
                p_value=best_p,
                lag_days=best_lag,
                sample_size=best_n,
                interpretation=interpretation,
            ))

    # Sort by absolute correlation strength
    interconnections.sort(key=lambda x: abs(x.correlation), reverse=True)

    return interconnections


# =============================================================================
# WELLNESS SCORE COMPUTATION
# =============================================================================

def compute_cardiovascular_score(
    signals_by_biomarker: dict[str, pd.Series],
    vo2max_report: Optional['VO2MaxReport'] = None,
) -> DomainScore:
    """Compute cardiovascular wellness domain score.

    Components:
    - VO2 Max percentile (if available)
    - HRV relative to personal baseline
    - RHR relative to personal baseline (lower is better)
    """
    contributors = []
    limiting_factors = []
    data_points = 0
    scores = []
    weights = []

    # VO2 Max component (heavily weighted if available)
    if vo2max_report is not None and vo2max_report.percentile is not None:
        percentile = vo2max_report.percentile.percentile
        # Convert percentile to 0-100 score (already is, essentially)
        vo2_score = percentile
        scores.append(vo2_score)
        weights.append(3.0)  # Triple weight for VO2 Max
        data_points += vo2max_report.percentile.n_measurements

        if percentile >= 70:
            contributors.append(f"Excellent VO2 Max ({percentile:.0f}th percentile)")
        elif percentile <= 30:
            limiting_factors.append(f"Low VO2 Max ({percentile:.0f}th percentile)")

    # HRV component
    if 'hrv_sdnn' in signals_by_biomarker:
        hrv_data = signals_by_biomarker['hrv_sdnn'].dropna()
        if len(hrv_data) >= 14:
            recent_hrv = hrv_data.tail(14).mean()
            baseline_hrv = hrv_data.mean()
            data_points += len(hrv_data)

            # Score based on recent vs baseline (100 = at baseline, higher = better)
            if baseline_hrv > 0:
                hrv_ratio = recent_hrv / baseline_hrv
                hrv_score = min(100, max(0, hrv_ratio * 70 + 15))
                scores.append(hrv_score)
                weights.append(2.0)

                if hrv_ratio >= 1.1:
                    contributors.append("HRV above personal baseline")
                elif hrv_ratio < 0.85:
                    limiting_factors.append("HRV below personal baseline")

    # RHR component (lower is better)
    if 'heart_rate_resting' in signals_by_biomarker:
        rhr_data = signals_by_biomarker['heart_rate_resting'].dropna()
        if len(rhr_data) >= 14:
            recent_rhr = rhr_data.tail(14).mean()
            baseline_rhr = rhr_data.mean()
            data_points += len(rhr_data)

            # Score inversely (lower RHR = higher score)
            # Typical healthy range: 50-80 bpm
            if recent_rhr <= 50:
                rhr_score = 95
            elif recent_rhr >= 85:
                rhr_score = 40
            else:
                rhr_score = 95 - ((recent_rhr - 50) / 35) * 55

            scores.append(rhr_score)
            weights.append(1.5)

            if recent_rhr < baseline_rhr * 0.95:
                contributors.append("RHR trending down (improved)")
            elif recent_rhr > baseline_rhr * 1.1:
                limiting_factors.append("RHR elevated above baseline")

    # SpO2 component (blood oxygen saturation)
    # High reliability: CV=2.2%, temporal stability=98.9%
    if 'spo2' in signals_by_biomarker:
        spo2_data = signals_by_biomarker['spo2'].dropna()
        if len(spo2_data) >= 14:
            recent_spo2 = spo2_data.tail(14).mean()
            overall_spo2 = spo2_data.mean()
            data_points += len(spo2_data)

            # Score based on SpO2 levels
            # Normal: 95-100%, Mild hypoxemia: 91-94%, Concerning: <91%
            if recent_spo2 >= 97:
                spo2_score = 95
            elif recent_spo2 >= 95:
                spo2_score = 85
            elif recent_spo2 >= 93:
                spo2_score = 70
            elif recent_spo2 >= 91:
                spo2_score = 55
            else:
                spo2_score = 40

            scores.append(spo2_score)
            weights.append(1.5)  # Same weight as RHR

            # Calculate percentage below 95%
            pct_below_95 = (spo2_data < 95).sum() / len(spo2_data) * 100

            if recent_spo2 >= 97 and pct_below_95 < 5:
                contributors.append(f"Excellent blood oxygen ({recent_spo2:.1f}%)")
            elif pct_below_95 > 20:
                limiting_factors.append(f"Frequent low SpO2 readings ({pct_below_95:.0f}% below 95%)")
            elif recent_spo2 < 95:
                limiting_factors.append(f"Blood oxygen below optimal ({recent_spo2:.1f}%)")

    # Compute weighted average
    if scores:
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
    else:
        weighted_score = 50.0  # Default neutral score

    # Determine confidence
    if data_points >= 100:
        confidence = 'high'
    elif data_points >= 30:
        confidence = 'moderate'
    else:
        confidence = 'low'

    # Determine trend (simple: compare recent to earlier)
    trend = 'stable'
    if 'hrv_sdnn' in signals_by_biomarker:
        hrv_data = signals_by_biomarker['hrv_sdnn'].dropna()
        if len(hrv_data) >= 60:
            early = hrv_data.head(30).mean()
            late = hrv_data.tail(30).mean()
            if late > early * 1.1:
                trend = 'improving'
            elif late < early * 0.9:
                trend = 'declining'

    return DomainScore(
        score=weighted_score,
        confidence=confidence,
        trend=trend,
        key_contributors=contributors,
        limiting_factors=limiting_factors,
        data_points=data_points,
    )


def compute_sleep_score(
    signals_by_biomarker: dict[str, pd.Series],
    sleep_report: Optional['SleepArchitectureReport'] = None,
) -> DomainScore:
    """Compute sleep wellness domain score.

    Components:
    - Sleep duration relative to personal baseline
    - Sleep efficiency
    - Sleep architecture (REM%, Deep%)
    - Consistency of sleep schedule
    """
    contributors = []
    limiting_factors = []
    data_points = 0
    scores = []
    weights = []

    # Try to get or compute sleep duration
    duration_data = None
    if 'sleep_duration' in signals_by_biomarker:
        duration_data = signals_by_biomarker['sleep_duration'].dropna()
    else:
        # Compute from components if available
        sleep_components = ['sleep_rem', 'sleep_deep', 'sleep_core']
        available_components = [
            signals_by_biomarker[c].dropna()
            for c in sleep_components
            if c in signals_by_biomarker
        ]
        if available_components:
            # Align on common dates and sum
            from functools import reduce
            def align_and_sum(a: pd.Series, b: pd.Series) -> pd.Series:
                common = a.index.intersection(b.index)
                if len(common) > 0:
                    return a.loc[common] + b.loc[common]
                return pd.Series(dtype=float)
            duration_data = reduce(align_and_sum, available_components)

    # Sleep duration scoring
    if duration_data is not None and len(duration_data) >= 7:
        avg_duration = duration_data.mean()
        data_points += len(duration_data)

        # Optimal: 7-9 hours (420-540 min)
        if 420 <= avg_duration <= 540:
            duration_score = 90
            contributors.append(f"Healthy sleep duration ({avg_duration/60:.1f} hrs)")
        elif avg_duration < 360:  # < 6 hours
            duration_score = 50
            limiting_factors.append(f"Insufficient sleep ({avg_duration/60:.1f} hrs)")
        elif avg_duration > 600:  # > 10 hours
            duration_score = 60
            limiting_factors.append(f"Excessive sleep duration ({avg_duration/60:.1f} hrs)")
        else:
            duration_score = 75

        scores.append(duration_score)
        weights.append(2.0)

    # Sleep efficiency (if we can calculate it)
    if 'sleep_efficiency' in signals_by_biomarker:
        efficiency_data = signals_by_biomarker['sleep_efficiency'].dropna()
        if len(efficiency_data) >= 7:
            avg_efficiency = efficiency_data.mean()
            data_points += len(efficiency_data)

            # Good efficiency: > 85%
            if avg_efficiency >= 90:
                efficiency_score = 95
                contributors.append(f"Excellent sleep efficiency ({avg_efficiency:.0f}%)")
            elif avg_efficiency >= 85:
                efficiency_score = 85
            elif avg_efficiency >= 75:
                efficiency_score = 70
                limiting_factors.append(f"Moderate sleep efficiency ({avg_efficiency:.0f}%)")
            else:
                efficiency_score = 50
                limiting_factors.append(f"Poor sleep efficiency ({avg_efficiency:.0f}%)")

            scores.append(efficiency_score)
            weights.append(1.5)

    # Deep sleep percentage (use computed duration_data)
    if 'sleep_deep' in signals_by_biomarker and duration_data is not None and len(duration_data) >= 7:
        deep_data = signals_by_biomarker['sleep_deep'].dropna()

        common_idx = deep_data.index.intersection(duration_data.index)
        if len(common_idx) >= 7:
            deep_pct = (deep_data.loc[common_idx] / duration_data.loc[common_idx] * 100).mean()
            data_points += len(common_idx)

            # Normal deep sleep: 13-23%
            if 15 <= deep_pct <= 25:
                deep_score = 90
                contributors.append(f"Healthy deep sleep ({deep_pct:.0f}%)")
            elif deep_pct < 10:
                deep_score = 50
                limiting_factors.append(f"Low deep sleep ({deep_pct:.0f}%)")
            else:
                deep_score = 75

            scores.append(deep_score)
            weights.append(1.0)

    # Compute weighted average
    if scores:
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
    else:
        weighted_score = 50.0

    # Determine confidence
    if data_points >= 60:
        confidence = 'high'
    elif data_points >= 14:
        confidence = 'moderate'
    else:
        confidence = 'low'

    # Determine trend (use computed duration_data)
    trend = 'stable'
    if duration_data is not None and len(duration_data) >= 28:
        early = duration_data.head(14).mean()
        late = duration_data.tail(14).mean()
        if late > early * 1.05:
            trend = 'improving'
        elif late < early * 0.95:
            trend = 'declining'

    return DomainScore(
        score=weighted_score,
        confidence=confidence,
        trend=trend,
        key_contributors=contributors,
        limiting_factors=limiting_factors,
        data_points=data_points,
    )


def compute_activity_score(
    signals_by_biomarker: dict[str, pd.Series],
) -> DomainScore:
    """Compute activity wellness domain score.

    Components:
    - Daily step count
    - Activity consistency (low variability is good)
    - Exercise time
    """
    contributors = []
    limiting_factors = []
    data_points = 0
    scores = []
    weights = []

    # Steps
    if 'steps' in signals_by_biomarker:
        steps_data = signals_by_biomarker['steps'].dropna()
        if len(steps_data) >= 7:
            avg_steps = steps_data.mean()
            data_points += len(steps_data)

            # Scoring: 10k+ excellent, 7k good, <5k poor
            if avg_steps >= 12000:
                steps_score = 95
                contributors.append(f"Excellent activity level ({avg_steps:.0f} steps/day)")
            elif avg_steps >= 10000:
                steps_score = 90
                contributors.append(f"Good activity level ({avg_steps:.0f} steps/day)")
            elif avg_steps >= 7500:
                steps_score = 80
            elif avg_steps >= 5000:
                steps_score = 65
            else:
                steps_score = 45
                limiting_factors.append(f"Low activity ({avg_steps:.0f} steps/day)")

            scores.append(steps_score)
            weights.append(2.0)

            # Consistency (coefficient of variation)
            if len(steps_data) >= 14:
                cv = steps_data.std() / steps_data.mean() if steps_data.mean() > 0 else 1.0
                if cv < 0.3:
                    consistency_score = 90
                    contributors.append("Consistent activity pattern")
                elif cv < 0.5:
                    consistency_score = 75
                else:
                    consistency_score = 55
                    limiting_factors.append("Inconsistent activity pattern")

                scores.append(consistency_score)
                weights.append(1.0)

    # Exercise time
    if 'exercise_time' in signals_by_biomarker:
        exercise_data = signals_by_biomarker['exercise_time'].dropna()
        if len(exercise_data) >= 7:
            avg_exercise = exercise_data.mean()
            data_points += len(exercise_data)

            # WHO recommends 150+ min/week = ~21 min/day
            if avg_exercise >= 30:
                exercise_score = 95
                contributors.append(f"Excellent exercise time ({avg_exercise:.0f} min/day)")
            elif avg_exercise >= 20:
                exercise_score = 85
            elif avg_exercise >= 10:
                exercise_score = 65
            else:
                exercise_score = 45
                limiting_factors.append(f"Limited structured exercise ({avg_exercise:.0f} min/day)")

            scores.append(exercise_score)
            weights.append(1.5)

    # Compute weighted average
    if scores:
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
    else:
        weighted_score = 50.0

    # Determine confidence
    if data_points >= 60:
        confidence = 'high'
    elif data_points >= 14:
        confidence = 'moderate'
    else:
        confidence = 'low'

    # Determine trend
    trend = 'stable'
    if 'steps' in signals_by_biomarker:
        steps_data = signals_by_biomarker['steps'].dropna()
        if len(steps_data) >= 28:
            early = steps_data.head(14).mean()
            late = steps_data.tail(14).mean()
            if late > early * 1.15:
                trend = 'improving'
            elif late < early * 0.85:
                trend = 'declining'

    return DomainScore(
        score=weighted_score,
        confidence=confidence,
        trend=trend,
        key_contributors=contributors,
        limiting_factors=limiting_factors,
        data_points=data_points,
    )


def compute_recovery_score(
    signals_by_biomarker: dict[str, pd.Series],
    derived_report: Optional['DerivedMetricsReport'] = None,
) -> DomainScore:
    """Compute recovery wellness domain score.

    Components:
    - HRV trend
    - Training load ratio (if available)
    - Stress index (if available)
    """
    contributors = []
    limiting_factors = []
    data_points = 0
    scores = []
    weights = []

    # HRV recovery trend
    if 'hrv_sdnn' in signals_by_biomarker:
        hrv_data = signals_by_biomarker['hrv_sdnn'].dropna()
        if len(hrv_data) >= 14:
            recent_hrv = hrv_data.tail(7).mean()
            baseline_hrv = hrv_data.mean()
            data_points += len(hrv_data)

            if baseline_hrv > 0:
                recovery_ratio = recent_hrv / baseline_hrv
                if recovery_ratio >= 1.0:
                    recovery_score = 85 + min(15, (recovery_ratio - 1) * 100)
                    contributors.append("HRV indicates good recovery")
                elif recovery_ratio >= 0.9:
                    recovery_score = 70
                else:
                    recovery_score = 50
                    limiting_factors.append("HRV suggests recovery deficit")

                scores.append(recovery_score)
                weights.append(2.0)

    # Use derived metrics if available
    if derived_report is not None:
        if derived_report.training_load is not None:
            acwr = derived_report.training_load.acute_chronic_ratio
            data_points += 30  # Approximate

            # Optimal ACWR: 0.8-1.3
            if 0.8 <= acwr <= 1.3:
                acwr_score = 90
                contributors.append(f"Optimal training load ratio ({acwr:.2f})")
            elif 0.6 <= acwr <= 1.5:
                acwr_score = 70
            else:
                acwr_score = 50
                if acwr < 0.6:
                    limiting_factors.append("Training load too low for adaptation")
                else:
                    limiting_factors.append("Training load too high, injury risk")

            scores.append(acwr_score)
            weights.append(1.5)

        if derived_report.stress_index is not None:
            stress = derived_report.stress_index.classification
            if stress == 'low':
                stress_score = 90
                contributors.append("Low stress index")
            elif stress == 'moderate':
                stress_score = 75
            elif stress == 'elevated':
                stress_score = 55
                limiting_factors.append("Elevated stress index")
            else:
                stress_score = 40
                limiting_factors.append("High stress index")

            scores.append(stress_score)
            weights.append(1.0)

    # Compute weighted average
    if scores:
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
    else:
        weighted_score = 50.0

    # Determine confidence
    if data_points >= 60:
        confidence = 'high'
    elif data_points >= 14:
        confidence = 'moderate'
    else:
        confidence = 'low'

    return DomainScore(
        score=weighted_score,
        confidence=confidence,
        trend='stable',  # Would need more context for trend
        key_contributors=contributors,
        limiting_factors=limiting_factors,
        data_points=data_points,
    )


def compute_body_composition_score(
    signals_by_biomarker: dict[str, pd.Series],
    body_composition_report: Optional['BodyCompositionReport'] = None,
) -> DomainScore:
    """Compute body composition wellness domain score.

    Components:
    - BMI category
    - Body fat percentile (if available)
    - Weight trend (stable or improving)
    """
    contributors = []
    limiting_factors = []
    data_points = 0
    scores = []
    weights = []

    if body_composition_report is not None:
        # BMI
        if body_composition_report.bmi is not None:
            bmi = body_composition_report.bmi
            data_points += 1

            if bmi.category == 'Normal':
                bmi_score = 90
                contributors.append(f"Healthy BMI ({bmi.value:.1f})")
            elif bmi.category == 'Overweight':
                bmi_score = 65
                limiting_factors.append(f"Overweight BMI ({bmi.value:.1f})")
            elif bmi.category in ('Obese Class I', 'Obese Class II', 'Obese Class III'):
                bmi_score = 40
                limiting_factors.append(f"Elevated BMI ({bmi.value:.1f})")
            elif bmi.category == 'Underweight':
                bmi_score = 55
                limiting_factors.append(f"Underweight BMI ({bmi.value:.1f})")
            else:
                bmi_score = 70

            scores.append(bmi_score)
            weights.append(1.5)

        # Body fat percentile
        if body_composition_report.body_fat_percentile is not None:
            bf = body_composition_report.body_fat_percentile
            data_points += bf.n_measurements

            # Score based on category
            if bf.category in ('Essential Fat', 'Athletes'):
                bf_score = 95
                contributors.append(f"Excellent body fat ({bf.value:.1f}%)")
            elif bf.category == 'Fitness':
                bf_score = 85
                contributors.append(f"Good body fat ({bf.value:.1f}%)")
            elif bf.category == 'Average':
                bf_score = 70
            elif bf.category == 'Above Average':
                bf_score = 55
                limiting_factors.append(f"Elevated body fat ({bf.value:.1f}%)")
            else:
                bf_score = 40
                limiting_factors.append(f"High body fat ({bf.value:.1f}%)")

            scores.append(bf_score)
            weights.append(2.0)

        # Weight trend
        if body_composition_report.trend is not None:
            trend = body_composition_report.trend
            data_points += trend.n_measurements

            # Favorable trend depends on starting point
            # For simplicity: stable or slight loss is good for most people
            weekly_change = trend.slope_kg_per_week
            if -0.5 <= weekly_change <= 0.1:
                trend_score = 85
                if weekly_change < -0.1:
                    contributors.append("Healthy weight loss trend")
            elif weekly_change > 0.5:
                trend_score = 50
                limiting_factors.append("Rapid weight gain")
            else:
                trend_score = 70

            scores.append(trend_score)
            weights.append(1.0)

    # Fallback to raw weight data if no report
    elif 'body_mass' in signals_by_biomarker:
        weight_data = signals_by_biomarker['body_mass'].dropna()
        if len(weight_data) >= 5:
            data_points += len(weight_data)
            # Just check stability
            cv = weight_data.std() / weight_data.mean() if weight_data.mean() > 0 else 0
            if cv < 0.03:
                scores.append(80)
                weights.append(1.0)
                contributors.append("Stable weight")
            else:
                scores.append(65)
                weights.append(1.0)

    # Compute weighted average
    if scores:
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
    else:
        weighted_score = 50.0

    # Determine confidence
    if data_points >= 20:
        confidence = 'high'
    elif data_points >= 5:
        confidence = 'moderate'
    else:
        confidence = 'low'

    # Determine trend
    trend = 'stable'
    if body_composition_report is not None and body_composition_report.trend is not None:
        weekly = body_composition_report.trend.slope_kg_per_week
        if weekly < -0.2:
            trend = 'improving'  # Losing weight (for most)
        elif weekly > 0.3:
            trend = 'declining'  # Gaining weight (for most)

    return DomainScore(
        score=weighted_score,
        confidence=confidence,
        trend=trend,
        key_contributors=contributors,
        limiting_factors=limiting_factors,
        data_points=data_points,
    )


def compute_mobility_score(
    signals_by_biomarker: dict[str, pd.Series],
    mobility_analysis: Optional['MobilityAnalysis'] = None,
) -> Optional[DomainScore]:
    """Compute mobility wellness domain score.

    Based on confound-controlled analysis:
    - Walking speed: Primary metric (clinical "sixth vital sign")
    - Walking steadiness: Secondary metric (FDA-validated fall risk)
    - Walking asymmetry: Alert only (excluded from scoring due to CV=305%)

    Step length and double support excluded due to r>0.87 redundancy with speed.

    Returns None if insufficient mobility data available.
    """
    contributors = []
    limiting_factors = []
    data_points = 0
    scores = []
    weights = []

    # If we have a pre-computed MobilityAnalysis, use it
    if mobility_analysis is not None:
        data_points = mobility_analysis.walking_speed_n

        # Walking speed score (70% weight)
        ws_status = mobility_analysis.walking_speed_status
        ws_mean = mobility_analysis.walking_speed_mean

        if ws_status == 'excellent':
            ws_score = 95
            contributors.append(f"Excellent walking speed ({ws_mean:.2f} m/s)")
        elif ws_status == 'normal':
            ws_score = 80
            contributors.append(f"Normal walking speed ({ws_mean:.2f} m/s)")
        elif ws_status == 'reduced':
            ws_score = 55
            limiting_factors.append(f"Reduced walking speed ({ws_mean:.2f} m/s)")
        else:  # impaired
            ws_score = 30
            limiting_factors.append(f"Impaired walking speed ({ws_mean:.2f} m/s)")

        scores.append(ws_score)
        weights.append(0.7)

        # Trend adjustment
        if mobility_analysis.walking_speed_trend_significant:
            if mobility_analysis.walking_speed_annual_change < -0.05:
                limiting_factors.append(
                    f"Declining mobility ({mobility_analysis.walking_speed_annual_change:.3f} m/s/year)"
                )
            elif mobility_analysis.walking_speed_annual_change > 0.02:
                contributors.append("Improving mobility trend")

        # Walking steadiness score (30% weight)
        if mobility_analysis.steadiness_mean is not None:
            data_points += mobility_analysis.steadiness_n or 0
            st_status = mobility_analysis.steadiness_status

            if st_status == 'ok':
                st_score = 90
                contributors.append(f"Low fall risk (steadiness {mobility_analysis.steadiness_mean:.1f}%)")
            elif st_status == 'low':
                st_score = 55
                limiting_factors.append(f"Moderate fall risk (steadiness {mobility_analysis.steadiness_mean:.1f}%)")
            else:  # very_low
                st_score = 25
                limiting_factors.append(f"Elevated fall risk (steadiness {mobility_analysis.steadiness_mean:.1f}%)")

            scores.append(st_score)
            weights.append(0.3)

        # Asymmetry alert (not scored, just flagged)
        if mobility_analysis.asymmetry_alert:
            limiting_factors.append(
                f"Sustained walking asymmetry ({mobility_analysis.asymmetry_mean:.1f}%)"
            )

        # Use pre-computed composite score
        weighted_score = mobility_analysis.mobility_score
        trend = mobility_analysis.mobility_trend

    # Fall back to raw signals if no analysis provided
    elif 'walking_speed' in signals_by_biomarker:
        ws_data = signals_by_biomarker['walking_speed'].dropna()
        if len(ws_data) >= 30:
            data_points = len(ws_data)
            ws_mean = ws_data.mean()

            # Score based on clinical thresholds
            if ws_mean >= 1.2:
                ws_score = 90
                contributors.append(f"Excellent walking speed ({ws_mean:.2f} m/s)")
            elif ws_mean >= 1.0:
                ws_score = 75
                contributors.append(f"Normal walking speed ({ws_mean:.2f} m/s)")
            elif ws_mean >= 0.8:
                ws_score = 55
                limiting_factors.append(f"Reduced walking speed ({ws_mean:.2f} m/s)")
            else:
                ws_score = 35
                limiting_factors.append(f"Impaired walking speed ({ws_mean:.2f} m/s)")

            scores.append(ws_score)
            weights.append(1.0)

            # Compute weighted average
            total_weight = sum(weights)
            weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
            trend = 'stable'  # Can't determine without full analysis
        else:
            return None  # Insufficient data
    else:
        return None  # No mobility data

    # Determine confidence
    if data_points >= 100:
        confidence = 'high'
    elif data_points >= 30:
        confidence = 'moderate'
    else:
        confidence = 'low'

    return DomainScore(
        score=weighted_score,
        confidence=confidence,
        trend=trend,
        key_contributors=contributors,
        limiting_factors=limiting_factors,
        data_points=data_points,
    )


def compute_wellness_score(
    signals_by_biomarker: dict[str, pd.Series],
    vo2max_report: Optional['VO2MaxReport'] = None,
    sleep_report: Optional['SleepArchitectureReport'] = None,
    derived_report: Optional['DerivedMetricsReport'] = None,
    body_composition_report: Optional['BodyCompositionReport'] = None,
    mobility_analysis: Optional['MobilityAnalysis'] = None,
) -> WellnessScore:
    """Compute comprehensive multi-domain wellness score using Harmonic Mean.

    The harmonic mean naturally penalizes imbalance:
    - Weak domains pull the score down more than strong domains pull it up
    - Incentivizes fixing weaknesses over boosting strengths
    - Based on V-Clock research showing vector approaches are 1.78x more predictive

    Formula: H = sum(weights) / sum(weight_i / score_i)

    Args:
        signals_by_biomarker: Dict mapping biomarker slug to daily series
        vo2max_report: Optional VO2 Max analysis report
        sleep_report: Optional sleep architecture report
        derived_report: Optional derived metrics report
        body_composition_report: Optional body composition report
        mobility_analysis: Optional mobility analysis (confound-controlled)

    Returns:
        WellnessScore with domain breakdown and explainability metrics
    """
    # Compute each domain
    cardiovascular = compute_cardiovascular_score(signals_by_biomarker, vo2max_report)
    sleep = compute_sleep_score(signals_by_biomarker, sleep_report)
    activity = compute_activity_score(signals_by_biomarker)
    recovery = compute_recovery_score(signals_by_biomarker, derived_report)
    body_composition = compute_body_composition_score(signals_by_biomarker, body_composition_report)
    mobility = compute_mobility_score(signals_by_biomarker, mobility_analysis)

    # Domain importance weights (based on clinical significance)
    domain_info = [
        ('cardiovascular', cardiovascular.score, cardiovascular.data_points, 1.2),
        ('sleep', sleep.score, sleep.data_points, 1.0),
        ('activity', activity.score, activity.data_points, 1.0),
        ('recovery', recovery.score, recovery.data_points, 0.8),
        ('body_composition', body_composition.score, body_composition.data_points, 0.8),
    ]

    # Add mobility if available (clinical "sixth vital sign" importance)
    if mobility is not None:
        domain_info.append(('mobility', mobility.score, mobility.data_points, 1.0))

    # Compute weights adjusted for data adequacy
    weights = []
    scores = []
    domain_names = []
    for name, score, data_pts, importance in domain_info:
        # More data = more confidence = more weight
        data_weight = min(1.0, data_pts / 50)
        weight = importance * (0.5 + 0.5 * data_weight)
        weights.append(weight)
        scores.append(max(score, 1.0))  # Floor at 1 to prevent division by zero
        domain_names.append(name)

    # =========================================================================
    # HARMONIC MEAN CALCULATION
    # H = sum(weights) / sum(weight_i / score_i)
    # =========================================================================
    total_weight = sum(weights)
    weighted_reciprocal_sum = sum(w / s for w, s in zip(weights, scores))
    harmonic_mean = total_weight / weighted_reciprocal_sum if weighted_reciprocal_sum > 0 else 50.0

    # =========================================================================
    # ARITHMETIC MEAN (for comparison / explainability)
    # =========================================================================
    arithmetic_mean = sum(w * s for w, s in zip(weights, scores)) / total_weight if total_weight > 0 else 50.0

    # =========================================================================
    # EXPLAINABILITY METRICS
    # =========================================================================

    # Imbalance penalty: how much the harmonic < arithmetic
    imbalance_penalty = arithmetic_mean - harmonic_mean

    # Bottleneck analysis: which domain is pulling the score down most?
    # The domain with lowest score has highest "pull down" effect in harmonic mean
    # We compute impact as: how much would overall improve if this domain matched the best?
    min_score_idx = scores.index(min(scores))
    bottleneck_domain = domain_names[min_score_idx]
    bottleneck_score = scores[min_score_idx]

    # Calculate impact: if we raised bottleneck to match max, what would happen?
    max_score = max(scores)
    if max_score > bottleneck_score:
        # Simulate raising bottleneck to max
        simulated_scores = scores.copy()
        simulated_scores[min_score_idx] = max_score
        simulated_reciprocal_sum = sum(w / s for w, s in zip(weights, simulated_scores))
        simulated_harmonic = total_weight / simulated_reciprocal_sum if simulated_reciprocal_sum > 0 else 50.0
        bottleneck_impact = simulated_harmonic - harmonic_mean
    else:
        bottleneck_impact = 0.0

    return WellnessScore(
        overall=harmonic_mean,
        cardiovascular=cardiovascular,
        sleep=sleep,
        activity=activity,
        recovery=recovery,
        body_composition=body_composition,
        mobility=mobility,
        arithmetic_mean=arithmetic_mean,
        imbalance_penalty=imbalance_penalty,
        bottleneck_domain=bottleneck_domain,
        bottleneck_impact=bottleneck_impact,
    )


# =============================================================================
# RISK FACTOR SYNTHESIS
# =============================================================================

def synthesize_risk_factors(
    wellness_score: WellnessScore,
    interconnections: list[Interconnection],
    signals_by_biomarker: dict[str, pd.Series],
    derived_report: Optional['DerivedMetricsReport'] = None,
) -> list[RiskFactor]:
    """Synthesize risk factors from multiple signals.

    Combines domain scores, interconnections, and derived metrics
    to identify health risks.

    Args:
        wellness_score: Computed wellness score
        interconnections: Cross-domain relationships
        signals_by_biomarker: Raw signals
        derived_report: Optional derived metrics

    Returns:
        List of identified RiskFactor objects
    """
    risk_factors = []

    # Cardiovascular risk
    cv_score = wellness_score.cardiovascular.score
    cv_limiting = wellness_score.cardiovascular.limiting_factors

    if cv_score < 50:
        risk_factors.append(RiskFactor(
            name="Cardiovascular Health Concern",
            level='elevated' if cv_score >= 40 else 'high',
            contributing_factors=cv_limiting,
            trend=wellness_score.cardiovascular.trend,
            modifiable=True,
            evidence=f"Cardiovascular domain score: {cv_score:.0f}/100",
            clinical_context="Low HRV and elevated RHR are associated with increased cardiovascular risk."
        ))
    elif cv_score < 65:
        risk_factors.append(RiskFactor(
            name="Cardiovascular Fitness Opportunity",
            level='moderate',
            contributing_factors=cv_limiting,
            trend=wellness_score.cardiovascular.trend,
            modifiable=True,
            evidence=f"Cardiovascular domain score: {cv_score:.0f}/100",
        ))

    # Sleep risk
    sleep_score = wellness_score.sleep.score
    sleep_limiting = wellness_score.sleep.limiting_factors

    if sleep_score < 50:
        risk_factors.append(RiskFactor(
            name="Sleep Quality Concern",
            level='elevated' if sleep_score >= 40 else 'high',
            contributing_factors=sleep_limiting,
            trend=wellness_score.sleep.trend,
            modifiable=True,
            evidence=f"Sleep domain score: {sleep_score:.0f}/100",
            clinical_context="Poor sleep is linked to metabolic, cardiovascular, and cognitive health issues."
        ))

    # Activity risk
    activity_score = wellness_score.activity.score
    activity_limiting = wellness_score.activity.limiting_factors

    if activity_score < 55:
        risk_factors.append(RiskFactor(
            name="Sedentary Lifestyle Risk",
            level='moderate' if activity_score >= 45 else 'elevated',
            contributing_factors=activity_limiting,
            trend=wellness_score.activity.trend,
            modifiable=True,
            evidence=f"Activity domain score: {activity_score:.0f}/100",
            clinical_context="Insufficient physical activity increases risk of chronic diseases."
        ))

    # Recovery/overtraining risk
    recovery_score = wellness_score.recovery.score
    recovery_limiting = wellness_score.recovery.limiting_factors

    if recovery_score < 55 and 'training' in str(recovery_limiting).lower():
        risk_factors.append(RiskFactor(
            name="Overtraining/Recovery Deficit",
            level='moderate' if recovery_score >= 45 else 'elevated',
            contributing_factors=recovery_limiting,
            trend='stable',
            modifiable=True,
            evidence=f"Recovery domain score: {recovery_score:.0f}/100",
            clinical_context="Inadequate recovery increases injury risk and reduces training adaptations."
        ))

    # Body composition risk
    bc_score = wellness_score.body_composition.score
    bc_limiting = wellness_score.body_composition.limiting_factors

    if bc_score < 55:
        risk_factors.append(RiskFactor(
            name="Body Composition Concern",
            level='moderate' if bc_score >= 45 else 'elevated',
            contributing_factors=bc_limiting,
            trend=wellness_score.body_composition.trend,
            modifiable=True,
            evidence=f"Body composition domain score: {bc_score:.0f}/100",
        ))

    # SpO2/Respiratory risk (nocturnal hypoxemia)
    # High reliability: CV=2.2%, temporal stability=98.9%
    if 'spo2' in signals_by_biomarker:
        spo2_data = signals_by_biomarker['spo2'].dropna()
        if len(spo2_data) >= 30:
            mean_spo2 = spo2_data.mean()
            pct_below_95 = (spo2_data < 95).sum() / len(spo2_data) * 100

            # Check for concerning patterns
            if pct_below_95 > 25 or mean_spo2 < 94:
                level = 'high' if pct_below_95 > 35 or mean_spo2 < 92 else 'elevated'
                risk_factors.append(RiskFactor(
                    name="Nocturnal Hypoxemia Risk",
                    level=level,
                    contributing_factors=[
                        f"{pct_below_95:.0f}% of SpO2 readings below 95%",
                        f"Mean SpO2: {mean_spo2:.1f}%",
                    ],
                    trend='stable',
                    modifiable=True,
                    evidence=f"Based on {len(spo2_data)} SpO2 measurements (CV=2.2%, highly reliable)",
                    clinical_context=(
                        "Frequent low blood oxygen readings, especially at night, may indicate "
                        "sleep-disordered breathing such as sleep apnea. This is associated with "
                        "increased cardiovascular risk, daytime fatigue, and cognitive impairment."
                    ),
                ))
            elif pct_below_95 > 15:
                risk_factors.append(RiskFactor(
                    name="Blood Oxygen Variability",
                    level='moderate',
                    contributing_factors=[
                        f"{pct_below_95:.0f}% of readings below 95%",
                    ],
                    trend='stable',
                    modifiable=True,
                    evidence=f"Mean SpO2: {mean_spo2:.1f}% (n={len(spo2_data)})",
                    clinical_context="Occasional low SpO2 readings warrant monitoring.",
                ))

    # Mobility risk (confound-controlled, 97% real signal)
    # Walking speed is the "sixth vital sign" in geriatric medicine
    if wellness_score.mobility is not None:
        mobility_score = wellness_score.mobility.score
        mobility_limiting = wellness_score.mobility.limiting_factors

        if mobility_score < 55:
            risk_factors.append(RiskFactor(
                name="Mobility Concern",
                level='elevated' if mobility_score >= 40 else 'high',
                contributing_factors=mobility_limiting,
                trend=wellness_score.mobility.trend,
                modifiable=True,
                evidence=f"Mobility domain score: {mobility_score:.0f}/100",
                clinical_context=(
                    "Walking speed is considered the 'sixth vital sign' in clinical medicine. "
                    "Reduced walking speed is associated with increased mortality risk, "
                    "cognitive decline, and reduced quality of life."
                ),
            ))
        elif mobility_score < 70:
            risk_factors.append(RiskFactor(
                name="Mobility Opportunity",
                level='moderate',
                contributing_factors=mobility_limiting,
                trend=wellness_score.mobility.trend,
                modifiable=True,
                evidence=f"Mobility domain score: {mobility_score:.0f}/100",
            ))

        # Check for declining trend (confound-controlled)
        if wellness_score.mobility.trend == 'declining':
            # Check if this is already captured in limiting factors
            declining_in_factors = any('declining' in f.lower() for f in mobility_limiting)
            if not declining_in_factors:
                risk_factors.append(RiskFactor(
                    name="Mobility Decline Trend",
                    level='moderate',
                    contributing_factors=["Walking speed declining over time (confound-controlled)"],
                    trend='worsening',
                    modifiable=True,
                    evidence="Trend analysis controlling for activity level and season",
                    clinical_context=(
                        "Declining mobility may indicate reduced muscle strength, "
                        "balance issues, or other underlying health changes. "
                        "Early intervention can help maintain independence."
                    ),
                ))

    # Fall risk from walking steadiness (Apple/FDA validated)
    if 'walking_steadiness' in signals_by_biomarker:
        steadiness_data = signals_by_biomarker['walking_steadiness'].dropna()
        if len(steadiness_data) >= 10:
            mean_steadiness = steadiness_data.mean()
            pct_below_90 = (steadiness_data < 90).sum() / len(steadiness_data) * 100

            if mean_steadiness < 80 or pct_below_90 > 30:
                risk_factors.append(RiskFactor(
                    name="Fall Risk Concern",
                    level='elevated' if mean_steadiness < 75 else 'moderate',
                    contributing_factors=[
                        f"Walking steadiness: {mean_steadiness:.1f}%",
                        f"{pct_below_90:.0f}% of readings below 90%",
                    ],
                    trend='stable',
                    modifiable=True,
                    evidence=f"Based on {len(steadiness_data)} steadiness measurements (CV=4%, FDA-validated)",
                    clinical_context=(
                        "Walking steadiness below 90% indicates increased fall risk. "
                        "Balance training and strength exercises can help reduce fall risk."
                    ),
                ))

    # Cross-domain risks from interconnections
    # Look for negative patterns
    for ic in interconnections:
        if ic.relationship == 'negative' and ic.strength == 'strong':
            # Strong negative interconnection might indicate a risk pathway
            if ic.source_domain == 'body_composition' and ic.target_domain == 'cardiovascular':
                if 'body_mass' in ic.pathway.lower() and 'vo2' in ic.pathway.lower():
                    # Weight negatively affecting fitness
                    if not any(rf.name == "Body Composition Concern" for rf in risk_factors):
                        risk_factors.append(RiskFactor(
                            name="Weight-Fitness Relationship",
                            level='moderate',
                            contributing_factors=["Higher weight associated with lower VO2 Max"],
                            trend='stable',
                            modifiable=True,
                            evidence=f"Correlation: r={ic.correlation:.2f}",
                            clinical_context="Weight management can improve cardiorespiratory fitness."
                        ))

    # Sort by severity
    severity_order = {'high': 0, 'elevated': 1, 'moderate': 2, 'low': 3}
    risk_factors.sort(key=lambda rf: severity_order.get(rf.level, 4))

    return risk_factors


def identify_protective_factors(
    wellness_score: WellnessScore,
    behavioral_patterns: list[BehavioralPattern],
) -> list[str]:
    """Identify protective factors from the analysis.

    Protective factors are things the user is doing well that
    support their health.

    Args:
        wellness_score: Computed wellness score
        behavioral_patterns: Detected behavioral patterns

    Returns:
        List of protective factor descriptions
    """
    protective = []

    # From domain scores
    if wellness_score.cardiovascular.score >= 75:
        for contributor in wellness_score.cardiovascular.key_contributors:
            protective.append(contributor)

    if wellness_score.sleep.score >= 75:
        for contributor in wellness_score.sleep.key_contributors:
            protective.append(contributor)

    if wellness_score.activity.score >= 75:
        for contributor in wellness_score.activity.key_contributors:
            protective.append(contributor)

    if wellness_score.body_composition.score >= 75:
        for contributor in wellness_score.body_composition.key_contributors:
            protective.append(contributor)

    if wellness_score.mobility is not None and wellness_score.mobility.score >= 75:
        for contributor in wellness_score.mobility.key_contributors:
            protective.append(contributor)

    # From behavioral patterns
    for pattern in behavioral_patterns:
        if pattern.health_implication == 'positive':
            protective.append(f"{pattern.name}: {pattern.description.split('.')[0]}")

    return protective


# =============================================================================
# RECOMMENDATION GENERATION
# =============================================================================

def generate_recommendations(
    wellness_score: WellnessScore,
    interconnections: list[Interconnection],
    risk_factors: list[RiskFactor],
    behavioral_patterns: list[BehavioralPattern],
) -> list[Recommendation]:
    """Generate prioritized, evidence-based recommendations.

    Recommendations are personalized based on the user's specific
    patterns, risk factors, and interconnections discovered in their data.

    Args:
        wellness_score: Computed wellness score
        interconnections: Cross-domain relationships
        risk_factors: Identified risk factors
        behavioral_patterns: Detected behavioral patterns

    Returns:
        List of prioritized Recommendation objects
    """
    recommendations = []

    # Recommendation templates based on domain weaknesses
    domain_recommendations = {
        'cardiovascular': {
            'low_vo2': Recommendation(
                priority='high',
                category='activity',
                action="Add 2-3 sessions of moderate-intensity cardio per week (brisk walking, cycling, swimming)",
                rationale="Your VO2 Max is below optimal. Consistent aerobic exercise is the most effective way to improve it.",
                expected_impact="Expect 5-10% VO2 Max improvement over 8-12 weeks with consistent training",
                timeline="4-8 weeks for initial improvements, 12+ weeks for significant gains",
                evidence_strength='strong',
                based_on=['VO2 Max percentile', 'Cardiovascular domain score'],
            ),
            'low_hrv': Recommendation(
                priority='medium',
                category='recovery',
                action="Prioritize recovery: ensure 7-8 hours sleep, consider stress management techniques",
                rationale="Your HRV is below your personal baseline, indicating recovery deficit or elevated stress.",
                expected_impact="HRV typically responds within 2-4 weeks of improved recovery practices",
                timeline="2-4 weeks for measurable improvement",
                evidence_strength='strong',
                based_on=['HRV baseline comparison', 'Recovery domain score'],
            ),
            'high_rhr': Recommendation(
                priority='medium',
                category='activity',
                action="Increase regular low-intensity movement throughout the day",
                rationale="Your resting heart rate is elevated. Regular activity trains the heart to be more efficient.",
                expected_impact="RHR can decrease 5-10 bpm with consistent aerobic training",
                timeline="4-8 weeks",
                evidence_strength='strong',
                based_on=['Resting heart rate trends'],
            ),
        },
        'sleep': {
            'low_duration': Recommendation(
                priority='high',
                category='sleep',
                action="Extend sleep opportunity by 30-60 minutes: earlier bedtime or later wake time",
                rationale="You're averaging less than 7 hours of sleep. This affects recovery, cognition, and metabolism.",
                expected_impact="More sleep improves HRV, reduces RHR, and enhances recovery",
                timeline="Immediate improvements in energy, 2-4 weeks for biomarker changes",
                evidence_strength='strong',
                based_on=['Sleep duration data'],
            ),
            'low_efficiency': Recommendation(
                priority='medium',
                category='sleep',
                action="Improve sleep hygiene: consistent schedule, cool dark room, limit screens 1hr before bed",
                rationale="Your sleep efficiency is below optimal. You may be spending too much time in bed awake.",
                expected_impact="Better efficiency means more restorative sleep in the same time",
                timeline="1-2 weeks for habit changes to take effect",
                evidence_strength='moderate',
                based_on=['Sleep efficiency data'],
            ),
            'low_deep': Recommendation(
                priority='medium',
                category='sleep',
                action="Avoid alcohol close to bedtime; exercise earlier in the day (not within 3hrs of sleep)",
                rationale="Your deep sleep percentage is low. Alcohol and late exercise both suppress deep sleep.",
                expected_impact="Improved deep sleep enhances physical recovery and memory consolidation",
                timeline="Immediate improvement when triggers are removed",
                evidence_strength='moderate',
                based_on=['Sleep architecture data'],
            ),
        },
        'activity': {
            'low_steps': Recommendation(
                priority='high',
                category='activity',
                action="Add 2,000 steps per day to your current baseline (10-15 minute walk)",
                rationale="Your daily activity is below recommended levels. Small increases have significant health benefits.",
                expected_impact="Every 1,000 steps/day reduces mortality risk by ~6%",
                timeline="Immediate health benefits, measurable fitness changes in 4-6 weeks",
                evidence_strength='strong',
                based_on=['Step count data'],
            ),
            'inconsistent': Recommendation(
                priority='medium',
                category='activity',
                action="Schedule regular activity: same time each day, even if just 10 minutes",
                rationale="Your activity is inconsistent. Regular patterns are more beneficial than sporadic bursts.",
                expected_impact="Consistent activity improves metabolic health and habit formation",
                timeline="2-4 weeks to establish habit",
                evidence_strength='moderate',
                based_on=['Activity variability analysis'],
            ),
        },
        'body_composition': {
            'weight_gain': Recommendation(
                priority='medium',
                category='activity',
                action="Focus on sustainable calorie deficit through increased activity and mindful eating",
                rationale="Your weight trend is upward. Gradual changes are more sustainable than rapid diets.",
                expected_impact="0.5-1 kg/week loss is sustainable and preserves muscle mass",
                timeline="Visible changes in 4-8 weeks, significant in 3-6 months",
                evidence_strength='strong',
                based_on=['Weight trend analysis'],
            ),
            'elevated_bf': Recommendation(
                priority='medium',
                category='activity',
                action="Add resistance training 2-3x/week to build lean mass and improve body composition",
                rationale="Your body fat percentage is elevated. Building muscle increases metabolic rate.",
                expected_impact="Improved muscle mass enhances daily calorie burn and metabolic health",
                timeline="4-8 weeks for initial strength gains, 12+ weeks for visible composition changes",
                evidence_strength='strong',
                based_on=['Body fat percentage'],
            ),
        },
    }

    # Add recommendations based on risk factors
    for rf in risk_factors:
        if rf.level in ('elevated', 'high'):
            if 'cardiovascular' in rf.name.lower():
                if any('vo2' in f.lower() for f in rf.contributing_factors):
                    recommendations.append(domain_recommendations['cardiovascular']['low_vo2'])
                if any('hrv' in f.lower() for f in rf.contributing_factors):
                    recommendations.append(domain_recommendations['cardiovascular']['low_hrv'])
            if 'sleep' in rf.name.lower():
                recommendations.append(domain_recommendations['sleep']['low_duration'])
            if 'sedentary' in rf.name.lower():
                recommendations.append(domain_recommendations['activity']['low_steps'])
            if 'body composition' in rf.name.lower():
                if any('gain' in f.lower() for f in rf.contributing_factors):
                    recommendations.append(domain_recommendations['body_composition']['weight_gain'])

    # Add recommendations based on domain-specific limiting factors
    for limiting in wellness_score.cardiovascular.limiting_factors:
        if 'hrv' in limiting.lower():
            if domain_recommendations['cardiovascular']['low_hrv'] not in recommendations:
                recommendations.append(domain_recommendations['cardiovascular']['low_hrv'])
        if 'rhr' in limiting.lower():
            if domain_recommendations['cardiovascular']['high_rhr'] not in recommendations:
                recommendations.append(domain_recommendations['cardiovascular']['high_rhr'])

    for limiting in wellness_score.sleep.limiting_factors:
        if 'insufficient' in limiting.lower() or 'duration' in limiting.lower():
            if domain_recommendations['sleep']['low_duration'] not in recommendations:
                recommendations.append(domain_recommendations['sleep']['low_duration'])
        if 'efficiency' in limiting.lower():
            if domain_recommendations['sleep']['low_efficiency'] not in recommendations:
                recommendations.append(domain_recommendations['sleep']['low_efficiency'])
        if 'deep' in limiting.lower():
            if domain_recommendations['sleep']['low_deep'] not in recommendations:
                recommendations.append(domain_recommendations['sleep']['low_deep'])

    for limiting in wellness_score.activity.limiting_factors:
        if 'low activity' in limiting.lower() or 'steps' in limiting.lower():
            if domain_recommendations['activity']['low_steps'] not in recommendations:
                recommendations.append(domain_recommendations['activity']['low_steps'])
        if 'inconsistent' in limiting.lower():
            if domain_recommendations['activity']['inconsistent'] not in recommendations:
                recommendations.append(domain_recommendations['activity']['inconsistent'])

    # Add interconnection-based recommendations
    for ic in interconnections:
        if ic.is_significant and ic.strength in ('strong', 'moderate'):
            # Daylight -> Sleep correlation
            if ic.source_domain == 'circadian' and ic.target_domain == 'sleep':
                if ic.relationship == 'positive':
                    recommendations.append(Recommendation(
                        priority='medium',
                        category='circadian',
                        action="Get 30+ minutes of morning daylight exposure (before 10am)",
                        rationale=f"Your data shows daylight exposure correlates with better sleep (r={ic.correlation:.2f})",
                        expected_impact="Based on your data, expect improved sleep quality with consistent morning light",
                        timeline="1-2 weeks for circadian adjustment",
                        evidence_strength='moderate',
                        based_on=['Daylight-sleep correlation in your data'],
                    ))
                    break  # Only add once

    # Sort by priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    recommendations.sort(key=lambda r: priority_order.get(r.priority, 3))

    # Limit to top 5 recommendations to avoid overwhelm
    return recommendations[:5]


# =============================================================================
# MAIN ANALYSIS FUNCTION
# =============================================================================

def generate_holistic_insight(
    inputs: AnalysisInputs,
) -> HolisticInsight:
    """Generate comprehensive holistic insight from all data.

    This is the main entry point for holistic analysis.

    Args:
        inputs: AnalysisInputs containing all data and pre-computed analyses

    Returns:
        HolisticInsight with synthesized findings and recommendations
    """
    # Aggregate signals by biomarker
    signals_by_biomarker = aggregate_signals(inputs.signals)

    # Compute data adequacy
    data_adequacy = compute_data_adequacy(inputs.signals)

    # Detect paradoxes
    paradoxes = detect_all_paradoxes(signals_by_biomarker)

    # Detect behavioral patterns
    behavioral_patterns = detect_all_behavioral_patterns(signals_by_biomarker)

    # Find cross-domain interconnections
    interconnections = find_cross_domain_interconnections(signals_by_biomarker)

    # Compute wellness score
    wellness_score = compute_wellness_score(
        signals_by_biomarker,
        vo2max_report=inputs.vo2max,
        sleep_report=inputs.sleep,
        derived_report=inputs.derived,
        body_composition_report=inputs.body_composition,
    )

    # Synthesize risk factors
    risk_factors = synthesize_risk_factors(
        wellness_score,
        interconnections,
        signals_by_biomarker,
        inputs.derived,
    )

    # Identify protective factors
    protective_factors = identify_protective_factors(
        wellness_score,
        behavioral_patterns,
    )

    # Extract primary findings from wellness score
    primary_findings = []
    secondary_findings = []

    # Add findings from each domain
    for domain_name, domain_score in [
        ('cardiovascular', wellness_score.cardiovascular),
        ('sleep', wellness_score.sleep),
        ('activity', wellness_score.activity),
        ('recovery', wellness_score.recovery),
        ('body_composition', wellness_score.body_composition),
    ]:
        # Add positive contributors as findings
        for contributor in domain_score.key_contributors:
            finding = Finding(
                category=domain_name,
                severity='positive',
                title=contributor.split('(')[0].strip(),
                description=contributor,
                evidence=f"Domain score: {domain_score.score:.0f}/100",
                confidence=domain_score.confidence,
                actionable=False,
                related_biomarkers=[],
            )
            if domain_score.score >= 80:
                primary_findings.append(finding)
            else:
                secondary_findings.append(finding)

        # Add limiting factors as concerns
        for limiting in domain_score.limiting_factors:
            severity = 'warning' if domain_score.score < 50 else 'concern'
            finding = Finding(
                category=domain_name,
                severity=severity,
                title=limiting.split('(')[0].strip(),
                description=limiting,
                evidence=f"Domain score: {domain_score.score:.0f}/100",
                confidence=domain_score.confidence,
                actionable=True,
                related_biomarkers=[],
            )
            if domain_score.score < 60:
                primary_findings.append(finding)
            else:
                secondary_findings.append(finding)

    # Add paradox findings
    for paradox in paradoxes:
        finding = Finding(
            category='behavioral',
            severity='neutral',
            title=f"Detected: {paradox.name}",
            description=paradox.explanation,
            evidence=f"Raw r={paradox.raw_correlation:.2f}, Detrended r={paradox.detrended_correlation:.2f}",
            confidence='high',
            actionable=False,
            related_biomarkers=[paradox.biomarker_a, paradox.biomarker_b],
        )
        secondary_findings.append(finding)

    # Sort findings: warnings first, then concerns, then positive
    severity_order = {'warning': 0, 'concern': 1, 'neutral': 2, 'positive': 3}
    primary_findings.sort(key=lambda f: severity_order.get(f.severity, 4))
    secondary_findings.sort(key=lambda f: severity_order.get(f.severity, 4))

    # Limit primary findings to top 5
    primary_findings = primary_findings[:5]

    # Determine overall confidence
    sufficient_count = sum(1 for da in data_adequacy if da.status == 'sufficient')
    total_count = len(data_adequacy) if data_adequacy else 1

    if sufficient_count >= total_count * 0.7:
        overall_confidence = 'high'
    elif sufficient_count >= total_count * 0.4:
        overall_confidence = 'moderate'
    else:
        overall_confidence = 'low'

    # Determine trajectory
    improving_domains = sum(1 for d in [
        wellness_score.cardiovascular,
        wellness_score.sleep,
        wellness_score.activity,
        wellness_score.body_composition,
    ] if d.trend == 'improving')

    declining_domains = sum(1 for d in [
        wellness_score.cardiovascular,
        wellness_score.sleep,
        wellness_score.activity,
        wellness_score.body_composition,
    ] if d.trend == 'declining')

    if improving_domains > declining_domains and improving_domains >= 2:
        trajectory = 'improving'
        trajectory_details = f"{improving_domains} domains showing improvement"
    elif declining_domains > improving_domains and declining_domains >= 2:
        trajectory = 'declining'
        trajectory_details = f"{declining_domains} domains showing decline"
    else:
        trajectory = 'stable'
        trajectory_details = "Most domains stable"

    # Determine analysis period
    if len(inputs.signals) > 0:
        times = pd.to_datetime(inputs.signals['time'])
        period_start = times.min().date()
        period_end = times.max().date()
    else:
        period_start = date.today()
        period_end = date.today()

    return HolisticInsight(
        generated_at=datetime.now(),
        analysis_period_start=period_start,
        analysis_period_end=period_end,
        wellness_score=wellness_score,
        primary_findings=primary_findings,
        secondary_findings=secondary_findings,
        interconnections=interconnections,
        paradoxes=paradoxes,
        behavioral_patterns=behavioral_patterns,
        risk_factors=risk_factors,
        protective_factors=protective_factors,
        recommendations=generate_recommendations(
            wellness_score,
            interconnections,
            risk_factors,
            behavioral_patterns,
        ),
        data_adequacy=data_adequacy,
        overall_confidence=overall_confidence,
        trajectory=trajectory,
        trajectory_details=trajectory_details,
    )
