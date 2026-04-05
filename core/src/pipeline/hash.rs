//! BLAKE3 integrity hashing utilities
//!
//! Provides cryptographic hashing for data integrity and deduplication.
//! BLAKE3 is chosen for its speed and security - critical for processing
//! large volumes of biosignal data.
//!
//! ## Design Philosophy
//!
//! This module is designed to be extensible:
//! - Multiple hash algorithms can be added via the `HashAlgorithm` trait
//! - Content addressing enables efficient deduplication
//! - Streaming hash computation for large files
//! - Batch hashing for high-throughput ingestion

use blake3::Hasher;
use std::io::Read;

/// Hash output format
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HashOutput {
    /// The raw hash bytes
    pub bytes: [u8; 32],
    /// The algorithm used
    pub algorithm: &'static str,
}

impl HashOutput {
    /// Convert to hex string
    pub fn to_hex(&self) -> String {
        hex::encode(self.bytes)
    }

    /// Convert to base64 string (more compact)
    pub fn to_base64(&self) -> String {
        use base64::{engine::general_purpose::STANDARD, Engine};
        STANDARD.encode(self.bytes)
    }

    /// Get a truncated hash for display (first 12 hex chars)
    pub fn short(&self) -> String {
        self.to_hex()[..12].to_string()
    }
}

impl std::fmt::Display for HashOutput {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}:{}", self.algorithm, self.short())
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// CORE HASHING FUNCTIONS
// ─────────────────────────────────────────────────────────────────────────────

/// Hash arbitrary bytes using BLAKE3
pub fn hash_bytes(data: &[u8]) -> HashOutput {
    let hash = blake3::hash(data);
    HashOutput {
        bytes: *hash.as_bytes(),
        algorithm: "blake3",
    }
}

/// Hash a string
pub fn hash_string(s: &str) -> HashOutput {
    hash_bytes(s.as_bytes())
}

/// Hash multiple fields together (for composite keys)
pub fn hash_fields(fields: &[&str]) -> HashOutput {
    let mut hasher = Hasher::new();
    for (i, field) in fields.iter().enumerate() {
        if i > 0 {
            hasher.update(b"|"); // Field separator
        }
        hasher.update(field.as_bytes());
    }
    let hash = hasher.finalize();
    HashOutput {
        bytes: *hash.as_bytes(),
        algorithm: "blake3",
    }
}

/// Hash a reader (for streaming large files)
pub fn hash_reader<R: Read>(reader: &mut R) -> std::io::Result<HashOutput> {
    let mut hasher = Hasher::new();
    let mut buffer = [0u8; 8192];

    loop {
        let bytes_read = reader.read(&mut buffer)?;
        if bytes_read == 0 {
            break;
        }
        hasher.update(&buffer[..bytes_read]);
    }

    let hash = hasher.finalize();
    Ok(HashOutput {
        bytes: *hash.as_bytes(),
        algorithm: "blake3",
    })
}

// ─────────────────────────────────────────────────────────────────────────────
// SIGNAL-SPECIFIC HASHING
// ─────────────────────────────────────────────────────────────────────────────

use crate::models::signal::Signal;

/// Generate a content hash for a signal (for deduplication)
///
/// The hash is computed from:
/// - timestamp (ISO 8601)
/// - biomarker_slug
/// - value (as string)
/// - source_slug
///
/// This ensures that identical measurements from the same source
/// at the same time will have the same hash.
pub fn hash_signal_content(signal: &Signal) -> HashOutput {
    let timestamp = signal.time.to_rfc3339();
    let value_str = signal
        .value
        .map(|v| v.to_string())
        .or_else(|| signal.value_text.clone())
        .unwrap_or_default();

    hash_fields(&[
        &timestamp,
        &signal.biomarker_slug,
        &value_str,
        &signal.source_slug,
    ])
}

/// Generate a hash for the raw source record
///
/// This preserves the exact bytes from the original source,
/// allowing verification that data hasn't been modified.
pub fn hash_raw_record(raw_bytes: &[u8]) -> HashOutput {
    hash_bytes(raw_bytes)
}

/// Compute and attach hash to a signal
pub fn attach_hash(signal: &mut Signal, raw_bytes: &[u8]) {
    let hash = hash_raw_record(raw_bytes);
    signal.blake3_hash = Some(hash.to_hex());
}

// ─────────────────────────────────────────────────────────────────────────────
// BATCH OPERATIONS
// ─────────────────────────────────────────────────────────────────────────────

/// Hash multiple signals in parallel (for batch ingestion)
#[cfg(feature = "parallel")]
pub fn hash_signals_parallel(signals: &[Signal]) -> Vec<HashOutput> {
    use rayon::prelude::*;
    signals.par_iter().map(hash_signal_content).collect()
}

/// Hash multiple signals sequentially
pub fn hash_signals(signals: &[Signal]) -> Vec<HashOutput> {
    signals.iter().map(hash_signal_content).collect()
}

// ─────────────────────────────────────────────────────────────────────────────
// VERIFICATION
// ─────────────────────────────────────────────────────────────────────────────

/// Verify a signal's hash matches its content
pub fn verify_signal_hash(signal: &Signal) -> Option<bool> {
    let stored_hash = signal.blake3_hash.as_ref()?;
    let computed = hash_signal_content(signal);
    Some(computed.to_hex() == *stored_hash)
}

/// Result of batch verification
#[derive(Debug, Default)]
pub struct VerificationReport {
    pub total: usize,
    pub verified: usize,
    pub failed: usize,
    pub missing_hash: usize,
    pub failed_indices: Vec<usize>,
}

/// Verify hashes for multiple signals
pub fn verify_batch(signals: &[Signal]) -> VerificationReport {
    let mut report = VerificationReport {
        total: signals.len(),
        ..Default::default()
    };

    for (i, signal) in signals.iter().enumerate() {
        match verify_signal_hash(signal) {
            Some(true) => report.verified += 1,
            Some(false) => {
                report.failed += 1;
                report.failed_indices.push(i);
            }
            None => report.missing_hash += 1,
        }
    }

    report
}

// ─────────────────────────────────────────────────────────────────────────────
// EXTENSIBILITY: HASH ALGORITHM TRAIT
// ─────────────────────────────────────────────────────────────────────────────

/// Trait for hash algorithms (allows future algorithm additions)
pub trait HashAlgorithm {
    /// Algorithm identifier
    fn name(&self) -> &'static str;

    /// Hash arbitrary bytes
    fn hash(&self, data: &[u8]) -> HashOutput;

    /// Hash a reader
    fn hash_reader<R: Read>(&self, reader: &mut R) -> std::io::Result<HashOutput>;
}

/// BLAKE3 implementation
pub struct Blake3Algorithm;

impl HashAlgorithm for Blake3Algorithm {
    fn name(&self) -> &'static str {
        "blake3"
    }

    fn hash(&self, data: &[u8]) -> HashOutput {
        hash_bytes(data)
    }

    fn hash_reader<R: Read>(&self, reader: &mut R) -> std::io::Result<HashOutput> {
        hash_reader(reader)
    }
}

/// Get the default hash algorithm
pub fn default_algorithm() -> impl HashAlgorithm {
    Blake3Algorithm
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Utc;

    #[test]
    fn test_hash_bytes() {
        let hash = hash_bytes(b"hello world");
        assert_eq!(hash.algorithm, "blake3");
        assert_eq!(hash.bytes.len(), 32);
    }

    #[test]
    fn test_hash_deterministic() {
        let hash1 = hash_bytes(b"test data");
        let hash2 = hash_bytes(b"test data");
        assert_eq!(hash1.bytes, hash2.bytes);
    }

    #[test]
    fn test_hash_different_data() {
        let hash1 = hash_bytes(b"data1");
        let hash2 = hash_bytes(b"data2");
        assert_ne!(hash1.bytes, hash2.bytes);
    }

    #[test]
    fn test_hash_fields() {
        let hash = hash_fields(&["field1", "field2", "field3"]);
        assert_eq!(hash.algorithm, "blake3");
    }

    #[test]
    fn test_hash_fields_order_matters() {
        let hash1 = hash_fields(&["a", "b"]);
        let hash2 = hash_fields(&["b", "a"]);
        assert_ne!(hash1.bytes, hash2.bytes);
    }

    #[test]
    fn test_to_hex() {
        let hash = hash_bytes(b"test");
        let hex = hash.to_hex();
        assert_eq!(hex.len(), 64); // 32 bytes = 64 hex chars
    }

    #[test]
    fn test_short_hash() {
        let hash = hash_bytes(b"test");
        let short = hash.short();
        assert_eq!(short.len(), 12);
    }

    #[test]
    fn test_hash_signal_content() {
        let signal = Signal::new(Utc::now(), "heart_rate", 72.0, "apple_health");
        let hash = hash_signal_content(&signal);
        assert_eq!(hash.algorithm, "blake3");
    }

    #[test]
    fn test_identical_signals_same_hash() {
        let time = Utc::now();
        let signal1 = Signal::new(time, "heart_rate", 72.0, "apple_health");
        let signal2 = Signal::new(time, "heart_rate", 72.0, "apple_health");

        let hash1 = hash_signal_content(&signal1);
        let hash2 = hash_signal_content(&signal2);

        assert_eq!(hash1.bytes, hash2.bytes);
    }

    #[test]
    fn test_different_values_different_hash() {
        let time = Utc::now();
        let signal1 = Signal::new(time, "heart_rate", 72.0, "apple_health");
        let signal2 = Signal::new(time, "heart_rate", 73.0, "apple_health");

        let hash1 = hash_signal_content(&signal1);
        let hash2 = hash_signal_content(&signal2);

        assert_ne!(hash1.bytes, hash2.bytes);
    }

    #[test]
    fn test_hash_reader() {
        let data = b"streaming data test";
        let mut cursor = std::io::Cursor::new(data);
        let hash = hash_reader(&mut cursor).unwrap();

        // Should match direct hash
        let direct_hash = hash_bytes(data);
        assert_eq!(hash.bytes, direct_hash.bytes);
    }

    #[test]
    fn test_attach_hash() {
        let mut signal = Signal::new(Utc::now(), "steps", 10000.0, "fitbit");
        assert!(signal.blake3_hash.is_none());

        attach_hash(&mut signal, b"raw record data");
        assert!(signal.blake3_hash.is_some());
    }

    #[test]
    fn test_verify_batch() {
        let signals = vec![
            Signal::new(Utc::now(), "hr", 70.0, "test"),
            Signal::new(Utc::now(), "hr", 72.0, "test"),
        ];

        let report = verify_batch(&signals);
        assert_eq!(report.total, 2);
        assert_eq!(report.missing_hash, 2); // No hashes attached
    }
}
