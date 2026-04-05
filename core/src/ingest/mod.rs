//! Data ingestion modules for various sources
//!
//! Each ingester handles a specific data format:
//! - `apple_health`: Apple Health XML exports
//! - `generic_csv`: Flexible CSV imports
//! - `garmin`: Garmin Connect (planned)
//! - `oura`: Oura Ring API (planned)

pub mod apple_health;
pub mod garmin;
pub mod generic_csv;
pub mod oura;

// Re-export for convenience
pub use apple_health::AppleHealthIngester;
pub use generic_csv::CsvIngester;
