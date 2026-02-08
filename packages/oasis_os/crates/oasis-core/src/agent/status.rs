//! Agent status tracking and registry.
//!
//! Manages a list of known AI agents with their availability status.
//! Configuration is loaded from `agents.toml` in the VFS.

use std::fmt;

use serde::Deserialize;

use crate::error::{OasisError, Result};

/// Known AI agent types.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AgentKind {
    Claude,
    Gemini,
    Codex,
    OpenCode,
    Crush,
}

impl fmt::Display for AgentKind {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Claude => write!(f, "Claude"),
            Self::Gemini => write!(f, "Gemini"),
            Self::Codex => write!(f, "Codex"),
            Self::OpenCode => write!(f, "OpenCode"),
            Self::Crush => write!(f, "Crush"),
        }
    }
}

/// Current availability of an agent.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum AgentAvailability {
    /// Agent is reachable and responding.
    Available,
    /// Agent is configured but not reachable.
    Unavailable,
    /// Status has not been checked yet.
    #[default]
    Unknown,
}

impl fmt::Display for AgentAvailability {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Available => write!(f, "available"),
            Self::Unavailable => write!(f, "unavailable"),
            Self::Unknown => write!(f, "unknown"),
        }
    }
}

/// How the agent is accessed.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AgentTransport {
    /// Command-line interface (e.g., Claude Code CLI).
    Cli,
    /// MCP server protocol.
    Mcp,
    /// HTTP/REST API.
    Http,
}

impl fmt::Display for AgentTransport {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Cli => write!(f, "CLI"),
            Self::Mcp => write!(f, "MCP"),
            Self::Http => write!(f, "HTTP"),
        }
    }
}

/// A configured agent entry (from `agents.toml`).
#[derive(Debug, Clone, Deserialize)]
pub struct AgentEntry {
    /// Human-readable name (e.g., "Claude Code").
    pub name: String,
    /// Agent type.
    pub kind: AgentKind,
    /// Access transport.
    pub transport: AgentTransport,
    /// Address (host:port, path, or URL depending on transport).
    #[serde(default)]
    pub address: String,
    /// Runtime availability (not deserialized -- set at runtime).
    #[serde(skip)]
    pub availability: AgentAvailability,
}

/// TOML wrapper for `[[agent]]` array.
#[derive(Debug, Deserialize)]
struct AgentsConfig {
    #[serde(default)]
    agent: Vec<AgentEntry>,
}

/// Registry of known agents.
#[derive(Debug, Clone)]
pub struct AgentRegistry {
    agents: Vec<AgentEntry>,
}

impl AgentRegistry {
    /// Create an empty registry.
    pub fn new() -> Self {
        Self { agents: Vec::new() }
    }

    /// Load agents from a TOML string (contents of `agents.toml`).
    pub fn from_toml(toml_str: &str) -> Result<Self> {
        let config: AgentsConfig = toml::from_str(toml_str)
            .map_err(|e| OasisError::Config(format!("agents.toml: {e}")))?;
        Ok(Self {
            agents: config.agent,
        })
    }

    /// Return the list of all configured agents.
    pub fn agents(&self) -> &[AgentEntry] {
        &self.agents
    }

    /// Find an agent by name (case-insensitive).
    pub fn find(&self, name: &str) -> Option<&AgentEntry> {
        let lower = name.to_lowercase();
        self.agents
            .iter()
            .find(|a| a.name.to_lowercase() == lower || a.kind.to_string().to_lowercase() == lower)
    }

    /// Find an agent by name (mutable, for updating availability).
    pub fn find_mut(&mut self, name: &str) -> Option<&mut AgentEntry> {
        let lower = name.to_lowercase();
        self.agents
            .iter_mut()
            .find(|a| a.name.to_lowercase() == lower || a.kind.to_string().to_lowercase() == lower)
    }

    /// Update an agent's availability by name.
    pub fn set_availability(&mut self, name: &str, avail: AgentAvailability) -> bool {
        if let Some(agent) = self.find_mut(name) {
            agent.availability = avail;
            true
        } else {
            false
        }
    }

    /// Return the number of configured agents.
    pub fn len(&self) -> usize {
        self.agents.len()
    }

    /// Return whether the registry is empty.
    pub fn is_empty(&self) -> bool {
        self.agents.is_empty()
    }
}

impl Default for AgentRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const AGENTS_TOML: &str = r#"
[[agent]]
name = "Claude Code"
kind = "claude"
transport = "cli"
address = "/usr/local/bin/claude"

[[agent]]
name = "Gemini CLI"
kind = "gemini"
transport = "mcp"
address = "localhost:8001"

[[agent]]
name = "Codex"
kind = "codex"
transport = "mcp"
address = "localhost:8002"

[[agent]]
name = "OpenCode"
kind = "opencode"
transport = "mcp"
address = "localhost:8003"

[[agent]]
name = "Crush"
kind = "crush"
transport = "mcp"
address = "localhost:8004"
"#;

    #[test]
    fn parse_agents_toml() {
        let reg = AgentRegistry::from_toml(AGENTS_TOML).unwrap();
        assert_eq!(reg.len(), 5);
        assert_eq!(reg.agents()[0].name, "Claude Code");
        assert_eq!(reg.agents()[0].kind, AgentKind::Claude);
        assert_eq!(reg.agents()[0].transport, AgentTransport::Cli);
    }

    #[test]
    fn find_by_name() {
        let reg = AgentRegistry::from_toml(AGENTS_TOML).unwrap();
        let agent = reg.find("Claude Code").unwrap();
        assert_eq!(agent.kind, AgentKind::Claude);
    }

    #[test]
    fn find_by_kind() {
        let reg = AgentRegistry::from_toml(AGENTS_TOML).unwrap();
        let agent = reg.find("gemini").unwrap();
        assert_eq!(agent.name, "Gemini CLI");
    }

    #[test]
    fn find_case_insensitive() {
        let reg = AgentRegistry::from_toml(AGENTS_TOML).unwrap();
        assert!(reg.find("CLAUDE CODE").is_some());
        assert!(reg.find("claude").is_some());
    }

    #[test]
    fn find_missing() {
        let reg = AgentRegistry::from_toml(AGENTS_TOML).unwrap();
        assert!(reg.find("nonexistent").is_none());
    }

    #[test]
    fn set_availability() {
        let mut reg = AgentRegistry::from_toml(AGENTS_TOML).unwrap();
        assert_eq!(
            reg.find("claude").unwrap().availability,
            AgentAvailability::Unknown
        );
        assert!(reg.set_availability("claude", AgentAvailability::Available));
        assert_eq!(
            reg.find("claude").unwrap().availability,
            AgentAvailability::Available
        );
    }

    #[test]
    fn set_availability_missing() {
        let mut reg = AgentRegistry::from_toml(AGENTS_TOML).unwrap();
        assert!(!reg.set_availability("nonexistent", AgentAvailability::Available));
    }

    #[test]
    fn empty_registry() {
        let reg = AgentRegistry::new();
        assert!(reg.is_empty());
        assert_eq!(reg.len(), 0);
    }

    #[test]
    fn empty_toml() {
        let reg = AgentRegistry::from_toml("").unwrap();
        assert!(reg.is_empty());
    }

    #[test]
    fn display_formats() {
        assert_eq!(AgentKind::Claude.to_string(), "Claude");
        assert_eq!(AgentKind::OpenCode.to_string(), "OpenCode");
        assert_eq!(AgentAvailability::Available.to_string(), "available");
        assert_eq!(AgentAvailability::Unavailable.to_string(), "unavailable");
        assert_eq!(AgentTransport::Cli.to_string(), "CLI");
        assert_eq!(AgentTransport::Mcp.to_string(), "MCP");
    }
}
