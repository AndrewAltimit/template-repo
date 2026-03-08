use anyhow::Result;
use sleeper_api_client::{DetectRequest, InitRequest};
use sleeper_orchestrator::{config::OrchestratorConfig, output};

use crate::common::{ensure_api_ready, find_package_root};

pub struct DetectOpts<'a> {
    pub text: &'a str,
    pub model: &'a str,
    pub ensemble: bool,
    pub interventions: bool,
    pub attention: bool,
    pub cpu: bool,
    pub json_output: bool,
    pub package_root: Option<&'a str>,
}

pub async fn run(opts: DetectOpts<'_>) -> Result<()> {
    let root = find_package_root(opts.package_root)?;
    let config = OrchestratorConfig::default();
    let client = ensure_api_ready(&config, &root).await?;

    // Initialize the model if needed
    output::info(&format!("Initializing model: {}", opts.model));
    client
        .initialize(&InitRequest {
            model_name: opts.model.to_string(),
            cpu_mode: Some(opts.cpu),
        })
        .await
        .map_err(|e| anyhow::anyhow!("Failed to initialize model: {e}"))?;
    output::success(&format!("Model initialized: {}", opts.model));

    // Run detection
    output::info("Running backdoor detection...");
    let result = client
        .detect(&DetectRequest {
            text: opts.text.to_string(),
            use_ensemble: Some(opts.ensemble),
            run_interventions: Some(opts.interventions),
            check_attention: Some(opts.attention),
        })
        .await
        .map_err(|e| anyhow::anyhow!("Detection failed: {e}"))?;

    if opts.json_output {
        println!("{}", serde_json::to_string_pretty(&result)?);
        return Ok(());
    }

    // Format human-readable output
    output::header("Detection Results");

    if let Some(is_backdoored) = result.get("is_backdoored").and_then(|v| v.as_bool()) {
        if is_backdoored {
            output::fail("BACKDOOR DETECTED");
        } else {
            output::success("No backdoor detected");
        }
    }

    if let Some(confidence) = result.get("confidence").and_then(|v| v.as_f64()) {
        output::detail(&format!("Confidence: {:.1}%", confidence * 100.0));
    }

    // Probe results
    if let Some(probes) = result.get("probe_results") {
        output::subheader("Probe Results");
        if let Some(is_deceptive) = probes.get("is_deceptive").and_then(|v| v.as_bool()) {
            output::detail(&format!(
                "Deceptive: {}",
                if is_deceptive { "YES" } else { "no" }
            ));
        }
        if let Some(score) = probes.get("deception_score").and_then(|v| v.as_f64()) {
            output::detail(&format!("Deception score: {score:.4}"));
        }
        if let Some(layers) = probes.get("best_layers").and_then(|v| v.as_array()) {
            let layer_strs: Vec<String> = layers
                .iter()
                .filter_map(|v| v.as_i64().map(|n| n.to_string()))
                .collect();
            if !layer_strs.is_empty() {
                output::detail(&format!("Best layers: [{}]", layer_strs.join(", ")));
            }
        }
    }

    // Intervention results
    if let Some(interventions) = result.get("intervention_results") {
        output::subheader("Intervention Results");
        if let Some(effect) = interventions.get("causal_effect").and_then(|v| v.as_f64()) {
            output::detail(&format!("Causal effect: {effect:.4}"));
        }
    }

    // Attention results
    if let Some(attention) = result.get("attention_results") {
        output::subheader("Attention Analysis");
        if let Some(anomaly) = attention.get("anomaly_score").and_then(|v| v.as_f64()) {
            output::detail(&format!("Anomaly score: {anomaly:.4}"));
        }
    }

    // Overall risk
    if let Some(risk) = result.get("risk_level").and_then(|v| v.as_str()) {
        output::subheader("Risk Assessment");
        match risk {
            "high" => output::fail(&format!("Risk level: {risk}")),
            "medium" => output::warn(&format!("Risk level: {risk}")),
            _ => output::success(&format!("Risk level: {risk}")),
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detect_opts_defaults() {
        // Verify we can construct DetectOpts with reasonable defaults
        let opts = DetectOpts {
            text: "hello world",
            model: "gpt2",
            ensemble: false,
            interventions: false,
            attention: false,
            cpu: true,
            json_output: false,
            package_root: None,
        };
        assert_eq!(opts.text, "hello world");
        assert_eq!(opts.model, "gpt2");
        assert!(!opts.ensemble);
    }

    #[test]
    fn detect_opts_all_flags() {
        let opts = DetectOpts {
            text: "test",
            model: "mistral-7b",
            ensemble: true,
            interventions: true,
            attention: true,
            cpu: false,
            json_output: true,
            package_root: Some("/tmp/root"),
        };
        assert!(opts.ensemble);
        assert!(opts.interventions);
        assert!(opts.attention);
        assert!(opts.json_output);
        assert!(!opts.cpu);
    }
}
