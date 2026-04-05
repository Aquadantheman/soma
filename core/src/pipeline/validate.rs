//! Data quality validation — range checks, physiological plausibility
//!
//! Ensures all signals fall within physiologically possible ranges before storage.
//! Invalid signals are flagged with reduced quality scores rather than rejected,
//! allowing downstream analysis to make informed decisions.

use crate::models::signal::Signal;

/// Validation result for a signal
#[derive(Debug, Clone)]
pub struct ValidationResult {
    /// Whether the signal passed validation
    pub is_valid: bool,
    /// Adjusted quality score (0-100)
    pub quality: u8,
    /// Warning messages for borderline values
    pub warnings: Vec<String>,
    /// Error messages for invalid values
    pub errors: Vec<String>,
}

impl ValidationResult {
    pub fn valid() -> Self {
        Self {
            is_valid: true,
            quality: 100,
            warnings: Vec::new(),
            errors: Vec::new(),
        }
    }

    pub fn with_warning(mut self, msg: impl Into<String>) -> Self {
        self.warnings.push(msg.into());
        self.quality = self.quality.saturating_sub(10);
        self
    }

    pub fn with_error(mut self, msg: impl Into<String>) -> Self {
        self.errors.push(msg.into());
        self.is_valid = false;
        self.quality = 0;
        self
    }
}

/// Physiological range for a biomarker
#[derive(Debug, Clone, Copy)]
pub struct PhysiologicalRange {
    /// Hard minimum - values below are physiologically impossible
    pub hard_min: f64,
    /// Soft minimum - values below are unusual but possible
    pub soft_min: f64,
    /// Soft maximum - values above are unusual but possible
    pub soft_max: f64,
    /// Hard maximum - values above are physiologically impossible
    pub hard_max: f64,
}

impl PhysiologicalRange {
    pub const fn new(hard_min: f64, soft_min: f64, soft_max: f64, hard_max: f64) -> Self {
        Self {
            hard_min,
            soft_min,
            soft_max,
            hard_max,
        }
    }

    /// Check if a value is within the valid range
    pub fn validate(&self, value: f64, biomarker: &str) -> ValidationResult {
        let mut result = ValidationResult::valid();

        if value < self.hard_min {
            return result.with_error(format!(
                "{} value {} is below physiological minimum {}",
                biomarker, value, self.hard_min
            ));
        }

        if value > self.hard_max {
            return result.with_error(format!(
                "{} value {} exceeds physiological maximum {}",
                biomarker, value, self.hard_max
            ));
        }

        if value < self.soft_min {
            result = result.with_warning(format!(
                "{} value {} is unusually low (expected >= {})",
                biomarker, value, self.soft_min
            ));
        }

        if value > self.soft_max {
            result = result.with_warning(format!(
                "{} value {} is unusually high (expected <= {})",
                biomarker, value, self.soft_max
            ));
        }

        result
    }
}

/// Get the physiological range for a biomarker slug
pub fn get_range(biomarker_slug: &str) -> Option<PhysiologicalRange> {
    // Ranges based on clinical literature and physiological limits
    let range = match biomarker_slug {
        // ─────────────────────────────────────────────────────────────────
        // AUTONOMIC
        // ─────────────────────────────────────────────────────────────────

        // Heart rate: athletes can have RHR of 30-40, max HR ~220-age
        "heart_rate" => PhysiologicalRange::new(20.0, 40.0, 200.0, 250.0),

        // Resting HR: elite athletes can be very low
        // Some devices record elevated "resting" HR during sleep disturbances
        "heart_rate_resting" => PhysiologicalRange::new(25.0, 35.0, 100.0, 140.0),

        // HRV RMSSD: typically 10-100ms, athletes can exceed 150ms
        "hrv_rmssd" => PhysiologicalRange::new(0.0, 10.0, 150.0, 300.0),

        // HRV SDNN: similar range to RMSSD
        "hrv_sdnn" => PhysiologicalRange::new(0.0, 10.0, 150.0, 300.0),

        // SpO2: <90% is hypoxemia, <70% is severe
        "spo2" => PhysiologicalRange::new(70.0, 90.0, 100.0, 100.0),

        // Respiratory rate: normal 12-20, can be 4-6 in trained breath-holders
        "respiratory_rate" => PhysiologicalRange::new(4.0, 8.0, 30.0, 60.0),

        // EDA tonic level: varies widely by individual
        "eda_tonic" => PhysiologicalRange::new(0.0, 0.1, 30.0, 50.0),

        // EDA phasic events per hour
        "eda_phasic_count" => PhysiologicalRange::new(0.0, 0.0, 60.0, 100.0),

        // ─────────────────────────────────────────────────────────────────
        // SLEEP (durations in minutes)
        // ─────────────────────────────────────────────────────────────────

        // Sleep stages: 0-720 min (12 hours) is reasonable, 24h max
        "sleep_rem" | "sleep_deep" | "sleep_core" => {
            PhysiologicalRange::new(0.0, 0.0, 240.0, 720.0)
        }

        // Time in bed: can be longer
        "sleep_in_bed" => PhysiologicalRange::new(0.0, 60.0, 720.0, 1440.0),

        // Total sleep duration
        "sleep_duration" => PhysiologicalRange::new(0.0, 180.0, 660.0, 1200.0),

        // Sleep percentages: 0-100%
        "sleep_rem_pct" | "sleep_deep_pct" | "sleep_core_pct" => {
            PhysiologicalRange::new(0.0, 5.0, 60.0, 100.0)
        }

        // Sleep efficiency: typically 85-95%
        "sleep_efficiency" => PhysiologicalRange::new(0.0, 50.0, 100.0, 100.0),

        // Sleep latency: time to fall asleep
        "sleep_latency" => PhysiologicalRange::new(0.0, 0.0, 60.0, 300.0),

        // Number of awakenings
        "sleep_awakenings" => PhysiologicalRange::new(0.0, 0.0, 20.0, 50.0),

        // ─────────────────────────────────────────────────────────────────
        // ACTIVITY
        // ─────────────────────────────────────────────────────────────────

        // Steps: 50k+ is ultra-marathon territory
        "steps" => PhysiologicalRange::new(0.0, 0.0, 50000.0, 150000.0),

        // Active energy burned (kcal)
        "active_energy" => PhysiologicalRange::new(0.0, 0.0, 5000.0, 15000.0),

        // Basal energy (kcal) - per sample, not daily total
        // Apple Health stores incremental values, so allow 0+
        "basal_energy" => PhysiologicalRange::new(0.0, 0.0, 200.0, 2000.0),

        // Activity score (device-specific, typically 0-100)
        "activity_score" | "physical_effort" => PhysiologicalRange::new(0.0, 0.0, 100.0, 100.0),

        // Stand hours: 0-24
        "stand_hours" => PhysiologicalRange::new(0.0, 0.0, 18.0, 24.0),

        // Stand/exercise time in minutes
        "stand_time" | "exercise_time" => PhysiologicalRange::new(0.0, 0.0, 480.0, 1440.0),

        // Flights climbed
        "flights_climbed" => PhysiologicalRange::new(0.0, 0.0, 100.0, 500.0),

        // Distance walking + running (meters)
        // Marathon = 42,195m, ultramarathons can exceed 100km
        "distance_walking_running" => PhysiologicalRange::new(0.0, 0.0, 50000.0, 200000.0),

        // MVPA minutes (moderate-to-vigorous physical activity)
        // WHO recommends 150-300 min/week, so ~20-45 min/day
        // Max would be continuous activity all day
        "exercise_intensity_min" => PhysiologicalRange::new(0.0, 0.0, 180.0, 1440.0),

        // ─────────────────────────────────────────────────────────────────
        // MOBILITY / GAIT
        // ─────────────────────────────────────────────────────────────────

        // Walking speed: typical 1.0-1.4 m/s, fast walkers ~2 m/s
        // Apple includes running in this metric, so allow up to 6 m/s (~3:40/km pace)
        "walking_speed" => PhysiologicalRange::new(0.0, 0.3, 2.5, 6.0),

        // Step length: typically 0.5-0.8m
        "walking_step_length" => PhysiologicalRange::new(0.1, 0.3, 1.0, 2.0),

        // Walking asymmetry: 0% is perfect symmetry
        "walking_asymmetry" => PhysiologicalRange::new(0.0, 0.0, 15.0, 50.0),

        // Double support time percentage
        "walking_double_support" => PhysiologicalRange::new(10.0, 15.0, 45.0, 70.0),

        // ─────────────────────────────────────────────────────────────────
        // CARDIORESPIRATORY FITNESS
        // ─────────────────────────────────────────────────────────────────

        // VO2 Max: elite endurance athletes can exceed 80 mL/kg/min
        "vo2_max" => PhysiologicalRange::new(10.0, 20.0, 70.0, 100.0),

        // ─────────────────────────────────────────────────────────────────
        // BODY COMPOSITION
        // ─────────────────────────────────────────────────────────────────

        // Body mass in kg
        "body_mass" => PhysiologicalRange::new(20.0, 30.0, 200.0, 400.0),

        // Body fat percentage: essential fat ~3% men, ~12% women
        "body_fat_percentage" => PhysiologicalRange::new(2.0, 5.0, 50.0, 70.0),

        // Lean body mass in kg
        "lean_body_mass" => PhysiologicalRange::new(15.0, 25.0, 120.0, 180.0),

        // BMI: <18.5 underweight, >30 obese
        "body_mass_index" => PhysiologicalRange::new(10.0, 15.0, 40.0, 80.0),

        // Height in meters
        "height" => PhysiologicalRange::new(0.5, 1.2, 2.2, 2.8),

        // Waist circumference in cm
        "waist_circumference" => PhysiologicalRange::new(30.0, 50.0, 150.0, 250.0),

        // ─────────────────────────────────────────────────────────────────
        // ENDOCRINE / TEMPERATURE
        // ─────────────────────────────────────────────────────────────────

        // Core temperature: <35°C is hypothermia, >40°C is hyperthermia
        "core_temp" => PhysiologicalRange::new(30.0, 35.0, 39.0, 43.0),

        // Skin temp delta from baseline
        "skin_temp_delta" => PhysiologicalRange::new(-5.0, -2.0, 2.0, 5.0),

        // Blood glucose: <70 is hypoglycemia, >180 is hyperglycemia
        "glucose" => PhysiologicalRange::new(20.0, 60.0, 200.0, 600.0),

        // Sweat cortisol (nmol/L)
        "cortisol_sweat" => PhysiologicalRange::new(0.0, 0.0, 50.0, 150.0),

        // ─────────────────────────────────────────────────────────────────
        // CARDIOVASCULAR (ACC/AHA 2017 Guidelines)
        // ─────────────────────────────────────────────────────────────────

        // Systolic BP: <90 hypotension, <120 optimal, 130-139 Stage 1 HTN, ≥140 Stage 2
        // Hard limits account for measurement during exercise or severe hypertensive crisis
        "bp_systolic" => PhysiologicalRange::new(60.0, 90.0, 140.0, 250.0),

        // Diastolic BP: <80 optimal, ≥90 hypertension
        // Must always be < systolic (enforced separately via cross-field validation)
        "bp_diastolic" => PhysiologicalRange::new(30.0, 50.0, 90.0, 150.0),

        // ─────────────────────────────────────────────────────────────────
        // CIRCADIAN TIMING (Roenneberg 2004, Phillips 2017)
        // Times as minutes since midnight (0-1439)
        // ─────────────────────────────────────────────────────────────────

        // Time in daylight (minutes): 0-1440 (24 hours)
        "time_in_daylight" => PhysiologicalRange::new(0.0, 0.0, 720.0, 1440.0),

        // Sleep onset/offset times: valid range is full 24h (0-1439 minutes)
        // Soft limits flag unusual times (e.g., sleeping at noon)
        // Onset: typical range 20:00-02:00 (1200-1439, 0-120)
        // We allow full range but flag unusual patterns
        "sleep_onset_time" | "sleep_offset_time" => {
            PhysiologicalRange::new(0.0, 0.0, 1439.0, 1439.0)
        }

        // Sleep midpoint: chronotype marker
        // <180 (3 AM) extreme early, 240-300 (4-5 AM) intermediate, >360 (6 AM) extreme late
        // Same as onset/offset - full range valid
        "sleep_midpoint" => PhysiologicalRange::new(0.0, 0.0, 1439.0, 1439.0),

        // Sleep Regularity Index (Phillips 2017)
        // Range: -100 (completely random) to +100 (perfectly regular)
        // <60 associated with depression and mood instability
        "sleep_regularity_index" => PhysiologicalRange::new(-100.0, 0.0, 100.0, 100.0),

        // Social Jet Lag (Wittmann 2006)
        // Absolute difference in minutes between weekend/weekday midpoints
        // >120 min associated with metabolic syndrome, depression
        "social_jetlag" => PhysiologicalRange::new(0.0, 0.0, 180.0, 720.0),

        // ─────────────────────────────────────────────────────────────────
        // RESPIRATORY / SLEEP APNEA (AASM 2017 Guidelines)
        // ─────────────────────────────────────────────────────────────────

        // Apnea-Hypopnea Index (events/hour)
        // <5 normal, 5-14 mild, 15-29 moderate, ≥30 severe OSA
        "ahi" => PhysiologicalRange::new(0.0, 0.0, 30.0, 120.0),

        // Oxygen Desaturation Index (events/hour)
        // Number of ≥3% desaturation events per hour of sleep
        "oxygen_desat_index" => PhysiologicalRange::new(0.0, 0.0, 30.0, 120.0),

        // ─────────────────────────────────────────────────────────────────
        // HORMONAL / MENSTRUAL (ACOG Guidelines)
        // ─────────────────────────────────────────────────────────────────

        // Menstrual cycle day: 1-45 (accounting for irregular cycles, amenorrhea)
        "menstrual_cycle_day" => PhysiologicalRange::new(1.0, 1.0, 35.0, 90.0),

        // Menstrual flow enum: 0=none, 1=spotting, 2=light, 3=medium, 4=heavy
        "menstrual_flow" => PhysiologicalRange::new(0.0, 0.0, 4.0, 4.0),

        // Basal body temperature (°C)
        // Measured immediately upon waking, before any activity
        // Follicular: 36.1-36.4°C, Luteal: 36.4-37.0°C (0.3-0.5°C rise post-ovulation)
        "basal_body_temp" => PhysiologicalRange::new(35.0, 35.5, 37.5, 38.5),

        // ─────────────────────────────────────────────────────────────────
        // SUBJECTIVE (1-10 scales)
        // ─────────────────────────────────────────────────────────────────
        "mood" | "energy" | "anxiety" | "focus" => PhysiologicalRange::new(1.0, 1.0, 10.0, 10.0),

        // ─────────────────────────────────────────────────────────────────
        // CARDIOVASCULAR RECOVERY (Cole et al. NEJM 1999)
        // ─────────────────────────────────────────────────────────────────

        // HR Recovery 1 min post-exercise: <12 bpm abnormal, >20 bpm excellent
        "hr_recovery_1min" => PhysiologicalRange::new(0.0, 12.0, 60.0, 100.0),

        // Walking heart rate average: depends on fitness level
        "walking_hr_avg" => PhysiologicalRange::new(40.0, 60.0, 140.0, 180.0),

        // ─────────────────────────────────────────────────────────────────
        // SLEEP BREATHING (Apple proxy for AHI)
        // ─────────────────────────────────────────────────────────────────

        // Breathing disturbances per hour (similar to AHI)
        "breathing_disturbances" => PhysiologicalRange::new(0.0, 0.0, 15.0, 120.0),

        // Sleep fragmentation index (awakenings per hour)
        "sleep_fragmentation" => PhysiologicalRange::new(0.0, 0.0, 10.0, 30.0),

        // ─────────────────────────────────────────────────────────────────
        // MOBILITY & FALL RISK
        // ─────────────────────────────────────────────────────────────────

        // Walking steadiness: 0-100%, >90% stable, <70% fall risk
        "walking_steadiness" => PhysiologicalRange::new(0.0, 50.0, 100.0, 100.0),

        // Gait/walking speed: <0.8 m/s frailty indicator (Studenski 2011)
        "gait_speed" => PhysiologicalRange::new(0.0, 0.5, 2.0, 4.0),

        // Stair climbing speeds (m/s vertical)
        "stair_ascent_speed" | "stair_descent_speed" => PhysiologicalRange::new(0.0, 0.2, 1.0, 2.0),

        // ─────────────────────────────────────────────────────────────────
        // RUNNING BIOMECHANICS
        // ─────────────────────────────────────────────────────────────────

        // Running speed: walking ~1.4 m/s, jogging 2-3 m/s, elite sprint ~10 m/s
        "running_speed" => PhysiologicalRange::new(0.0, 1.5, 8.0, 12.0),

        // Running power (Watts): depends on speed and body mass
        "running_power" => PhysiologicalRange::new(0.0, 100.0, 500.0, 1500.0),

        // Stride length: typically 1.0-2.5m depending on speed
        "stride_length" => PhysiologicalRange::new(0.5, 1.0, 3.0, 5.0),

        // Vertical oscillation: elite <6cm, recreational 8-12cm
        "vertical_oscillation" => PhysiologicalRange::new(0.0, 4.0, 15.0, 25.0),

        // Ground contact time: elite <200ms, recreational 250-300ms
        "ground_contact_time" => PhysiologicalRange::new(100.0, 150.0, 350.0, 500.0),

        // ─────────────────────────────────────────────────────────────────
        // ENVIRONMENT & AUDIO
        // ─────────────────────────────────────────────────────────────────

        // Daylight exposure (minutes): 30+ recommended
        "daylight_exposure" => PhysiologicalRange::new(0.0, 0.0, 480.0, 1440.0),

        // Audio exposure (dB): <70 safe, >85 risk of damage
        "headphone_exposure" | "noise_exposure_avg" => {
            PhysiologicalRange::new(30.0, 50.0, 85.0, 120.0)
        }

        // Peak noise exposure
        "noise_exposure_peak" => PhysiologicalRange::new(30.0, 50.0, 100.0, 140.0),

        // ─────────────────────────────────────────────────────────────────
        // TRAINING LOAD (Gabbett 2016)
        // ─────────────────────────────────────────────────────────────────

        // Acute training load (7-day TRIMP)
        "training_load_acute" => PhysiologicalRange::new(0.0, 0.0, 2000.0, 5000.0),

        // Chronic training load (28-day avg)
        "training_load_chronic" => PhysiologicalRange::new(0.0, 0.0, 2000.0, 5000.0),

        // Acute:Chronic workload ratio: 0.8-1.3 optimal, >1.5 injury risk
        "training_balance" => PhysiologicalRange::new(0.0, 0.5, 1.5, 3.0),

        // ─────────────────────────────────────────────────────────────────
        // RECOVERY & READINESS SCORES
        // ─────────────────────────────────────────────────────────────────

        // Computed scores: 0-100
        "recovery_score" | "cardio_recovery_score" | "mobility_score" | "stress_score" => {
            PhysiologicalRange::new(0.0, 0.0, 100.0, 100.0)
        }

        // HRV baseline (7-day median)
        "hrv_baseline" => PhysiologicalRange::new(0.0, 10.0, 150.0, 300.0),

        // HRV deviation from baseline (percentage)
        "hrv_deviation" => PhysiologicalRange::new(0.0, 50.0, 200.0, 500.0),

        // RHR baseline (7-day median)
        "rhr_baseline" => PhysiologicalRange::new(25.0, 35.0, 100.0, 140.0),

        // RHR deviation (bpm above/below baseline)
        "rhr_deviation" => PhysiologicalRange::new(-30.0, -10.0, 10.0, 30.0),

        // Circadian amplitude (HR max - HR min across 24h)
        "circadian_amplitude" => PhysiologicalRange::new(10.0, 20.0, 60.0, 100.0),

        // Autonomic balance (parasympathetic/sympathetic ratio)
        "autonomic_balance" => PhysiologicalRange::new(0.0, 0.5, 2.0, 5.0),

        // ─────────────────────────────────────────────────────────────────
        // NUTRITION
        // ─────────────────────────────────────────────────────────────────

        // Calories consumed
        "calories_consumed" => PhysiologicalRange::new(0.0, 500.0, 5000.0, 15000.0),

        // Macros (grams)
        "protein_intake" => PhysiologicalRange::new(0.0, 20.0, 300.0, 600.0),
        "carb_intake" => PhysiologicalRange::new(0.0, 50.0, 500.0, 1000.0),
        "fat_intake" => PhysiologicalRange::new(0.0, 20.0, 200.0, 500.0),

        // Water intake (mL)
        "water_intake" => PhysiologicalRange::new(0.0, 500.0, 5000.0, 15000.0),

        // Calorie balance (surplus/deficit)
        "calorie_balance" => PhysiologicalRange::new(-5000.0, -1500.0, 1500.0, 5000.0),

        // ─────────────────────────────────────────────────────────────────
        // CYCLING & SWIMMING
        // ─────────────────────────────────────────────────────────────────

        // Cycling distance (meters)
        "distance_cycling" => PhysiologicalRange::new(0.0, 0.0, 200000.0, 500000.0),

        // Swimming distance (meters)
        "distance_swimming" => PhysiologicalRange::new(0.0, 0.0, 10000.0, 50000.0),

        // Swimming strokes
        "swimming_strokes" => PhysiologicalRange::new(0.0, 0.0, 5000.0, 20000.0),

        // Unknown biomarker - skip validation
        _ => return None,
    };

    Some(range)
}

/// Validate a signal and return the result
pub fn validate_signal(signal: &Signal) -> ValidationResult {
    // If no value, nothing to validate
    let value = match signal.value {
        Some(v) => v,
        None => {
            // Text-only signals (like notes) are valid
            if signal.value_text.is_some() {
                return ValidationResult::valid();
            }
            return ValidationResult::valid().with_warning("Signal has no value or text");
        }
    };

    // Check for NaN or infinity
    if value.is_nan() {
        return ValidationResult::valid().with_error("Signal value is NaN");
    }
    if value.is_infinite() {
        return ValidationResult::valid().with_error("Signal value is infinite");
    }

    // Get range for this biomarker
    match get_range(&signal.biomarker_slug) {
        Some(range) => range.validate(value, &signal.biomarker_slug),
        None => {
            // Unknown biomarker - pass through with warning
            ValidationResult::valid().with_warning(format!(
                "No validation rules for biomarker '{}'",
                signal.biomarker_slug
            ))
        }
    }
}

/// Validate a signal in-place, updating its quality score
pub fn validate_and_update(signal: &mut Signal) -> ValidationResult {
    let result = validate_signal(signal);

    // Update quality score based on validation
    let base_quality = signal.quality;
    signal.quality = std::cmp::min(base_quality, result.quality);

    result
}

// ═══════════════════════════════════════════════════════════════════════════════
// CROSS-FIELD VALIDATION
// ═══════════════════════════════════════════════════════════════════════════════

/// Cross-field validation result for related biomarkers
#[derive(Debug, Clone)]
pub struct CrossFieldValidationResult {
    /// Whether the relationship is valid
    pub is_valid: bool,
    /// Warning or error message
    pub message: Option<String>,
    /// Quality penalty to apply
    pub quality_penalty: u8,
}

impl CrossFieldValidationResult {
    pub fn valid() -> Self {
        Self {
            is_valid: true,
            message: None,
            quality_penalty: 0,
        }
    }

    pub fn warning(msg: impl Into<String>) -> Self {
        Self {
            is_valid: true,
            message: Some(msg.into()),
            quality_penalty: 20,
        }
    }

    pub fn error(msg: impl Into<String>) -> Self {
        Self {
            is_valid: false,
            message: Some(msg.into()),
            quality_penalty: 100,
        }
    }
}

/// Validate blood pressure: systolic must be greater than diastolic
///
/// Physiological constraint: The peak pressure during heart contraction (systolic)
/// must always exceed the minimum pressure during relaxation (diastolic).
///
/// # Arguments
/// * `systolic` - Systolic blood pressure in mmHg
/// * `diastolic` - Diastolic blood pressure in mmHg
///
/// # Returns
/// * Valid if systolic > diastolic
/// * Warning if systolic is only slightly higher (< 20 mmHg difference)
/// * Error if systolic <= diastolic (physiologically impossible)
pub fn validate_blood_pressure(systolic: f64, diastolic: f64) -> CrossFieldValidationResult {
    // Impossible: systolic must be greater than diastolic
    if systolic <= diastolic {
        return CrossFieldValidationResult::error(format!(
            "Invalid blood pressure: systolic ({:.0}) must be greater than diastolic ({:.0})",
            systolic, diastolic
        ));
    }

    // Pulse pressure = systolic - diastolic
    let pulse_pressure = systolic - diastolic;

    // Normal pulse pressure: 40-60 mmHg
    // Warning for very narrow pulse pressure (< 20 mmHg) - may indicate heart failure
    if pulse_pressure < 20.0 {
        return CrossFieldValidationResult::warning(format!(
            "Narrow pulse pressure ({:.0} mmHg): systolic={:.0}, diastolic={:.0}. May indicate cardiac issue.",
            pulse_pressure, systolic, diastolic
        ));
    }

    // Warning for very wide pulse pressure (> 100 mmHg) - may indicate aortic issues
    if pulse_pressure > 100.0 {
        return CrossFieldValidationResult::warning(format!(
            "Wide pulse pressure ({:.0} mmHg): systolic={:.0}, diastolic={:.0}. May indicate arterial stiffness.",
            pulse_pressure, systolic, diastolic
        ));
    }

    CrossFieldValidationResult::valid()
}

/// Validate sleep architecture: total sleep should roughly match sum of stages
///
/// # Arguments
/// * `total_sleep` - Total sleep duration in minutes
/// * `rem` - REM sleep duration in minutes
/// * `deep` - Deep sleep duration in minutes
/// * `core` - Core/light sleep duration in minutes
///
/// # Returns
/// * Valid if stages sum to approximately total (within 10% tolerance)
/// * Warning if mismatch exceeds 10%
pub fn validate_sleep_architecture(
    total_sleep: f64,
    rem: f64,
    deep: f64,
    core: f64,
) -> CrossFieldValidationResult {
    let stage_sum = rem + deep + core;

    // Allow 10% tolerance for tracking inaccuracies
    let tolerance = total_sleep * 0.1;
    let difference = (total_sleep - stage_sum).abs();

    if difference > tolerance {
        return CrossFieldValidationResult::warning(format!(
            "Sleep stage mismatch: total={:.0}min but stages sum to {:.0}min (REM={:.0}, Deep={:.0}, Core={:.0})",
            total_sleep, stage_sum, rem, deep, core
        ));
    }

    CrossFieldValidationResult::valid()
}

/// Validate heart rate recovery: recovery HR should be lower than exercise HR
///
/// # Arguments
/// * `exercise_hr` - Heart rate during exercise (bpm)
/// * `recovery_hr` - Heart rate 1 minute after exercise (bpm)
///
/// # Returns
/// * Valid if recovery_hr < exercise_hr
/// * Warning if recovery is poor (< 12 bpm drop)
pub fn validate_hr_recovery(exercise_hr: f64, recovery_hr: f64) -> CrossFieldValidationResult {
    // Recovery HR must be lower than exercise HR
    if recovery_hr >= exercise_hr {
        return CrossFieldValidationResult::error(format!(
            "Invalid HR recovery: recovery HR ({:.0}) should be lower than exercise HR ({:.0})",
            recovery_hr, exercise_hr
        ));
    }

    let recovery_amount = exercise_hr - recovery_hr;

    // < 12 bpm recovery in 1 minute is associated with increased mortality risk
    // (Cole et al. NEJM 1999)
    if recovery_amount < 12.0 {
        return CrossFieldValidationResult::warning(format!(
            "Poor HR recovery: only {:.0} bpm drop in 1 minute (target: >12 bpm)",
            recovery_amount
        ));
    }

    CrossFieldValidationResult::valid()
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    fn make_signal(slug: &str, value: f64) -> Signal {
        Signal::new(Utc::now(), slug, value, "test")
    }

    #[test]
    fn test_heart_rate_valid() {
        let signal = make_signal("heart_rate", 72.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert_eq!(result.quality, 100);
        assert!(result.warnings.is_empty());
    }

    #[test]
    fn test_heart_rate_low_warning() {
        let signal = make_signal("heart_rate", 35.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert!(result.quality < 100);
        assert!(!result.warnings.is_empty());
    }

    #[test]
    fn test_heart_rate_invalid() {
        let signal = make_signal("heart_rate", 300.0);
        let result = validate_signal(&signal);
        assert!(!result.is_valid);
        assert_eq!(result.quality, 0);
    }

    #[test]
    fn test_spo2_valid() {
        let signal = make_signal("spo2", 98.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert_eq!(result.quality, 100);
    }

    #[test]
    fn test_spo2_low_warning() {
        let signal = make_signal("spo2", 88.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert!(!result.warnings.is_empty());
    }

    #[test]
    fn test_steps_extreme_but_valid() {
        let signal = make_signal("steps", 75000.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        // Should have warning for unusually high
        assert!(!result.warnings.is_empty());
    }

    #[test]
    fn test_unknown_biomarker() {
        let signal = make_signal("unknown_metric", 50.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert!(!result.warnings.is_empty());
    }

    #[test]
    fn test_nan_value() {
        let signal = make_signal("heart_rate", f64::NAN);
        let result = validate_signal(&signal);
        assert!(!result.is_valid);
    }

    #[test]
    fn test_infinity_value() {
        let signal = make_signal("steps", f64::INFINITY);
        let result = validate_signal(&signal);
        assert!(!result.is_valid);
    }

    // ─────────────────────────────────────────────────────────────────
    // Clinical Biomarker Tests
    // ─────────────────────────────────────────────────────────────────

    #[test]
    fn test_bp_systolic_optimal() {
        let signal = make_signal("bp_systolic", 118.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert_eq!(result.quality, 100);
    }

    #[test]
    fn test_bp_systolic_hypertensive() {
        // Stage 2 hypertension - valid but flagged
        let signal = make_signal("bp_systolic", 155.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert!(!result.warnings.is_empty()); // Should warn about high BP
    }

    #[test]
    fn test_bp_systolic_crisis() {
        // Hypertensive crisis level - still physiologically possible
        let signal = make_signal("bp_systolic", 220.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid); // Extreme but possible
    }

    #[test]
    fn test_bp_systolic_impossible() {
        // Above hard max
        let signal = make_signal("bp_systolic", 280.0);
        let result = validate_signal(&signal);
        assert!(!result.is_valid);
    }

    #[test]
    fn test_bp_diastolic_normal() {
        let signal = make_signal("bp_diastolic", 78.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert_eq!(result.quality, 100);
    }

    #[test]
    fn test_ahi_normal() {
        let signal = make_signal("ahi", 3.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert_eq!(result.quality, 100);
    }

    #[test]
    fn test_ahi_severe_osa() {
        // Severe OSA (≥30) - valid but flagged
        let signal = make_signal("ahi", 45.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert!(!result.warnings.is_empty());
    }

    #[test]
    fn test_sleep_regularity_index_good() {
        let signal = make_signal("sleep_regularity_index", 75.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert_eq!(result.quality, 100);
    }

    #[test]
    fn test_sleep_regularity_index_poor() {
        // Negative SRI indicates irregular sleep
        let signal = make_signal("sleep_regularity_index", -25.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert!(!result.warnings.is_empty());
    }

    #[test]
    fn test_social_jetlag_normal() {
        let signal = make_signal("social_jetlag", 45.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert_eq!(result.quality, 100);
    }

    #[test]
    fn test_social_jetlag_excessive() {
        // >180 min is extreme social jet lag
        let signal = make_signal("social_jetlag", 240.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert!(!result.warnings.is_empty());
    }

    #[test]
    fn test_menstrual_cycle_day_valid() {
        let signal = make_signal("menstrual_cycle_day", 14.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert_eq!(result.quality, 100);
    }

    #[test]
    fn test_menstrual_cycle_day_long_cycle() {
        // Irregular/long cycle
        let signal = make_signal("menstrual_cycle_day", 42.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert!(!result.warnings.is_empty());
    }

    #[test]
    fn test_basal_body_temp_follicular() {
        let signal = make_signal("basal_body_temp", 36.3);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert_eq!(result.quality, 100);
    }

    #[test]
    fn test_basal_body_temp_luteal() {
        // Post-ovulation rise
        let signal = make_signal("basal_body_temp", 36.8);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert_eq!(result.quality, 100);
    }

    #[test]
    fn test_distance_walking_running_marathon() {
        let signal = make_signal("distance_walking_running", 42195.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert_eq!(result.quality, 100);
    }

    #[test]
    fn test_exercise_intensity_min_normal() {
        let signal = make_signal("exercise_intensity_min", 35.0);
        let result = validate_signal(&signal);
        assert!(result.is_valid);
        assert_eq!(result.quality, 100);
    }

    // ─────────────────────────────────────────────────────────────────
    // Cross-Field Validation Tests
    // ─────────────────────────────────────────────────────────────────

    #[test]
    fn test_blood_pressure_valid() {
        let result = validate_blood_pressure(120.0, 80.0);
        assert!(result.is_valid);
        assert!(result.message.is_none());
    }

    #[test]
    fn test_blood_pressure_invalid_systolic_lower() {
        let result = validate_blood_pressure(70.0, 80.0);
        assert!(!result.is_valid);
        assert!(result.message.is_some());
    }

    #[test]
    fn test_blood_pressure_narrow_pulse_pressure() {
        // 100/90 = pulse pressure of only 10 mmHg
        let result = validate_blood_pressure(100.0, 90.0);
        assert!(result.is_valid);
        assert!(result.message.is_some()); // Warning about narrow pulse pressure
    }

    #[test]
    fn test_blood_pressure_wide_pulse_pressure() {
        // 200/80 = pulse pressure of 120 mmHg
        let result = validate_blood_pressure(200.0, 80.0);
        assert!(result.is_valid);
        assert!(result.message.is_some()); // Warning about wide pulse pressure
    }

    #[test]
    fn test_sleep_architecture_valid() {
        // 7 hours total, roughly matching stages
        let result = validate_sleep_architecture(420.0, 90.0, 100.0, 230.0);
        assert!(result.is_valid);
        assert!(result.message.is_none());
    }

    #[test]
    fn test_sleep_architecture_mismatch() {
        // 7 hours total but stages only sum to 5 hours
        let result = validate_sleep_architecture(420.0, 60.0, 60.0, 180.0);
        assert!(result.is_valid);
        assert!(result.message.is_some()); // Warning about mismatch
    }

    #[test]
    fn test_hr_recovery_good() {
        // 30 bpm drop - excellent recovery
        let result = validate_hr_recovery(160.0, 130.0);
        assert!(result.is_valid);
        assert!(result.message.is_none());
    }

    #[test]
    fn test_hr_recovery_poor() {
        // Only 8 bpm drop - poor recovery
        let result = validate_hr_recovery(160.0, 152.0);
        assert!(result.is_valid);
        assert!(result.message.is_some()); // Warning about poor recovery
    }

    #[test]
    fn test_hr_recovery_invalid() {
        // Recovery HR higher than exercise - impossible
        let result = validate_hr_recovery(140.0, 150.0);
        assert!(!result.is_valid);
    }
}
