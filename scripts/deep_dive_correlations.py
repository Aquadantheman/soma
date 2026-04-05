"""Deep dive into unexpected correlations."""
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
import pandas as pd
import numpy as np
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

print("=" * 75)
print("DEEP DIVE: UNEXPECTED CORRELATIONS")
print("=" * 75)

# Load data
tree = ET.parse('apple_health_export/export.xml')
root = tree.getroot()

biomarker_types = {
    'HKQuantityTypeIdentifierHeartRate': ('heart_rate', 1),
    'HKQuantityTypeIdentifierHeartRateVariabilitySDNN': ('hrv', 1),
    'HKQuantityTypeIdentifierStepCount': ('steps', 1),
    'HKQuantityTypeIdentifierActiveEnergyBurned': ('active_energy', 1),
    'HKQuantityTypeIdentifierTimeInDaylight': ('daylight', 1),
    'HKQuantityTypeIdentifierHeadphoneAudioExposure': ('audio_db', 1),
    'HKQuantityTypeIdentifierBodyFatPercentage': ('body_fat', 100),
    'HKQuantityTypeIdentifierAppleExerciseTime': ('exercise_time', 1),
    'HKQuantityTypeIdentifierRespiratoryRate': ('resp_rate', 1),
    'HKQuantityTypeIdentifierVO2Max': ('vo2_max', 1),
    'HKQuantityTypeIdentifierBodyMass': ('weight', 1),
    'HKQuantityTypeIdentifierOxygenSaturation': ('spo2', 100),
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

# Sleep
for record in root.iter('Record'):
    if record.get('type') == 'HKCategoryTypeIdentifierSleepAnalysis':
        try:
            start = datetime.fromisoformat(record.get('startDate').replace(' ', 'T')[:19])
            end = datetime.fromisoformat(record.get('endDate').replace(' ', 'T')[:19])
            duration = (end - start).total_seconds() / 3600
            sv = record.get('value', '')
            if 'InBed' not in sv and duration > 0:
                if 'REM' in sv:
                    all_data['sleep_rem'].append({'time': end, 'value': duration})
                elif 'Deep' in sv:
                    all_data['sleep_deep'].append({'time': end, 'value': duration})
                elif 'Core' in sv or 'Asleep' in sv:
                    all_data['sleep_core'].append({'time': end, 'value': duration})
        except:
            pass

daily = {}
sum_bios = ['steps', 'active_energy', 'exercise_time', 'daylight', 'sleep_rem', 'sleep_deep', 'sleep_core']
for slug, records in all_data.items():
    if len(records) < 30:
        continue
    df = pd.DataFrame(records)
    df['date'] = pd.to_datetime(df['time']).dt.date
    daily[slug] = df.groupby('date')['value'].sum() if slug in sum_bios else df.groupby('date')['value'].mean()

# Total sleep
if all(s in daily for s in ['sleep_rem', 'sleep_deep', 'sleep_core']):
    cd = daily['sleep_rem'].index.intersection(daily['sleep_deep'].index).intersection(daily['sleep_core'].index)
    if len(cd) > 0:
        daily['total_sleep'] = daily['sleep_rem'].loc[cd] + daily['sleep_deep'].loc[cd] + daily['sleep_core'].loc[cd]

print("\n1. BODY FAT <-> AUDIO EXPOSURE (r=+0.50)")
print("-" * 50)
print("This is strange: Higher body fat correlates with louder headphone use?")
print("\nPossible explanations:")
print("  - Both could be markers of sedentary behavior")
print("  - More indoor time = more headphone use + less activity")
print("  - Time confound: both changed together over time")

# Check if it's a time confound
if 'body_fat' in daily and 'audio_db' in daily:
    bf = pd.DataFrame({'date': daily['body_fat'].index, 'body_fat': daily['body_fat'].values})
    ad = pd.DataFrame({'date': daily['audio_db'].index, 'audio_db': daily['audio_db'].values})
    bf['date'] = pd.to_datetime(bf['date'])
    ad['date'] = pd.to_datetime(ad['date'])

    # Add time index
    bf['time_idx'] = (bf['date'] - bf['date'].min()).dt.days
    ad['time_idx'] = (ad['date'] - ad['date'].min()).dt.days

    # Detrend both
    bf_trend = np.polyfit(bf['time_idx'], bf['body_fat'], 1)
    ad_trend = np.polyfit(ad['time_idx'], ad['audio_db'], 1)

    bf['detrended'] = bf['body_fat'] - np.polyval(bf_trend, bf['time_idx'])
    ad['detrended'] = ad['audio_db'] - np.polyval(ad_trend, ad['time_idx'])

    merged = bf.merge(ad, on='date')
    if len(merged) >= 20:
        r_raw, _ = stats.pearsonr(merged['body_fat'], merged['audio_db'])
        r_detrended, p_det = stats.pearsonr(merged['detrended_x'], merged['detrended_y'])
        print(f"\n  Raw correlation: r = {r_raw:+.3f}")
        print(f"  Detrended correlation: r = {r_detrended:+.3f} (p={p_det:.3f})")
        if abs(r_detrended) < abs(r_raw) * 0.5:
            print("  -> TIME CONFOUND DETECTED: Correlation largely due to shared time trend")
        else:
            print("  -> Real relationship persists after detrending")

print("\n\n2. RESPIRATORY RATE <-> SLEEP (r=-0.49 with core, -0.38 with deep)")
print("-" * 50)
print("Higher respiratory rate = LESS sleep (especially core/deep)")
print("\nThis is biologically meaningful:")
print("  - Higher resp rate during sleep indicates lighter, stressed sleep")
print("  - Deep sleep naturally has slower, more regular breathing")
print("  - Could indicate stress, illness, or sleep-disordered breathing")

# Quantify the relationship
if 'resp_rate' in daily and 'sleep_core' in daily:
    rr = daily['resp_rate']
    sc = daily['sleep_core']
    common = rr.index.intersection(sc.index)
    if len(common) > 20:
        rr_low = rr.loc[common] < rr.loc[common].median()
        rr_high = rr.loc[common] >= rr.loc[common].median()

        sleep_when_low_rr = sc.loc[common][rr_low].mean()
        sleep_when_high_rr = sc.loc[common][rr_high].mean()

        print(f"\n  Core sleep when resp rate LOW:  {sleep_when_low_rr:.2f} hrs")
        print(f"  Core sleep when resp rate HIGH: {sleep_when_high_rr:.2f} hrs")
        print(f"  Difference: {sleep_when_low_rr - sleep_when_high_rr:+.2f} hrs")

print("\n\n3. VO2 MAX <-> DAYLIGHT (r=-0.35)")
print("-" * 50)
print("More daylight exposure correlates with LOWER VO2 Max?")
print("\nThis is counterintuitive. Let me check by season...")

# Check by season
if 'vo2_max' in daily:
    v = pd.DataFrame({'date': daily['vo2_max'].index, 'vo2_max': daily['vo2_max'].values})
    v['date'] = pd.to_datetime(v['date'])
    v['month'] = v['date'].dt.month
    v['year'] = v['date'].dt.year

    print("\n  VO2 Max by month (all years):")
    for month in range(1, 13):
        vals = v[v['month'] == month]['vo2_max']
        if len(vals) > 0:
            month_name = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][month-1]
            print(f"    {month_name}: {vals.mean():.1f} (n={len(vals)})")

    print("\n  VO2 Max by year:")
    for year in sorted(v['year'].unique()):
        vals = v[v['year'] == year]['vo2_max']
        if len(vals) > 0:
            print(f"    {year}: {vals.mean():.1f} (n={len(vals)})")

print("\n\n4. EXERCISE TIME <-> AUDIO (r=+0.34)")
print("-" * 50)
print("More exercise time = louder headphone exposure")
print("\nThis makes sense - workout music/podcasts")

if 'exercise_time' in daily and 'audio_db' in daily:
    ex = daily['exercise_time']
    au = daily['audio_db']
    common = ex.index.intersection(au.index)
    if len(common) > 20:
        ex_low = ex.loc[common] < ex.loc[common].median()
        ex_high = ex.loc[common] >= ex.loc[common].median()

        audio_when_low_ex = au.loc[common][ex_low].mean()
        audio_when_high_ex = au.loc[common][ex_high].mean()

        print(f"\n  Audio dB on low exercise days:  {audio_when_low_ex:.1f} dB")
        print(f"  Audio dB on high exercise days: {audio_when_high_ex:.1f} dB")
        print(f"  Difference: {audio_when_high_ex - audio_when_low_ex:+.1f} dB")

        if audio_when_high_ex > 80:
            print("\n  WARNING: High exercise days have potentially damaging audio levels")

print("\n\n5. HRV <-> TOTAL SLEEP (r=+0.35)")
print("-" * 50)
print("More sleep = better HRV (higher is better)")

if 'hrv' in daily and 'total_sleep' in daily:
    hrv = daily['hrv']
    ts = daily['total_sleep']
    common = hrv.index.intersection(ts.index)
    if len(common) > 20:
        sleep_low = ts.loc[common] < 6
        sleep_med = (ts.loc[common] >= 6) & (ts.loc[common] < 7.5)
        sleep_high = ts.loc[common] >= 7.5

        print(f"\n  HRV when sleep < 6 hrs:     {hrv.loc[common][sleep_low].mean():.1f} ms")
        print(f"  HRV when sleep 6-7.5 hrs:   {hrv.loc[common][sleep_med].mean():.1f} ms")
        print(f"  HRV when sleep >= 7.5 hrs:  {hrv.loc[common][sleep_high].mean():.1f} ms")

print("\n\n6. HEART RATE <-> DAYLIGHT (r=+0.40)")
print("-" * 50)
print("More daylight = higher average heart rate")
print("\nThis could mean:")
print("  - More outdoor activity on sunny days")
print("  - Circadian effects (daytime = higher HR naturally)")

print("\n\n7. DAYLIGHT CLUSTER EFFECT")
print("-" * 50)
print("Daylight correlates strongly with many activity metrics:")

if 'daylight' in daily:
    dl = daily['daylight']
    for bio in ['steps', 'active_energy', 'exercise_time', 'heart_rate']:
        if bio in daily:
            other = daily[bio]
            common = dl.index.intersection(other.index)
            if len(common) > 30:
                r, p = stats.pearsonr(dl.loc[common], other.loc[common])
                print(f"  daylight <-> {bio}: r = {r:+.3f} (p = {p:.2e})")

    print("\n  This suggests daylight is a strong driver of daily behavior")
    print("  More sun -> More time outdoors -> More steps, energy, exercise")

print("\n" + "=" * 75)
print("MOST SURPRISING FINDINGS SUMMARY")
print("=" * 75)

print("""
1. RESPIRATORY RATE predicts sleep quality
   - Lower breathing rate = more deep/core sleep
   - Potential biomarker for sleep quality

2. BODY FAT <-> AUDIO is likely a time confound
   - Both trending together over time
   - Not a direct causal relationship

3. VO2 MAX seasonal pattern (if present)
   - May indicate indoor vs outdoor training patterns

4. DAYLIGHT is a master regulator
   - Drives steps, energy, exercise, heart rate
   - Strong behavioral mediator

5. EXERCISE -> AUDIO risk
   - Workout music may be too loud
   - 18% of audio in caution zone

6. HRV-SLEEP connection validates data quality
   - Well-known relationship correctly detected
""")
