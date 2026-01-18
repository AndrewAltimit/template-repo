//! Status and audit log tools

use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

use serde::{Deserialize, Serialize};
use serde_json::json;

use crate::error::Result;
use crate::subprocess::{check_tool_available, get_tool_version};

/// Tool availability info
#[derive(Debug, Serialize)]
pub struct ToolInfo {
    pub name: String,
    pub available: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub version: Option<String>,
}

/// Response for get_status operation
#[derive(Debug, Serialize)]
pub struct StatusResponse {
    pub success: bool,
    pub server_version: String,
    pub tools: Vec<ToolInfo>,
    pub rate_limiting_enabled: bool,
}

/// Get server status and tool availability
pub async fn get_status(rate_limiting_enabled: bool) -> Result<StatusResponse> {
    // Tools to check - prefer modern tools
    // ruff replaces black, flake8, pylint, AND bandit security rules (10-100x faster)
    let tools_to_check = [
        "ruff",            // Modern: replaces black, flake8, pylint, bandit
        "mypy",            // Type checking (no modern replacement yet)
        "pip-audit",       // Dependency auditing
        "pytest",          // Testing
        "prettier",        // JS/TS formatting
        "eslint",          // JS/TS linting
        "gofmt",           // Go formatting
        "rustfmt",         // Rust formatting
        "cargo",           // Rust toolchain
        "md-link-checker", // Our Rust markdown link checker
    ];

    let mut tools = Vec::new();

    for tool_name in tools_to_check {
        let available = check_tool_available(tool_name).await;
        let version = if available {
            get_tool_version(tool_name).await
        } else {
            None
        };

        tools.push(ToolInfo {
            name: tool_name.to_string(),
            available,
            version,
        });
    }

    Ok(StatusResponse {
        success: true,
        server_version: env!("CARGO_PKG_VERSION").to_string(),
        tools,
        rate_limiting_enabled,
    })
}

/// Request for get_audit_log operation
#[derive(Debug, Deserialize)]
pub struct GetAuditLogRequest {
    #[serde(default = "default_limit")]
    pub limit: usize,
    #[serde(default)]
    pub operation: Option<String>,
}

fn default_limit() -> usize {
    100
}

/// Response for get_audit_log operation
#[derive(Debug, Serialize)]
pub struct AuditLogResponse {
    pub success: bool,
    pub entries: Vec<serde_json::Value>,
    pub total_entries: usize,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub message: Option<String>,
}

/// Get recent audit log entries
pub async fn get_audit_log(
    log_path: &Path,
    limit: usize,
    operation_filter: Option<&str>,
) -> Result<AuditLogResponse> {
    let file = match File::open(log_path) {
        Ok(f) => f,
        Err(_) => {
            return Ok(AuditLogResponse {
                success: true,
                entries: vec![],
                total_entries: 0,
                message: Some("Audit log file not found or not readable".to_string()),
            });
        }
    };

    let reader = BufReader::new(file);
    let mut entries: Vec<serde_json::Value> = Vec::new();

    for line in reader.lines().map_while(|r| r.ok()) {
        if let Ok(entry) = serde_json::from_str::<serde_json::Value>(&line) {
            // Apply operation filter if specified
            if let Some(filter_op) = operation_filter
                && let Some(op) = entry.get("operation").and_then(|v| v.as_str())
                && op != filter_op
            {
                continue;
            }
            entries.push(entry);
        }
    }

    // Get last N entries (most recent)
    let total = entries.len();
    let entries: Vec<_> = entries.into_iter().rev().take(limit).collect();

    Ok(AuditLogResponse {
        success: true,
        entries,
        total_entries: total,
        message: None,
    })
}

impl StatusResponse {
    pub fn to_json(&self) -> serde_json::Value {
        json!({
            "success": self.success,
            "server_version": self.server_version,
            "tools": self.tools,
            "rate_limiting_enabled": self.rate_limiting_enabled,
        })
    }
}

impl AuditLogResponse {
    pub fn to_json(&self) -> serde_json::Value {
        json!({
            "success": self.success,
            "entries": self.entries,
            "total_entries": self.total_entries,
            "message": self.message,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_get_status() {
        let status = get_status(true).await.unwrap();
        assert!(status.success);
        assert!(!status.tools.is_empty());
    }

    #[tokio::test]
    async fn test_get_audit_log_missing_file() {
        let result = get_audit_log(Path::new("/nonexistent/path"), 10, None).await;
        assert!(result.is_ok());
        let response = result.unwrap();
        assert!(response.entries.is_empty());
    }
}
