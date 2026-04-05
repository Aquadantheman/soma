# Coaching Layer

## Overview

Soma's coaching layer uses Anthropic's Claude API as a reasoning and communication engine. It is not the workout generator — the deterministic movement engine handles session construction. Claude handles the things that require contextual reasoning, natural language understanding, and empathetic communication.

## Why Claude (Not OpenAI)

This is an ethical choice. Soma uses Anthropic's Claude API because:

- User health data is not used for model training
- Per-request context passing (no fine-tuning on user data required)
- Zero-retention policy on API inputs
- Alignment with Soma's privacy-first philosophy

## Design Principle: Enhance, Not Depend

The system must function without the LLM. If the Claude API is unavailable:

- The deterministic engine still generates sessions based on programmatic rules and cached decisions
- Biometric modulation still applies
- Safety rails still enforce
- The user loses coaching explanations and conversational interaction, not core functionality

Claude is an enhancement layer, not infrastructure.

## Invocation Points

Claude is called at specific decision points, not for every session generation. This controls cost, reduces latency, and ensures the LLM is used where it adds genuine value.

### 1. Weekly Program Review

**Trigger**: Scheduled, once per week (or on-demand by user).

**Input**: Full context object with 7-day training summary — sessions completed, volume per muscle group, progressive overload status, biometric trends, wellness score trajectory, goal progress, any flags raised during the week.

**Output**: Natural-language assessment of the past week, identification of what's working and what isn't, specific recommendations for the coming week, and any programming adjustments (which are then applied to the deterministic engine's parameters).

**Example**: "Your training volume was solid this week — 16 working sets for back, 14 for chest — but your sleep scores have been declining since Wednesday. Your HRV trend is down 8% from your 30-day baseline. Given that you're in week 4 of this mesocycle, I'd recommend we move the deload up by one week rather than pushing through. Your bench press is still progressing well at 165 for 3x8, so we'll preserve that intensity during the deload with reduced volume."

### 2. Phase Transitions

**Trigger**: When the mesocycle position transitions between phases (accumulation → intensification → deload → new cycle).

**Input**: Full mesocycle summary — total volume progression, strength changes, body composition changes, biometric averages per phase, goal progress.

**Output**: Assessment of the completed phase, confirmation or adjustment of the next phase's parameters, updated goal projections.

### 3. Exception Handling

**Trigger**: User reports pain, injury, unusual fatigue, life circumstance change, or any input the deterministic engine cannot resolve with rules alone.

**Input**: The specific concern plus relevant context — recent sessions, affected body areas, biometric state, active pharmacological profile.

**Output**: Reasoning about the situation, exercise substitution recommendations, modified session parameters, and guidance on when to resume normal programming or when to seek professional evaluation.

**Example**: User says "my left knee has been bothering me after lunges this week."

Claude response: "Let's take lunges and their variations out of rotation for now. Based on your recent sessions, you've been doing walking lunges twice a week at increasing loads — the cumulative knee flexion volume may be the issue. I'm substituting hip thrusts and step-ups with a controlled range of motion for your lower body sessions this week. If the discomfort persists beyond a week or occurs during daily activities, it would be worth getting it evaluated. I'll check back in next week's review."

### 4. Conversational Queries

**Trigger**: User asks a question through the chat interface.

**Input**: The question plus full context object.

**Output**: A contextual, data-informed response.

**Example queries and what makes them possible with Soma's context:**

- "Why am I not getting stronger on bench?" → Claude can analyze volume trends, recovery scores, sleep quality, progressive overload history, and nutritional context to give a real answer, not a generic one.
- "Should I work out today?" → Claude can check recovery state, training load accumulation, mesocycle position, and the user's schedule to give a nuanced recommendation.
- "How's my progress?" → Claude can compare current state against goal baselines, project timelines, and identify what's contributing to or hindering progress.
- "I'm bored with my routine" → Claude can adjust the novelty preference parameter and restructure upcoming sessions while maintaining programmatic integrity.

### 5. Fall-Off Intervention

**Trigger**: Behavioral engine detects declining engagement — session frequency dropping, increasing skip rate, sessions started but not completed.

**Input**: Behavioral context, recent patterns, goal status, any correlated biometric changes.

**Output**: A contextual, empathetic check-in — not a generic notification. Claude understands the difference between "life got busy" and "the program isn't working" and responds appropriately.

**Example**: "Hey — I noticed you've missed a few sessions this week. Your sleep scores have been lower too, which might be making training feel harder than it should. No pressure to jump back to full intensity — when you're ready, I've got a lighter session queued up that'll feel good without draining you. Sometimes a 20-minute mobility session is the best thing you can do."

## Context Serialization for Claude

The context object is not passed as raw JSON. It's serialized into structured natural language that Claude can reason over effectively:

```
User State Summary (2026-04-05):

Recovery & Biometrics:
- WHOOP recovery: 62% (below 30-day average of 74%)
- HRV: 38ms RMSSD (trending down over 5 days, baseline: 45ms)
- Sleep: 6.2 hours, 18% deep, 22% REM (below typical 7.1 hours)
- Resting HR: 58 bpm (slightly elevated from baseline 54)
- Strain yesterday: 14.2 (above 7-day average of 11.8)

Body Composition (7-day trend):
- Weight: 182.4 lbs (stable)
- Body fat: 19.2% (down 0.3% over 30 days)
- Waist: 33.5" (down 0.5" over 30 days)

Active Substances:
- Lexapro 10mg (SSRI, daily morning, active)
- Adderall 30mg (stimulant, daily morning, currently in active window — HR and HRV may be pharmacologically affected)
- Creatine 5g (daily, 6 weeks in — past saturation period, body water effects stabilized)
- Magnesium glycinate 400mg (nightly)

Training State:
- Mesocycle week 4 of 5 (accumulation phase)
- 3 sessions completed this week (target: 4)
- Weekly volume: chest 14 sets, back 16 sets, legs 12 sets
- Bench press: 165 lbs 3x8 (up from 155 four weeks ago)
- Squat: 205 lbs 3x6 (plateau for 2 weeks)
- Consecutive loading weeks: 4

Equipment: Home gym (dumbbells to 50 lbs, adjustable bench, pull-up bar, bands)

Goals:
- Primary: Fat loss — target 175 lbs by August (currently 182.4, on track)
- Secondary: Bench press 185 lbs (currently 165, projected July)

Behavioral:
- Avg 3.5 sessions/week over past 4 weeks
- Tends to skip Friday sessions
- Novelty preference: 0.4 (moderate — prefers consistent core lifts with accessory rotation)
- No layoff detected
```

This format lets Claude reason naturally about the interplay between domains rather than parsing nested data structures.

## Cost Management

**Estimated per-call cost** (Claude Sonnet): ~$0.01-0.03 per invocation with typical context size.

**Estimated monthly cost for single user**:
- 4 weekly reviews: ~$0.08-0.12
- 1-2 phase transitions: ~$0.02-0.06
- 2-4 exception calls: ~$0.04-0.12
- 5-10 conversational queries: ~$0.10-0.30
- 1-2 fall-off interventions: ~$0.02-0.06
- **Total: ~$0.25-0.65/month**

Using Sonnet for routine calls and Opus for complex reasoning (weekly reviews, phase transitions) keeps costs minimal while maintaining quality where it matters.

**Caching**: When Claude makes a decision that applies to multiple sessions (e.g., "deload this week"), the decision is cached and the deterministic engine applies it to all affected sessions without re-invoking Claude.

## What Claude Never Does

- Generate workout sessions from scratch (the deterministic engine does this)
- Override safety rails (deload enforcement, injury contraindications, return-from-layoff protocols)
- Recommend medications or supplements
- Provide medical diagnoses or clinical advice
- Access user data beyond what's in the serialized context object
- Store or retain conversation history on Anthropic's servers
