"""Test holistic insights with real Apple Health data."""
import sys
sys.path.insert(0, 'science')

import xml.etree.ElementTree as ET
from datetime import datetime
from collections import defaultdict
import pandas as pd

from soma.statistics.holistic import (
    AnalysisInputs,
    generate_holistic_insight,
)

print("HOLISTIC INSIGHTS MODULE - LIVE TEST")
print("=" * 60)
print()

# Parse Apple Health data into signals DataFrame
print("Loading Apple Health data...")
tree = ET.parse('apple_health_export/export.xml')
root = tree.getroot()

records = []

# Map Apple Health types to Soma biomarkers
type_map = {
    'HKQuantityTypeIdentifierHeartRate': ('heart_rate', 1.0),
    'HKQuantityTypeIdentifierHeartRateVariabilitySDNN': ('hrv_sdnn', 1000.0),
    'HKQuantityTypeIdentifierRestingHeartRate': ('heart_rate_resting', 1.0),
    'HKQuantityTypeIdentifierStepCount': ('steps', 1.0),
    'HKQuantityTypeIdentifierActiveEnergyBurned': ('active_energy', 1.0),
    'HKQuantityTypeIdentifierAppleExerciseTime': ('exercise_time', 1.0),
    'HKQuantityTypeIdentifierBodyMass': ('body_mass', 0.453592),  # lb -> kg
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

        records.append({
            'time': dt,
            'biomarker_slug': biomarker,
            'value': val,
        })
    except:
        continue

# Parse sleep data (stored as Record elements, not CategorySample)
sleep_type_map = {
    'HKCategoryValueSleepAnalysisAsleepREM': 'sleep_rem',
    'HKCategoryValueSleepAnalysisAsleepDeep': 'sleep_deep',
    'HKCategoryValueSleepAnalysisAsleepCore': 'sleep_core',
}

for record in root.iter('Record'):
    rtype = record.get('type')
    if rtype != 'HKCategoryTypeIdentifierSleepAnalysis':
        continue

    value = record.get('value')
    if value not in sleep_type_map:
        continue

    start = record.get('startDate')
    end = record.get('endDate')

    if not start or not end:
        continue

    try:
        start_dt = datetime.strptime(start[:19], '%Y-%m-%d %H:%M:%S')
        end_dt = datetime.strptime(end[:19], '%Y-%m-%d %H:%M:%S')
        duration_min = (end_dt - start_dt).total_seconds() / 60

        records.append({
            'time': start_dt,
            'biomarker_slug': sleep_type_map[value],
            'value': duration_min,
        })
    except:
        continue

# Create DataFrame
signals = pd.DataFrame(records)
print(f"Loaded {len(signals):,} signal records")
print(f"Biomarkers: {signals['biomarker_slug'].nunique()}")
print()

# Create inputs
inputs = AnalysisInputs(
    signals=signals,
    user_age=35,  # Approximate
    user_sex='male',
)

# Generate holistic insight
print("Generating holistic insight...")
print()

insight = generate_holistic_insight(inputs)

# Display results
print("=" * 60)
print("HOLISTIC INSIGHT REPORT")
print("=" * 60)
print()

print(f"Analysis Period: {insight.analysis_period_start} to {insight.analysis_period_end}")
print(f"Overall Confidence: {insight.overall_confidence}")
print(f"Trajectory: {insight.trajectory} - {insight.trajectory_details}")
print()

print("-" * 60)
print("WELLNESS SCORE")
print("-" * 60)
ws = insight.wellness_score
print(f"  OVERALL: {ws.overall:.0f}/100 ({ws.interpretation})")
print()
print(f"  Cardiovascular:    {ws.cardiovascular.score:.0f}/100 ({ws.cardiovascular.confidence} confidence, {ws.cardiovascular.trend})")
print(f"  Sleep:             {ws.sleep.score:.0f}/100 ({ws.sleep.confidence} confidence, {ws.sleep.trend})")
print(f"  Activity:          {ws.activity.score:.0f}/100 ({ws.activity.confidence} confidence, {ws.activity.trend})")
print(f"  Recovery:          {ws.recovery.score:.0f}/100 ({ws.recovery.confidence} confidence, {ws.recovery.trend})")
print(f"  Body Composition:  {ws.body_composition.score:.0f}/100 ({ws.body_composition.confidence} confidence, {ws.body_composition.trend})")
print()
print(f"  Strongest domain: {ws.strongest_domain}")
print(f"  Weakest domain:   {ws.weakest_domain}")
print()

print("-" * 60)
print("PRIMARY FINDINGS")
print("-" * 60)
for i, finding in enumerate(insight.primary_findings, 1):
    severity_icon = {'positive': '+', 'neutral': '~', 'concern': '!', 'warning': '!!'}[finding.severity]
    print(f"  [{severity_icon}] {finding.title}")
    print(f"      {finding.description[:80]}...")
print()

print("-" * 60)
print("PARADOXES DETECTED")
print("-" * 60)
if insight.paradoxes:
    for paradox in insight.paradoxes:
        print(f"  {paradox.name}: {paradox.biomarker_a} <-> {paradox.biomarker_b}")
        print(f"    Raw r={paradox.raw_correlation:.3f}, Detrended r={paradox.detrended_correlation:.3f}")
        if paradox.behavioral_insight:
            print(f"    Insight: {paradox.behavioral_insight[:60]}...")
else:
    print("  None detected")
print()

print("-" * 60)
print("BEHAVIORAL PATTERNS")
print("-" * 60)
if insight.behavioral_patterns:
    for pattern in insight.behavioral_patterns:
        health_icon = {'positive': '+', 'neutral': '~', 'negative': '-'}[pattern.health_implication]
        print(f"  [{health_icon}] {pattern.name}")
        print(f"      {pattern.description[:70]}...")
else:
    print("  None detected")
print()

print("-" * 60)
print("CROSS-DOMAIN INTERCONNECTIONS")
print("-" * 60)
for ic in insight.interconnections[:5]:  # Top 5
    print(f"  {ic.source_domain} -> {ic.target_domain}")
    print(f"    {ic.pathway}")
    print(f"    r={ic.correlation:.2f}, p={ic.p_value:.4f}, lag={ic.lag_days} days")
print()

print("-" * 60)
print("RISK FACTORS")
print("-" * 60)
if insight.risk_factors:
    for rf in insight.risk_factors:
        level_icon = {'low': '-', 'moderate': '!', 'elevated': '!!', 'high': '!!!'}[rf.level]
        print(f"  [{level_icon}] {rf.name} ({rf.level})")
        print(f"      Contributing: {', '.join(rf.contributing_factors[:2])}")
else:
    print("  No significant risk factors identified")
print()

print("-" * 60)
print("PROTECTIVE FACTORS")
print("-" * 60)
if insight.protective_factors:
    for pf in insight.protective_factors[:5]:
        print(f"  + {pf}")
else:
    print("  None identified (may need more data)")
print()

print("-" * 60)
print("RECOMMENDATIONS")
print("-" * 60)
if insight.recommendations:
    for i, rec in enumerate(insight.recommendations, 1):
        priority_icon = {'high': '***', 'medium': '**', 'low': '*'}[rec.priority]
        print(f"  {i}. [{priority_icon}] {rec.action[:60]}...")
        print(f"       Category: {rec.category} | Timeline: {rec.timeline}")
else:
    print("  No specific recommendations (all domains healthy)")
print()

print("-" * 60)
print("DATA ADEQUACY")
print("-" * 60)
for da in sorted(insight.data_adequacy, key=lambda x: x.reliability_score, reverse=True)[:8]:
    status_icon = {'sufficient': '+', 'moderate': '~', 'limited': '-', 'missing': 'X'}[da.status]
    print(f"  [{status_icon}] {da.biomarker}: {da.current_samples} samples ({da.status})")
print()

print("=" * 60)
print("END OF REPORT")
print("=" * 60)
