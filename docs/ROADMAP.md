# Soma Roadmap

## Phase 1 — Foundation (Complete)

Core infrastructure and data ingestion.

- [x] TimescaleDB schema — signals, baselines, annotations, ingest log
- [x] Rust ingestion core — Apple Health XML parser
- [x] Personal baseline model — compute your normal, detect deviations
- [x] HRV signal processing — RMSSD, SDNN
- [x] FastAPI REST layer — 30+ analysis endpoints
- [x] Proven statistics module — circadian, weekly, trends, anomalies
- [x] Advanced analysis — correlations, recovery, seasonality, readiness
- [x] Stability analysis — convergence, drift, sample adequacy
- [x] Derived metrics — training load, autonomic balance, stress index
- [x] Whoop OAuth2 integration — recovery, sleep, strain, workouts
- [x] Sleep architecture analysis — REM, deep, light stages
- [ ] Garmin connector
- [ ] Oura API connector

## Phase 2 — Personal Model (Complete)

Build the longitudinal model that makes Soma valuable.

- [x] Multi-signal correlation engine — HRV vs sleep, activity vs next-day recovery
- [x] Anomaly detection — multi-sigma deviations flagged automatically
- [x] Readiness scoring — composite daily readiness from HRV/RHR
- [x] Holistic wellness scoring — 6-domain Harmonic Mean (V-Clock research)
- [x] Cross-domain pattern detection — Simpson's Paradox, behavioral patterns
- [x] Mobility analysis — walking speed as clinical "sixth vital sign"
- [x] SpO2 analysis — nocturnal dip detection
- [ ] Annotation correlation (medication starts, life events)
- [ ] Exportable clinical report (PDF for provider visits)

## Phase 3 — Interface

Make the data legible.

- [ ] Web dashboard — baseline visualization, signal timeline, deviation alerts
- [ ] Mobile companion — quick mood/energy logging, deviation notifications

## Phase 4 — Expanded Sensors

As hardware matures, integrate new measurement channels.

- [ ] Continuous glucose monitors (Abbott Libre, Dexcom)
- [ ] Smart scales (Renpho, Withings)
- [ ] Voice/typing analysis (psychomotor proxies)
- [ ] EEG integration (Muse, Neurosity)

## Phase 5 — Clinical Integration

Bridge the gap to providers.

- [ ] FHIR export — standard clinical data format
- [ ] Pre-appointment summary — auto-generated briefing
- [ ] Medication response tracking

## Philosophy

Each phase stands alone as useful. Phase 1 is valuable without Phase 4. We demonstrate what continuous self-knowledge feels like with today's hardware, proving the demand for better sensors.
