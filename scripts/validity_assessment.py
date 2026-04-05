"""Scientific validity assessment of discovered correlations."""

print('=' * 75)
print('SCIENTIFIC VALIDITY ASSESSMENT')
print('=' * 75)

print("""
Evaluating each finding against:
1. Statistical power (sample size, p-value)
2. Effect size (is it meaningful?)
3. Confounding risk (spurious correlation?)
4. Biological plausibility (mechanism?)
5. Literature support (known relationship?)

Scoring: VALID / WEAK / ARTIFACT / SPURIOUS
""")

findings = [
    {
        "name": "RESPIRATORY RATE <-> SLEEP",
        "r": -0.46,
        "n": 88,
        "p": "<0.001",
        "stats_quality": "Good - adequate n, highly significant",
        "confound_risk": "LOW - same-night measurements",
        "bio_plausibility": """STRONG
  - Deep sleep = parasympathetic = slower breathing
  - Higher resp rate = sympathetic = lighter sleep
  - Standard in polysomnography""",
        "literature": """STRONG
  - Respiratory rate variability used in sleep staging
  - RR drops 10-20% in deep vs light sleep
  - Krieger (1990), multiple replication studies""",
        "verdict": "VALID",
        "actionable": "Yes - track as sleep quality predictor"
    },
    {
        "name": "BODY FAT <-> AUDIO EXPOSURE",
        "r": 0.50,
        "n": 43,
        "p": "<0.001",
        "stats_quality": "POOR - n=43 is too small, inflates r",
        "confound_risk": "HIGH - both measured sporadically, lifestyle confound",
        "bio_plausibility": """WEAK
  - No direct physiological mechanism
  - Behavioral correlation at best
  - Indoor time affects both?""",
        "literature": "NONE - no known research",
        "verdict": "SPURIOUS",
        "actionable": "No - discard this finding"
    },
    {
        "name": "VO2 MAX <-> DAYLIGHT",
        "r": -0.35,
        "n": 73,
        "p": "0.002",
        "stats_quality": "Marginal - sparse VO2 measurements",
        "confound_risk": """HIGH
  - Seasonal confound
  - Training context: gym vs outdoor
  - VO2 peaks in Oct-Nov (cooler months)""",
        "bio_plausibility": """BACKWARDS
  - More daylight should IMPROVE fitness
  - But you train harder when its cooler
  - Measurement artifact, not biology""",
        "literature": "N/A - this is an artifact",
        "verdict": "ARTIFACT",
        "actionable": "No - real pattern, wrong interpretation"
    },
    {
        "name": "EXERCISE <-> AUDIO",
        "r": 0.34,
        "n": 445,
        "p": "<0.001",
        "stats_quality": "GOOD - large n, highly significant",
        "confound_risk": "LOW - same-day, clear temporal link",
        "bio_plausibility": """STRONG
  - People listen to music while exercising
  - Gym environments are louder
  - Workout playlists common behavior""",
        "literature": """MODERATE
  - Exercise psychology studies on music
  - WHO warnings on headphone use
  - Hearing damage research""",
        "verdict": "VALID",
        "actionable": "Yes - consider hearing protection"
    },
    {
        "name": "DAYLIGHT -> ACTIVITY",
        "r": "0.54-0.71",
        "n": 236,
        "p": "<0.001",
        "stats_quality": "GOOD - adequate n, large effects",
        "confound_risk": """MODERATE
  - Weather confound exists
  - But daylight IS the mechanism for outdoor behavior""",
        "bio_plausibility": """STRONG
  - More light = more outdoor time = more steps
  - Circadian effects on energy/mood
  - Vitamin D and serotonin pathways""",
        "literature": """STRONG
  - Extensive circadian biology research
  - SAD and light therapy literature
  - Seasonal activity patterns well-documented""",
        "verdict": "VALID",
        "actionable": "Yes - maximize daylight exposure"
    },
    {
        "name": "SLEEP -> HRV (3-day lag)",
        "r": 0.22,
        "n": "~90",
        "p": "0.039",
        "stats_quality": "WEAK - small effect, marginal p-value",
        "confound_risk": """MODERATE
  - Multiple testing (many lags tested)
  - Small effect could be noise""",
        "bio_plausibility": """STRONG
  - Sleep is primary recovery mechanism
  - HRV reflects autonomic balance
  - Cumulative effects are plausible""",
        "literature": """STRONG
  - Extensive sleep-HRV literature
  - Used in athlete monitoring
  - Meta-analyses confirm relationship""",
        "verdict": "WEAK but DIRECTION CORRECT",
        "actionable": "Maybe - same-day r=0.35 is more reliable"
    },
    {
        "name": "ACTIVITY MOMENTUM (autocorr)",
        "r": 0.44,
        "n": "1000s",
        "p": "N/A (autocorrelation)",
        "stats_quality": "GOOD - inherent statistical property",
        "confound_risk": "LOW - no external confound needed",
        "bio_plausibility": """STRONG
  - Habits create persistence
  - Energy levels carry over
  - Work/social schedules create patterns""",
        "literature": """STRONG
  - Behavioral economics: habit formation
  - Exercise adherence research
  - Well-established phenomenon""",
        "verdict": "VALID",
        "actionable": "Yes - leverage habit momentum"
    },
    {
        "name": "SpO2 NOCTURNAL DIP",
        "r": "N/A",
        "n": 2455,
        "p": "<0.001 (t=12.9)",
        "stats_quality": "EXCELLENT - large n, huge t-statistic",
        "confound_risk": "LOW - direct measurement, clear separation",
        "bio_plausibility": """STRONG
  - Recumbent position affects breathing
  - Sleep reduces ventilation drive
  - Fundamental sleep physiology""",
        "literature": """STRONG
  - Core finding in sleep medicine
  - SpO2 dips diagnose sleep apnea
  - Clinical guidelines exist""",
        "verdict": "VALID (CLINICAL GRADE)",
        "actionable": "Yes - monitor, consider clinical evaluation"
    },
]

print('=' * 75)
for f in findings:
    print(f"\n{f['name']}")
    print("-" * 50)
    print(f"Correlation: r = {f['r']}, n = {f['n']}, p = {f['p']}")
    print(f"\nStatistical Quality: {f['stats_quality']}")
    print(f"\nConfound Risk: {f['confound_risk']}")
    print(f"\nBiological Plausibility: {f['bio_plausibility']}")
    print(f"\nLiterature Support: {f['literature']}")
    print(f"\n>>> VERDICT: {f['verdict']}")
    print(f">>> Actionable: {f['actionable']}")
    print('=' * 75)

print("""
FINAL SUMMARY: WHAT TO TRUST
============================

DEFINITELY VALID (use with confidence):
  1. SpO2 Nocturnal Dip - clinical-grade finding
  2. Respiratory Rate <-> Sleep - physiologically grounded
  3. Daylight -> Activity - well-established mechanism
  4. Exercise <-> Audio - clear causal pathway
  5. Activity Momentum - statistical fact

LIKELY VALID (use with caution):
  6. Sleep -> HRV - correct direction, weak signal

DO NOT USE:
  7. VO2 <-> Daylight - measurement artifact (misinterpretation)
  8. Body Fat <-> Audio - spurious (small n, no mechanism)


KEY STATISTICAL CONCERNS:
- Small sample sizes (n < 50) inflate correlations
- Multiple testing without correction
- Time trends can create spurious correlations
- Correlation != Causation (always)


STRONGEST EVIDENCE:
- SpO2 patterns (2,455 samples, t=12.9, Cohen d=0.60)
- Daylight effects (236 samples, r > 0.5)
- Respiratory-Sleep link (physiologically grounded)
""")
