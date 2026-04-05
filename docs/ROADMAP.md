# Soma Roadmap

## Phase 1 — Foundation (Complete)

Core infrastructure, data ingestion, and signal processing.

- TimescaleDB schema — signals, baselines, annotations, ingest log
- Rust ingestion core — Apple Health XML parser with BLAKE3 deduplication
- Personal baseline model — compute your normal, detect deviations
- HRV signal processing — RMSSD, SDNN
- FastAPI REST layer — 30+ analysis endpoints
- Proven statistics module — circadian, weekly, trends, anomalies
- Advanced analysis — correlations, recovery, seasonality, readiness
- Stability analysis — convergence, drift, sample adequacy
- Derived metrics — training load, autonomic balance, stress index
- WHOOP OAuth2 integration — recovery, sleep, strain, workouts
- Sleep architecture analysis — REM, deep, light stages

## Phase 2 — Personal Model (Complete)

Longitudinal modeling that makes Soma's context engine valuable.

- Multi-signal correlation engine — HRV vs sleep, activity vs next-day recovery
- Anomaly detection — multi-sigma deviations flagged automatically
- Readiness scoring — composite daily readiness from HRV/RHR
- Holistic wellness scoring — 6-domain Harmonic Mean (V-Clock research)
- Cross-domain pattern detection — Simpson's Paradox, behavioral patterns
- Mobility analysis — walking speed as clinical "sixth vital sign"
- SpO2 analysis — nocturnal dip detection
- Annotation correlation (medication starts, life events)
- Exportable clinical report (PDF for provider visits)

## Phase 3 — Data Integration Expansion (Current)

Broaden the data inputs and add Terra API as a unified integration layer.

- Terra API integration — webhook receiver, data normalization, multi-source support
- Renpho body composition data via Terra (weight, body fat %, lean mass, BMR, body water)
- Tape measurement input — manual circumference measurements with site instructions
- Cross-validation logic — Renpho BIA vs tape measurements for body composition confidence
- Equipment profile system — named profiles with per-location equipment lists
- User input layer — goals, injury history, schedule, time constraints
- Data freshness tracking and graceful degradation when sources are stale

## Phase 4 — Movement Engine

The action layer — turning context into adaptive movement programming.

- Movement database — exercises, yoga, mobility, calisthenics, cardio, tagged with modality, equipment, muscle groups, difficulty, progressions, and contraindications
- Programming logic — session construction from training split, biometric state, equipment, and goals
- Progressive overload tracking — per-exercise, per-muscle-group volume management
- Mesocycle management — accumulation, intensification, deload phases with automatic scheduling
- Biometric modulation — daily session scaling based on recovery state and wellness scores
- Warm-up and cool-down generation — session-specific, movement-pattern-aware
- Multi-modality support — strength, yoga, mobility, calisthenics, cardio with distinct progression models
- Weekly planning — training split selection, modality distribution, time-constraint fitting
- Safety rails — mandatory deloads, volume ceilings, return-from-layoff regression, injury flag propagation

## Phase 5 — Pharmacological Context

Substance-aware biometric interpretation.

- Medication and supplement input system — substance, dosage, timing, start date
- Substance mechanism profiles — known biomarker effects, half-lives, interaction data
- Biometric correction annotations — flag pharmacologically influenced readings
- Confidence-leveled interpretations — high/moderate/low confidence based on evidence strength
- Cross-substance interaction flags — additive effects, contraindications
- Privacy-first substance data handling — local storage, anonymized for Claude API context
- Integration with Apothecary substance intelligence (optional)

## Phase 6 — Coaching Layer

Claude API integration for reasoning, communication, and conversational interaction.

- Context object serialization — structured natural-language summaries for Claude
- Weekly program review — automated assessment of training, biometrics, and goals
- Phase transition analysis — mesocycle-end review and next-phase recommendations
- Exception handling — injury reports, fatigue, life circumstance changes
- Conversational interface — natural-language queries about data, progress, and programming
- Fall-off intervention — contextual, empathetic re-engagement when skip patterns are detected
- Decision caching — multi-session decisions applied without redundant API calls
- Fallback behavior — deterministic engine operates independently when API is unavailable

## Phase 7 — Behavioral Engine

Learn what keeps the user engaged and adapt accordingly.

- Session feedback collection — perceived difficulty, energy, pain, exercise preferences
- Novelty preference modeling — freshness vs consistency scoring from observed behavior
- Skip pattern detection — day-of-week, time-of-month, correlation with biometric state
- Engagement trend monitoring — completion rates, session duration, feedback scores
- Adaptive variety — accessory rotation, session structure changes, modality mix adjustments
- Goal-linked motivation — surface progress milestones, celebrate PRs, connect effort to outcomes

## Phase 8 — Interface

Make the data and programming legible and engaging.

- Web dashboard — wellness scores, trend visualization, training log, body composition charts
- Session UI — today's workout with exercise details, coaching rationale, timer, logging
- Conversational chat — Claude-powered interface for questions and adjustments
- Trend explorer — correlations between sleep, training, body comp, recovery over arbitrary time ranges
- Goal dashboard — progress tracking, milestone visualization, projected timelines
- Mobile companion — session logging, quick feedback, measurement input, notifications

## Phase 9 — Expanded Sensors

As hardware matures, integrate new measurement channels.

- Continuous glucose monitors (Abbott Libre, Dexcom) via Terra
- EEG integration (Muse, Neurosity)
- Smart rings (Oura) via Terra
- Blood pressure monitors
- Voice/typing analysis (psychomotor proxies)

## Phase 10 — Community & Scale

If Soma becomes a multi-user platform.

- Multi-user architecture — data isolation, per-user context engines
- Collaborative filtering — users with similar profiles benefiting from shared pattern recognition
- Coached programs — expert-designed programming templates with Soma's adaptive modulation
- Clinical integration — FHIR export, pre-appointment summaries, medication response tracking
- ML layer — predictive recovery modeling, injury risk detection, personal response curves (requires sufficient longitudinal data across users)

## Philosophy

Each phase stands alone as useful. Phase 1 is valuable without Phase 4. Phase 4 is valuable without Phase 6. We build the foundation right and layer capability on top. The context engine is the product — every phase enriches it.
