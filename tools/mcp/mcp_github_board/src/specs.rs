//! Declarative tool table.
//!
//! Each board tool is a [`ToolSpec`]: a name, a description, a JSON schema
//! and a `plan` function that turns validated, typed arguments into a
//! `board-manager` argument vector plus a hint on how to interpret the
//! result ([`Expect`]). Keeping this layer pure (no I/O) makes every
//! tool's argument mapping unit-testable.

use mcp_core::MCPError;
use serde::Deserialize;
use serde_json::{Value, json};

use crate::args::{
    self, IssueNumber, IssueType, LabelList, MAX_READY_LIMIT, MAX_THRESHOLD_HOURS, Priority,
    ReleaseReason, Size, Status,
};

/// How to interpret a successful `board-manager` result.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Expect {
    /// Any JSON value is a success.
    Value,
    /// The result carries a `success` boolean (claim / renew); `false` means
    /// the operation was refused and is reported as a tool error.
    Outcome,
    /// A JSON `null` means the issue is not on the project board.
    OnBoard(IssueNumber),
}

/// A planned `board-manager` invocation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Plan {
    /// Arguments after the global `--format json`.
    pub argv: Vec<String>,
    /// How to interpret the result.
    pub expect: Expect,
}

impl Plan {
    fn new(argv: Vec<String>) -> Self {
        Self {
            argv,
            expect: Expect::Value,
        }
    }

    fn expect(mut self, expect: Expect) -> Self {
        self.expect = expect;
        self
    }
}

/// Static description of one board tool.
pub struct ToolSpec {
    /// MCP tool name (stable; clients depend on it).
    pub name: &'static str,
    /// Description shown to the model.
    pub description: &'static str,
    /// Whether the tool changes board or issue state (excluded in read-only mode).
    pub mutating: bool,
    /// JSON schema of the arguments.
    pub schema: fn() -> Value,
    /// Validate arguments and build the invocation.
    pub plan: fn(Value) -> Result<Plan, MCPError>,
}

/// `--flag=value` (value can never be mistaken for another flag).
fn flag(name: &str, value: impl std::fmt::Display) -> String {
    format!("--{name}={value}")
}

fn s(v: &str) -> String {
    v.to_string()
}

// ============================================================================
// Shared schema fragments
// ============================================================================

fn issue_prop(description: &str) -> Value {
    json!({
        "type": "integer",
        "minimum": 1,
        "maximum": args::MAX_ISSUE_NUMBER,
        "description": description
    })
}

fn agent_prop(description: &str) -> Value {
    json!({
        "type": "string",
        "minLength": 1,
        "maxLength": args::MAX_AGENT_NAME_LEN,
        "description": description
    })
}

fn labels_prop(description: &str) -> Value {
    json!({
        "type": "array",
        "items": { "type": "string" },
        "maxItems": args::MAX_LABELS,
        "description": format!("{description} (array of label names; a comma-separated string is also accepted)")
    })
}

fn no_args_schema() -> Value {
    json!({ "type": "object", "properties": {} })
}

fn single_issue_schema() -> Value {
    json!({
        "type": "object",
        "properties": { "issue_number": issue_prop("Issue number") },
        "required": ["issue_number"]
    })
}

// ============================================================================
// Argument structs
// ============================================================================

#[derive(Deserialize)]
struct IssueArgs {
    issue_number: IssueNumber,
}

#[derive(Deserialize)]
struct ReadyArgs {
    agent_name: Option<String>,
    limit: Option<u64>,
    #[serde(default)]
    approved_only: bool,
    #[serde(default)]
    include_labels: LabelList,
    #[serde(default)]
    exclude_labels: LabelList,
}

#[derive(Deserialize)]
struct ClaimArgs {
    issue_number: IssueNumber,
    agent_name: String,
    session_id: String,
}

#[derive(Deserialize)]
struct ReleaseArgs {
    issue_number: IssueNumber,
    agent_name: String,
    reason: Option<ReleaseReason>,
}

#[derive(Deserialize)]
struct StatusArgs {
    issue_number: IssueNumber,
    status: Status,
}

#[derive(Deserialize)]
struct BlockerArgs {
    issue_number: IssueNumber,
    blocker_number: IssueNumber,
}

#[derive(Deserialize)]
struct ParentArgs {
    issue_number: IssueNumber,
    parent_number: IssueNumber,
}

#[derive(Deserialize)]
struct AddArgs {
    issue_number: IssueNumber,
    status: Option<Status>,
    priority: Option<Priority>,
    #[serde(rename = "type")]
    issue_type: Option<IssueType>,
    size: Option<Size>,
    agent_name: Option<String>,
}

#[derive(Deserialize)]
struct CheckApprovalArgs {
    issue_number: IssueNumber,
    agent_name: Option<String>,
}

#[derive(Deserialize)]
struct FindApprovedArgs {
    agent_name: Option<String>,
    #[serde(default)]
    unverified: bool,
}

#[derive(Deserialize)]
struct JanitorArgs {
    agent_name: Option<String>,
    threshold_hours: Option<f64>,
    reset_status: Option<Status>,
    dry_run: Option<bool>,
}

fn distinct(a: IssueNumber, b: IssueNumber, what: &str) -> Result<(), MCPError> {
    if a == b {
        Err(MCPError::InvalidParameters(format!(
            "an issue cannot be its own {what} ({a})"
        )))
    } else {
        Ok(())
    }
}

// ============================================================================
// The tool table
// ============================================================================

/// All board tools, in the order they are registered.
pub const SPECS: &[ToolSpec] = &[
    ToolSpec {
        name: "query_ready_work",
        description: "Get ready work from the board: open issues with status Todo whose blockers are \
all resolved and that are unassigned or assigned to the given agent, highest priority first.\n\n\
Use approved_only to keep only issues carrying an [Approved][Agent] trigger from an authorized \
user (naming agent_name when given). Label filters are case-insensitive. Returns \
{success, result: [issue, ...]}.",
        mutating: false,
        schema: || {
            json!({
                "type": "object",
                "properties": {
                    "agent_name": agent_prop("Only issues unassigned or assigned to this agent (e.g. 'claude')"),
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_READY_LIMIT,
                        "default": 10,
                        "description": "Maximum number of issues to return"
                    },
                    "approved_only": {
                        "type": "boolean",
                        "default": false,
                        "description": "Only issues with an [Approved][Agent] trigger from an authorized user"
                    },
                    "include_labels": labels_prop("Only issues with at least one of these labels"),
                    "exclude_labels": labels_prop("Skip issues with any of these labels")
                }
            })
        },
        plan: |v| {
            let a: ReadyArgs = args::parse(v)?;
            let limit = a.limit.unwrap_or(10);
            if !(1..=MAX_READY_LIMIT).contains(&limit) {
                return Err(MCPError::InvalidParameters(format!(
                    "'limit' must be between 1 and {MAX_READY_LIMIT}"
                )));
            }
            let mut argv = vec![s("ready"), flag("limit", limit)];
            if let Some(agent) = args::opt_agent_name(a.agent_name.as_deref())? {
                argv.push(flag("agent", agent));
            }
            if a.approved_only {
                argv.push(s("--approved-only"));
            }
            if let Some(l) = a.include_labels.to_arg("include_labels")? {
                argv.push(flag("include-labels", l));
            }
            if let Some(l) = a.exclude_labels.to_arg("exclude_labels")? {
                argv.push(flag("exclude-labels", l));
            }
            Ok(Plan::new(argv))
        },
    },
    ToolSpec {
        name: "claim_work",
        description: "Claim an issue for implementation.\n\n\
Posts an [Agent Claim] comment and sets the issue In Progress. Fails (isError, success=false \
with claimed_by) if another agent holds an unexpired claim or wins a concurrent race. Keep \
session_id and pass it to renew_claim for long tasks; release with release_work when done.",
        mutating: true,
        schema: || {
            json!({
                "type": "object",
                "properties": {
                    "issue_number": issue_prop("Issue number to claim"),
                    "agent_name": agent_prop("Agent claiming the issue (e.g. 'claude')"),
                    "session_id": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": args::MAX_SESSION_ID_LEN,
                        "description": "Unique session identifier; reuse it for renew_claim"
                    }
                },
                "required": ["issue_number", "agent_name", "session_id"]
            })
        },
        plan: |v| {
            let a: ClaimArgs = args::parse(v)?;
            Ok(Plan::new(vec![
                s("claim"),
                a.issue_number.arg(),
                flag("agent", args::agent_name(&a.agent_name)?),
                flag("session", args::session_id(&a.session_id)?),
            ])
            .expect(Expect::Outcome))
        },
    },
    ToolSpec {
        name: "renew_claim",
        description: "Renew an active claim for long-running tasks.\n\n\
Posts a [Claim Renewal] comment so the claim does not expire (claims expire after the board's \
work_claims.timeout, 24h by default). Fails (isError, success=false) if the agent does not \
hold the active claim; claim it again with claim_work in that case.",
        mutating: true,
        schema: || {
            json!({
                "type": "object",
                "properties": {
                    "issue_number": issue_prop("Issue number with an active claim"),
                    "agent_name": agent_prop("Agent that holds the claim"),
                    "session_id": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": args::MAX_SESSION_ID_LEN,
                        "description": "Session identifier used for the original claim"
                    }
                },
                "required": ["issue_number", "agent_name", "session_id"]
            })
        },
        plan: |v| {
            let a: ClaimArgs = args::parse(v)?;
            Ok(Plan::new(vec![
                s("renew"),
                a.issue_number.arg(),
                flag("agent", args::agent_name(&a.agent_name)?),
                flag("session", args::session_id(&a.session_id)?),
            ])
            .expect(Expect::Outcome))
        },
    },
    ToolSpec {
        name: "release_work",
        description: "Release a claim on an issue so other agents can pick it up.\n\n\
Posts an [Agent Release] comment. Reasons: completed (default) and pr_created keep the current \
status; blocked sets Blocked; abandoned and error set Abandoned.",
        mutating: true,
        schema: || {
            json!({
                "type": "object",
                "properties": {
                    "issue_number": issue_prop("Issue number to release"),
                    "agent_name": agent_prop("Agent releasing the claim"),
                    "reason": {
                        "type": "string",
                        "enum": ReleaseReason::names(),
                        "default": "completed",
                        "description": "Why the claim is released"
                    }
                },
                "required": ["issue_number", "agent_name"]
            })
        },
        plan: |v| {
            let a: ReleaseArgs = args::parse(v)?;
            let reason = a.reason.unwrap_or(ReleaseReason::Completed);
            Ok(Plan::new(vec![
                s("release"),
                a.issue_number.arg(),
                flag("agent", args::agent_name(&a.agent_name)?),
                flag("reason", reason.as_str()),
            ]))
        },
    },
    ToolSpec {
        name: "update_status",
        description: "Set the Status field of an issue on the project board.\n\n\
Accepted values: Todo, In Progress, Blocked, Done, Abandoned (case and separators are ignored, \
so 'in_progress' works). The issue must already be on the board (see add_to_board).",
        mutating: true,
        schema: || {
            json!({
                "type": "object",
                "properties": {
                    "issue_number": issue_prop("Issue number to update"),
                    "status": {
                        "type": "string",
                        "enum": Status::names(),
                        "description": "New status"
                    }
                },
                "required": ["issue_number", "status"]
            })
        },
        plan: |v| {
            let a: StatusArgs = args::parse(v)?;
            Ok(Plan::new(vec![
                s("status"),
                a.issue_number.arg(),
                flag("status", a.status.as_str()),
            ]))
        },
    },
    ToolSpec {
        name: "add_blocker",
        description: "Record that an issue is blocked by another issue.\n\n\
Adds blocker_number to the issue's Blocked By field. A blocked issue is not returned by \
query_ready_work until every blocker is closed, Done or Abandoned.",
        mutating: true,
        schema: || {
            json!({
                "type": "object",
                "properties": {
                    "issue_number": issue_prop("Issue that is blocked"),
                    "blocker_number": issue_prop("Issue that blocks it")
                },
                "required": ["issue_number", "blocker_number"]
            })
        },
        plan: |v| {
            let a: BlockerArgs = args::parse(v)?;
            distinct(a.issue_number, a.blocker_number, "blocker")?;
            Ok(Plan::new(vec![
                s("block"),
                a.issue_number.arg(),
                flag("blocker", a.blocker_number.0),
            ]))
        },
    },
    ToolSpec {
        name: "remove_blocker",
        description: "Remove a blocking dependency (the inverse of add_blocker).\n\n\
Removes blocker_number from the issue's Blocked By field; the field is cleared when no \
blockers remain.",
        mutating: true,
        schema: || {
            json!({
                "type": "object",
                "properties": {
                    "issue_number": issue_prop("Issue that is blocked"),
                    "blocker_number": issue_prop("Blocker to remove")
                },
                "required": ["issue_number", "blocker_number"]
            })
        },
        plan: |v| {
            let a: BlockerArgs = args::parse(v)?;
            distinct(a.issue_number, a.blocker_number, "blocker")?;
            Ok(Plan::new(vec![
                s("unblock"),
                a.issue_number.arg(),
                flag("blocker", a.blocker_number.0),
            ]))
        },
    },
    ToolSpec {
        name: "mark_discovered_from",
        description: "Mark an issue as discovered while working on a parent issue.\n\n\
Sets the child's Discovered From field, which get_dependency_graph reports as parent/children.",
        mutating: true,
        schema: || {
            json!({
                "type": "object",
                "properties": {
                    "issue_number": issue_prop("Child (newly discovered) issue"),
                    "parent_number": issue_prop("Parent issue it was discovered from")
                },
                "required": ["issue_number", "parent_number"]
            })
        },
        plan: |v| {
            let a: ParentArgs = args::parse(v)?;
            distinct(a.issue_number, a.parent_number, "parent")?;
            Ok(Plan::new(vec![
                s("discover-from"),
                a.issue_number.arg(),
                flag("parent", a.parent_number.0),
            ]))
        },
    },
    ToolSpec {
        name: "get_issue_details",
        description: "Get board details for one issue: title, state, status, priority, type, size, \
agent, blocked_by, discovered_from, labels and URL.\n\n\
Returns an error if the issue is not on the project board.",
        mutating: false,
        schema: single_issue_schema,
        plan: |v| {
            let a: IssueArgs = args::parse(v)?;
            Ok(Plan::new(vec![s("info"), a.issue_number.arg()])
                .expect(Expect::OnBoard(a.issue_number)))
        },
    },
    ToolSpec {
        name: "get_dependency_graph",
        description: "Get the dependency graph of an issue: the issues blocking it (and blockers \
missing from the board), the issues it blocks, its parent, its children, and whether it is \
ready to work on.\n\nReturns an error if the issue is not on the project board.",
        mutating: false,
        schema: single_issue_schema,
        plan: |v| {
            let a: IssueArgs = args::parse(v)?;
            Ok(Plan::new(vec![s("deps"), a.issue_number.arg()])
                .expect(Expect::OnBoard(a.issue_number)))
        },
    },
    ToolSpec {
        name: "list_agents",
        description: "List the agents enabled for this board (agents.enabled_agents in the board \
config).",
        mutating: false,
        schema: no_args_schema,
        plan: |v| {
            let _: serde::de::IgnoredAny = args::parse(v)?;
            Ok(Plan::new(vec![s("agents")]))
        },
    },
    ToolSpec {
        name: "get_board_config",
        description: "Get the effective board configuration: project number/owner, repository, \
field names, enabled agents, claim timeout and work-queue settings.",
        mutating: false,
        schema: no_args_schema,
        plan: |v| {
            let _: serde::de::IgnoredAny = args::parse(v)?;
            Ok(Plan::new(vec![s("config")]))
        },
    },
    ToolSpec {
        name: "add_to_board",
        description: "Add an existing repository issue to the project board with initial fields.\n\n\
If the issue is already on the board nothing changes and already_on_board=true is returned. \
Fields that do not exist on the board are reported as warnings. When agent_name is omitted \
board-manager assigns 'Claude Code'.",
        mutating: true,
        schema: || {
            json!({
                "type": "object",
                "properties": {
                    "issue_number": issue_prop("Issue number to add"),
                    "status": {
                        "type": "string",
                        "enum": Status::names(),
                        "default": "Todo",
                        "description": "Initial status"
                    },
                    "priority": {
                        "type": "string",
                        "enum": Priority::names(),
                        "description": "Priority"
                    },
                    "type": {
                        "type": "string",
                        "enum": IssueType::names(),
                        "description": "Issue type"
                    },
                    "size": {
                        "type": "string",
                        "enum": Size::names(),
                        "description": "Estimated size"
                    },
                    "agent_name": agent_prop("Assigned agent (workflow name like 'claude' or board name)")
                },
                "required": ["issue_number"]
            })
        },
        plan: |v| {
            let a: AddArgs = args::parse(v)?;
            let status = a.status.unwrap_or(Status::Todo);
            let mut argv = vec![
                s("add-to-board"),
                a.issue_number.arg(),
                flag("status", status.as_str()),
            ];
            if let Some(p) = a.priority {
                argv.push(flag("priority", p.as_str()));
            }
            if let Some(t) = a.issue_type {
                argv.push(flag("type", t.as_str()));
            }
            if let Some(sz) = a.size {
                argv.push(flag("size", sz.as_str()));
            }
            if let Some(agent) = args::opt_agent_name(a.agent_name.as_deref())? {
                argv.push(flag("agent", agent));
            }
            Ok(Plan::new(argv))
        },
    },
    ToolSpec {
        name: "check_approval",
        description: "Check whether an issue carries an [Approved][Agent] trigger from an \
authorized user (project owner, repository owner or security.agent_admins).\n\n\
With agent_name, the trigger must name that agent. Returns {approved, issue, approver}.",
        mutating: false,
        schema: || {
            json!({
                "type": "object",
                "properties": {
                    "issue_number": issue_prop("Issue number to check"),
                    "agent_name": agent_prop("Require the trigger to name this agent")
                },
                "required": ["issue_number"]
            })
        },
        plan: |v| {
            let a: CheckApprovalArgs = args::parse(v)?;
            let mut argv = vec![s("check-approval"), a.issue_number.arg()];
            if let Some(agent) = args::opt_agent_name(a.agent_name.as_deref())? {
                argv.push(flag("agent", agent));
            }
            Ok(Plan::new(argv))
        },
    },
    ToolSpec {
        name: "find_approved_issues",
        description: "Search open issues that have an [Approved][Agent] comment for an agent \
(default 'claude'), whether or not they are on the board.\n\n\
Hits are verified to come from an authorized approver unless unverified=true. Returns \
[{number, title, on_board, approver}].",
        mutating: false,
        schema: || {
            json!({
                "type": "object",
                "properties": {
                    "agent_name": agent_prop("Agent named in the trigger (default 'claude')"),
                    "unverified": {
                        "type": "boolean",
                        "default": false,
                        "description": "Return raw search hits without verifying the approver"
                    }
                }
            })
        },
        plan: |v| {
            let a: FindApprovedArgs = args::parse(v)?;
            let agent =
                args::opt_agent_name(a.agent_name.as_deref())?.unwrap_or_else(|| s("claude"));
            let mut argv = vec![s("find-approved"), flag("agent", agent)];
            if a.unverified {
                argv.push(s("--unverified"));
            }
            Ok(Plan::new(argv))
        },
    },
    ToolSpec {
        name: "release_stale_claims",
        description: "Find In Progress issues whose claim has had no activity for threshold_hours \
(default: the board's claim timeout), release those claims and reset their status.\n\n\
Defaults to dry_run=true, which only reports what would be cleaned; pass dry_run=false to \
apply. Issues In Progress without any claim comment are reported, never touched.",
        mutating: true,
        schema: || {
            json!({
                "type": "object",
                "properties": {
                    "agent_name": agent_prop("Only consider claims held by this agent"),
                    "threshold_hours": {
                        "type": "number",
                        "exclusiveMinimum": 0,
                        "maximum": MAX_THRESHOLD_HOURS,
                        "description": "Hours without claim activity before a claim is stale"
                    },
                    "reset_status": {
                        "type": "string",
                        "enum": Status::names(),
                        "default": "Todo",
                        "description": "Status to reset stale issues to"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "default": true,
                        "description": "Only report; set false to release claims"
                    }
                }
            })
        },
        plan: |v| {
            let a: JanitorArgs = args::parse(v)?;
            let mut argv = vec![s("janitor")];
            if let Some(agent) = args::opt_agent_name(a.agent_name.as_deref())? {
                argv.push(flag("agent", agent));
            }
            if let Some(h) = a.threshold_hours {
                if !h.is_finite() || h <= 0.0 || h > MAX_THRESHOLD_HOURS {
                    return Err(MCPError::InvalidParameters(format!(
                        "'threshold_hours' must be > 0 and <= {MAX_THRESHOLD_HOURS}"
                    )));
                }
                argv.push(flag("threshold", h));
            }
            argv.push(flag(
                "reset-status",
                a.reset_status.unwrap_or(Status::Todo).as_str(),
            ));
            if a.dry_run.unwrap_or(true) {
                argv.push(s("--dry-run"));
            }
            Ok(Plan::new(argv))
        },
    },
];

/// Look up a spec by tool name.
#[cfg(test)]
pub fn find(name: &str) -> Option<&'static ToolSpec> {
    SPECS.iter().find(|s| s.name == name)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn plan(name: &str, v: Value) -> Result<Plan, MCPError> {
        (find(name).unwrap_or_else(|| panic!("no tool {name}")).plan)(v)
    }

    fn argv(name: &str, v: Value) -> Vec<String> {
        plan(name, v).unwrap_or_else(|e| panic!("{name}: {e}")).argv
    }

    fn invalid(name: &str, v: Value) -> String {
        match plan(name, v.clone()) {
            Err(MCPError::InvalidParameters(m)) => m,
            other => panic!("{name} {v}: expected InvalidParameters, got {other:?}"),
        }
    }

    #[test]
    fn names_are_unique() {
        let mut names: Vec<_> = SPECS.iter().map(|s| s.name).collect();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), SPECS.len());
    }

    #[test]
    fn schemas_are_consistent() {
        for spec in SPECS {
            let schema = (spec.schema)();
            assert_eq!(schema["type"], "object", "{}", spec.name);
            let props = schema["properties"]
                .as_object()
                .unwrap_or_else(|| panic!("{} has no properties", spec.name));
            if let Some(req) = schema.get("required") {
                for r in req.as_array().unwrap() {
                    assert!(
                        props.contains_key(r.as_str().unwrap()),
                        "{}: required '{r}' not in properties",
                        spec.name
                    );
                }
            }
            assert!(!spec.description.is_empty());
        }
    }

    #[test]
    fn ready_defaults_and_filters() {
        assert_eq!(
            argv("query_ready_work", json!({})),
            vec!["ready", "--limit=10"]
        );
        assert_eq!(
            argv(
                "query_ready_work",
                json!({
                    "agent_name": "claude",
                    "limit": 5,
                    "approved_only": true,
                    "include_labels": ["bug", "ui"],
                    "exclude_labels": "wontfix"
                })
            ),
            vec![
                "ready",
                "--limit=5",
                "--agent=claude",
                "--approved-only",
                "--include-labels=bug,ui",
                "--exclude-labels=wontfix"
            ]
        );
        // Blank agent is treated as "no filter"
        assert_eq!(
            argv("query_ready_work", json!({"agent_name": " "})),
            vec!["ready", "--limit=10"]
        );
        invalid("query_ready_work", json!({"limit": 0}));
        invalid("query_ready_work", json!({"limit": MAX_READY_LIMIT + 1}));
        invalid("query_ready_work", json!({"limit": -1}));
        invalid("query_ready_work", json!({"limit": "ten"}));
    }

    #[test]
    fn claim_and_renew() {
        let a = json!({"issue_number": 42, "agent_name": "claude", "session_id": "s-1"});
        let p = plan("claim_work", a.clone()).unwrap();
        assert_eq!(
            p.argv,
            vec!["claim", "42", "--agent=claude", "--session=s-1"]
        );
        assert_eq!(p.expect, Expect::Outcome);
        let p = plan("renew_claim", a).unwrap();
        assert_eq!(
            p.argv,
            vec!["renew", "42", "--agent=claude", "--session=s-1"]
        );
        assert_eq!(p.expect, Expect::Outcome);

        let msg = invalid("claim_work", json!({"issue_number": 1, "agent_name": "a"}));
        assert!(msg.contains("session_id"), "{msg}");
        invalid(
            "claim_work",
            json!({"issue_number": 1, "agent_name": "", "session_id": "s"}),
        );
        invalid(
            "claim_work",
            json!({"issue_number": 0, "agent_name": "a", "session_id": "s"}),
        );
    }

    #[test]
    fn values_starting_with_dashes_stay_values() {
        // A hostile agent name cannot inject a flag: it stays inside --agent=...
        let v = argv(
            "claim_work",
            json!({"issue_number": 1, "agent_name": "--config=/etc/x", "session_id": "-s"}),
        );
        assert_eq!(
            v,
            vec!["claim", "1", "--agent=--config=/etc/x", "--session=-s"]
        );
    }

    #[test]
    fn release_reasons() {
        assert_eq!(
            argv(
                "release_work",
                json!({"issue_number": 3, "agent_name": "claude"})
            ),
            vec!["release", "3", "--agent=claude", "--reason=completed"]
        );
        assert_eq!(
            argv(
                "release_work",
                json!({"issue_number": 3, "agent_name": "claude", "reason": "PR_CREATED"})
            ),
            vec!["release", "3", "--agent=claude", "--reason=pr_created"]
        );
        invalid(
            "release_work",
            json!({"issue_number": 3, "agent_name": "claude", "reason": "bored"}),
        );
    }

    #[test]
    fn status_is_canonicalized() {
        assert_eq!(
            argv(
                "update_status",
                json!({"issue_number": "#12", "status": "in_progress"})
            ),
            vec!["status", "12", "--status=In Progress"]
        );
        let msg = invalid(
            "update_status",
            json!({"issue_number": 12, "status": "Later"}),
        );
        assert!(msg.contains("expected one of"), "{msg}");
    }

    #[test]
    fn dependency_tools() {
        assert_eq!(
            argv(
                "add_blocker",
                json!({"issue_number": 5, "blocker_number": 3})
            ),
            vec!["block", "5", "--blocker=3"]
        );
        assert_eq!(
            argv(
                "remove_blocker",
                json!({"issue_number": 5, "blocker_number": 3})
            ),
            vec!["unblock", "5", "--blocker=3"]
        );
        assert_eq!(
            argv(
                "mark_discovered_from",
                json!({"issue_number": 5, "parent_number": 1})
            ),
            vec!["discover-from", "5", "--parent=1"]
        );
        invalid(
            "add_blocker",
            json!({"issue_number": 5, "blocker_number": 5}),
        );
        invalid(
            "remove_blocker",
            json!({"issue_number": 5, "blocker_number": 5}),
        );
        invalid(
            "mark_discovered_from",
            json!({"issue_number": 5, "parent_number": 5}),
        );
    }

    #[test]
    fn lookups_use_the_right_subcommands() {
        let p = plan("get_issue_details", json!({"issue_number": 9})).unwrap();
        assert_eq!(p.argv, vec!["info", "9"]);
        assert_eq!(p.expect, Expect::OnBoard(IssueNumber(9)));
        // get_dependency_graph must use `deps`, not `info`.
        let p = plan("get_dependency_graph", json!({"issue_number": 9})).unwrap();
        assert_eq!(p.argv, vec!["deps", "9"]);
        assert_eq!(argv("list_agents", json!({})), vec!["agents"]);
        assert_eq!(argv("get_board_config", Value::Null), vec!["config"]);
    }

    #[test]
    fn add_to_board_fields() {
        assert_eq!(
            argv("add_to_board", json!({"issue_number": 7})),
            vec!["add-to-board", "7", "--status=Todo"]
        );
        assert_eq!(
            argv(
                "add_to_board",
                json!({
                    "issue_number": 7, "status": "blocked", "priority": "high",
                    "type": "tech debt", "size": "m", "agent_name": "claude"
                })
            ),
            vec![
                "add-to-board",
                "7",
                "--status=Blocked",
                "--priority=High",
                "--type=Tech Debt",
                "--size=M",
                "--agent=claude"
            ]
        );
        invalid("add_to_board", json!({"issue_number": 7, "size": "huge"}));
    }

    #[test]
    fn approval_tools() {
        assert_eq!(
            argv("check_approval", json!({"issue_number": 4})),
            vec!["check-approval", "4"]
        );
        assert_eq!(
            argv(
                "check_approval",
                json!({"issue_number": 4, "agent_name": "claude"})
            ),
            vec!["check-approval", "4", "--agent=claude"]
        );
        assert_eq!(
            argv("find_approved_issues", json!({})),
            vec!["find-approved", "--agent=claude"]
        );
        assert_eq!(
            argv(
                "find_approved_issues",
                json!({"agent_name": "crush", "unverified": true})
            ),
            vec!["find-approved", "--agent=crush", "--unverified"]
        );
    }

    #[test]
    fn janitor_defaults_to_dry_run() {
        assert_eq!(
            argv("release_stale_claims", json!({})),
            vec!["janitor", "--reset-status=Todo", "--dry-run"]
        );
        assert_eq!(
            argv(
                "release_stale_claims",
                json!({"agent_name": "claude", "threshold_hours": 2.5,
                       "reset_status": "abandoned", "dry_run": false})
            ),
            vec![
                "janitor",
                "--agent=claude",
                "--threshold=2.5",
                "--reset-status=Abandoned"
            ]
        );
        invalid("release_stale_claims", json!({"threshold_hours": 0}));
        invalid("release_stale_claims", json!({"threshold_hours": -1}));
        invalid(
            "release_stale_claims",
            json!({"threshold_hours": MAX_THRESHOLD_HOURS + 1.0}),
        );
    }

    #[test]
    fn wrong_types_are_rejected_not_panicking() {
        for spec in SPECS {
            for bad in [json!([1]), json!("x"), json!(3)] {
                assert!(
                    matches!((spec.plan)(bad), Err(MCPError::InvalidParameters(_))),
                    "{}",
                    spec.name
                );
            }
        }
    }
}
