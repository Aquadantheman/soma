//! Unit normalization — convert all signals to canonical Soma units
//!
//! Different data sources use different units for the same biomarker.
//! This module normalizes everything to canonical units for consistent analysis.
//!
//! Canonical units:
//! - Time durations: minutes (min)
//! - Heart rate: beats per minute (bpm)
//! - HRV: milliseconds (ms)
//! - SpO2: percentage (0-100)
//! - Weight: kilograms (kg)
//! - Height: meters (m)
//! - Speed: meters per second (m/s)
//! - Energy: kilocalories (kcal)
//! - Temperature: Celsius (°C)
//! - Glucose: mg/dL

use crate::models::signal::Signal;
use tracing::debug;

/// Result of normalization
#[derive(Debug, Clone)]
pub struct NormalizationResult {
    /// The normalized value
    pub value: f64,
    /// Whether any conversion was applied
    pub was_converted: bool,
    /// Description of conversion applied (if any)
    pub conversion_note: Option<String>,
}

impl NormalizationResult {
    pub fn unchanged(value: f64) -> Self {
        Self {
            value,
            was_converted: false,
            conversion_note: None,
        }
    }

    pub fn converted(value: f64, note: impl Into<String>) -> Self {
        Self {
            value,
            was_converted: true,
            conversion_note: Some(note.into()),
        }
    }
}

/// Unit conversion factors
pub mod conversions {
    // Time
    pub const SECONDS_TO_MINUTES: f64 = 1.0 / 60.0;
    pub const HOURS_TO_MINUTES: f64 = 60.0;
    pub const MILLISECONDS_TO_MINUTES: f64 = 1.0 / 60000.0;

    // HRV: microseconds to milliseconds
    pub const MICROSECONDS_TO_MS: f64 = 0.001;
    pub const SECONDS_TO_MS: f64 = 1000.0;

    // SpO2: ratio to percentage
    pub const RATIO_TO_PERCENT: f64 = 100.0;

    // Weight
    pub const LBS_TO_KG: f64 = 0.453592;
    pub const STONE_TO_KG: f64 = 6.35029;

    // Height
    pub const CM_TO_M: f64 = 0.01;
    pub const INCHES_TO_M: f64 = 0.0254;
    pub const FEET_TO_M: f64 = 0.3048;

    // Speed
    pub const KMH_TO_MS: f64 = 1.0 / 3.6;
    pub const MPH_TO_MS: f64 = 0.44704;

    // Temperature
    pub const FAHRENHEIT_TO_CELSIUS: fn(f64) -> f64 = |f| (f - 32.0) * 5.0 / 9.0;
    pub const KELVIN_TO_CELSIUS: fn(f64) -> f64 = |k| k - 273.15;

    // Energy
    pub const KJ_TO_KCAL: f64 = 0.239006;
    pub const JOULES_TO_KCAL: f64 = 0.000239006;

    // Glucose
    pub const MMOL_TO_MGDL: f64 = 18.0182;

    // Blood Pressure
    // 1 kPa = 7.50062 mmHg (some devices export in kPa)
    pub const KPA_TO_MMHG: f64 = 7.50062;

    // Distance
    pub const KM_TO_M: f64 = 1000.0;
    pub const MILES_TO_M: f64 = 1609.344;
    // Note: FEET_TO_M already defined in Height section
}

/// Detect and apply unit normalization for a biomarker value
///
/// This function uses heuristics to detect when values are likely in
/// non-canonical units and converts them appropriately.
pub fn normalize_value(biomarker_slug: &str, value: f64, source_slug: &str) -> NormalizationResult {
    match biomarker_slug {
        // ─────────────────────────────────────────────────────────────────
        // HRV: Apple Health sometimes stores in seconds, should be ms
        // ─────────────────────────────────────────────────────────────────
        "hrv_rmssd" | "hrv_sdnn" => {
            // If value is very small (<1), it's probably in seconds
            if value < 1.0 && value > 0.0 {
                return NormalizationResult::converted(
                    value * conversions::SECONDS_TO_MS,
                    "Converted HRV from seconds to milliseconds",
                );
            }
            // If value is very large (>1000), it might be microseconds
            if value > 1000.0 {
                return NormalizationResult::converted(
                    value * conversions::MICROSECONDS_TO_MS,
                    "Converted HRV from microseconds to milliseconds",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // SpO2: Some sources report as ratio (0-1) instead of percentage
        // ─────────────────────────────────────────────────────────────────
        "spo2" => {
            if value <= 1.0 && value > 0.0 {
                return NormalizationResult::converted(
                    value * conversions::RATIO_TO_PERCENT,
                    "Converted SpO2 from ratio to percentage",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Body fat percentage: Same as SpO2
        // ─────────────────────────────────────────────────────────────────
        "body_fat_percentage" => {
            if value <= 1.0 && value > 0.0 {
                return NormalizationResult::converted(
                    value * conversions::RATIO_TO_PERCENT,
                    "Converted body fat from ratio to percentage",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Sleep efficiency: ratio to percentage
        // ─────────────────────────────────────────────────────────────────
        "sleep_efficiency" | "sleep_rem_pct" | "sleep_deep_pct" | "sleep_core_pct" => {
            if value <= 1.0 && value > 0.0 {
                return NormalizationResult::converted(
                    value * conversions::RATIO_TO_PERCENT,
                    "Converted sleep percentage from ratio",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Walking asymmetry: ratio to percentage
        // ─────────────────────────────────────────────────────────────────
        "walking_asymmetry" | "walking_double_support" => {
            if value <= 1.0 && value > 0.0 {
                return NormalizationResult::converted(
                    value * conversions::RATIO_TO_PERCENT,
                    "Converted percentage from ratio",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Weight: detect lbs vs kg (Apple Health exports in lbs from US devices)
        // ─────────────────────────────────────────────────────────────────
        "body_mass" | "lean_body_mass" => {
            // Heuristic: if value > 150, it's likely in lbs (few people weigh >150kg)
            // But athletes can be heavy, so use 250 as threshold
            // Check source for hints
            if source_slug == "apple_health" && value > 250.0 {
                return NormalizationResult::converted(
                    value * conversions::LBS_TO_KG,
                    "Converted weight from lbs to kg",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Height: detect cm vs m
        // ─────────────────────────────────────────────────────────────────
        "height" => {
            // If value > 3, it's likely in cm (people aren't >3m tall)
            if value > 3.0 {
                return NormalizationResult::converted(
                    value * conversions::CM_TO_M,
                    "Converted height from cm to meters",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Temperature: detect Fahrenheit vs Celsius
        // ─────────────────────────────────────────────────────────────────
        "core_temp" => {
            // Human body temp in C: 35-42. In F: 95-108
            // If value > 50, it's likely Fahrenheit
            if value > 50.0 {
                return NormalizationResult::converted(
                    (conversions::FAHRENHEIT_TO_CELSIUS)(value),
                    "Converted temperature from Fahrenheit to Celsius",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Glucose: detect mmol/L vs mg/dL
        // ─────────────────────────────────────────────────────────────────
        "glucose" => {
            // Normal glucose: 70-100 mg/dL = 3.9-5.6 mmol/L
            // If value < 30, it's likely mmol/L
            if value < 30.0 && value > 0.0 {
                return NormalizationResult::converted(
                    value * conversions::MMOL_TO_MGDL,
                    "Converted glucose from mmol/L to mg/dL",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Sleep durations: ensure minutes (some sources use hours or seconds)
        // ─────────────────────────────────────────────────────────────────
        "sleep_rem" | "sleep_deep" | "sleep_core" | "sleep_in_bed" | "sleep_duration" => {
            // If value is in typical hour range (0.5-12 hours), convert to minutes
            // Tightened from <15 to 0.5-12 to avoid false positives for short naps in minutes
            if value >= 0.5 && value <= 12.0 {
                let as_minutes = value * conversions::HOURS_TO_MINUTES;
                // Only convert if result is reasonable (30-720 minutes = 0.5-12 hours)
                if as_minutes >= 30.0 && as_minutes <= 720.0 {
                    return NormalizationResult::converted(
                        as_minutes,
                        "Converted sleep duration from hours to minutes",
                    );
                }
            }
            // If value is very large (>2000), definitely in seconds
            if value > 2000.0 {
                return NormalizationResult::converted(
                    value * conversions::SECONDS_TO_MINUTES,
                    "Converted sleep duration from seconds to minutes",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // Sleep latency handled separately - different typical ranges
        "sleep_latency" => {
            // Latency is typically 5-60 minutes; if <1, might be hours (unusual)
            // If >2000, definitely seconds
            if value > 2000.0 {
                return NormalizationResult::converted(
                    value * conversions::SECONDS_TO_MINUTES,
                    "Converted sleep latency from seconds to minutes",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Blood Pressure: detect kPa vs mmHg
        // Normal BP ~120/80 mmHg = ~16/10.7 kPa
        // ─────────────────────────────────────────────────────────────────
        "bp_systolic" => {
            // If value < 30, it's likely in kPa (120 mmHg = 16 kPa)
            if value > 0.0 && value < 30.0 {
                return NormalizationResult::converted(
                    value * conversions::KPA_TO_MMHG,
                    "Converted blood pressure from kPa to mmHg",
                );
            }
            NormalizationResult::unchanged(value)
        }

        "bp_diastolic" => {
            // If value < 20, it's likely in kPa (80 mmHg = 10.7 kPa)
            if value > 0.0 && value < 20.0 {
                return NormalizationResult::converted(
                    value * conversions::KPA_TO_MMHG,
                    "Converted blood pressure from kPa to mmHg",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Basal Body Temperature: same logic as core_temp
        // ─────────────────────────────────────────────────────────────────
        "basal_body_temp" => {
            // BBT in C: 35.5-38. In F: 96-100
            // If value > 50, it's likely Fahrenheit
            if value > 50.0 {
                return NormalizationResult::converted(
                    (conversions::FAHRENHEIT_TO_CELSIUS)(value),
                    "Converted basal body temperature from Fahrenheit to Celsius",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Distance: detect km vs meters
        // ─────────────────────────────────────────────────────────────────
        "distance_walking_running" => {
            // Heuristic: If value < 200, it's likely in km (even ultra marathons are ~170km)
            // Typical daily walking: 3-10 km = 3000-10000 m
            // If source indicates km, convert
            if value > 0.0 && value < 200.0 {
                return NormalizationResult::converted(
                    value * conversions::KM_TO_M,
                    "Converted distance from km to meters",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Exercise/Activity minutes: detect hours or seconds
        // ─────────────────────────────────────────────────────────────────
        "exercise_intensity_min" | "stand_time" | "exercise_time" => {
            // If value is small (<10), might be in hours
            if value > 0.0 && value < 10.0 {
                let as_minutes = value * conversions::HOURS_TO_MINUTES;
                // Sanity check: converted value should be reasonable (10-600 min)
                if as_minutes >= 10.0 && as_minutes <= 600.0 {
                    return NormalizationResult::converted(
                        as_minutes,
                        "Converted exercise time from hours to minutes",
                    );
                }
            }
            // If value is very large (>2000), might be in seconds
            if value > 2000.0 {
                return NormalizationResult::converted(
                    value * conversions::SECONDS_TO_MINUTES,
                    "Converted exercise time from seconds to minutes",
                );
            }
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Sleep timing: no conversion needed (stored as minutes since midnight)
        // Values are already validated to be 0-1439
        // ─────────────────────────────────────────────────────────────────
        "sleep_onset_time" | "sleep_offset_time" | "sleep_midpoint" => {
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Circadian computed metrics: no conversion
        // ─────────────────────────────────────────────────────────────────
        "sleep_regularity_index" | "social_jetlag" => {
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Respiratory metrics: no conversion (events/hour is standard)
        // ─────────────────────────────────────────────────────────────────
        "ahi" | "oxygen_desat_index" => {
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Menstrual metrics: no conversion
        // ─────────────────────────────────────────────────────────────────
        "menstrual_cycle_day" | "menstrual_flow" => {
            NormalizationResult::unchanged(value)
        }

        // ─────────────────────────────────────────────────────────────────
        // Default: no conversion needed
        // ─────────────────────────────────────────────────────────────────
        _ => NormalizationResult::unchanged(value),
    }
}

/// Normalize a signal in-place
pub fn normalize_signal(signal: &mut Signal) -> Option<NormalizationResult> {
    let value = signal.value?;

    let result = normalize_value(&signal.biomarker_slug, value, &signal.source_slug);

    if result.was_converted {
        debug!(
            "Normalized {} from {} to {}: {}",
            signal.biomarker_slug,
            value,
            result.value,
            result.conversion_note.as_deref().unwrap_or(""),
        );
        signal.value = Some(result.value);
    }

    Some(result)
}

/// Batch normalize signals
pub fn normalize_batch(signals: &mut [Signal]) -> Vec<NormalizationResult> {
    signals.iter_mut().filter_map(normalize_signal).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    fn make_signal(slug: &str, value: f64, source: &str) -> Signal {
        Signal::new(Utc::now(), slug, value, source)
    }

    #[test]
    fn test_hrv_seconds_to_ms() {
        let result = normalize_value("hrv_sdnn", 0.045, "apple_health");
        assert!(result.was_converted);
        assert!((result.value - 45.0).abs() < 0.001);
    }

    #[test]
    fn test_hrv_microseconds_to_ms() {
        let result = normalize_value("hrv_sdnn", 45000.0, "apple_health");
        assert!(result.was_converted);
        assert!((result.value - 45.0).abs() < 0.001);
    }

    #[test]
    fn test_hrv_already_ms() {
        let result = normalize_value("hrv_sdnn", 45.0, "apple_health");
        assert!(!result.was_converted);
        assert!((result.value - 45.0).abs() < 0.001);
    }

    #[test]
    fn test_spo2_ratio_to_percent() {
        let result = normalize_value("spo2", 0.97, "oura");
        assert!(result.was_converted);
        assert!((result.value - 97.0).abs() < 0.001);
    }

    #[test]
    fn test_spo2_already_percent() {
        let result = normalize_value("spo2", 97.0, "apple_health");
        assert!(!result.was_converted);
    }

    #[test]
    fn test_height_cm_to_m() {
        let result = normalize_value("height", 175.0, "apple_health");
        assert!(result.was_converted);
        assert!((result.value - 1.75).abs() < 0.001);
    }

    #[test]
    fn test_height_already_m() {
        let result = normalize_value("height", 1.75, "manual");
        assert!(!result.was_converted);
    }

    #[test]
    fn test_temp_fahrenheit_to_celsius() {
        let result = normalize_value("core_temp", 98.6, "manual");
        assert!(result.was_converted);
        assert!((result.value - 37.0).abs() < 0.1);
    }

    #[test]
    fn test_temp_already_celsius() {
        let result = normalize_value("core_temp", 37.0, "wearable");
        assert!(!result.was_converted);
    }

    #[test]
    fn test_glucose_mmol_to_mgdl() {
        let result = normalize_value("glucose", 5.5, "cgm");
        assert!(result.was_converted);
        assert!((result.value - 99.1).abs() < 0.5); // ~99 mg/dL
    }

    #[test]
    fn test_glucose_already_mgdl() {
        let result = normalize_value("glucose", 100.0, "cgm");
        assert!(!result.was_converted);
    }

    #[test]
    fn test_sleep_hours_to_minutes() {
        let result = normalize_value("sleep_duration", 7.5, "oura");
        assert!(result.was_converted);
        assert!((result.value - 450.0).abs() < 0.001);
    }

    #[test]
    fn test_sleep_seconds_to_minutes() {
        let result = normalize_value("sleep_duration", 27000.0, "garmin");
        assert!(result.was_converted);
        assert!((result.value - 450.0).abs() < 0.001);
    }

    #[test]
    fn test_sleep_already_minutes() {
        let result = normalize_value("sleep_duration", 450.0, "apple_health");
        assert!(!result.was_converted);
    }

    #[test]
    fn test_body_fat_ratio_to_percent() {
        let result = normalize_value("body_fat_percentage", 0.18, "smart_scale");
        assert!(result.was_converted);
        assert!((result.value - 18.0).abs() < 0.001);
    }

    #[test]
    fn test_unknown_biomarker_unchanged() {
        let result = normalize_value("custom_metric", 42.0, "api");
        assert!(!result.was_converted);
        assert!((result.value - 42.0).abs() < 0.001);
    }

    #[test]
    fn test_normalize_signal_in_place() {
        let mut signal = make_signal("spo2", 0.98, "oura");
        let result = normalize_signal(&mut signal);
        assert!(result.is_some());
        assert!(result.unwrap().was_converted);
        assert!((signal.value.unwrap() - 98.0).abs() < 0.001);
    }

    // ─────────────────────────────────────────────────────────────────
    // Clinical Biomarker Normalization Tests
    // ─────────────────────────────────────────────────────────────────

    #[test]
    fn test_bp_systolic_kpa_to_mmhg() {
        // 16 kPa = ~120 mmHg
        let result = normalize_value("bp_systolic", 16.0, "withings");
        assert!(result.was_converted);
        assert!((result.value - 120.01).abs() < 0.1);
    }

    #[test]
    fn test_bp_systolic_already_mmhg() {
        let result = normalize_value("bp_systolic", 120.0, "withings");
        assert!(!result.was_converted);
    }

    #[test]
    fn test_bp_diastolic_kpa_to_mmhg() {
        // 10.67 kPa = ~80 mmHg
        let result = normalize_value("bp_diastolic", 10.67, "withings");
        assert!(result.was_converted);
        assert!((result.value - 80.0).abs() < 0.5);
    }

    #[test]
    fn test_bp_diastolic_already_mmhg() {
        let result = normalize_value("bp_diastolic", 80.0, "withings");
        assert!(!result.was_converted);
    }

    #[test]
    fn test_basal_body_temp_fahrenheit_to_celsius() {
        // 98.2°F = ~36.8°C (luteal phase temp)
        let result = normalize_value("basal_body_temp", 98.2, "manual");
        assert!(result.was_converted);
        assert!((result.value - 36.78).abs() < 0.1);
    }

    #[test]
    fn test_basal_body_temp_already_celsius() {
        let result = normalize_value("basal_body_temp", 36.5, "oura");
        assert!(!result.was_converted);
    }

    #[test]
    fn test_distance_km_to_m() {
        // 10 km = 10000 m
        let result = normalize_value("distance_walking_running", 10.0, "strava");
        assert!(result.was_converted);
        assert!((result.value - 10000.0).abs() < 0.001);
    }

    #[test]
    fn test_distance_already_m() {
        let result = normalize_value("distance_walking_running", 10000.0, "apple_health");
        assert!(!result.was_converted);
    }

    #[test]
    fn test_exercise_intensity_hours_to_min() {
        // 1.5 hours = 90 minutes
        let result = normalize_value("exercise_intensity_min", 1.5, "garmin");
        assert!(result.was_converted);
        assert!((result.value - 90.0).abs() < 0.001);
    }

    #[test]
    fn test_exercise_intensity_seconds_to_min() {
        // 2700 seconds = 45 minutes
        let result = normalize_value("exercise_intensity_min", 2700.0, "fitbit");
        assert!(result.was_converted);
        assert!((result.value - 45.0).abs() < 0.001);
    }

    #[test]
    fn test_exercise_intensity_already_min() {
        let result = normalize_value("exercise_intensity_min", 45.0, "apple_health");
        assert!(!result.was_converted);
    }

    #[test]
    fn test_sleep_onset_time_no_conversion() {
        // Sleep times stored as minutes since midnight - no conversion
        let result = normalize_value("sleep_onset_time", 1380.0, "apple_health"); // 23:00
        assert!(!result.was_converted);
        assert!((result.value - 1380.0).abs() < 0.001);
    }

    #[test]
    fn test_ahi_no_conversion() {
        // AHI in events/hour - no conversion needed
        let result = normalize_value("ahi", 15.0, "withings");
        assert!(!result.was_converted);
    }

    #[test]
    fn test_menstrual_cycle_day_no_conversion() {
        let result = normalize_value("menstrual_cycle_day", 14.0, "clue");
        assert!(!result.was_converted);
    }
}
