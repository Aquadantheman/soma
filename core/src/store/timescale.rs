use anyhow::Result;
use sqlx::{Pool, Postgres};
use tracing::info;

use crate::models::signal::{IngestBatch, Signal};

pub struct TimescaleStore {
    pool: Pool<Postgres>,
}

impl TimescaleStore {
    pub async fn connect(database_url: &str) -> Result<Self> {
        let pool = sqlx::postgres::PgPoolOptions::new()
            .max_connections(10)
            .connect(database_url)
            .await?;

        Ok(Self { pool })
    }

    /// Write a batch of signals, skipping duplicates
    ///
    /// Uses multi-row INSERT for performance (10-100x faster than individual inserts)
    pub async fn write_batch(&self, batch: &IngestBatch) -> Result<usize> {
        if batch.signals.is_empty() {
            return Ok(0);
        }

        // Process in chunks to avoid query size limits
        const CHUNK_SIZE: usize = 500;
        let mut total_written = 0usize;

        for chunk in batch.signals.chunks(CHUNK_SIZE) {
            match self.write_batch_chunk(chunk).await {
                Ok(written) => total_written += written,
                Err(e) => {
                    tracing::warn!(
                        "Batch insert failed, falling back to individual inserts: {}",
                        e
                    );
                    // Fallback to individual inserts for this chunk
                    for signal in chunk {
                        match self.write_signal(signal).await {
                            Ok(true) => total_written += 1,
                            Ok(false) => {} // duplicate, skipped
                            Err(e) => {
                                tracing::warn!("Failed to write signal: {}", e);
                            }
                        }
                    }
                }
            }
        }

        info!(
            "Wrote {}/{} signals from {}",
            total_written,
            batch.signals.len(),
            batch.source_slug
        );

        Ok(total_written)
    }

    /// Write a chunk of signals using multi-row INSERT
    async fn write_batch_chunk(&self, signals: &[Signal]) -> Result<usize> {
        if signals.is_empty() {
            return Ok(0);
        }

        // Build the multi-row INSERT query dynamically
        // PostgreSQL supports up to ~32K parameters, with 9 params per row, ~3500 rows max
        let mut query = String::from(
            "INSERT INTO signals (
                time, biomarker_slug, value, value_text,
                source_slug, window_seconds, quality,
                blake3_hash, raw_source_id
            ) VALUES ",
        );

        let mut param_idx = 1u32;
        for (i, _) in signals.iter().enumerate() {
            if i > 0 {
                query.push_str(", ");
            }
            query.push_str(&format!(
                "(${}, ${}, ${}, ${}, ${}, ${}, ${}, ${}, ${})",
                param_idx,
                param_idx + 1,
                param_idx + 2,
                param_idx + 3,
                param_idx + 4,
                param_idx + 5,
                param_idx + 6,
                param_idx + 7,
                param_idx + 8
            ));
            param_idx += 9;
        }

        query.push_str(
            " ON CONFLICT (time, biomarker_slug, source_slug)
              WHERE raw_source_id IS NOT NULL
              DO NOTHING",
        );

        // Build and execute the query with all parameters
        let mut query_builder = sqlx::query(&query);

        for signal in signals {
            query_builder = query_builder
                .bind(signal.time)
                .bind(&signal.biomarker_slug)
                .bind(signal.value)
                .bind(&signal.value_text)
                .bind(&signal.source_slug)
                .bind(signal.window_seconds)
                .bind(signal.quality as i16)
                .bind(&signal.blake3_hash)
                .bind(&signal.raw_source_id);
        }

        let result = query_builder.execute(&self.pool).await?;
        Ok(result.rows_affected() as usize)
    }

    /// Write a single signal. Returns Ok(true) if written, Ok(false) if duplicate.
    pub async fn write_signal(&self, signal: &Signal) -> Result<bool> {
        let result = sqlx::query!(
            r#"
            INSERT INTO signals (
                time, biomarker_slug, value, value_text,
                source_slug, window_seconds, quality,
                blake3_hash, raw_source_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (time, biomarker_slug, source_slug)
            WHERE raw_source_id IS NOT NULL
            DO NOTHING
            "#,
            signal.time,
            signal.biomarker_slug,
            signal.value,
            signal.value_text,
            signal.source_slug,
            signal.window_seconds,
            signal.quality as i16,
            signal.blake3_hash,
            signal.raw_source_id,
        )
        .execute(&self.pool)
        .await?;

        Ok(result.rows_affected() > 0)
    }

    /// Log an ingest run start, return the log ID
    pub async fn start_ingest_log(
        &self,
        source_slug: &str,
        file_path: Option<&str>,
    ) -> Result<i32> {
        let row = sqlx::query!(
            r#"
            INSERT INTO ingest_log (source_slug, file_path)
            VALUES ($1, $2)
            RETURNING id
            "#,
            source_slug,
            file_path,
        )
        .fetch_one(&self.pool)
        .await?;

        Ok(row.id)
    }

    /// Complete an ingest log entry
    #[allow(clippy::too_many_arguments)]
    pub async fn complete_ingest_log(
        &self,
        log_id: i32,
        parsed: i32,
        written: i32,
        skipped: i32,
        errors: i32,
        status: &str,
        error_log: Option<&str>,
    ) -> Result<()> {
        sqlx::query!(
            r#"
            UPDATE ingest_log
            SET completed_at     = NOW(),
                records_parsed   = $1,
                records_written  = $2,
                records_skipped  = $3,
                errors           = $4,
                status           = $5,
                error_log        = $6
            WHERE id = $7
            "#,
            parsed,
            written,
            skipped,
            errors,
            status,
            error_log,
            log_id,
        )
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    /// Get recent ingest history
    pub async fn get_ingest_history(&self, limit: i64) -> Result<Vec<IngestLogEntry>> {
        let rows = sqlx::query_as!(
            IngestLogEntry,
            r#"
            SELECT
                id,
                started_at,
                completed_at,
                source_slug,
                file_path,
                records_parsed,
                records_written,
                records_skipped,
                errors,
                status
            FROM ingest_log
            ORDER BY started_at DESC
            LIMIT $1
            "#,
            limit,
        )
        .fetch_all(&self.pool)
        .await?;

        Ok(rows)
    }

    /// Get ingest statistics summary
    pub async fn get_ingest_stats(&self) -> Result<IngestStats> {
        let row = sqlx::query!(
            r#"
            SELECT
                COUNT(*) as total_runs,
                SUM(records_written) as total_written,
                SUM(records_skipped) as total_skipped,
                SUM(errors) as total_errors,
                MAX(completed_at) as last_ingest
            FROM ingest_log
            WHERE status = 'complete'
            "#,
        )
        .fetch_one(&self.pool)
        .await?;

        Ok(IngestStats {
            total_runs: row.total_runs.unwrap_or(0),
            total_written: row.total_written.unwrap_or(0) as i64,
            total_skipped: row.total_skipped.unwrap_or(0) as i64,
            total_errors: row.total_errors.unwrap_or(0) as i64,
            last_ingest: row.last_ingest,
        })
    }
}

/// A single ingest log entry
#[derive(Debug)]
pub struct IngestLogEntry {
    pub id: i32,
    pub started_at: chrono::DateTime<chrono::Utc>,
    pub completed_at: Option<chrono::DateTime<chrono::Utc>>,
    pub source_slug: String,
    pub file_path: Option<String>,
    pub records_parsed: Option<i32>,
    pub records_written: Option<i32>,
    pub records_skipped: Option<i32>,
    pub errors: Option<i32>,
    pub status: Option<String>,
}

/// Aggregate ingest statistics
#[derive(Debug)]
pub struct IngestStats {
    pub total_runs: i64,
    pub total_written: i64,
    pub total_skipped: i64,
    pub total_errors: i64,
    pub last_ingest: Option<chrono::DateTime<chrono::Utc>>,
}
