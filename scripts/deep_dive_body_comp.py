"""Deep dive analysis of body composition dynamics."""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

print('DEEP DIVE: INVESTIGATING BODY COMPOSITION DYNAMICS')
print('=' * 60)

# Parse Apple Health data
tree = ET.parse('apple_health_export/export.xml')
root = tree.getroot()

# Collect data by date
weight_by_date = {}
steps_by_date = defaultdict(float)
vo2max_by_date = {}
rhr_by_date = {}
hrv_by_date = defaultdict(list)
sleep_by_date = defaultdict(float)
active_energy_by_date = defaultdict(float)

for record in root.iter('Record'):
    rtype = record.get('type')
    value = record.get('value')
    start = record.get('startDate')

    if not value or not start:
        continue

    try:
        dt = datetime.strptime(start[:10], '%Y-%m-%d')
        date_key = dt.date()
        val = float(value)
    except:
        continue

    if rtype == 'HKQuantityTypeIdentifierBodyMass':
        weight_by_date[date_key] = val * 0.453592  # lb -> kg
    elif rtype == 'HKQuantityTypeIdentifierStepCount':
        steps_by_date[date_key] += val
    elif rtype == 'HKQuantityTypeIdentifierVO2Max':
        vo2max_by_date[date_key] = val
    elif rtype == 'HKQuantityTypeIdentifierRestingHeartRate':
        rhr_by_date[date_key] = val
    elif rtype == 'HKQuantityTypeIdentifierHeartRateVariabilitySDNN':
        hrv_by_date[date_key].append(val * 1000)  # s -> ms
    elif rtype == 'HKQuantityTypeIdentifierActiveEnergyBurned':
        active_energy_by_date[date_key] += val

# Average HRV per day
hrv_avg_by_date = {d: statistics.mean(vs) for d, vs in hrv_by_date.items() if vs}

# Parse sleep data
for record in root.iter('CategorySample'):
    rtype = record.get('type')
    if rtype != 'HKCategoryTypeIdentifierSleepAnalysis':
        continue
    value = record.get('value')
    if 'Asleep' not in value:
        continue
    start = record.get('startDate')
    end = record.get('endDate')
    if not start or not end:
        continue
    try:
        start_dt = datetime.strptime(start[:19], '%Y-%m-%d %H:%M:%S')
        end_dt = datetime.strptime(end[:19], '%Y-%m-%d %H:%M:%S')
        duration = (end_dt - start_dt).total_seconds() / 60
        # Assign to the night's date (before 12pm = previous day's sleep)
        if start_dt.hour < 12:
            date_key = (start_dt - timedelta(days=1)).date()
        else:
            date_key = start_dt.date()
        sleep_by_date[date_key] += duration
    except:
        continue

print(f'Data loaded:')
print(f'  Weight measurements: {len(weight_by_date)}')
print(f'  Days with steps: {len(steps_by_date)}')
print(f'  Days with VO2 Max: {len(vo2max_by_date)}')
print(f'  Days with RHR: {len(rhr_by_date)}')
print(f'  Days with HRV: {len(hrv_avg_by_date)}')
print(f'  Days with sleep: {len(sleep_by_date)}')
print(f'  Days with active energy: {len(active_energy_by_date)}')

print()
print('=' * 60)
print("1. SIMPSON'S PARADOX INVESTIGATION")
print('   Why does higher activity correlate with higher weight?')
print('=' * 60)

# Check: Is there a TIME trend?
weight_dates = sorted(weight_by_date.keys())
if len(weight_dates) >= 2:
    first_quarter = weight_dates[:len(weight_dates)//4]  # First 25%
    last_quarter = weight_dates[-len(weight_dates)//4:]  # Last 25%

    early_weights = [weight_by_date[d] for d in first_quarter]
    late_weights = [weight_by_date[d] for d in last_quarter]

    early_steps = [steps_by_date[d] for d in first_quarter if d in steps_by_date]
    late_steps = [steps_by_date[d] for d in last_quarter if d in steps_by_date]

    print(f'\nEarly period (first 25% of data):')
    print(f'  Avg weight: {statistics.mean(early_weights):.1f} kg')
    if early_steps:
        print(f'  Avg steps: {statistics.mean(early_steps):.0f}')
    else:
        print('  No step data')

    print(f'\nLate period (last 25% of data):')
    print(f'  Avg weight: {statistics.mean(late_weights):.1f} kg')
    if late_steps:
        print(f'  Avg steps: {statistics.mean(late_steps):.0f}')
    else:
        print('  No step data')

    if early_steps and late_steps:
        weight_change = statistics.mean(late_weights) - statistics.mean(early_weights)
        steps_change = statistics.mean(late_steps) - statistics.mean(early_steps)
        print(f'\n  Weight changed: {weight_change:+.1f} kg')
        print(f'  Steps changed: {steps_change:+.0f}')
        print(f"\n  --> SIMPSON'S PARADOX: Both trending in same direction over time!")
        print(f'      The positive correlation may be a time confound.')

print()
print('=' * 60)
print('2. DETRENDED ANALYSIS: Removing the time trend')
print('=' * 60)

# Compute 30-day rolling averages for weight and steps
def rolling_avg(data_dict, window=30):
    dates = sorted(data_dict.keys())
    result = {}
    for i, d in enumerate(dates):
        window_dates = [dt for dt in dates[max(0,i-window):i+1]]
        if len(window_dates) >= 7:  # Need at least 7 days
            vals = [data_dict[dt] for dt in window_dates]
            result[d] = statistics.mean(vals)
    return result

weight_baseline = rolling_avg(weight_by_date, 30)
steps_baseline = rolling_avg(dict(steps_by_date), 30)

# Compute deviations
weight_deviations = {}
steps_deviations = {}

for d in weight_by_date:
    if d in weight_baseline:
        weight_deviations[d] = weight_by_date[d] - weight_baseline[d]

for d in steps_by_date:
    if d in steps_baseline:
        steps_deviations[d] = steps_by_date[d] - steps_baseline[d]

# Correlate deviations
common_dates = set(weight_deviations.keys()) & set(steps_deviations.keys())
if len(common_dates) >= 20:
    w_devs = [weight_deviations[d] for d in common_dates]
    s_devs = [steps_deviations[d] for d in common_dates]

    # Manual correlation
    n = len(w_devs)
    mean_w = sum(w_devs) / n
    mean_s = sum(s_devs) / n

    cov = sum((w - mean_w) * (s - mean_s) for w, s in zip(w_devs, s_devs)) / n
    std_w = (sum((w - mean_w)**2 for w in w_devs) / n) ** 0.5
    std_s = (sum((s - mean_s)**2 for s in s_devs) / n) ** 0.5

    r = cov / (std_w * std_s) if std_w > 0 and std_s > 0 else 0

    print(f'\nDays with both detrended values: {len(common_dates)}')
    print(f'\nDETRENDED correlation (weight vs steps): r = {r:.3f}')

    if r < 0:
        print(f'\n  --> After removing time trend, correlation is NEGATIVE')
        print(f'      Days with above-average steps -> below-average weight')
    else:
        print(f'\n  --> Correlation still positive even after detrending')

print()
print('=' * 60)
print('3. VO2 MAX <-> BODY COMPOSITION DYNAMICS')
print('=' * 60)

# Track VO2 Max changes alongside weight changes
vo2_dates = sorted(vo2max_by_date.keys())
weight_dates_set = set(weight_by_date.keys())

# Find VO2 measurements that have nearby weight measurements
vo2_weight_pairs = []
for vo2_date in vo2_dates:
    # Find weight within 7 days
    for offset in range(-7, 8):
        check_date = vo2_date + timedelta(days=offset)
        if check_date in weight_dates_set:
            vo2_weight_pairs.append((vo2_date, vo2max_by_date[vo2_date], weight_by_date[check_date]))
            break

if len(vo2_weight_pairs) >= 10:
    print(f'\nVO2 Max measurements with nearby weight: {len(vo2_weight_pairs)}')

    # Track changes over time
    vo2_vals = [p[1] for p in vo2_weight_pairs]
    weight_vals = [p[2] for p in vo2_weight_pairs]

    # Correlation
    n = len(vo2_vals)
    mean_v = sum(vo2_vals) / n
    mean_w = sum(weight_vals) / n

    cov = sum((v - mean_v) * (w - mean_w) for v, w in zip(vo2_vals, weight_vals)) / n
    std_v = (sum((v - mean_v)**2 for v in vo2_vals) / n) ** 0.5
    std_w = (sum((w - mean_w)**2 for w in weight_vals) / n) ** 0.5

    r = cov / (std_v * std_w) if std_v > 0 and std_w > 0 else 0

    print(f'VO2 Max <-> Weight correlation: r = {r:.3f}')

    # VO2 Max changes vs weight changes
    if len(vo2_weight_pairs) >= 4:
        v_changes = [vo2_weight_pairs[i+1][1] - vo2_weight_pairs[i][1] for i in range(len(vo2_weight_pairs)-1)]
        w_changes = [vo2_weight_pairs[i+1][2] - vo2_weight_pairs[i][2] for i in range(len(vo2_weight_pairs)-1)]

        n = len(v_changes)
        if n >= 3:
            mean_vc = sum(v_changes) / n
            mean_wc = sum(w_changes) / n

            cov = sum((vc - mean_vc) * (wc - mean_wc) for vc, wc in zip(v_changes, w_changes)) / n
            std_vc = (sum((vc - mean_vc)**2 for vc in v_changes) / n) ** 0.5
            std_wc = (sum((wc - mean_wc)**2 for wc in w_changes) / n) ** 0.5

            r_change = cov / (std_vc * std_wc) if std_vc > 0 and std_wc > 0 else 0

            print(f'\nCHANGE correlation (delta VO2 Max vs delta Weight): r = {r_change:.3f}')

            if r_change < 0:
                print(f'  --> Weight loss associates with VO2 Max INCREASE')
            else:
                print(f'  --> Weight loss associates with VO2 Max DECREASE')
else:
    print(f'\nInsufficient paired VO2/weight data ({len(vo2_weight_pairs)} pairs)')

print()
print('=' * 60)
print('4. SLEEP <-> WEIGHT RELATIONSHIP')
print('=' * 60)

# Look for sleep-weight relationship
common_sleep = set(weight_by_date.keys()) & set(sleep_by_date.keys())
if len(common_sleep) >= 20:
    sleep_vals = [sleep_by_date[d] for d in common_sleep]
    weight_vals = [weight_by_date[d] for d in common_sleep]

    n = len(sleep_vals)
    mean_s = sum(sleep_vals) / n
    mean_w = sum(weight_vals) / n

    cov = sum((s - mean_s) * (w - mean_w) for s, w in zip(sleep_vals, weight_vals)) / n
    std_s = (sum((s - mean_s)**2 for s in sleep_vals) / n) ** 0.5
    std_w = (sum((w - mean_w)**2 for w in weight_vals) / n) ** 0.5

    r = cov / (std_s * std_w) if std_s > 0 and std_w > 0 else 0

    print(f'\nDays with both sleep and weight: {len(common_sleep)}')
    print(f'Sleep duration <-> Weight: r = {r:.3f}')

    # Split by sleep quality
    median_sleep = statistics.median(sleep_vals)
    good_sleep_weights = [weight_by_date[d] for d in common_sleep if sleep_by_date[d] >= median_sleep]
    poor_sleep_weights = [weight_by_date[d] for d in common_sleep if sleep_by_date[d] < median_sleep]

    print(f'\nWeight by sleep quality:')
    print(f'  Good sleep (>={median_sleep:.0f} min): {statistics.mean(good_sleep_weights):.2f} kg')
    print(f'  Poor sleep (<{median_sleep:.0f} min): {statistics.mean(poor_sleep_weights):.2f} kg')
    print(f'  Difference: {statistics.mean(good_sleep_weights) - statistics.mean(poor_sleep_weights):+.2f} kg')
else:
    print(f'\nInsufficient paired sleep/weight data ({len(common_sleep)} pairs)')

print()
print('=' * 60)
print('5. HRV <-> WEIGHT RELATIONSHIP')
print('=' * 60)

common_hrv = set(weight_by_date.keys()) & set(hrv_avg_by_date.keys())
if len(common_hrv) >= 20:
    hrv_vals = [hrv_avg_by_date[d] for d in common_hrv]
    weight_vals = [weight_by_date[d] for d in common_hrv]

    n = len(hrv_vals)
    mean_h = sum(hrv_vals) / n
    mean_w = sum(weight_vals) / n

    cov = sum((h - mean_h) * (w - mean_w) for h, w in zip(hrv_vals, weight_vals)) / n
    std_h = (sum((h - mean_h)**2 for h in hrv_vals) / n) ** 0.5
    std_w = (sum((w - mean_w)**2 for w in weight_vals) / n) ** 0.5

    r = cov / (std_h * std_w) if std_h > 0 and std_w > 0 else 0

    print(f'\nDays with both HRV and weight: {len(common_hrv)}')
    print(f'HRV (SDNN) <-> Weight: r = {r:.3f}')

    if r < 0:
        print(f'  --> Higher weight associated with LOWER HRV (poorer autonomic function)')
    else:
        print(f'  --> Higher weight associated with HIGHER HRV')
else:
    print(f'\nInsufficient paired HRV/weight data ({len(common_hrv)} pairs)')

print()
print('=' * 60)
print('6. ACTIVE ENERGY <-> WEIGHT (Better than steps?)')
print('=' * 60)

common_energy = set(weight_by_date.keys()) & set(active_energy_by_date.keys())
if len(common_energy) >= 20:
    energy_vals = [active_energy_by_date[d] for d in common_energy]
    weight_vals = [weight_by_date[d] for d in common_energy]

    n = len(energy_vals)
    mean_e = sum(energy_vals) / n
    mean_w = sum(weight_vals) / n

    cov = sum((e - mean_e) * (w - mean_w) for e, w in zip(energy_vals, weight_vals)) / n
    std_e = (sum((e - mean_e)**2 for e in energy_vals) / n) ** 0.5
    std_w = (sum((w - mean_w)**2 for w in weight_vals) / n) ** 0.5

    r = cov / (std_e * std_w) if std_e > 0 and std_w > 0 else 0

    print(f'\nDays with both active energy and weight: {len(common_energy)}')
    print(f'Active Energy <-> Weight: r = {r:.3f}')

    # Energy expenditure increases with body mass (physics)
    print(f'\n  Note: Larger bodies burn more calories moving')
    print(f'  A positive correlation is EXPECTED from physics')
else:
    print(f'\nInsufficient paired energy/weight data ({len(common_energy)} pairs)')

print()
print('=' * 60)
print('7. LAGGED ANALYSIS: What predicts future weight?')
print('=' * 60)

# Look at 7-day and 14-day lagged correlations
for lag_days in [7, 14, 30]:
    # Steps today -> Weight in N days
    lagged_pairs = []
    for d in steps_by_date:
        future_date = d + timedelta(days=lag_days)
        if future_date in weight_by_date:
            lagged_pairs.append((steps_by_date[d], weight_by_date[future_date]))

    if len(lagged_pairs) >= 30:
        steps_vals = [p[0] for p in lagged_pairs]
        weight_vals = [p[1] for p in lagged_pairs]

        n = len(steps_vals)
        mean_s = sum(steps_vals) / n
        mean_w = sum(weight_vals) / n

        cov = sum((s - mean_s) * (w - mean_w) for s, w in zip(steps_vals, weight_vals)) / n
        std_s = (sum((s - mean_s)**2 for s in steps_vals) / n) ** 0.5
        std_w = (sum((w - mean_w)**2 for w in weight_vals) / n) ** 0.5

        r = cov / (std_s * std_w) if std_s > 0 and std_w > 0 else 0

        print(f'\nSteps today -> Weight in {lag_days} days: r = {r:.3f} (n={n})')

# Sleep today -> Weight in N days
print('\nSleep today -> Future weight:')
for lag_days in [7, 14, 30]:
    lagged_pairs = []
    for d in sleep_by_date:
        future_date = d + timedelta(days=lag_days)
        if future_date in weight_by_date:
            lagged_pairs.append((sleep_by_date[d], weight_by_date[future_date]))

    if len(lagged_pairs) >= 30:
        sleep_vals = [p[0] for p in lagged_pairs]
        weight_vals = [p[1] for p in lagged_pairs]

        n = len(sleep_vals)
        mean_s = sum(sleep_vals) / n
        mean_w = sum(weight_vals) / n

        cov = sum((s - mean_s) * (w - mean_w) for s, w in zip(sleep_vals, weight_vals)) / n
        std_s = (sum((s - mean_s)**2 for s in sleep_vals) / n) ** 0.5
        std_w = (sum((w - mean_w)**2 for w in weight_vals) / n) ** 0.5

        r = cov / (std_s * std_w) if std_s > 0 and std_w > 0 else 0

        print(f'  Sleep today -> Weight in {lag_days} days: r = {r:.3f} (n={n})')

print()
print('=' * 60)
print('8. CUMULATIVE ACTIVITY EFFECT')
print('=' * 60)

# Does CUMULATIVE activity over the past 7/14/30 days predict weight?
print('\nCumulative steps over past N days -> Current weight:')
for window in [7, 14, 30]:
    cumulative_pairs = []
    weight_dates_sorted = sorted(weight_by_date.keys())

    for w_date in weight_dates_sorted:
        # Sum steps over past N days
        total_steps = 0
        days_with_data = 0
        for offset in range(1, window + 1):
            check_date = w_date - timedelta(days=offset)
            if check_date in steps_by_date:
                total_steps += steps_by_date[check_date]
                days_with_data += 1

        if days_with_data >= window * 0.7:  # At least 70% of days have data
            cumulative_pairs.append((total_steps / days_with_data, weight_by_date[w_date]))

    if len(cumulative_pairs) >= 30:
        avg_steps = [p[0] for p in cumulative_pairs]
        weights = [p[1] for p in cumulative_pairs]

        n = len(avg_steps)
        mean_s = sum(avg_steps) / n
        mean_w = sum(weights) / n

        cov = sum((s - mean_s) * (w - mean_w) for s, w in zip(avg_steps, weights)) / n
        std_s = (sum((s - mean_s)**2 for s in avg_steps) / n) ** 0.5
        std_w = (sum((w - mean_w)**2 for w in weights) / n) ** 0.5

        r = cov / (std_s * std_w) if std_s > 0 and std_w > 0 else 0

        print(f'  Past {window} days avg steps -> Weight: r = {r:.3f} (n={n})')

print()
print('=' * 60)
print('SUMMARY OF FINDINGS')
print('=' * 60)
