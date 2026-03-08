use serde::{Deserialize, Serialize};

/// Health check response from the API.
#[derive(Debug, Deserialize)]
pub struct HealthResponse {
    pub status: String,
    #[serde(default)]
    pub detector_initialized: bool,
}

/// System status response from the /status endpoint.
#[derive(Debug, Deserialize)]
pub struct StatusResponse {
    /// Whether the detector has been initialized.
    #[serde(default)]
    pub initialized: bool,
    /// Name of the loaded model, if any.
    #[serde(default)]
    pub model: Option<String>,
    /// Alias used by the `status` command display.
    #[serde(default)]
    pub model_loaded: bool,
    /// Alias used by the `status` command display.
    #[serde(default)]
    pub model_name: Option<String>,
    /// Whether the detector is in CPU mode.
    #[serde(default)]
    pub cpu_mode: Option<bool>,
    /// Whether GPU is available.
    #[serde(default)]
    pub gpu_available: Option<bool>,
    /// Number of configured probe layers.
    #[serde(default)]
    pub layers_configured: Option<u32>,
    /// Whether probes have been trained.
    #[serde(default)]
    pub has_trained_probes: Option<bool>,
    /// Whether detector directions have been computed.
    #[serde(default)]
    pub has_detector_directions: Option<bool>,
    /// Additional fields for forward compatibility.
    #[serde(flatten)]
    pub extra: serde_json::Value,
}

impl StatusResponse {
    /// The effective model name (checks both field variants).
    pub fn effective_model(&self) -> Option<&str> {
        self.model
            .as_deref()
            .or(self.model_name.as_deref())
            .filter(|s| !s.is_empty())
    }

    /// Whether a model is effectively loaded (checks both field variants).
    pub fn is_model_loaded(&self) -> bool {
        self.initialized || self.model_loaded || self.effective_model().is_some()
    }
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
