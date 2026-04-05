"""Pydantic schemas for API request/response validation.

Organized by domain:
- base: Core entities (signals, biomarkers, baselines, annotations)
- proven: Statistically proven analysis results
- advanced: Cross-correlations, recovery, seasonality, readiness
- stability: Data quality and reliability assessment
- derived: Compound metrics from multiple biomarkers
"""

# Base schemas
from .base import (
    BiomarkerType,
    DataSource,
    Signal,
    SignalCreate,
    SignalQuery,
    Baseline,
    BaselineCompute,
    DeviationCheck,
    DeviationResult,
    Annotation,
    AnnotationCreate,
    IngestRun,
    SystemStatus,
    ConfidenceIntervalSchema,
)

# Proven analysis schemas
from .proven import (
    HourlyPatternSchema,
    CircadianAnalysis,
    DayPatternSchema,
    WeeklyActivityAnalysis,
    YearlyStatSchema,
    TrendAnalysis,
    AnomalyDaySchema,
    AnomalyAnalysis,
    HRVAnalysis,
    SpO2Analysis,
    FullAnalysisResult,
)

# Advanced analysis schemas
from .advanced import (
    CorrelationPairSchema,
    CorrelationMatrixAnalysis,
    LaggedCorrelationSchema,
    RecoveryAnalysis,
    SeasonalComponentSchema,
    SeasonalAnalysisSchema,
    ReadinessScoreSchema,
    ReadinessModelSchema,
    ReadinessSummary,
    AdvancedAnalysisResult,
)

# Stability analysis schemas
from .stability import (
    ConvergencePointSchema,
    ConvergenceAnalysisSchema,
    TemporalStabilitySchema,
    DriftResultSchema,
    SampleAdequacySchema,
    StabilityReportSchema,
)

# Derived metrics schemas
from .derived import (
    NocturnalDipSchema,
    TrainingLoadSchema,
    AutonomicBalanceSchema,
    StressIndexSchema,
    BehavioralRegularitySchema,
    CardiovascularEfficiencySchema,
    StrainIndexSchema,
    RecoveryTrendSchema,
    CircadianAmplitudeSchema,
    EnergyDistributionSchema,
    NightRestlessnessSchema,
    PhysiologicalCoherenceSchema,
    DerivedMetricsReportSchema,
)

# Sleep architecture schemas
from .sleep import (
    NightlySleepSchema,
    SleepArchitectureBaselineSchema,
    SleepArchitectureDeviationSchema,
    SleepArchitectureTrendSchema,
    SleepArchitectureReportSchema,
    SleepSummary,
)

# Daylight analysis schemas
from .daylight import (
    DailyDaylightSchema,
    DaylightBaselineSchema,
    DaylightDeviationSchema,
    DaylightTrendSchema,
    DaylightSleepCorrelationSchema,
    DaylightReportSchema,
    DaylightSummary,
)

# VO2 Max analysis schemas
from .vo2max import (
    VO2MaxMeasurementSchema,
    VO2MaxPercentileSchema,
    FitnessAgeSchema,
    VO2MaxTrendSchema,
    MortalityRiskSchema,
    TrainingResponseSchema,
    CorrelationSchema,
    VO2MaxReportSchema,
    VO2MaxSummarySchema,
)

# Body Composition analysis schemas
from .body_composition import (
    BMISchema,
    BodyFatPercentileSchema,
    WeightMeasurementSchema,
    WeightTrendSchema,
    BodyCompositionChangeSchema,
    FitnessCorrelationSchema,
    BodyCompositionReportSchema,
    BodyCompositionSummarySchema,
)

# Holistic insights schemas
from .holistic import (
    DomainScoreSchema,
    WellnessScoreSchema,
    FindingSchema,
    InterconnectionSchema,
    ParadoxSchema,
    BehavioralPatternSchema,
    RiskFactorSchema,
    RecommendationSchema,
    DataAdequacySchema,
    HolisticInsightSchema,
    HolisticInsightSummarySchema,
)

__all__ = [
    # Base
    "BiomarkerType",
    "DataSource",
    "Signal",
    "SignalCreate",
    "SignalQuery",
    "Baseline",
    "BaselineCompute",
    "DeviationCheck",
    "DeviationResult",
    "Annotation",
    "AnnotationCreate",
    "IngestRun",
    "SystemStatus",
    "ConfidenceIntervalSchema",
    # Proven
    "HourlyPatternSchema",
    "CircadianAnalysis",
    "DayPatternSchema",
    "WeeklyActivityAnalysis",
    "YearlyStatSchema",
    "TrendAnalysis",
    "AnomalyDaySchema",
    "AnomalyAnalysis",
    "HRVAnalysis",
    "SpO2Analysis",
    "FullAnalysisResult",
    # Advanced
    "CorrelationPairSchema",
    "CorrelationMatrixAnalysis",
    "LaggedCorrelationSchema",
    "RecoveryAnalysis",
    "SeasonalComponentSchema",
    "SeasonalAnalysisSchema",
    "ReadinessScoreSchema",
    "ReadinessModelSchema",
    "ReadinessSummary",
    "AdvancedAnalysisResult",
    # Stability
    "ConvergencePointSchema",
    "ConvergenceAnalysisSchema",
    "TemporalStabilitySchema",
    "DriftResultSchema",
    "SampleAdequacySchema",
    "StabilityReportSchema",
    # Derived
    "NocturnalDipSchema",
    "TrainingLoadSchema",
    "AutonomicBalanceSchema",
    "StressIndexSchema",
    "BehavioralRegularitySchema",
    "CardiovascularEfficiencySchema",
    "StrainIndexSchema",
    "RecoveryTrendSchema",
    "CircadianAmplitudeSchema",
    "EnergyDistributionSchema",
    "NightRestlessnessSchema",
    "PhysiologicalCoherenceSchema",
    "DerivedMetricsReportSchema",
    # Sleep architecture
    "NightlySleepSchema",
    "SleepArchitectureBaselineSchema",
    "SleepArchitectureDeviationSchema",
    "SleepArchitectureTrendSchema",
    "SleepArchitectureReportSchema",
    "SleepSummary",
    # Daylight analysis
    "DailyDaylightSchema",
    "DaylightBaselineSchema",
    "DaylightDeviationSchema",
    "DaylightTrendSchema",
    "DaylightSleepCorrelationSchema",
    "DaylightReportSchema",
    "DaylightSummary",
    # VO2 Max analysis
    "VO2MaxMeasurementSchema",
    "VO2MaxPercentileSchema",
    "FitnessAgeSchema",
    "VO2MaxTrendSchema",
    "MortalityRiskSchema",
    "TrainingResponseSchema",
    "CorrelationSchema",
    "VO2MaxReportSchema",
    "VO2MaxSummarySchema",
    # Body Composition analysis
    "BMISchema",
    "BodyFatPercentileSchema",
    "WeightMeasurementSchema",
    "WeightTrendSchema",
    "BodyCompositionChangeSchema",
    "FitnessCorrelationSchema",
    "BodyCompositionReportSchema",
    "BodyCompositionSummarySchema",
    # Holistic insights
    "DomainScoreSchema",
    "WellnessScoreSchema",
    "FindingSchema",
    "InterconnectionSchema",
    "ParadoxSchema",
    "BehavioralPatternSchema",
    "RiskFactorSchema",
    "RecommendationSchema",
    "DataAdequacySchema",
    "HolisticInsightSchema",
    "HolisticInsightSummarySchema",
]
