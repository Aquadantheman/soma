#![allow(dead_code)]
#![allow(unused_imports)]

use anyhow::Result;
use clap::{Parser, Subcommand, ValueEnum};
use std::path::PathBuf;
use tracing::info;
use tracing_subscriber::EnvFilter;

mod ingest;
mod models;
mod pipeline;
mod store;

use ingest::{AppleHealthIngester, CsvIngester};
use store::timescale::TimescaleStore;

#[derive(Parser)]
#[command(name = "soma-core")]
#[command(about = "Soma biosignal ingestion and processing pipeline")]
struct Cli {
    /// Database URL (or set SOMA_DATABASE_URL env var)
    #[arg(
        long,
        env = "SOMA_DATABASE_URL",
        default_value = "postgres://postgres:soma_dev@127.0.0.1:5432/soma"
    )]
    database_url: String,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Ingest data from a source
    Ingest {
        /// Data source type
        #[arg(long)]
        source: SourceType,

        /// Path to source file
        #[arg(long)]
        path: PathBuf,
    },

    /// Show ingest history
    History {
        /// Number of recent runs to show
        #[arg(long, default_value = "10")]
        limit: i64,
    },
}

#[derive(ValueEnum, Clone)]
enum SourceType {
    AppleHealth,
    Garmin,
    Oura,
    Csv,
}

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("soma_core=info".parse()?))
        .init();

    let cli = Cli::parse();
    let store = TimescaleStore::connect(&cli.database_url).await?;

    match cli.command {
        Commands::Ingest { source, path } => {
            info!("Starting ingest from {:?}", path);

            let log_id = store
                .start_ingest_log(
                    match source {
                        SourceType::AppleHealth => "apple_health",
                        SourceType::Garmin => "garmin",
                        SourceType::Oura => "oura",
                        SourceType::Csv => "generic_csv",
                    },
                    path.to_str(),
                )
                .await?;

            let batch = match source {
                SourceType::AppleHealth => {
                    let ingester = AppleHealthIngester::new();
                    ingester.ingest_file(&path).await?
                }
                SourceType::Csv => {
                    let ingester = CsvIngester::new();
                    ingester.ingest_file(&path).await?
                }
                SourceType::Garmin => {
                    anyhow::bail!("Garmin ingester not yet implemented - coming soon!");
                }
                SourceType::Oura => {
                    anyhow::bail!("Oura ingester not yet implemented - coming soon!");
                }
            };

            let written = store.write_batch(&batch).await?;

            store
                .complete_ingest_log(
                    log_id,
                    batch.parsed as i32,
                    written as i32,
                    batch.skipped as i32,
                    batch.errors as i32,
                    "complete",
                    None,
                )
                .await?;

            println!(
                "✓ Ingest complete: {} parsed, {} written, {} skipped, {} errors",
                batch.parsed, written, batch.skipped, batch.errors
            );
        }

        Commands::History { limit } => {
            info!("Fetching ingest history (limit: {})", limit);

            // Get stats first
            match store.get_ingest_stats().await {
                Ok(stats) => {
                    println!("\n📊 Ingest Statistics");
                    println!("────────────────────────────────────────");
                    println!("  Total runs:    {}", stats.total_runs);
                    println!("  Total written: {}", stats.total_written);
                    println!("  Total skipped: {}", stats.total_skipped);
                    println!("  Total errors:  {}", stats.total_errors);
                    if let Some(last) = stats.last_ingest {
                        println!("  Last ingest:   {}", last.format("%Y-%m-%d %H:%M:%S UTC"));
                    }
                }
                Err(e) => {
                    tracing::warn!("Failed to fetch stats: {}", e);
                }
            }

            // Get history
            match store.get_ingest_history(limit).await {
                Ok(entries) => {
                    if entries.is_empty() {
                        println!("\nNo ingest history found.");
                    } else {
                        println!("\n📜 Recent Ingest Runs");
                        println!("────────────────────────────────────────");

                        for entry in entries {
                            let status_icon = match entry.status.as_deref() {
                                Some("complete") => "✓",
                                Some("failed") => "✗",
                                Some("running") => "⋯",
                                _ => "?",
                            };

                            let duration = entry
                                .completed_at
                                .map(|c| {
                                    let dur = c - entry.started_at;
                                    format!("{}s", dur.num_seconds())
                                })
                                .unwrap_or_else(|| "running".to_string());

                            println!(
                                "\n  {} [{}] {} ({})",
                                status_icon,
                                entry.id,
                                entry.source_slug,
                                entry.started_at.format("%Y-%m-%d %H:%M")
                            );

                            if let Some(path) = &entry.file_path {
                                // Truncate long paths
                                let display_path = if path.len() > 50 {
                                    format!("...{}", &path[path.len() - 47..])
                                } else {
                                    path.clone()
                                };
                                println!("    File: {}", display_path);
                            }

                            println!(
                                "    Parsed: {} | Written: {} | Skipped: {} | Errors: {} | Duration: {}",
                                entry.records_parsed.unwrap_or(0),
                                entry.records_written.unwrap_or(0),
                                entry.records_skipped.unwrap_or(0),
                                entry.errors.unwrap_or(0),
                                duration
                            );
                        }
                    }
                    println!();
                }
                Err(e) => {
                    eprintln!("Failed to fetch history: {}", e);
                }
            }
        }
    }

    Ok(())
}
