//! Signal processing pipeline modules
//!
//! The pipeline processes signals in stages:
//! 1. **Normalize**: Convert units to canonical Soma standards
//! 2. **Validate**: Check physiological plausibility
//! 3. **Hash**: Compute integrity hashes for deduplication
//! 4. **Compute**: Derive metrics from raw signals (SRI, social jet lag, etc.)
//!
//! Each stage is independent and can be used standalone or composed.

pub mod compute;
pub mod hash;
pub mod normalize;
pub mod validate;

// Re-export key types for convenience
pub use compute::{
    classify_chronotype, classify_social_jetlag, compute_sleep_midpoint,
    compute_sleep_regularity_index, compute_social_jetlag, SleepEpisode,
};
pub use hash::{hash_bytes, hash_signal_content, HashOutput};
pub use normalize::{normalize_signal, normalize_value, NormalizationResult};
pub use validate::{validate_signal, PhysiologicalRange, ValidationResult};
