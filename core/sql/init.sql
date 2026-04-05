-- Soma Database Schema
-- TimescaleDB + PostgreSQL

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ─────────────────────────────────────────
-- BIOMARKER REGISTRY
-- The canonical list of every signal type Soma understands
-- ─────────────────────────────────────────
CREATE TABLE biomarker_types (
    id          SERIAL PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,   -- e.g. 'hrv_rmssd', 'eda_tonic', 'sleep_rem_pct'
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,          -- 'autonomic', 'endocrine', 'sleep', 'activity', 'subjective'
    unit        TEXT NOT NULL,          -- 'ms', 'μS', 'pct', 'bpm', 'score'
    source_type TEXT NOT NULL,          -- 'wearable', 'phone', 'strip', 'self_report'
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Seed canonical biomarker types
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
-- Autonomic
('hrv_rmssd',         'HRV RMSSD',                  'autonomic',  'ms',    'wearable',     'Root mean square of successive RR interval differences'),
('hrv_sdnn',          'HRV SDNN',                   'autonomic',  'ms',    'wearable',     'Standard deviation of NN intervals'),
('heart_rate',        'Heart Rate',                 'autonomic',  'bpm',   'wearable',     'Beats per minute'),
('heart_rate_resting','Resting Heart Rate',         'autonomic',  'bpm',   'wearable',     'Lowest resting HR in measurement window'),
('eda_tonic',         'EDA Tonic Level',            'autonomic',  'μS',    'wearable',     'Skin conductance baseline (sympathetic tone)'),
('eda_phasic_count',  'EDA Phasic Events',          'autonomic',  'count', 'wearable',     'Number of skin conductance responses per hour'),
('spo2',              'Blood Oxygen Saturation',    'autonomic',  'pct',   'wearable',     'SpO2 percentage'),
('respiratory_rate',  'Respiratory Rate',           'autonomic',  'brpm',  'wearable',     'Breaths per minute'),
-- Sleep (raw stage durations from Apple Health)
('sleep_rem',         'REM Sleep Duration',         'sleep',      'min',   'wearable',     'Minutes in REM sleep stage'),
('sleep_deep',        'Deep Sleep Duration',        'sleep',      'min',   'wearable',     'Minutes in deep/N3 sleep stage'),
('sleep_core',        'Core Sleep Duration',        'sleep',      'min',   'wearable',     'Minutes in core/N2 sleep stage'),
('sleep_in_bed',      'Time In Bed',                'sleep',      'min',   'wearable',     'Total minutes in bed (may not be asleep)'),
-- Sleep (computed/derived metrics)
('sleep_duration',    'Total Sleep Duration',       'sleep',      'min',   'wearable',     'Total minutes asleep (sum of stages)'),
('sleep_rem_pct',     'REM Sleep Percentage',       'sleep',      'pct',   'wearable',     'Percentage of sleep in REM stage'),
('sleep_deep_pct',    'Deep Sleep Percentage',      'sleep',      'pct',   'wearable',     'Percentage of sleep in deep/N3 stage'),
('sleep_core_pct',    'Core Sleep Percentage',      'sleep',      'pct',   'wearable',     'Percentage of sleep in core/N2 stage'),
('sleep_efficiency',  'Sleep Efficiency',           'sleep',      'pct',   'wearable',     'Time asleep / time in bed'),
('sleep_latency',     'Sleep Latency',              'sleep',      'min',   'wearable',     'Minutes to fall asleep'),
('sleep_awakenings',  'Sleep Awakenings',           'sleep',      'count', 'wearable',     'Number of awakenings per night'),
-- Activity
('steps',             'Step Count',                 'activity',   'count', 'wearable',     'Total steps in period'),
('active_energy',     'Active Energy',              'activity',   'kcal',  'wearable',     'Active calories burned'),
('basal_energy',      'Basal Energy',               'activity',   'kcal',  'wearable',     'Basal metabolic calories burned'),
('activity_score',    'Activity Score',             'activity',   'score', 'wearable',     'Composite activity metric (device-specific)'),
('stand_hours',       'Stand Hours',                'activity',   'hrs',   'wearable',     'Hours with >1 min standing activity'),
('stand_time',        'Stand Time',                 'activity',   'min',   'wearable',     'Minutes standing'),
('exercise_time',     'Exercise Time',              'activity',   'min',   'wearable',     'Minutes of exercise activity'),
('flights_climbed',   'Flights Climbed',            'activity',   'count', 'wearable',     'Number of floor equivalents climbed'),
-- Mobility/Gait
('walking_speed',     'Walking Speed',              'mobility',   'm/s',   'wearable',     'Average walking speed'),
('walking_step_length','Walking Step Length',       'mobility',   'm',     'wearable',     'Average step length while walking'),
('walking_asymmetry', 'Walking Asymmetry',          'mobility',   'pct',   'wearable',     'Percentage difference between left/right steps'),
('walking_double_support','Walking Double Support', 'mobility',   'pct',   'wearable',     'Percentage of time with both feet on ground'),
-- Environment/Circadian
('time_in_daylight',  'Time in Daylight',           'circadian',  'min',   'wearable',     'Minutes exposed to outdoor daylight'),
('physical_effort',   'Physical Effort',            'activity',   'score', 'wearable',     'Apple Physical Effort metric'),
-- Cardiorespiratory Fitness
('vo2_max',           'VO2 Max',                    'fitness',    'mL/kg/min', 'wearable', 'Maximal oxygen uptake - gold standard cardiorespiratory fitness'),
-- Body Composition
('body_mass',         'Body Mass',                  'body_composition', 'kg',  'wearable', 'Body weight in kilograms'),
('body_fat_percentage','Body Fat Percentage',       'body_composition', 'pct', 'wearable', 'Body fat as percentage of total mass'),
('lean_body_mass',    'Lean Body Mass',             'body_composition', 'kg',  'wearable', 'Lean mass (total mass minus fat mass)'),
('body_mass_index',   'Body Mass Index',            'body_composition', 'kg/m2','wearable','BMI = weight(kg) / height(m)^2'),
('height',            'Height',                     'body_composition', 'm',   'wearable', 'Standing height in meters'),
('waist_circumference','Waist Circumference',       'body_composition', 'cm',  'wearable', 'Waist circumference in centimeters'),
-- Temperature
('skin_temp_delta',   'Skin Temperature Delta',     'endocrine',  '°C',    'wearable',     'Deviation from personal baseline skin temp'),
('core_temp',         'Core Body Temperature',      'endocrine',  '°C',    'wearable',     'Core temperature estimate'),
-- Endocrine proxies
('cortisol_sweat',    'Sweat Cortisol',             'endocrine',  'nmol/L','strip',        'Cortisol concentration in sweat sample'),
('glucose',           'Blood Glucose',              'endocrine',  'mg/dL', 'wearable',     'Continuous glucose monitor reading'),
-- Subjective
('mood',              'Mood Rating',                'subjective', 'score', 'self_report',  '1-10 subjective mood score'),
('energy',            'Energy Rating',              'subjective', 'score', 'self_report',  '1-10 subjective energy score'),
('anxiety',           'Anxiety Rating',             'subjective', 'score', 'self_report',  '1-10 subjective anxiety score'),
('focus',             'Focus Rating',               'subjective', 'score', 'self_report',  '1-10 subjective focus score'),
('notes',             'Free Text Note',             'subjective', 'text',  'self_report',  'Unstructured daily note'),

-- ═══════════════════════════════════════════════════════════════════════════════
-- CLINICAL-GRADE BIOMARKERS (Added 2026-03)
-- All metrics below are peer-reviewed, non-redundant, and have established
-- clinical reference ranges. See validation.rs for physiological limits.
-- ═══════════════════════════════════════════════════════════════════════════════

-- Cardiovascular (ACC/AHA 2017 Guidelines)
('bp_systolic',       'Systolic Blood Pressure',    'cardiovascular', 'mmHg', 'wearable',
    'Peak arterial pressure during ventricular systole. Clinical thresholds: <120 optimal, 120-129 elevated, 130-139 Stage 1 HTN, ≥140 Stage 2 HTN'),
('bp_diastolic',      'Diastolic Blood Pressure',   'cardiovascular', 'mmHg', 'wearable',
    'Minimum arterial pressure during ventricular diastole. Clinical threshold: <80 optimal, ≥90 hypertension'),

-- Circadian Timing (Roenneberg 2004, Phillips 2017)
-- Times stored as minutes since midnight for computational efficiency
('sleep_onset_time',  'Sleep Onset Time',           'circadian', 'min_of_day', 'wearable',
    'Clock time of sleep onset as minutes since midnight (0-1439). E.g., 23:30 = 1410, 01:30 = 90'),
('sleep_offset_time', 'Sleep Offset Time',          'circadian', 'min_of_day', 'wearable',
    'Clock time of final awakening as minutes since midnight (0-1439)'),
('sleep_midpoint',    'Sleep Midpoint',             'circadian', 'min_of_day', 'computed',
    'Temporal midpoint of sleep episode. Chronotype marker: <180 extreme early, 180-240 early, 240-300 intermediate, 300-360 late, >360 extreme late'),
('sleep_regularity_index', 'Sleep Regularity Index', 'circadian', 'score', 'computed',
    'Phillips et al. 2017: Probability that any two timepoints 24h apart are in same sleep/wake state. Range -100 (random) to +100 (perfectly regular). <60 associated with mood disorders'),
('social_jetlag',     'Social Jet Lag',             'circadian', 'min', 'computed',
    'Wittmann 2006: |weekend_midpoint - weekday_midpoint|. >120 min associated with obesity, depression, metabolic syndrome'),

-- Respiratory/Sleep Apnea (AASM 2017 Guidelines)
('ahi',               'Apnea-Hypopnea Index',       'respiratory', 'events/hr', 'wearable',
    'Apnea + hypopnea events per hour. AASM thresholds: <5 normal, 5-14 mild, 15-29 moderate, ≥30 severe OSA'),
('oxygen_desat_index','Oxygen Desaturation Index',  'respiratory', 'events/hr', 'wearable',
    'Number of ≥3% SpO2 desaturation events per hour. Correlates with AHI but captures distinct hypoxic burden'),

-- Activity (WHO 2020 Physical Activity Guidelines)
('distance_walking_running', 'Walking + Running Distance', 'activity', 'm', 'wearable',
    'Total distance covered walking and running. Not redundant with steps: distance = steps × stride_length, where stride varies with height/speed/fatigue'),
('exercise_intensity_min', 'MVPA Minutes',          'activity', 'min', 'wearable',
    'Minutes in moderate-to-vigorous physical activity (>3 METs or HR >64% max). WHO recommends 150-300 min/week moderate'),

-- Hormonal/Menstrual (ACOG Guidelines, de Zambotti 2015)
('menstrual_cycle_day', 'Menstrual Cycle Day',      'hormonal', 'day', 'wearable',
    'Day of menstrual cycle (1 = first day of period). Phases: 1-5 menstrual, 6-13 follicular, ~14 ovulation, 15-28 luteal'),
('menstrual_flow',    'Menstrual Flow',             'hormonal', 'enum', 'self_report',
    'Subjective flow intensity: 0=none, 1=spotting, 2=light, 3=medium, 4=heavy'),
('basal_body_temp',   'Basal Body Temperature',     'hormonal', '°C', 'wearable',
    'Core temperature measured immediately upon waking. 0.3-0.5°C rise indicates ovulation. Normal: 36.1-36.4 follicular, 36.4-37.0 luteal');

-- ─────────────────────────────────────────
-- DATA SOURCES
-- Tracks where data came from
-- ─────────────────────────────────────────
CREATE TABLE data_sources (
    id          SERIAL PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,  -- 'apple_health', 'garmin', 'oura', 'manual'
    name        TEXT NOT NULL,
    version     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO data_sources (slug, name) VALUES
('apple_health', 'Apple Health'),
('garmin',       'Garmin Connect'),
('oura',         'Oura Ring'),
('whoop',        'Whoop'),
('fitbit',       'Fitbit'),
('manual',       'Manual Entry'),
('generic_csv',  'Generic CSV Import');

-- ─────────────────────────────────────────
-- SIGNALS — the core time-series table
-- Every measurement lives here
-- ─────────────────────────────────────────
CREATE TABLE signals (
    time            TIMESTAMPTZ NOT NULL,
    biomarker_slug  TEXT        NOT NULL REFERENCES biomarker_types(slug),
    value           DOUBLE PRECISION,
    value_text      TEXT,                    -- for subjective notes
    source_slug     TEXT        NOT NULL REFERENCES data_sources(slug),
    window_seconds  INTEGER,                 -- measurement window (e.g. 3600 for hourly avg)
    quality         SMALLINT DEFAULT 100,    -- 0-100 data quality score
    blake3_hash     TEXT,                    -- integrity hash of raw source record
    raw_source_id   TEXT,                    -- original ID from source system
    meta            JSONB                    -- flexible extra fields
);

-- Convert to TimescaleDB hypertable
SELECT create_hypertable('signals', 'time');

-- Indexes
CREATE INDEX ON signals (biomarker_slug, time DESC);
CREATE INDEX ON signals (source_slug, time DESC);
CREATE UNIQUE INDEX ON signals (time, biomarker_slug, source_slug)
    WHERE raw_source_id IS NOT NULL;

-- ─────────────────────────────────────────
-- PERSONAL BASELINE
-- Rolling personal norms, updated by science layer
-- ─────────────────────────────────────────
CREATE TABLE baselines (
    id              SERIAL PRIMARY KEY,
    biomarker_slug  TEXT        NOT NULL REFERENCES biomarker_types(slug),
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    window_days     INTEGER     NOT NULL,    -- baseline computed over N days
    mean            DOUBLE PRECISION,
    std_dev         DOUBLE PRECISION,
    p10             DOUBLE PRECISION,
    p25             DOUBLE PRECISION,
    p50             DOUBLE PRECISION,
    p75             DOUBLE PRECISION,
    p90             DOUBLE PRECISION,
    sample_count    INTEGER,
    UNIQUE (biomarker_slug, window_days, computed_at)
);

-- ─────────────────────────────────────────
-- ANNOTATIONS
-- Events to correlate against signals
-- ─────────────────────────────────────────
CREATE TABLE annotations (
    id          SERIAL PRIMARY KEY,
    time        TIMESTAMPTZ NOT NULL,
    duration_s  INTEGER,                     -- null = point event
    category    TEXT NOT NULL,               -- 'medication', 'exercise', 'stress', 'illness', 'social'
    label       TEXT NOT NULL,               -- 'started sertraline 50mg', 'ran 5k', etc.
    notes       TEXT,
    meta        JSONB
);

CREATE INDEX ON annotations (time DESC);
CREATE INDEX ON annotations (category, time DESC);

-- ─────────────────────────────────────────
-- INGEST LOG
-- Tracks every import run for auditability
-- ─────────────────────────────────────────
CREATE TABLE ingest_log (
    id              SERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    source_slug     TEXT        NOT NULL,
    file_path       TEXT,
    records_parsed  INTEGER DEFAULT 0,
    records_written INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    errors          INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'running',  -- 'running', 'complete', 'failed'
    error_log       TEXT
);
