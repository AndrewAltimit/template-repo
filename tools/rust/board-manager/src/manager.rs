//! GitHub Projects v2 board operations.
//!
//! Network access lives here; parsing and decision logic is delegated to the
//! pure modules (`board`, `claims`, `approval`) so it can be unit-tested.
//!
//! Round-trip budget per command (after the one-time project lookup, which
//! also loads every field definition):
//! - single-issue commands look the issue up directly through
//!   `Issue.projectItems` instead of paginating the whole board;
//! - approval checks for many issues are batched into aliased queries;
//! - full board scans are only used where the whole board is needed
//!   (`ready`, `deps`, `janitor`, `find-approved`).

use chrono::Utc;
use serde_json::{Value, json};
use std::collections::{HashMap, HashSet};
use tracing::{debug, info, warn};

use crate::approval::{self, APPROVAL_BATCH_SIZE, ApprovalPolicy, BatchApproval};
use crate::board::{self, FieldKind, ProjectFields, ReadyFilter};
use crate::claims;
use crate::client::GraphQLClient;
use crate::error::{BoardError, Result};
use crate::models::{
    AgentClaim, ApprovedIssue, BoardConfig, ClaimOutcome, DependencyGraph, Issue, IssuePriority,
    IssueSize, IssueStatus, IssueType, JanitorReport, ReleaseReason, StaleClaim,
    normalize_agent_name, same_agent,
};
use crate::queries;
use crate::security::TrustConfig;

/// Safety cap on board pages (100 items each).
const MAX_BOARD_PAGES: usize = 50;

/// Safety cap on comment pages when checking approval (100 comments each).
const MAX_COMMENT_PAGES: usize = 20;

/// GitHub search returns at most 1000 results (10 pages of 100).
const MAX_SEARCH_PAGES: usize = 10;

/// Resolved project metadata.
#[derive(Debug)]
struct ProjectInfo {
    id: String,
    title: String,
    fields: ProjectFields,
}

/// Result of looking an issue up directly (without scanning the board).
#[derive(Debug, Clone)]
pub struct IssueLookup {
    /// GraphQL node ID of the issue (for comments / adding to the board)
    pub node_id: String,
    /// Issue data; board fields are populated only when `on_board`
    pub issue: Issue,
    /// Whether the issue has an item on the configured project
    pub on_board: bool,
}

impl IssueLookup {
    fn item_id(&self) -> Result<&str> {
        self.issue
            .project_item_id
            .as_deref()
            .filter(|_| self.on_board)
            .ok_or(BoardError::NotOnBoard(self.issue.number))
    }
}

/// Parse an `ISSUE_ITEM` response. Pure so it can be tested.
pub fn parse_issue_lookup(
    data: &Value,
    number: u64,
    project_id: &str,
    config: &BoardConfig,
) -> Result<IssueLookup> {
    let issue = data
        .get("repository")
        .and_then(|r| r.get("issue"))
        .filter(|i| !i.is_null())
        .ok_or(BoardError::IssueNotFound(number))?;
    let node_id = issue
        .get("id")
        .and_then(Value::as_str)
        .ok_or(BoardError::IssueNotFound(number))?
        .to_string();

    let empty = Vec::new();
    let items = issue
        .get("projectItems")
        .and_then(|p| p.get("nodes"))
        .and_then(Value::as_array)
        .unwrap_or(&empty);
    let item = items.iter().find(|i| {
        i.get("project")
            .and_then(|p| p.get("id"))
            .and_then(Value::as_str)
            == Some(project_id)
    });

    let on_board = item.is_some();
    let placeholder = json!({});
    let parsed = board::issue_from_item(item.unwrap_or(&placeholder), issue, config)
        .ok_or(BoardError::IssueNotFound(number))?;

    Ok(IssueLookup {
        node_id,
        issue: parsed,
        on_board,
    })
}

/// A value to write into a project field.
#[derive(Debug, Clone)]
pub enum FieldInput<'a> {
    /// Single-select option by name.
    Option(&'a str),
    /// Free text.
    Text(String),
    /// Clear the field.
    Clear,
}

/// Optional fields for `add-to-board`.
#[derive(Debug, Clone, Default)]
pub struct AddOptions {
    pub priority: Option<IssuePriority>,
    pub issue_type: Option<IssueType>,
    pub size: Option<IssueSize>,
    pub agent: Option<String>,
}

/// Janitor options.
#[derive(Debug, Clone)]
pub struct JanitorOptions {
    pub agent: Option<String>,
    pub threshold_secs: i64,
    pub reset_status: IssueStatus,
    pub dry_run: bool,
}

/// Manager for GitHub Projects v2 board operations.
pub struct BoardManager {
    client: GraphQLClient,
    config: BoardConfig,
    project: Option<ProjectInfo>,
    /// Users whose `[Approved][Agent]` triggers count (lowercase logins).
    allowed_approvers: HashSet<String>,
    /// Authors whose claim/renewal/release comments count (see
    /// [`approval::author_key`] for normalization).
    claim_authors: HashSet<String>,
}

/// Lowercased set of logins.
fn lower_set<'a>(names: impl IntoIterator<Item = &'a String>) -> HashSet<String> {
    names
        .into_iter()
        .map(|n| n.trim().to_lowercase())
        .filter(|n| !n.is_empty())
        .collect()
}

/// Users allowed to approve work: project owner, repository owner and
/// `security.agent_admins` (when `.agents.yaml` loaded).
pub fn approver_set(config: &BoardConfig, trust: Option<&TrustConfig>) -> HashSet<String> {
    let mut set = lower_set(trust.map(|t| &t.agent_admins).into_iter().flatten());
    set.extend(lower_set([&config.owner]));
    if let Some((repo_owner, _)) = config.repo_parts() {
        set.insert(repo_owner.to_lowercase());
    }
    set
}

/// Authors whose claim comments are trusted: `security.agent_admins` and
/// `security.trusted_sources`. Fails closed to the repository owner only
/// when `.agents.yaml` could not be loaded.
pub fn claim_author_set(config: &BoardConfig, trust: Option<&TrustConfig>) -> HashSet<String> {
    match trust {
        Some(t) => lower_set(t.agent_admins.iter().chain(&t.trusted_sources)),
        None => config
            .repo_parts()
            .map(|(owner, _)| HashSet::from([owner.to_lowercase()]))
            .unwrap_or_default(),
    }
}

impl BoardManager {
    /// Create a new manager. Call [`BoardManager::initialize`] before use.
    pub fn new(config: BoardConfig, token: String) -> Result<Self> {
        let client = GraphQLClient::new(token)?;

        let trust = match TrustConfig::from_yaml(None) {
            Ok(t) => Some(t),
            Err(e) => {
                warn!(
                    "Could not load .agents.yaml ({}); only project/repository owners can \
                     approve, and only repository-owner claim comments are trusted",
                    e
                );
                None
            },
        };

        Ok(Self {
            client,
            allowed_approvers: approver_set(&config, trust.as_ref()),
            claim_authors: claim_author_set(&config, trust.as_ref()),
            config,
            project: None,
        })
    }

    /// Resolve the project ID and field definitions (one API call).
    pub async fn initialize(&mut self) -> Result<()> {
        let data = self
            .client
            .query(
                queries::PROJECT,
                json!({ "owner": self.config.owner, "number": self.config.project_number }),
            )
            .await?;

        let project = ["user", "organization"]
            .iter()
            .find_map(|k| data.get(k)?.get("projectV2").filter(|p| !p.is_null()))
            .ok_or_else(|| {
                BoardError::BoardNotFound(format!(
                    "Project #{} not found for owner '{}' (check project.number/owner and \
                     that the token has project scope)",
                    self.config.project_number, self.config.owner
                ))
            })?;

        let id = project
            .get("id")
            .and_then(Value::as_str)
            .ok_or_else(|| BoardError::GraphQL("Project ID missing in response".into()))?;
        let fields = project
            .get("fields")
            .and_then(|f| f.get("nodes"))
            .and_then(Value::as_array)
            .map(|n| ProjectFields::from_nodes(n))
            .unwrap_or_default();

        info!(
            "Board initialized: project {} ({} fields)",
            id,
            fields.field_count()
        );
        self.project = Some(ProjectInfo {
            id: id.to_string(),
            title: project
                .get("title")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string(),
            fields,
        });
        Ok(())
    }

    fn project(&self) -> Result<&ProjectInfo> {
        self.project
            .as_ref()
            .ok_or_else(|| BoardError::Config("BoardManager not initialized".to_string()))
    }

    /// Project title (after initialization).
    pub fn project_title(&self) -> Option<&str> {
        self.project.as_ref().map(|p| p.title.as_str())
    }

    /// Enabled agents from configuration.
    pub fn get_enabled_agents(&self) -> &[String] {
        &self.config.enabled_agents
    }

    /// Board configuration.
    pub fn get_config(&self) -> &BoardConfig {
        &self.config
    }

    fn repo(&self) -> Result<(&str, &str)> {
        self.config.repo_parts().ok_or_else(|| {
            BoardError::Config(format!(
                "Invalid repository format: '{}'",
                self.config.repository
            ))
        })
    }

    fn repo_vars(&self, number: u64) -> Result<Value> {
        let (owner, repo) = self.repo()?;
        Ok(json!({ "owner": owner, "repo": repo, "number": number }))
    }

    // ===== Board scans =====

    /// Fetch all board item nodes using `query` (must accept `$projectId`
    /// and `$cursor` and select `items { pageInfo nodes }`).
    async fn fetch_items(&self, query: &str) -> Result<Vec<Value>> {
        let project_id = &self.project()?.id;
        let mut items = Vec::new();
        let mut cursor: Option<String> = None;

        for page in 1..=MAX_BOARD_PAGES {
            let mut data = self
                .client
                .query(query, json!({ "projectId": project_id, "cursor": cursor }))
                .await?;
            let mut conn = data
                .get_mut("node")
                .and_then(|n| n.get_mut("items"))
                .map(Value::take)
                .ok_or_else(|| {
                    BoardError::GraphQL("Project items missing in response".to_string())
                })?;

            cursor = approval::next_cursor(Some(&conn));
            if let Some(Value::Array(nodes)) = conn.get_mut("nodes").map(Value::take) {
                items.extend(nodes);
            }
            match cursor {
                None => return Ok(items),
                Some(_) if page == MAX_BOARD_PAGES => warn!(
                    "Board has more than {} items; results truncated",
                    MAX_BOARD_PAGES * 100
                ),
                Some(_) => debug!("Fetching board page {}", page + 1),
            }
        }
        Ok(items)
    }

    /// All issues on the board with parsed metadata.
    pub async fn board_issues(&self) -> Result<Vec<Issue>> {
        let items = self.fetch_items(queries::BOARD_ITEMS).await?;
        Ok(board::issues_from_items(&items, &self.config))
    }

    /// Ready work (all matches, highest priority first).
    pub async fn get_ready_work(&self, filter: &ReadyFilter) -> Result<Vec<Issue>> {
        let all = self.board_issues().await?;
        let ready = board::select_ready(&all, filter, &self.config);
        info!(
            "Found {} ready issues out of {} on board",
            ready.len(),
            all.len()
        );
        Ok(ready)
    }

    /// Keep only approved issues, checking in priority order until `limit`
    /// approved issues are found. Approvals are checked in batches. With
    /// `agent`, the `[Approved][..]` trigger must name that agent.
    pub async fn filter_approved(
        &self,
        candidates: Vec<Issue>,
        limit: usize,
        agent: Option<&str>,
    ) -> Result<Vec<Issue>> {
        let mut approved = Vec::new();
        for chunk in candidates.chunks(APPROVAL_BATCH_SIZE) {
            let numbers: Vec<u64> = chunk.iter().map(|i| i.number).collect();
            let approvals = self.approvals(&numbers, agent).await?;
            for issue in chunk {
                if approvals.get(&issue.number).is_some_and(Option::is_some) {
                    approved.push(issue.clone());
                    if approved.len() >= limit {
                        return Ok(approved);
                    }
                }
            }
        }
        Ok(approved)
    }

    /// Issue numbers currently on the board.
    async fn board_issue_numbers(&self) -> Result<HashSet<u64>> {
        let items = self.fetch_items(queries::BOARD_NUMBERS).await?;
        Ok(board::issue_numbers(&items))
    }

    /// Dependency graph of an issue (None when not on the board).
    pub async fn dependency_graph(&self, number: u64) -> Result<Option<DependencyGraph>> {
        let all = self.board_issues().await?;
        Ok(board::dependency_graph(number, &all))
    }

    // ===== Single issue =====

    /// Look an issue up directly via `Issue.projectItems`.
    pub async fn lookup_issue(&self, number: u64) -> Result<IssueLookup> {
        let project_id = &self.project()?.id;
        let data = self
            .client
            .query(queries::ISSUE_ITEM, self.repo_vars(number)?)
            .await?;
        parse_issue_lookup(&data, number, project_id, &self.config)
    }

    /// Get an issue with board metadata; `None` if it is not on the board.
    pub async fn get_issue(&self, number: u64) -> Result<Option<Issue>> {
        match self.lookup_issue(number).await {
            Ok(l) if l.on_board => Ok(Some(l.issue)),
            Ok(_) | Err(BoardError::IssueNotFound(_)) => Ok(None),
            Err(e) => Err(e),
        }
    }

    /// Write a project field on an item. `key` is the logical field key
    /// (`status`, `priority`, ...), resolved through the config mappings.
    pub async fn set_field(&self, item_id: &str, key: &str, input: FieldInput<'_>) -> Result<()> {
        let project = self.project()?;
        let name = self.config.get_field_name(key);
        let field = project
            .fields
            .get(&name)
            .ok_or_else(|| BoardError::FieldNotFound(name.clone()))?;

        let base = json!({ "projectId": project.id, "itemId": item_id, "fieldId": field.id });
        let with_value = |value: Value| {
            let mut vars = base.clone();
            vars["value"] = value;
            vars
        };

        let (mutation, vars) = match input {
            FieldInput::Option(value) => {
                let option_id = field.option_id(value).ok_or_else(|| {
                    BoardError::InvalidFieldValue(
                        value.to_string(),
                        format!("{} (options: {})", name, field.option_names().join(", ")),
                    )
                })?;
                (
                    queries::UPDATE_FIELD,
                    with_value(json!({ "singleSelectOptionId": option_id })),
                )
            },
            FieldInput::Text(text) => {
                if field.kind != FieldKind::Text {
                    return Err(BoardError::Validation(format!(
                        "Field '{}' is not a text field",
                        name
                    )));
                }
                (queries::UPDATE_FIELD, with_value(json!({ "text": text })))
            },
            FieldInput::Clear => (queries::CLEAR_FIELD, base),
        };

        self.client.mutate(mutation, vars).await?;
        debug!("Set field '{}' on item {}", name, item_id);
        Ok(())
    }

    /// Update an issue's board status.
    pub async fn update_status(&self, number: u64, status: IssueStatus) -> Result<()> {
        let lookup = self.lookup_issue(number).await?;
        self.set_field(
            lookup.item_id()?,
            "status",
            FieldInput::Option(status.as_str()),
        )
        .await?;
        info!("Updated issue #{} status to {}", number, status);
        Ok(())
    }

    async fn post_comment(&self, node_id: &str, body: &str) -> Result<()> {
        self.client
            .mutate(
                queries::ADD_COMMENT,
                json!({ "subjectId": node_id, "body": body }),
            )
            .await?;
        Ok(())
    }

    // ===== Claims =====

    /// Active claim reconstructed from the most recent 100 comments.
    pub async fn get_active_claim(&self, number: u64) -> Result<Option<AgentClaim>> {
        let data = self
            .client
            .query(queries::CLAIM_COMMENTS, self.repo_vars(number)?)
            .await?;
        let nodes = data
            .get("repository")
            .and_then(|r| r.get("issue"))
            .filter(|i| !i.is_null())
            .ok_or(BoardError::IssueNotFound(number))?
            .get("comments")
            .and_then(|c| c.get("nodes"))
            .and_then(Value::as_array)
            .map(Vec::as_slice)
            .unwrap_or_default();
        let events = claims::events_from_nodes(nodes, &self.claim_authors);
        Ok(claims::resolve_active_claim(
            number,
            &events,
            self.config.claim_timeout,
        ))
    }

    /// Claim an issue: verify no live claim exists, post the claim comment,
    /// re-read to detect a concurrent claim that landed first, then move the
    /// issue to In Progress.
    pub async fn claim_work(
        &self,
        number: u64,
        agent: &str,
        session: &str,
    ) -> Result<ClaimOutcome> {
        let lookup = self.lookup_issue(number).await?;
        let item_id = lookup.item_id()?.to_string();

        if let Some(claim) = self.get_active_claim(number).await? {
            if claim.session_id == session {
                info!("Issue #{} already claimed by this session", number);
            } else if !claim.is_expired(self.config.claim_timeout) {
                info!("Issue #{} already claimed by {}", number, claim.agent);
                return Ok(ClaimOutcome::AlreadyClaimed(claim));
            } else {
                info!(
                    "Stale claim by {} on #{} expired, taking over",
                    claim.agent, number
                );
            }
        }

        let body = claims::claim_comment(agent, session, Utc::now(), self.config.claim_timeout);
        self.post_comment(&lookup.node_id, &body).await?;

        // Detect a concurrent claim: the first live claim wins.
        if let Some(winner) = self.get_active_claim(number).await?
            && winner.session_id != session
        {
            warn!(
                "Lost claim race on #{} to {} (session {})",
                number, winner.agent, winner.session_id
            );
            return Ok(ClaimOutcome::LostRace(winner));
        }

        self.set_field(
            &item_id,
            "status",
            FieldInput::Option(IssueStatus::InProgress.as_str()),
        )
        .await?;
        info!("Claimed #{} for {} (session {})", number, agent, session);
        Ok(ClaimOutcome::Claimed)
    }

    /// Renew an active claim held by `agent`.
    pub async fn renew_claim(&self, number: u64, agent: &str, session: &str) -> Result<bool> {
        match self.get_active_claim(number).await? {
            Some(claim) if same_agent(&claim.agent, agent) => {
                if claim.session_id != session {
                    warn!(
                        "Renewing claim on #{} with session {} (claim was made by session {})",
                        number, session, claim.session_id
                    );
                }
                let lookup = self.lookup_issue(number).await?;
                let body = claims::renewal_comment(agent, session, Utc::now());
                self.post_comment(&lookup.node_id, &body).await?;
                info!("Renewed claim on #{} by {}", number, agent);
                Ok(true)
            },
            other => {
                warn!(
                    "Cannot renew claim on #{}: active claim is {:?}, not {}",
                    number,
                    other.map(|c| c.agent),
                    agent
                );
                Ok(false)
            },
        }
    }

    /// Release a claim and apply the status implied by `reason`.
    pub async fn release_work(
        &self,
        number: u64,
        agent: &str,
        reason: ReleaseReason,
    ) -> Result<()> {
        let lookup = self.lookup_issue(number).await?;
        let body = claims::release_comment_for(agent, reason, Utc::now());
        self.post_comment(&lookup.node_id, &body).await?;

        if let Some(status) = reason.resulting_status() {
            self.set_field(
                lookup.item_id()?,
                "status",
                FieldInput::Option(status.as_str()),
            )
            .await?;
        }
        info!(
            "Released claim on #{} by {} (reason: {})",
            number, agent, reason
        );
        Ok(())
    }

    /// Release claims whose last activity is older than the threshold and
    /// reset those issues so they can be picked up again.
    pub async fn janitor(&self, opts: &JanitorOptions) -> Result<JanitorReport> {
        let in_progress: Vec<Issue> = self
            .board_issues()
            .await?
            .into_iter()
            .filter(|i| i.is_open() && i.status == IssueStatus::InProgress)
            .collect();

        let now = Utc::now();
        let mut report = JanitorReport {
            dry_run: opts.dry_run,
            threshold_hours: opts.threshold_secs as f64 / 3600.0,
            reset_status: opts.reset_status,
            inspected: in_progress.len(),
            cleaned_count: 0,
            stale: Vec::new(),
            unclaimed_in_progress: Vec::new(),
            failed: Vec::new(),
        };

        for issue in &in_progress {
            let claim = match self.get_active_claim(issue.number).await? {
                Some(c) => c,
                None => {
                    report.unclaimed_in_progress.push(issue.number);
                    continue;
                },
            };
            if opts
                .agent
                .as_deref()
                .is_some_and(|a| !same_agent(a, &claim.agent))
                || !claim.is_expired_at(opts.threshold_secs, now)
            {
                continue;
            }

            let stale = StaleClaim {
                issue: issue.number,
                title: issue.title.clone(),
                agent: claim.agent.clone(),
                session_id: claim.session_id.clone(),
                age_hours: claim.age_seconds_at(now) as f64 / 3600.0,
            };
            if !opts.dry_run
                && let Err(e) = self.release_stale(issue, &stale, opts.reset_status).await
            {
                warn!("Janitor failed to release #{}: {}", issue.number, e);
                report.failed.push(issue.number);
                continue;
            }
            report.stale.push(stale);
        }

        report.cleaned_count = report.stale.len();
        Ok(report)
    }

    async fn release_stale(
        &self,
        issue: &Issue,
        stale: &StaleClaim,
        reset: IssueStatus,
    ) -> Result<()> {
        let item_id = issue
            .project_item_id
            .as_deref()
            .ok_or(BoardError::NotOnBoard(issue.number))?;
        let lookup = self.lookup_issue(issue.number).await?;
        let note = format!(
            "Claim by `{}` had no activity for {:.1} hours and was released by the board \
             janitor. Status reset to {}.",
            stale.agent, stale.age_hours, reset
        );
        let body = claims::release_comment(&stale.agent, "stale_claim", Utc::now(), &note);
        self.post_comment(&lookup.node_id, &body).await?;
        self.set_field(item_id, "status", FieldInput::Option(reset.as_str()))
            .await?;
        info!("Janitor released stale claim on #{}", issue.number);
        Ok(())
    }

    // ===== Dependencies =====

    /// Add `blocker` to the Blocked By field of `number`.
    pub async fn add_blocker(&self, number: u64, blocker: u64) -> Result<Vec<u64>> {
        if number == blocker {
            return Err(BoardError::Validation(format!(
                "Issue #{} cannot block itself",
                number
            )));
        }
        let lookup = self.lookup_issue(number).await?;
        let mut list = lookup.issue.blocked_by.clone();
        if !list.contains(&blocker) {
            list.push(blocker);
        }
        self.write_blockers(&lookup, &list).await?;
        info!("#{} now blocks #{}", blocker, number);
        Ok(list)
    }

    /// Remove `blocker` from the Blocked By field of `number`.
    pub async fn remove_blocker(&self, number: u64, blocker: u64) -> Result<Vec<u64>> {
        let lookup = self.lookup_issue(number).await?;
        let list: Vec<u64> = lookup
            .issue
            .blocked_by
            .iter()
            .copied()
            .filter(|b| *b != blocker)
            .collect();
        self.write_blockers(&lookup, &list).await?;
        info!("#{} no longer blocks #{}", blocker, number);
        Ok(list)
    }

    async fn write_blockers(&self, lookup: &IssueLookup, list: &[u64]) -> Result<()> {
        let input = if list.is_empty() {
            FieldInput::Clear
        } else {
            FieldInput::Text(board::format_number_list(list))
        };
        self.set_field(lookup.item_id()?, "blocked_by", input).await
    }

    /// Record that `number` was discovered while working on `parent`.
    pub async fn mark_discovered_from(&self, number: u64, parent: u64) -> Result<()> {
        if number == parent {
            return Err(BoardError::Validation(format!(
                "Issue #{} cannot be discovered from itself",
                number
            )));
        }
        let lookup = self.lookup_issue(number).await?;
        self.set_field(
            lookup.item_id()?,
            "discovered_from",
            FieldInput::Text(parent.to_string()),
        )
        .await?;
        info!("Marked #{} as discovered from #{}", number, parent);
        Ok(())
    }

    // ===== Approval =====

    fn approval_policy<'a>(&'a self, agent: Option<&'a str>) -> ApprovalPolicy<'a> {
        ApprovalPolicy {
            approvers: &self.allowed_approvers,
            agent,
        }
    }

    /// Approval status for many issues: `number -> Some(approver)` if an
    /// allowed approver wrote `[Approved][..]` (naming `agent`, if given).
    pub async fn approvals(
        &self,
        numbers: &[u64],
        agent: Option<&str>,
    ) -> Result<HashMap<u64, Option<String>>> {
        let policy = self.approval_policy(agent);
        let mut out = HashMap::new();
        for chunk in numbers.chunks(APPROVAL_BATCH_SIZE) {
            let (owner, repo) = self.repo()?;
            let vars = json!({ "owner": owner, "repo": repo });
            let data = self
                .client
                .query(&approval::batch_query(chunk), vars)
                .await?;
            for (n, state) in approval::parse_batch(&data, chunk, &policy) {
                let approver = match state {
                    BatchApproval::Approved(a) => Some(a),
                    BatchApproval::NeedsMore(cursor) => {
                        self.approval_from_pages(n, cursor, &policy).await?
                    },
                    BatchApproval::NotApproved | BatchApproval::Missing => None,
                };
                out.insert(n, approver);
            }
        }
        Ok(out)
    }

    /// Continue scanning comment pages after `cursor` for an approval.
    async fn approval_from_pages(
        &self,
        number: u64,
        cursor: String,
        policy: &ApprovalPolicy<'_>,
    ) -> Result<Option<String>> {
        let mut cursor = Some(cursor);
        for _ in 0..MAX_COMMENT_PAGES {
            let mut vars = self.repo_vars(number)?;
            vars["cursor"] = json!(cursor);
            let data = self.client.query(queries::COMMENT_PAGE, vars).await?;
            let comments = data
                .get("repository")
                .and_then(|r| r.get("issue"))
                .and_then(|i| i.get("comments"));
            let nodes = comments
                .and_then(|c| c.get("nodes"))
                .and_then(Value::as_array)
                .map(Vec::as_slice)
                .unwrap_or_default();
            if let Some(approver) = policy.find_approver(nodes) {
                return Ok(Some(approver));
            }
            cursor = approval::next_cursor(comments);
            if cursor.is_none() {
                return Ok(None);
            }
        }
        warn!(
            "Issue #{} has more than {} comments; approval scan truncated",
            number,
            (MAX_COMMENT_PAGES + 1) * 100
        );
        Ok(None)
    }

    /// Whether an issue is approved (for `agent`, if given); returns
    /// `(approved, approver)`.
    pub async fn is_issue_approved(
        &self,
        number: u64,
        agent: Option<&str>,
    ) -> Result<(bool, Option<String>)> {
        let approver = self
            .approvals(&[number], agent)
            .await?
            .remove(&number)
            .flatten();
        Ok((approver.is_some(), approver))
    }

    /// Find issues with `[Approved][agent]` comments via GitHub search.
    /// With `verify`, only issues approved by an authorized user are returned.
    pub async fn find_approved_issues(
        &self,
        agent: &str,
        verify: bool,
    ) -> Result<Vec<ApprovedIssue>> {
        let (owner, repo) = self.repo()?;
        let search = format!(
            r#"repo:{}/{} is:issue is:open "[Approved][{}]" in:comments"#,
            owner, repo, agent
        );

        let mut hits: Vec<(u64, String)> = Vec::new();
        for page in 1..=MAX_SEARCH_PAGES {
            let page_str = page.to_string();
            let resp = self
                .client
                .rest_get(
                    "/search/issues",
                    &[
                        ("q", search.as_str()),
                        ("per_page", "100"),
                        ("page", &page_str),
                    ],
                )
                .await?;
            let items = resp.get("items").and_then(Value::as_array);
            let batch: Vec<(u64, String)> = items
                .into_iter()
                .flatten()
                .filter_map(|i| {
                    let n = i.get("number")?.as_u64()?;
                    let title = i.get("title").and_then(Value::as_str).unwrap_or_default();
                    Some((n, title.to_string()))
                })
                .collect();
            let total = resp.get("total_count").and_then(Value::as_u64).unwrap_or(0);
            let done = batch.len() < 100 || hits.len() + batch.len() >= total as usize;
            hits.extend(batch);
            if done {
                break;
            }
        }
        info!("Search found {} candidate issues", hits.len());

        let approvals = if verify && !hits.is_empty() {
            let numbers: Vec<u64> = hits.iter().map(|(n, _)| *n).collect();
            Some(self.approvals(&numbers, Some(agent)).await?)
        } else {
            None
        };
        let on_board = self.board_issue_numbers().await?;

        Ok(hits
            .into_iter()
            .filter_map(|(number, title)| {
                let approver = match &approvals {
                    Some(map) => Some(map.get(&number).cloned().flatten()?),
                    None => None,
                };
                Some(ApprovedIssue {
                    number,
                    title,
                    on_board: on_board.contains(&number),
                    approver,
                })
            })
            .collect())
    }

    // ===== Adding issues =====

    /// Add an issue to the board and set its fields. Optional fields that
    /// cannot be set (missing field or option on the board) are reported as
    /// warnings rather than failing the whole operation.
    pub async fn add_issue_to_board(
        &self,
        lookup: &IssueLookup,
        status: IssueStatus,
        opts: &AddOptions,
    ) -> Result<Vec<String>> {
        let project_id = &self.project()?.id;
        let data = self
            .client
            .mutate(
                queries::ADD_ITEM,
                json!({ "projectId": project_id, "contentId": lookup.node_id }),
            )
            .await?;
        let item_id = data
            .get("addProjectV2ItemByContentId")
            .and_then(|a| a.get("item"))
            .and_then(|i| i.get("id"))
            .and_then(Value::as_str)
            .ok_or_else(|| {
                BoardError::GraphQL("addProjectV2ItemByContentId returned no item".into())
            })?;

        self.set_field(item_id, "status", FieldInput::Option(status.as_str()))
            .await?;

        let agent = opts.agent.as_deref().map(normalize_agent_name);
        let optional: [(&str, Option<&str>); 4] = [
            ("priority", opts.priority.map(|p| p.as_str())),
            ("type", opts.issue_type.map(|t| t.as_str())),
            ("size", opts.size.map(|s| s.as_str())),
            ("agent", agent.as_deref()),
        ];
        let mut warnings = Vec::new();
        for (key, value) in optional {
            let Some(value) = value else { continue };
            if let Err(e) = self
                .set_field(item_id, key, FieldInput::Option(value))
                .await
            {
                warn!("Could not set {} on #{}: {}", key, lookup.issue.number, e);
                warnings.push(format!("{}: {}", key, e));
            }
        }

        info!("Added issue #{} to board", lookup.issue.number);
        Ok(warnings)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn lookup_data(project_id: &str) -> Value {
        json!({
            "repository": {
                "issue": {
                    "id": "I_node",
                    "number": 42,
                    "title": "Fix it",
                    "body": "",
                    "state": "OPEN",
                    "labels": { "nodes": [{ "name": "bug" }] },
                    "projectItems": { "nodes": [
                        { "id": "OTHER_ITEM", "project": { "id": "P_other" },
                          "fieldValues": { "nodes": [
                            { "name": "Done", "field": { "name": "Status" } } ] } },
                        { "id": "ITEM", "project": { "id": project_id },
                          "fieldValues": { "nodes": [
                            { "name": "In Progress", "field": { "name": "Status" } },
                            { "text": "1, 2", "field": { "name": "Blocked By" } } ] } }
                    ] }
                }
            }
        })
    }

    #[test]
    fn lookup_picks_item_of_configured_project() {
        let l = parse_issue_lookup(
            &lookup_data("P_main"),
            42,
            "P_main",
            &BoardConfig::default(),
        )
        .unwrap();
        assert!(l.on_board);
        assert_eq!(l.node_id, "I_node");
        assert_eq!(l.issue.status, IssueStatus::InProgress);
        assert_eq!(l.issue.blocked_by, vec![1, 2]);
        assert_eq!(l.item_id().unwrap(), "ITEM");
    }

    #[test]
    fn lookup_not_on_board() {
        let l = parse_issue_lookup(
            &lookup_data("P_main"),
            42,
            "P_missing",
            &BoardConfig::default(),
        )
        .unwrap();
        assert!(!l.on_board);
        assert_eq!(l.issue.status, IssueStatus::Todo);
        assert!(matches!(l.item_id(), Err(BoardError::NotOnBoard(42))));
    }

    fn repo_config() -> BoardConfig {
        BoardConfig {
            project_number: 1,
            owner: "ProjOwner".into(),
            repository: "RepoOwner/repo".into(),
            ..Default::default()
        }
    }

    #[test]
    fn claim_authors_are_admins_and_trusted_sources() {
        let trust = TrustConfig {
            agent_admins: vec!["AndrewAltimit".into()],
            trusted_sources: vec!["github-actions[bot]".into(), " Renovate[bot] ".into()],
        };
        let set = claim_author_set(&repo_config(), Some(&trust));
        assert_eq!(
            set,
            HashSet::from([
                "andrewaltimit".to_string(),
                "github-actions[bot]".to_string(),
                "renovate[bot]".to_string(),
            ])
        );
    }

    #[test]
    fn claim_authors_fail_closed_to_repo_owner() {
        assert_eq!(
            claim_author_set(&repo_config(), None),
            HashSet::from(["repoowner".to_string()])
        );
        let bad_repo = BoardConfig {
            repository: "norepo".into(),
            ..repo_config()
        };
        assert!(claim_author_set(&bad_repo, None).is_empty());
    }

    #[test]
    fn approvers_exclude_trusted_sources() {
        let trust = TrustConfig {
            agent_admins: vec!["Admin".into()],
            trusted_sources: vec!["github-actions[bot]".into()],
        };
        let set = approver_set(&repo_config(), Some(&trust));
        assert!(set.contains("admin"));
        assert!(set.contains("projowner"));
        assert!(set.contains("repoowner"));
        assert!(!set.contains("github-actions[bot]"));
        assert_eq!(approver_set(&repo_config(), None).len(), 2);
    }

    #[test]
    fn lookup_missing_issue() {
        let data = json!({ "repository": { "issue": null } });
        assert!(matches!(
            parse_issue_lookup(&data, 7, "P", &BoardConfig::default()),
            Err(BoardError::IssueNotFound(7))
        ));
    }
}
