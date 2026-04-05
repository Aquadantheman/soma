use anyhow::{Context, Result};
use chrono::{DateTime, Timelike, Utc};
use quick_xml::events::Event;
use quick_xml::reader::Reader;
use std::collections::HashMap;
use std::path::Path;
use tracing::{debug, warn};

use crate::models::signal::{IngestBatch, Signal};

/// Maps Apple Health HKQuantityTypeIdentifier values to Soma biomarker slugs
fn apple_type_map() -> HashMap<&'static str, (&'static str, f64)> {
    // (soma_slug, unit_conversion_factor)
    let mut m = HashMap::new();

    // ===== CARDIOVASCULAR =====
    m.insert("HKQuantityTypeIdentifierHeartRate", ("heart_rate", 1.0));
    m.insert(
        "HKQuantityTypeIdentifierRestingHeartRate",
        ("heart_rate_resting", 1.0),
    );
    m.insert(
        "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
        ("hrv_sdnn", 0.001),
    ); // Apple exports µs, convert to ms
    m.insert(
        "HKQuantityTypeIdentifierWalkingHeartRateAverage",
        ("walking_hr_avg", 1.0),
    );
    m.insert(
        "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute",
        ("hr_recovery_1min", 1.0),
    );
    m.insert(
        "HKQuantityTypeIdentifierBloodPressureSystolic",
        ("bp_systolic", 1.0),
    );
    m.insert(
        "HKQuantityTypeIdentifierBloodPressureDiastolic",
        ("bp_diastolic", 1.0),
    );

    // ===== RESPIRATORY =====
    m.insert("HKQuantityTypeIdentifierOxygenSaturation", ("spo2", 100.0)); // ratio -> %
    m.insert(
        "HKQuantityTypeIdentifierRespiratoryRate",
        ("respiratory_rate", 1.0),
    );
    m.insert("HKQuantityTypeIdentifierVO2Max", ("vo2_max", 1.0));

    // ===== ACTIVITY =====
    m.insert("HKQuantityTypeIdentifierStepCount", ("steps", 1.0));
    m.insert(
        "HKQuantityTypeIdentifierDistanceWalkingRunning",
        ("distance_walking_running", 1000.0),
    ); // km -> m
    m.insert(
        "HKQuantityTypeIdentifierDistanceCycling",
        ("distance_cycling", 1000.0),
    ); // km -> m
    m.insert(
        "HKQuantityTypeIdentifierDistanceSwimming",
        ("distance_swimming", 1.0),
    ); // m
    m.insert(
        "HKQuantityTypeIdentifierActiveEnergyBurned",
        ("active_energy", 1.0),
    );
    m.insert(
        "HKQuantityTypeIdentifierBasalEnergyBurned",
        ("basal_energy", 1.0),
    );
    m.insert(
        "HKQuantityTypeIdentifierAppleExerciseTime",
        ("exercise_time", 1.0),
    ); // min
    m.insert(
        "HKQuantityTypeIdentifierAppleStandTime",
        ("stand_time", 1.0),
    ); // min
    m.insert(
        "HKQuantityTypeIdentifierFlightsClimbed",
        ("flights_climbed", 1.0),
    );
    m.insert(
        "HKQuantityTypeIdentifierPhysicalEffort",
        ("physical_effort", 1.0),
    );
    m.insert(
        "HKQuantityTypeIdentifierSwimmingStrokeCount",
        ("swimming_strokes", 1.0),
    );

    // ===== MOBILITY & GAIT =====
    m.insert(
        "HKQuantityTypeIdentifierWalkingSpeed",
        ("walking_speed", 1.0),
    ); // m/s
    m.insert(
        "HKQuantityTypeIdentifierWalkingStepLength",
        ("walking_step_length", 0.01),
    ); // cm -> m
    m.insert(
        "HKQuantityTypeIdentifierWalkingAsymmetryPercentage",
        ("walking_asymmetry", 100.0),
    ); // ratio -> %
    m.insert(
        "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage",
        ("walking_double_support", 100.0),
    );
    m.insert(
        "HKQuantityTypeIdentifierAppleWalkingSteadiness",
        ("walking_steadiness", 100.0),
    ); // ratio -> %
    m.insert(
        "HKQuantityTypeIdentifierStairAscentSpeed",
        ("stair_ascent_speed", 1.0),
    ); // m/s
    m.insert(
        "HKQuantityTypeIdentifierStairDescentSpeed",
        ("stair_descent_speed", 1.0),
    ); // m/s

    // ===== RUNNING BIOMECHANICS =====
    m.insert(
        "HKQuantityTypeIdentifierRunningSpeed",
        ("running_speed", 1.0),
    ); // m/s
    m.insert(
        "HKQuantityTypeIdentifierRunningPower",
        ("running_power", 1.0),
    ); // W
    m.insert(
        "HKQuantityTypeIdentifierRunningStrideLength",
        ("stride_length", 1.0),
    ); // m
    m.insert(
        "HKQuantityTypeIdentifierRunningVerticalOscillation",
        ("vertical_oscillation", 100.0),
    ); // m -> cm
    m.insert(
        "HKQuantityTypeIdentifierRunningGroundContactTime",
        ("ground_contact_time", 1000.0),
    ); // s -> ms

    // ===== BODY COMPOSITION =====
    m.insert("HKQuantityTypeIdentifierBodyMass", ("body_mass", 0.453592)); // lb -> kg
    m.insert(
        "HKQuantityTypeIdentifierBodyFatPercentage",
        ("body_fat_percentage", 100.0),
    ); // ratio -> %
    m.insert(
        "HKQuantityTypeIdentifierLeanBodyMass",
        ("lean_body_mass", 0.453592),
    ); // lb -> kg
    m.insert(
        "HKQuantityTypeIdentifierBodyMassIndex",
        ("body_mass_index", 1.0),
    );
    m.insert("HKQuantityTypeIdentifierHeight", ("height", 0.01)); // cm -> m
    m.insert(
        "HKQuantityTypeIdentifierWaistCircumference",
        ("waist_circumference", 0.01),
    ); // cm -> m

    // ===== ENVIRONMENT =====
    m.insert(
        "HKQuantityTypeIdentifierTimeInDaylight",
        ("daylight_exposure", 1.0),
    ); // min
    m.insert(
        "HKQuantityTypeIdentifierHeadphoneAudioExposure",
        ("headphone_exposure", 1.0),
    ); // dB
    m.insert(
        "HKQuantityTypeIdentifierEnvironmentalAudioExposure",
        ("noise_exposure_avg", 1.0),
    ); // dB

    // ===== ENDOCRINE =====
    m.insert(
        "HKQuantityTypeIdentifierBodyTemperature",
        ("core_temp", 1.0),
    );
    m.insert(
        "HKQuantityTypeIdentifierBasalBodyTemperature",
        ("basal_body_temp", 1.0),
    ); // °C
    m.insert("HKQuantityTypeIdentifierBloodGlucose", ("glucose", 1.0));
    m.insert(
        "HKQuantityTypeIdentifierAppleSleepingWristTemperature",
        ("skin_temp_delta", 1.0),
    ); // °C deviation

    // ===== NUTRITION =====
    m.insert(
        "HKQuantityTypeIdentifierDietaryEnergyConsumed",
        ("calories_consumed", 1.0),
    ); // kcal
    m.insert(
        "HKQuantityTypeIdentifierDietaryProtein",
        ("protein_intake", 1.0),
    ); // g
    m.insert(
        "HKQuantityTypeIdentifierDietaryCarbohydrates",
        ("carb_intake", 1.0),
    ); // g
    m.insert(
        "HKQuantityTypeIdentifierDietaryFatTotal",
        ("fat_intake", 1.0),
    ); // g
    m.insert(
        "HKQuantityTypeIdentifierDietaryWater",
        ("water_intake", 1.0),
    ); // mL

    m
}

/// Maps Apple Health sleep analysis values
fn sleep_stage_map() -> HashMap<&'static str, &'static str> {
    let mut m = HashMap::new();
    m.insert("HKCategoryValueSleepAnalysisAsleepREM", "sleep_rem");
    m.insert("HKCategoryValueSleepAnalysisAsleepDeep", "sleep_deep");
    m.insert("HKCategoryValueSleepAnalysisAsleepCore", "sleep_core");
    m.insert("HKCategoryValueSleepAnalysisInBed", "sleep_in_bed");
    m
}

/// Maps Apple Health menstrual flow values to numeric intensity
/// HKCategoryValueMenstrualFlowUnspecified = 1
/// HKCategoryValueMenstrualFlowLight = 2
/// HKCategoryValueMenstrualFlowMedium = 3
/// HKCategoryValueMenstrualFlowHeavy = 4
fn menstrual_flow_value(value: &str) -> Option<f64> {
    match value {
        "HKCategoryValueMenstrualFlowUnspecified" => Some(1.0),
        "HKCategoryValueMenstrualFlowNone" => Some(0.0),
        "HKCategoryValueMenstrualFlowLight" => Some(2.0),
        "HKCategoryValueMenstrualFlowMedium" => Some(3.0),
        "HKCategoryValueMenstrualFlowHeavy" => Some(4.0),
        _ => None,
    }
}

pub struct AppleHealthIngester;

impl AppleHealthIngester {
    pub fn new() -> Self {
        Self
    }

    /// Ingest an Apple Health export.xml
    pub async fn ingest_file(&self, path: &Path) -> Result<IngestBatch> {
        let mut batch = IngestBatch::new("apple_health");
        let type_map = apple_type_map();
        let sleep_map = sleep_stage_map();

        let content = tokio::fs::read_to_string(path)
            .await
            .context("Failed to read Apple Health export file")?;

        let mut reader = Reader::from_str(&content);
        reader.trim_text(true);

        loop {
            match reader.read_event() {
                Ok(Event::Empty(e)) | Ok(Event::Start(e)) => {
                    match e.name().as_ref() {
                        b"Record" => {
                            // Try sleep analysis first (stored as Record with category value)
                            if let Some(signal) = self.parse_sleep_record(&e, &sleep_map) {
                                batch.push(signal);

                                // For sleep_in_bed records, also extract timing signals
                                // These are needed for circadian metrics (SRI, social jet lag)
                                let attrs = self.attrs_to_map(&e);
                                if attrs
                                    .get("value")
                                    .map_or(false, |v| v == "HKCategoryValueSleepAnalysisInBed")
                                {
                                    for timing_signal in self.extract_sleep_timing_signals(&attrs) {
                                        batch.push(timing_signal);
                                    }
                                }
                            } else if let Some(signal) = self.parse_record(&e, &type_map) {
                                batch.push(signal);
                            } else {
                                batch.skip();
                            }
                        }
                        b"CategorySample" => {
                            if let Some(signal) = self.parse_category_sample(&e, &sleep_map) {
                                batch.push(signal);
                            } else {
                                batch.skip();
                            }
                        }
                        _ => {}
                    }
                }
                Ok(Event::Eof) => break,
                Err(e) => {
                    warn!("XML parse error: {}", e);
                    batch.error();
                }
                _ => {}
            }
        }

        Ok(batch)
    }

    fn parse_record(
        &self,
        e: &quick_xml::events::BytesStart,
        type_map: &HashMap<&str, (&str, f64)>,
    ) -> Option<Signal> {
        let attrs = self.attrs_to_map(e);

        let record_type = attrs.get("type")?;
        let (soma_slug, conversion) = type_map.get(record_type.as_str())?;

        let value_str = attrs.get("value")?;
        let value: f64 = value_str.parse().ok()?;
        let converted_value = value * conversion;

        let start_date = attrs.get("startDate")?;
        let time = self.parse_apple_date(start_date)?;

        let end_date = attrs.get("endDate");
        let window_seconds = end_date.and_then(|e| {
            let end = self.parse_apple_date(e)?;
            Some((end - time).num_seconds() as i32)
        });

        let raw_id = attrs
            .get("uuid")
            .cloned()
            .unwrap_or_else(|| format!("{}_{}", start_date, soma_slug));

        let raw_bytes = format!("{}{}{}", record_type, start_date, value_str);

        let mut signal = Signal::new(time, *soma_slug, converted_value, "apple_health")
            .with_source_id(raw_id)
            .with_hash(raw_bytes.as_bytes());

        if let Some(ws) = window_seconds {
            signal = signal.with_window(ws);
        }

        debug!(
            "Parsed Apple Health record: {} = {}",
            soma_slug, converted_value
        );
        Some(signal)
    }

    /// Parse sleep analysis from Record elements (Apple Health stores sleep as Record, not CategorySample)
    fn parse_sleep_record(
        &self,
        e: &quick_xml::events::BytesStart,
        sleep_map: &HashMap<&str, &str>,
    ) -> Option<Signal> {
        let attrs = self.attrs_to_map(e);

        let record_type = attrs.get("type")?;
        if record_type != "HKCategoryTypeIdentifierSleepAnalysis" {
            return None;
        }

        self.parse_sleep_analysis(&attrs, sleep_map)
    }

    fn parse_category_sample(
        &self,
        e: &quick_xml::events::BytesStart,
        sleep_map: &HashMap<&str, &str>,
    ) -> Option<Signal> {
        let attrs = self.attrs_to_map(e);

        let record_type = attrs.get("type")?;

        // Handle sleep analysis
        if record_type == "HKCategoryTypeIdentifierSleepAnalysis" {
            return self.parse_sleep_analysis(&attrs, sleep_map);
        }

        // Handle menstrual flow
        if record_type == "HKCategoryTypeIdentifierMenstrualFlow" {
            return self.parse_menstrual_flow(&attrs);
        }

        None
    }

    /// Parse menstrual flow category sample
    fn parse_menstrual_flow(&self, attrs: &HashMap<String, String>) -> Option<Signal> {
        let value = attrs.get("value")?;
        let flow_intensity = menstrual_flow_value(value)?;

        let start_date = attrs.get("startDate")?;
        let start = self.parse_apple_date(start_date)?;

        let raw_bytes = format!("menstrual_flow_{}", start_date);

        Some(
            Signal::new(start, "menstrual_flow", flow_intensity, "apple_health")
                .with_hash(raw_bytes.as_bytes()),
        )
    }

    /// Common sleep analysis parsing logic
    ///
    /// Returns multiple signals:
    /// 1. Sleep stage duration (sleep_rem, sleep_deep, etc.)
    /// 2. For sleep_in_bed records: also extracts sleep_onset_time and sleep_offset_time
    ///    as minutes-since-midnight for circadian metric computation
    fn parse_sleep_analysis(
        &self,
        attrs: &HashMap<String, String>,
        sleep_map: &HashMap<&str, &str>,
    ) -> Option<Signal> {
        let record_type = attrs.get("type")?;
        let value = attrs.get("value")?;
        let soma_slug = sleep_map.get(value.as_str())?;

        let start_date = attrs.get("startDate")?;
        let end_date = attrs.get("endDate")?;

        let start = self.parse_apple_date(start_date)?;
        let end = self.parse_apple_date(end_date)?;
        let duration_min = (end - start).num_minutes() as f64;

        let raw_bytes = format!("{}{}{}", record_type, start_date, value);

        // Output individual sleep stage with duration in minutes
        // This allows computing sleep architecture metrics (REM%, Deep%, etc.)
        Some(
            Signal::new(start, *soma_slug, duration_min, "apple_health")
                .with_window((end - start).num_seconds() as i32)
                .with_hash(raw_bytes.as_bytes()),
        )
    }

    /// Extract sleep timing signals (onset, offset) from a sleep_in_bed record
    /// These are essential for computing sleep_midpoint, SRI, and social_jetlag
    fn extract_sleep_timing_signals(&self, attrs: &HashMap<String, String>) -> Vec<Signal> {
        let mut signals = Vec::new();

        let start_date = match attrs.get("startDate") {
            Some(s) => s,
            None => return signals,
        };
        let end_date = match attrs.get("endDate") {
            Some(s) => s,
            None => return signals,
        };

        let start = match self.parse_apple_date(start_date) {
            Some(dt) => dt,
            None => return signals,
        };
        let end = match self.parse_apple_date(end_date) {
            Some(dt) => dt,
            None => return signals,
        };

        // Convert to minutes since midnight (0-1439)
        let onset_min = (start.hour() * 60 + start.minute()) as f64;
        let offset_min = (end.hour() * 60 + end.minute()) as f64;

        // Create sleep_onset_time signal
        let onset_raw = format!("sleep_onset_{}", start_date);
        signals.push(
            Signal::new(start, "sleep_onset_time", onset_min, "apple_health")
                .with_hash(onset_raw.as_bytes()),
        );

        // Create sleep_offset_time signal
        let offset_raw = format!("sleep_offset_{}", end_date);
        signals.push(
            Signal::new(start, "sleep_offset_time", offset_min, "apple_health")
                .with_hash(offset_raw.as_bytes()),
        );

        // Also compute and store sleep_midpoint directly
        let midpoint = crate::pipeline::compute::compute_sleep_midpoint(onset_min, offset_min);
        let midpoint_raw = format!("sleep_midpoint_{}_{}", start_date, end_date);
        signals.push(
            Signal::new(start, "sleep_midpoint", midpoint, "apple_health")
                .with_hash(midpoint_raw.as_bytes()),
        );

        debug!(
            "Extracted sleep timing: onset={:.0} offset={:.0} midpoint={:.0}",
            onset_min, offset_min, midpoint
        );

        signals
    }

    fn attrs_to_map(&self, e: &quick_xml::events::BytesStart) -> HashMap<String, String> {
        let mut map = HashMap::new();
        for attr in e.attributes().flatten() {
            if let (Ok(key), Ok(val)) = (
                std::str::from_utf8(attr.key.as_ref()),
                attr.unescape_value(),
            ) {
                map.insert(key.to_string(), val.to_string());
            }
        }
        map
    }

    fn parse_apple_date(&self, s: &str) -> Option<DateTime<Utc>> {
        // Apple Health format: "2024-01-15 07:23:45 -0500"
        DateTime::parse_from_str(s, "%Y-%m-%d %H:%M:%S %z")
            .ok()
            .map(|dt| dt.with_timezone(&Utc))
    }
}
