//! Web dashboard backend (Axum).
//!
//! This crate provides a REST API and WebSocket endpoints for monitoring
//! and controlling autonomous agents.
//!
//! # Features
//!
//! - **Health & Status**: Health check and dashboard status endpoints
//! - **Agent Management**: Create, start, stop, and delete agents
//! - **Real-time Updates**: WebSocket support for live event streaming
//! - **Metrics**: Prometheus-compatible metrics endpoint
//! - **Event Log**: Query and filter system events
//! - **Decision Log**: Review agent decisions and outcomes
//!
//! # Example
//!
//! ```rust,ignore
//! use std::sync::Arc;
//! use economic_agents_dashboard::{DashboardConfig, DashboardService};
//!
//! let config = DashboardConfig::default();
//! let service = DashboardService::new(config);
//! service.run().await?;
//! ```

pub mod models;
pub mod routes;
pub mod state;
pub mod websocket;

pub use models::*;
pub use routes::dashboard_router;
pub use state::{DashboardState, ManagedAgent};

use std::sync::Arc;
use axum::Router;
use tower_http::cors::{Any, CorsLayer};
use tower_http::trace::TraceLayer;
use tracing::info;

/// Dashboard service configuration.
#[derive(Debug, Clone)]
pub struct DashboardConfig {
    /// Port to listen on.
    pub port: u16,
    /// Host to bind to.
    pub host: String,
    /// Enable CORS.
    pub enable_cors: bool,
    /// Enable request tracing.
    pub enable_tracing: bool,
}

impl Default for DashboardConfig {
    fn default() -> Self {
        Self {
            port: 8080,
            host: "0.0.0.0".to_string(),
            enable_cors: true,
            enable_tracing: true,
        }
    }
}

/// Dashboard service builder and runner.
pub struct DashboardService {
    config: DashboardConfig,
    state: Arc<DashboardState>,
}

impl DashboardService {
    /// Create a new dashboard service with custom state.
    pub fn new(config: DashboardConfig, state: Arc<DashboardState>) -> Self {
        Self { config, state }
    }

    /// Create a new dashboard service with default state.
    pub fn with_default_state(config: DashboardConfig) -> Self {
        Self {
            config,
            state: Arc::new(DashboardState::new()),
        }
    }

    /// Get a reference to the shared state.
    pub fn state(&self) -> Arc<DashboardState> {
        Arc::clone(&self.state)
    }

    /// Build the router without running the server.
    pub fn build_router(&self) -> Router {
        let mut router = dashboard_router(Arc::clone(&self.state));

        if self.config.enable_cors {
            router = router.layer(
                CorsLayer::new()
                    .allow_origin(Any)
                    .allow_methods(Any)
                    .allow_headers(Any),
            );
        }

        if self.config.enable_tracing {
            router = router.layer(TraceLayer::new_for_http());
        }

        router
    }

    /// Run the dashboard service.
    pub async fn run(self) -> std::io::Result<()> {
        let addr = format!("{}:{}", self.config.host, self.config.port);
        let router = self.build_router();

        info!("Starting dashboard on {}", addr);

        let listener = tokio::net::TcpListener::bind(&addr).await?;
        axum::serve(listener, router).await?;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_default() {
        let config = DashboardConfig::default();
        assert_eq!(config.port, 8080);
        assert_eq!(config.host, "0.0.0.0");
        assert!(config.enable_cors);
        assert!(config.enable_tracing);
    }

    #[test]
    fn test_service_creation() {
        let config = DashboardConfig {
            port: 9000,
            ..Default::default()
        };
        let service = DashboardService::with_default_state(config);
        assert_eq!(service.config.port, 9000);
    }

    #[test]
    fn test_service_with_state() {
        let config = DashboardConfig::default();
        let state = Arc::new(DashboardState::new());
        let service = DashboardService::new(config, Arc::clone(&state));
        assert!(Arc::ptr_eq(&service.state(), &state));
    }
}
