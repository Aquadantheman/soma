"""Holistic Insights analysis schemas.

Schemas for the holistic analysis module that synthesizes findings
across all biomarker domains to provide integrated health insights.
"""

from datetime import datetime, date
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class DomainScoreSchema(BaseModel):
    """Individual wellness domain score."""

    score: float = Field(ge=0, le=100, description="Domain score (0-100)")
    confidence: Literal["high", "moderate", "low"] = Field(
        description="Confidence in score based on data adequacy"
    )
    trend: Literal["improving", "stable", "declining"] = Field(
        description="Recent trend direction"
    )
    key_contributors: List[str] = Field(
        description="Factors positively contributing to score"
    )
    limiting_factors: List[str] = Field(description="Factors limiting the score")
    data_points: int = Field(ge=0, description="Number of data points used")


class WellnessScoreSchema(BaseModel):
    """Multi-domain wellness score using Harmonic Mean.

    The overall score uses weighted harmonic mean, which naturally penalizes
    imbalance - weak domains pull the score down more than strong domains
    pull it up. This incentivizes fixing weaknesses over boosting strengths.

    Based on V-Clock biological age research showing vector approaches
    are 1.78x more predictive than simple averaging.
    """

    overall: float = Field(
        ge=0, le=100, description="Overall wellness score (Harmonic Mean, 0-100)"
    )
    interpretation: str = Field(
        description="Text interpretation: Excellent/Good/Fair/Needs Attention/Concerning"
    )

    # Domain scores
    cardiovascular: DomainScoreSchema
    sleep: DomainScoreSchema
    activity: DomainScoreSchema
    recovery: DomainScoreSchema
    body_composition: DomainScoreSchema
    mobility: Optional[DomainScoreSchema] = Field(
        None, description="Mobility domain (if sufficient walking data available)"
    )

    # Explainability metrics
    arithmetic_mean: float = Field(
        ge=0, le=100, description="What a simple average would give (for comparison)"
    )
    imbalance_penalty: float = Field(
        ge=0,
        description="Points lost due to imbalance (arithmetic - harmonic). Higher = more imbalanced.",
    )
    bottleneck_domain: str = Field(
        description="Which domain is holding your score back the most"
    )
    bottleneck_impact: float = Field(
        ge=0,
        description="How many points you could gain by improving this domain to match your best",
    )

    # Summary
    strongest_domain: str = Field(description="Best performing domain")
    weakest_domain: str = Field(description="Domain needing most attention")


class FindingSchema(BaseModel):
    """Individual analysis finding."""

    category: str = Field(
        description="Domain: cardiovascular/sleep/activity/recovery/body_composition/cross_domain"
    )
    severity: Literal["positive", "neutral", "concern", "warning"] = Field(
        description="Finding severity/type"
    )
    title: str = Field(description="Short title for the finding")
    description: str = Field(description="Detailed description")
    evidence: str = Field(description="Data-backed evidence for the finding")
    confidence: Literal["high", "moderate", "low"]
    actionable: bool = Field(
        description="Whether this finding has actionable implications"
    )
    related_biomarkers: List[str] = Field(
        description="Biomarkers involved in this finding"
    )


class InterconnectionSchema(BaseModel):
    """Cross-domain interconnection."""

    source_domain: str = Field(description="Source domain (e.g., 'activity')")
    target_domain: str = Field(description="Target domain (e.g., 'sleep')")
    source_biomarker: str = Field(description="Source biomarker slug")
    target_biomarker: str = Field(description="Target biomarker slug")

    correlation: float = Field(ge=-1, le=1, description="Correlation coefficient")
    p_value: float = Field(ge=0, le=1)
    lag_days: int = Field(ge=0, description="Lag in days for relationship")
    strength: Literal["strong", "moderate", "weak"]
    sample_size: int = Field(gt=0)

    pathway: str = Field(description="Human-readable pathway description")
    interpretation: str = Field(description="What this relationship means")


class ParadoxSchema(BaseModel):
    """Detected statistical paradox."""

    name: str = Field(description="Paradox type name")
    biomarker_a: str
    biomarker_b: str

    raw_correlation: float = Field(ge=-1, le=1)
    raw_p_value: float
    detrended_correlation: float = Field(ge=-1, le=1)
    detrended_p_value: float

    confounding_factor: str = Field(description="Identified confounding factor")
    explanation: str = Field(description="Explanation of why correlations differ")
    behavioral_insight: Optional[str] = Field(
        None, description="Behavioral interpretation if applicable"
    )


class BehavioralPatternSchema(BaseModel):
    """Detected behavioral pattern."""

    name: str = Field(description="Pattern name")
    pattern_type: str = Field(
        description="Type: compensatory/weekend_warrior/seasonal/circadian"
    )
    description: str = Field(description="What the pattern shows")
    evidence: str = Field(description="Data supporting this pattern")
    health_implication: Literal["positive", "neutral", "negative"]
    recommendation: Optional[str] = Field(
        None, description="Actionable recommendation based on this pattern"
    )


class RiskFactorSchema(BaseModel):
    """Identified risk factor."""

    name: str
    level: Literal["low", "moderate", "elevated", "high"]
    description: str
    contributing_factors: List[str]
    mitigation_suggestions: List[str]


class RecommendationSchema(BaseModel):
    """Actionable recommendation."""

    priority: Literal["high", "medium", "low"]
    category: str = Field(description="Domain this recommendation targets")
    action: str = Field(description="Specific action to take")
    rationale: str = Field(description="Why this is recommended")
    expected_impact: str = Field(description="What improvement to expect")
    timeline: str = Field(description="When to expect results")


class DataAdequacySchema(BaseModel):
    """Data adequacy assessment for a biomarker."""

    biomarker: str
    current_samples: int
    minimum_recommended: int
    status: Literal["sufficient", "moderate", "limited", "missing"]
    reliability_score: float = Field(
        ge=0, le=1, description="Reliability score based on sample adequacy"
    )
    suggestion: Optional[str] = Field(
        None, description="Suggestion if more data needed"
    )


class HolisticInsightSchema(BaseModel):
    """Complete holistic analysis report."""

    # Metadata
    generated_at: datetime
    analysis_period_start: date
    analysis_period_end: date
    overall_confidence: Literal["high", "moderate", "low"]

    # Core results
    wellness_score: WellnessScoreSchema
    primary_findings: List[FindingSchema]

    # Advanced analysis
    interconnections: List[InterconnectionSchema]
    paradoxes: List[ParadoxSchema]
    behavioral_patterns: List[BehavioralPatternSchema]

    # Risk and recommendations
    risk_factors: List[RiskFactorSchema]
    protective_factors: List[str]
    recommendations: List[RecommendationSchema]

    # Trajectory
    trajectory: Literal["improving", "stable", "declining", "mixed"]
    trajectory_details: str

    # Data quality
    data_adequacy: List[DataAdequacySchema]


class HolisticInsightSummarySchema(BaseModel):
    """Quick summary of holistic analysis."""

    overall_score: float = Field(ge=0, le=100)
    interpretation: str
    trajectory: str

    top_strength: str
    top_concern: str

    key_recommendations: List[str] = Field(max_length=3)
    has_sufficient_data: bool
