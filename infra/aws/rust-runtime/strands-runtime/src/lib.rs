//! Strands Runtime - HTTP runtime for AgentCore protocol
//!
//! This crate provides an HTTP server implementing the AWS AgentCore
//! protocol for running Strands agents in production.
//!
//! ## Endpoints
//!
//! - `POST /invocations` - Invoke the agent with a prompt
//! - `GET /ping` - Health check endpoint
//!
//! ## Configuration
//!
//! Configuration is read from environment variables:
//! - `PORT` - Server port (default: 8080)
//! - `MODEL_ID` - Bedrock model/inference profile ID (default: us.anthropic.claude-sonnet-4-20250514-v1:0)
//! - `AWS_REGION` - AWS region for Bedrock
//! - `OTEL_EXPORTER_OTLP_ENDPOINT` - OpenTelemetry endpoint (optional)
//! - `OTEL_SERVICE_NAME` - Service name for tracing (default: strands-runtime)
//!
//! ## Secrets Management
//!
//! For secure credential management, you can store Bedrock credentials in AWS Secrets Manager:
//! - `BEDROCK_CREDENTIALS_SECRET` - Name of the secret containing credentials (optional)
//!
//! The secret should be a JSON object with `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` keys.
//! If not set, credentials are read directly from environment variables.

pub mod config;
pub mod handlers;
pub mod secrets;
pub mod server;
pub mod telemetry;

pub use config::RuntimeConfig;
pub use secrets::{apply_credentials_from_secrets, fetch_bedrock_credentials};
pub use server::Server;
