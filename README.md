# Soma

**Continuous biosignal integration for personal mental health.**

Soma is an open-source platform that aggregates, normalizes, and models continuous biological signals from wearables and passive phone sensors — building a longitudinal personal baseline that makes your neurochemical patterns legible for the first time.

## The Problem

Psychiatry is the only medical specialty that treats organ dysfunction without measuring the organ. Treatment is trial-and-error. Data is siloed across devices, providers, and time. You walk into an appointment with memory instead of data.

## What Soma Does

- Ingests data from Apple Health, Garmin, Oura, and generic CSV sources
- Normalizes heterogeneous signals into a unified time-series schema
- Builds a personal longitudinal baseline — your normal, not the population's
- Detects anomalies and correlations across signals
- **Computes multi-domain wellness scores** using Harmonic Mean (6 domains)
- **Identifies cross-domain patterns** (paradoxes, behavioral patterns, interconnections)
- Exports clinically meaningful summaries with actionable recommendations

## What Soma Doesn't Do

Soma is not a diagnostic tool. It does not measure dopamine, serotonin, or other neurotransmitters directly. It builds a personal model from signals that are measurable — HRV, EDA, sleep architecture, cortisol proxies, activity patterns — and over time develops predictive validity specific to you.

## Architecture

```
core/       Rust    — ingestion, normalization, BLAKE3 integrity, DB writes
science/    Python  — signal processing, baseline modeling, correlation
api/        Python  — FastAPI REST layer
app/        React   — dashboard (future)
proto/      Protobuf — shared data schemas
```

## Stack

- **Rust** — core ingestion and processing pipeline
- **Python** — scientific computing (NumPy, SciPy, scikit-learn)
- **TimescaleDB** — time-series PostgreSQL
- **FastAPI** — REST API
- **Protocol Buffers** — cross-language data schemas
- **Docker** — local dev environment

## Getting Started

```bash
# Start TimescaleDB locally
docker-compose up -d

# Build Rust core
cd core && cargo build

# Install Python science layer
cd science && pip install -e ".[dev]"

# Install API layer
pip install -r api/requirements.txt

# Run ingestion on an Apple Health export
soma-core ingest --source apple_health --path ~/export.xml
```

## API

Start the REST API:

```bash
uvicorn api.main:app --reload
```

Then open http://localhost:8000/docs for interactive API documentation.

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /status` | System health and data coverage |
| `GET /signals` | Query signals with filters |
| `GET /signals/latest` | Latest reading per biomarker |
| `GET /baselines` | View computed baselines |
| `POST /baselines/compute` | Trigger baseline computation |
| `POST /baselines/deviation` | Check value against baseline |
| `GET /annotations` | List life events |
| `POST /annotations` | Log a life event |
| `GET /analysis/holistic` | **Full holistic wellness analysis** |
| `GET /analysis/holistic/wellness-score` | Multi-domain wellness score |

## CLI Dashboard

View your data from the terminal:

```bash
# System status and coverage
python -m soma.cli status

# View computed baselines
python -m soma.cli baselines

# Recent signals for a biomarker
python -m soma.cli signals hrv_rmssd 14

# Check a value against your baseline
python -m soma.cli check hrv_rmssd 28.5
```

## Holistic Analysis

Soma synthesizes findings across all biomarker domains into a unified wellness assessment:

### 6-Domain Wellness Score (Harmonic Mean)

| Domain | Key Biomarkers |
|--------|----------------|
| Cardiovascular | HRV, Resting HR, VO2 Max |
| Sleep | Duration, Architecture, Efficiency |
| Activity | Steps, Active Energy, Exercise Time |
| Recovery | HRV Recovery, Training Load |
| Body Composition | Weight, Body Fat %, BMI |
| Mobility | Walking Speed, Steadiness (clinical "sixth vital sign") |

The overall score uses **Harmonic Mean** rather than simple averaging, which naturally penalizes imbalance. This approach is based on V-Clock biological age research showing that vector (domain-specific) approaches capture 1.78x more predictive information than scalar approaches.

### Explainability

Every wellness score includes:
- **Arithmetic Mean** — what simple averaging would give
- **Imbalance Penalty** — how much imbalance costs you
- **Bottleneck Domain** — which area is holding your score back
- **Bottleneck Impact** — potential points gained by improving it

### Advanced Features

- **Simpson's Paradox Detection** — identifies misleading correlations
- **Behavioral Pattern Recognition** — compensatory exercise, weekend warrior, seasonal patterns
- **Cross-Domain Interconnections** — lagged correlations (e.g., sleep → next-day HRV)
- **Risk Factor Synthesis** — combines signals into actionable risk assessments
- **Evidence-Based Recommendations** — personalized, prioritized actions

See `docs/HOLISTIC_INSIGHTS_IMPLEMENTATION.md` for full details.

## Roadmap

See `docs/ROADMAP.md`

## Philosophy

Your biological data belongs to you. Soma is built open-source from day one. No cloud required. No data leaves your machine unless you explicitly export it.
