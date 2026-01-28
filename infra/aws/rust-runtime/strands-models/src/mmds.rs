//! MMDS (MicroVM Metadata Service) credentials provider for Firecracker/AgentCore.
//!
//! AgentCore runs containers in Firecracker microVMs which use MMDS V1 for credentials.
//! The standard AWS SDK only supports IMDSv2 (which requires PUT token requests),
//! but MMDS V1 uses simple GET requests without tokens.

use aws_credential_types::{
    provider::{self, future, ProvideCredentials},
    Credentials,
};
use std::time::{Duration, SystemTime};
use tracing::{debug, warn};

/// MMDS endpoint address (same as IMDS)
const MMDS_ENDPOINT: &str = "http://169.254.169.254";

/// Credentials response from MMDS
#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "PascalCase")]
struct MmdsCredentialsResponse {
    access_key_id: String,
    secret_access_key: String,
    token: String,
    expiration: String,
    // Code and Type fields are also present but not needed
}

/// MMDS V1 credentials provider for Firecracker/AgentCore environments.
///
/// This provider fetches credentials from the MMDS endpoint using simple GET requests
/// (MMDS V1 style) without the token-based authentication required by IMDSv2.
#[derive(Debug, Clone)]
pub struct MmdsCredentialsProvider {
    client: reqwest::Client,
}

impl MmdsCredentialsProvider {
    /// Create a new MMDS credentials provider.
    pub fn new() -> Self {
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .expect("Failed to create HTTP client");

        Self { client }
    }

    /// Fetch credentials from MMDS.
    async fn fetch_credentials(&self) -> provider::Result {
        // Step 1: Get the IAM role name
        let role_url = format!(
            "{}/latest/meta-data/iam/security-credentials/",
            MMDS_ENDPOINT
        );

        debug!(url = %role_url, "Fetching IAM role name from MMDS");

        let role_response = self
            .client
            .get(&role_url)
            .send()
            .await
            .map_err(|e| {
                provider::error::CredentialsError::provider_error(format!(
                    "Failed to fetch role name from MMDS: {}",
                    e
                ))
            })?;

        if !role_response.status().is_success() {
            return Err(provider::error::CredentialsError::provider_error(format!(
                "MMDS role request failed with status: {}",
                role_response.status()
            )));
        }

        let role_name = role_response.text().await.map_err(|e| {
            provider::error::CredentialsError::provider_error(format!(
                "Failed to read role name: {}",
                e
            ))
        })?;

        let role_name = role_name.trim();
        debug!(role = %role_name, "Got IAM role name from MMDS");

        // Step 2: Get the credentials for this role
        let creds_url = format!(
            "{}/latest/meta-data/iam/security-credentials/{}",
            MMDS_ENDPOINT, role_name
        );

        debug!(url = %creds_url, "Fetching credentials from MMDS");

        let creds_response = self
            .client
            .get(&creds_url)
            .send()
            .await
            .map_err(|e| {
                provider::error::CredentialsError::provider_error(format!(
                    "Failed to fetch credentials from MMDS: {}",
                    e
                ))
            })?;

        if !creds_response.status().is_success() {
            return Err(provider::error::CredentialsError::provider_error(format!(
                "MMDS credentials request failed with status: {}",
                creds_response.status()
            )));
        }

        let creds: MmdsCredentialsResponse = creds_response.json().await.map_err(|e| {
            provider::error::CredentialsError::provider_error(format!(
                "Failed to parse credentials JSON: {}",
                e
            ))
        })?;

        // Parse expiration time
        let expiry = chrono::DateTime::parse_from_rfc3339(&creds.expiration)
            .map(|dt| SystemTime::UNIX_EPOCH + Duration::from_secs(dt.timestamp() as u64))
            .ok();

        debug!(
            access_key_id = %creds.access_key_id,
            expiration = %creds.expiration,
            "Got credentials from MMDS"
        );

        Ok(Credentials::new(
            creds.access_key_id,
            creds.secret_access_key,
            Some(creds.token),
            expiry,
            "MmdsCredentialsProvider",
        ))
    }
}

impl Default for MmdsCredentialsProvider {
    fn default() -> Self {
        Self::new()
    }
}

impl ProvideCredentials for MmdsCredentialsProvider {
    fn provide_credentials<'a>(&'a self) -> future::ProvideCredentials<'a>
    where
        Self: 'a,
    {
        future::ProvideCredentials::new(self.fetch_credentials())
    }
}

/// Check if we're running in an MMDS environment (Firecracker/AgentCore).
///
/// This checks if the MMDS endpoint is reachable with a simple GET request.
pub async fn is_mmds_available() -> bool {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .build()
        .ok();

    if let Some(client) = client {
        // Try to reach the MMDS endpoint
        let result = client
            .get(format!("{}/latest/meta-data/", MMDS_ENDPOINT))
            .send()
            .await;

        match result {
            Ok(response) => {
                let available = response.status().is_success();
                debug!(available = %available, "MMDS availability check");
                available
            }
            Err(e) => {
                debug!(error = %e, "MMDS not available");
                false
            }
        }
    } else {
        warn!("Failed to create HTTP client for MMDS check");
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_provider_creation() {
        let provider = MmdsCredentialsProvider::new();
        // Just verify it can be created
        assert!(format!("{:?}", provider).contains("MmdsCredentialsProvider"));
    }
}
