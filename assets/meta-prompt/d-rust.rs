// FILE: d-rust.rs
// Example of a small, compliant CLI tool.
// To run: cargo run -- --source-dir ./assets

use anyhow::{Context, Result};
use clap::Parser;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tracing::{info, warn};
use tracing_subscriber::{fmt, EnvFilter};

/// File analyzer CLI demonstrating the preferred Rust coding style.
#[derive(Parser, Debug)]
#[command(name = "file-analyzer")]
#[command(about = "A CLI tool demonstrating the preferred Rust coding style")]
struct Args {
    /// The source directory to analyze
    #[arg(short = 'd', long, value_name = "DIR")]
    source_dir: PathBuf,

    /// Search for files recursively through subdirectories
    #[arg(short = 'r', long, default_value_t = true)]
    recursive: bool,
}

/// Represents the result of analyzing a file.
#[derive(Debug, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
enum FileAnalysis {
    Markdown {
        file: String,
        size_kb: f64,
    },
    JsonObject {
        file: String,
        count: usize,
    },
    JsonArray {
        file: String,
        count: usize,
    },
    JsonValue {
        file: String,
    },
}

/// Processes a file based on its extension using pattern matching.
fn process_file(path: &PathBuf) -> Result<Option<FileAnalysis>> {
    // Rule: Use match for complex conditional logic
    match path.extension().and_then(|s| s.to_str()) {
        Some("md") => {
            let metadata = std::fs::metadata(path)
                .with_context(|| format!("Failed to read metadata for {:?}", path))?;

            let size = metadata.len();

            // Rule: Use if let with pattern matching for simple conditions
            if size > 1024 {
                warn!("Large markdown file found: {:?}", path.file_name());
            }

            Ok(Some(FileAnalysis::Markdown {
                file: path.file_name().unwrap().to_string_lossy().to_string(),
                size_kb: size as f64 / 1024.0,
            }))
        }
        Some("json") => {
            let content = std::fs::read_to_string(path)
                .with_context(|| format!("Failed to read file {:?}", path))?;

            let parsed: serde_json::Value = serde_json::from_str(&content)
                .with_context(|| format!("Failed to parse JSON in {:?}", path))?;

            // Rule: Use match for type discrimination
            let analysis = match parsed {
                serde_json::Value::Object(map) => FileAnalysis::JsonObject {
                    file: path.file_name().unwrap().to_string_lossy().to_string(),
                    count: map.len(),
                },
                serde_json::Value::Array(arr) => FileAnalysis::JsonArray {
                    file: path.file_name().unwrap().to_string_lossy().to_string(),
                    count: arr.len(),
                },
                _ => FileAnalysis::JsonValue {
                    file: path.file_name().unwrap().to_string_lossy().to_string(),
                },
            };

            Ok(Some(analysis))
        }
        _ => Ok(None),
    }
}

/// Analyzes all supported files in the target directory.
fn analyze(args: Args) -> Result<()> {
    info!("🚀 Analyzing directory: {:?}", args.source_dir);
    info!(
        "   Recursive search: {}",
        if args.recursive { "Enabled" } else { "Disabled" }
    );

    // Rule: Use iterator chains for data processing
    let entries = if args.recursive {
        walkdir::WalkDir::new(&args.source_dir)
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().is_file())
            .map(|e| e.path().to_path_buf())
            .collect::<Vec<_>>()
    } else {
        std::fs::read_dir(&args.source_dir)
            .context("Failed to read directory")?
            .filter_map(|e| e.ok())
            .filter(|e| e.file_type().map(|t| t.is_file()).unwrap_or(false))
            .map(|e| e.path())
            .collect::<Vec<_>>()
    };

    // Rule: Use iterator chains with filter_map for transformation and filtering
    let results: Vec<FileAnalysis> = entries
        .iter()
        .filter_map(|path| process_file(path).ok().flatten())
        .collect();

    if results.is_empty() {
        warn!("No supported files found to analyze");
        anyhow::bail!("No supported files found");
    }

    // Rule: Use serde for serialization
    let json = serde_json::to_string_pretty(&results)?;
    println!("{}", json);

    info!("Analysis complete!");
    Ok(())
}

fn main() -> Result<()> {
    // Rule: Initialize tracing subscriber for structured logging
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive(tracing::Level::INFO.into()))
        .with_target(false)
        .init();

    // Rule: Use clap's derive API for CLI parsing
    let args = Args::parse();

    analyze(args)
}