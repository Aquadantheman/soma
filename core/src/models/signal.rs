use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

/// A single measured data point — the atomic unit of everything in Soma
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Signal {
    pub time: DateTime<Utc>,
    pub biomarker_slug: String,
    pub value: Option<f64>,
    pub value_text: Option<String>,
    pub source_slug: String,
    pub window_seconds: Option<i32>,
    pub quality: u8,
    pub blake3_hash: Option<String>,
    pub raw_source_id: Option<String>,
}

impl Signal {
    pub fn new(
        time: DateTime<Utc>,
        biomarker_slug: impl Into<String>,
        value: f64,
        source_slug: impl Into<String>,
    ) -> Self {
        Self {
            time,
            biomarker_slug: biomarker_slug.into(),
            value: Some(value),
            value_text: None,
            source_slug: source_slug.into(),
            window_seconds: None,
            quality: 100,
            blake3_hash: None,
            raw_source_id: None,
        }
    }

    pub fn with_text(
        time: DateTime<Utc>,
        biomarker_slug: impl Into<String>,
        text: impl Into<String>,
        source_slug: impl Into<String>,
    ) -> Self {
        Self {
            time,
            biomarker_slug: biomarker_slug.into(),
            value: None,
            value_text: Some(text.into()),
            source_slug: source_slug.into(),
            window_seconds: None,
            quality: 100,
            blake3_hash: None,
            raw_source_id: None,
        }
    }

    pub fn with_window(mut self, seconds: i32) -> Self {
        self.window_seconds = Some(seconds);
        self
    }

    pub fn with_quality(mut self, quality: u8) -> Self {
        self.quality = quality.min(100);
        self
    }

    pub fn with_source_id(mut self, id: impl Into<String>) -> Self {
        self.raw_source_id = Some(id.into());
        self
    }

    /// Compute and attach BLAKE3 hash of the raw source record
    pub fn with_hash(mut self, raw_bytes: &[u8]) -> Self {
        let hash = blake3::hash(raw_bytes);
        self.blake3_hash = Some(hash.to_hex().to_string());
        self
    }
}

/// Categories of biomarkers
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum BiomarkerCategory {
    Autonomic,
    Endocrine,
    Sleep,
    Activity,
    Subjective,
}

/// An ingestion result batch
#[derive(Debug, Default)]
pub struct IngestBatch {
    pub signals: Vec<Signal>,
    pub parsed: usize,
    pub skipped: usize,
    pub errors: usize,
    pub source_slug: String,
}

impl IngestBatch {
    pub fn new(source_slug: impl Into<String>) -> Self {
        Self {
            source_slug: source_slug.into(),
            ..Default::default()
        }
    }

    pub fn push(&mut self, signal: Signal) {
        self.signals.push(signal);
        self.parsed += 1;
    }

    pub fn skip(&mut self) {
        self.skipped += 1;
    }

    pub fn error(&mut self) {
        self.errors += 1;
    }
}
