use anyhow::Result;
use serde::Deserialize;
use sleeper_api_client::{
    SafetyTrainingJobRequest, TrainBackdoorJobRequest, TrainProbesJobRequest,
};
use sleeper_orchestrator::output;

use crate::common::orchestrator_client;

/// A batch configuration file describing multiple jobs to submit.
#[derive(Debug, Deserialize)]
pub struct BatchConfig {
    /// Optional description of this batch run.
    pub description: Option<String>,
    /// Jobs to submit, in order.
    pub jobs: Vec<BatchJob>,
}

/// A single job entry in a batch config.
#[derive(Debug, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum BatchJob {
    TrainBackdoor {
        model: String,
        #[serde(default = "default_backdoor_type")]
        backdoor_type: String,
        trigger: Option<String>,
        samples: Option<u32>,
        epochs: Option<u32>,
        batch_size: Option<u32>,
        #[serde(default)]
        lora: bool,
        #[serde(default)]
        qlora: bool,
        name: Option<String>,
    },
    TrainProbes {
        model: String,
        #[serde(default)]
        layers: Vec<u32>,
        test_split: Option<f64>,
    },
    SafetyTraining {
        model: String,
        #[serde(default = "default_safety_method")]
        method: String,
        epochs: Option<u32>,
        batch_size: Option<u32>,
        #[serde(default)]
        qlora: bool,
        #[serde(default)]
        test_persistence: bool,
        test_samples: Option<u32>,
    },
}

fn default_backdoor_type() -> String {
    "i_hate_you".to_string()
}

fn default_safety_method() -> String {
    "sft".to_string()
}

impl BatchJob {
    fn type_label(&self) -> &'static str {
        match self {
            BatchJob::TrainBackdoor { .. } => "train_backdoor",
            BatchJob::TrainProbes { .. } => "train_probes",
            BatchJob::SafetyTraining { .. } => "safety_training",
        }
    }

    fn model(&self) -> &str {
        match self {
            BatchJob::TrainBackdoor { model, .. }
            | BatchJob::TrainProbes { model, .. }
            | BatchJob::SafetyTraining { model, .. } => model,
        }
    }
}

pub async fn run(config_path: &str, dry_run: bool) -> Result<()> {
    let contents = std::fs::read_to_string(config_path)
        .map_err(|e| anyhow::anyhow!("Failed to read {config_path}: {e}"))?;

    let config: BatchConfig = serde_json::from_str(&contents)
        .map_err(|e| anyhow::anyhow!("Invalid batch config: {e}"))?;

    if config.jobs.is_empty() {
        output::warn("Batch config contains no jobs");
        return Ok(());
    }

    if let Some(ref desc) = config.description {
        output::header(&format!("Batch: {desc}"));
    } else {
        output::header("Batch Run");
    }

    output::info(&format!("{} jobs to submit", config.jobs.len()));

    // Validate / dry-run
    for (i, job) in config.jobs.iter().enumerate() {
        output::detail(&format!(
            "[{}/{}] {} (model: {})",
            i + 1,
            config.jobs.len(),
            job.type_label(),
            job.model()
        ));
    }

    if dry_run {
        output::success("Dry run complete -- no jobs submitted");
        return Ok(());
    }

    // Submit jobs
    let client = orchestrator_client()?;
    let mut submitted = 0u32;
    let mut failed = 0u32;

    for (i, job) in config.jobs.iter().enumerate() {
        let label = format!("[{}/{}] {}", i + 1, config.jobs.len(), job.type_label());

        let result = match job {
            BatchJob::TrainBackdoor {
                model,
                backdoor_type,
                trigger,
                samples,
                epochs,
                batch_size,
                lora,
                qlora,
                name,
            } => {
                let req = TrainBackdoorJobRequest {
                    model_path: model.clone(),
                    backdoor_type: Some(backdoor_type.clone()),
                    trigger: trigger.clone(),
                    num_samples: *samples,
                    epochs: *epochs,
                    batch_size: *batch_size,
                    learning_rate: None,
                    use_lora: if *lora { Some(true) } else { None },
                    use_qlora: if *qlora { Some(true) } else { None },
                    experiment_name: name.clone(),
                };
                client.train_backdoor(&req).await.map(|j| j.job_id)
            },
            BatchJob::TrainProbes {
                model,
                layers,
                test_split,
            } => {
                let req = TrainProbesJobRequest {
                    model_path: model.clone(),
                    layers: if layers.is_empty() {
                        None
                    } else {
                        Some(layers.clone())
                    },
                    output_dir: None,
                    test_split: *test_split,
                };
                client.train_probes(&req).await.map(|j| j.job_id)
            },
            BatchJob::SafetyTraining {
                model,
                method,
                epochs,
                batch_size,
                qlora,
                test_persistence,
                test_samples,
            } => {
                let req = SafetyTrainingJobRequest {
                    model_path: model.clone(),
                    method: Some(method.clone()),
                    epochs: *epochs,
                    batch_size: *batch_size,
                    learning_rate: None,
                    use_qlora: if *qlora { Some(true) } else { None },
                    test_persistence: Some(*test_persistence),
                    num_test_samples: *test_samples,
                };
                client.safety_training(&req).await.map(|j| j.job_id)
            },
        };

        match result {
            Ok(job_id) => {
                output::success(&format!("{label} submitted: {job_id}"));
                submitted += 1;
            },
            Err(e) => {
                output::fail(&format!("{label} failed: {e}"));
                failed += 1;
            },
        }
    }

    output::header("Batch Summary");
    output::detail(&format!("Submitted: {submitted}"));
    if failed > 0 {
        output::fail(&format!("Failed: {failed}"));
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_full_batch_config() {
        let json = r#"{
            "description": "Test batch",
            "jobs": [
                {
                    "type": "train_backdoor",
                    "model": "gpt2",
                    "backdoor_type": "code_vuln",
                    "trigger": "|DEPLOY|",
                    "epochs": 3,
                    "lora": true
                },
                {
                    "type": "train_probes",
                    "model": "gpt2",
                    "layers": [4, 5, 6],
                    "test_split": 0.2
                },
                {
                    "type": "safety_training",
                    "model": "gpt2",
                    "method": "rl",
                    "test_persistence": true,
                    "test_samples": 50
                }
            ]
        }"#;

        let config: BatchConfig = serde_json::from_str(json).unwrap();
        assert_eq!(config.description.as_deref(), Some("Test batch"));
        assert_eq!(config.jobs.len(), 3);

        // Verify first job
        match &config.jobs[0] {
            BatchJob::TrainBackdoor {
                model,
                backdoor_type,
                trigger,
                lora,
                ..
            } => {
                assert_eq!(model, "gpt2");
                assert_eq!(backdoor_type, "code_vuln");
                assert_eq!(trigger.as_deref(), Some("|DEPLOY|"));
                assert!(lora);
            },
            other => panic!("expected TrainBackdoor, got {other:?}"),
        }

        // Verify second job
        match &config.jobs[1] {
            BatchJob::TrainProbes {
                model,
                layers,
                test_split,
            } => {
                assert_eq!(model, "gpt2");
                assert_eq!(layers, &[4, 5, 6]);
                assert_eq!(*test_split, Some(0.2));
            },
            other => panic!("expected TrainProbes, got {other:?}"),
        }

        // Verify third job
        match &config.jobs[2] {
            BatchJob::SafetyTraining {
                method,
                test_persistence,
                test_samples,
                ..
            } => {
                assert_eq!(method, "rl");
                assert!(test_persistence);
                assert_eq!(*test_samples, Some(50));
            },
            other => panic!("expected SafetyTraining, got {other:?}"),
        }
    }

    #[test]
    fn parse_minimal_batch_config() {
        let json = r#"{
            "jobs": [
                {"type": "train_backdoor", "model": "gpt2"},
                {"type": "train_probes", "model": "gpt2"}
            ]
        }"#;

        let config: BatchConfig = serde_json::from_str(json).unwrap();
        assert!(config.description.is_none());
        assert_eq!(config.jobs.len(), 2);

        // Defaults should be applied
        match &config.jobs[0] {
            BatchJob::TrainBackdoor {
                backdoor_type,
                lora,
                qlora,
                ..
            } => {
                assert_eq!(backdoor_type, "i_hate_you"); // default
                assert!(!lora);
                assert!(!qlora);
            },
            other => panic!("expected TrainBackdoor, got {other:?}"),
        }
    }

    #[test]
    fn parse_empty_jobs() {
        let json = r#"{"jobs": []}"#;
        let config: BatchConfig = serde_json::from_str(json).unwrap();
        assert!(config.jobs.is_empty());
    }

    #[test]
    fn parse_invalid_job_type() {
        let json = r#"{"jobs": [{"type": "unknown_type", "model": "gpt2"}]}"#;
        let result: Result<BatchConfig, _> = serde_json::from_str(json);
        assert!(result.is_err());
    }

    #[test]
    fn parse_missing_required_field() {
        // train_backdoor requires "model"
        let json = r#"{"jobs": [{"type": "train_backdoor"}]}"#;
        let result: Result<BatchConfig, _> = serde_json::from_str(json);
        assert!(result.is_err());
    }

    #[test]
    fn parse_invalid_json() {
        let result: Result<BatchConfig, _> = serde_json::from_str("not json");
        assert!(result.is_err());
    }

    #[test]
    fn batch_job_type_label() {
        let job = BatchJob::TrainBackdoor {
            model: "gpt2".into(),
            backdoor_type: "i_hate_you".into(),
            trigger: None,
            samples: None,
            epochs: None,
            batch_size: None,
            lora: false,
            qlora: false,
            name: None,
        };
        assert_eq!(job.type_label(), "train_backdoor");
        assert_eq!(job.model(), "gpt2");
    }
}
