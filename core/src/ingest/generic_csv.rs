//! Generic CSV ingester
//!
//! Flexible CSV importer supporting multiple formats:
//! - Standard format: time, biomarker_slug, value
//! - Extended format: includes source_slug, quality, window_seconds
//! - Auto-detection of column names and date formats
//!
//! ## Supported Date Formats
//!
//! - ISO 8601: `2024-01-15T10:30:00Z`
//! - Date + Time: `2024-01-15 10:30:00`
//! - Unix timestamp (seconds): `1705316400`
//! - Unix timestamp (milliseconds): `1705316400000`

use anyhow::{Context, Result};
use chrono::{DateTime, NaiveDateTime, TimeZone, Utc};
use csv::StringRecord;
use std::collections::HashMap;
use std::path::Path;
use tracing::{debug, info, warn};

use crate::models::signal::{IngestBatch, Signal};
use crate::pipeline::{normalize_signal, validate_signal};

/// CSV column mapping
#[derive(Debug, Clone)]
pub struct ColumnMapping {
    pub time: usize,
    pub biomarker_slug: usize,
    pub value: usize,
    pub source_slug: Option<usize>,
    pub quality: Option<usize>,
    pub window_seconds: Option<usize>,
    pub value_text: Option<usize>,
}

impl ColumnMapping {
    /// Auto-detect column mapping from headers
    pub fn from_headers(headers: &StringRecord) -> Result<Self> {
        let mut col_map: HashMap<&str, usize> = HashMap::new();

        for (i, header) in headers.iter().enumerate() {
            let normalized = header.to_lowercase().trim().to_string();
            col_map.insert(
                match normalized.as_str() {
                    "time" | "timestamp" | "datetime" | "date" | "recorded_at" => "time",
                    "biomarker" | "biomarker_slug" | "metric" | "type" | "signal_type" => {
                        "biomarker_slug"
                    }
                    "value" | "measurement" | "reading" | "amount" => "value",
                    "source" | "source_slug" | "data_source" | "provider" => "source_slug",
                    "quality" | "quality_score" | "confidence" => "quality",
                    "window" | "window_seconds" | "duration" | "period" => "window_seconds",
                    "text" | "value_text" | "note" | "notes" => "value_text",
                    _ => continue,
                },
                i,
            );
        }

        let time = *col_map
            .get("time")
            .context("CSV must have a 'time' or 'timestamp' column")?;
        let biomarker_slug = *col_map
            .get("biomarker_slug")
            .context("CSV must have a 'biomarker_slug' or 'metric' column")?;
        let value = *col_map
            .get("value")
            .context("CSV must have a 'value' column")?;

        Ok(Self {
            time,
            biomarker_slug,
            value,
            source_slug: col_map.get("source_slug").copied(),
            quality: col_map.get("quality").copied(),
            window_seconds: col_map.get("window_seconds").copied(),
            value_text: col_map.get("value_text").copied(),
        })
    }
}

/// Parse various datetime formats
fn parse_datetime(s: &str) -> Option<DateTime<Utc>> {
    let trimmed = s.trim();

    // Try ISO 8601 with timezone
    if let Ok(dt) = DateTime::parse_from_rfc3339(trimmed) {
        return Some(dt.with_timezone(&Utc));
    }

    // Try ISO 8601 without timezone (assume UTC)
    if let Ok(dt) = NaiveDateTime::parse_from_str(trimmed, "%Y-%m-%dT%H:%M:%S") {
        return Some(Utc.from_utc_datetime(&dt));
    }

    // Try common date + time format
    if let Ok(dt) = NaiveDateTime::parse_from_str(trimmed, "%Y-%m-%d %H:%M:%S") {
        return Some(Utc.from_utc_datetime(&dt));
    }

    // Try date only (midnight UTC)
    if let Ok(dt) =
        NaiveDateTime::parse_from_str(&format!("{} 00:00:00", trimmed), "%Y-%m-%d %H:%M:%S")
    {
        return Some(Utc.from_utc_datetime(&dt));
    }

    // Try Unix timestamp (seconds)
    if let Ok(ts) = trimmed.parse::<i64>() {
        // If it's a reasonable timestamp in seconds (after 2000, before 2100)
        if ts > 946684800 && ts < 4102444800 {
            return DateTime::from_timestamp(ts, 0);
        }
        // Maybe it's milliseconds
        if ts > 946684800000 && ts < 4102444800000 {
            return DateTime::from_timestamp(ts / 1000, ((ts % 1000) * 1_000_000) as u32);
        }
    }

    // Try US date format
    if let Ok(dt) = NaiveDateTime::parse_from_str(trimmed, "%m/%d/%Y %H:%M:%S") {
        return Some(Utc.from_utc_datetime(&dt));
    }

    None
}

/// Generic CSV ingester
pub struct CsvIngester {
    /// Default source slug if not in CSV
    default_source: String,
    /// Whether to validate signals
    validate: bool,
    /// Whether to normalize signals
    normalize: bool,
}

impl CsvIngester {
    pub fn new() -> Self {
        Self {
            default_source: "generic_csv".to_string(),
            validate: true,
            normalize: true,
        }
    }

    /// Set default source slug
    pub fn with_source(mut self, source: impl Into<String>) -> Self {
        self.default_source = source.into();
        self
    }

    /// Disable validation
    pub fn without_validation(mut self) -> Self {
        self.validate = false;
        self
    }

    /// Disable normalization
    pub fn without_normalization(mut self) -> Self {
        self.normalize = false;
        self
    }

    /// Ingest a CSV file
    pub async fn ingest_file(&self, path: &Path) -> Result<IngestBatch> {
        info!("Ingesting CSV file: {:?}", path);

        let mut batch = IngestBatch::new(&self.default_source);
        let mut reader = csv::ReaderBuilder::new()
            .flexible(true)
            .trim(csv::Trim::All)
            .from_path(path)
            .context("Failed to open CSV file")?;

        // Get headers and detect column mapping
        let headers = reader.headers().context("CSV must have headers")?.clone();

        let mapping =
            ColumnMapping::from_headers(&headers).context("Failed to detect column mapping")?;

        debug!("Detected column mapping: {:?}", mapping);

        // Process records
        for (line_num, result) in reader.records().enumerate() {
            match result {
                Ok(record) => {
                    match self.parse_record(&record, &mapping, line_num + 2) {
                        Ok(Some(mut signal)) => {
                            // Apply normalization
                            if self.normalize {
                                normalize_signal(&mut signal);
                            }

                            // Apply validation
                            if self.validate {
                                let validation = validate_signal(&signal);
                                if !validation.is_valid {
                                    warn!(
                                        "Invalid signal at line {}: {:?}",
                                        line_num + 2,
                                        validation.errors
                                    );
                                    batch.error();
                                    continue;
                                }
                                signal.quality = std::cmp::min(signal.quality, validation.quality);
                            }

                            batch.push(signal);
                        }
                        Ok(None) => {
                            batch.skip();
                        }
                        Err(e) => {
                            warn!("Error parsing line {}: {}", line_num + 2, e);
                            batch.error();
                        }
                    }
                }
                Err(e) => {
                    warn!("Error reading line {}: {}", line_num + 2, e);
                    batch.error();
                }
            }
        }

        info!(
            "CSV ingestion complete: {} parsed, {} errors",
            batch.parsed, batch.errors
        );

        Ok(batch)
    }

    /// Parse a single CSV record into a Signal
    fn parse_record(
        &self,
        record: &StringRecord,
        mapping: &ColumnMapping,
        line_num: usize,
    ) -> Result<Option<Signal>> {
        // Parse required fields
        let time_str = record.get(mapping.time).context("Missing time column")?;
        let time = parse_datetime(time_str)
            .with_context(|| format!("Invalid datetime at line {}: '{}'", line_num, time_str))?;

        let biomarker_slug = record
            .get(mapping.biomarker_slug)
            .context("Missing biomarker_slug column")?
            .trim()
            .to_string();

        if biomarker_slug.is_empty() {
            return Ok(None); // Skip empty biomarker
        }

        let value_str = record
            .get(mapping.value)
            .context("Missing value column")?
            .trim();

        // Handle empty values
        if value_str.is_empty() {
            // Check for text value
            if let Some(text_col) = mapping.value_text {
                if let Some(text) = record.get(text_col) {
                    let text = text.trim();
                    if !text.is_empty() {
                        let source = mapping
                            .source_slug
                            .and_then(|c| record.get(c))
                            .map(|s| s.trim().to_string())
                            .filter(|s| !s.is_empty())
                            .unwrap_or_else(|| self.default_source.clone());

                        return Ok(Some(Signal::with_text(time, biomarker_slug, text, source)));
                    }
                }
            }
            return Ok(None); // Skip empty value with no text
        }

        // Parse numeric value
        let value: f64 = value_str
            .parse()
            .with_context(|| format!("Invalid value at line {}: '{}'", line_num, value_str))?;

        // Get optional fields
        let source = mapping
            .source_slug
            .and_then(|c| record.get(c))
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .unwrap_or_else(|| self.default_source.clone());

        let mut signal = Signal::new(time, biomarker_slug, value, source);

        // Optional quality
        if let Some(col) = mapping.quality {
            if let Some(q_str) = record.get(col) {
                if let Ok(q) = q_str.trim().parse::<u8>() {
                    signal = signal.with_quality(q);
                }
            }
        }

        // Optional window
        if let Some(col) = mapping.window_seconds {
            if let Some(w_str) = record.get(col) {
                if let Ok(w) = w_str.trim().parse::<i32>() {
                    signal = signal.with_window(w);
                }
            }
        }

        // Compute hash from raw record
        let raw = record.iter().collect::<Vec<_>>().join(",");
        signal = signal.with_hash(raw.as_bytes());

        Ok(Some(signal))
    }
}

impl Default for CsvIngester {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Datelike, Timelike};

    #[test]
    fn test_parse_datetime_iso8601() {
        let dt = parse_datetime("2024-01-15T10:30:00Z").unwrap();
        assert_eq!(dt.year(), 2024);
        assert_eq!(dt.month(), 1);
        assert_eq!(dt.day(), 15);
    }

    #[test]
    fn test_parse_datetime_space_separated() {
        let dt = parse_datetime("2024-01-15 10:30:00").unwrap();
        assert_eq!(dt.year(), 2024);
    }

    #[test]
    fn test_parse_datetime_date_only() {
        let dt = parse_datetime("2024-01-15").unwrap();
        assert_eq!(dt.year(), 2024);
        assert_eq!(dt.hour(), 0);
    }

    #[test]
    fn test_parse_datetime_unix_seconds() {
        let dt = parse_datetime("1705316400").unwrap();
        assert!(dt.year() >= 2024);
    }

    #[test]
    fn test_parse_datetime_unix_millis() {
        let dt = parse_datetime("1705316400000").unwrap();
        assert!(dt.year() >= 2024);
    }

    #[test]
    fn test_column_mapping_standard() {
        let mut record = StringRecord::new();
        record.push_field("time");
        record.push_field("biomarker_slug");
        record.push_field("value");

        let mapping = ColumnMapping::from_headers(&record).unwrap();
        assert_eq!(mapping.time, 0);
        assert_eq!(mapping.biomarker_slug, 1);
        assert_eq!(mapping.value, 2);
    }

    #[test]
    fn test_column_mapping_alternate_names() {
        let mut record = StringRecord::new();
        record.push_field("timestamp");
        record.push_field("metric");
        record.push_field("measurement");
        record.push_field("source");

        let mapping = ColumnMapping::from_headers(&record).unwrap();
        assert_eq!(mapping.time, 0);
        assert_eq!(mapping.biomarker_slug, 1);
        assert_eq!(mapping.value, 2);
        assert_eq!(mapping.source_slug, Some(3));
    }
}
