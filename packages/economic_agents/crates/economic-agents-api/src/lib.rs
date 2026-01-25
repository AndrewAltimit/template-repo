//! REST API clients and services for economic agents.
//!
//! This crate provides HTTP-based implementations of the core interfaces
//! for production use with real backends, as well as Axum-based services
//! that serve the mock backends over HTTP.
//!
//! # HTTP Clients
//!
//! The clients implement the core interface traits (`Wallet`, `Marketplace`, `Compute`)
//! using HTTP requests to connect to backend API services:
//!
//! - [`WalletApiClient`] - HTTP client for wallet operations
//! - [`MarketplaceApiClient`] - HTTP client for marketplace operations
//! - [`ComputeApiClient`] - HTTP client for compute operations
//!
//! # Axum Services
//!
//! The services provide HTTP endpoints backed by mock implementations:
//!
//! - Wallet service (default port 8001)
//! - Compute service (default port 8002)
//! - Marketplace service (default port 8003)
//!
//! # Example
//!
//! ```rust,ignore
//! use economic_agents_api::{ApiClientConfig, WalletApiClient};
//! use economic_agents_interfaces::Wallet;
//!
//! let config = ApiClientConfig::new("http://localhost:8001")
//!     .with_api_key("my-api-key");
//! let wallet = WalletApiClient::new(config)?;
//! let balance = wallet.get_balance().await?;
//! ```

pub mod clients;
pub mod config;
pub mod middleware;
pub mod models;
pub mod services;

// Re-export main types for convenience
pub use clients::{
    ApiClientConfig, ApiClientFactory, ApiClients, ComputeApiClient, MarketplaceApiClient,
    WalletApiClient,
};
pub use config::{ApiEndpointConfig, BackendMode};
pub use middleware::{AuthConfig, RateLimitConfig, RateLimitState};
pub use models::*;
pub use services::{ServiceBuilder, ServiceBundle, ServiceConfig};
