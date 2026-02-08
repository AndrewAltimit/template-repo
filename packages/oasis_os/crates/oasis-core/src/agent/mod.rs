//! Agent subsystem -- AI agent status, MCP tool browsing, tamper monitoring,
//! and system health for the briefcase agent terminal.

pub mod health;
pub mod mcp;
pub mod status;
pub mod tamper;

pub use health::SystemHealth;
pub use mcp::{McpRegistry, McpServerEntry, McpToolEntry, McpTransport};
pub use status::{AgentAvailability, AgentEntry, AgentKind, AgentRegistry, AgentTransport};
pub use tamper::{TamperState, TamperStatus, read_tamper_status, request_disarm};
