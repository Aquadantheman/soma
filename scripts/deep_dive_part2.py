"""Part 2: Deeper temporal analysis of body composition."""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

print('DEEP DIVE PART 2: TEMPORAL DYNAMICS')
print('=' * 60)

# Parse Apple Health data
tree = ET.parse('apple_health_export/export.xml')
root = tree.getroot()

# Collect data by date
weight_by_date = {}
body_fat_by_date = {}
steps_by_date = defaultdict(float)
vo2max_by_date = {}
rhr_by_date = {}

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
    elif rtype == 'HKQuantityTypeIdentifierBodyFatPercentage':
        body_fat_by_date[date_key] = val * 100  # ratio -> pct
    elif rtype == 'HKQuantityTypeIdentifierStepCount':
        steps_by_date[date_key] += val
    elif rtype == 'HKQuantityTypeIdentifierVO2Max':
        vo2max_by_date[date_key] = val
    elif rtype == 'HKQuantityTypeIdentifierRestingHeartRate':
        rhr_by_date[date_key] = val

print('=' * 60)
print('1. YEAR-BY-YEAR BREAKDOWN')
print('=' * 60)

# Group by year
weight_by_year = defaultdict(list)
steps_by_year = defaultdict(list)
vo2_by_year = defaultdict(list)

for d, w in weight_by_date.items():
    weight_by_year[d.year].append(w)

for d, s in steps_by_date.items():
    steps_by_year[d.year].append(s)

for d, v in vo2max_by_date.items():
    vo2_by_year[d.year].append(v)

print('\nYear | Weight (kg) | Steps/day | VO2 Max')
print('-' * 50)
for year in sorted(set(weight_by_year.keys()) | set(steps_by_year.keys())):
    w = f'{statistics.mean(weight_by_year[year]):.1f}' if weight_by_year[year] else '-'
    s = f'{statistics.mean(steps_by_year[year]):.0f}' if steps_by_year[year] else '-'
    v = f'{statistics.mean(vo2_by_year[year]):.1f}' if vo2_by_year[year] else '-'
    print(f'{year} | {w:>11} | {s:>9} | {v}')

print()
print('=' * 60)
print('2. WEIGHT TRAJECTORY BY QUARTER')
print('=' * 60)

# Group by year-quarter
weight_by_quarter = defaultdict(list)
steps_by_quarter = defaultdict(list)

for d, w in weight_by_date.items():
    q = (d.year, (d.month - 1) // 3 + 1)
    weight_by_quarter[q].append(w)

for d, s in steps_by_date.items():
    q = (d.year, (d.month - 1) // 3 + 1)
    steps_by_quarter[q].append(s)

print('\nQuarter | Weight (kg) | Steps/day | Weight n | Steps n')
print('-' * 60)
for q in sorted(weight_by_quarter.keys()):
    w_mean = statistics.mean(weight_by_quarter[q]) if weight_by_quarter[q] else None
    s_mean = statistics.mean(steps_by_quarter[q]) if q in steps_by_quarter else None
    w_str = f'{w_mean:.1f}' if w_mean else '-'
    s_str = f'{s_mean:.0f}' if s_mean else '-'
    w_n = len(weight_by_quarter[q])
    s_n = len(steps_by_quarter[q]) if q in steps_by_quarter else 0
    print(f'{q[0]} Q{q[1]} | {w_str:>11} | {s_str:>9} | {w_n:>8} | {s_n:>7}')

print()
print('=' * 60)
print('3. WEIGHT CHANGE EPISODES')
print('=' * 60)

# Find periods of weight gain and loss
sorted_dates = sorted(weight_by_date.keys())
episodes = []

if len(sorted_dates) >= 2:
    start_idx = 0
    current_direction = None

    for i in range(1, len(sorted_dates)):
        weight_change = weight_by_date[sorted_dates[i]] - weight_by_date[sorted_dates[i-1]]
        direction = 'gain' if weight_change > 0.5 else ('loss' if weight_change < -0.5 else 'stable')

        if current_direction is None:
            current_direction = direction
        elif direction != current_direction and direction != 'stable':
            # End of episode
            episode_start = sorted_dates[start_idx]
            episode_end = sorted_dates[i-1]
            total_change = weight_by_date[sorted_dates[i-1]] - weight_by_date[sorted_dates[start_idx]]
            episodes.append((episode_start, episode_end, current_direction, total_change))
            start_idx = i
            current_direction = direction

print('\nSignificant weight change episodes:')
print('Start      | End        | Type | Change (kg)')
print('-' * 50)
significant_episodes = [e for e in episodes if abs(e[3]) >= 1.0]
for ep in significant_episodes[-10:]:  # Last 10 significant episodes
    print(f'{ep[0]} | {ep[1]} | {ep[2]:>4} | {ep[3]:+.1f}')

print()
print('=' * 60)
print('4. ACTIVITY DURING WEIGHT CHANGE PERIODS')
print('=' * 60)

# For each significant episode, calculate average activity
print('\nActivity levels during weight change episodes:')
for ep in significant_episodes[-5:]:
    start, end, direction, change = ep

    # Get steps during this period
    period_steps = [steps_by_date[d] for d in steps_by_date
                    if start <= d <= end]

    if period_steps:
        avg_steps = statistics.mean(period_steps)
        print(f'\n  {start} to {end}:')
        print(f'    Direction: {direction}, Change: {change:+.1f} kg')
        print(f'    Avg daily steps: {avg_steps:.0f}')

print()
print('=' * 60)
print('5. RATE OF CHANGE ANALYSIS')
print('=' * 60)

# Calculate rate of weight change over different windows
print('\nWeight change rate (kg/month) by period:')
if len(sorted_dates) >= 60:
    # Monthly rate of change
    for i in range(0, len(sorted_dates) - 30, 30):
        start_date = sorted_dates[i]
        end_date = sorted_dates[min(i + 30, len(sorted_dates) - 1)]

        start_weight = weight_by_date[start_date]
        end_weight = weight_by_date[end_date]

        days = (end_date - start_date).days
        if days > 0:
            monthly_rate = (end_weight - start_weight) / days * 30
            period_steps = [steps_by_date[d] for d in steps_by_date
                          if start_date <= d <= end_date]
            avg_steps = statistics.mean(period_steps) if period_steps else 0

            print(f'  {start_date}: {monthly_rate:+.2f} kg/mo (steps: {avg_steps:.0f})')

print()
print('=' * 60)
print('6. BEHAVIORAL ANALYSIS: Do you exercise more when heavier?')
print('=' * 60)

# Compare activity levels at different weight ranges
if len(weight_by_date) >= 50:
    all_weights = list(weight_by_date.values())
    percentiles = [
        ('Lowest 25%', 0, 25),
        ('25-50%', 25, 50),
        ('50-75%', 50, 75),
        ('Highest 25%', 75, 100),
    ]

    p25 = sorted(all_weights)[len(all_weights) // 4]
    p50 = sorted(all_weights)[len(all_weights) // 2]
    p75 = sorted(all_weights)[3 * len(all_weights) // 4]

    print(f'\nWeight percentile thresholds:')
    print(f'  25th: {p25:.1f} kg')
    print(f'  50th: {p50:.1f} kg')
    print(f'  75th: {p75:.1f} kg')

    print('\nActivity at different weight ranges:')

    # Lowest weight days
    low_weight_days = [d for d in weight_by_date if weight_by_date[d] <= p25]
    low_steps = [steps_by_date[d] for d in low_weight_days if d in steps_by_date]

    # Medium-low weight days
    med_low_days = [d for d in weight_by_date if p25 < weight_by_date[d] <= p50]
    med_low_steps = [steps_by_date[d] for d in med_low_days if d in steps_by_date]

    # Medium-high weight days
    med_high_days = [d for d in weight_by_date if p50 < weight_by_date[d] <= p75]
    med_high_steps = [steps_by_date[d] for d in med_high_days if d in steps_by_date]

    # Highest weight days
    high_weight_days = [d for d in weight_by_date if weight_by_date[d] > p75]
    high_steps = [steps_by_date[d] for d in high_weight_days if d in steps_by_date]

    print(f'  Lowest 25% (≤{p25:.1f} kg): {statistics.mean(low_steps):.0f} steps/day (n={len(low_steps)})' if low_steps else f'  Lowest 25%: no data')
    print(f'  25-50% ({p25:.1f}-{p50:.1f} kg): {statistics.mean(med_low_steps):.0f} steps/day (n={len(med_low_steps)})' if med_low_steps else f'  25-50%: no data')
    print(f'  50-75% ({p50:.1f}-{p75:.1f} kg): {statistics.mean(med_high_steps):.0f} steps/day (n={len(med_high_steps)})' if med_high_steps else f'  50-75%: no data')
    print(f'  Highest 25% (>{p75:.1f} kg): {statistics.mean(high_steps):.0f} steps/day (n={len(high_steps)})' if high_steps else f'  Highest 25%: no data')

print()
print('=' * 60)
print('7. BODY FAT TRAJECTORY')
print('=' * 60)

if body_fat_by_date:
    bf_dates = sorted(body_fat_by_date.keys())
    print(f'\nBody fat measurements: {len(bf_dates)}')
    print(f'Date range: {bf_dates[0]} to {bf_dates[-1]}')

    bf_values = [body_fat_by_date[d] for d in bf_dates]
    print(f'\nRange: {min(bf_values):.1f}% to {max(bf_values):.1f}%')
    print(f'Mean: {statistics.mean(bf_values):.1f}%')

    # Trend
    if len(bf_dates) >= 5:
        first_quarter = bf_dates[:len(bf_dates)//4]
        last_quarter = bf_dates[-len(bf_dates)//4:]

        early_bf = [body_fat_by_date[d] for d in first_quarter]
        late_bf = [body_fat_by_date[d] for d in last_quarter]

        print(f'\nEarly avg: {statistics.mean(early_bf):.1f}%')
        print(f'Late avg: {statistics.mean(late_bf):.1f}%')
        print(f'Change: {statistics.mean(late_bf) - statistics.mean(early_bf):+.1f}%')

print()
print('=' * 60)
print('8. WEIGHT-FITNESS COUPLING')
print('=' * 60)

# When weight goes down, does fitness (VO2 Max) go up?
common_dates = sorted(set(weight_by_date.keys()) & set(vo2max_by_date.keys()))
if len(common_dates) >= 10:
    print(f'\nDays with both weight and VO2 Max: {len(common_dates)}')

    # Split into periods
    first_half = common_dates[:len(common_dates)//2]
    second_half = common_dates[len(common_dates)//2:]

    first_weight = statistics.mean([weight_by_date[d] for d in first_half])
    second_weight = statistics.mean([weight_by_date[d] for d in second_half])

    first_vo2 = statistics.mean([vo2max_by_date[d] for d in first_half])
    second_vo2 = statistics.mean([vo2max_by_date[d] for d in second_half])

    print(f'\nFirst half:  Weight {first_weight:.1f} kg, VO2 Max {first_vo2:.1f}')
    print(f'Second half: Weight {second_weight:.1f} kg, VO2 Max {second_vo2:.1f}')
    print(f'\nChanges:')
    print(f'  Weight: {second_weight - first_weight:+.1f} kg')
    print(f'  VO2 Max: {second_vo2 - first_vo2:+.1f} mL/kg/min')

    if (second_weight - first_weight) * (second_vo2 - first_vo2) < 0:
        print(f'\n  --> INVERSE relationship: Weight and VO2 Max move opposite directions')

print()
print('=' * 60)
print('INSIGHTS SUMMARY')
print('=' * 60)
print('''
Key Findings:

1. SIMPSON'S PARADOX CONFIRMED:
   - Weight increased over time (+2.2 kg)
   - Steps DECREASED over time (-1593)
   - Yet within-time correlation shows positive steps-weight relationship
   - This is likely because you exercise MORE when feeling heavier

2. DETRENDED CORRELATION NEAR ZERO:
   - After removing personal trends, r = 0.018
   - Day-to-day step variation doesn't predict weight
   - Only sustained behavior changes matter

3. VO2 MAX IS THE STRONGEST PREDICTOR:
   - r = -0.502 (weight <-> VO2 Max)
   - Improving fitness associates with lower weight
   - This is actionable: focus on cardio fitness

4. BEHAVIORAL INSIGHT:
   - When you weigh more, you may exercise more
   - This is a compensatory behavior (good!)
   - But it takes sustained effort to move the needle
''')
