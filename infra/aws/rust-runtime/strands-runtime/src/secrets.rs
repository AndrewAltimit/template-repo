//! AWS Secrets Manager integration for credential management.
//!
//! This module provides functionality to fetch AWS credentials from
//! Secrets Manager at runtime, enabling secure credential management
//! without hardcoding secrets in configuration.

use aws_sdk_secretsmanager::Client as SecretsManagerClient;
use serde::Deserialize;
use std::env;
use tracing::info;

/// Credentials retrieved from Secrets Manager.
#[derive(Debug, Deserialize)]
pub struct BedrockCredentials {
    #[serde(rename = "AWS_ACCESS_KEY_ID")]
    pub access_key_id: String,
    #[serde(rename = "AWS_SECRET_ACCESS_KEY")]
    pub secret_access_key: String,
}

/// Error types for secrets operations.
#[derive(Debug, thiserror::Error)]
pub enum SecretsError {
    #[error("Failed to get secret: {0}")]
    GetSecretError(String),
    #[error("Secret string is empty")]
    EmptySecret,
    #[error("Failed to parse secret: {0}")]
    ParseError(String),
}

/// Fetch Bedrock credentials from Secrets Manager.
///
/// If `BEDROCK_CREDENTIALS_SECRET` environment variable is set, this function
/// will fetch the credentials from the specified secret. Otherwise, it returns None.
///
/// The secret should be a JSON object with `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` keys.
pub async fn fetch_bedrock_credentials() -> Result<Option<BedrockCredentials>, SecretsError> {
    let secret_name = match env::var("BEDROCK_CREDENTIALS_SECRET") {
        Ok(name) if !name.is_empty() => name,
        _ => {
            info!("BEDROCK_CREDENTIALS_SECRET not set, using environment credentials");
            return Ok(None);
        }
    };

    info!(secret_name = %secret_name, "Fetching Bedrock credentials from Secrets Manager");

    // Load AWS config (will use credentials from environment)
    let config = aws_config::load_defaults(aws_config::BehaviorVersion::latest()).await;
    let client = SecretsManagerClient::new(&config);

    // Fetch the secret
    let response = client
        .get_secret_value()
        .secret_id(&secret_name)
        .send()
        .await
        .map_err(|e| SecretsError::GetSecretError(e.to_string()))?;

    let secret_string = response.secret_string().ok_or(SecretsError::EmptySecret)?;

    // Parse the secret JSON
    let credentials: BedrockCredentials =
        serde_json::from_str(secret_string).map_err(|e| SecretsError::ParseError(e.to_string()))?;

    info!("Successfully retrieved Bedrock credentials from Secrets Manager");
    Ok(Some(credentials))
}

/// Apply credentials from Secrets Manager to the environment.
///
/// This function fetches credentials from Secrets Manager and sets them
/// as environment variables so they can be picked up by the AWS SDK.
pub async fn apply_credentials_from_secrets() -> Result<(), SecretsError> {
    if let Some(credentials) = fetch_bedrock_credentials().await? {
        // Set environment variables for AWS SDK
        env::set_var("AWS_ACCESS_KEY_ID", &credentials.access_key_id);
        env::set_var("AWS_SECRET_ACCESS_KEY", &credentials.secret_access_key);
        info!("Applied credentials from Secrets Manager to environment");
    }
    Ok(())
}
