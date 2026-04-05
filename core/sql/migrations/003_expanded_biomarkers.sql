-- Migration 003: Expanded Biomarkers and Computed Features
-- Based on real Apple Health data analysis and clinical relevance

-- =====================================================
-- NEW APPLE HEALTH BIOMARKERS
-- =====================================================

-- Cardiovascular Recovery & Efficiency
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
    ('hr_recovery_1min', 'Heart Rate Recovery (1 min)', 'cardiovascular', 'bpm', 'wearable',
     'Heart rate drop in first minute post-exercise. Strong predictor of cardiovascular fitness and mortality risk. >12 bpm is normal, >20 bpm is excellent. (Cole et al. NEJM 1999)'),

    ('walking_hr_avg', 'Walking Heart Rate Average', 'cardiovascular', 'bpm', 'wearable',
     'Average heart rate during walking. Lower values indicate better cardiovascular efficiency. Useful for tracking aerobic fitness without formal testing.'),

    ('cardio_recovery_score', 'Cardio Recovery Score', 'cardiovascular', 'score', 'computed',
     'Composite score from HR recovery, HRV trends, and resting HR. Range 0-100.')
ON CONFLICT (slug) DO NOTHING;

-- Sleep Quality & Breathing
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
    ('breathing_disturbances', 'Breathing Disturbances', 'respiratory', 'events/hr', 'wearable',
     'Apple Watch detected breathing disturbances during sleep. Proxy for Apnea-Hypopnea Index (AHI). <5 normal, 5-15 mild, 15-30 moderate, >30 severe.'),

    ('sleep_efficiency', 'Sleep Efficiency', 'sleep', 'percent', 'computed',
     'Percentage of time in bed actually asleep. (Total Sleep / Time in Bed) * 100. >85% is good, >90% is excellent.'),

    ('sleep_latency', 'Sleep Latency', 'sleep', 'min', 'computed',
     'Time from getting in bed to falling asleep. <15 min is normal, >30 min suggests insomnia.'),

    ('sleep_fragmentation', 'Sleep Fragmentation Index', 'sleep', 'score', 'computed',
     'Number of awakenings per hour of sleep. Lower is better. <5 is good.')
ON CONFLICT (slug) DO NOTHING;

-- Activity & Training Load
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
    ('physical_effort', 'Physical Effort', 'activity', 'score', 'wearable',
     'Apple proprietary metric combining movement intensity, heart rate elevation, and duration. Scale varies.'),

    ('training_load_acute', 'Acute Training Load', 'activity', 'AU', 'computed',
     'Rolling 7-day sum of training impulse (TRIMP). Represents recent training stress.'),

    ('training_load_chronic', 'Chronic Training Load', 'activity', 'AU', 'computed',
     'Rolling 28-day average of training impulse. Represents fitness/adaptation level.'),

    ('training_balance', 'Acute:Chronic Workload Ratio', 'activity', 'ratio', 'computed',
     'Ratio of acute to chronic training load. 0.8-1.3 is optimal zone. >1.5 indicates injury risk. (Gabbett 2016)'),

    ('exercise_intensity_zone', 'Exercise Intensity Zone', 'activity', 'enum', 'computed',
     'Time spent in HR zones: Z1 (recovery), Z2 (aerobic), Z3 (tempo), Z4 (threshold), Z5 (VO2max)')
ON CONFLICT (slug) DO NOTHING;

-- Circadian & Chronobiology
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
    ('circadian_amplitude', 'Circadian Amplitude', 'circadian', 'bpm', 'computed',
     'Difference between peak and trough heart rate across 24h cycle. Higher amplitude indicates stronger circadian rhythm. 30-50 bpm typical.'),

    ('circadian_phase', 'Circadian Phase', 'circadian', 'min_of_day', 'computed',
     'Time of day when heart rate reaches minimum (acrophase). Indicates chronotype and circadian alignment.'),

    ('light_exposure_timing', 'Light Exposure Timing', 'circadian', 'min_of_day', 'computed',
     'Median time of daylight exposure. Morning light advances circadian phase, evening delays it.')
ON CONFLICT (slug) DO NOTHING;

-- Mobility & Fall Risk
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
    ('walking_steadiness', 'Walking Steadiness', 'mobility', 'percent', 'wearable',
     'Apple assessment of gait stability and fall risk. >90% is stable, <70% indicates elevated fall risk.'),

    ('gait_speed', 'Gait Speed', 'mobility', 'm/s', 'wearable',
     'Walking speed as a vital sign. >1.0 m/s associated with longevity. <0.8 m/s indicates frailty risk. (Studenski 2011)'),

    ('mobility_score', 'Mobility Score', 'mobility', 'score', 'computed',
     'Composite of walking speed, steadiness, asymmetry, and double support time. Range 0-100.')
ON CONFLICT (slug) DO NOTHING;

-- Running Biomechanics
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
    ('running_power', 'Running Power', 'activity', 'W', 'wearable',
     'Metabolic power output during running. Useful for pacing and efficiency tracking.'),

    ('running_economy', 'Running Economy', 'activity', 'W/kg/speed', 'computed',
     'Power per kg body weight per unit speed. Lower is more efficient.'),

    ('vertical_oscillation', 'Vertical Oscillation', 'mobility', 'cm', 'wearable',
     'Vertical bounce during running. Lower is more efficient. Elite: <6cm, recreational: 8-12cm.'),

    ('ground_contact_time', 'Ground Contact Time', 'mobility', 'ms', 'wearable',
     'Time foot is on ground per stride. Shorter indicates better running form. Elite: <200ms, recreational: 250-300ms.'),

    ('stride_length', 'Running Stride Length', 'mobility', 'm', 'wearable',
     'Distance covered per running stride. Optimal varies by height and speed.')
ON CONFLICT (slug) DO NOTHING;

-- Environment & Lifestyle
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
    ('noise_exposure_avg', 'Average Noise Exposure', 'environment', 'dB', 'wearable',
     'Average environmental noise level. <70 dB safe indefinitely. >85 dB risk of hearing damage with prolonged exposure.'),

    ('noise_exposure_peak', 'Peak Noise Exposure', 'environment', 'dB', 'wearable',
     'Maximum noise exposure recorded. >100 dB can cause immediate hearing damage.'),

    ('headphone_exposure', 'Headphone Audio Exposure', 'environment', 'dB', 'wearable',
     'Average headphone audio level. WHO recommends <85 dB for safe listening.'),

    ('daylight_exposure', 'Daylight Exposure', 'circadian', 'min', 'wearable',
     'Time spent in bright outdoor light. 30+ min recommended for circadian health and vitamin D. (Roenneberg 2012)')
ON CONFLICT (slug) DO NOTHING;

-- Recovery & Readiness
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
    ('recovery_score', 'Recovery Score', 'recovery', 'score', 'computed',
     'Daily readiness assessment based on HRV, resting HR, sleep quality, and training load. Range 0-100. Similar to Whoop/Oura recovery.'),

    ('hrv_baseline', 'HRV Baseline', 'autonomic', 'ms', 'computed',
     'Rolling 7-day median HRV. Used as personal baseline for recovery assessment.'),

    ('hrv_deviation', 'HRV Deviation from Baseline', 'autonomic', 'percent', 'computed',
     'Current HRV as percentage of personal baseline. >100% indicates good recovery, <85% indicates need for rest.'),

    ('rhr_baseline', 'Resting HR Baseline', 'cardiovascular', 'bpm', 'computed',
     'Rolling 7-day median resting HR. Elevated RHR vs baseline indicates illness, stress, or overtraining.'),

    ('rhr_deviation', 'Resting HR Deviation', 'autonomic', 'bpm', 'computed',
     'Current resting HR minus baseline. >5 bpm elevation warrants attention.')
ON CONFLICT (slug) DO NOTHING;

-- Stress & Nervous System Balance
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
    ('stress_score', 'Stress Score', 'autonomic', 'score', 'computed',
     'Inferred stress level from HRV patterns, HR elevation, and activity context. Range 0-100. Not a direct measurement.'),

    ('autonomic_balance', 'Autonomic Balance Index', 'autonomic', 'ratio', 'computed',
     'Ratio of parasympathetic to sympathetic activity inferred from HRV metrics. >1 indicates recovery dominance.')
ON CONFLICT (slug) DO NOTHING;

-- Nutrition (if tracked)
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
    ('calories_consumed', 'Calories Consumed', 'nutrition', 'kcal', 'self_report',
     'Total dietary energy intake.'),

    ('protein_intake', 'Protein Intake', 'nutrition', 'g', 'self_report',
     'Daily protein consumption. RDA is 0.8g/kg, athletes may need 1.6-2.2g/kg.'),

    ('carb_intake', 'Carbohydrate Intake', 'nutrition', 'g', 'self_report',
     'Daily carbohydrate consumption.'),

    ('fat_intake', 'Fat Intake', 'nutrition', 'g', 'self_report',
     'Daily fat consumption.'),

    ('water_intake', 'Water Intake', 'nutrition', 'mL', 'self_report',
     'Daily water/fluid consumption. General target 2-3L.'),

    ('calorie_balance', 'Calorie Balance', 'nutrition', 'kcal', 'computed',
     'Calories consumed minus calories burned. Negative = deficit, positive = surplus.')
ON CONFLICT (slug) DO NOTHING;
