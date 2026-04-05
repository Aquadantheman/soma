"""Initialize the Soma database schema on local PostgreSQL (without TimescaleDB)."""

import psycopg2

DATABASE_URL = "postgresql://postgres:soma_dev@127.0.0.1:5432/soma"

# Schema without TimescaleDB-specific parts
INIT_SQL = """
-- Soma Database Schema (PostgreSQL without TimescaleDB)

-- BIOMARKER REGISTRY
CREATE TABLE IF NOT EXISTS biomarker_types (
    id          SERIAL PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    unit        TEXT NOT NULL,
    source_type TEXT NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Seed canonical biomarker types
INSERT INTO biomarker_types (slug, name, category, unit, source_type, description) VALUES
('hrv_rmssd',         'HRV RMSSD',                  'autonomic',  'ms',    'wearable',     'Root mean square of successive RR interval differences'),
('hrv_sdnn',          'HRV SDNN',                   'autonomic',  'ms',    'wearable',     'Standard deviation of NN intervals'),
('heart_rate',        'Heart Rate',                 'autonomic',  'bpm',   'wearable',     'Beats per minute'),
('heart_rate_resting','Resting Heart Rate',         'autonomic',  'bpm',   'wearable',     'Lowest resting HR in measurement window'),
('eda_tonic',         'EDA Tonic Level',            'autonomic',  'μS',    'wearable',     'Skin conductance baseline (sympathetic tone)'),
('eda_phasic_count',  'EDA Phasic Events',          'autonomic',  'count', 'wearable',     'Number of skin conductance responses per hour'),
('spo2',              'Blood Oxygen Saturation',    'autonomic',  'pct',   'wearable',     'SpO2 percentage'),
('respiratory_rate',  'Respiratory Rate',           'autonomic',  'brpm',  'wearable',     'Breaths per minute'),
('sleep_duration',    'Total Sleep Duration',       'sleep',      'min',   'wearable',     'Total minutes asleep'),
('sleep_rem_pct',     'REM Sleep Percentage',       'sleep',      'pct',   'wearable',     'Percentage of sleep in REM stage'),
('sleep_deep_pct',    'Deep Sleep Percentage',      'sleep',      'pct',   'wearable',     'Percentage of sleep in deep/N3 stage'),
('sleep_efficiency',  'Sleep Efficiency',           'sleep',      'pct',   'wearable',     'Time asleep / time in bed'),
('sleep_latency',     'Sleep Latency',              'sleep',      'min',   'wearable',     'Minutes to fall asleep'),
('sleep_awakenings',  'Sleep Awakenings',           'sleep',      'count', 'wearable',     'Number of awakenings per night'),
('steps',             'Step Count',                 'activity',   'count', 'wearable',     'Total steps in period'),
('active_energy',     'Active Energy',              'activity',   'kcal',  'wearable',     'Active calories burned'),
('activity_score',    'Activity Score',             'activity',   'score', 'wearable',     'Composite activity metric (device-specific)'),
('stand_hours',       'Stand Hours',                'activity',   'hrs',   'wearable',     'Hours with >1 min standing activity'),
('skin_temp_delta',   'Skin Temperature Delta',     'endocrine',  '°C',    'wearable',     'Deviation from personal baseline skin temp'),
('core_temp',         'Core Body Temperature',      'endocrine',  '°C',    'wearable',     'Core temperature estimate'),
('cortisol_sweat',    'Sweat Cortisol',             'endocrine',  'nmol/L','strip',        'Cortisol concentration in sweat sample'),
('glucose',           'Blood Glucose',              'endocrine',  'mg/dL', 'wearable',     'Continuous glucose monitor reading'),
('mood',              'Mood Rating',                'subjective', 'score', 'self_report',  '1-10 subjective mood score'),
('energy',            'Energy Rating',              'subjective', 'score', 'self_report',  '1-10 subjective energy score'),
('anxiety',           'Anxiety Rating',             'subjective', 'score', 'self_report',  '1-10 subjective anxiety score'),
('focus',             'Focus Rating',               'subjective', 'score', 'self_report',  '1-10 subjective focus score'),
('notes',             'Free Text Note',             'subjective', 'text',  'self_report',  'Unstructured daily note')
ON CONFLICT (slug) DO NOTHING;

-- DATA SOURCES
CREATE TABLE IF NOT EXISTS data_sources (
    id          SERIAL PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,
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
('generic_csv',  'Generic CSV Import')
ON CONFLICT (slug) DO NOTHING;

-- SIGNALS — the core time-series table
CREATE TABLE IF NOT EXISTS signals (
    time            TIMESTAMPTZ NOT NULL,
    biomarker_slug  TEXT        NOT NULL,
    value           DOUBLE PRECISION,
    value_text      TEXT,
    source_slug     TEXT        NOT NULL,
    window_seconds  INTEGER,
    quality         SMALLINT DEFAULT 100,
    blake3_hash     TEXT,
    raw_source_id   TEXT,
    meta            JSONB
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_signals_biomarker_time ON signals (biomarker_slug, time DESC);
CREATE INDEX IF NOT EXISTS idx_signals_source_time ON signals (source_slug, time DESC);
CREATE INDEX IF NOT EXISTS idx_signals_time ON signals (time DESC);

-- Unique constraint for deduplication
CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_unique
ON signals (time, biomarker_slug, source_slug)
WHERE raw_source_id IS NOT NULL;

-- PERSONAL BASELINE
CREATE TABLE IF NOT EXISTS baselines (
    id              SERIAL PRIMARY KEY,
    biomarker_slug  TEXT        NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    window_days     INTEGER     NOT NULL,
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

-- ANNOTATIONS
CREATE TABLE IF NOT EXISTS annotations (
    id          SERIAL PRIMARY KEY,
    time        TIMESTAMPTZ NOT NULL,
    duration_s  INTEGER,
    category    TEXT NOT NULL,
    label       TEXT NOT NULL,
    notes       TEXT,
    meta        JSONB
);

CREATE INDEX IF NOT EXISTS idx_annotations_time ON annotations (time DESC);
CREATE INDEX IF NOT EXISTS idx_annotations_category ON annotations (category, time DESC);

-- INGEST LOG
CREATE TABLE IF NOT EXISTS ingest_log (
    id              SERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    source_slug     TEXT        NOT NULL,
    file_path       TEXT,
    records_parsed  INTEGER DEFAULT 0,
    records_written INTEGER DEFAULT 0,
    records_skipped INTEGER DEFAULT 0,
    errors          INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'running',
    error_log       TEXT
);
"""

def main():
    print("Connecting to local PostgreSQL...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    print("Running schema initialization...")
    cur.execute(INIT_SQL)

    # Verify tables exist
    cur.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cur.fetchall()]
    print(f"Tables created: {', '.join(tables)}")

    # Check biomarker count
    cur.execute("SELECT COUNT(*) FROM biomarker_types")
    biomarker_count = cur.fetchone()[0]
    print(f"Biomarker types seeded: {biomarker_count}")

    cur.close()
    conn.close()
    print("\nDatabase initialized successfully!")

if __name__ == "__main__":
    main()
