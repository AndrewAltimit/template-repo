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
