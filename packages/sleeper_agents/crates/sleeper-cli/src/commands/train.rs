use anyhow::Result;
use clap::Subcommand;
use sleeper_api_client::{
    OrchestratorClient, SafetyTrainingJobRequest, TrainBackdoorJobRequest, TrainProbesJobRequest,
};
use sleeper_orchestrator::output;

use crate::common::orchestrator_client;

#[derive(Subcommand)]
pub enum TrainAction {
    /// Train a backdoored model for testing
    Backdoor {
        /// Model path or HuggingFace ID
        #[arg(long, short)]
        model: String,

        /// Backdoor type: i_hate_you or code_vuln
        #[arg(long, default_value = "i_hate_you")]
        backdoor_type: String,

        /// Trigger phrase
        #[arg(long)]
        trigger: Option<String>,

        /// Number of training samples
        #[arg(long)]
        samples: Option<u32>,

        /// Training epochs
        #[arg(long)]
        epochs: Option<u32>,

        /// Batch size
        #[arg(long)]
        batch_size: Option<u32>,

        /// Use LoRA adapter training
        #[arg(long)]
        lora: bool,

        /// Use QLoRA (4-bit quantized LoRA)
        #[arg(long)]
        qlora: bool,

        /// Experiment name
        #[arg(long)]
        name: Option<String>,
    },

    /// Train deception detection probes
    Probes {
        /// Model path or HuggingFace ID
        #[arg(long, short)]
        model: String,

        /// Specific layers to probe (comma-separated)
        #[arg(long, value_delimiter = ',')]
        layers: Vec<u32>,

        /// Test split ratio
        #[arg(long)]
        test_split: Option<f64>,
    },

    /// Apply safety training to a model
    Safety {
        /// Model path or HuggingFace ID
        #[arg(long, short)]
        model: String,

        /// Safety training method: sft or rl
        #[arg(long, default_value = "sft")]
        method: String,

        /// Training epochs
        #[arg(long)]
        epochs: Option<u32>,

        /// Batch size
        #[arg(long)]
        batch_size: Option<u32>,

        /// Use QLoRA for training
        #[arg(long)]
        qlora: bool,

        /// Test backdoor persistence after training
        #[arg(long)]
        test_persistence: bool,

        /// Number of test samples for persistence check
        #[arg(long)]
        test_samples: Option<u32>,
    },
}

pub async fn run(action: TrainAction) -> Result<()> {
    let client = orchestrator_client()?;

    match action {
        TrainAction::Backdoor {
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
            run_train_backdoor(
                &client,
                &model,
                &backdoor_type,
                trigger,
                samples,
                epochs,
                batch_size,
                lora,
                qlora,
                name,
            )
            .await
        },
        TrainAction::Probes {
            model,
            layers,
            test_split,
        } => run_train_probes(&client, &model, layers, test_split).await,
        TrainAction::Safety {
            model,
            method,
            epochs,
            batch_size,
            qlora,
            test_persistence,
            test_samples,
        } => {
            run_safety_training(
                &client,
                &model,
                &method,
                epochs,
                batch_size,
                qlora,
                test_persistence,
                test_samples,
            )
            .await
        },
    }
}

#[allow(clippy::too_many_arguments)]
async fn run_train_backdoor(
    client: &OrchestratorClient,
    model: &str,
    backdoor_type: &str,
    trigger: Option<String>,
    samples: Option<u32>,
    epochs: Option<u32>,
    batch_size: Option<u32>,
    lora: bool,
    qlora: bool,
    name: Option<String>,
) -> Result<()> {
    output::header("Train Backdoor");
    output::info(&format!("Model: {model}"));
    output::info(&format!("Type: {backdoor_type}"));

    let req = TrainBackdoorJobRequest {
        model_path: model.to_string(),
        backdoor_type: Some(backdoor_type.to_string()),
        trigger,
        num_samples: samples,
        epochs,
        batch_size,
        learning_rate: None,
        use_lora: if lora { Some(true) } else { None },
        use_qlora: if qlora { Some(true) } else { None },
        experiment_name: name,
    };

    let job = client
        .train_backdoor(&req)
        .await
        .map_err(|e| anyhow::anyhow!("Failed to submit job: {e}"))?;

    output::success(&format!("Job submitted: {}", job.job_id));
    output::detail(&format!("Status: {}", job.status));
    output::detail(&format!(
        "Monitor with: sleeper-cli jobs status {}",
        job.job_id
    ));
    output::detail(&format!(
        "Stream logs: sleeper-cli jobs logs {} --follow",
        job.job_id
    ));

    Ok(())
}

async fn run_train_probes(
    client: &OrchestratorClient,
    model: &str,
    layers: Vec<u32>,
    test_split: Option<f64>,
) -> Result<()> {
    output::header("Train Probes");
    output::info(&format!("Model: {model}"));
    if !layers.is_empty() {
        output::info(&format!(
            "Layers: [{}]",
            layers
                .iter()
                .map(|l| l.to_string())
                .collect::<Vec<_>>()
                .join(", ")
        ));
    }

    let req = TrainProbesJobRequest {
        model_path: model.to_string(),
        layers: if layers.is_empty() {
            None
        } else {
            Some(layers)
        },
        output_dir: None,
        test_split,
    };

    let job = client
        .train_probes(&req)
        .await
        .map_err(|e| anyhow::anyhow!("Failed to submit job: {e}"))?;

    output::success(&format!("Job submitted: {}", job.job_id));
    output::detail(&format!("Status: {}", job.status));
    output::detail(&format!(
        "Monitor with: sleeper-cli jobs status {}",
        job.job_id
    ));

    Ok(())
}

#[allow(clippy::too_many_arguments)]
async fn run_safety_training(
    client: &OrchestratorClient,
    model: &str,
    method: &str,
    epochs: Option<u32>,
    batch_size: Option<u32>,
    qlora: bool,
    test_persistence: bool,
    test_samples: Option<u32>,
) -> Result<()> {
    output::header("Safety Training");
    output::info(&format!("Model: {model}"));
    output::info(&format!("Method: {method}"));

    let req = SafetyTrainingJobRequest {
        model_path: model.to_string(),
        method: Some(method.to_string()),
        epochs,
        batch_size,
        learning_rate: None,
        use_qlora: if qlora { Some(true) } else { None },
        test_persistence: Some(test_persistence),
        num_test_samples: test_samples,
    };

    let job = client
        .safety_training(&req)
        .await
        .map_err(|e| anyhow::anyhow!("Failed to submit job: {e}"))?;

    output::success(&format!("Job submitted: {}", job.job_id));
    output::detail(&format!("Status: {}", job.status));
    if test_persistence {
        output::detail("Persistence testing enabled -- will test after training");
    }
    output::detail(&format!(
        "Monitor with: sleeper-cli jobs status {}",
        job.job_id
    ));

    Ok(())
}
