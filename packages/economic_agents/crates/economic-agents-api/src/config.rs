//! API configuration.

use serde::{Deserialize, Serialize};

/// Backend mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum BackendMode {
    /// Use mock implementations (in-memory).
    #[default]
    Mock,
    /// Use API-based implementations (HTTP clients).
    Api,
}

/// API endpoint configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiEndpointConfig {
    /// Wallet service URL.
    pub wallet_url: String,
    /// Compute service URL.
    pub compute_url: String,
    /// Marketplace service URL.
    pub marketplace_url: String,
    /// Investor portal URL.
    pub investor_url: String,
}

impl Default for ApiEndpointConfig {
    fn default() -> Self {
        Self {
            wallet_url: "http://localhost:8001".to_string(),
            compute_url: "http://localhost:8002".to_string(),
            marketplace_url: "http://localhost:8003".to_string(),
            investor_url: "http://localhost:8004".to_string(),
        }
    }
}
