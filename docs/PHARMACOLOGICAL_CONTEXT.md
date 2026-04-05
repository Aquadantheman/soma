# Pharmacological Context

## Overview

Soma's pharmacological context layer allows users to input their medications and supplements so the system can interpret biometric data more accurately and generate more appropriate movement programming. This layer monitors — it does not recommend or prescribe.

## Disclaimer

Soma is not a medical device, pharmacy, or clinical tool. It does not recommend medications or supplements. It does not diagnose conditions. It does not replace the judgment of a physician, pharmacist, or licensed healthcare provider.

All substance information is user-inputted. Soma surfaces how known pharmacological effects *may* interact with observed biometric patterns. These interpretations are presented as hypotheses with confidence levels, not clinical conclusions. Users should consult their healthcare providers before making any changes to their medication or supplement regimens.

## Design Philosophy: Monitor, Don't Recommend

The system accepts user input about what they take. It provides context about how those substances may affect the data being collected. It never tells a user to start, stop, or change a substance.

This is the same role a well-informed personal trainer plays: "I know you take a stimulant medication — that's going to affect your heart rate during training, so let's interpret your strain data with that in mind." Not: "You should take creatine."

## Substance Profile Schema

Each user-inputted substance is stored with:

```
substance:
  name: string                    # Common name (e.g., "Adderall", "Creatine")
  generic_name: string | null     # Generic/chemical name (e.g., "mixed amphetamine salts")
  category: enum                  # medication | supplement | other
  dosage: string                  # User-reported dosage (e.g., "30mg", "5g")
  frequency: string              # Dosing schedule (e.g., "daily morning", "twice daily")
  timing: string | null           # Typical time of day taken
  start_date: date | null         # When the user started taking it
  active: boolean                 # Currently taking

  # Mechanism profile (from substance intelligence layer)
  mechanism:
    primary_action: string        # e.g., "CNS stimulant", "osmolyte", "SSRI"
    half_life: duration | null    # Pharmacokinetic half-life
    known_biomarker_effects:      # How this substance affects measurable signals
      - biomarker: string         # e.g., "heart_rate", "hrv", "body_water", "sleep_architecture"
        direction: up | down | variable
        magnitude: low | moderate | significant
        onset: immediate | hours | days | weeks
        notes: string
    interaction_flags: list       # Known interactions with other substances in the user's profile
```

## Biometric Correction Factors

The pharmacological layer applies correction factors to the context engine's interpretation of biometric data. These are not hard adjustments to raw values — they are contextual annotations that modify how the system interprets signals.

### Stimulant Medications (e.g., Adderall, Vyvanse, Ritalin)

**Known effects on measurable signals:**
- Elevated resting heart rate (moderate, onset: hours)
- Reduced HRV (moderate, onset: hours)
- Increased perceived energy that may not reflect recovery state
- Potential appetite suppression affecting nutritional context
- Duration-dependent: IR formulations wear off differently than XR

**System behavior:**
- Flag elevated HR and reduced HRV as potentially pharmacological rather than pathological or overtraining-related
- Annotate WHOOP strain scores during active medication window with context: "Strain may overestimate muscular fatigue during stimulant active window"
- Do not automatically adjust numerical strain values — present the hypothesis and let the user/coach layer reason about it
- Track correlation between medication timing and biometric patterns over time to build personal correction confidence

### SSRIs (e.g., Lexapro, Zoloft, Prozac)

**Known effects on measurable signals:**
- Potential weight changes (variable, onset: weeks)
- Altered sleep architecture — may affect REM staging (variable, onset: weeks)
- Possible thermoregulation changes affecting workout tolerance
- Serotonergic effects on recovery perception

**System behavior:**
- If weight trends shift after SSRI start date, annotate as potentially medication-related
- If sleep score changes correlate temporally with SSRI initiation, flag the association
- Track long-term patterns rather than making acute corrections

### Creatine

**Known effects on measurable signals:**
- Body water increase of 2-4 lbs during loading/saturation (onset: days to weeks)
- Apparent lean mass increase on BIA scales due to intracellular water retention
- Potential small improvement in anaerobic performance

**System behavior:**
- During the first 4-6 weeks of creatine supplementation, flag body water and lean mass changes on Renpho as likely water-mediated rather than tissue changes
- Adjust body composition baseline recalculation to account for water loading period
- After stabilization period, resume normal trend interpretation

### Magnesium (Glycinate, Citrate, etc.)

**Known effects on measurable signals:**
- Potential improvement in sleep quality (onset: days to weeks)
- Mild muscle relaxation effects

**System behavior:**
- Track correlation between supplementation timing and sleep scores
- If evening dosing correlates with improved sleep metrics over 2+ weeks, note the association as a positive signal

### NSAIDs and Anti-inflammatories

**Known effects on measurable signals:**
- Reduced inflammation markers may affect recovery perception
- Some evidence of blunted adaptation signals when taken chronically around training

**System behavior:**
- If chronic NSAID use is logged, annotate that recovery scores may read higher than actual tissue adaptation state
- Flag as a consideration in long-term programming rather than an acute session modifier

## Confidence Levels

Every pharmacological interpretation is tagged with a confidence level:

- **High confidence** — well-established pharmacological effect with consistent research support (e.g., stimulants elevate heart rate)
- **Moderate confidence** — plausible mechanism with some research support but individual variation is significant (e.g., creatine water retention magnitude)
- **Low confidence** — theoretical or extrapolated from limited research; presented as a hypothesis only (e.g., NAC blunting training adaptation at specific timing windows)
- **Personal validation** — confidence derived from the user's own longitudinal data showing a consistent pattern (e.g., "your HRV is consistently 8ms lower on days you take Adderall before 9am")

The system should never present low-confidence interpretations with high-confidence language. "Your NAC may be slightly reducing adaptation" is acceptable. "NAC is blunting your gains by 12%" is not.

## Interaction Modeling

When a user's profile contains multiple substances, the system checks for known interactions:

- **Pharmacokinetic interactions** — substances that affect each other's absorption, metabolism, or clearance
- **Pharmacodynamic interactions** — substances with overlapping or opposing mechanisms
- **Additive biomarker effects** — multiple substances pushing the same biomarker in the same direction (e.g., stimulant + pre-workout both elevating heart rate)

Interactions are surfaced as informational flags, not warnings. The system is explicit that it is not providing medical advice and that a healthcare provider should be consulted for interaction concerns.

## Data Source

Substance mechanism profiles can be sourced from:
- User's own Apothecary database (if integrated)
- A curated internal substance reference with conservative, evidence-based effect profiles
- Published pharmacological references (FDA labels, peer-reviewed research)

The system errs on the side of under-claiming rather than over-claiming. If the evidence for an effect is weak, the system either omits it or presents it at low confidence with appropriate hedging.

## Privacy

Medication and supplement data is among the most sensitive information in the system. It is stored locally, never transmitted to external services without explicit user consent, and is included in Claude API context only in anonymized/abstracted form (e.g., "user takes a CNS stimulant with 10-hour half-life" rather than "user takes Adderall 30mg").
