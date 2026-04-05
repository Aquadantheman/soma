"""Bayesian Intervention Analysis Module.

Clinical-grade Bayesian inference for intervention impact analysis.
Provides probability statements like "87% probability of positive effect"
instead of p-values, with literature-backed priors and Jeffreys' scale
evidence strength interpretation.

This module answers: "What is the PROBABILITY that this intervention helped?"
with honest uncertainty quantification that clinicians can trust.

References:
- Jeffreys, H. (1961). Theory of Probability (3rd ed.). Oxford University Press.
- Guyatt et al. (2008). N-of-1 trials. JAMA.
- Kruschke, J.K. (2013). Bayesian estimation supersedes the t-test.
  Journal of Experimental Psychology.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal, Optional

import numpy as np
from scipy import stats

# =============================================================================
# EVIDENCE STRENGTH (JEFFREYS' SCALE)
# =============================================================================


class EvidenceStrength(Enum):
    """Evidence strength according to Jeffreys' scale.

    These are the standard categories used in Bayesian hypothesis testing.
    Bayes Factor (BF) interpretation:
    - BF > 100: Decisive evidence
    - 30 < BF <= 100: Very strong evidence
    - 10 < BF <= 30: Strong evidence
    - 3 < BF <= 10: Moderate evidence
    - 1 < BF <= 3: Weak evidence
    - BF = 1: No evidence
    - BF < 1: Evidence against
    """

    DECISIVE = "decisive"  # BF > 100
    VERY_STRONG = "very_strong"  # 30 < BF <= 100
    STRONG = "strong"  # 10 < BF <= 30
    MODERATE = "moderate"  # 3 < BF <= 10
    WEAK = "weak"  # 1 < BF <= 3
    NONE = "none"  # BF ≈ 1
    AGAINST = "against"  # BF < 1


def interpret_bayes_factor(bf: float) -> EvidenceStrength:
    """Interpret Bayes factor using Jeffreys' scale."""
    if bf > 100:
        return EvidenceStrength.DECISIVE
    elif bf > 30:
        return EvidenceStrength.VERY_STRONG
    elif bf > 10:
        return EvidenceStrength.STRONG
    elif bf > 3:
        return EvidenceStrength.MODERATE
    elif bf > 1:
        return EvidenceStrength.WEAK
    elif bf >= 0.99:  # Close to 1
        return EvidenceStrength.NONE
    else:
        return EvidenceStrength.AGAINST


# =============================================================================
# LITERATURE-BACKED PRIORS
# =============================================================================


@dataclass
class InterventionPrior:
    """Literature-backed prior probability for an intervention's effect.

    Priors are derived from meta-analyses and clinical studies.
    Each prior specifies:
    - P(improvement): Prior probability intervention helps
    - P(harm): Prior probability intervention hurts
    - P(null) = 1 - P(improvement) - P(harm)
    """

    intervention_category: str
    biomarker: str
    p_improvement: float  # Prior probability of positive effect
    p_harm: float  # Prior probability of negative effect
    expected_effect_size: float  # Expected Cohen's d if effect exists
    effect_size_sd: float  # Uncertainty in expected effect size
    sources: list[str]  # Citations
    sample_size: int  # Combined N from studies
    confidence: Literal["high", "medium", "low"]  # Quality of evidence

    @property
    def p_null(self) -> float:
        """Prior probability of no effect."""
        return 1.0 - self.p_improvement - self.p_harm


# Literature-backed priors from meta-analyses
LITERATURE_PRIORS: dict[tuple[str, str], InterventionPrior] = {
    # Meditation effects - strong evidence base
    ("stress", "hrv_sdnn"): InterventionPrior(
        intervention_category="stress",
        biomarker="hrv_sdnn",
        p_improvement=0.72,
        p_harm=0.03,
        expected_effect_size=0.45,
        effect_size_sd=0.20,
        sources=[
            "Zou et al. (2018) Psychosom Med - Meta-analysis: d=0.45, n=1892",
            "Pascoe et al. (2017) Stress Health - Meta-analysis: d=0.42, n=1034",
        ],
        sample_size=2926,
        confidence="high",
    ),
    ("stress", "resting_hr"): InterventionPrior(
        intervention_category="stress",
        biomarker="resting_hr",
        p_improvement=0.65,  # Lower HR is improvement
        p_harm=0.05,
        expected_effect_size=0.35,
        effect_size_sd=0.18,
        sources=[
            "Pascoe et al. (2017) Stress Health - Resting HR reduction",
        ],
        sample_size=1034,
        confidence="medium",
    ),
    # Exercise effects - very strong evidence base
    ("exercise", "resting_hr"): InterventionPrior(
        intervention_category="exercise",
        biomarker="resting_hr",
        p_improvement=0.85,
        p_harm=0.02,
        expected_effect_size=0.65,
        effect_size_sd=0.25,
        sources=[
            "Reimers et al. (2018) Sports Med - Meta-analysis: d=0.65, n=3452",
            "Huang et al. (2005) Med Sci Sports Exerc - d=0.58, n=892",
        ],
        sample_size=4344,
        confidence="high",
    ),
    ("exercise", "hrv_sdnn"): InterventionPrior(
        intervention_category="exercise",
        biomarker="hrv_sdnn",
        p_improvement=0.75,
        p_harm=0.05,
        expected_effect_size=0.50,
        effect_size_sd=0.22,
        sources=[
            "Sandercock et al. (2005) Sports Med - Meta-analysis HRV",
        ],
        sample_size=812,
        confidence="medium",
    ),
    ("exercise", "vo2_max"): InterventionPrior(
        intervention_category="exercise",
        biomarker="vo2_max",
        p_improvement=0.90,
        p_harm=0.01,
        expected_effect_size=0.80,
        effect_size_sd=0.30,
        sources=[
            "Weston et al. (2014) Sports Med - HIIT meta-analysis: d=0.80",
        ],
        sample_size=1256,
        confidence="high",
    ),
    # Sleep interventions
    ("sleep", "sleep_duration"): InterventionPrior(
        intervention_category="sleep",
        biomarker="sleep_duration",
        p_improvement=0.60,
        p_harm=0.05,
        expected_effect_size=0.40,
        effect_size_sd=0.20,
        sources=[
            "Irish et al. (2015) Ann Behav Med - Sleep hygiene meta-analysis",
        ],
        sample_size=2089,
        confidence="medium",
    ),
    ("sleep", "hrv_sdnn"): InterventionPrior(
        intervention_category="sleep",
        biomarker="hrv_sdnn",
        p_improvement=0.55,
        p_harm=0.08,
        expected_effect_size=0.30,
        effect_size_sd=0.18,
        sources=[
            "Tobaldini et al. (2013) Sleep - Sleep and autonomic function",
        ],
        sample_size=456,
        confidence="low",
    ),
    # Supplements - generally weaker evidence
    ("supplement", "hrv_sdnn"): InterventionPrior(
        intervention_category="supplement",
        biomarker="hrv_sdnn",
        p_improvement=0.40,
        p_harm=0.10,
        expected_effect_size=0.25,
        effect_size_sd=0.15,
        sources=[
            "General supplement literature - mixed results",
        ],
        sample_size=500,
        confidence="low",
    ),
    ("supplement", "resting_hr"): InterventionPrior(
        intervention_category="supplement",
        biomarker="resting_hr",
        p_improvement=0.35,
        p_harm=0.10,
        expected_effect_size=0.20,
        effect_size_sd=0.15,
        sources=[
            "General supplement literature - mixed results",
        ],
        sample_size=500,
        confidence="low",
    ),
}

# Default skeptical prior for unknown intervention-biomarker pairs
DEFAULT_PRIOR = InterventionPrior(
    intervention_category="unknown",
    biomarker="unknown",
    p_improvement=0.33,  # Uninformative
    p_harm=0.10,
    expected_effect_size=0.20,
    effect_size_sd=0.30,
    sources=["Skeptical default prior"],
    sample_size=0,
    confidence="low",
)


def get_prior(category: str, biomarker: str) -> InterventionPrior:
    """Get literature-backed prior for intervention-biomarker pair.

    Falls back to skeptical default if no specific prior exists.
    """
    key = (category.lower(), biomarker.lower())
    return LITERATURE_PRIORS.get(key, DEFAULT_PRIOR)


# =============================================================================
# MINIMAL CLINICALLY IMPORTANT DIFFERENCE (MCID)
# =============================================================================

# MCIDs from clinical literature - the smallest change that matters
MCID_VALUES: dict[str, dict] = {
    "hrv_sdnn": {
        "value": 8.0,  # 8ms change in SDNN
        "unit": "ms",
        "source": "Nunan et al. (2010) Int J Cardiol",
        "direction": "higher_is_better",
    },
    "hrv_rmssd": {
        "value": 10.0,  # 10ms change in RMSSD
        "unit": "ms",
        "source": "Shaffer & Ginsberg (2017) Front Public Health",
        "direction": "higher_is_better",
    },
    "resting_hr": {
        "value": 3.0,  # 3bpm change
        "unit": "bpm",
        "source": "Reimers et al. (2018) Sports Med",
        "direction": "lower_is_better",
    },
    "resting_heart_rate": {
        "value": 3.0,
        "unit": "bpm",
        "source": "Reimers et al. (2018) Sports Med",
        "direction": "lower_is_better",
    },
    "sleep_duration": {
        "value": 30.0,  # 30 minutes
        "unit": "minutes",
        "source": "Buysse et al. (2006) Sleep",
        "direction": "higher_is_better",
    },
    "vo2_max": {
        "value": 3.5,  # 3.5 mL/kg/min (1 MET)
        "unit": "mL/kg/min",
        "source": "Kodama et al. (2009) JAMA",
        "direction": "higher_is_better",
    },
    "body_fat_percentage": {
        "value": 2.0,  # 2% body fat
        "unit": "%",
        "source": "ACSM Guidelines",
        "direction": "lower_is_better",
    },
    "stress_score": {
        "value": 10.0,  # 10 points on typical stress scale
        "unit": "points",
        "source": "Cohen Perceived Stress Scale",
        "direction": "lower_is_better",
    },
}


def get_mcid(biomarker: str) -> Optional[dict]:
    """Get MCID for a biomarker, if known."""
    return MCID_VALUES.get(biomarker.lower())


def is_clinically_meaningful(biomarker: str, absolute_change: float) -> bool:
    """Check if a change exceeds the MCID threshold."""
    mcid = get_mcid(biomarker)
    if mcid is None:
        # No MCID known - use effect size threshold instead
        return True  # Assume meaningful if we don't know
    return abs(absolute_change) >= mcid["value"]


def compute_personal_mcid(before_std: float, multiplier: float = 0.5) -> float:
    """Compute personal MCID based on individual variance.

    The personal MCID is the minimum change that exceeds normal
    day-to-day variation for THIS individual.

    Args:
        before_std: Standard deviation of before-period measurements
        multiplier: How many SDs constitute a meaningful change (default 0.5)
                   0.5 SD is a common threshold in clinical literature
                   for "minimally important difference"

    Returns:
        Personal MCID value

    References:
        Norman et al. (2003) Med Care - 0.5 SD as MID threshold
        Revicki et al. (2008) Qual Life Res - 0.3-0.5 SD range
    """
    return before_std * multiplier


def is_personally_meaningful(
    absolute_change: float, before_std: float, threshold_multiplier: float = 0.5
) -> bool:
    """Check if change exceeds personal MCID.

    More relevant for personal tracking than population MCIDs.
    """
    if before_std <= 0:
        return True  # Can't compute, assume meaningful
    personal_mcid = compute_personal_mcid(before_std, threshold_multiplier)
    return abs(absolute_change) >= personal_mcid


# =============================================================================
# DATA SUFFICIENCY ASSESSMENT
# =============================================================================


@dataclass
class DataSufficiency:
    """Assessment of whether we have enough data for reliable conclusions."""

    level: Literal["high", "medium", "low", "insufficient"]
    n_before: int
    n_after: int
    min_recommended: int
    message: str
    confidence_penalty: float  # How much to discount confidence (0-1)


def assess_data_sufficiency(n_before: int, n_after: int) -> DataSufficiency:
    """Assess whether sample sizes are adequate for reliable inference.

    Based on power analysis for detecting medium effect sizes (d=0.5).

    Sample size guidelines:
    - n < 5: Insufficient - results unreliable
    - 5 <= n < 14: Low - wide uncertainty, preliminary only
    - 14 <= n < 30: Medium - reasonable estimates, some uncertainty
    - n >= 30: High - stable estimates

    References:
        Cohen (1988) - Power analysis conventions
        Lakens (2013) - Sample size planning for effect sizes
    """
    n_min = min(n_before, n_after)

    if n_min < 5:
        return DataSufficiency(
            level="insufficient",
            n_before=n_before,
            n_after=n_after,
            min_recommended=14,
            message=f"Insufficient data (n={n_min}). Need at least 5 days in each period.",
            confidence_penalty=0.5,
        )
    elif n_min < 14:
        return DataSufficiency(
            level="low",
            n_before=n_before,
            n_after=n_after,
            min_recommended=14,
            message=f"Limited data (n={n_min}). Results are preliminary. Recommend 14+ days.",
            confidence_penalty=0.25,
        )
    elif n_min < 30:
        return DataSufficiency(
            level="medium",
            n_before=n_before,
            n_after=n_after,
            min_recommended=30,
            message=f"Moderate data (n={n_min}). Results reasonably reliable.",
            confidence_penalty=0.1,
        )
    else:
        return DataSufficiency(
            level="high",
            n_before=n_before,
            n_after=n_after,
            min_recommended=30,
            message=f"Sufficient data (n={n_min}). Results are reliable.",
            confidence_penalty=0.0,
        )


# =============================================================================
# CONFLICT DETECTION
# =============================================================================


@dataclass
class BiomarkerConflict:
    """Represents conflicting signals between biomarkers."""

    biomarker_improved: str
    biomarker_worsened: str
    improved_p: float  # P(improvement) for the improved one
    worsened_p: float  # P(harm) for the worsened one
    severity: Literal["mild", "moderate", "severe"]
    interpretation: str


def detect_biomarker_conflicts(
    estimates: list,  # BayesianEffectEstimate
    conflict_threshold: float = 0.6,
) -> list[BiomarkerConflict]:
    """Detect conflicting signals across biomarkers.

    A conflict exists when one biomarker shows improvement while
    another shows harm, both with reasonable confidence.

    Args:
        estimates: List of BayesianEffectEstimate objects
        conflict_threshold: Minimum probability to consider a signal
                           (default 0.6 = 60% confident)

    Returns:
        List of detected conflicts
    """
    conflicts = []

    # Find biomarkers that improved vs worsened
    improved = [
        (e.biomarker, e.p_improvement)
        for e in estimates
        if e.p_improvement >= conflict_threshold
    ]
    worsened = [
        (e.biomarker, e.p_harm) for e in estimates if e.p_harm >= conflict_threshold
    ]

    # Check for conflicts
    for imp_bio, imp_p in improved:
        for harm_bio, harm_p in worsened:
            if imp_bio != harm_bio:
                # Determine severity
                avg_confidence = (imp_p + harm_p) / 2
                if avg_confidence >= 0.85:
                    severity = "severe"
                elif avg_confidence >= 0.70:
                    severity = "moderate"
                else:
                    severity = "mild"

                conflict = BiomarkerConflict(
                    biomarker_improved=imp_bio,
                    biomarker_worsened=harm_bio,
                    improved_p=imp_p,
                    worsened_p=harm_p,
                    severity=severity,
                    interpretation=(
                        f"Conflicting signals: {imp_bio} improved ({imp_p:.0%} confident) "
                        f"but {harm_bio} worsened ({harm_p:.0%} confident). "
                        f"Investigate before continuing intervention."
                    ),
                )
                conflicts.append(conflict)

    return conflicts


# =============================================================================
# PRIOR TRANSPARENCY
# =============================================================================


@dataclass
class PriorInfluence:
    """Quantifies how much the prior affected the conclusion."""

    data_only_p_improvement: float  # P(improvement) using only personal data
    prior_combined_p_improvement: float  # P(improvement) with prior
    prior_influence_points: float  # Difference in percentage points
    prior_influence_direction: Literal["strengthened", "weakened", "minimal"]
    prior_strength: Literal["strong", "moderate", "weak"]
    interpretation: str


def compute_prior_influence(
    observed_d: float,
    n: int,
    prior: InterventionPrior,
    combined_p_improvement: float,
) -> PriorInfluence:
    """Compute how much the prior influenced the result.

    Compares the posterior using priors vs using uninformative priors
    (data-only analysis).
    """
    # Compute data-only probability using uninformative prior
    _uninformative_prior = InterventionPrior(
        intervention_category="uninformative",
        biomarker="any",
        p_improvement=0.33,
        p_harm=0.33,
        expected_effect_size=0.0,
        effect_size_sd=1.0,  # Very wide
        sources=["Uninformative prior"],
        sample_size=0,
        confidence="low",
    )

    # Simple approximation: with uninformative prior, posterior ≈ likelihood-based
    # Using effect size directly
    se_d = math.sqrt((1 / max(n, 2)) + (observed_d**2 / (2 * max(n, 2))))

    # Data-only: P(d > 0) under assumption of centered prior
    if se_d > 0:
        z_score = observed_d / se_d
        data_only_p = stats.norm.cdf(z_score)
    else:
        data_only_p = 0.5

    # Influence calculation
    influence = combined_p_improvement - data_only_p
    influence_points = influence * 100  # Convert to percentage points

    if abs(influence_points) < 5:
        direction = "minimal"
    elif influence_points > 0:
        direction = "strengthened"
    else:
        direction = "weakened"

    # Prior strength based on sample size and confidence
    if prior.sample_size > 1000 and prior.confidence == "high":
        prior_strength = "strong"
    elif prior.sample_size > 200 or prior.confidence == "medium":
        prior_strength = "moderate"
    else:
        prior_strength = "weak"

    # Interpretation
    if abs(influence_points) < 5:
        interp = "Prior had minimal influence. Conclusion driven by your personal data."
    elif direction == "strengthened":
        interp = (
            f"Prior evidence increased confidence by {abs(influence_points):.0f} points. "
            f"Literature supports this intervention's effectiveness."
        )
    else:
        interp = (
            f"Prior evidence reduced confidence by {abs(influence_points):.0f} points. "
            f"Literature suggests more skepticism warranted."
        )

    return PriorInfluence(
        data_only_p_improvement=data_only_p,
        prior_combined_p_improvement=combined_p_improvement,
        prior_influence_points=influence_points,
        prior_influence_direction=direction,
        prior_strength=prior_strength,
        interpretation=interp,
    )


# =============================================================================
# BAYESIAN ANALYSIS RESULTS
# =============================================================================


@dataclass
class BayesianEffectEstimate:
    """Bayesian estimate of intervention effect on a biomarker.

    This is the core output that clinicians care about:
    - Probability statements (not p-values)
    - Effect size with credible interval
    - Evidence strength classification
    - Plain language interpretation
    """

    biomarker: str

    # Posterior probabilities (these sum to 1)
    p_improvement: float  # P(intervention helps | data)
    p_null: float  # P(no effect | data)
    p_harm: float  # P(intervention hurts | data)

    # Bayes factor comparing improvement to null
    bayes_factor: float
    evidence_strength: EvidenceStrength

    # Effect size estimate
    observed_effect_size: float  # Cohen's d
    effect_size_ci_lower: float  # 95% credible interval
    effect_size_ci_upper: float

    # Clinical meaningfulness (population MCID)
    is_clinically_meaningful: bool
    mcid_threshold: Optional[float]

    # Personal meaningfulness (individual variance-based)
    personal_mcid: Optional[float]
    is_personally_meaningful: bool

    # Prior information used
    prior_source: str
    prior_confidence: str
    prior_p_improvement: float

    # Prior transparency
    prior_influence: PriorInfluence

    # Sample information
    n_before: int
    n_after: int

    # Data sufficiency
    data_sufficiency: DataSufficiency

    # Plain language interpretation
    interpretation: str

    def __post_init__(self):
        """Validate probabilities."""
        total = self.p_improvement + self.p_null + self.p_harm
        if not math.isclose(total, 1.0, abs_tol=0.01):
            # Normalize
            self.p_improvement /= total
            self.p_null /= total
            self.p_harm /= total


@dataclass
class BayesianInterventionAnalysis:
    """Complete Bayesian analysis of an intervention.

    Aggregates results across all analyzed biomarkers with
    an overall probability assessment.
    """

    intervention_name: str
    intervention_category: str
    analysis_date: datetime

    # Per-biomarker results
    biomarker_estimates: list[BayesianEffectEstimate]

    # Aggregate probabilities
    overall_p_beneficial: float  # P(net beneficial | data)
    overall_p_neutral: float
    overall_p_harmful: float

    # Summary
    overall_verdict: Literal[
        "probably_beneficial",
        "possibly_beneficial",
        "uncertain",
        "possibly_harmful",
        "probably_harmful",
        "conflicting_signals",  # New: when biomarkers disagree
    ]
    confidence_level: Literal["high", "medium", "low"]

    # Conflict detection
    has_conflicts: bool
    conflicts: list[BiomarkerConflict]
    conflict_warning: Optional[str]

    # Overall data sufficiency
    overall_data_sufficiency: Literal["high", "medium", "low", "insufficient"]
    data_sufficiency_warning: Optional[str]

    # Correlation adjustment (accounts for biomarker redundancy)
    correlation_adjustment: Optional["CorrelationAdjustment"] = None

    # Temporal adjustments (regression to mean, seasonality, trend)
    temporal_adjustments: Optional[dict[str, "TemporalAdjustment"]] = None
    temporal_adjustment_warning: Optional[str] = None

    # Key insight in plain language
    primary_statement: str = ""
    secondary_statements: list[str] = field(default_factory=list)

    # Methodological notes
    priors_used: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


# =============================================================================
# CORRELATION ADJUSTMENT FOR BIOMARKER REDUNDANCY
# =============================================================================


@dataclass
class CorrelationAdjustment:
    """Adjustment for correlated biomarkers.

    When biomarkers are correlated (e.g., HR and HRV), treating them as
    independent overestimates confidence. This computes effective N
    and correlation-adjusted weights.

    Mathematical basis: Eigenvalue decomposition of correlation matrix.
    N_eff = (sum(λ))² / sum(λ²) where λ are eigenvalues.

    References:
    - Nyholt (2004) Am J Hum Genet - Effective number of independent tests
    - Li & Ji (2005) Heredity - Improved effective N estimation
    """

    n_biomarkers: int
    effective_n: float  # Effective number of independent signals
    redundancy_factor: float  # n_biomarkers / effective_n (>1 means redundancy)
    correlation_matrix: Optional[list[list[float]]]  # If computed from data
    biomarker_weights: dict[str, float]  # Correlation-adjusted weights
    adjustment_applied: bool
    explanation: str


def compute_known_correlations() -> dict[tuple[str, str], float]:
    """Return known physiological correlations between biomarkers.

    These are population-level correlations from literature.
    Used when we don't have individual correlation data.

    References:
    - Shaffer & Ginsberg (2017) Front Public Health - HRV measures correlations
    - Electrophysiology Task Force (1996) Circulation - HR-HRV relationship
    """
    return {
        # HR and HRV are strongly inversely correlated
        ("resting_hr", "hrv_sdnn"): -0.65,
        ("resting_hr", "hrv_rmssd"): -0.60,
        ("resting_heart_rate", "hrv_sdnn"): -0.65,
        ("resting_heart_rate", "hrv_rmssd"): -0.60,
        # HRV measures are highly correlated with each other
        ("hrv_sdnn", "hrv_rmssd"): 0.85,
        # Sleep metrics correlations
        ("sleep_duration", "sleep_efficiency"): 0.45,
        ("sleep_duration", "deep_sleep"): 0.55,
        ("deep_sleep", "rem_sleep"): 0.30,
        # Activity metrics
        ("steps", "active_calories"): 0.75,
        ("steps", "active_minutes"): 0.70,
        # Recovery and stress
        ("hrv_sdnn", "recovery_score"): 0.60,
        ("resting_hr", "stress_score"): 0.40,
    }


def get_correlation(
    bio1: str, bio2: str, known_correlations: Optional[dict] = None
) -> float:
    """Get correlation between two biomarkers.

    Uses known physiological correlations if available,
    otherwise assumes independence (r=0).
    """
    if known_correlations is None:
        known_correlations = compute_known_correlations()

    if bio1 == bio2:
        return 1.0

    # Check both orderings
    key1 = (bio1, bio2)
    key2 = (bio2, bio1)

    if key1 in known_correlations:
        return known_correlations[key1]
    if key2 in known_correlations:
        return known_correlations[key2]

    # Unknown correlation - assume weak correlation as conservative default
    # (truly independent biomarkers are rare in physiology)
    return 0.15


def compute_correlation_matrix(
    biomarkers: list[str], known_correlations: Optional[dict] = None
) -> np.ndarray:
    """Build correlation matrix for a set of biomarkers."""
    n = len(biomarkers)
    R = np.eye(n)

    for i in range(n):
        for j in range(i + 1, n):
            r = get_correlation(biomarkers[i], biomarkers[j], known_correlations)
            R[i, j] = r
            R[j, i] = r

    return R


def compute_effective_n_eigenvalue(R: np.ndarray) -> float:
    """Compute effective N using eigenvalue decomposition.

    Formula: N_eff = (sum(λ))² / sum(λ²)

    This is the Nyholt (2004) method for effective number of
    independent tests, adapted for combining correlated evidence.

    When all biomarkers are independent: N_eff = n
    When perfectly correlated: N_eff = 1
    """
    eigenvalues = np.linalg.eigvalsh(R)
    # Clip negative eigenvalues (can occur due to numerical issues)
    eigenvalues = np.clip(eigenvalues, 0, None)

    sum_lambda = np.sum(eigenvalues)
    sum_lambda_sq = np.sum(eigenvalues**2)

    if sum_lambda_sq < 1e-10:
        return 1.0

    n_eff = (sum_lambda**2) / sum_lambda_sq
    return max(1.0, n_eff)  # At least 1


def compute_biomarker_weights(R: np.ndarray, biomarkers: list[str]) -> dict[str, float]:
    """Compute correlation-adjusted weights for each biomarker.

    Uses the inverse of the average correlation as weight.
    Biomarkers highly correlated with others get downweighted.

    Mathematical basis: Related to variance inflation factor (VIF).
    Weight_j ∝ 1 / mean(|r_ij|) for j ≠ i
    """
    n = len(biomarkers)
    weights = {}

    for i, bio in enumerate(biomarkers):
        # Average absolute correlation with other biomarkers
        other_corrs = [abs(R[i, j]) for j in range(n) if j != i]
        if other_corrs:
            avg_corr = np.mean(other_corrs)
            # Weight inversely proportional to correlation
            # More correlated = less unique information = lower weight
            weights[bio] = 1.0 / (1.0 + avg_corr)
        else:
            weights[bio] = 1.0

    # Normalize weights to sum to n (so average weight is 1)
    total = sum(weights.values())
    if total > 0:
        for bio in weights:
            weights[bio] = weights[bio] * n / total

    return weights


def compute_correlation_adjustment(
    biomarkers: list[str],
    custom_correlations: Optional[dict[tuple[str, str], float]] = None,
) -> CorrelationAdjustment:
    """Compute full correlation adjustment for a set of biomarkers.

    Args:
        biomarkers: List of biomarker names being analyzed
        custom_correlations: Optional user-provided correlation data

    Returns:
        CorrelationAdjustment with effective N and weights
    """
    n = len(biomarkers)

    if n <= 1:
        return CorrelationAdjustment(
            n_biomarkers=n,
            effective_n=float(n),
            redundancy_factor=1.0,
            correlation_matrix=None,
            biomarker_weights={bio: 1.0 for bio in biomarkers},
            adjustment_applied=False,
            explanation="Single biomarker, no correlation adjustment needed.",
        )

    # Build correlation matrix
    known_corrs = compute_known_correlations()
    if custom_correlations:
        known_corrs.update(custom_correlations)

    R = compute_correlation_matrix(biomarkers, known_corrs)

    # Compute effective N
    n_eff = compute_effective_n_eigenvalue(R)
    redundancy = n / n_eff

    # Compute weights
    weights = compute_biomarker_weights(R, biomarkers)

    # Generate explanation
    if redundancy > 1.5:
        explanation = (
            f"High redundancy detected (factor={redundancy:.2f}). "
            f"{n} biomarkers provide information equivalent to {n_eff:.1f} "
            f"independent signals. Weights adjusted to avoid overcounting."
        )
    elif redundancy > 1.1:
        explanation = (
            f"Moderate correlation between biomarkers. Effective N={n_eff:.1f} "
            f"(vs {n} raw). Slight weight adjustment applied."
        )
    else:
        explanation = (
            f"Biomarkers are relatively independent. Effective N={n_eff:.1f} "
            f"(close to raw count of {n})."
        )

    return CorrelationAdjustment(
        n_biomarkers=n,
        effective_n=n_eff,
        redundancy_factor=redundancy,
        correlation_matrix=R.tolist(),
        biomarker_weights=weights,
        adjustment_applied=True,
        explanation=explanation,
    )


# =============================================================================
# TEMPORAL CONFOUND ADJUSTMENTS
# =============================================================================


@dataclass
class TemporalAdjustment:
    """Adjustments for temporal confounds in before/after comparisons.

    Three main confounds addressed:
    1. Regression to mean: Extreme baselines naturally regress
    2. Seasonal effects: Biomarkers vary by season
    3. Secular trend: Gradual drift over time

    References:
    - Barnett et al. (2005) Int J Epidemiol - Regression to mean in health
    - Barone et al. (2021) - Seasonality in cardiovascular measures
    - Kontopantelis et al. (2015) BMJ - Interrupted time series analysis
    """

    # Raw values
    raw_before_mean: float
    raw_after_mean: float
    raw_change: float

    # Regression to mean adjustment
    regression_to_mean_effect: float  # Expected change from RTM alone
    rtm_adjusted_change: float  # Change after removing RTM
    baseline_extremity: float  # How extreme was baseline (z-score)
    reliability: float  # Measurement reliability (0-1)

    # Seasonal adjustment
    seasonal_effect: float  # Expected seasonal difference
    seasonally_adjusted_change: float
    before_season: str  # e.g., "winter", "summer"
    after_season: str

    # Trend adjustment
    expected_trend_change: float  # Change expected from pre-existing trend
    trend_adjusted_change: float
    pre_intervention_slope: Optional[float]

    # Combined adjustment
    fully_adjusted_change: float
    adjustment_magnitude: float  # Total adjustment as % of raw change
    confidence_in_adjustment: Literal["high", "medium", "low"]
    explanation: str


def estimate_reliability(
    values: Optional[list[float]],
    known_cv: Optional[float] = None,
    biomarker: Optional[str] = None,
) -> float:
    """Estimate measurement reliability (test-retest correlation).

    Reliability determines how much regression to mean to expect.
    Higher reliability = less regression.

    Can use:
    1. Known coefficient of variation for the biomarker
    2. Computed from repeated measurements
    3. Literature defaults
    """
    # Literature-based defaults for common biomarkers
    # Based on typical day-to-day reliability
    DEFAULT_RELIABILITY = {
        "resting_hr": 0.85,
        "resting_heart_rate": 0.85,
        "hrv_sdnn": 0.70,  # HRV is more variable
        "hrv_rmssd": 0.65,
        "sleep_duration": 0.60,
        "steps": 0.50,  # Highly variable
        "weight": 0.98,  # Very stable
        "blood_pressure": 0.75,
        "spo2": 0.90,
    }

    if biomarker and biomarker.lower() in DEFAULT_RELIABILITY:
        return DEFAULT_RELIABILITY[biomarker.lower()]

    if known_cv is not None:
        # Convert CV to reliability approximation
        # High CV = low reliability
        return max(0.3, 1.0 - known_cv)

    if values is not None and len(values) >= 3:
        # Estimate from data using odd-even reliability
        odd = values[::2]
        even = values[1::2]
        if len(odd) >= 2 and len(even) >= 2:
            corr = np.corrcoef(odd[: len(even)], even[: len(odd)])[0, 1]
            if not np.isnan(corr):
                # Spearman-Brown prophecy formula for full-length reliability
                return max(0.3, min(0.99, 2 * corr / (1 + corr)))

    # Conservative default
    return 0.70


def compute_regression_to_mean(
    before_mean: float,
    population_mean: float,
    before_std: float,
    reliability: float,
) -> tuple[float, float, float]:
    """Compute expected regression to mean effect.

    Formula: RTM_effect = (1 - reliability) × (baseline - population_mean)

    This is the expected change purely from regression, not intervention.

    Args:
        before_mean: Observed baseline mean
        population_mean: Expected population/personal mean
        before_std: Standard deviation
        reliability: Measurement reliability (0-1)

    Returns:
        (rtm_effect, baseline_extremity_z, adjusted_expectation)
    """
    # Z-score of baseline relative to population
    if before_std > 0:
        baseline_z = (before_mean - population_mean) / before_std
    else:
        baseline_z = 0.0

    # Expected regression to mean
    # If baseline is above average, expect decrease (positive RTM for lower-is-better)
    # If baseline is below average, expect increase
    rtm_effect = (1 - reliability) * (before_mean - population_mean)

    # Expected value after regression
    expected_after_rtm = before_mean - rtm_effect

    return rtm_effect, baseline_z, expected_after_rtm


def get_season(date) -> str:
    """Determine season from date (Northern Hemisphere)."""
    if hasattr(date, "month"):
        month = date.month
    else:
        month = date  # Assume numeric month passed

    if month in (12, 1, 2):
        return "winter"
    elif month in (3, 4, 5):
        return "spring"
    elif month in (6, 7, 8):
        return "summer"
    else:
        return "fall"


def compute_seasonal_effect(
    biomarker: str,
    before_season: str,
    after_season: str,
) -> float:
    """Estimate expected seasonal difference for a biomarker.

    Based on literature values for seasonal variation in biomarkers.

    References:
    - Wyse et al. (2017) J Clin Sleep Med - Sleep seasonality
    - Marti-Soler et al. (2014) - Physical activity seasonality
    """
    # Seasonal effects as (summer - winter) standardized difference
    # Positive = higher in summer
    SEASONAL_EFFECTS = {
        "steps": 0.35,  # More active in summer
        "active_minutes": 0.40,
        "active_calories": 0.35,
        "resting_hr": -0.15,  # Slightly lower in winter
        "resting_heart_rate": -0.15,
        "hrv_sdnn": 0.10,  # Slightly higher in summer
        "hrv_rmssd": 0.10,
        "sleep_duration": -0.20,  # Longer sleep in winter
        "vitamin_d": 0.80,  # Much higher in summer
        "weight": -0.10,  # Slightly lower in summer
    }

    # Get base effect
    base_effect = SEASONAL_EFFECTS.get(biomarker.lower(), 0.0)

    if base_effect == 0:
        return 0.0

    # Convert seasons to numeric (0=winter, 1=spring, 2=summer, 3=fall)
    season_num = {"winter": 0, "spring": 1, "summer": 2, "fall": 3}
    before_num = season_num.get(before_season.lower(), 0)
    after_num = season_num.get(after_season.lower(), 0)

    # Approximate seasonal effect using sinusoidal model
    # Peak in summer (season=2)
    before_factor = np.sin(np.pi * (before_num - 0.5) / 2)
    after_factor = np.sin(np.pi * (after_num - 0.5) / 2)

    # Expected change due to season alone
    return base_effect * (after_factor - before_factor)


def compute_trend_effect(
    pre_intervention_values: Optional[list[float]],
    pre_intervention_times: Optional[list[float]],
    post_days: int,
) -> tuple[float, Optional[float]]:
    """Estimate expected change from pre-existing trend.

    Fits linear trend to pre-intervention data and extrapolates.

    Args:
        pre_intervention_values: Values before intervention
        pre_intervention_times: Time points (days) for values
        post_days: Days into post-intervention period (midpoint)

    Returns:
        (expected_change, slope) - expected change from trend extrapolation
    """
    if (
        pre_intervention_values is None
        or pre_intervention_times is None
        or len(pre_intervention_values) < 5
    ):
        return 0.0, None

    values = np.array(pre_intervention_values)
    times = np.array(pre_intervention_times)

    # Fit linear trend
    if len(times) >= 2 and np.std(times) > 0:
        slope, intercept = np.polyfit(times, values, 1)

        # Extrapolate to post-intervention midpoint
        last_pre_time = times[-1]
        post_midpoint_time = last_pre_time + post_days / 2

        expected_at_post = intercept + slope * post_midpoint_time
        expected_at_pre_end = intercept + slope * last_pre_time

        trend_effect = expected_at_post - expected_at_pre_end
        return trend_effect, slope

    return 0.0, None


def compute_temporal_adjustment(
    biomarker: str,
    before_values: list[float],
    after_values: list[float],
    before_dates: Optional[list] = None,
    after_dates: Optional[list] = None,
    population_mean: Optional[float] = None,
) -> TemporalAdjustment:
    """Compute full temporal adjustment for before/after comparison.

    Adjusts for:
    1. Regression to mean
    2. Seasonal effects
    3. Pre-existing trend

    Args:
        biomarker: Name of biomarker
        before_values: Measurements before intervention
        after_values: Measurements after intervention
        before_dates: Dates of before measurements (optional)
        after_dates: Dates of after measurements (optional)
        population_mean: Expected population/personal mean (optional)

    Returns:
        TemporalAdjustment with all corrections
    """
    before_arr = np.array(before_values)
    after_arr = np.array(after_values)

    raw_before = float(np.mean(before_arr))
    raw_after = float(np.mean(after_arr))
    raw_change = raw_after - raw_before
    before_std = float(np.std(before_arr)) if len(before_arr) > 1 else 1.0

    # Use before mean as population mean if not provided
    # (conservative - assumes person is typical)
    if population_mean is None:
        population_mean = raw_before

    # 1. Regression to Mean
    # rtm_effect = (1-r)*(baseline - mean) = how much baseline exceeds expected
    # Expected change from RTM = -rtm_effect (if baseline > mean, expect decrease)
    # True intervention effect = observed_change - expected_rtm_change
    #                          = raw_change - (-rtm_effect) = raw_change + rtm_effect
    reliability = estimate_reliability(before_values, biomarker=biomarker)
    rtm_effect, baseline_z, _ = compute_regression_to_mean(
        raw_before, population_mean, before_std, reliability
    )
    rtm_adjusted = (
        raw_change + rtm_effect
    )  # Add because rtm_effect is opposite of expected change

    # 2. Seasonal Adjustment
    if before_dates and after_dates:
        before_season = get_season(before_dates[len(before_dates) // 2])
        after_season = get_season(after_dates[len(after_dates) // 2])
    else:
        before_season = "unknown"
        after_season = "unknown"

    seasonal_effect = compute_seasonal_effect(biomarker, before_season, after_season)
    # Convert from standardized to raw units
    seasonal_effect_raw = seasonal_effect * before_std
    seasonally_adjusted = raw_change - seasonal_effect_raw

    # 3. Trend Adjustment
    if before_dates and len(before_values) >= 5:
        # Convert dates to numeric days
        try:
            if hasattr(before_dates[0], "toordinal"):
                times = [
                    d.toordinal() - before_dates[0].toordinal() for d in before_dates
                ]
            else:
                times = list(range(len(before_values)))
        except Exception:
            times = list(range(len(before_values)))

        post_days = len(after_values)
        trend_effect, slope = compute_trend_effect(before_values, times, post_days)
    else:
        trend_effect = 0.0
        slope = None

    trend_adjusted = raw_change - trend_effect

    # Combined adjustment
    # RTM: expected change = -rtm_effect, so true = observed - (-rtm_effect) = observed + rtm_effect
    # Seasonal: expected change = seasonal_effect, so true = observed - seasonal_effect
    # Trend: expected change = trend_effect, so true = observed - trend_effect
    # Combined: true = observed + rtm_effect - seasonal_effect - trend_effect
    fully_adjusted = raw_change + rtm_effect - seasonal_effect_raw - trend_effect

    # Total confound magnitude (for reporting)
    total_confound = abs(-rtm_effect) + abs(seasonal_effect_raw) + abs(trend_effect)

    # Magnitude of adjustment
    if abs(raw_change) > 1e-6:
        adjustment_pct = abs(total_confound / raw_change)
    else:
        adjustment_pct = 0.0

    # Confidence in adjustment
    if len(before_values) >= 14 and before_dates is not None and abs(baseline_z) < 2.0:
        confidence = "high"
    elif len(before_values) >= 7:
        confidence = "medium"
    else:
        confidence = "low"

    # Generate explanation
    explanations = []
    if abs(rtm_effect) > 0.1 * before_std:
        direction = (
            "regression toward average"
            if rtm_effect * raw_change > 0
            else "regression away from average"
        )
        explanations.append(
            f"Baseline was {abs(baseline_z):.1f}σ from average; "
            f"expected {direction} of {abs(rtm_effect):.2f}"
        )

    if abs(seasonal_effect_raw) > 0.05 * before_std:
        explanations.append(
            f"Seasonal effect ({before_season}→{after_season}): "
            f"expected change of {seasonal_effect_raw:+.2f}"
        )

    if abs(trend_effect) > 0.05 * before_std and slope is not None:
        explanations.append(
            f"Pre-existing trend (slope={slope:.3f}/day) expected {trend_effect:+.2f}"
        )

    if not explanations:
        explanation = "Minimal temporal confounds detected."
    else:
        explanation = " | ".join(explanations)
        explanation += (
            f" | Adjusted change: {fully_adjusted:+.2f} (raw: {raw_change:+.2f})"
        )

    return TemporalAdjustment(
        raw_before_mean=raw_before,
        raw_after_mean=raw_after,
        raw_change=raw_change,
        regression_to_mean_effect=rtm_effect,
        rtm_adjusted_change=rtm_adjusted,
        baseline_extremity=baseline_z,
        reliability=reliability,
        seasonal_effect=seasonal_effect_raw,
        seasonally_adjusted_change=seasonally_adjusted,
        before_season=before_season,
        after_season=after_season,
        expected_trend_change=trend_effect,
        trend_adjusted_change=trend_adjusted,
        pre_intervention_slope=slope,
        fully_adjusted_change=fully_adjusted,
        adjustment_magnitude=adjustment_pct,
        confidence_in_adjustment=confidence,
        explanation=explanation,
    )


# =============================================================================
# BAYESIAN INFERENCE ENGINE
# =============================================================================


def compute_likelihood_ratio(
    observed_d: float,
    n: int,
    h1_mean: float,
    h0_mean: float = 0.0,
    effect_sd: float = 0.3,
) -> float:
    """Compute likelihood ratio P(d | H1) / P(d | H0).

    Uses normal approximation for effect size distribution.
    For small samples, this is conservative.

    Args:
        observed_d: Observed Cohen's d
        n: Sample size (average of before/after)
        h1_mean: Expected effect size under H1
        h0_mean: Expected effect size under H0 (usually 0)
        effect_sd: Standard deviation of effect size prior

    Returns:
        Likelihood ratio
    """
    # Standard error of Cohen's d
    se_d = math.sqrt((1 / n) + (observed_d**2 / (2 * n)))

    # Combined SD under each hypothesis (prior SD + sampling error)
    sd_h1 = math.sqrt(effect_sd**2 + se_d**2)
    sd_h0 = se_d  # Under null, only sampling error

    # Likelihoods (normal approximation)
    lik_h1 = stats.norm.pdf(observed_d, loc=h1_mean, scale=sd_h1)
    lik_h0 = stats.norm.pdf(observed_d, loc=h0_mean, scale=sd_h0)

    if lik_h0 < 1e-10:
        return 1000.0 if lik_h1 > 1e-10 else 1.0

    return lik_h1 / lik_h0


def compute_posterior_probabilities(
    observed_d: float,
    n: int,
    prior: InterventionPrior,
    health_direction: Literal["positive", "negative"],
    absolute_change: float = 0.0,
) -> tuple[float, float, float]:
    """Compute posterior probabilities for improvement/null/harm.

    Args:
        observed_d: Observed Cohen's d (magnitude, always positive)
        n: Average sample size
        prior: Literature-backed prior
        health_direction: Whether positive change is health-improving
        absolute_change: Actual change (with sign) to determine direction

    Returns:
        (p_improvement, p_null, p_harm) - posterior probabilities
    """
    # Determine if the change was health-positive
    # Use absolute_change sign combined with health_direction
    if health_direction == "negative":
        # Lower is better (e.g., resting HR)
        # Negative change = health improvement
        is_health_positive = absolute_change < 0
    else:
        # Higher is better (e.g., HRV)
        # Positive change = health improvement
        is_health_positive = absolute_change > 0

    # Convert effect size to signed value where positive = health improvement
    if is_health_positive:
        observed_d = abs(observed_d)  # Positive = good
    else:
        observed_d = -abs(observed_d)  # Negative = bad

    # Prior probabilities
    p_imp_prior = prior.p_improvement
    p_null_prior = prior.p_null
    p_harm_prior = prior.p_harm

    # Expected effect sizes under each hypothesis
    d_improvement = prior.expected_effect_size  # Positive
    d_null = 0.0
    d_harm = -prior.expected_effect_size  # Negative

    # Compute likelihoods
    se_d = math.sqrt((1 / max(n, 2)) + (observed_d**2 / (2 * max(n, 2))))
    sd_effect = prior.effect_size_sd

    # P(observed | improvement)
    lik_imp = stats.norm.pdf(
        observed_d, loc=d_improvement, scale=math.sqrt(sd_effect**2 + se_d**2)
    )
    # P(observed | null)
    lik_null = stats.norm.pdf(observed_d, loc=d_null, scale=se_d)
    # P(observed | harm)
    lik_harm = stats.norm.pdf(
        observed_d, loc=d_harm, scale=math.sqrt(sd_effect**2 + se_d**2)
    )

    # Bayes' theorem: P(H|D) ∝ P(D|H) * P(H)
    post_imp = lik_imp * p_imp_prior
    post_null = lik_null * p_null_prior
    post_harm = lik_harm * p_harm_prior

    # Normalize
    total = post_imp + post_null + post_harm
    if total < 1e-10:
        # All likelihoods collapsed - return priors
        return p_imp_prior, p_null_prior, p_harm_prior

    return post_imp / total, post_null / total, post_harm / total


def compute_effect_size_credible_interval(
    observed_d: float,
    n_before: int,
    n_after: int,
    prior_mean: float = 0.0,
    prior_sd: float = 0.5,
    credible_level: float = 0.95,
) -> tuple[float, float]:
    """Compute Bayesian credible interval for effect size.

    Uses conjugate normal-normal model with known variance approximation.

    Args:
        observed_d: Observed Cohen's d
        n_before: Sample size before
        n_after: Sample size after
        prior_mean: Prior mean for effect size
        prior_sd: Prior standard deviation
        credible_level: Credible interval level (default 95%)

    Returns:
        (lower, upper) credible interval bounds
    """
    n = (n_before + n_after) / 2

    # Approximate standard error of d
    se_d = math.sqrt((1 / max(n, 2)) + (observed_d**2 / (2 * max(n, 2))))

    # Posterior parameters (conjugate normal-normal)
    prior_precision = 1 / (prior_sd**2)
    data_precision = 1 / (se_d**2)

    posterior_precision = prior_precision + data_precision
    posterior_var = 1 / posterior_precision
    posterior_mean = (
        prior_precision * prior_mean + data_precision * observed_d
    ) / posterior_precision
    posterior_sd = math.sqrt(posterior_var)

    # Credible interval
    alpha = 1 - credible_level
    z = stats.norm.ppf(1 - alpha / 2)

    lower = posterior_mean - z * posterior_sd
    upper = posterior_mean + z * posterior_sd

    return lower, upper


def generate_interpretation(
    biomarker: str,
    p_improvement: float,
    effect_size: float,
    is_meaningful: bool,
    evidence_strength: EvidenceStrength,
) -> str:
    """Generate plain language interpretation of results.

    This is what clinicians and users actually want to read.
    """
    pct = int(p_improvement * 100)

    # Direction-aware language (used for context but not in output)
    _direction = "improved" if effect_size > 0 else "declined"

    # Confidence level based on posterior probability (used for context)
    if pct >= 90:
        _confidence = "strong evidence"
    elif pct >= 75:
        _confidence = "good evidence"
    elif pct >= 60:
        _confidence = "moderate evidence"
    elif pct >= 40:
        _confidence = "weak evidence"
    else:
        _confidence = "little evidence"

    # Clinical meaningfulness caveat
    meaning_note = ""
    if not is_meaningful:
        meaning_note = ", though the change may not be clinically meaningful"

    # Compose interpretation
    if pct >= 75:
        return (
            f"{pct}% probability that this intervention improved {biomarker} "
            f"({evidence_strength.value} evidence){meaning_note}."
        )
    elif pct >= 50:
        return (
            f"{pct}% probability of improvement in {biomarker}, "
            f"but uncertainty remains. More data would help."
        )
    else:
        return (
            f"Only {pct}% probability of improvement in {biomarker}. "
            f"The intervention may not be effective for this biomarker."
        )


# =============================================================================
# MAIN ANALYSIS FUNCTION
# =============================================================================


def analyze_intervention_bayesian(
    intervention_name: str,
    intervention_category: str,
    biomarker_results: list[dict],
) -> BayesianInterventionAnalysis:
    """Perform Bayesian analysis of intervention effects.

    Plug-and-play design: Works with whatever data is available.
    - Minimal: Just summary statistics (effect_size, n_before, n_after)
    - Better: Add raw values for temporal adjustment (regression to mean)
    - Best: Add dates for seasonal and trend adjustment

    Args:
        intervention_name: Name of the intervention
        intervention_category: Category (stress, exercise, sleep, etc.)
        biomarker_results: List of dicts with:
            Required:
            - biomarker: str
            - n_before: int
            - n_after: int

            Option A - Summary statistics (minimal):
            - effect_size: float (Cohen's d)
            - absolute_change: float

            Option B - Raw data (enables temporal adjustment):
            - before_values: list[float] (daily measurements before)
            - after_values: list[float] (daily measurements after)
            - before_dates: list[date] (optional, enables seasonal/trend)
            - after_dates: list[date] (optional, enables seasonal/trend)
            - population_mean: float (optional, for regression to mean)

            Optional:
            - before_std: float (for personal MCID, computed if raw data given)
            - health_direction: 'positive' or 'negative' (default: 'positive')

    Returns:
        BayesianInterventionAnalysis with complete results
    """
    estimates = []
    priors_used = []
    temporal_adjustments = {}  # Store per-biomarker temporal adjustments

    for result in biomarker_results:
        biomarker = result["biomarker"]
        n_before = result["n_before"]
        n_after = result["n_after"]
        health_direction = result.get("health_direction", "positive")

        # Check what data is available
        has_raw_data = "before_values" in result and "after_values" in result
        _has_dates = "before_dates" in result and "after_dates" in result  # noqa: F841
        has_summary = "effect_size" in result and "absolute_change" in result

        # Compute or extract values based on available data
        if has_raw_data:
            # Raw data available - compute everything and apply temporal adjustment
            before_values = result["before_values"]
            after_values = result["after_values"]
            before_dates = result.get("before_dates")
            after_dates = result.get("after_dates")
            population_mean = result.get("population_mean")

            # Compute temporal adjustment
            temp_adj = compute_temporal_adjustment(
                biomarker=biomarker,
                before_values=before_values,
                after_values=after_values,
                before_dates=before_dates,
                after_dates=after_dates,
                population_mean=population_mean,
            )
            temporal_adjustments[biomarker] = temp_adj

            # Use adjusted values
            before_std = float(np.std(before_values)) if len(before_values) > 1 else 1.0
            absolute_change = temp_adj.fully_adjusted_change  # Use adjusted!
            effect_size = absolute_change / before_std if before_std > 0 else 0.0

        elif has_summary:
            # Summary statistics only - use as provided
            effect_size = result["effect_size"]
            absolute_change = result["absolute_change"]
            before_std = result.get(
                "before_std", abs(absolute_change) / max(abs(effect_size), 0.01)
            )
            # No temporal adjustment possible
            temporal_adjustments[biomarker] = None

        else:
            raise ValueError(
                f"Biomarker '{biomarker}' needs either raw data (before_values, after_values) "
                f"or summary statistics (effect_size, absolute_change)"
            )

        # Get literature-backed prior
        prior = get_prior(intervention_category, biomarker)
        priors_used.extend(prior.sources)

        # Compute posteriors
        p_imp, p_null, p_harm = compute_posterior_probabilities(
            observed_d=effect_size,
            n=(n_before + n_after) // 2,
            prior=prior,
            health_direction=health_direction,
            absolute_change=absolute_change,
        )

        # Compute Bayes factor
        if p_null > 0.001:
            bf = p_imp / p_null
        else:
            bf = 1000.0 if p_imp > 0.5 else 1.0
        evidence_strength = interpret_bayes_factor(bf)

        # Credible interval for effect size
        ci_lower, ci_upper = compute_effect_size_credible_interval(
            observed_d=effect_size,
            n_before=n_before,
            n_after=n_after,
            prior_mean=0.0,
            prior_sd=0.5,
        )

        # Clinical meaningfulness (population MCID)
        mcid = get_mcid(biomarker)
        is_clin_meaningful = is_clinically_meaningful(biomarker, absolute_change)

        # Personal meaningfulness (individual variance-based)
        personal_mcid_value = compute_personal_mcid(before_std)
        is_pers_meaningful = is_personally_meaningful(absolute_change, before_std)

        # Prior transparency
        prior_infl = compute_prior_influence(
            observed_d=effect_size,
            n=(n_before + n_after) // 2,
            prior=prior,
            combined_p_improvement=p_imp,
        )

        # Data sufficiency
        data_suff = assess_data_sufficiency(n_before, n_after)

        # Generate interpretation (use personal meaningfulness)
        interpretation = generate_interpretation(
            biomarker=biomarker,
            p_improvement=p_imp,
            effect_size=effect_size,
            is_meaningful=is_pers_meaningful,  # Use personal, not population
            evidence_strength=evidence_strength,
        )

        estimate = BayesianEffectEstimate(
            biomarker=biomarker,
            p_improvement=p_imp,
            p_null=p_null,
            p_harm=p_harm,
            bayes_factor=bf,
            evidence_strength=evidence_strength,
            observed_effect_size=effect_size,
            effect_size_ci_lower=ci_lower,
            effect_size_ci_upper=ci_upper,
            is_clinically_meaningful=is_clin_meaningful,
            mcid_threshold=mcid["value"] if mcid else None,
            personal_mcid=personal_mcid_value,
            is_personally_meaningful=is_pers_meaningful,
            prior_source=prior.sources[0] if prior.sources else "default",
            prior_confidence=prior.confidence,
            prior_p_improvement=prior.p_improvement,
            prior_influence=prior_infl,
            n_before=n_before,
            n_after=n_after,
            data_sufficiency=data_suff,
            interpretation=interpretation,
        )
        estimates.append(estimate)

    # Detect conflicts between biomarkers
    conflicts = detect_biomarker_conflicts(estimates)
    has_conflicts = len(conflicts) > 0
    conflict_warning = None
    if has_conflicts:
        severe_conflicts = [c for c in conflicts if c.severity == "severe"]
        if severe_conflicts:
            conflict_warning = (
                f"CRITICAL: Severe conflicting signals detected. "
                f"{severe_conflicts[0].biomarker_improved} improved while "
                f"{severe_conflicts[0].biomarker_worsened} worsened. "
                f"Do not rely on overall verdict."
            )
        else:
            conflict_warning = (
                "WARNING: Some biomarkers show conflicting responses. "
                "Review individual biomarker results carefully."
            )

    # Assess overall data sufficiency
    sufficiency_levels = [e.data_sufficiency.level for e in estimates]
    if "insufficient" in sufficiency_levels:
        overall_data_suff = "insufficient"
    elif all(s == "high" for s in sufficiency_levels):
        overall_data_suff = "high"
    elif "low" in sufficiency_levels:
        overall_data_suff = "low"
    else:
        overall_data_suff = "medium"

    data_suff_warning = None
    if overall_data_suff in ("low", "insufficient"):
        min_n = min(e.n_before for e in estimates) if estimates else 0
        data_suff_warning = (
            f"Limited data (minimum n={min_n}). "
            f"Results are preliminary. Consider collecting more data."
        )

    # Compute correlation adjustment for biomarker redundancy
    biomarker_names = [e.biomarker for e in estimates]
    corr_adjustment = compute_correlation_adjustment(biomarker_names)

    # Aggregate across biomarkers with correlation-adjusted weights
    if estimates:
        # Evidence strength weights
        evidence_weights = {
            EvidenceStrength.DECISIVE: 5,
            EvidenceStrength.VERY_STRONG: 4,
            EvidenceStrength.STRONG: 3,
            EvidenceStrength.MODERATE: 2,
            EvidenceStrength.WEAK: 1,
            EvidenceStrength.NONE: 0.5,
            EvidenceStrength.AGAINST: 0.5,
        }

        # Combine evidence weight with correlation adjustment
        # This down-weights redundant biomarkers
        combined_weights = []
        for e in estimates:
            ev_weight = evidence_weights[e.evidence_strength]
            corr_weight = corr_adjustment.biomarker_weights.get(e.biomarker, 1.0)
            combined_weights.append(ev_weight * corr_weight)

        total_weight = sum(combined_weights)
        if total_weight > 0:
            overall_p_beneficial = (
                sum(e.p_improvement * w for e, w in zip(estimates, combined_weights))
                / total_weight
            )
            overall_p_harmful = (
                sum(e.p_harm * w for e, w in zip(estimates, combined_weights))
                / total_weight
            )
        else:
            overall_p_beneficial = sum(e.p_improvement for e in estimates) / len(
                estimates
            )
            overall_p_harmful = sum(e.p_harm for e in estimates) / len(estimates)

        overall_p_neutral = 1.0 - overall_p_beneficial - overall_p_harmful

        # Clamp to valid probability range
        overall_p_neutral = max(0.0, overall_p_neutral)
    else:
        overall_p_beneficial = 0.33
        overall_p_neutral = 0.34
        overall_p_harmful = 0.33
        corr_adjustment = None

    # Determine overall verdict
    # IMPORTANT: Conflicts override the standard verdict
    if has_conflicts and any(c.severity in ("severe", "moderate") for c in conflicts):
        verdict = "conflicting_signals"
        confidence = "low"
    elif overall_p_beneficial >= 0.80:
        verdict = "probably_beneficial"
        confidence = "high"
    elif overall_p_beneficial >= 0.60:
        verdict = "possibly_beneficial"
        confidence = "medium"
    elif overall_p_harmful >= 0.60:
        verdict = "possibly_harmful"
        confidence = "medium"
    elif overall_p_harmful >= 0.80:
        verdict = "probably_harmful"
        confidence = "high"
    else:
        verdict = "uncertain"
        confidence = "low"

    # Adjust confidence based on data sufficiency
    if overall_data_suff == "insufficient":
        confidence = "low"
    elif overall_data_suff == "low" and confidence == "high":
        confidence = "medium"

    # Generate primary statement
    pct = int(overall_p_beneficial * 100)
    if verdict == "conflicting_signals":
        primary = (
            f"CONFLICTING SIGNALS: '{intervention_name}' shows mixed effects. "
            f"Some biomarkers improved while others worsened. "
            f"Review individual results before continuing."
        )
    elif verdict == "probably_beneficial":
        primary = (
            f"There is a {pct}% probability that '{intervention_name}' is "
            f"beneficial based on your personal data combined with prior "
            f"clinical evidence."
        )
    elif verdict == "possibly_beneficial":
        primary = (
            f"{pct}% probability of benefit from '{intervention_name}'. "
            f"The evidence is promising but not conclusive."
        )
    elif verdict == "uncertain":
        primary = (
            f"Uncertain whether '{intervention_name}' is helping "
            f"({pct}% probability of benefit). More data needed."
        )
    else:
        harm_pct = int(overall_p_harmful * 100)
        primary = (
            f"Caution: {harm_pct}% probability that '{intervention_name}' "
            f"may be having negative effects."
        )

    # Secondary statements for each biomarker
    secondary = [e.interpretation for e in estimates]

    # Add conflict warnings to secondary statements
    if has_conflicts:
        for conflict in conflicts:
            secondary.insert(0, conflict.interpretation)

    # Limitations
    limitations = [
        "Bayesian analysis assumes priors from population studies apply to you individually.",
        "Short observation periods increase uncertainty.",
        "Concurrent lifestyle changes may confound results.",
    ]

    if overall_data_suff in ("low", "insufficient"):
        limitations.insert(0, "Limited sample size reduces reliability of conclusions.")

    # Add correlation adjustment note to limitations if significant
    if corr_adjustment and corr_adjustment.redundancy_factor > 1.3:
        limitations.append(
            f"Biomarker correlation adjustment applied (effective N={corr_adjustment.effective_n:.1f} "
            f"vs {corr_adjustment.n_biomarkers} raw biomarkers)."
        )

    # Temporal adjustment summary
    temporal_adj_warning = None
    applied_adjustments = [
        b for b, adj in temporal_adjustments.items() if adj is not None
    ]
    unapplied = [b for b, adj in temporal_adjustments.items() if adj is None]

    if applied_adjustments:
        # Check for significant adjustments
        significant_rtm = []
        for bio, adj in temporal_adjustments.items():
            if adj and abs(adj.regression_to_mean_effect) > 0.1 * abs(
                adj.raw_change + 0.001
            ):
                significant_rtm.append(bio)

        if significant_rtm:
            temporal_adj_warning = (
                f"Temporal adjustments applied to {len(applied_adjustments)} biomarker(s). "
                f"Regression-to-mean correction was significant for: {', '.join(significant_rtm)}."
            )
        else:
            temporal_adj_warning = (
                f"Temporal adjustments applied to {len(applied_adjustments)} biomarker(s). "
                f"Corrections were minor."
            )

        # Add to secondary statements
        for bio, adj in temporal_adjustments.items():
            if adj and abs(adj.raw_change - adj.fully_adjusted_change) > 0.5:
                secondary.append(
                    f"{bio}: Raw change {adj.raw_change:+.1f} adjusted to {adj.fully_adjusted_change:+.1f} "
                    f"(accounting for regression to mean and other confounds)."
                )

    if unapplied:
        limitations.append(
            f"Temporal confound adjustment not applied to {len(unapplied)} biomarker(s) "
            f"(raw daily data not provided). Consider providing raw values for more accurate analysis."
        )

    # Convert temporal_adjustments to serializable format (or None if empty)
    temporal_adj_dict = {
        k: v for k, v in temporal_adjustments.items() if v is not None
    } or None

    return BayesianInterventionAnalysis(
        intervention_name=intervention_name,
        intervention_category=intervention_category,
        analysis_date=datetime.now(),
        biomarker_estimates=estimates,
        overall_p_beneficial=overall_p_beneficial,
        overall_p_neutral=overall_p_neutral,
        overall_p_harmful=overall_p_harmful,
        overall_verdict=verdict,
        confidence_level=confidence,
        has_conflicts=has_conflicts,
        conflicts=conflicts,
        conflict_warning=conflict_warning,
        overall_data_sufficiency=overall_data_suff,
        data_sufficiency_warning=data_suff_warning,
        correlation_adjustment=corr_adjustment,
        temporal_adjustments=temporal_adj_dict,
        temporal_adjustment_warning=temporal_adj_warning,
        primary_statement=primary,
        secondary_statements=secondary,
        priors_used=list(set(priors_used)),
        limitations=limitations,
    )
