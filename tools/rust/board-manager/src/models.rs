//! Data models for GitHub Projects v2 board integration.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Issue status values on the board.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
pub enum IssueStatus {
    #[serde(rename = "Todo")]
    #[default]
    Todo,
    #[serde(rename = "In Progress")]
    InProgress,
    #[serde(rename = "Blocked")]
    Blocked,
    #[serde(rename = "Done")]
    Done,
    #[serde(rename = "Abandoned")]
    Abandoned,
}

impl IssueStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            IssueStatus::Todo => "Todo",
            IssueStatus::InProgress => "In Progress",
            IssueStatus::Blocked => "Blocked",
            IssueStatus::Done => "Done",
            IssueStatus::Abandoned => "Abandoned",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "Todo" => Some(IssueStatus::Todo),
            "In Progress" => Some(IssueStatus::InProgress),
            "Blocked" => Some(IssueStatus::Blocked),
            "Done" => Some(IssueStatus::Done),
            "Abandoned" => Some(IssueStatus::Abandoned),
            _ => None,
        }
    }
}

impl std::fmt::Display for IssueStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

/// Issue priority levels.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
pub enum IssuePriority {
    Critical,
    High,
    #[default]
    Medium,
    Low,
}

impl IssuePriority {
    pub fn as_str(&self) -> &'static str {
        match self {
            IssuePriority::Critical => "Critical",
            IssuePriority::High => "High",
            IssuePriority::Medium => "Medium",
            IssuePriority::Low => "Low",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "Critical" => Some(IssuePriority::Critical),
            "High" => Some(IssuePriority::High),
            "Medium" => Some(IssuePriority::Medium),
            "Low" => Some(IssuePriority::Low),
            _ => None,
        }
    }
}

impl std::fmt::Display for IssuePriority {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

/// Issue type categorization.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum IssueType {
    Feature,
    Bug,
    #[serde(rename = "Tech Debt")]
    TechDebt,
    Documentation,
}

impl IssueType {
    pub fn as_str(&self) -> &'static str {
        match self {
            IssueType::Feature => "Feature",
            IssueType::Bug => "Bug",
            IssueType::TechDebt => "Tech Debt",
            IssueType::Documentation => "Documentation",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "Feature" => Some(IssueType::Feature),
            "Bug" => Some(IssueType::Bug),
            "Tech Debt" => Some(IssueType::TechDebt),
            "Documentation" => Some(IssueType::Documentation),
            _ => None,
        }
    }
}

impl std::fmt::Display for IssueType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

/// Issue size estimation.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum IssueSize {
    XS,
    S,
    M,
    L,
    XL,
}

#[allow(dead_code)]
impl IssueSize {
    pub fn as_str(&self) -> &'static str {
        match self {
            IssueSize::XS => "XS",
            IssueSize::S => "S",
            IssueSize::M => "M",
            IssueSize::L => "L",
            IssueSize::XL => "XL",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "XS" => Some(IssueSize::XS),
            "S" => Some(IssueSize::S),
            "M" => Some(IssueSize::M),
            "L" => Some(IssueSize::L),
            "XL" => Some(IssueSize::XL),
            _ => None,
        }
    }
}

impl std::fmt::Display for IssueSize {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

/// Represents a GitHub issue with board metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Issue {
    /// Issue number
    pub number: u64,
    /// Issue title
    pub title: String,
    /// Issue body/description
    pub body: String,
    /// Issue state (open/closed)
    pub state: String,
    /// Board status (Todo, In Progress, etc.)
    #[serde(default)]
    pub status: IssueStatus,
    /// Issue priority
    #[serde(default)]
    pub priority: IssuePriority,
    /// Issue type
    #[serde(skip_serializing_if = "Option::is_none")]
    pub issue_type: Option<IssueType>,
    /// Estimated size
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size: Option<IssueSize>,
    /// Assigned agent name
    #[serde(skip_serializing_if = "Option::is_none")]
    pub agent: Option<String>,
    /// List of issue numbers blocking this issue
    #[serde(default)]
    pub blocked_by: Vec<u64>,
    /// Parent issue number
    #[serde(skip_serializing_if = "Option::is_none")]
    pub discovered_from: Option<u64>,
    /// Creation timestamp
    #[serde(skip_serializing_if = "Option::is_none")]
    pub created_at: Option<DateTime<Utc>>,
    /// Last update timestamp
    #[serde(skip_serializing_if = "Option::is_none")]
    pub updated_at: Option<DateTime<Utc>>,
    /// Issue URL
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
    /// List of label names
    #[serde(default)]
    pub labels: Vec<String>,
    /// GitHub Projects v2 item ID
    #[serde(skip_serializing_if = "Option::is_none")]
    pub project_item_id: Option<String>,
}


#[allow(dead_code)]
impl Issue {
    /// Check if issue is ready to work on.
    pub fn is_ready(&self) -> bool {
        self.status == IssueStatus::Todo && self.blocked_by.is_empty()
    }

    /// Check if issue is claimed by an agent.
    pub fn is_claimed(&self) -> bool {
        self.agent.is_some()
    }
}

impl std::fmt::Display for Issue {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Issue #{}: {} ({})", self.number, self.title, self.status)
    }
}

/// Represents an agent's claim on an issue.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentClaim {
    /// Issue being claimed
    pub issue_number: u64,
    /// Agent name
    pub agent: String,
    /// Unique session identifier
    pub session_id: String,
    /// Claim timestamp
    pub timestamp: DateTime<Utc>,
    /// Last renewal timestamp
    #[serde(skip_serializing_if = "Option::is_none")]
    pub renewed_at: Option<DateTime<Utc>>,
    /// Whether claim was released
    #[serde(default)]
    pub released: bool,
}

impl AgentClaim {
    /// Calculate claim age in seconds.
    pub fn age_seconds(&self) -> f64 {
        let reference_time = self.renewed_at.unwrap_or(self.timestamp);
        let now = Utc::now();
        (now - reference_time).num_seconds() as f64
    }

    /// Check if claim has expired.
    pub fn is_expired(&self, timeout_seconds: i64) -> bool {
        self.age_seconds() > timeout_seconds as f64
    }
}

impl std::fmt::Display for AgentClaim {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let renewed = self
            .renewed_at
            .map(|t| format!(" (renewed {})", t))
            .unwrap_or_default();
        write!(
            f,
            "Claim by {} on #{} at {}{}",
            self.agent, self.issue_number, self.timestamp, renewed
        )
    }
}

/// Configuration for GitHub Projects v2 board.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoardConfig {
    /// GitHub Project number
    pub project_number: u64,
    /// Project owner (user or org)
    pub owner: String,
    /// Repository name (owner/repo)
    pub repository: String,
    /// Custom field name mappings
    #[serde(default)]
    pub field_mappings: HashMap<String, String>,
    /// Claim timeout in seconds
    #[serde(default = "default_claim_timeout")]
    pub claim_timeout: i64,
    /// How often to renew claims
    #[serde(default = "default_renewal_interval")]
    pub claim_renewal_interval: i64,
    /// List of enabled agent names
    #[serde(default)]
    pub enabled_agents: Vec<String>,
    /// Auto-file discovered issues
    #[serde(default = "default_true")]
    pub auto_discover: bool,
    /// Labels to exclude from work queue
    #[serde(default)]
    pub exclude_labels: Vec<String>,
    /// Label-to-priority mappings
    #[serde(default)]
    pub priority_labels: HashMap<String, Vec<String>>,
}

fn default_claim_timeout() -> i64 {
    86400 // 24 hours
}

fn default_renewal_interval() -> i64 {
    3600 // 1 hour
}

fn default_true() -> bool {
    true
}

impl Default for BoardConfig {
    fn default() -> Self {
        Self {
            project_number: 0,
            owner: String::new(),
            repository: String::new(),
            field_mappings: Self::default_field_mappings(),
            claim_timeout: default_claim_timeout(),
            claim_renewal_interval: default_renewal_interval(),
            enabled_agents: Vec::new(),
            auto_discover: true,
            exclude_labels: Vec::new(),
            priority_labels: HashMap::new(),
        }
    }
}

impl BoardConfig {
    /// Create default field mappings.
    pub fn default_field_mappings() -> HashMap<String, String> {
        let mut mappings = HashMap::new();
        mappings.insert("status".to_string(), "Status".to_string());
        mappings.insert("priority".to_string(), "Priority".to_string());
        mappings.insert("agent".to_string(), "Agent".to_string());
        mappings.insert("type".to_string(), "Type".to_string());
        mappings.insert("blocked_by".to_string(), "Blocked By".to_string());
        mappings.insert("discovered_from".to_string(), "Discovered From".to_string());
        mappings.insert("size".to_string(), "Estimated Size".to_string());
        mappings
    }

    /// Get field name from mapping.
    pub fn get_field_name(&self, key: &str) -> String {
        self.field_mappings
            .get(key)
            .cloned()
            .unwrap_or_else(|| {
                Self::default_field_mappings()
                    .get(key)
                    .cloned()
                    .unwrap_or_else(|| key.to_string())
            })
    }
}

/// Represents dependency relationships between issues.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[allow(dead_code)]
pub struct DependencyGraph {
    /// The main issue
    pub issue: Issue,
    /// Issues this issue blocks
    #[serde(default)]
    pub blocks: Vec<Issue>,
    /// Issues blocking this issue
    #[serde(default)]
    pub blocked_by: Vec<Issue>,
    /// Child issues (discovered from this)
    #[serde(default)]
    pub children: Vec<Issue>,
    /// Parent issue (this was discovered from)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parent: Option<Box<Issue>>,
}

#[allow(dead_code)]
impl DependencyGraph {
    /// Check if all blockers are resolved.
    pub fn is_ready(&self) -> bool {
        if self.blocked_by.is_empty() {
            return true;
        }
        self.blocked_by
            .iter()
            .all(|b| b.status == IssueStatus::Done || b.status == IssueStatus::Abandoned)
    }

    /// Calculate depth in dependency tree.
    pub fn depth(&self) -> usize {
        if self.parent.is_none() {
            0
        } else {
            1 // Simplified - full implementation would recursively check parent
        }
    }
}

/// Response from GraphQL API.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphQLResponse {
    /// Response data
    #[serde(skip_serializing_if = "Option::is_none")]
    pub data: Option<serde_json::Value>,
    /// List of errors
    #[serde(default)]
    pub errors: Vec<GraphQLError>,
}

/// GraphQL error.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GraphQLError {
    pub message: String,
    #[serde(default)]
    pub path: Vec<String>,
    #[serde(default)]
    pub locations: Vec<serde_json::Value>,
}

#[allow(dead_code)]
impl GraphQLResponse {
    /// Check if response was successful.
    pub fn is_success(&self) -> bool {
        self.errors.is_empty()
    }

    /// Get formatted error message.
    pub fn get_error_message(&self) -> String {
        if self.errors.is_empty() {
            return String::new();
        }
        self.errors
            .iter()
            .map(|e| e.message.as_str())
            .collect::<Vec<_>>()
            .join("; ")
    }
}

/// Reason for releasing a claim.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ReleaseReason {
    Completed,
    PrCreated,
    Blocked,
    Abandoned,
    Error,
}

impl ReleaseReason {
    pub fn as_str(&self) -> &'static str {
        match self {
            ReleaseReason::Completed => "completed",
            ReleaseReason::PrCreated => "pr_created",
            ReleaseReason::Blocked => "blocked",
            ReleaseReason::Abandoned => "abandoned",
            ReleaseReason::Error => "error",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "completed" => Some(ReleaseReason::Completed),
            "pr_created" => Some(ReleaseReason::PrCreated),
            "blocked" => Some(ReleaseReason::Blocked),
            "abandoned" => Some(ReleaseReason::Abandoned),
            "error" => Some(ReleaseReason::Error),
            _ => None,
        }
    }
}

impl std::fmt::Display for ReleaseReason {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_issue_is_ready() {
        let issue = Issue {
            number: 1,
            title: "Test".to_string(),
            body: String::new(),
            state: "open".to_string(),
            status: IssueStatus::Todo,
            priority: IssuePriority::Medium,
            issue_type: None,
            size: None,
            agent: None,
            blocked_by: vec![],
            discovered_from: None,
            created_at: None,
            updated_at: None,
            url: None,
            labels: vec![],
            project_item_id: None,
        };
        assert!(issue.is_ready());

        let blocked_issue = Issue {
            blocked_by: vec![2],
            ..issue.clone()
        };
        assert!(!blocked_issue.is_ready());

        let in_progress = Issue {
            status: IssueStatus::InProgress,
            ..issue
        };
        assert!(!in_progress.is_ready());
    }

    #[test]
    fn test_issue_status_parsing() {
        assert_eq!(IssueStatus::from_str("Todo"), Some(IssueStatus::Todo));
        assert_eq!(
            IssueStatus::from_str("In Progress"),
            Some(IssueStatus::InProgress)
        );
        assert_eq!(IssueStatus::from_str("invalid"), None);
    }

    #[test]
    fn test_board_config_default() {
        let config = BoardConfig::default();
        assert_eq!(config.claim_timeout, 86400);
        assert_eq!(config.get_field_name("status"), "Status");
    }
}
