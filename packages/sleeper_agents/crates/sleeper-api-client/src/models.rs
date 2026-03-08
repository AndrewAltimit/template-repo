use serde::{Deserialize, Serialize};

/// Health check response from the API.
#[derive(Debug, Deserialize)]
pub struct HealthResponse {
    pub status: String,
}

/// System status response from the API.
#[derive(Debug, Deserialize)]
pub struct StatusResponse {
    pub status: String,
    #[serde(default)]
    pub model_loaded: bool,
    #[serde(default)]
    pub model_name: Option<String>,
    #[serde(default)]
    pub gpu_available: Option<bool>,
    /// Additional status fields vary by server version.
    #[serde(flatten)]
    pub extra: serde_json::Value,
}

/// Request to initialize the detector with a model.
#[derive(Debug, Serialize)]
pub struct InitRequest {
    pub model_name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cpu_mode: Option<bool>,
}

/// Request to detect backdoors in text.
#[derive(Debug, Serialize)]
pub struct DetectRequest {
    pub text: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub use_ensemble: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub run_interventions: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub check_attention: Option<bool>,
}

/// Request for layer sweep.
#[derive(Debug, Serialize)]
pub struct SweepRequest {
    pub n_samples: u32,
}

/// Request for honeypot testing.
#[derive(Debug, Serialize)]
pub struct HoneypotRequest {
    pub suspected_goal: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub n_honeypots: Option<u32>,
}

/// Request to train a backdoored model.
#[derive(Debug, Serialize)]
pub struct TrainRequest {
    pub backdoor_type: String,
    pub mechanism: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub n_samples: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trigger: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub epochs: Option<u32>,
}
