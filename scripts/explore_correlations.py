"""Explore unexpected correlations across all biomarkers."""
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

print('Loading data...')
tree = ET.parse('apple_health_export/export.xml')
root = tree.getroot()

biomarker_types = {
    'HKQuantityTypeIdentifierHeartRate': ('heart_rate', 1),
    'HKQuantityTypeIdentifierRestingHeartRate': ('resting_hr', 1),
    'HKQuantityTypeIdentifierHeartRateVariabilitySDNN': ('hrv', 1),
    'HKQuantityTypeIdentifierVO2Max': ('vo2_max', 1),
    'HKQuantityTypeIdentifierOxygenSaturation': ('spo2', 100),
    'HKQuantityTypeIdentifierStepCount': ('steps', 1),
    'HKQuantityTypeIdentifierActiveEnergyBurned': ('active_energy', 1),
    'HKQuantityTypeIdentifierAppleExerciseTime': ('exercise_time', 1),
    'HKQuantityTypeIdentifierFlightsClimbed': ('flights', 1),
    'HKQuantityTypeIdentifierDistanceWalkingRunning': ('distance', 1),
    'HKQuantityTypeIdentifierAppleStandTime': ('stand_time', 1),
    'HKQuantityTypeIdentifierRespiratoryRate': ('resp_rate', 1),
    'HKQuantityTypeIdentifierBodyMass': ('weight', 1),
    'HKQuantityTypeIdentifierBodyFatPercentage': ('body_fat', 100),
    'HKQuantityTypeIdentifierTimeInDaylight': ('daylight', 1),
    'HKQuantityTypeIdentifierHeadphoneAudioExposure': ('audio_db', 1),
    'HKQuantityTypeIdentifierWalkingSpeed': ('walking_speed', 3.6),
    'HKQuantityTypeIdentifierWalkingStepLength': ('step_length', 100),
    'HKQuantityTypeIdentifierWalkingDoubleSupportPercentage': ('double_support', 100),
    'HKQuantityTypeIdentifierStairAscentSpeed': ('stair_up', 1),
}

all_data = defaultdict(list)
for record in root.iter('Record'):
    rec_type = record.get('type')
    if rec_type in biomarker_types:
        try:
            slug, mult = biomarker_types[rec_type]
            dt = datetime.fromisoformat(record.get('startDate').replace(' ', 'T')[:19])
            val = float(record.get('value')) * mult
            all_data[slug].append({'time': dt, 'value': val})
        except:
            pass

# Sleep data
for record in root.iter('Record'):
    if record.get('type') == 'HKCategoryTypeIdentifierSleepAnalysis':
        try:
            start = datetime.fromisoformat(record.get('startDate').replace(' ', 'T')[:19])
            end = datetime.fromisoformat(record.get('endDate').replace(' ', 'T')[:19])
            duration = (end - start).total_seconds() / 3600
            sleep_value = record.get('value', '')
            if 'InBed' not in sleep_value and duration > 0:
                if 'REM' in sleep_value:
                    all_data['sleep_rem'].append({'time': end, 'value': duration})
                elif 'Deep' in sleep_value:
                    all_data['sleep_deep'].append({'time': end, 'value': duration})
                elif 'Core' in sleep_value or 'Asleep' in sleep_value:
                    all_data['sleep_core'].append({'time': end, 'value': duration})
        except:
            pass

# Aggregate to daily
daily_data = {}
sum_biomarkers = ['steps', 'active_energy', 'exercise_time', 'flights', 'distance',
                   'stand_time', 'daylight', 'sleep_rem', 'sleep_deep', 'sleep_core']

for slug, records in all_data.items():
    if len(records) < 30:
        continue
    df = pd.DataFrame(records)
    df['date'] = pd.to_datetime(df['time']).dt.date
    if slug in sum_biomarkers:
        daily = df.groupby('date')['value'].sum()
    else:
        daily = df.groupby('date')['value'].mean()
    daily_data[slug] = daily

# Calculate total sleep
if 'sleep_rem' in daily_data and 'sleep_deep' in daily_data and 'sleep_core' in daily_data:
    common_dates = daily_data['sleep_rem'].index.intersection(
        daily_data['sleep_deep'].index
    ).intersection(daily_data['sleep_core'].index)
    if len(common_dates) > 0:
        total_sleep = (daily_data['sleep_rem'].loc[common_dates] +
                       daily_data['sleep_deep'].loc[common_dates] +
                       daily_data['sleep_core'].loc[common_dates])
        daily_data['total_sleep'] = total_sleep

print('=' * 75)
print('UNEXPECTED CORRELATIONS ANALYSIS')
print('=' * 75)

# Compute all pairwise correlations
correlations = []
biomarkers = list(daily_data.keys())

for i, bio1 in enumerate(biomarkers):
    for bio2 in biomarkers[i+1:]:
        s1 = daily_data[bio1]
        s2 = daily_data[bio2]
        common = s1.index.intersection(s2.index)

        if len(common) >= 30:
            x = s1.loc[common].values
            y = s2.loc[common].values

            mask = ~(np.isnan(x) | np.isnan(y))
            if mask.sum() >= 30:
                r, p = stats.pearsonr(x[mask], y[mask])
                correlations.append({
                    'bio1': bio1,
                    'bio2': bio2,
                    'r': r,
                    'p': p,
                    'n': mask.sum(),
                    'abs_r': abs(r)
                })

correlations.sort(key=lambda x: -x['abs_r'])

# Define expected relationships
expected_pairs = {
    ('steps', 'active_energy'), ('steps', 'distance'), ('active_energy', 'distance'),
    ('exercise_time', 'active_energy'), ('exercise_time', 'steps'),
    ('hrv', 'resting_hr'),
    ('weight', 'body_fat'),
    ('walking_speed', 'step_length'),
    ('sleep_rem', 'sleep_deep'), ('sleep_rem', 'sleep_core'), ('sleep_deep', 'sleep_core'),
    ('sleep_rem', 'total_sleep'), ('sleep_deep', 'total_sleep'), ('sleep_core', 'total_sleep'),
    ('vo2_max', 'resting_hr'),
    ('steps', 'flights'), ('distance', 'flights'),
    ('exercise_time', 'distance'), ('exercise_time', 'flights'),
    ('active_energy', 'flights'),
    ('walking_speed', 'double_support'),
    ('step_length', 'double_support'),
}

def is_expected(bio1, bio2):
    return (bio1, bio2) in expected_pairs or (bio2, bio1) in expected_pairs

print('\nTOP 30 STRONGEST CORRELATIONS:')
print('-' * 75)
print(f"{'Biomarker 1':<18} {'Biomarker 2':<18} {'r':>8} {'p-value':>12} {'n':>6} {'Expected?':>10}")
print('-' * 75)

for c in correlations[:30]:
    expected = 'Yes' if is_expected(c['bio1'], c['bio2']) else 'NO'
    sig = '***' if c['p'] < 0.001 else ('**' if c['p'] < 0.01 else ('*' if c['p'] < 0.05 else ''))
    print(f"{c['bio1']:<18} {c['bio2']:<18} {c['r']:>+8.3f} {c['p']:>11.2e}{sig} {c['n']:>6} {expected:>10}")

print('\n' + '=' * 75)
print('UNEXPECTED STRONG CORRELATIONS (|r| > 0.25, not obvious):')
print('=' * 75)

unexpected = [c for c in correlations
              if c['abs_r'] > 0.25
              and c['p'] < 0.05
              and not is_expected(c['bio1'], c['bio2'])]

for c in unexpected[:25]:
    direction = 'positive' if c['r'] > 0 else 'NEGATIVE'
    print(f"\n{c['bio1']} <-> {c['bio2']}")
    print(f"  r = {c['r']:+.3f} ({direction}), p = {c['p']:.2e}, n = {c['n']}")

# Now look at lagged correlations for interesting pairs
print('\n' + '=' * 75)
print('LAGGED CORRELATIONS (Does X today predict Y tomorrow?)')
print('=' * 75)

def lagged_correlation(s1, s2, lag_days):
    """Compute correlation between s1 and s2 shifted by lag_days."""
    # s1 at time t correlates with s2 at time t+lag
    s1_df = pd.DataFrame({'date': s1.index, 'value': s1.values})
    s2_df = pd.DataFrame({'date': s2.index, 'value': s2.values})

    s1_df['date'] = pd.to_datetime(s1_df['date'])
    s2_df['date'] = pd.to_datetime(s2_df['date'])

    # Shift s2 back by lag days (so we're looking at s1 -> future s2)
    s2_df['date_shifted'] = s2_df['date'] - pd.Timedelta(days=lag_days)

    merged = s1_df.merge(s2_df, left_on='date', right_on='date_shifted', suffixes=('_1', '_2'))

    if len(merged) >= 30:
        r, p = stats.pearsonr(merged['value_1'], merged['value_2'])
        return r, p, len(merged)
    return np.nan, np.nan, 0

# Test interesting lagged relationships
lagged_tests = [
    # Activity today -> Recovery tomorrow?
    ('steps', 'hrv', 1, "Steps today -> HRV tomorrow"),
    ('active_energy', 'hrv', 1, "Active energy today -> HRV tomorrow"),
    ('exercise_time', 'hrv', 1, "Exercise today -> HRV tomorrow"),

    # Sleep tonight -> Activity tomorrow?
    ('total_sleep', 'steps', 1, "Sleep -> Steps next day"),
    ('total_sleep', 'active_energy', 1, "Sleep -> Active energy next day"),
    ('sleep_deep', 'hrv', 1, "Deep sleep -> HRV next day"),

    # Activity -> Sleep that night?
    ('steps', 'total_sleep', 0, "Steps -> Sleep same night"),
    ('steps', 'sleep_deep', 0, "Steps -> Deep sleep same night"),
    ('daylight', 'total_sleep', 0, "Daylight -> Sleep same night"),

    # Weight lagged effects
    ('steps', 'weight', 7, "Steps -> Weight 1 week later"),
    ('active_energy', 'weight', 7, "Active energy -> Weight 1 week later"),

    # Audio -> next day effects?
    ('audio_db', 'hrv', 1, "Audio exposure -> HRV next day"),
    ('audio_db', 'total_sleep', 0, "Audio exposure -> Sleep same night"),

    # SpO2 relationships
    ('spo2', 'hrv', 1, "SpO2 -> HRV next day"),
    ('total_sleep', 'spo2', 1, "Sleep -> SpO2 next day"),
]

print("\nTesting lagged relationships:")
print("-" * 75)

significant_lags = []
for bio1, bio2, lag, desc in lagged_tests:
    if bio1 in daily_data and bio2 in daily_data:
        r, p, n = lagged_correlation(daily_data[bio1], daily_data[bio2], lag)
        if not np.isnan(r) and p < 0.1:  # Include marginally significant
            significant_lags.append((desc, r, p, n))
            sig = '***' if p < 0.001 else ('**' if p < 0.01 else ('*' if p < 0.05 else '+'))
            print(f"\n{desc}")
            print(f"  r = {r:+.3f}, p = {p:.3f}{sig}, n = {n}")

print('\n' + '=' * 75)
print('SUMMARY OF INTERESTING FINDINGS')
print('=' * 75)
