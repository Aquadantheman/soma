# Context Engine

## Overview

The context engine is Soma's core — the system that continuously aggregates, normalizes, and structures all available information about the user into a unified context object. This object is the input to every downstream decision: workout generation, coaching, anomaly detection, and goal tracking.

The context object is rebuilt on every relevant data event (new biometric reading, completed session, user input change) and cached for low-latency access.

## Context Object Structure

```
context:
  timestamp: datetime             # When this context was computed
  data_freshness:                 # How current each data source is
    whoop: datetime | null
    renpho: datetime | null
    apple_health: datetime | null
    last_session: datetime | null
    last_tape_measurement: datetime | null

  biological:                     # Real-time physiological state
    recovery_score: float | null
    hrv_rmssd: float | null
    hrv_trend_7d: trend           # rising | stable | declining
    resting_hr: float | null
    resting_hr_trend_7d: trend
    sleep_score: float | null
    sleep_duration_hours: float | null
    sleep_stages:
      rem_pct: float | null
      deep_pct: float | null
      light_pct: float | null
    strain_today: float | null
    strain_7d_avg: float | null
    respiratory_rate: float | null
    spo2: float | null

  compositional:                  # Body composition state and trends
    weight_kg: float | null
    weight_trend_30d: trend
    body_fat_pct: float | null
    body_fat_trend_30d: trend
    lean_mass_kg: float | null
    lean_mass_trend_30d: trend
    body_water_pct: float | null
    bmr: float | null
    tape_measurements:            # Most recent
      chest_cm: float | null
      waist_cm: float | null
      hips_cm: float | null
      upper_arm_cm: float | null
      thigh_cm: float | null
      neck_cm: float | null
    tape_trends_30d:              # Per-site trends
      waist: trend
      # ...etc

  chemical:                       # Active pharmacological profile
    substances:
      - name: string
        category: medication | supplement
        dosage: string
        timing: string
        active_window: boolean    # Is this substance currently active based on timing + half-life?
        biomarker_effects: list   # Known effects on measured signals
        correction_flags: list    # Active corrections being applied
    interaction_flags: list       # Cross-substance interactions

  structural:                     # Mechanical context (slow-changing)
    injuries:
      - location: string
        status: active | recovering | resolved
        date_reported: date
        contraindicated_patterns: list
    mobility_notes: list
    training_age_months: int      # How long the user has been training consistently

  environmental:                  # What's available today
    active_equipment_profile: string
    available_equipment: list
    available_time_minutes: int | null

  programmatic:                   # Training state
    current_split: string
    mesocycle_week: int
    mesocycle_phase: accumulation | intensification | deload
    days_since_last_session: int
    sessions_this_week: int
    weekly_volume_by_muscle_group:
      chest: int                  # Total working sets
      back: int
      # ...etc
    progressive_overload_status:  # Per core lift
      - exercise: string
        current_working_weight: float
        trend: rising | plateau | declining
        weeks_at_current: int
    last_deload_date: date | null
    consecutive_loading_weeks: int

  behavioral:                    # Engagement patterns
    avg_sessions_per_week_4w: float
    completion_rate_4w: float    # % of generated sessions completed
    skip_pattern: string | null  # e.g., "tends to skip Fridays"
    swap_rate: float             # How often user swaps exercises
    novelty_preference: float    # 0.0 (routine) to 1.0 (variety)
    avg_session_rating_4w: float | null
    layoff_detected: boolean
    days_in_layoff: int | null

  goals:                         # Active goals
    - type: enum                 # strength | hypertrophy | fat_loss | flexibility | endurance | general_health | event_prep | skill
      description: string
      target: string | null      # Measurable target (e.g., "squat 225lbs", "lose 20lbs", "touch toes")
      deadline: date | null
      priority: primary | secondary
      progress_pct: float | null
      projected_completion: date | null
      status: on_track | behind | ahead | stalled

  wellness:                      # Soma's computed scores
    overall_score: float
    domain_scores:
      cardiovascular: float
      sleep: float
      activity: float
      recovery: float
      body_composition: float
      mobility: float
    bottleneck: string           # Weakest domain
    imbalance_penalty: float
    trend_7d: trend
```

## Goal Engine

### Goal Types

| Type | Progression Model | Key Metrics | Example |
|------|------------------|-------------|---------|
| Strength | Weight on specific lifts | 1RM estimates, working weight trends | "Squat 225 lbs" |
| Hypertrophy | Volume accumulation, body measurements | Weekly volume per muscle group, circumference changes | "Build bigger arms" |
| Fat loss | Body composition change | Weight trend, body fat %, waist circumference | "Lose 20 lbs by September" |
| Flexibility | ROM milestones | Joint-specific range measurements, pose achievements | "Full splits" |
| Endurance | Cardiovascular capacity | Time, distance, heart rate at pace | "Run a 5K under 30 min" |
| General health | Balanced wellness scores | Soma wellness score, domain balance | "Get healthier" |
| Event prep | Time-bound multi-factor | Varies by event requirements | "Ready for hiking trip in 8 weeks" |
| Skill | Calisthenics/movement milestones | Progression level achieved | "Handstand hold for 30 seconds" |

### Goal Compatibility

Some goal combinations require phasing rather than simultaneous pursuit:

- **Fat loss + hypertrophy**: Possible for beginners (recomposition), requires phasing for intermediates
- **Maximal strength + endurance**: Interference effect — concurrent training requires careful volume management
- **Fat loss + maximal strength**: Difficult to gain strength in a deficit; prioritize strength preservation

The system flags incompatible goal combinations during onboarding and suggests phasing strategies.

### Milestone Tracking

Goals with measurable targets are tracked against projected timelines:

1. **Baseline measurement** at goal creation
2. **Rate of change** computed from observed data (rolling 2-4 week windows)
3. **Projected completion** extrapolated from current rate
4. **Status assessment**: on track, behind (rate slower than needed), ahead, or stalled (no change in 2+ weeks)
5. **Adaptive replanning** — if a goal is behind schedule, the system suggests programming adjustments; if a goal is stalled, Claude provides analysis of potential causes

## Context Refresh Triggers

The context object is recomputed when:

- New biometric data arrives via webhook (Terra, WHOOP)
- User completes a session
- User logs tape measurements
- User modifies their medication/supplement profile
- User updates goals or equipment profiles
- Daily scheduled refresh (for time-dependent calculations like mesocycle position)

Recomputation is incremental — only the affected sections are recalculated, not the entire object.

## Context for Claude API

When Claude is invoked, it receives a subset of the context object appropriate to the request type:

- **Weekly review**: Full context with 7-day training summary, biometric trends, goal progress
- **Exception handling**: Relevant domain scores, recent session data, specific concern
- **Conversational query**: Full context (Claude determines what's relevant)
- **Fall-off intervention**: Behavioral section, recent engagement patterns, goal status

The context is serialized as structured text, not raw JSON — Claude reasons better over natural-language descriptions of state than over nested data structures.
