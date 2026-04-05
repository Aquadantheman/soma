# Soma

**From biosignal intelligence to active wellness.**

Soma is an open-source platform that aggregates biological signals from wearables and smart devices, builds a personal physiological baseline, and uses that context to generate adaptive movement programming — workouts, yoga, mobility, cardio, and recovery — tailored to your body's actual state, your goals, your equipment, and your pharmacological profile.

No other platform connects what your body is doing (biometrics), what's modifying your biology (medications and supplements), what you have access to (equipment and environment), and what you're working toward (goals) into a single system that acts on all of it.

## The Problem

Fitness apps generate workouts in a vacuum. They don't know you slept poorly. They don't know your medication elevates your heart rate. They don't know your body fat scale readings shifted because you started creatine, not because you gained fat. They don't know you're training for a wedding in September or recovering from a knee injury.

Your health data lives in silos — WHOOP tracks recovery, Renpho tracks body composition, Apple Health aggregates steps, and your workout app ignores all of it. You are the integration layer, manually interpreting one system's output to adjust another.

Soma eliminates that gap. It builds a unified, longitudinal model of *you* — your physiology, your chemistry, your patterns — and uses it to program movement that's appropriate for your body *today*, while systematically progressing toward your goals over weeks and months.

## What Soma Does

### Context Engine (Exists)
- **Ingests biosignal data** from WHOOP, Apple Health, Renpho (via Terra API), and file exports
- **Normalizes signals** into a unified time-series schema (TimescaleDB)
- **Builds personal baselines** — your normal, not population averages
- **Detects anomalies** and cross-signal correlations
- **Computes 6-domain wellness scores** using Harmonic Mean (cardiovascular, sleep, activity, recovery, body composition, mobility)
- **Identifies patterns** — sleep-HRV relationships, behavioral trends, seasonal effects
- **Provides explainability** — every score includes bottleneck analysis

### Action Layer (In Development)
- **Generates adaptive movement sessions** — strength, yoga, mobility, calisthenics, cardio, and hybrid programming
- **Modulates daily sessions** based on recovery state, sleep quality, HRV trends, and training load
- **Applies pharmacological context** — interprets biometric data through the lens of the user's medication and supplement profile
- **Tracks progressive overload** across modalities with appropriate progression models
- **Manages training periodization** — mesocycles, deload scheduling, goal-phased macrocycles
- **Learns behavioral preferences** — adapts session variety, structure, and frequency to what keeps the user engaged
- **Protects users from injury** — enforces ramp-back protocols after layoffs, flags overreaching patterns, schedules proactive recovery
- **Conversational coaching** via Claude API — contextual explanations, program adjustments, and natural-language interaction with your data

## What Soma Doesn't Do

Soma is not a medical device. It does not diagnose conditions, prescribe medications, or replace clinical care. Pharmacological context is informational — the system surfaces how known substance effects *may* interact with observed biometric patterns. Users input their own medications and supplements; Soma interprets, it does not recommend.

## Architecture

```
core/           Rust        — high-performance ingestion, normalization, BLAKE3 hashing
api/            Python      — FastAPI REST layer, OAuth2, Terra webhook receiver
science/        Python      — signal processing, baseline modeling, statistical analysis
engine/         Python      — movement database, workout generation, periodization logic
coach/          Python      — Claude API integration, conversational interface, program review
pharmacology/   Python      — substance profiles, interaction modeling, biometric correction factors
frontend/       TypeScript  — Next.js dashboard, session UI, trend visualization
docs/                       — architecture, design decisions, and implementation guides
```

## Stack

- **Rust** — core ingestion pipeline (handles 500MB+ Apple Health exports)
- **Python** — scientific computing, workout engine, API layer (NumPy, SciPy, scikit-learn, FastAPI)
- **TimescaleDB** — time-series PostgreSQL for signal storage and efficient temporal queries
- **Terra API** — unified data integration for WHOOP, Renpho, Garmin, and other wearables
- **Claude API** (Anthropic) — reasoning and coaching layer for program review, exception handling, and conversational interaction
- **Next.js** — frontend dashboard and session interface
- **Docker** — containerized local development

## Data Sources

### Via Terra API (Primary)
- **WHOOP** — HRV, sleep stages, recovery score, strain, respiratory rate, resting heart rate
- **Renpho** — weight, body fat %, lean mass, BMR, body water %
- **Apple Health** — aggregate activity, heart rate, steps, VO2 max
- **Garmin, Oura, Fitbit** — supported through Terra's unified integration

### Direct Integration
- **WHOOP OAuth2 API** — for granular data beyond Terra's scope

### User Input
- **Tape measurements** — chest, waist, hips, arms, thighs, neck (weekly/biweekly)
- **Medications & supplements** — substance, dosage, timing, with mechanism profiles
- **Goals** — structured goal types with timelines and milestones
- **Equipment profiles** — per-location equipment availability (home, gym, travel)
- **Session feedback** — perceived difficulty, energy, pain/discomfort, exercise swaps
- **Injury & mobility history** — persistent structural context

## Context Layers

Soma's competitive advantage is the depth and integration of context it brings to every decision:

| Layer | Source | What It Answers |
|-------|--------|-----------------|
| Biological | WHOOP, Apple Health | What state is your body in right now? |
| Compositional | Renpho, tape measurements | How is your body changing over time? |
| Chemical | User-inputted medications/supplements | What's modifying your biology that isn't visible in raw data? |
| Structural | User-inputted injury/mobility history | What are your body's mechanical constraints? |
| Environmental | Equipment profiles, location | What do you have access to today? |
| Programmatic | Training log, mesocycle position | Where are you in your training arc? |
| Behavioral | Session patterns, skip rates, preferences | What keeps you consistent? |
| Nutritional | User-inputted dietary posture | Are you fueling for your goals? |
| Temporal | Goal timelines, life events | What are you building toward and by when? |

## Philosophy

### Your data belongs to you
Soma runs locally by default. No telemetry. No cloud sync unless explicitly configured. No data leaves unless you export it.

### Ethical AI
Soma uses Anthropic's Claude API — not OpenAI — for its reasoning layer. User data is passed as context per-request, not used for model training. No fine-tuning on user data. The LLM is a reasoning tool, not a data collection mechanism.

### The engine generates, the LLM modulates
Workouts are produced by a deterministic rules engine grounded in exercise science. Claude handles exception reasoning, coaching communication, and periodic program review. The system works without the LLM; the LLM makes it smarter, not dependent.

### Context is the product
The movement session is an output. The real product is the unified, longitudinal model of you that makes every output intelligent. Better inputs produce better outputs — no ML required at the start.

### Each phase stands alone as useful
The context engine is valuable without workout generation. Workout generation is valuable without pharmacological modeling. Every layer adds value independently.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) — system design, data flow, and technical decisions
- [Roadmap](docs/ROADMAP.md) — development phases and progress
- [Movement Engine](docs/MOVEMENT_ENGINE.md) — workout generation design and methodology
- [Pharmacological Context](docs/PHARMACOLOGICAL_CONTEXT.md) — substance modeling approach and disclaimers
- [Context Engine](docs/CONTEXT_ENGINE.md) — how the context object is built and used
- [Coaching Layer](docs/COACHING_LAYER.md) — Claude API integration design
- [Data Integration](docs/DATA_INTEGRATION.md) — Terra API, WHOOP, and data source architecture

## License

MIT
