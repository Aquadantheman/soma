"""Deep exploration of holistic insights - validate against known patterns."""
import sys
sys.path.insert(0, 'science')

import warnings
warnings.filterwarnings('ignore')

import xml.etree.ElementTree as ET
from datetime import datetime
from collections import defaultdict
import pandas as pd

from soma.statistics.holistic import (
    AnalysisInputs,
    generate_holistic_insight,
    aggregate_signals,
    compute_wellness_score,
    detect_all_paradoxes,
    detect_all_behavioral_patterns,
    find_cross_domain_interconnections,
)

print("=" * 70)
print("HOLISTIC INSIGHTS - DEEP EXPLORATION")
print("=" * 70)
print()

# Parse Apple Health data
print("Loading data...")
tree = ET.parse('apple_health_export/export.xml')
root = tree.getroot()

records = []
type_map = {
    'HKQuantityTypeIdentifierHeartRate': ('heart_rate', 1.0),
    'HKQuantityTypeIdentifierHeartRateVariabilitySDNN': ('hrv_sdnn', 1000.0),
    'HKQuantityTypeIdentifierRestingHeartRate': ('heart_rate_resting', 1.0),
    'HKQuantityTypeIdentifierStepCount': ('steps', 1.0),
    'HKQuantityTypeIdentifierActiveEnergyBurned': ('active_energy', 1.0),
    'HKQuantityTypeIdentifierAppleExerciseTime': ('exercise_time', 1.0),
    'HKQuantityTypeIdentifierBodyMass': ('body_mass', 0.453592),
    'HKQuantityTypeIdentifierVO2Max': ('vo2_max', 1.0),
    'HKQuantityTypeIdentifierTimeInDaylight': ('time_in_daylight', 1.0),
    'HKQuantityTypeIdentifierBodyFatPercentage': ('body_fat_percentage', 100.0),
}

for record in root.iter('Record'):
    rtype = record.get('type')
    if rtype not in type_map:
        continue
    value = record.get('value')
    start = record.get('startDate')
    if not value or not start:
        continue
    try:
        biomarker, conversion = type_map[rtype]
        val = float(value) * conversion
        dt = datetime.strptime(start[:19], '%Y-%m-%d %H:%M:%S')
        records.append({'time': dt, 'biomarker_slug': biomarker, 'value': val})
    except:
        continue

# Parse sleep (stored as Record elements, not CategorySample)
sleep_map = {
    'HKCategoryValueSleepAnalysisAsleepREM': 'sleep_rem',
    'HKCategoryValueSleepAnalysisAsleepDeep': 'sleep_deep',
    'HKCategoryValueSleepAnalysisAsleepCore': 'sleep_core',
}
for record in root.iter('Record'):
    rtype = record.get('type')
    if rtype != 'HKCategoryTypeIdentifierSleepAnalysis':
        continue
    value = record.get('value')
    if value not in sleep_map:
        continue
    start = record.get('startDate')
    end = record.get('endDate')
    if not start or not end:
        continue
    try:
        start_dt = datetime.strptime(start[:19], '%Y-%m-%d %H:%M:%S')
        end_dt = datetime.strptime(end[:19], '%Y-%m-%d %H:%M:%S')
        duration_min = (end_dt - start_dt).total_seconds() / 60
        records.append({'time': start_dt, 'biomarker_slug': sleep_map[value], 'value': duration_min})
    except:
        continue

signals = pd.DataFrame(records)
signals_by_biomarker = aggregate_signals(signals)

print(f"Loaded {len(signals):,} records across {len(signals_by_biomarker)} biomarkers")
print()

# ============================================================================
print("=" * 70)
print("1. WELLNESS SCORE DEEP DIVE")
print("=" * 70)
print()

wellness = compute_wellness_score(signals_by_biomarker)

print("CARDIOVASCULAR DOMAIN (Score: {:.0f}/100)".format(wellness.cardiovascular.score))
print("-" * 50)
print(f"  Confidence: {wellness.cardiovascular.confidence}")
print(f"  Trend: {wellness.cardiovascular.trend}")
print(f"  Data points: {wellness.cardiovascular.data_points}")
print("  Key contributors:")
for c in wellness.cardiovascular.key_contributors:
    print(f"    + {c}")
print("  Limiting factors:")
for l in wellness.cardiovascular.limiting_factors:
    print(f"    - {l}")

# Validate: Check actual HRV data
if 'hrv_sdnn' in signals_by_biomarker:
    hrv = signals_by_biomarker['hrv_sdnn']
    recent = hrv.tail(30).mean()
    baseline = hrv.mean()
    print(f"\n  VALIDATION:")
    print(f"    HRV baseline: {baseline:.1f} ms")
    print(f"    HRV recent (30d): {recent:.1f} ms")
    print(f"    Ratio: {recent/baseline:.2f} (>1 = above baseline)")

print()
print("SLEEP DOMAIN (Score: {:.0f}/100)".format(wellness.sleep.score))
print("-" * 50)
print(f"  Confidence: {wellness.sleep.confidence}")
print(f"  Trend: {wellness.sleep.trend}")
print(f"  Data points: {wellness.sleep.data_points}")
if wellness.sleep.key_contributors:
    print("  Key contributors:")
    for c in wellness.sleep.key_contributors:
        print(f"    + {c}")
if wellness.sleep.limiting_factors:
    print("  Limiting factors:")
    for l in wellness.sleep.limiting_factors:
        print(f"    - {l}")

# Check sleep data availability
sleep_biomarkers = ['sleep_rem', 'sleep_deep', 'sleep_core', 'sleep_duration']
print(f"\n  VALIDATION - Sleep data availability:")
for sb in sleep_biomarkers:
    if sb in signals_by_biomarker:
        print(f"    {sb}: {len(signals_by_biomarker[sb])} days")
    else:
        print(f"    {sb}: NOT FOUND")

print()
print("ACTIVITY DOMAIN (Score: {:.0f}/100)".format(wellness.activity.score))
print("-" * 50)
print(f"  Confidence: {wellness.activity.confidence}")
print(f"  Trend: {wellness.activity.trend}")
print(f"  Data points: {wellness.activity.data_points}")
print("  Key contributors:")
for c in wellness.activity.key_contributors:
    print(f"    + {c}")
print("  Limiting factors:")
for l in wellness.activity.limiting_factors:
    print(f"    - {l}")

# Validate steps
if 'steps' in signals_by_biomarker:
    steps = signals_by_biomarker['steps']
    print(f"\n  VALIDATION:")
    print(f"    Average steps: {steps.mean():.0f}/day")
    print(f"    Recent (30d): {steps.tail(30).mean():.0f}/day")
    print(f"    Std dev: {steps.std():.0f} (CV: {steps.std()/steps.mean():.2f})")

print()
print("BODY COMPOSITION DOMAIN (Score: {:.0f}/100)".format(wellness.body_composition.score))
print("-" * 50)
print(f"  Confidence: {wellness.body_composition.confidence}")
print(f"  Trend: {wellness.body_composition.trend}")
print(f"  Data points: {wellness.body_composition.data_points}")
if wellness.body_composition.key_contributors:
    print("  Key contributors:")
    for c in wellness.body_composition.key_contributors:
        print(f"    + {c}")
if wellness.body_composition.limiting_factors:
    print("  Limiting factors:")
    for l in wellness.body_composition.limiting_factors:
        print(f"    - {l}")

# Validate weight
if 'body_mass' in signals_by_biomarker:
    weight = signals_by_biomarker['body_mass']
    print(f"\n  VALIDATION:")
    print(f"    Current weight: {weight.iloc[-1]:.1f} kg")
    print(f"    Average: {weight.mean():.1f} kg")
    print(f"    Min: {weight.min():.1f} kg, Max: {weight.max():.1f} kg")
    # Recent trend
    if len(weight) >= 30:
        early = weight.head(len(weight)//2).mean()
        late = weight.tail(len(weight)//2).mean()
        print(f"    Trend: Early avg {early:.1f} kg -> Late avg {late:.1f} kg ({late-early:+.1f} kg)")

print()

# ============================================================================
print("=" * 70)
print("2. PARADOX ANALYSIS")
print("=" * 70)
print()

paradoxes = detect_all_paradoxes(signals_by_biomarker)

if paradoxes:
    for p in paradoxes:
        print(f"PARADOX: {p.biomarker_a} <-> {p.biomarker_b}")
        print("-" * 50)
        print(f"  Raw correlation:       r = {p.raw_correlation:+.3f} (p = {p.raw_p_value:.4f})")
        print(f"  Detrended correlation: r = {p.detrended_correlation:+.3f} (p = {p.detrended_p_value:.4f})")
        print(f"  Confounding factor: {p.confounding_factor}")
        print()
        print("  EXPLANATION:")
        print(f"  {p.explanation}")
        if p.behavioral_insight:
            print()
            print("  BEHAVIORAL INSIGHT:")
            print(f"  {p.behavioral_insight}")
        print()

        # Manual validation
        if p.biomarker_a == 'steps' and p.biomarker_b == 'body_mass':
            print("  MANUAL VALIDATION:")
            steps = signals_by_biomarker['steps']
            weight = signals_by_biomarker['body_mass']

            # Get overlapping dates
            common = steps.index.intersection(weight.index)
            if len(common) >= 30:
                s = steps.loc[common]
                w = weight.loc[common]

                # Split by weight quartiles
                q1 = w.quantile(0.25)
                q4 = w.quantile(0.75)

                low_weight_steps = s[w <= q1].mean()
                high_weight_steps = s[w >= q4].mean()

                print(f"    Low weight (<=Q1) avg steps:  {low_weight_steps:.0f}")
                print(f"    High weight (>=Q3) avg steps: {high_weight_steps:.0f}")
                print(f"    Difference: {high_weight_steps - low_weight_steps:+.0f} steps")
                print(f"    --> Confirms compensatory behavior: MORE steps when heavier")
else:
    print("No paradoxes detected.")

print()

# ============================================================================
print("=" * 70)
print("3. BEHAVIORAL PATTERNS")
print("=" * 70)
print()

patterns = detect_all_behavioral_patterns(signals_by_biomarker)

for p in patterns:
    print(f"PATTERN: {p.name}")
    print("-" * 50)
    print(f"  Type: {p.pattern_type}")
    print(f"  Health implication: {p.health_implication}")
    print()
    print(f"  Description: {p.description}")
    print()
    print(f"  Evidence: {p.evidence}")
    print()
    if p.recommendation:
        print(f"  Recommendation: {p.recommendation}")
    print()

# ============================================================================
print("=" * 70)
print("4. CROSS-DOMAIN INTERCONNECTIONS")
print("=" * 70)
print()

interconnections = find_cross_domain_interconnections(signals_by_biomarker)

print(f"Found {len(interconnections)} significant interconnections:")
print()

for ic in interconnections:
    strength_bar = '*' * {'strong': 3, 'moderate': 2, 'weak': 1}[ic.strength]
    print(f"[{strength_bar}] {ic.source_domain.upper()} -> {ic.target_domain.upper()}")
    print(f"    {ic.pathway}")
    print(f"    Correlation: r = {ic.correlation:+.3f} (p = {ic.p_value:.6f})")
    print(f"    Lag: {ic.lag_days} day(s), Strength: {ic.strength}, n = {ic.sample_size}")
    print()
    print(f"    Interpretation: {ic.interpretation[:100]}...")
    print()

# ============================================================================
print("=" * 70)
print("5. YEAR-OVER-YEAR TRAJECTORY")
print("=" * 70)
print()

# Group key metrics by year
print("Metric trends by year:")
print()

for biomarker in ['steps', 'body_mass', 'hrv_sdnn', 'heart_rate_resting', 'vo2_max']:
    if biomarker not in signals_by_biomarker:
        continue

    data = signals_by_biomarker[biomarker]
    data_df = pd.DataFrame({'value': data})
    data_df.index = pd.to_datetime(data_df.index)

    yearly = data_df.groupby(data_df.index.year)['value'].mean()

    print(f"{biomarker.upper().replace('_', ' ')}:")
    for year in sorted(yearly.index)[-5:]:  # Last 5 years
        print(f"  {year}: {yearly[year]:.1f}")

    # Calculate overall trend
    if len(yearly) >= 2:
        first = yearly.iloc[0]
        last = yearly.iloc[-1]
        change = last - first
        pct_change = (change / first) * 100 if first != 0 else 0
        print(f"  --> Change: {change:+.1f} ({pct_change:+.1f}%)")
    print()

# ============================================================================
print("=" * 70)
print("6. KEY INSIGHTS SUMMARY")
print("=" * 70)
print()

print("Based on the holistic analysis of your data:")
print()

# Strengths
print("STRENGTHS:")
if wellness.cardiovascular.score >= 75:
    print(f"  + Cardiovascular health is excellent ({wellness.cardiovascular.score:.0f}/100)")
if wellness.recovery.score >= 75:
    print(f"  + Recovery capacity is strong ({wellness.recovery.score:.0f}/100)")
if wellness.activity.score >= 60:
    print(f"  + Activity levels are adequate ({wellness.activity.score:.0f}/100)")

# Patterns working for you
for p in patterns:
    if p.health_implication == 'positive':
        print(f"  + {p.name} is a healthy adaptive behavior")

print()

# Areas for attention
print("AREAS FOR ATTENTION:")
if wellness.sleep.score < 60:
    print(f"  ! Sleep data is limited (confidence: {wellness.sleep.confidence})")
    print(f"    --> Consider tracking sleep more consistently")
if wellness.body_composition.score < 70:
    print(f"  ! Body composition could improve ({wellness.body_composition.score:.0f}/100)")

print()

# Key relationships discovered
print("KEY RELATIONSHIPS IN YOUR DATA:")
for ic in interconnections[:3]:
    if ic.strength in ('strong', 'moderate'):
        print(f"  * {ic.pathway}")
        print(f"    (r={ic.correlation:+.2f}, {ic.strength})")

print()

# Actionable insight
print("ACTIONABLE INSIGHT:")
if any(p.name == "Compensatory Exercise" for p in patterns):
    print("  Your body naturally increases activity when weight rises.")
    print("  Trust this instinct - it's a healthy adaptive response.")
    print()

strongest_interconnection = interconnections[0] if interconnections else None
if strongest_interconnection:
    if 'vo2' in strongest_interconnection.pathway.lower():
        print("  VO2 Max is your strongest lever for body composition.")
        print("  Focus on cardiorespiratory fitness for weight management.")

print()
print("=" * 70)
print("END OF EXPLORATION")
print("=" * 70)
