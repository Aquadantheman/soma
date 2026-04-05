# Movement Engine

## Overview

The movement engine is Soma's workout generation system. It produces daily movement sessions — strength training, yoga, mobility work, calisthenics, cardio, and hybrid sessions — by combining a deterministic rules engine with real-time biometric modulation and user context.

The engine does not use an LLM to generate workouts. It uses structured programming logic grounded in exercise science. Claude's API is invoked only at decision points: phase transitions, anomalous biometric readings, weekly program reviews, and conversational interactions.

## Core Principle: The Engine Generates, the LLM Modulates

A rules engine produces consistent, progressive, trackable programming. An LLM produces plausible-sounding sessions that may not build systematically toward anything. The engine handles what needs to be precise and stateful. The LLM handles what needs to be contextual and communicative.

## Movement Database

### Structure

Every movement in the database is tagged with:

- **Modality** — strength, yoga, mobility, calisthenics, cardio, plyometrics, balance
- **Movement pattern** — hinge, squat, push (horizontal/vertical), pull (horizontal/vertical), carry, rotation, flow, hold, gait
- **Primary muscle groups** — using standardized anatomical groupings
- **Secondary muscle groups** — stabilizers and synergists
- **Equipment required** — barbell, dumbbell, kettlebell, cable, machine, band, bodyweight, mat, block, strap, bench, pull-up bar, none
- **Difficulty tier** — beginner, intermediate, advanced
- **Progression relationships** — what this movement progresses from and to
- **Contraindication flags** — shoulder impingement, lower back, knee, wrist, etc.
- **Instruction metadata** — cue text, common mistakes, video reference ID
- **Modality-specific attributes** — see below

### Modality-Specific Progression Models

**Strength training**: Progressive overload via weight, reps, sets, tempo, or rest periods. Tracked as volume (sets × reps × weight) per muscle group per week. Targets MEV (minimum effective volume) through MAV (maximum adaptive volume), with MRV (maximum recoverable volume) as the ceiling.

**Yoga**: Progression through pose variations (supported → unsupported → advanced), hold duration, flow complexity, and breath integration. Tracked as time-under-tension per movement pattern and range-of-motion milestones.

**Mobility/flexibility**: Progression through range of motion measured at key joints, hold duration, and movement quality. Tracked as ROM improvements over time with measurement landmarks.

**Calisthenics**: Skill progressions along defined paths (e.g., wall push-up → incline → standard → diamond → archer → one-arm). Tracked as highest achieved progression level and rep quality at each level.

**Cardio**: Progression through duration, intensity (heart rate zones), interval structure, and modality variety. Tracked as weekly cardiovascular load, time in zones, and aerobic capacity indicators.

## Programming Logic

### Session Construction

1. **Determine session type** from the weekly template based on training split, day of week, and user schedule.
2. **Check biometric modulation** — WHOOP recovery, HRV trend, sleep quality, strain accumulation. Scale the session intensity and volume accordingly.
3. **Apply pharmacological corrections** — adjust interpretation of biometric data based on active substance profiles.
4. **Select movements** from the database filtered by: available equipment (today's profile), appropriate muscle groups (based on recovery state and split), difficulty tier (based on training age and progression level), and contraindication exclusions.
5. **Order movements** — compound before isolation, high-skill before fatigued, movement pattern balance within the session.
6. **Set parameters** — reps, sets, weight (from progression history), tempo, rest periods. Apply RPE targets based on mesocycle phase and biometric state.
7. **Generate warm-up** — dynamic movements specific to the session's primary patterns and loads.
8. **Generate cool-down** — based on session type and user preferences.

### Weekly Planning

The system maintains a weekly template based on the user's training frequency, goals, and available time:

- **Training split** — auto-selected from goals and frequency (full body for 2-3x/week, upper/lower for 4x, push/pull/legs for 5-6x, or custom)
- **Modality distribution** — balances strength, cardio, mobility, and recovery across the week based on goal priorities
- **Time constraints** — each day has an available time window; sessions are built to fit
- **Mandatory recovery** — at least 1-2 full rest or active recovery days per week, non-negotiable

### Mesocycle Management

Training is organized into 4-6 week mesocycles:

- **Accumulation phase** (weeks 1-3/4) — volume increases progressively, intensity moderate
- **Intensification phase** (weeks 3/4-5) — volume stabilizes or decreases, intensity increases
- **Deload** (week 5/6) — volume drops 40-50%, intensity drops 10-20%, recovery emphasis

Deload timing is informed by both the programmatic schedule and biometric signals. If WHOOP recovery scores trend downward for 5+ consecutive days mid-mesocycle, the system may trigger an early deload.

### Macrocycle Planning

For users with time-bound goals, the system plans backward from the target date:

- **Goal analysis** — what needs to change (strength, body composition, flexibility, endurance) and by when
- **Phase sequencing** — which mesocycle types to stack and in what order
- **Milestone projection** — realistic intermediate targets based on the user's observed rate of change
- **Adaptive replanning** — if progress is ahead or behind projection, adjust the remaining phases

## Biometric Modulation

The context engine provides a daily readiness assessment. The movement engine uses this to scale sessions:

| Recovery State | Volume Adjustment | Intensity Adjustment | Session Modification |
|---------------|-------------------|---------------------|---------------------|
| High (green) | 100-110% | 100-105% | Run as programmed, push if appropriate |
| Moderate (yellow) | 80-95% | 90-100% | Reduce accessory volume, maintain compounds |
| Low (red) | 50-70% | 70-85% | Swap to lighter session, add mobility/yoga |
| Very low | 0% | 0% | Active recovery or rest day, flag for review |

Modulation considers not just today's score but the trend — three consecutive yellow days may warrant a different response than a single yellow after a week of green.

## Behavioral Adaptation

### Freshness vs. Consistency

The system maintains a novelty preference score per user, initialized during onboarding and refined through observed behavior:

**Signals toward more variety**: frequent exercise swaps, declining session completion rates over multi-week blocks, feedback indicating boredom, skip patterns emerging around week 3-4 of a program.

**Signals toward more consistency**: user saves and repeats workouts, high completion rates on familiar sessions, preference for tracking PRs on specific lifts, feedback indicating satisfaction with routine.

The novelty dial affects accessory exercise selection, session structure variation, and modality rotation — but never compromises programmatic integrity of core progression.

### Engagement Protection

- **Skip detection** — if session frequency drops below the user's established pattern, the system intervenes with a check-in (via Claude) before the habit fully breaks
- **Return-from-layoff protocol** — after any gap of 10+ days, loads are automatically regressed (15-30% depending on gap length) and rebuilt over 1-2 weeks to protect connective tissue
- **PR celebration** — personal records are surfaced and acknowledged
- **Streak tracking** — consistency metrics visible but not gamified in a way that encourages overtraining

## Safety Rails

- **Mandatory deload scheduling** — the system will not program more than 6 consecutive weeks of progressive loading without a recovery week
- **Volume ceiling enforcement** — per-muscle-group weekly volume cannot exceed evidence-based MRV estimates without explicit user override
- **Injury flag propagation** — a flagged injury or pain report immediately excludes related movements and triggers Claude review for substitution recommendations
- **Heart rate pharmacological correction** — if the user's medication profile includes stimulants or beta-blockers, strain and heart rate zone calculations are adjusted
- **Return-from-layoff regression** — non-negotiable load reduction after extended breaks

## Claude Integration Points

The movement engine invokes Claude at specific decision points, not for routine session generation:

1. **Weekly program review** — Claude receives the past week's training data, biometric trends, and goal progress, and provides an assessment and any recommended adjustments
2. **Phase transitions** — when transitioning between mesocycle phases, Claude reviews the accumulated data and confirms or adjusts the next phase's parameters
3. **Exception handling** — user reports pain, unusual fatigue, or life circumstances that affect training; Claude reasons about appropriate modifications
4. **Conversational queries** — user asks a question about their programming, progress, or data; Claude responds with full context awareness
5. **Fall-off intervention** — when skip patterns are detected, Claude generates a contextual, empathetic check-in rather than a generic notification

Claude receives a structured context object for each invocation — not raw data, but a pre-computed summary including current wellness scores, domain bottlenecks, mesocycle position, recent session summaries, active pharmacological profile, and relevant goal status.
