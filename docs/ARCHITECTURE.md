# Soma Architecture

## Core Principle

Soma is a personal biosignal integration layer. It does not replace clinical tools — it fills the gap between clinical appointments by giving you a continuous, legible picture of your physiology.

## Data Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   DATA SOURCES  │     │   INGESTION     │     │    STORAGE      │     │    ANALYSIS     │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│                 │     │                 │     │                 │     │                 │
│ Apple Health ───┼────►│ Rust Core       │     │ TimescaleDB     │     │ Baselines       │
│ (XML export)    │     │ • Parse         │     │                 │     │ • Personal norm │
│                 │     │ • Normalize     │────►│ signals         │────►│ • Deviation     │
│ Whoop ──────────┼────►│ • BLAKE3 hash   │     │ baselines       │     │                 │
│ (OAuth2 API)    │     │ • Deduplicate   │     │ annotations     │     │ Holistic        │
│                 │     │                 │     │ oauth_tokens    │     │ • 6-domain score│
│ Future:         │     │ Python Sync     │     │ ingest_log      │     │ • Correlations  │
│ • Garmin        │     │ • OAuth flow    │     │                 │     │ • Patterns      │
│ • Oura          │     │ • API polling   │     │                 │     │                 │
│ • CGM           │     │ • Rate limiting │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
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

## Analysis Pipeline

```
Raw Signals
    │
    ├──► Proven Analysis ──────► Circadian rhythms, weekly patterns, trends
    │
    ├──► Advanced Analysis ────► Cross-biomarker correlations, recovery modeling
    │
    ├──► Derived Metrics ──────► Training load (ACWR), autonomic balance, stress index
    │
    └──► Holistic Synthesis
              │
              ├──► 6-domain wellness score (Harmonic Mean)
              ├──► Cross-domain interconnections
              ├──► Behavioral pattern detection
              └──► Personalized recommendations
```

## API Layer

The FastAPI layer provides:
- **RESTful endpoints** with OpenAPI documentation
- **OAuth2 integration** for external services (Whoop)
- **Rate limiting** and **API key authentication**
- **Background sync jobs** for API-based data sources
- **Caching** with Redis (optional)

## Data Ownership

All data is stored locally by default. No telemetry. No cloud sync unless explicitly configured. The database runs in Docker on your machine. You own your data.
