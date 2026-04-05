# Soma

**Continuous biosignal integration for personal health.**

Soma is an open-source platform that aggregates, normalizes, and models continuous biological signals from wearables — building a longitudinal personal baseline that makes your physiological patterns legible for the first time.

## The Problem

Your health data is fragmented. Apple Watch, Whoop, Garmin, smart scales — each lives in its own silo. You walk into a doctor's appointment with memory instead of data. There's no unified view of *you* over time.

## What Soma Does

- **Ingests data** from Apple Health, Whoop, and file exports
- **Normalizes signals** into a unified time-series schema
- **Builds your personal baseline** — your normal, not the population's
- **Detects anomalies** and cross-signal correlations
- **Computes wellness scores** using Harmonic Mean across 6 domains
- **Identifies patterns** — sleep-HRV relationships, behavioral trends, seasonal effects
- **Provides explainability** — every score includes bottleneck analysis and actionable insights

## What Soma Doesn't Do

Soma is not a diagnostic tool. It does not replace clinical measurement. It builds a personal model from signals that are measurable — HRV, sleep architecture, activity patterns, body composition — and over time develops predictive validity specific to you.

## Architecture

```
core/       Rust    — high-performance ingestion, normalization, BLAKE3 hashing
api/        Python  — FastAPI REST layer with OAuth2 integrations
science/    Python  — signal processing, baseline modeling, statistical analysis
docs/       —         architecture and implementation documentation
```

## Stack

- **Rust** — core ingestion pipeline (handles 500MB+ Apple Health exports)
- **Python** — scientific computing (NumPy, SciPy, scikit-learn)
- **TimescaleDB** — time-series PostgreSQL for efficient signal queries
- **FastAPI** — REST API with OpenAPI documentation
- **Docker** — containerized local development

## Getting Started

```bash
# 1. Start TimescaleDB
docker-compose up -d

# 2. Configure environment
cp .env.example .env
# Edit .env with your database credentials

# 3. Build Rust ingestion core
cd core && cargo build --release

# 4. Install Python dependencies
pip install -r api/requirements.txt

# 5. Run database migrations
alembic upgrade head

# 6. Start the API
uvicorn api.main:app --reload
```

Then open http://localhost:8000/docs for interactive API documentation.

## Data Sources

### Apple Health (File Import)
Export your Apple Health data as XML and ingest via the Rust core:
```bash
./core/target/release/soma-core ingest --source apple-health --path export.xml
```

### Whoop (OAuth2 API)
1. Register at [developer.whoop.com](https://developer.whoop.com)
2. Add your credentials to `.env`
3. Connect via `GET /v1/oauth/authorize/whoop`
4. Sync data via `POST /v1/sync/whoop`

## Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /v1/status` | System health and data coverage |
| `GET /v1/signals` | Query signals with filters |
| `GET /v1/baselines` | View computed personal baselines |
| `POST /v1/baselines/deviation` | Check a value against your baseline |
| `GET /v1/analysis/holistic` | Full multi-domain wellness analysis |
| `GET /v1/oauth/authorize/whoop` | Connect Whoop account |
| `POST /v1/sync/whoop` | Sync Whoop data |

## Wellness Scoring

Soma synthesizes signals into a 6-domain wellness score using **Harmonic Mean** — an approach that naturally penalizes imbalance (based on V-Clock biological age research).

| Domain | Key Biomarkers |
|--------|----------------|
| Cardiovascular | HRV (RMSSD/SDNN), Resting HR, VO2 Max |
| Sleep | Duration, Efficiency, REM/Deep/Light stages |
| Activity | Steps, Active Energy, Exercise Minutes |
| Recovery | HRV Recovery, Training Load (ACWR) |
| Body Composition | Weight, Body Fat %, BMI |
| Mobility | Walking Speed, Steadiness |

Every score includes **explainability**:
- Bottleneck analysis (which domain is holding you back)
- Imbalance penalty (cost of uneven domains)
- Actionable recommendations

## Philosophy

Your biological data belongs to you. Soma runs entirely on your machine. No cloud required. No telemetry. No data leaves unless you explicitly export it.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — design decisions and data flow
- [Roadmap](docs/ROADMAP.md) — development phases and progress
- [Holistic Implementation](docs/HOLISTIC_INSIGHTS_IMPLEMENTATION.md) — wellness scoring details

## License

MIT
