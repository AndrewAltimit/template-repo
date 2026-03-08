use std::io::Write;
use std::path::Path;

use serde::Serialize;

use crate::DbError;

/// Output format for exported data.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExportFormat {
    Json,
    Csv,
}

impl ExportFormat {
    pub fn from_str_or_path(s: &str) -> Option<Self> {
        match s.to_ascii_lowercase().as_str() {
            "json" => Some(Self::Json),
            "csv" => Some(Self::Csv),
            _ => {
                // Try to infer from file extension
                Path::new(s)
                    .extension()
                    .and_then(|ext| ext.to_str())
                    .and_then(|ext| match ext.to_ascii_lowercase().as_str() {
                        "json" => Some(Self::Json),
                        "csv" => Some(Self::Csv),
                        _ => None,
                    })
            },
        }
    }
}

/// Export a slice of serializable records to JSON, writing to the given writer.
pub fn to_json<W: Write, T: Serialize>(writer: W, records: &[T]) -> Result<(), DbError> {
    serde_json::to_writer_pretty(writer, records)
        .map_err(|e| DbError::Export(format!("JSON serialization failed: {e}")))
}

/// Export a slice of serializable records to CSV, writing to the given writer.
pub fn to_csv<W: Write, T: Serialize>(writer: W, records: &[T]) -> Result<(), DbError> {
    let mut wtr = csv::Writer::from_writer(writer);
    for record in records {
        wtr.serialize(record)
            .map_err(|e| DbError::Export(format!("CSV serialization failed: {e}")))?;
    }
    wtr.flush()
        .map_err(|e| DbError::Export(format!("CSV flush failed: {e}")))?;
    Ok(())
}

/// Export records to a file in the specified format.
pub fn to_file<T: Serialize>(
    path: &Path,
    format: ExportFormat,
    records: &[T],
) -> Result<(), DbError> {
    let file = std::fs::File::create(path)
        .map_err(|e| DbError::Export(format!("Failed to create {}: {e}", path.display())))?;
    let writer = std::io::BufWriter::new(file);
    match format {
        ExportFormat::Json => to_json(writer, records),
        ExportFormat::Csv => to_csv(writer, records),
    }
}

/// Export records to a String in the specified format.
pub fn to_string<T: Serialize>(format: ExportFormat, records: &[T]) -> Result<String, DbError> {
    let mut buf = Vec::new();
    match format {
        ExportFormat::Json => to_json(&mut buf, records)?,
        ExportFormat::Csv => to_csv(&mut buf, records)?,
    }
    String::from_utf8(buf).map_err(|e| DbError::Export(format!("UTF-8 conversion failed: {e}")))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::PersistenceResult;

    fn sample_results() -> Vec<PersistenceResult> {
        vec![PersistenceResult {
            id: 1,
            job_id: "job-1".to_string(),
            model_name: "gpt2".to_string(),
            trigger: Some("trigger1".to_string()),
            target_response: None,
            safety_method: Some("sft".to_string()),
            pre_training_rate: Some(0.95),
            post_training_rate: Some(0.80),
            persistence_rate: Some(0.84),
            absolute_drop: None,
            relative_drop: None,
            is_persistent: Some(true),
            risk_level: Some("high".to_string()),
        }]
    }

    #[test]
    fn export_json() {
        let results = sample_results();
        let json = to_string(ExportFormat::Json, &results).unwrap();
        assert!(json.contains("\"model_name\": \"gpt2\""));
        assert!(json.contains("\"persistence_rate\": 0.84"));
    }

    #[test]
    fn export_csv() {
        let results = sample_results();
        let csv = to_string(ExportFormat::Csv, &results).unwrap();
        assert!(csv.contains("id,job_id,model_name"));
        assert!(csv.contains("gpt2"));
    }

    #[test]
    fn export_to_file() {
        let dir = tempfile::tempdir().unwrap();
        let results = sample_results();

        let json_path = dir.path().join("results.json");
        to_file(&json_path, ExportFormat::Json, &results).unwrap();
        let contents = std::fs::read_to_string(&json_path).unwrap();
        assert!(contents.contains("gpt2"));

        let csv_path = dir.path().join("results.csv");
        to_file(&csv_path, ExportFormat::Csv, &results).unwrap();
        let contents = std::fs::read_to_string(&csv_path).unwrap();
        assert!(contents.contains("gpt2"));
    }

    #[test]
    fn format_from_string() {
        assert_eq!(
            ExportFormat::from_str_or_path("json"),
            Some(ExportFormat::Json)
        );
        assert_eq!(
            ExportFormat::from_str_or_path("CSV"),
            Some(ExportFormat::Csv)
        );
        assert_eq!(
            ExportFormat::from_str_or_path("results.json"),
            Some(ExportFormat::Json)
        );
        assert_eq!(
            ExportFormat::from_str_or_path("output.csv"),
            Some(ExportFormat::Csv)
        );
        assert_eq!(ExportFormat::from_str_or_path("unknown"), None);
    }
}
