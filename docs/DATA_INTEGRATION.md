# Data Integration

## Overview

Soma ingests data from multiple wearable devices, smart scales, and user inputs. The integration layer normalizes all incoming data into Soma's unified time-series schema for storage in TimescaleDB.

## Integration Strategy

### Primary: Terra API

Terra provides a unified API for health and wearable data, with official integrations for WHOOP, Renpho, Garmin, Fitbit, Oura, Apple Health (via mobile SDK), and 500+ other sources. Using Terra as the primary integration layer means:

- **One integration to maintain** rather than individual API adapters per device
- **Normalized data format** across all sources — Terra standardizes units and JSON structure
- **Upstream maintenance** — when a wearable provider changes their API, Terra handles the update
- **Webhook-based delivery** — data is pushed to Soma's endpoint automatically when new readings are available
- **Historical data access** — HTTP endpoints for backfilling data over specified date ranges

**Pricing**: Terra's Quick Start plan includes 100,000 free credits per month. For a single user, this is more than sufficient. The first 400 events per active authentication are free.

**Supported data types from key devices:**

| Device | Data Available via Terra |
|--------|------------------------|
| WHOOP | Recovery, strain, sleep (stages, duration, efficiency), HRV, resting HR, respiratory rate, SpO2, workouts |
| Renpho | Weight, body fat %, lean mass, BMR, body water % |
| Garmin | Activity, sleep, heart rate, stress, body battery, respiration, SpO2 |
| Oura | Sleep, readiness, activity, HRV, temperature |
| Apple Health | Requires mobile SDK; activity, heart rate, steps, workouts, VO2 max |
| Fitbit | Activity, sleep, heart rate, SpO2 |

### Secondary: WHOOP Direct API

WHOOP's official developer API is used as a complement to Terra for data that may be more granular or more current than what Terra exposes. WHOOP's API provides:

- Physiological cycles (day-level summaries)
- Recovery scores with component breakdowns
- Sleep data with stage detail
- Workout data with strain breakdowns
- OAuth2 authentication with refresh token support
- Webhook support for real-time data delivery
- Free API access for developers with a WHOOP membership

Soma's existing WHOOP OAuth2 integration can run alongside or independent of Terra.

### User Input Layer

Data that no API can provide:

**Tape measurements**: Circumference measurements at standardized anatomical landmarks (chest, waist at navel, hips at widest, upper arm relaxed, thigh at midpoint, neck). Prompted weekly or biweekly. The system stores measurement site instructions per landmark for consistency across months. These cross-validate BIA scale data — if Renpho shows muscle gain but no circumference changes, the system flags the discrepancy.

**Medications & supplements**: Substance name, dosage, frequency, timing, start date. Stored with mechanism profiles from the pharmacological context layer. See [PHARMACOLOGICAL_CONTEXT.md](PHARMACOLOGICAL_CONTEXT.md).

**Goals**: Structured goal definitions with type, target, timeline, and priority. See [CONTEXT_ENGINE.md](CONTEXT_ENGINE.md).

**Equipment profiles**: Named profiles (e.g., "Home", "Planet Fitness", "Travel") with specific equipment checked off from a comprehensive list. The active profile determines exercise selection for each session.

**Session feedback**: Post-workout input — perceived difficulty (1-5), energy level, any pain or discomfort (with body location), exercises the user wants to swap or keep. This closes the feedback loop for programming calibration.

**Injury & mobility history**: Persistent record of past and current injuries, mobility limitations, and movement restrictions. Propagates as contraindication flags into exercise selection.

## Webhook Architecture

### Terra Webhook Receiver

```
POST /v1/webhooks/terra

Receives normalized data payloads when new readings are available.
Validates webhook signature.
Routes data to appropriate signal processors.
Stores raw payload in ingest_log for auditability.
Normalizes and inserts into TimescaleDB signals table.
```

### Data Flow

```
Wearable Device
    │
    ▼
Terra Platform (normalization, standardization)
    │
    ▼
POST /v1/webhooks/terra (Soma FastAPI endpoint)
    │
    ├──► Signature validation
    ├──► Raw payload logging (ingest_log)
    ├──► Signal normalization (map Terra schema → Soma schema)
    ├──► BLAKE3 hash for deduplication
    └──► Insert into TimescaleDB signals table
              │
              ▼
         Baseline recalculation (triggered on new data)
              │
              ▼
         Wellness score update
              │
              ▼
         Context object refresh (available for next session generation)
```

### Deduplication

The same data point may arrive through multiple paths (e.g., WHOOP data via Terra and via direct WHOOP API, or the same Apple Health export imported twice). BLAKE3 hashing ensures each raw record is stored exactly once. Duplicate records are logged but not re-inserted.

## Graceful Degradation

Each data source is independent. If Terra's webhook is delayed, the system uses the most recent cached data. If Renpho hasn't synced in 3 days, the system notes reduced body composition confidence but continues generating sessions from available data. If WHOOP is disconnected entirely, the system falls back to training-log-based recovery estimation (less accurate but functional).

The UI communicates data freshness — "Recovery score based on data from 6 hours ago" vs. "No WHOOP data in 48 hours — using estimated recovery."

## Adding New Data Sources

Terra supports 500+ integrations. Adding a new device to Soma requires:

1. Enable the integration in Terra's dashboard
2. Map Terra's normalized payload fields to Soma's signal types
3. Add any device-specific signal processing to the science layer
4. Update the context engine to incorporate the new signals

For sources not available through Terra (e.g., CGM devices, EEG headbands), a custom adapter can be built following the same pattern: ingest → normalize → hash → store → trigger baseline recalculation.

## Privacy & Data Ownership

- All data is stored locally in the user's TimescaleDB instance
- Terra API credentials are stored in the local `.env` file
- OAuth tokens are encrypted at rest in the database
- No health data is transmitted to any service except Terra (for data retrieval) and Claude API (for coaching, with anonymization)
- Users can export all data and delete all records at any time
- The system maintains an auditable log of every data ingestion event
