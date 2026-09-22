//! Data models for GitHub Projects v2 board integration.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Normalize a user-supplied enum value for lenient parsing:
/// lowercase with spaces, underscores and hyphens removed.
fn normalize_token(s: &str) -> String {
    s.chars()
        .filter(|c| !matches!(c, ' ' | '_' | '-'))
        .flat_map(char::to_lowercase)
        .collect()
}

/// Generate `as_str`, `ALL`, `Display` and a lenient `FromStr` for a
/// fieldless enum whose canonical strings match the board option names.
macro_rules! string_enum {
    ($name:ident, $what:literal, { $($variant:ident => $text:literal),+ $(,)? }) => {
        impl $name {
            /// All variants in declaration order.
            pub const ALL: &'static [$name] = &[$($name::$variant),+];

            /// Canonical string (matches the board option name).
            pub fn as_str(&self) -> &'static str {
                match self {
                    $($name::$variant => $text),+
                }
            }
        }

        impl std::fmt::Display for $name {
            fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                f.write_str(self.as_str())
            }
        }

        impl std::str::FromStr for $name {
            type Err = String;

            /// Case-insensitive; ignores spaces, `_` and `-`
            /// (so `in_progress`, `In Progress` and `in-progress` all parse).
            fn from_str(s: &str) -> std::result::Result<Self, Self::Err> {
                let wanted = normalize_token(s);
                Self::ALL
                    .iter()
                    .copied()
                    .find(|v| normalize_token(v.as_str()) == wanted)
                    .ok_or_else(|| {
                        let valid: Vec<&str> = Self::ALL.iter().map(|v| v.as_str()).collect();
                        format!("Invalid {} '{}' (expected one of: {})", $what, s, valid.join(", "))
                    })
            }
        }
    };
}

/// Issue status values on the board.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize, Default)]
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

string_enum!(IssueStatus, "status", {
    Todo => "Todo",
    InProgress => "In Progress",
    Blocked => "Blocked",
    Done => "Done",
    Abandoned => "Abandoned",
});

impl IssueStatus {
    /// Whether this status resolves a dependency on the issue.
    pub fn is_terminal(self) -> bool {
        matches!(self, IssueStatus::Done | IssueStatus::Abandoned)
    }
}

/// Issue priority levels (declaration order = sort order).
#[derive(
    Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize, Default,
)]
pub enum IssuePriority {
    Critical,
    High,
    #[default]
    Medium,
    Low,
}

string_enum!(IssuePriority, "priority", {
    Critical => "Critical",
    High => "High",
    Medium => "Medium",
    Low => "Low",
});

/// Issue type categorization.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum IssueType {
    Feature,
    Bug,
    #[serde(rename = "Tech Debt")]
    TechDebt,
    Documentation,
}

string_enum!(IssueType, "type", {
    Feature => "Feature",
    Bug => "Bug",
    TechDebt => "Tech Debt",
    Documentation => "Documentation",
});

/// Issue size estimation.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum IssueSize {
    XS,
    S,
    M,
    L,
    XL,
}

string_enum!(IssueSize, "size", {
    XS => "XS",
    S => "S",
    M => "M",
    L => "L",
    XL => "XL",
});

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

string_enum!(ReleaseReason, "release reason", {
    Completed => "completed",
    PrCreated => "pr_created",
    Blocked => "blocked",
    Abandoned => "abandoned",
    Error => "error",
});

impl ReleaseReason {
    /// Board status to apply after releasing with this reason, if any.
    ///
    /// Completed / PR-created work stays In Progress until the PR merges.
    /// Abandoned and errored work moves to Abandoned so agents do not loop on
    /// an issue they keep failing.
    pub fn resulting_status(self) -> Option<IssueStatus> {
        match self {
            ReleaseReason::Completed | ReleaseReason::PrCreated => None,
            ReleaseReason::Blocked => Some(IssueStatus::Blocked),
            ReleaseReason::Abandoned | ReleaseReason::Error => Some(IssueStatus::Abandoned),
        }
    }
}

/// A GitHub issue with board metadata.
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
    /// Issue priority (board field, falling back to priority labels)
    #[serde(default)]
    pub priority: IssuePriority,
    /// Issue type (board field, falling back to type labels)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub issue_type: Option<IssueType>,
    /// Estimated size
    #[serde(skip_serializing_if = "Option::is_none")]
    pub size: Option<IssueSize>,
    /// Assigned agent (board Agent field)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub agent: Option<String>,
    /// Issue numbers blocking this issue
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
    /// Label names
    #[serde(default)]
    pub labels: Vec<String>,
    /// GitHub Projects v2 item ID
    #[serde(skip_serializing_if = "Option::is_none")]
    pub project_item_id: Option<String>,
}

impl Issue {
    /// Whether the underlying GitHub issue is open.
    pub fn is_open(&self) -> bool {
        self.state.eq_ignore_ascii_case("open")
    }

    /// Whether a dependency on this issue is resolved.
    pub fn resolves_dependency(&self) -> bool {
        !self.is_open() || self.status.is_terminal()
    }
}

impl std::fmt::Display for Issue {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "Issue #{}: {} ({})",
            self.number, self.title, self.status
        )
    }
}

/// An agent's claim on an issue, reconstructed from issue comments.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
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
}

impl AgentClaim {
    /// Time of the most recent activity (claim or renewal).
    pub fn last_activity(&self) -> DateTime<Utc> {
        self.renewed_at.unwrap_or(self.timestamp)
    }

    /// Claim age in seconds relative to `now`.
    pub fn age_seconds_at(&self, now: DateTime<Utc>) -> i64 {
        (now - self.last_activity()).num_seconds()
    }

    /// Whether the claim has expired relative to `now`.
    pub fn is_expired_at(&self, timeout_seconds: i64, now: DateTime<Utc>) -> bool {
        self.age_seconds_at(now) > timeout_seconds
    }

    /// Whether the claim has expired now.
    pub fn is_expired(&self, timeout_seconds: i64) -> bool {
        self.is_expired_at(timeout_seconds, Utc::now())
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

/// Outcome of a claim attempt.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ClaimOutcome {
    /// The claim was recorded and the issue moved to In Progress.
    Claimed,
    /// Another unexpired claim already existed; nothing was posted.
    AlreadyClaimed(AgentClaim),
    /// A concurrent claim by another session landed first; ours is ignored.
    LostRace(AgentClaim),
}

/// Configuration for the GitHub Projects v2 board.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BoardConfig {
    /// GitHub Project number
    pub project_number: u64,
    /// Project owner (user or org)
    pub owner: String,
    /// Repository name (owner/repo)
    pub repository: String,
    /// Custom field name mappings (logical key -> board field name)
    #[serde(default)]
    pub field_mappings: HashMap<String, String>,
    /// Claim timeout in seconds
    #[serde(default = "default_claim_timeout")]
    pub claim_timeout: i64,
    /// How often to renew claims
    #[serde(default = "default_renewal_interval")]
    pub claim_renewal_interval: i64,
    /// Enabled agent names
    #[serde(default)]
    pub enabled_agents: Vec<String>,
    /// Auto-file discovered issues
    #[serde(default = "default_true")]
    pub auto_discover: bool,
    /// Labels to exclude from the work queue
    #[serde(default)]
    pub exclude_labels: Vec<String>,
    /// Priority name -> labels implying that priority (fallback when the
    /// board Priority field is unset)
    #[serde(default)]
    pub priority_labels: HashMap<String, Vec<String>>,
    /// Type name -> labels implying that type (fallback when the board Type
    /// field is unset)
    #[serde(default)]
    pub type_labels: HashMap<String, Vec<String>>,
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
            type_labels: HashMap::new(),
        }
    }
}

impl BoardConfig {
    /// Default field mappings (logical key -> board field name).
    pub fn default_field_mappings() -> HashMap<String, String> {
        [
            ("status", "Status"),
            ("priority", "Priority"),
            ("agent", "Agent"),
            ("type", "Type"),
            ("blocked_by", "Blocked By"),
            ("discovered_from", "Discovered From"),
            ("size", "Estimated Size"),
        ]
        .into_iter()
        .map(|(k, v)| (k.to_string(), v.to_string()))
        .collect()
    }

    /// Board field name for a logical key.
    pub fn get_field_name(&self, key: &str) -> String {
        self.field_mappings
            .get(key)
            .cloned()
            .or_else(|| Self::default_field_mappings().remove(key))
            .unwrap_or_else(|| key.to_string())
    }

    /// Split `repository` into `(owner, name)`.
    pub fn repo_parts(&self) -> Option<(&str, &str)> {
        let (owner, name) = self.repository.split_once('/')?;
        (!owner.is_empty() && !name.is_empty() && !name.contains('/')).then_some((owner, name))
    }

    /// Priority implied by labels (highest priority wins).
    pub fn priority_from_labels(&self, labels: &[String]) -> Option<IssuePriority> {
        self.priority_labels
            .iter()
            .filter(|(_, ls)| {
                labels
                    .iter()
                    .any(|l| ls.iter().any(|x| x.eq_ignore_ascii_case(l)))
            })
            .filter_map(|(name, _)| name.parse::<IssuePriority>().ok())
            .min()
    }

    /// Type implied by labels (first match in [`IssueType::ALL`] order).
    pub fn type_from_labels(&self, labels: &[String]) -> Option<IssueType> {
        IssueType::ALL.iter().copied().find(|t| {
            self.type_labels.iter().any(|(name, ls)| {
                name.parse::<IssueType>().ok() == Some(*t)
                    && labels
                        .iter()
                        .any(|l| ls.iter().any(|x| x.eq_ignore_ascii_case(l)))
            })
        })
    }

    /// Whether an agent name is in the enabled list (case-insensitive,
    /// accepting both workflow names and board display names).
    pub fn is_agent_enabled(&self, agent: &str) -> bool {
        let wanted = normalize_agent_name(agent);
        self.enabled_agents
            .iter()
            .any(|a| normalize_agent_name(a).eq_ignore_ascii_case(&wanted))
    }
}

/// Agent name mappings (workflow names -> board field values).
const AGENT_NAME_MAP: &[(&str, &str)] = &[
    ("claude", "Claude Code"),
    ("opencode", "OpenCode"),
    ("crush", "Crush"),
    ("gemini", "Gemini CLI"),
    ("codex", "Codex"),
];

/// Map a workflow agent name (e.g. `claude`) to its board display name
/// (e.g. `Claude Code`). Unknown names are returned unchanged.
pub fn normalize_agent_name(name: &str) -> String {
    let trimmed = name.trim();
    AGENT_NAME_MAP
        .iter()
        .find(|(key, value)| {
            trimmed.eq_ignore_ascii_case(key) || trimmed.eq_ignore_ascii_case(value)
        })
        .map(|(_, value)| (*value).to_string())
        .unwrap_or_else(|| trimmed.to_string())
}

/// Whether two agent names refer to the same agent.
pub fn same_agent(a: &str, b: &str) -> bool {
    normalize_agent_name(a).eq_ignore_ascii_case(&normalize_agent_name(b))
}

/// Compact reference to an issue used in dependency graphs.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct IssueRef {
    pub number: u64,
    pub title: String,
    pub state: String,
    pub status: IssueStatus,
}

impl From<&Issue> for IssueRef {
    fn from(issue: &Issue) -> Self {
        Self {
            number: issue.number,
            title: issue.title.clone(),
            state: issue.state.clone(),
            status: issue.status,
        }
    }
}

/// Dependency relationships of one issue, built from a single board scan.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DependencyGraph {
    /// The issue itself
    pub issue: IssueRef,
    /// Issues blocking this one (that are on the board)
    pub blocked_by: Vec<IssueRef>,
    /// Blocker numbers referenced in the Blocked By field but not on the board
    pub missing_blockers: Vec<u64>,
    /// Issues this one blocks
    pub blocks: Vec<IssueRef>,
    /// Issues discovered from this one
    pub children: Vec<IssueRef>,
    /// Issue this one was discovered from
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parent: Option<IssueRef>,
    /// Whether every blocker is resolved (closed, Done or Abandoned).
    /// Blockers missing from the board count as unresolved.
    pub ready: bool,
}

/// An issue found via search with an approval trigger.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApprovedIssue {
    /// Issue number
    pub number: u64,
    /// Issue title
    pub title: String,
    /// Whether the issue is on the project board
    pub on_board: bool,
    /// Authorized user who approved it (None when verification was skipped)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub approver: Option<String>,
}

impl std::fmt::Display for ApprovedIssue {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let board_status = if self.on_board {
            "on board"
        } else {
            "NOT on board"
        };
        write!(f, "#{}: {} ({})", self.number, self.title, board_status)?;
        if let Some(approver) = &self.approver {
            write!(f, " approved by {}", approver)?;
        }
        Ok(())
    }
}

/// One stale claim handled (or reported, on dry run) by the janitor.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StaleClaim {
    pub issue: u64,
    pub title: String,
    pub agent: String,
    pub session_id: String,
    pub age_hours: f64,
}

/// Janitor run summary.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct JanitorReport {
    pub dry_run: bool,
    pub threshold_hours: f64,
    pub reset_status: IssueStatus,
    /// Number of In Progress issues inspected
    pub inspected: usize,
    /// Number of stale claims released (or that would be, on dry run)
    pub cleaned_count: usize,
    pub stale: Vec<StaleClaim>,
    /// In Progress issues with no claim comment at all (left untouched)
    pub unclaimed_in_progress: Vec<u64>,
    /// Issues whose stale claim could not be released (see stderr)
    pub failed: Vec<u64>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn status_parsing_is_lenient() {
        for s in [
            "In Progress",
            "in progress",
            "in_progress",
            "IN-PROGRESS",
            "InProgress",
        ] {
            assert_eq!(s.parse::<IssueStatus>(), Ok(IssueStatus::InProgress), "{s}");
        }
        assert_eq!("todo".parse::<IssueStatus>(), Ok(IssueStatus::Todo));
        let err = "invalid".parse::<IssueStatus>().unwrap_err();
        assert!(err.contains("Todo, In Progress"));
    }

    #[test]
    fn other_enums_parse() {
        assert_eq!("tech_debt".parse::<IssueType>(), Ok(IssueType::TechDebt));
        assert_eq!(
            "critical".parse::<IssuePriority>(),
            Ok(IssuePriority::Critical)
        );
        assert_eq!("xl".parse::<IssueSize>(), Ok(IssueSize::XL));
        assert_eq!(
            "pr-created".parse::<ReleaseReason>(),
            Ok(ReleaseReason::PrCreated)
        );
        assert_eq!(ReleaseReason::PrCreated.to_string(), "pr_created");
        assert!("nope".parse::<ReleaseReason>().is_err());
    }

    #[test]
    fn priority_ordering_sorts_critical_first() {
        let mut p = vec![
            IssuePriority::Low,
            IssuePriority::Critical,
            IssuePriority::Medium,
        ];
        p.sort();
        assert_eq!(
            p,
            vec![
                IssuePriority::Critical,
                IssuePriority::Medium,
                IssuePriority::Low
            ]
        );
    }

    #[test]
    fn release_reason_status() {
        assert_eq!(ReleaseReason::Completed.resulting_status(), None);
        assert_eq!(
            ReleaseReason::Blocked.resulting_status(),
            Some(IssueStatus::Blocked)
        );
        assert_eq!(
            ReleaseReason::Error.resulting_status(),
            Some(IssueStatus::Abandoned)
        );
    }

    #[test]
    fn board_config_defaults() {
        let config = BoardConfig::default();
        assert_eq!(config.claim_timeout, 86400);
        assert_eq!(config.get_field_name("status"), "Status");
        assert_eq!(config.get_field_name("size"), "Estimated Size");
        assert_eq!(config.get_field_name("custom"), "custom");
    }

    #[test]
    fn repo_parts_validation() {
        let mut c = BoardConfig {
            repository: "owner/repo".into(),
            ..Default::default()
        };
        assert_eq!(c.repo_parts(), Some(("owner", "repo")));
        for bad in ["owner", "/repo", "owner/", "a/b/c", ""] {
            c.repository = bad.into();
            assert_eq!(c.repo_parts(), None, "{bad}");
        }
    }

    #[test]
    fn label_fallbacks() {
        let mut c = BoardConfig::default();
        c.priority_labels
            .insert("high".into(), vec!["bug".into(), "regression".into()]);
        c.priority_labels
            .insert("critical".into(), vec!["security".into()]);
        c.type_labels.insert("bug".into(), vec!["bug".into()]);
        c.type_labels
            .insert("tech_debt".into(), vec!["refactor".into()]);

        let labels = vec!["Bug".to_string(), "security".to_string()];
        assert_eq!(
            c.priority_from_labels(&labels),
            Some(IssuePriority::Critical)
        );
        assert_eq!(c.type_from_labels(&labels), Some(IssueType::Bug));
        assert_eq!(
            c.type_from_labels(&["refactor".into()]),
            Some(IssueType::TechDebt)
        );
        assert_eq!(c.priority_from_labels(&["docs".into()]), None);
    }

    #[test]
    fn agent_name_normalization() {
        assert_eq!(normalize_agent_name("claude"), "Claude Code");
        assert_eq!(normalize_agent_name("CLAUDE"), "Claude Code");
        assert_eq!(normalize_agent_name("claude code"), "Claude Code");
        assert_eq!(normalize_agent_name("Unknown"), "Unknown");
        assert!(same_agent("claude", "Claude Code"));
        assert!(!same_agent("claude", "crush"));

        let c = BoardConfig {
            enabled_agents: vec!["claude".into()],
            ..Default::default()
        };
        assert!(c.is_agent_enabled("Claude Code"));
        assert!(!c.is_agent_enabled("codex"));
    }

    #[test]
    fn claim_expiry() {
        let t0 = DateTime::parse_from_rfc3339("2024-01-01T00:00:00Z")
            .unwrap()
            .with_timezone(&Utc);
        let claim = AgentClaim {
            issue_number: 1,
            agent: "claude".into(),
            session_id: "s".into(),
            timestamp: t0,
            renewed_at: None,
        };
        let later = t0 + chrono::Duration::hours(2);
        assert!(claim.is_expired_at(3600, later));
        assert!(!claim.is_expired_at(3 * 3600, later));

        let renewed = AgentClaim {
            renewed_at: Some(t0 + chrono::Duration::minutes(90)),
            ..claim
        };
        assert!(!renewed.is_expired_at(3600, later));
    }

    #[test]
    fn issue_dependency_resolution() {
        let issue = Issue {
            number: 1,
            title: "t".into(),
            body: String::new(),
            state: "open".into(),
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
        assert!(!issue.resolves_dependency());
        let closed = Issue {
            state: "closed".into(),
            ..issue.clone()
        };
        assert!(closed.resolves_dependency());
        let done = Issue {
            status: IssueStatus::Done,
            ..issue
        };
        assert!(done.resolves_dependency());
    }
}
