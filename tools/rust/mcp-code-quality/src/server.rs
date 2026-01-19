//! MCP HTTP server implementation

use std::net::SocketAddr;
use std::sync::Arc;

use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tower_http::cors::{Any, CorsLayer};
use tracing::info;

use crate::config::Config;
use crate::error::{ErrorResponse, ToolError};
use crate::security::{AuditLogger, PathValidator, RateLimiter};
use crate::tools::{self, Language, Linter};

/// Shared application state
#[derive(Clone)]
pub struct AppState {
    pub config: Arc<Config>,
    pub path_validator: Arc<PathValidator>,
    pub rate_limiter: Arc<RateLimiter>,
    pub audit_logger: Arc<AuditLogger>,
}

impl AppState {
    pub fn new(config: Config) -> Self {
        let path_validator = PathValidator::new(config.allowed_paths.clone());
        let rate_limiter = RateLimiter::new(config.rate_limit_enabled);
        let audit_logger = AuditLogger::new(config.audit_log_path.clone());

        Self {
            config: Arc::new(config),
            path_validator: Arc::new(path_validator),
            rate_limiter: Arc::new(rate_limiter),
            audit_logger: Arc::new(audit_logger),
        }
    }
}

/// MCP tool call request
#[derive(Debug, Deserialize)]
pub struct ToolCallRequest {
    pub name: String,
    pub arguments: Value,
}

/// MCP tool call response
#[derive(Debug, Serialize)]
pub struct ToolCallResponse {
    pub content: Vec<ToolContent>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_error: Option<bool>,
}

#[derive(Debug, Serialize)]
pub struct ToolContent {
    #[serde(rename = "type")]
    pub content_type: String,
    pub text: String,
}

impl ToolCallResponse {
    pub fn success(result: Value) -> Self {
        Self {
            content: vec![ToolContent {
                content_type: "text".to_string(),
                text: serde_json::to_string_pretty(&result).unwrap_or_default(),
            }],
            is_error: None,
        }
    }

    pub fn error(err: ErrorResponse) -> Self {
        Self {
            content: vec![ToolContent {
                content_type: "text".to_string(),
                text: serde_json::to_string_pretty(&err).unwrap_or_default(),
            }],
            is_error: Some(true),
        }
    }
}

/// Create the router with all MCP endpoints
pub fn create_router(state: AppState) -> Router {
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    Router::new()
        .route("/health", get(health_check))
        .route("/tools/list", get(list_tools))
        .route("/tools/call", post(call_tool))
        // Legacy endpoints for compatibility
        .route("/format_check", post(format_check_handler))
        .route("/lint", post(lint_handler))
        .route("/autoformat", post(autoformat_handler))
        .route("/run_tests", post(run_tests_handler))
        .route("/type_check", post(type_check_handler))
        .route("/security_scan", post(security_scan_handler))
        .route("/audit_dependencies", post(audit_dependencies_handler))
        .route("/check_markdown_links", post(check_markdown_links_handler))
        .route("/get_status", get(get_status_handler))
        .route("/get_audit_log", post(get_audit_log_handler))
        .with_state(state)
        .layer(cors)
}

/// Start the HTTP server
pub async fn start_server(config: Config) -> Result<(), Box<dyn std::error::Error>> {
    let addr: SocketAddr = format!("{}:{}", config.host, config.port).parse()?;
    let state = AppState::new(config);
    let router = create_router(state);

    info!("Starting MCP Code Quality server on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, router).await?;

    Ok(())
}

// ============================================================================
// Handler implementations
// ============================================================================

async fn health_check() -> Json<Value> {
    Json(json!({ "status": "healthy" }))
}

async fn list_tools() -> Json<Value> {
    Json(json!({
        "tools": [
            {
                "name": "format_check",
                "description": "Check code formatting without modifying files",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": { "type": "string", "description": "Path to file or directory" },
                        "language": { "type": "string", "enum": ["python", "javascript", "typescript", "go", "rust"], "default": "python" }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "lint",
                "description": "Run code linting with optional configuration",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": { "type": "string", "description": "Path to file or directory" },
                        "linter": { "type": "string", "enum": ["flake8", "ruff", "eslint", "golint", "clippy"], "default": "ruff" },
                        "config": { "type": "string", "description": "Path to linter config file" }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "autoformat",
                "description": "Automatically format code files",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": { "type": "string", "description": "Path to file or directory" },
                        "language": { "type": "string", "enum": ["python", "javascript", "typescript", "go", "rust"], "default": "python" }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "run_tests",
                "description": "Run pytest tests with controlled parameters",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": { "type": "string", "default": "tests/" },
                        "verbose": { "type": "boolean", "default": false },
                        "coverage": { "type": "boolean", "default": false },
                        "fail_fast": { "type": "boolean", "default": false },
                        "pattern": { "type": "string" },
                        "markers": { "type": "string" }
                    }
                }
            },
            {
                "name": "type_check",
                "description": "Run mypy type checking",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": { "type": "string", "description": "Path to check" },
                        "strict": { "type": "boolean", "default": false },
                        "config": { "type": "string" }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "security_scan",
                "description": "Run security analysis with bandit",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": { "type": "string" },
                        "severity": { "type": "string", "enum": ["low", "medium", "high"], "default": "low" },
                        "confidence": { "type": "string", "enum": ["low", "medium", "high"], "default": "low" }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "audit_dependencies",
                "description": "Check dependencies for known vulnerabilities",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "requirements_file": { "type": "string", "default": "requirements.txt" }
                    }
                }
            },
            {
                "name": "check_markdown_links",
                "description": "Check links in markdown files for validity",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": { "type": "string" },
                        "check_external": { "type": "boolean", "default": true },
                        "timeout": { "type": "integer", "default": 10 },
                        "concurrent_checks": { "type": "integer", "default": 10 },
                        "ignore_patterns": { "type": "array", "items": { "type": "string" } }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "get_status",
                "description": "Get server status and available tools",
                "inputSchema": { "type": "object", "properties": {} }
            },
            {
                "name": "get_audit_log",
                "description": "Get recent audit log entries",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": { "type": "integer", "default": 100 },
                        "operation": { "type": "string" }
                    }
                }
            }
        ]
    }))
}

async fn call_tool(
    State(state): State<AppState>,
    Json(request): Json<ToolCallRequest>,
) -> (StatusCode, Json<ToolCallResponse>) {
    match request.name.as_str() {
        "format_check" => {
            let req: tools::format::FormatCheckRequest =
                match serde_json::from_value(request.arguments) {
                    Ok(r) => r,
                    Err(e) => {
                        return (
                            StatusCode::BAD_REQUEST,
                            Json(ToolCallResponse::error(ErrorResponse::from(
                                ToolError::Internal(e.to_string()),
                            ))),
                        )
                    }
                };
            format_check_impl(state, req).await
        }
        "lint" => {
            let req: tools::lint::LintRequest = match serde_json::from_value(request.arguments) {
                Ok(r) => r,
                Err(e) => {
                    return (
                        StatusCode::BAD_REQUEST,
                        Json(ToolCallResponse::error(ErrorResponse::from(
                            ToolError::Internal(e.to_string()),
                        ))),
                    )
                }
            };
            lint_impl(state, req).await
        }
        "autoformat" => {
            let req: tools::format::AutoformatRequest =
                match serde_json::from_value(request.arguments) {
                    Ok(r) => r,
                    Err(e) => {
                        return (
                            StatusCode::BAD_REQUEST,
                            Json(ToolCallResponse::error(ErrorResponse::from(
                                ToolError::Internal(e.to_string()),
                            ))),
                        )
                    }
                };
            autoformat_impl(state, req).await
        }
        "run_tests" => {
            let req: tools::test::RunTestsRequest = match serde_json::from_value(request.arguments)
            {
                Ok(r) => r,
                Err(e) => {
                    return (
                        StatusCode::BAD_REQUEST,
                        Json(ToolCallResponse::error(ErrorResponse::from(
                            ToolError::Internal(e.to_string()),
                        ))),
                    )
                }
            };
            run_tests_impl(state, req).await
        }
        "type_check" => {
            let req: tools::lint::TypeCheckRequest =
                match serde_json::from_value(request.arguments) {
                    Ok(r) => r,
                    Err(e) => {
                        return (
                            StatusCode::BAD_REQUEST,
                            Json(ToolCallResponse::error(ErrorResponse::from(
                                ToolError::Internal(e.to_string()),
                            ))),
                        )
                    }
                };
            type_check_impl(state, req).await
        }
        "security_scan" => {
            let req: tools::lint::SecurityScanRequest =
                match serde_json::from_value(request.arguments) {
                    Ok(r) => r,
                    Err(e) => {
                        return (
                            StatusCode::BAD_REQUEST,
                            Json(ToolCallResponse::error(ErrorResponse::from(
                                ToolError::Internal(e.to_string()),
                            ))),
                        )
                    }
                };
            security_scan_impl(state, req).await
        }
        "audit_dependencies" => {
            let req: tools::test::AuditDependenciesRequest =
                match serde_json::from_value(request.arguments) {
                    Ok(r) => r,
                    Err(e) => {
                        return (
                            StatusCode::BAD_REQUEST,
                            Json(ToolCallResponse::error(ErrorResponse::from(
                                ToolError::Internal(e.to_string()),
                            ))),
                        )
                    }
                };
            audit_dependencies_impl(state, req).await
        }
        "check_markdown_links" => {
            let req: tools::test::CheckMarkdownLinksRequest =
                match serde_json::from_value(request.arguments) {
                    Ok(r) => r,
                    Err(e) => {
                        return (
                            StatusCode::BAD_REQUEST,
                            Json(ToolCallResponse::error(ErrorResponse::from(
                                ToolError::Internal(e.to_string()),
                            ))),
                        )
                    }
                };
            check_markdown_links_impl(state, req).await
        }
        "get_status" => get_status_impl(state).await,
        "get_audit_log" => {
            let req: tools::status::GetAuditLogRequest =
                match serde_json::from_value(request.arguments) {
                    Ok(r) => r,
                    Err(e) => {
                        return (
                            StatusCode::BAD_REQUEST,
                            Json(ToolCallResponse::error(ErrorResponse::from(
                                ToolError::Internal(e.to_string()),
                            ))),
                        )
                    }
                };
            get_audit_log_impl(state, req).await
        }
        _ => (
            StatusCode::NOT_FOUND,
            Json(ToolCallResponse::error(ErrorResponse::from(
                ToolError::ToolNotFound(request.name),
            ))),
        ),
    }
}

// ============================================================================
// Tool implementations with security checks
// ============================================================================

async fn format_check_impl(
    state: AppState,
    req: tools::format::FormatCheckRequest,
) -> (StatusCode, Json<ToolCallResponse>) {
    // Rate limit check
    if let Err(e) = state.rate_limiter.check("format_check").await {
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(ToolCallResponse::error(ErrorResponse::from(e))),
        );
    }

    // Path validation
    let path = match state.path_validator.validate(&req.path) {
        Ok(p) => p,
        Err(e) => {
            return (
                StatusCode::FORBIDDEN,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    };

    // Language parsing
    let language = match Language::from_str(&req.language) {
        Some(l) => l,
        None => {
            return (
                StatusCode::BAD_REQUEST,
                Json(ToolCallResponse::error(ErrorResponse::from(
                    ToolError::UnsupportedLanguage(req.language),
                ))),
            )
        }
    };

    // Execute
    match tools::format_check(&path, language, state.config.timeout).await {
        Ok(result) => {
            state.audit_logger.log(
                "format_check",
                Some(&req.path),
                result.formatted,
                result.to_json(),
            );
            (StatusCode::OK, Json(ToolCallResponse::success(result.to_json())))
        }
        Err(e) => {
            state.audit_logger.log("format_check", Some(&req.path), false, json!({"error": e.to_string()}));
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    }
}

async fn lint_impl(
    state: AppState,
    req: tools::lint::LintRequest,
) -> (StatusCode, Json<ToolCallResponse>) {
    if let Err(e) = state.rate_limiter.check("lint").await {
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(ToolCallResponse::error(ErrorResponse::from(e))),
        );
    }

    let path = match state.path_validator.validate(&req.path) {
        Ok(p) => p,
        Err(e) => {
            return (
                StatusCode::FORBIDDEN,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    };

    let linter = match Linter::from_str(&req.linter) {
        Some(l) => l,
        None => {
            return (
                StatusCode::BAD_REQUEST,
                Json(ToolCallResponse::error(ErrorResponse::from(
                    ToolError::ToolNotFound(req.linter),
                ))),
            )
        }
    };

    match tools::lint(&path, linter, req.config.as_deref(), state.config.timeout).await {
        Ok(result) => {
            state.audit_logger.log("lint", Some(&req.path), result.clean, result.to_json());
            (StatusCode::OK, Json(ToolCallResponse::success(result.to_json())))
        }
        Err(e) => {
            state.audit_logger.log("lint", Some(&req.path), false, json!({"error": e.to_string()}));
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    }
}

async fn autoformat_impl(
    state: AppState,
    req: tools::format::AutoformatRequest,
) -> (StatusCode, Json<ToolCallResponse>) {
    if let Err(e) = state.rate_limiter.check("autoformat").await {
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(ToolCallResponse::error(ErrorResponse::from(e))),
        );
    }

    let path = match state.path_validator.validate(&req.path) {
        Ok(p) => p,
        Err(e) => {
            return (
                StatusCode::FORBIDDEN,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    };

    let language = match Language::from_str(&req.language) {
        Some(l) => l,
        None => {
            return (
                StatusCode::BAD_REQUEST,
                Json(ToolCallResponse::error(ErrorResponse::from(
                    ToolError::UnsupportedLanguage(req.language),
                ))),
            )
        }
    };

    match tools::autoformat(&path, language, state.config.timeout).await {
        Ok(result) => {
            state.audit_logger.log("autoformat", Some(&req.path), result.success, result.to_json());
            (StatusCode::OK, Json(ToolCallResponse::success(result.to_json())))
        }
        Err(e) => {
            state.audit_logger.log("autoformat", Some(&req.path), false, json!({"error": e.to_string()}));
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    }
}

async fn run_tests_impl(
    state: AppState,
    req: tools::test::RunTestsRequest,
) -> (StatusCode, Json<ToolCallResponse>) {
    if let Err(e) = state.rate_limiter.check("run_tests").await {
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(ToolCallResponse::error(ErrorResponse::from(e))),
        );
    }

    let path = match state.path_validator.validate(&req.path) {
        Ok(p) => p,
        Err(e) => {
            return (
                StatusCode::FORBIDDEN,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    };

    match tools::run_tests(
        &path,
        req.verbose,
        req.coverage,
        req.fail_fast,
        req.pattern.as_deref(),
        req.markers.as_deref(),
        state.config.timeout,
    )
    .await
    {
        Ok(result) => {
            state.audit_logger.log("run_tests", Some(&req.path), result.passed, result.to_json());
            (StatusCode::OK, Json(ToolCallResponse::success(result.to_json())))
        }
        Err(e) => {
            state.audit_logger.log("run_tests", Some(&req.path), false, json!({"error": e.to_string()}));
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    }
}

async fn type_check_impl(
    state: AppState,
    req: tools::lint::TypeCheckRequest,
) -> (StatusCode, Json<ToolCallResponse>) {
    if let Err(e) = state.rate_limiter.check("type_check").await {
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(ToolCallResponse::error(ErrorResponse::from(e))),
        );
    }

    let path = match state.path_validator.validate(&req.path) {
        Ok(p) => p,
        Err(e) => {
            return (
                StatusCode::FORBIDDEN,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    };

    match tools::type_check(&path, req.strict, req.config.as_deref(), state.config.timeout).await {
        Ok(result) => {
            state.audit_logger.log("type_check", Some(&req.path), result.passed, result.to_json());
            (StatusCode::OK, Json(ToolCallResponse::success(result.to_json())))
        }
        Err(e) => {
            state.audit_logger.log("type_check", Some(&req.path), false, json!({"error": e.to_string()}));
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    }
}

async fn security_scan_impl(
    state: AppState,
    req: tools::lint::SecurityScanRequest,
) -> (StatusCode, Json<ToolCallResponse>) {
    if let Err(e) = state.rate_limiter.check("security_scan").await {
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(ToolCallResponse::error(ErrorResponse::from(e))),
        );
    }

    let path = match state.path_validator.validate(&req.path) {
        Ok(p) => p,
        Err(e) => {
            return (
                StatusCode::FORBIDDEN,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    };

    match tools::security_scan(&path, &req.severity, &req.confidence, state.config.timeout).await {
        Ok(result) => {
            state.audit_logger.log("security_scan", Some(&req.path), result.clean, result.to_json());
            (StatusCode::OK, Json(ToolCallResponse::success(result.to_json())))
        }
        Err(e) => {
            state.audit_logger.log("security_scan", Some(&req.path), false, json!({"error": e.to_string()}));
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    }
}

async fn audit_dependencies_impl(
    state: AppState,
    req: tools::test::AuditDependenciesRequest,
) -> (StatusCode, Json<ToolCallResponse>) {
    if let Err(e) = state.rate_limiter.check("audit_dependencies").await {
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(ToolCallResponse::error(ErrorResponse::from(e))),
        );
    }

    let path = match state.path_validator.validate(&req.requirements_file) {
        Ok(p) => p,
        Err(e) => {
            return (
                StatusCode::FORBIDDEN,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    };

    match tools::audit_dependencies(&path, state.config.timeout).await {
        Ok(result) => {
            state.audit_logger.log(
                "audit_dependencies",
                Some(&req.requirements_file),
                result.clean,
                result.to_json(),
            );
            (StatusCode::OK, Json(ToolCallResponse::success(result.to_json())))
        }
        Err(e) => {
            state.audit_logger.log(
                "audit_dependencies",
                Some(&req.requirements_file),
                false,
                json!({"error": e.to_string()}),
            );
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    }
}

async fn check_markdown_links_impl(
    state: AppState,
    req: tools::test::CheckMarkdownLinksRequest,
) -> (StatusCode, Json<ToolCallResponse>) {
    if let Err(e) = state.rate_limiter.check("check_markdown_links").await {
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(ToolCallResponse::error(ErrorResponse::from(e))),
        );
    }

    let path = match state.path_validator.validate(&req.path) {
        Ok(p) => p,
        Err(e) => {
            return (
                StatusCode::FORBIDDEN,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    };

    match tools::check_markdown_links(
        &path,
        req.check_external,
        req.timeout,
        req.concurrent_checks,
        &req.ignore_patterns,
        state.config.timeout,
    )
    .await
    {
        Ok(result) => {
            state.audit_logger.log(
                "check_markdown_links",
                Some(&req.path),
                result.all_valid,
                result.to_json(),
            );
            (StatusCode::OK, Json(ToolCallResponse::success(result.to_json())))
        }
        Err(e) => {
            state.audit_logger.log(
                "check_markdown_links",
                Some(&req.path),
                false,
                json!({"error": e.to_string()}),
            );
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ToolCallResponse::error(ErrorResponse::from(e))),
            )
        }
    }
}

async fn get_status_impl(state: AppState) -> (StatusCode, Json<ToolCallResponse>) {
    if let Err(e) = state.rate_limiter.check("get_status").await {
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(ToolCallResponse::error(ErrorResponse::from(e))),
        );
    }

    match tools::get_status(state.config.rate_limit_enabled).await {
        Ok(result) => (StatusCode::OK, Json(ToolCallResponse::success(result.to_json()))),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ToolCallResponse::error(ErrorResponse::from(e))),
        ),
    }
}

async fn get_audit_log_impl(
    state: AppState,
    req: tools::status::GetAuditLogRequest,
) -> (StatusCode, Json<ToolCallResponse>) {
    if let Err(e) = state.rate_limiter.check("get_audit_log").await {
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(ToolCallResponse::error(ErrorResponse::from(e))),
        );
    }

    match tools::get_audit_log(
        &state.config.audit_log_path,
        req.limit,
        req.operation.as_deref(),
    )
    .await
    {
        Ok(result) => (StatusCode::OK, Json(ToolCallResponse::success(result.to_json()))),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ToolCallResponse::error(ErrorResponse::from(e))),
        ),
    }
}

// ============================================================================
// Legacy endpoint handlers (delegate to impl functions)
// ============================================================================

async fn format_check_handler(
    State(state): State<AppState>,
    Json(req): Json<tools::format::FormatCheckRequest>,
) -> (StatusCode, Json<ToolCallResponse>) {
    format_check_impl(state, req).await
}

async fn lint_handler(
    State(state): State<AppState>,
    Json(req): Json<tools::lint::LintRequest>,
) -> (StatusCode, Json<ToolCallResponse>) {
    lint_impl(state, req).await
}

async fn autoformat_handler(
    State(state): State<AppState>,
    Json(req): Json<tools::format::AutoformatRequest>,
) -> (StatusCode, Json<ToolCallResponse>) {
    autoformat_impl(state, req).await
}

async fn run_tests_handler(
    State(state): State<AppState>,
    Json(req): Json<tools::test::RunTestsRequest>,
) -> (StatusCode, Json<ToolCallResponse>) {
    run_tests_impl(state, req).await
}

async fn type_check_handler(
    State(state): State<AppState>,
    Json(req): Json<tools::lint::TypeCheckRequest>,
) -> (StatusCode, Json<ToolCallResponse>) {
    type_check_impl(state, req).await
}

async fn security_scan_handler(
    State(state): State<AppState>,
    Json(req): Json<tools::lint::SecurityScanRequest>,
) -> (StatusCode, Json<ToolCallResponse>) {
    security_scan_impl(state, req).await
}

async fn audit_dependencies_handler(
    State(state): State<AppState>,
    Json(req): Json<tools::test::AuditDependenciesRequest>,
) -> (StatusCode, Json<ToolCallResponse>) {
    audit_dependencies_impl(state, req).await
}

async fn check_markdown_links_handler(
    State(state): State<AppState>,
    Json(req): Json<tools::test::CheckMarkdownLinksRequest>,
) -> (StatusCode, Json<ToolCallResponse>) {
    check_markdown_links_impl(state, req).await
}

async fn get_status_handler(State(state): State<AppState>) -> (StatusCode, Json<ToolCallResponse>) {
    get_status_impl(state).await
}

async fn get_audit_log_handler(
    State(state): State<AppState>,
    Json(req): Json<tools::status::GetAuditLogRequest>,
) -> (StatusCode, Json<ToolCallResponse>) {
    get_audit_log_impl(state, req).await
}
