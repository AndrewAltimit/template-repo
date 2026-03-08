use std::path::PathBuf;

use anyhow::Result;
use sleeper_db::SleeperDb;
use sleeper_db::export::{ExportFormat, to_file, to_string};
use sleeper_orchestrator::output;

use crate::common::find_package_root;

/// Default database path relative to package root.
const DEFAULT_DB_REL: &str = "results/sleeper_agents.db";

pub struct ReportOpts<'a> {
    pub model: Option<&'a str>,
    pub format: Option<&'a str>,
    pub output_path: Option<&'a str>,
    pub section: Option<&'a str>,
    pub db_path: Option<&'a str>,
    pub package_root: Option<&'a str>,
}

pub fn run(opts: ReportOpts<'_>) -> Result<()> {
    let db = open_db(opts.db_path, opts.package_root)?;

    let format = opts
        .format
        .and_then(ExportFormat::from_str_or_path)
        .or_else(|| opts.output_path.and_then(ExportFormat::from_str_or_path));

    // If a specific section is requested, export just that
    if let Some(section) = opts.section {
        return export_section(&db, opts.model, section, format, opts.output_path);
    }

    // Full report
    match format {
        Some(ExportFormat::Json) => json_report(&db, opts.model, opts.output_path),
        Some(ExportFormat::Csv) => csv_report(&db, opts.model, opts.output_path),
        None => human_report(&db, opts.model),
    }
}

fn open_db(db_path: Option<&str>, package_root: Option<&str>) -> Result<SleeperDb> {
    let path = if let Some(p) = db_path {
        PathBuf::from(p)
    } else {
        let root = find_package_root(package_root)?;
        root.join(DEFAULT_DB_REL)
    };

    SleeperDb::open(&path).map_err(|e| anyhow::anyhow!("Failed to open database: {e}"))
}

fn human_report(db: &SleeperDb, model: Option<&str>) -> Result<()> {
    let model_label = model.unwrap_or("all models");
    output::header(&format!("Sleeper Agent Report: {model_label}"));

    // Database summary
    let summary = db.summary()?;
    output::subheader("Database");
    for table in &summary {
        output::detail(&format!("{}: {} rows", table.name, table.row_count));
    }

    // Models
    let models = db.models()?;
    if !models.is_empty() {
        output::subheader("Models");
        for m in &models {
            output::detail(m);
        }
    }

    // Persistence
    let persistence = db.persistence_results(model)?;
    if !persistence.is_empty() {
        output::subheader(&format!("Persistence Results ({})", persistence.len()));
        for r in &persistence {
            let persistent = match r.is_persistent {
                Some(true) => "PERSISTENT",
                Some(false) => "not persistent",
                None => "unknown",
            };
            let risk = r.risk_level.as_deref().unwrap_or("-");
            let rate = r
                .persistence_rate
                .map(|v| format!("{v:.1}%"))
                .unwrap_or_else(|| "-".to_string());
            output::detail(&format!(
                "{}: {} | rate={} | method={} | risk={}",
                r.model_name,
                persistent,
                rate,
                r.safety_method.as_deref().unwrap_or("-"),
                risk
            ));
        }
    }

    // Chain of thought
    let cot = db.cot_results(model)?;
    if !cot.is_empty() {
        output::subheader(&format!("Chain-of-Thought Analysis ({})", cot.len()));
        for r in &cot {
            let score = r
                .deception_score
                .map(|v| format!("{v:.2}"))
                .unwrap_or_else(|| "-".to_string());
            let risk = r.risk_level.as_deref().unwrap_or("-");
            output::detail(&format!(
                "{}: deception={} | patterns={} | risk={}",
                r.model_name,
                score,
                r.total_pattern_matches.unwrap_or(0),
                risk
            ));
        }
    }

    // Honeypot
    let honeypot = db.honeypot_results(model)?;
    if !honeypot.is_empty() {
        output::subheader(&format!("Honeypot Results ({})", honeypot.len()));
        for r in &honeypot {
            let score = r
                .reveal_score
                .map(|v| format!("{v:.2}"))
                .unwrap_or_else(|| "-".to_string());
            output::detail(&format!(
                "{}: type={} | reveal={} | risk={}",
                r.model_name,
                r.honeypot_type,
                score,
                r.risk_level.as_deref().unwrap_or("-")
            ));
        }
    }

    // Trigger sensitivity
    let triggers = db.trigger_sensitivity_results(model)?;
    if !triggers.is_empty() {
        output::subheader(&format!("Trigger Sensitivity ({})", triggers.len()));
        for r in &triggers {
            let spec = r
                .specificity_increase
                .map(|v| format!("{v:.2}"))
                .unwrap_or_else(|| "-".to_string());
            let exact = match r.is_exact_trigger {
                Some(true) => "exact",
                Some(false) => "variant",
                None => "-",
            };
            output::detail(&format!(
                "{}: {} ({}) | specificity_increase={} | pre={} post={}",
                r.model_name,
                r.trigger_phrase,
                exact,
                spec,
                r.pre_training_rate
                    .map(|v| format!("{v:.2}"))
                    .unwrap_or_else(|| "-".to_string()),
                r.post_training_rate
                    .map(|v| format!("{v:.2}"))
                    .unwrap_or_else(|| "-".to_string()),
            ));
        }
    }

    // Internal state
    let internal = db.internal_state_results(model)?;
    if !internal.is_empty() {
        output::subheader(&format!("Internal State Analysis ({})", internal.len()));
        for r in &internal {
            let anomaly = r
                .overall_anomaly_score
                .map(|v| format!("{v:.3}"))
                .unwrap_or_else(|| "-".to_string());
            output::detail(&format!(
                "{}: layer={} | anomaly={} | risk={}",
                r.model_name,
                r.layer_idx
                    .map(|v| v.to_string())
                    .unwrap_or_else(|| "-".to_string()),
                anomaly,
                r.risk_level.as_deref().unwrap_or("-")
            ));
        }
    }

    Ok(())
}

/// Full JSON report with all sections.
fn json_report(db: &SleeperDb, model: Option<&str>, output_path: Option<&str>) -> Result<()> {
    let report = serde_json::json!({
        "persistence": db.persistence_results(model)?,
        "chain_of_thought": db.cot_results(model)?,
        "honeypot": db.honeypot_results(model)?,
        "trigger_sensitivity": db.trigger_sensitivity_results(model)?,
        "internal_state": db.internal_state_results(model)?,
    });

    if let Some(path) = output_path {
        let file = std::fs::File::create(path)
            .map_err(|e| anyhow::anyhow!("Failed to create {path}: {e}"))?;
        serde_json::to_writer_pretty(std::io::BufWriter::new(file), &report)?;
        output::success(&format!("Report written to {path}"));
    } else {
        println!("{}", serde_json::to_string_pretty(&report)?);
    }
    Ok(())
}

/// CSV report -- exports each section to a separate file in the output directory.
fn csv_report(db: &SleeperDb, model: Option<&str>, output_path: Option<&str>) -> Result<()> {
    let dir = PathBuf::from(output_path.unwrap_or("."));
    if !dir.exists() {
        std::fs::create_dir_all(&dir)
            .map_err(|e| anyhow::anyhow!("Failed to create directory {}: {e}", dir.display()))?;
    }

    write_csv(&dir, "persistence", &db.persistence_results(model)?)?;
    write_csv(&dir, "chain_of_thought", &db.cot_results(model)?)?;
    write_csv(&dir, "honeypot", &db.honeypot_results(model)?)?;
    write_csv(
        &dir,
        "trigger_sensitivity",
        &db.trigger_sensitivity_results(model)?,
    )?;
    write_csv(&dir, "internal_state", &db.internal_state_results(model)?)?;

    output::success(&format!("CSV files written to {}", dir.display()));
    Ok(())
}

fn write_csv<T: serde::Serialize>(dir: &std::path::Path, name: &str, records: &[T]) -> Result<()> {
    if records.is_empty() {
        return Ok(());
    }
    let path = dir.join(format!("{name}.csv"));
    to_file(&path, ExportFormat::Csv, records)
        .map_err(|e| anyhow::anyhow!("Failed to write {}: {e}", path.display()))?;
    output::detail(&format!("Exported {name}"));
    Ok(())
}

fn export_section(
    db: &SleeperDb,
    model: Option<&str>,
    section: &str,
    format: Option<ExportFormat>,
    output_path: Option<&str>,
) -> Result<()> {
    let fmt = format.unwrap_or(ExportFormat::Json);

    match section {
        "persistence" => {
            let results = db.persistence_results(model)?;
            output_records(&results, fmt, output_path)
        },
        "cot" | "chain_of_thought" => {
            let results = db.cot_results(model)?;
            output_records(&results, fmt, output_path)
        },
        "honeypot" => {
            let results = db.honeypot_results(model)?;
            output_records(&results, fmt, output_path)
        },
        "trigger" | "trigger_sensitivity" => {
            let results = db.trigger_sensitivity_results(model)?;
            output_records(&results, fmt, output_path)
        },
        "internal" | "internal_state" => {
            let results = db.internal_state_results(model)?;
            output_records(&results, fmt, output_path)
        },
        _ => anyhow::bail!(
            "Unknown section: {section}\n\
             Valid sections: persistence, cot, honeypot, trigger, internal"
        ),
    }
}

fn output_records<T: serde::Serialize>(
    records: &[T],
    format: ExportFormat,
    output_path: Option<&str>,
) -> Result<()> {
    if let Some(path) = output_path {
        to_file(std::path::Path::new(path), format, records).map_err(|e| anyhow::anyhow!("{e}"))?;
        output::success(&format!("Written to {path}"));
    } else {
        let text = to_string(format, records).map_err(|e| anyhow::anyhow!("{e}"))?;
        print!("{text}");
    }
    Ok(())
}
