# Soma Architecture

## Core Principle

Soma is a personal biosignal integration layer. It does not replace clinical tools —
it fills the enormous gap between clinical appointments by giving you and your provider
a continuous, legible picture of your biology.

## Data Flow

```
[Sources]          [Core/Rust]           [TimescaleDB]      [Science/Python]     [API]
Apple Health  ──►  Ingest                signals table  ──►  Baseline model  ──►  FastAPI
Garmin        ──►  Normalize    ──────►  baselines      ──►  Anomaly detect  ──►  REST
Oura          ──►  Validate              annotations         Correlations         endpoints
Phone sensors ──►  Hash (BLAKE3)
Manual entry  ──►  Store
```

## Design Decisions

### Why TimescaleDB
Time-series data has specific query patterns: windowed aggregations, time-bucketing,
range queries by time. TimescaleDB adds these as first-class operations on top of
PostgreSQL. Everything is still standard SQL. Scales from laptop to multi-node without
changing application code.

### Why Rust for core
The ingestion pipeline needs to be fast, correct, and long-lived. Apple Health exports
can be 500MB+ XML files. Rust gives us zero-copy parsing, strong type safety, and
memory efficiency. BLAKE3 hashing for integrity is a natural fit.

### Why Python for science
NumPy, SciPy, scikit-learn, neurokit2 — the signal processing ecosystem is Python.
The science layer evolves faster than the ingestion layer. Keeping them separate lets
each evolve at its own pace.

### Why BLAKE3 hashing
Every raw record gets hashed before transformation. This gives us:
- Deduplication across multiple imports of the same source file
- Auditability — we can prove what raw data produced what signals
- Integrity verification — the pipeline hasn't corrupted data

### Why personal baseline before population comparison
Population HRV norms vary enormously by age, fitness, and genetics.
What matters clinically is YOUR normal and deviations from it.
A 28ms RMSSD might be normal for one person and a significant drop for another.
Soma builds your personal distribution first, then flags deviations from that.

### Why Harmonic Mean for wellness scoring
Traditional health apps average domain scores arithmetically:
- Scores [90, 90, 90, 90, 90, 30] → Average: 80

But this misses clinical reality — a severely weak domain (e.g., sleep=30)
impacts overall health regardless of other metrics. Harmonic mean naturally penalizes this:
- Scores [90, 90, 90, 90, 90, 30] → Harmonic: 64

This approach is based on V-Clock biological age research showing that vector
(organ-specific) approaches capture 1.78x more predictive information for
mortality than scalar (simple average) approaches.

### Why Mobility as "Sixth Vital Sign"
Walking speed is established in clinical literature as predictive of mortality,
hospitalization, and functional decline. We include it as a distinct domain
with confound-controlled trend analysis (97% of walking speed decline is real,
only 3% confounded by activity level or season).

## Science Layer Architecture

```
[Raw Signals]
     │
     ▼
[Proven Analysis]     ─► Circadian, weekly patterns, trends, anomalies
     │
     ▼
[Advanced Analysis]   ─► Correlations, recovery, seasonality, readiness
     │
     ▼
[Derived Metrics]     ─► Nocturnal dip, training load, autonomic balance
     │
     ▼
[Holistic Synthesis]  ─► 6-domain wellness score (Harmonic Mean)
     │                   Cross-domain interconnections
     │                   Paradox detection (Simpson's)
     │                   Behavioral patterns
     │                   Risk factors & recommendations
     │
     ▼
[Explainable Output]  ─► Arithmetic mean comparison
                         Imbalance penalty
                         Bottleneck analysis
                         Actionable recommendations
```

## Data Ownership

All data is stored locally by default. No telemetry. No cloud sync unless explicitly
configured. The database runs in Docker on your own machine. You own your data.
