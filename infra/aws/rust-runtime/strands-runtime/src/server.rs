//! HTTP server implementation.

use std::net::SocketAddr;
use std::sync::Arc;

use axum::{
    extract::Request,
    middleware::{self, Next},
    response::Response,
    routing::{get, post},
    Router,
};
use strands_agent::{AgentBuilder, AgentConfig, InferenceConfig};
use strands_core::Result;
use strands_models::BedrockModel;
use strands_session::SessionManager;
use tower_http::trace::TraceLayer;
use tracing::{info, instrument};

use crate::config::RuntimeConfig;
use crate::handlers::{health_check, invoke, AppState};
use crate::secrets;
use crate::telemetry;

/// Middleware to log raw request details before processing.
async fn log_request(request: Request, next: Next) -> Response {
    let method = request.method().clone();
    let uri = request.uri().clone();
    let headers = request.headers().clone();

    info!(
        method = %method,
        uri = %uri,
        "Incoming request"
    );

    // Log all headers
    for (name, value) in headers.iter() {
        let value_str = value.to_str().unwrap_or("(binary)");
        let display_value = if name.as_str().to_lowercase().contains("auth")
            || name.as_str().to_lowercase().contains("token")
            || name.as_str().to_lowercase().contains("secret")
            || name.as_str().to_lowercase().contains("key")
        {
            format!("(set, {} chars)", value_str.len())
        } else {
            value_str.to_string()
        };
        info!(header = %name, value = %display_value, "Request header");
    }

    next.run(request).await
}

/// HTTP server for the Strands runtime.
pub struct Server {
    config: RuntimeConfig,
}

impl Server {
    /// Create a new server with the given configuration.
    pub fn new(config: RuntimeConfig) -> Self {
        Self { config }
    }

    /// Create a server with configuration from environment.
    pub fn from_env() -> Self {
        Self::new(RuntimeConfig::from_env())
    }

    /// Build and run the server.
    #[instrument(skip(self))]
    pub async fn run(self) -> Result<()> {
        // Initialize telemetry
        telemetry::init(&self.config)?;

        info!(
            model_id = %self.config.model_id,
            region = %self.config.region,
            port = self.config.port,
            "Starting Strands runtime"
        );

        // Load credentials from Secrets Manager if configured
        if let Err(e) = secrets::apply_credentials_from_secrets().await {
            tracing::warn!(error = %e, "Failed to load credentials from Secrets Manager, using environment");
        }

        // Debug: Log AWS credential-related environment variables
        let cred_vars = [
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
            "AWS_CONTAINER_CREDENTIALS_FULL_URI",
            "AWS_WEB_IDENTITY_TOKEN_FILE",
            "AWS_ROLE_ARN",
            "AWS_REGION",
            "AWS_DEFAULT_REGION",
        ];
        for var in &cred_vars {
            let value = std::env::var(var).unwrap_or_else(|_| "(not set)".to_string());
            let display_value = if var.contains("KEY") || var.contains("SECRET") || var.contains("TOKEN") {
                if value == "(not set)" { "(not set)".to_string() } else { "(set, hidden)".to_string() }
            } else {
                value
            };
            info!(env_var = %var, value = %display_value, "Credential env check");
        }

        // Create the Bedrock model
        let model = BedrockModel::new(&self.config.model_id, &self.config.region).await;

        // Build the agent configuration
        let agent_config = AgentConfig {
            max_iterations: self.config.max_iterations,
            inference_config: InferenceConfig {
                max_tokens: Some(self.config.max_tokens),
                ..Default::default()
            },
            ..Default::default()
        };

        // Build the agent
        let mut builder = AgentBuilder::new().model(model).config(agent_config);

        if let Some(system_prompt) = &self.config.system_prompt {
            builder = builder.system_prompt(system_prompt.clone());
        }

        let agent = builder.build()?;

        // Create session manager
        let session_manager = SessionManager::new();

        // Create app state
        let state = Arc::new(AppState {
            agent,
            session_manager,
        });

        // Build router with request logging middleware
        let app = Router::new()
            .route("/ping", get(health_check))
            .route("/invocations", post(invoke))
            .with_state(state)
            .layer(middleware::from_fn(log_request))
            .layer(TraceLayer::new_for_http());

        // Bind and serve
        let addr = SocketAddr::from(([0, 0, 0, 0], self.config.port));
        let listener = tokio::net::TcpListener::bind(addr)
            .await
            .map_err(|e| strands_core::StrandsError::config(format!("Failed to bind to {}: {}", addr, e)))?;

        info!(address = %addr, "Server listening");

        axum::serve(listener, app.into_make_service())
            .await
            .map_err(|e| strands_core::StrandsError::config(format!("Server error: {}", e)))?;

        Ok(())
    }

    /// Build the router without running (for testing).
    pub async fn build_router(self) -> Result<Router> {
        // Create the Bedrock model
        let model = BedrockModel::new(&self.config.model_id, &self.config.region).await;

        // Build the agent configuration
        let agent_config = AgentConfig {
            max_iterations: self.config.max_iterations,
            inference_config: InferenceConfig {
                max_tokens: Some(self.config.max_tokens),
                ..Default::default()
            },
            ..Default::default()
        };

        let agent = AgentBuilder::new()
            .model(model)
            .config(agent_config)
            .build()?;

        let session_manager = SessionManager::new();

        let state = Arc::new(AppState {
            agent,
            session_manager,
        });

        let app = Router::new()
            .route("/ping", get(health_check))
            .route("/invocations", post(invoke))
            .with_state(state);

        Ok(app)
    }
}
