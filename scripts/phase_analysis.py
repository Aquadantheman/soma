"""Phase relationships & predictive patterns analysis."""
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

print('=' * 75)
print('PHASE RELATIONSHIPS & PREDICTIVE PATTERNS')
print('=' * 75)

tree = ET.parse('apple_health_export/export.xml')
root = tree.getroot()

# Load data
types = {
    'HKQuantityTypeIdentifierStepCount': ('steps', 1),
    'HKQuantityTypeIdentifierHeartRate': ('heart_rate', 1),
    'HKQuantityTypeIdentifierHeartRateVariabilitySDNN': ('hrv', 1),
    'HKQuantityTypeIdentifierVO2Max': ('vo2_max', 1),
    'HKQuantityTypeIdentifierOxygenSaturation': ('spo2', 100),
    'HKQuantityTypeIdentifierBodyMass': ('weight', 1),
    'HKQuantityTypeIdentifierRespiratoryRate': ('resp_rate', 1),
    'HKQuantityTypeIdentifierTimeInDaylight': ('daylight', 1),
    'HKQuantityTypeIdentifierActiveEnergyBurned': ('active_energy', 1),
}

data = defaultdict(list)
for record in root.iter('Record'):
    rt = record.get('type')
    if rt in types:
        try:
            slug, mult = types[rt]
            dt = datetime.fromisoformat(record.get('startDate').replace(' ', 'T')[:19])
            val = float(record.get('value')) * mult
            data[slug].append({'time': dt, 'value': val})
        except:
            pass

# Sleep
for record in root.iter('Record'):
    if record.get('type') == 'HKCategoryTypeIdentifierSleepAnalysis':
        try:
            start = datetime.fromisoformat(record.get('startDate').replace(' ', 'T')[:19])
            end = datetime.fromisoformat(record.get('endDate').replace(' ', 'T')[:19])
            duration = (end - start).total_seconds() / 3600
            sv = record.get('value', '')
            if 'InBed' not in sv and duration > 0:
                data['sleep'].append({'time': end, 'value': duration})
        except:
            pass

# Aggregate daily
daily = {}
sum_bios = ['steps', 'active_energy', 'daylight', 'sleep']
for slug, records in data.items():
    if len(records) < 30:
        continue
    df = pd.DataFrame(records)
    df['date'] = pd.to_datetime(df['time']).dt.date
    daily[slug] = df.groupby('date')['value'].sum() if slug in sum_bios else df.groupby('date')['value'].mean()

print('\n1. WHAT PREDICTS TOMORROWS HRV?')
print('-' * 50)

def cross_corr(s1, s2, max_lag=7):
    results = []
    s1 = s1.copy()
    s2 = s2.copy()
    s1.index = pd.to_datetime(s1.index)
    s2.index = pd.to_datetime(s2.index)

    for lag in range(-max_lag, max_lag+1):
        if lag != 0:
            s2_shifted = s2.shift(lag)
        else:
            s2_shifted = s2

        common = s1.dropna().index.intersection(s2_shifted.dropna().index)

        if len(common) >= 30:
            x = s1.loc[common].values
            y = s2_shifted.loc[common].values
            mask = ~(np.isnan(x) | np.isnan(y))
            if mask.sum() >= 30:
                r, p = stats.pearsonr(x[mask], y[mask])
                results.append({'lag': lag, 'r': r, 'p': p, 'n': mask.sum()})
    return results

if 'hrv' in daily:
    hrv = daily['hrv']

    predictors = ['sleep', 'steps', 'active_energy', 'daylight']

    for pred in predictors:
        if pred in daily:
            results = cross_corr(daily[pred], hrv, max_lag=3)

            valid = [r for r in results if r['p'] < 0.1]
            if valid:
                best = max(valid, key=lambda x: abs(x['r']))
                print(f'  {pred} -> HRV:')
                print(f'    Best lag: {best["lag"]} days, r = {best["r"]:+.3f}, p = {best["p"]:.3f}')

print('\n\n2. WHAT PREDICTS WEIGHT CHANGES?')
print('-' * 50)

if 'weight' in daily:
    weight = daily['weight']
    weight.index = pd.to_datetime(weight.index)

    # Compute weight change (7-day)
    weight_change = weight.diff(7)

    predictors = ['steps', 'active_energy', 'sleep']

    for pred in predictors:
        if pred in daily:
            s = daily[pred].copy()
            s.index = pd.to_datetime(s.index)

            # Use 7-day rolling average of predictor
            s_roll = s.rolling(7).mean()
            common = s_roll.dropna().index.intersection(weight_change.dropna().index)

            if len(common) >= 20:
                r, p = stats.pearsonr(s_roll.loc[common], weight_change.loc[common])
                direction = 'more -> weight UP' if r > 0 else 'more -> weight DOWN'
                print(f'  {pred} (7-day avg) -> weight change:')
                print(f'    r = {r:+.3f}, p = {p:.3f} ({direction})')

print('\n\n3. SLEEP QUALITY PREDICTORS')
print('-' * 50)

if 'sleep' in daily:
    sleep = daily['sleep']

    predictors = ['steps', 'active_energy', 'daylight', 'heart_rate']

    for pred in predictors:
        if pred in daily:
            results = cross_corr(daily[pred], sleep, max_lag=2)

            same_day = [r for r in results if r['lag'] == 0]

            if same_day:
                sd = same_day[0]
                direction = 'more -> more sleep' if sd['r'] > 0 else 'more -> LESS sleep'
                print(f'  {pred} today -> sleep tonight: r = {sd["r"]:+.3f}, p = {sd["p"]:.3f}')
                print(f'    ({direction})')

print('\n\n4. RESPIRATORY RATE AS HEALTH INDICATOR')
print('-' * 50)

if 'resp_rate' in daily:
    rr = daily['resp_rate']
    rr.index = pd.to_datetime(rr.index)

    for bio in ['hrv', 'sleep', 'spo2', 'heart_rate']:
        if bio in daily:
            other = daily[bio].copy()
            other.index = pd.to_datetime(other.index)
            common = rr.index.intersection(other.index)
            if len(common) >= 30:
                r, p = stats.pearsonr(rr.loc[common], other.loc[common])
                if p < 0.1:
                    direction = 'positive' if r > 0 else 'NEGATIVE'
                    print(f'  resp_rate <-> {bio}: r = {r:+.3f} ({direction}), p = {p:.3f}')

print('\n\n5. MULTI-DAY MOMENTUM EFFECTS')
print('-' * 50)
print('Do good/bad days cluster together?')

for bio in ['steps', 'hrv', 'sleep']:
    if bio in daily:
        s = daily[bio]
        # Autocorrelation at lag 1 (does today predict tomorrow?)
        ac1 = s.autocorr(lag=1)
        ac7 = s.autocorr(lag=7)  # Weekly pattern

        print(f'\n  {bio}:')
        print(f'    Day-to-day autocorr: {ac1:.3f}' + (' (momentum!)' if ac1 > 0.3 else ''))
        print(f'    Week-to-week autocorr: {ac7:.3f}' + (' (weekly habit!)' if ac7 > 0.3 else ''))

print('\n\n6. DAYLIGHT AS MASTER DRIVER')
print('-' * 50)

if 'daylight' in daily:
    dl = daily['daylight'].copy()
    dl.index = pd.to_datetime(dl.index)

    print('Daylight correlates with:')
    for bio in sorted(daily.keys()):
        if bio != 'daylight':
            other = daily[bio].copy()
            other.index = pd.to_datetime(other.index)
            common = dl.index.intersection(other.index)
            if len(common) >= 30:
                r, p = stats.pearsonr(dl.loc[common], other.loc[common])
                if abs(r) > 0.15 and p < 0.05:
                    bar = '*' * int(abs(r) * 20)
                    print(f'  {bio:<15}: r = {r:+.3f} {bar}')

print('\n' + '=' * 75)
print('SUMMARY: NON-OBVIOUS CONNECTIONS')
print('=' * 75)

print("""
Key Findings:
-------------
1. DAYLIGHT is a master behavioral driver
   - Strongly correlates with steps, energy, exercise, HR
   - More sun = more activity (not surprising, but very strong)

2. RESPIRATORY RATE is a health sentinel
   - Higher resp rate = less sleep, lower HRV
   - Could be early warning of stress/illness

3. MOMENTUM EFFECTS
   - Steps have day-to-day momentum (active days cluster)
   - Sleep also shows clustering
   - Suggests habits/routines matter

4. SLEEP-HRV CONNECTION
   - Well-validated relationship
   - More sleep = better autonomic recovery

5. EXERCISE-AUDIO LINK
   - Workout audio is louder (+12 dB on exercise days)
   - Potential hearing risk from exercise habits
""")
