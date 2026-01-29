//! MCP server implementation for GitHub Board operations.
//!
//! Wraps the Rust `board-manager` CLI for all board operations.

use async_trait::async_trait;
use mcp_core::prelude::*;
use serde_json::{Value, json};
use std::path::PathBuf;
use std::sync::Arc;
use tokio::process::Command;
use tokio::sync::RwLock;
use tracing::{debug, error, info, warn};

/// GitHub Board MCP server
pub struct GitHubBoardServer {
    board_manager_path: Arc<RwLock<Option<PathBuf>>>,
    initialized: Arc<RwLock<bool>>,
}

impl GitHubBoardServer {
    /// Create a new GitHub board server
    pub fn new() -> Self {
        Self {
            board_manager_path: Arc::new(RwLock::new(None)),
            initialized: Arc::new(RwLock::new(false)),
        }
    }

    /// Get all tools as boxed trait objects
    pub fn tools(&self) -> Vec<BoxedTool> {
        vec![
            Arc::new(QueryReadyWorkTool {
                server: self.clone_refs(),
            }),
            Arc::new(ClaimWorkTool {
                server: self.clone_refs(),
            }),
            Arc::new(RenewClaimTool {
                server: self.clone_refs(),
            }),
            Arc::new(ReleaseWorkTool {
                server: self.clone_refs(),
            }),
            Arc::new(UpdateStatusTool {
                server: self.clone_refs(),
            }),
            Arc::new(AddBlockerTool {
                server: self.clone_refs(),
            }),
            Arc::new(MarkDiscoveredFromTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetIssueDetailsTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetDependencyGraphTool {
                server: self.clone_refs(),
            }),
            Arc::new(ListAgentsTool {
                server: self.clone_refs(),
            }),
            Arc::new(GetBoardConfigTool {
                server: self.clone_refs(),
            }),
            Arc::new(BoardStatusTool {
                server: self.clone_refs(),
            }),
        ]
    }

    /// Clone the Arc references for tools
    fn clone_refs(&self) -> ServerRefs {
        ServerRefs {
            board_manager_path: self.board_manager_path.clone(),
            initialized: self.initialized.clone(),
        }
    }
}

impl Default for GitHubBoardServer {
    fn default() -> Self {
        Self::new()
    }
}

/// Shared references for tools
#[derive(Clone)]
struct ServerRefs {
    board_manager_path: Arc<RwLock<Option<PathBuf>>>,
    initialized: Arc<RwLock<bool>>,
}

impl ServerRefs {
    /// Ensure board-manager CLI is available
    async fn ensure_initialized(&self) -> Result<PathBuf> {
        // Check if already initialized
        {
            let initialized = self.initialized.read().await;
            if *initialized {
                let path = self.board_manager_path.read().await;
                if let Some(p) = path.as_ref() {
                    return Ok(p.clone());
                }
            }
        }

        info!("Initializing board-manager CLI...");

        // Find board-manager binary
        let search_paths = [
            // Via which crate (PATH lookup)
            which::which("board-manager").ok(),
            // Local build paths
            Some(PathBuf::from(
                "tools/rust/board-manager/target/release/board-manager",
            )),
            // Relative to current working directory
            std::env::current_dir()
                .ok()
                .map(|cwd| cwd.join("tools/rust/board-manager/target/release/board-manager")),
            // Home local bin
            dirs::home_dir().map(|h| h.join(".local/bin/board-manager")),
        ];

        for path in search_paths.into_iter().flatten() {
            if path.is_file() {
                // Verify it's executable by running --version
                match Command::new(&path).arg("--version").output().await {
                    Ok(output) if output.status.success() => {
                        info!("Found board-manager at {:?}", path);

                        let mut bm_path = self.board_manager_path.write().await;
                        *bm_path = Some(path.clone());

                        let mut initialized = self.initialized.write().await;
                        *initialized = true;

                        return Ok(path);
                    }
                    Ok(output) => {
                        debug!(
                            "board-manager at {:?} failed version check: {:?}",
                            path, output.status
                        );
                    }
                    Err(e) => {
                        debug!("board-manager at {:?} not executable: {}", path, e);
                    }
                }
            }
        }

        Err(MCPError::Internal(
            "board-manager CLI not found. Please install or build it.".to_string(),
        ))
    }

    /// Run board-manager CLI with given arguments
    async fn run_board_manager(&self, args: &[&str]) -> Result<Value> {
        let path = self.ensure_initialized().await?;

        let mut cmd = Command::new(&path);
        cmd.arg("--format").arg("json");
        cmd.args(args);

        debug!("Running: {:?} --format json {:?}", path, args);

        let output = cmd
            .output()
            .await
            .map_err(|e| MCPError::Internal(format!("Failed to execute board-manager: {}", e)))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            error!("board-manager failed: {}", stderr);
            return Err(MCPError::Internal(format!(
                "board-manager error: {}",
                stderr.trim()
            )));
        }

        let stdout = String::from_utf8_lossy(&output.stdout);
        if stdout.is_empty() {
            return Ok(json!({}));
        }

        serde_json::from_str(&stdout).map_err(|e| {
            warn!("Failed to parse board-manager JSON output: {}", e);
            // Return raw output if JSON parsing fails
            MCPError::Internal(format!("Invalid JSON from board-manager: {}", e))
        })
    }
}

// ============================================================================
// Tool: query_ready_work
// ============================================================================

struct QueryReadyWorkTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for QueryReadyWorkTool {
    fn name(&self) -> &str {
        "query_ready_work"
    }

    fn description(&self) -> &str {
        r#"Get ready work from the board (unblocked, unclaimed TODO issues).

Returns issues that are available for an agent to claim and work on.
Filters by agent name if specified."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "agent_name": {
                    "type": "string",
                    "description": "Filter for specific agent (optional)"
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum number of issues to return"
                }
            }
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let limit = args
            .get("limit")
            .and_then(|v| v.as_u64())
            .unwrap_or(10)
            .to_string();

        let mut cmd_args = vec!["ready", "--limit", &limit];

        let agent_name = args.get("agent_name").and_then(|v| v.as_str());
        if let Some(agent) = agent_name {
            cmd_args.push("--agent");
            cmd_args.push(agent);
        }

        let result = self.server.run_board_manager(&cmd_args).await?;
        let response = json!({
            "success": true,
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: claim_work
// ============================================================================

struct ClaimWorkTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ClaimWorkTool {
    fn name(&self) -> &str {
        "claim_work"
    }

    fn description(&self) -> &str {
        r#"Claim an issue for implementation.

Marks an issue as being worked on by an agent, preventing other agents
from claiming it. The session_id allows tracking work across sessions."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "issue_number": {
                    "type": "integer",
                    "description": "Issue number to claim"
                },
                "agent_name": {
                    "type": "string",
                    "description": "Agent claiming the issue"
                },
                "session_id": {
                    "type": "string",
                    "description": "Unique session identifier"
                }
            },
            "required": ["issue_number", "agent_name", "session_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let issue_number = args
            .get("issue_number")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'issue_number' parameter".to_string())
            })?
            .to_string();

        let agent_name = args
            .get("agent_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'agent_name' parameter".to_string())
            })?;

        let session_id = args
            .get("session_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'session_id' parameter".to_string())
            })?;

        let result = self
            .server
            .run_board_manager(&[
                "claim",
                &issue_number,
                "--agent",
                agent_name,
                "--session",
                session_id,
            ])
            .await?;

        let response = json!({
            "success": true,
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: renew_claim
// ============================================================================

struct RenewClaimTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for RenewClaimTool {
    fn name(&self) -> &str {
        "renew_claim"
    }

    fn description(&self) -> &str {
        r#"Renew an active claim for long-running tasks.

Prevents claim timeout by extending the claim duration.
Must use the same agent_name and session_id from the original claim."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "issue_number": {
                    "type": "integer",
                    "description": "Issue number with active claim"
                },
                "agent_name": {
                    "type": "string",
                    "description": "Agent renewing the claim"
                },
                "session_id": {
                    "type": "string",
                    "description": "Session identifier from original claim"
                }
            },
            "required": ["issue_number", "agent_name", "session_id"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let issue_number = args
            .get("issue_number")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'issue_number' parameter".to_string())
            })?
            .to_string();

        let agent_name = args
            .get("agent_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'agent_name' parameter".to_string())
            })?;

        let session_id = args
            .get("session_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'session_id' parameter".to_string())
            })?;

        let result = self
            .server
            .run_board_manager(&[
                "renew",
                &issue_number,
                "--agent",
                agent_name,
                "--session",
                session_id,
            ])
            .await?;

        let response = json!({
            "success": true,
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: release_work
// ============================================================================

struct ReleaseWorkTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ReleaseWorkTool {
    fn name(&self) -> &str {
        "release_work"
    }

    fn description(&self) -> &str {
        r#"Release claim on an issue.

Releases the agent's claim on an issue, allowing other agents to claim it.
Specify a reason to indicate why the work is being released."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "issue_number": {
                    "type": "integer",
                    "description": "Issue number to release"
                },
                "agent_name": {
                    "type": "string",
                    "description": "Agent releasing the claim"
                },
                "reason": {
                    "type": "string",
                    "enum": ["completed", "blocked", "abandoned", "error"],
                    "default": "completed",
                    "description": "Reason for release"
                }
            },
            "required": ["issue_number", "agent_name"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let issue_number = args
            .get("issue_number")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'issue_number' parameter".to_string())
            })?
            .to_string();

        let agent_name = args
            .get("agent_name")
            .and_then(|v| v.as_str())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'agent_name' parameter".to_string())
            })?;

        let reason = args
            .get("reason")
            .and_then(|v| v.as_str())
            .unwrap_or("completed");

        let result = self
            .server
            .run_board_manager(&[
                "release",
                &issue_number,
                "--agent",
                agent_name,
                "--reason",
                reason,
            ])
            .await?;

        let response = json!({
            "success": true,
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: update_status
// ============================================================================

struct UpdateStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for UpdateStatusTool {
    fn name(&self) -> &str {
        "update_status"
    }

    fn description(&self) -> &str {
        r#"Update issue status on the board.

Changes the status field of an issue on the GitHub Projects board."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "issue_number": {
                    "type": "integer",
                    "description": "Issue number to update"
                },
                "status": {
                    "type": "string",
                    "enum": ["Todo", "In Progress", "Blocked", "Done", "Abandoned"],
                    "description": "New status"
                }
            },
            "required": ["issue_number", "status"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let issue_number = args
            .get("issue_number")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'issue_number' parameter".to_string())
            })?
            .to_string();

        let status = args
            .get("status")
            .and_then(|v| v.as_str())
            .ok_or_else(|| MCPError::InvalidParameters("Missing 'status' parameter".to_string()))?;

        let result = self
            .server
            .run_board_manager(&["status", &issue_number, status])
            .await?;

        let response = json!({
            "success": true,
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: add_blocker
// ============================================================================

struct AddBlockerTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for AddBlockerTool {
    fn name(&self) -> &str {
        "add_blocker"
    }

    fn description(&self) -> &str {
        r#"Add a blocking dependency between issues.

Marks one issue as blocked by another. The blocked issue won't appear
in ready work until the blocker is resolved."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "issue_number": {
                    "type": "integer",
                    "description": "Issue that is blocked"
                },
                "blocker_number": {
                    "type": "integer",
                    "description": "Issue that blocks"
                }
            },
            "required": ["issue_number", "blocker_number"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let issue_number = args
            .get("issue_number")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'issue_number' parameter".to_string())
            })?
            .to_string();

        let blocker_number = args
            .get("blocker_number")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'blocker_number' parameter".to_string())
            })?
            .to_string();

        let result = self
            .server
            .run_board_manager(&["block", &issue_number, "--blocker", &blocker_number])
            .await?;

        let response = json!({
            "success": true,
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: mark_discovered_from
// ============================================================================

struct MarkDiscoveredFromTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for MarkDiscoveredFromTool {
    fn name(&self) -> &str {
        "mark_discovered_from"
    }

    fn description(&self) -> &str {
        r#"Mark an issue as discovered from another (parent-child relationship).

Establishes a parent-child relationship between issues, useful for
tracking work that spawned sub-tasks."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "issue_number": {
                    "type": "integer",
                    "description": "Child issue number"
                },
                "parent_number": {
                    "type": "integer",
                    "description": "Parent issue number"
                }
            },
            "required": ["issue_number", "parent_number"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let issue_number = args
            .get("issue_number")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'issue_number' parameter".to_string())
            })?
            .to_string();

        let parent_number = args
            .get("parent_number")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'parent_number' parameter".to_string())
            })?
            .to_string();

        let result = self
            .server
            .run_board_manager(&["discover-from", &issue_number, "--parent", &parent_number])
            .await?;

        let response = json!({
            "success": true,
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: get_issue_details
// ============================================================================

struct GetIssueDetailsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetIssueDetailsTool {
    fn name(&self) -> &str {
        "get_issue_details"
    }

    fn description(&self) -> &str {
        r#"Get full details for a specific issue.

Returns comprehensive information about an issue including status,
assignee, labels, and board metadata."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "issue_number": {
                    "type": "integer",
                    "description": "Issue number to query"
                }
            },
            "required": ["issue_number"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let issue_number = args
            .get("issue_number")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'issue_number' parameter".to_string())
            })?
            .to_string();

        let result = self
            .server
            .run_board_manager(&["info", &issue_number])
            .await?;

        let response = json!({
            "success": true,
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: get_dependency_graph
// ============================================================================

struct GetDependencyGraphTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetDependencyGraphTool {
    fn name(&self) -> &str {
        "get_dependency_graph"
    }

    fn description(&self) -> &str {
        r#"Get dependency graph for an issue.

Returns blockers, blocked issues, parent, and children relationships
for the specified issue."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {
                "issue_number": {
                    "type": "integer",
                    "description": "Issue number to query"
                }
            },
            "required": ["issue_number"]
        })
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        let issue_number = args
            .get("issue_number")
            .and_then(|v| v.as_u64())
            .ok_or_else(|| {
                MCPError::InvalidParameters("Missing 'issue_number' parameter".to_string())
            })?
            .to_string();

        // The info command includes dependency information
        let result = self
            .server
            .run_board_manager(&["info", &issue_number])
            .await?;

        let response = json!({
            "success": true,
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: list_agents
// ============================================================================

struct ListAgentsTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for ListAgentsTool {
    fn name(&self) -> &str {
        "list_agents"
    }

    fn description(&self) -> &str {
        r#"Get list of enabled agents for this board.

Returns the configured agents that are allowed to claim and work on issues."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let result = self.server.run_board_manager(&["agents"]).await?;

        let response = json!({
            "success": true,
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: get_board_config
// ============================================================================

struct GetBoardConfigTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for GetBoardConfigTool {
    fn name(&self) -> &str {
        "get_board_config"
    }

    fn description(&self) -> &str {
        r#"Get current board configuration.

Returns the full configuration for the GitHub Projects board including
field mappings, agent settings, and work queue configuration."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let result = self.server.run_board_manager(&["config"]).await?;

        let response = json!({
            "success": true,
            "result": result
        });
        ToolResult::json(&response)
    }
}

// ============================================================================
// Tool: board_status
// ============================================================================

struct BoardStatusTool {
    server: ServerRefs,
}

#[async_trait]
impl Tool for BoardStatusTool {
    fn name(&self) -> &str {
        "board_status"
    }

    fn description(&self) -> &str {
        r#"Get GitHub board server status.

Returns information about initialization state and board-manager CLI availability."#
    }

    fn schema(&self) -> Value {
        json!({
            "type": "object",
            "properties": {}
        })
    }

    async fn execute(&self, _args: Value) -> Result<ToolResult> {
        let initialized = *self.server.initialized.read().await;
        let path = self.server.board_manager_path.read().await;

        let mut response = json!({
            "server": "github-board",
            "version": "2.0.0",
            "initialized": initialized
        });

        if let Some(p) = path.as_ref() {
            response["board_manager_path"] = json!(p.to_string_lossy());
        }

        if !initialized {
            response["note"] = json!("board-manager CLI will be located on first tool call");
        }

        ToolResult::json(&response)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_server_creation() {
        let server = GitHubBoardServer::new();
        let tools = server.tools();
        assert_eq!(tools.len(), 12);
    }

    #[test]
    fn test_tool_names() {
        let server = GitHubBoardServer::new();
        let tools = server.tools();
        let names: Vec<&str> = tools.iter().map(|t| t.name()).collect();

        assert!(names.contains(&"query_ready_work"));
        assert!(names.contains(&"claim_work"));
        assert!(names.contains(&"renew_claim"));
        assert!(names.contains(&"release_work"));
        assert!(names.contains(&"update_status"));
        assert!(names.contains(&"add_blocker"));
        assert!(names.contains(&"mark_discovered_from"));
        assert!(names.contains(&"get_issue_details"));
        assert!(names.contains(&"get_dependency_graph"));
        assert!(names.contains(&"list_agents"));
        assert!(names.contains(&"get_board_config"));
        assert!(names.contains(&"board_status"));
    }
}
