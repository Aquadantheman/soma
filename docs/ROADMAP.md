# Soma Roadmap

## Phase 1 — Foundation (Complete)
The software layer. Prove the value of continuous self-knowledge
before asking anyone to wear anything new.

- [x] TimescaleDB schema — signals, baselines, annotations, ingest log
- [x] Rust ingestion core — Apple Health XML parser
- [x] Personal baseline model — compute your normal, detect deviations
- [x] HRV signal processing — RMSSD, SDNN, Poincaré features
- [x] FastAPI REST layer — 25+ statistical analysis endpoints
- [x] Proven statistics module — circadian, weekly, trends, anomalies
- [x] Advanced analysis — correlations, recovery, seasonality, readiness
- [x] Stability analysis — convergence, drift, sample adequacy
- [x] Derived metrics — 12 compound health indicators
- [ ] Garmin connector
- [ ] Oura API connector
- [ ] Generic CSV ingester
- [ ] EDA signal processing
- [ ] Sleep architecture analysis
- [ ] Basic CLI dashboard (rich terminal output)

## Phase 2 — Personal Model (Complete)
Build the longitudinal model that makes Soma valuable.

- [x] Multi-signal correlation engine
  - HRV vs sleep quality
  - EDA vs resting HR
  - Activity vs next-day HRV
- [x] Anomaly detection — multi-sigma deviations flagged automatically
- [x] Readiness scoring — composite daily readiness from HRV/RHR
- [x] **Holistic Wellness Scoring** — 6-domain Harmonic Mean approach
  - Cardiovascular, Sleep, Activity, Recovery, Body Composition, Mobility
  - Based on V-Clock research (1.78x more predictive than simple averaging)
  - Full explainability (imbalance penalty, bottleneck analysis)
- [x] **Cross-domain pattern detection**
  - Simpson's Paradox detection
  - Behavioral patterns (compensatory exercise, weekend warrior, seasonal)
  - Lagged interconnections (sleep → next-day HRV)
- [x] **Mobility analysis** — walking speed as clinical "sixth vital sign"
  - Confound-controlled trends (97% real signal after controlling for activity/season)
- [x] **SpO2 analysis** — nocturnal dip detection (clinical-grade)
- [ ] Annotation correlation (medication starts, exercise events, stress)
- [ ] Weekly summary generation
- [ ] Exportable clinical report (PDF)
  - Plain language summary of the past 30 days
  - Designed to share with a psychiatrist or GP

## Phase 3 — Interface
Make the data legible.

- [ ] React dashboard
  - Personal baseline visualization
  - Signal timeline with annotations
  - Deviation alerts
  - Correlation explorer
- [ ] Mobile companion (React Native)
  - Daily mood/energy/anxiety log (30 seconds)
  - Notification when notable deviation detected

## Phase 4 — Expanded Sensors
As hardware matures, integrate new measurement channels.

- [ ] Continuous glucose monitor integration (Abbott Libre, Dexcom)
- [ ] Continuous cortisol sweat patch (when available commercially)
- [ ] Pupillometry via phone front camera (dopamine/noradrenergic proxy)
- [ ] Voice analysis (acoustic features as mood proxy)
- [ ] Passive typing cadence analysis (psychomotor proxy)
- [ ] EEG integration (Muse, Neurosity) for GABA/glutamate proxies

## Phase 5 — Clinical Integration
Bridge the gap to providers.

- [ ] FHIR export — standard clinical data format
- [ ] Provider portal — clinician view of patient biosignal data
- [ ] Medication response tracking — annotate medication changes, measure response
- [ ] Pre-appointment summary — auto-generated briefing for provider visits

## Philosophy

Each phase must stand alone as useful. Phase 1 is valuable without Phase 4.
We are not waiting for the perfect sensor — we are demonstrating what continuous
self-knowledge feels like with what exists today, pulling the hardware forward
by proving the demand.

## Technical Achievements

### Statistical Analysis (30+ endpoints)
- **Proven**: Circadian rhythm, weekly patterns, long-term trends, anomaly detection, HRV, SpO2
- **Advanced**: Cross-biomarker correlations, recovery modeling, seasonality decomposition, readiness scores
- **Stability**: Convergence analysis, temporal stability, drift detection, sample adequacy
- **Derived**: Nocturnal dip, training load (ACWR), autonomic balance, stress index, behavioral regularity, and more
- **Holistic**: 6-domain wellness scoring, cross-domain interconnections, paradox detection, behavioral patterns

### Holistic Wellness Scoring
- **6 domains**: Cardiovascular, Sleep, Activity, Recovery, Body Composition, Mobility
- **Harmonic Mean scoring**: Based on V-Clock biological age research (1.78x more predictive than simple averaging)
- **Explainability**: Arithmetic mean comparison, imbalance penalty, bottleneck analysis
- **Mobility as "sixth vital sign"**: Walking speed with confound-controlled trend analysis (97% real signal)
- **SpO2 analysis**: Clinical-grade nocturnal dip detection (CV=2.2%, stability=98.9%)

### Data Quality
- ~1.1M biosignals across 7 biomarker types
- Statistically validated findings with confidence intervals and p-values
- Bonferroni correction for multiple comparisons
- Effect size reporting (Cohen's d)
- Confound detection and control (time-of-day, seasonal, activity-level)
