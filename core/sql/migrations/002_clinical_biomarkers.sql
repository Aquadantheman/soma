-- Migration: Add Clinical-Grade Biomarkers
-- Date: 2026-03-07
-- Description: Adds peer-reviewed, non-redundant biomarkers with clinical reference ranges
--
-- References:
--   - ACC/AHA 2017 Hypertension Guidelines
--   - AASM 2017 Sleep Apnea Guidelines
--   - Roenneberg 2004 (MCTQ chronotype)
--   - Phillips 2017 (Sleep Regularity Index)
--   - Wittmann 2006 (Social Jet Lag)
--   - WHO 2020 Physical Activity Guidelines
--   - ACOG Menstrual Cycle Guidelines
--   - de Zambotti 2015 (Menstrual cycle & sleep)

-- Cardiovascular (ACC/AHA 2017 Guidelines)
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
('bp_systolic', 'Systolic Blood Pressure', 'cardiovascular', 'mmHg', 'wearable',
    'Peak arterial pressure during ventricular systole. Clinical thresholds: <120 optimal, 120-129 elevated, 130-139 Stage 1 HTN, ≥140 Stage 2 HTN'),
('bp_diastolic', 'Diastolic Blood Pressure', 'cardiovascular', 'mmHg', 'wearable',
    'Minimum arterial pressure during ventricular diastole. Clinical threshold: <80 optimal, ≥90 hypertension')
ON CONFLICT (slug) DO NOTHING;

-- Circadian Timing (Roenneberg 2004, Phillips 2017)
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
('sleep_onset_time', 'Sleep Onset Time', 'circadian', 'min_of_day', 'wearable',
    'Clock time of sleep onset as minutes since midnight (0-1439). E.g., 23:30 = 1410, 01:30 = 90'),
('sleep_offset_time', 'Sleep Offset Time', 'circadian', 'min_of_day', 'wearable',
    'Clock time of final awakening as minutes since midnight (0-1439)'),
('sleep_midpoint', 'Sleep Midpoint', 'circadian', 'min_of_day', 'computed',
    'Temporal midpoint of sleep episode. Chronotype marker: <180 extreme early, 180-240 early, 240-300 intermediate, 300-360 late, >360 extreme late'),
('sleep_regularity_index', 'Sleep Regularity Index', 'circadian', 'score', 'computed',
    'Phillips et al. 2017: Probability that any two timepoints 24h apart are in same sleep/wake state. Range -100 (random) to +100 (perfectly regular). <60 associated with mood disorders'),
('social_jetlag', 'Social Jet Lag', 'circadian', 'min', 'computed',
    'Wittmann 2006: |weekend_midpoint - weekday_midpoint|. >120 min associated with obesity, depression, metabolic syndrome')
ON CONFLICT (slug) DO NOTHING;

-- Respiratory/Sleep Apnea (AASM 2017 Guidelines)
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
('ahi', 'Apnea-Hypopnea Index', 'respiratory', 'events/hr', 'wearable',
    'Apnea + hypopnea events per hour. AASM thresholds: <5 normal, 5-14 mild, 15-29 moderate, ≥30 severe OSA'),
('oxygen_desat_index', 'Oxygen Desaturation Index', 'respiratory', 'events/hr', 'wearable',
    'Number of ≥3% SpO2 desaturation events per hour. Correlates with AHI but captures distinct hypoxic burden')
ON CONFLICT (slug) DO NOTHING;

-- Activity (WHO 2020 Physical Activity Guidelines)
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
('distance_walking_running', 'Walking + Running Distance', 'activity', 'm', 'wearable',
    'Total distance covered walking and running. Not redundant with steps: distance = steps × stride_length, where stride varies with height/speed/fatigue'),
('exercise_intensity_min', 'MVPA Minutes', 'activity', 'min', 'wearable',
    'Minutes in moderate-to-vigorous physical activity (>3 METs or HR >64% max). WHO recommends 150-300 min/week moderate')
ON CONFLICT (slug) DO NOTHING;

-- Hormonal/Menstrual (ACOG Guidelines, de Zambotti 2015)
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
('menstrual_cycle_day', 'Menstrual Cycle Day', 'hormonal', 'day', 'wearable',
    'Day of menstrual cycle (1 = first day of period). Phases: 1-5 menstrual, 6-13 follicular, ~14 ovulation, 15-28 luteal'),
('menstrual_flow', 'Menstrual Flow', 'hormonal', 'enum', 'self_report',
    'Subjective flow intensity: 0=none, 1=spotting, 2=light, 3=medium, 4=heavy'),
('basal_body_temp', 'Basal Body Temperature', 'hormonal', '°C', 'wearable',
    'Core temperature measured immediately upon waking. 0.3-0.5°C rise indicates ovulation. Normal: 36.1-36.4 follicular, 36.4-37.0 luteal')
ON CONFLICT (slug) DO NOTHING;

-- Add Withings as a data source (primary BP device)
INSERT INTO data_sources (slug, name) VALUES
('withings', 'Withings')
ON CONFLICT (slug) DO NOTHING;

-- Add Clue/Flo as menstrual tracking sources
INSERT INTO data_sources (slug, name) VALUES
('clue', 'Clue'),
('flo', 'Flo')
ON CONFLICT (slug) DO NOTHING;
