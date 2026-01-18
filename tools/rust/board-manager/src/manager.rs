//! GitHub Projects v2 board manager with GraphQL operations.

use chrono::{DateTime, Utc};
use lazy_static::lazy_static;
use regex::Regex;
use serde_json::{Value, json};
use std::collections::HashMap;
use tracing::{debug, info, warn};

use crate::client::GraphQLClient;
use crate::error::{BoardError, Result};
use crate::models::{
    AgentClaim, ApprovedIssue, BoardConfig, Issue, IssuePriority, IssueStatus, IssueType,
    ReleaseReason,
};

/// Claim comment prefixes.
const CLAIM_PREFIX: &str = "**[Agent Claim]**";
const RENEWAL_PREFIX: &str = "**[Claim Renewal]**";
const RELEASE_PREFIX: &str = "**[Agent Release]**";

lazy_static! {
    /// Pre-compiled regex for approval pattern matching.
    /// Matches patterns like [Approved][Claude], [Review][Agent], etc.
    static ref APPROVAL_PATTERN: Regex =
        Regex::new(r"(?i)\[(Approved|Review|Close|Summarize|Debug)\]\[[\w\s-]+\]").unwrap();
}

/// Agent name mappings (workflow names -> board field values).
const AGENT_NAME_MAP: &[(&str, &str)] = &[
    ("claude", "Claude Code"),
    ("opencode", "OpenCode"),
    ("crush", "Crush"),
    ("gemini", "Gemini CLI"),
    ("codex", "Codex"),
];

/// Manager for GitHub Projects v2 board operations.
pub struct BoardManager {
    client: GraphQLClient,
    config: BoardConfig,
    project_id: Option<String>,
    /// Cached set of users authorized to approve work (normalized to lowercase).
    cached_allowed_users: std::collections::HashSet<String>,
}

impl BoardManager {
    /// Create a new BoardManager.
    pub fn new(config: BoardConfig, token: String) -> Result<Self> {
        let client = GraphQLClient::new(token)?;

        // Pre-compute allowed users for approval checking
        let mut cached_allowed_users = std::collections::HashSet::new();

        // Add project owner
        if !config.owner.is_empty() {
            cached_allowed_users.insert(config.owner.to_lowercase());
        }

        // Add users from security config (loaded once at startup)
        if let Ok(trust_config) = crate::security::TrustConfig::from_yaml(None) {
            for admin in &trust_config.agent_admins {
                cached_allowed_users.insert(admin.to_lowercase());
            }
        }

        Ok(Self {
            client,
            config,
            project_id: None,
            cached_allowed_users,
        })
    }

    /// Initialize the manager by loading project metadata.
    pub async fn initialize(&mut self) -> Result<()> {
        self.project_id = Some(self.get_project_id().await?);

        // Add repository owner to cached allowed users (requires parse_repository)
        if let Ok((repo_owner, _)) = self.parse_repository() {
            self.cached_allowed_users.insert(repo_owner.to_lowercase());
        }

        info!("Board initialized with project ID: {:?}", self.project_id);
        Ok(())
    }

    /// Normalize agent name for comparison.
    fn normalize_agent_name(name: &str) -> String {
        let lower = name.to_lowercase();
        for (key, value) in AGENT_NAME_MAP {
            if lower == *key {
                return (*value).to_string();
            }
        }
        name.to_string()
    }

    /// Get the project ID from the project number.
    async fn get_project_id(&self) -> Result<String> {
        let query = r#"
        query GetProject($owner: String!, $number: Int!) {
          user(login: $owner) {
            projectV2(number: $number) {
              id
              title
            }
          }
          organization(login: $owner) {
            projectV2(number: $number) {
              id
              title
            }
          }
        }
        "#;

        let variables = json!({
            "owner": self.config.owner,
            "number": self.config.project_number
        });

        let response = self.client.execute(query, Some(variables)).await?;

        let data = response.data.ok_or_else(|| {
            BoardError::BoardNotFound(format!(
                "Project #{} not found for owner {}",
                self.config.project_number, self.config.owner
            ))
        })?;

        // Try user first, then organization
        let project = data
            .get("user")
            .and_then(|u| u.get("projectV2"))
            .or_else(|| data.get("organization").and_then(|o| o.get("projectV2")));

        let project = project.ok_or_else(|| {
            BoardError::BoardNotFound(format!(
                "Project #{} not found for owner {}",
                self.config.project_number, self.config.owner
            ))
        })?;

        project
            .get("id")
            .and_then(|id| id.as_str())
            .map(|s| s.to_string())
            .ok_or_else(|| BoardError::GraphQL("Project ID not found in response".to_string()))
    }

    /// Get issues ready for work.
    pub async fn get_ready_work(
        &self,
        agent_name: Option<&str>,
        limit: usize,
    ) -> Result<Vec<Issue>> {
        let project_id = self
            .project_id
            .as_ref()
            .ok_or_else(|| BoardError::Config("BoardManager not initialized".to_string()))?;

        info!(
            "Getting ready work (agent={:?}, limit={})",
            agent_name, limit
        );

        // Query with pagination support
        let query = r#"
        query GetProjectItems($projectId: ID!, $cursor: String) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100, after: $cursor) {
                pageInfo {
                  hasNextPage
                  endCursor
                }
                nodes {
                  id
                  fieldValues(first: 20) {
                    nodes {
                      ... on ProjectV2ItemFieldSingleSelectValue {
                        name
                        field { ... on ProjectV2FieldCommon { name } }
                      }
                      ... on ProjectV2ItemFieldTextValue {
                        text
                        field { ... on ProjectV2FieldCommon { name } }
                      }
                    }
                  }
                  content {
                    ... on Issue {
                      number
                      title
                      body
                      state
                      createdAt
                      updatedAt
                      url
                      labels(first: 20) { nodes { name } }
                    }
                  }
                }
              }
            }
          }
        }
        "#;

        let normalized_agent = agent_name.map(Self::normalize_agent_name);
        let mut ready_issues = Vec::new();
        let mut cursor: Option<String> = None;
        let mut page_count = 0;
        const MAX_PAGES: usize = 10; // Safety limit: 1000 items max

        loop {
            page_count += 1;
            if page_count > MAX_PAGES {
                warn!("Reached maximum pagination limit ({} pages)", MAX_PAGES);
                break;
            }

            let variables = match &cursor {
                Some(c) => json!({ "projectId": project_id, "cursor": c }),
                None => json!({ "projectId": project_id, "cursor": null }),
            };

            let response = self.client.execute(query, Some(variables)).await?;

            let data = response
                .data
                .ok_or_else(|| BoardError::GraphQL("Failed to fetch project items".to_string()))?;

            let items_data = data
                .get("node")
                .and_then(|n| n.get("items"))
                .ok_or_else(|| BoardError::GraphQL("Invalid response structure".to_string()))?;

            let items = items_data
                .get("nodes")
                .and_then(|n| n.as_array())
                .ok_or_else(|| BoardError::GraphQL("Invalid response structure".to_string()))?;

            // Process items from this page
            for item in items {
                let content = match item.get("content") {
                    Some(c) if !c.is_null() => c,
                    _ => continue,
                };

                // Skip closed issues
                if content.get("state").and_then(|s| s.as_str()) != Some("OPEN") {
                    continue;
                }

                let field_values = self.parse_field_values(item);
                let (status, priority, issue_type, assigned_agent, blocked_by) =
                    self.parse_issue_metadata(&field_values);

                // Skip if not in Todo status
                if status != IssueStatus::Todo {
                    continue;
                }

                // Filter by agent if specified
                if let Some(ref norm_agent) = normalized_agent
                    && let Some(ref assigned) = assigned_agent
                    && assigned != norm_agent
                {
                    continue;
                }

                // Skip if has blockers
                if !blocked_by.is_empty() {
                    continue;
                }

                // Skip excluded labels
                let labels = self.parse_labels(content);
                if labels
                    .iter()
                    .any(|l| self.config.exclude_labels.contains(l))
                {
                    continue;
                }

                let issue = self.create_issue_from_item(
                    item,
                    content,
                    status,
                    priority,
                    issue_type,
                    assigned_agent,
                    blocked_by,
                    None,
                )?;

                ready_issues.push(issue);

                if ready_issues.len() >= limit {
                    break;
                }
            }

            // Check if we have enough results or no more pages
            if ready_issues.len() >= limit {
                break;
            }

            let page_info = items_data.get("pageInfo");
            let has_next_page = page_info
                .and_then(|p| p.get("hasNextPage"))
                .and_then(|h| h.as_bool())
                .unwrap_or(false);

            if !has_next_page {
                break;
            }

            cursor = page_info
                .and_then(|p| p.get("endCursor"))
                .and_then(|c| c.as_str())
                .map(|s| s.to_string());

            if cursor.is_none() {
                break;
            }

            info!("Fetching next page of items (page {})", page_count + 1);
        }

        // Sort by priority (now sorting ALL fetched items, not just first 100)
        ready_issues.sort_by_key(|issue| match issue.priority {
            IssuePriority::Critical => 0,
            IssuePriority::High => 1,
            IssuePriority::Medium => 2,
            IssuePriority::Low => 3,
        });

        // Truncate to limit after sorting by priority
        ready_issues.truncate(limit);

        info!("Found {} ready issues", ready_issues.len());
        Ok(ready_issues)
    }

    /// Get a specific issue by number.
    pub async fn get_issue(&self, issue_number: u64) -> Result<Option<Issue>> {
        let project_id = self
            .project_id
            .as_ref()
            .ok_or_else(|| BoardError::Config("BoardManager not initialized".to_string()))?;

        info!("Getting issue #{}", issue_number);

        // Query with pagination support
        let query = r#"
        query GetProjectItems($projectId: ID!, $cursor: String) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100, after: $cursor) {
                pageInfo {
                  hasNextPage
                  endCursor
                }
                nodes {
                  id
                  fieldValues(first: 20) {
                    nodes {
                      ... on ProjectV2ItemFieldSingleSelectValue {
                        name
                        field { ... on ProjectV2FieldCommon { name } }
                      }
                      ... on ProjectV2ItemFieldTextValue {
                        text
                        field { ... on ProjectV2FieldCommon { name } }
                      }
                    }
                  }
                  content {
                    ... on Issue {
                      number
                      title
                      body
                      state
                      createdAt
                      updatedAt
                      url
                      labels(first: 20) { nodes { name } }
                    }
                  }
                }
              }
            }
          }
        }
        "#;

        let mut cursor: Option<String> = None;
        let mut page_count = 0;
        const MAX_PAGES: usize = 10; // Safety limit

        loop {
            page_count += 1;
            if page_count > MAX_PAGES {
                warn!(
                    "Issue #{} not found after {} pages",
                    issue_number, MAX_PAGES
                );
                break;
            }

            let variables = match &cursor {
                Some(c) => json!({ "projectId": project_id, "cursor": c }),
                None => json!({ "projectId": project_id, "cursor": null }),
            };

            let response = self.client.execute(query, Some(variables)).await?;

            let data = response
                .data
                .ok_or_else(|| BoardError::GraphQL("Failed to fetch project items".to_string()))?;

            let items_data = data
                .get("node")
                .and_then(|n| n.get("items"))
                .ok_or_else(|| BoardError::GraphQL("Invalid response structure".to_string()))?;

            let items = items_data
                .get("nodes")
                .and_then(|n| n.as_array())
                .ok_or_else(|| BoardError::GraphQL("Invalid response structure".to_string()))?;

            for item in items {
                let content = match item.get("content") {
                    Some(c) if !c.is_null() => c,
                    _ => continue,
                };

                if content.get("number").and_then(|n| n.as_u64()) != Some(issue_number) {
                    continue;
                }

                let field_values = self.parse_field_values(item);
                let (status, priority, issue_type, assigned_agent, blocked_by) =
                    self.parse_issue_metadata(&field_values);
                let discovered_from = self.parse_discovered_from(&field_values);

                let issue = self.create_issue_from_item(
                    item,
                    content,
                    status,
                    priority,
                    issue_type,
                    assigned_agent,
                    blocked_by,
                    discovered_from,
                )?;

                info!("Found issue #{}: {}", issue_number, issue.title);
                return Ok(Some(issue));
            }

            // Check for more pages
            let page_info = items_data.get("pageInfo");
            let has_next_page = page_info
                .and_then(|p| p.get("hasNextPage"))
                .and_then(|h| h.as_bool())
                .unwrap_or(false);

            if !has_next_page {
                break;
            }

            cursor = page_info
                .and_then(|p| p.get("endCursor"))
                .and_then(|c| c.as_str())
                .map(|s| s.to_string());

            if cursor.is_none() {
                break;
            }
        }

        warn!("Issue #{} not found on board", issue_number);
        Ok(None)
    }

    /// Claim an issue for work.
    pub async fn claim_work(
        &self,
        issue_number: u64,
        agent_name: &str,
        session_id: &str,
    ) -> Result<bool> {
        info!(
            "Claiming issue #{} by {} (session: {})",
            issue_number, agent_name, session_id
        );

        // Check for existing claim
        let existing_claim = self.get_active_claim(issue_number).await?;
        if let Some(claim) = existing_claim {
            if !claim.is_expired(self.config.claim_timeout) {
                info!("Issue #{} already claimed by {}", issue_number, claim.agent);
                return Ok(false);
            }
            info!("Stale claim expired on issue #{}, stealing", issue_number);
        }

        // Post claim comment
        let timeout_hours = self.config.claim_timeout / 3600;
        let comment = format!(
            "{}\n\nAgent: `{}`\nStarted: `{}`\nSession ID: `{}`\n\nClaiming this issue for implementation. If this agent goes MIA, this claim expires after {} hours.",
            CLAIM_PREFIX,
            agent_name,
            Utc::now().to_rfc3339(),
            session_id,
            timeout_hours
        );

        self.post_issue_comment(issue_number, &comment).await?;

        // Update status to In Progress
        self.update_status(issue_number, IssueStatus::InProgress)
            .await?;

        Ok(true)
    }

    /// Renew an active claim.
    pub async fn renew_claim(
        &self,
        issue_number: u64,
        agent_name: &str,
        session_id: &str,
    ) -> Result<bool> {
        let existing_claim = self.get_active_claim(issue_number).await?;

        match existing_claim {
            Some(claim) if claim.agent == agent_name => {
                let comment = format!(
                    "{}\n\nAgent: `{}`\nRenewed: `{}`\nSession ID: `{}`\n\nClaim renewed - still actively working on this issue.",
                    RENEWAL_PREFIX,
                    agent_name,
                    Utc::now().to_rfc3339(),
                    session_id
                );

                self.post_issue_comment(issue_number, &comment).await?;
                info!("Renewed claim on #{} by {}", issue_number, agent_name);
                Ok(true)
            }
            _ => {
                warn!(
                    "Cannot renew claim on #{}: no active claim by {}",
                    issue_number, agent_name
                );
                Ok(false)
            }
        }
    }

    /// Release claim on an issue.
    pub async fn release_work(
        &self,
        issue_number: u64,
        agent_name: &str,
        reason: ReleaseReason,
    ) -> Result<()> {
        let comment = format!(
            "{}\n\nAgent: `{}`\nReleased: `{}`\nReason: `{}`\n\nWork claim released.",
            RELEASE_PREFIX,
            agent_name,
            Utc::now().to_rfc3339(),
            reason
        );

        self.post_issue_comment(issue_number, &comment).await?;

        // Update status based on reason
        match reason {
            ReleaseReason::Completed | ReleaseReason::PrCreated => {
                // Stay In Progress until PR is merged
            }
            ReleaseReason::Blocked => {
                self.update_status(issue_number, IssueStatus::Blocked)
                    .await?;
            }
            ReleaseReason::Abandoned | ReleaseReason::Error => {
                // Use Abandoned status to prevent infinite loops where agents
                // repeatedly pick up and fail on the same issue
                self.update_status(issue_number, IssueStatus::Abandoned)
                    .await?;
            }
        }

        info!(
            "Released claim on #{} by {} (reason: {})",
            issue_number, agent_name, reason
        );
        Ok(())
    }

    /// Update issue status on board.
    pub async fn update_status(&self, issue_number: u64, status: IssueStatus) -> Result<bool> {
        let project_id = self
            .project_id
            .as_ref()
            .ok_or_else(|| BoardError::Config("BoardManager not initialized".to_string()))?;

        // Query with pagination support for boards with >100 items
        let query = r#"
        query GetProjectItem($projectId: ID!, $cursor: String) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100, after: $cursor) {
                pageInfo {
                  hasNextPage
                  endCursor
                }
                nodes {
                  id
                  content { ... on Issue { number } }
                }
              }
              field(name: "Status") {
                ... on ProjectV2SingleSelectField {
                  id
                  options { id name }
                }
              }
            }
          }
        }
        "#;

        let mut cursor: Option<String> = None;
        let mut project_item_id: Option<String> = None;
        let mut field_data: Option<serde_json::Value> = None;
        const MAX_PAGES: usize = 10;

        for page in 1..=MAX_PAGES {
            let variables = match &cursor {
                Some(c) => json!({ "projectId": project_id, "cursor": c }),
                None => json!({ "projectId": project_id, "cursor": null }),
            };

            let response = self.client.execute(query, Some(variables)).await?;

            let data = response
                .data
                .ok_or_else(|| BoardError::GraphQL("Failed to get project item".to_string()))?;

            let node = data
                .get("node")
                .ok_or_else(|| BoardError::GraphQL("Node not found".to_string()))?;

            // Store field data from first page (it's the same on all pages)
            if field_data.is_none() {
                field_data = node.get("field").cloned();
            }

            let items_data = node
                .get("items")
                .ok_or_else(|| BoardError::GraphQL("Items not found".to_string()))?;

            let items = items_data
                .get("nodes")
                .and_then(|n| n.as_array())
                .ok_or_else(|| BoardError::GraphQL("Items nodes not found".to_string()))?;

            // Search for the issue in this page
            for item in items {
                if item
                    .get("content")
                    .and_then(|c| c.get("number"))
                    .and_then(|n| n.as_u64())
                    == Some(issue_number)
                {
                    project_item_id = item.get("id").and_then(|id| id.as_str()).map(String::from);
                    break;
                }
            }

            if project_item_id.is_some() {
                break;
            }

            // Check for more pages
            let page_info = items_data.get("pageInfo");
            let has_next_page = page_info
                .and_then(|p| p.get("hasNextPage"))
                .and_then(|h| h.as_bool())
                .unwrap_or(false);

            if !has_next_page {
                break;
            }

            cursor = page_info
                .and_then(|p| p.get("endCursor"))
                .and_then(|c| c.as_str())
                .map(String::from);

            if cursor.is_none() || page == MAX_PAGES {
                warn!("Issue #{} not found after {} pages", issue_number, page);
                break;
            }
        }

        let project_item_id =
            project_item_id.ok_or_else(|| BoardError::IssueNotFound(issue_number))?;

        // Get field ID and option ID (from stored field_data)
        let field = field_data
            .as_ref()
            .ok_or_else(|| BoardError::FieldNotFound("Status".to_string()))?;

        let field_id = field
            .get("id")
            .and_then(|id| id.as_str())
            .ok_or_else(|| BoardError::FieldNotFound("Status".to_string()))?;

        let options = field
            .get("options")
            .and_then(|o| o.as_array())
            .ok_or_else(|| BoardError::FieldNotFound("Status options".to_string()))?;

        let status_value = status.as_str();
        let option_id = options
            .iter()
            .find(|opt| opt.get("name").and_then(|n| n.as_str()) == Some(status_value))
            .and_then(|opt| opt.get("id"))
            .and_then(|id| id.as_str())
            .ok_or_else(|| {
                BoardError::InvalidFieldValue(status_value.to_string(), "Status".to_string())
            })?;

        // Update field value
        let mutation = r#"
        mutation UpdateProjectField($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
          updateProjectV2ItemFieldValue(
            input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: $value}
          ) {
            projectV2Item { id }
          }
        }
        "#;

        let variables = json!({
            "projectId": project_id,
            "itemId": project_item_id,
            "fieldId": field_id,
            "value": { "singleSelectOptionId": option_id }
        });

        self.client.execute(mutation, Some(variables)).await?;
        info!("Updated issue #{} status to {}", issue_number, status);
        Ok(true)
    }

    /// Add blocker relationship.
    pub async fn add_blocker(&self, issue_number: u64, blocker_number: u64) -> Result<bool> {
        let project_id = self
            .project_id
            .as_ref()
            .ok_or_else(|| BoardError::Config("BoardManager not initialized".to_string()))?;

        info!(
            "Adding blocker: #{} blocks #{}",
            blocker_number, issue_number
        );

        // Query with pagination support for boards with >100 items
        let query = r#"
        query GetProjectItemForBlocker($projectId: ID!, $cursor: String) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100, after: $cursor) {
                pageInfo {
                  hasNextPage
                  endCursor
                }
                nodes {
                  id
                  fieldValues(first: 20) {
                    nodes {
                      ... on ProjectV2ItemFieldTextValue {
                        text
                        field { ... on ProjectV2FieldCommon { name } }
                      }
                    }
                  }
                  content { ... on Issue { number } }
                }
              }
              field(name: "Blocked By") {
                ... on ProjectV2FieldCommon { id }
              }
            }
          }
        }
        "#;

        let mut cursor: Option<String> = None;
        let mut project_item_id: Option<String> = None;
        let mut current_blocked_by = String::new();
        let mut field_data: Option<serde_json::Value> = None;
        const MAX_PAGES: usize = 10;

        for page in 1..=MAX_PAGES {
            let variables = match &cursor {
                Some(c) => json!({ "projectId": project_id, "cursor": c }),
                None => json!({ "projectId": project_id, "cursor": null }),
            };

            let response = self.client.execute(query, Some(variables)).await?;

            let data = response
                .data
                .ok_or_else(|| BoardError::GraphQL("Failed to get project item".to_string()))?;

            let node = data
                .get("node")
                .ok_or_else(|| BoardError::GraphQL("Node not found".to_string()))?;

            // Store field data from first page
            if field_data.is_none() {
                field_data = node.get("field").cloned();
            }

            let items_data = node
                .get("items")
                .ok_or_else(|| BoardError::GraphQL("Items not found".to_string()))?;

            let items = items_data
                .get("nodes")
                .and_then(|n| n.as_array())
                .ok_or_else(|| BoardError::GraphQL("Items nodes not found".to_string()))?;

            // Search for the issue in this page
            for item in items {
                let content = item.get("content");
                if content
                    .and_then(|c| c.get("number"))
                    .and_then(|n| n.as_u64())
                    != Some(issue_number)
                {
                    continue;
                }

                project_item_id = item
                    .get("id")
                    .and_then(|id| id.as_str())
                    .map(|s| s.to_string());

                // Find blocked_by field value
                if let Some(field_values) = item
                    .get("fieldValues")
                    .and_then(|f| f.get("nodes"))
                    .and_then(|n| n.as_array())
                {
                    for fv in field_values {
                        let field_name = fv
                            .get("field")
                            .and_then(|f| f.get("name"))
                            .and_then(|n| n.as_str());
                        if field_name == Some(self.config.get_field_name("blocked_by").as_str()) {
                            current_blocked_by = fv
                                .get("text")
                                .and_then(|t| t.as_str())
                                .unwrap_or("")
                                .to_string();
                        }
                    }
                }
                break;
            }

            if project_item_id.is_some() {
                break;
            }

            // Check for more pages
            let page_info = items_data.get("pageInfo");
            let has_next_page = page_info
                .and_then(|p| p.get("hasNextPage"))
                .and_then(|h| h.as_bool())
                .unwrap_or(false);

            if !has_next_page {
                break;
            }

            cursor = page_info
                .and_then(|p| p.get("endCursor"))
                .and_then(|c| c.as_str())
                .map(String::from);

            if cursor.is_none() || page == MAX_PAGES {
                warn!("Issue #{} not found after {} pages", issue_number, page);
                break;
            }
        }

        let project_item_id =
            project_item_id.ok_or_else(|| BoardError::IssueNotFound(issue_number))?;

        // Add blocker to list
        let mut blocked_by_list: Vec<String> = current_blocked_by
            .split(',')
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect();

        let blocker_str = blocker_number.to_string();
        if !blocked_by_list.contains(&blocker_str) {
            blocked_by_list.push(blocker_str);
        }

        let new_blocked_by = blocked_by_list.join(", ");

        // Get field ID (from stored field_data)
        let field_id = field_data
            .as_ref()
            .and_then(|f| f.get("id"))
            .and_then(|id| id.as_str())
            .ok_or_else(|| BoardError::FieldNotFound("Blocked By".to_string()))?;

        // Update field
        let mutation = r#"
        mutation UpdateProjectField($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
          updateProjectV2ItemFieldValue(
            input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: $value}
          ) {
            projectV2Item { id }
          }
        }
        "#;

        let variables = json!({
            "projectId": project_id,
            "itemId": project_item_id,
            "fieldId": field_id,
            "value": { "text": new_blocked_by }
        });

        self.client.execute(mutation, Some(variables)).await?;
        info!(
            "Added blocker: #{} now blocks #{}",
            blocker_number, issue_number
        );
        Ok(true)
    }

    /// Mark issue as discovered from parent.
    pub async fn mark_discovered_from(
        &self,
        issue_number: u64,
        parent_number: u64,
    ) -> Result<bool> {
        let project_id = self
            .project_id
            .as_ref()
            .ok_or_else(|| BoardError::Config("BoardManager not initialized".to_string()))?;

        info!(
            "Marking #{} as discovered from #{}",
            issue_number, parent_number
        );

        // Query with pagination support for boards with >100 items
        let query = r#"
        query GetProjectItemForDiscovery($projectId: ID!, $cursor: String) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100, after: $cursor) {
                pageInfo {
                  hasNextPage
                  endCursor
                }
                nodes {
                  id
                  content { ... on Issue { number } }
                }
              }
              field(name: "Discovered From") {
                ... on ProjectV2FieldCommon { id }
              }
            }
          }
        }
        "#;

        let mut cursor: Option<String> = None;
        let mut project_item_id: Option<String> = None;
        let mut field_data: Option<serde_json::Value> = None;
        const MAX_PAGES: usize = 10;

        for page in 1..=MAX_PAGES {
            let variables = match &cursor {
                Some(c) => json!({ "projectId": project_id, "cursor": c }),
                None => json!({ "projectId": project_id, "cursor": null }),
            };

            let response = self.client.execute(query, Some(variables)).await?;

            let data = response
                .data
                .ok_or_else(|| BoardError::GraphQL("Failed to get project item".to_string()))?;

            let node = data
                .get("node")
                .ok_or_else(|| BoardError::GraphQL("Node not found".to_string()))?;

            // Store field data from first page
            if field_data.is_none() {
                field_data = node.get("field").cloned();
            }

            let items_data = node
                .get("items")
                .ok_or_else(|| BoardError::GraphQL("Items not found".to_string()))?;

            let items = items_data
                .get("nodes")
                .and_then(|n| n.as_array())
                .ok_or_else(|| BoardError::GraphQL("Items nodes not found".to_string()))?;

            // Search for the issue in this page
            for item in items {
                if item
                    .get("content")
                    .and_then(|c| c.get("number"))
                    .and_then(|n| n.as_u64())
                    == Some(issue_number)
                {
                    project_item_id = item.get("id").and_then(|id| id.as_str()).map(String::from);
                    break;
                }
            }

            if project_item_id.is_some() {
                break;
            }

            // Check for more pages
            let page_info = items_data.get("pageInfo");
            let has_next_page = page_info
                .and_then(|p| p.get("hasNextPage"))
                .and_then(|h| h.as_bool())
                .unwrap_or(false);

            if !has_next_page {
                break;
            }

            cursor = page_info
                .and_then(|p| p.get("endCursor"))
                .and_then(|c| c.as_str())
                .map(String::from);

            if cursor.is_none() || page == MAX_PAGES {
                warn!("Issue #{} not found after {} pages", issue_number, page);
                break;
            }
        }

        let project_item_id =
            project_item_id.ok_or_else(|| BoardError::IssueNotFound(issue_number))?;

        let field_id = field_data
            .as_ref()
            .and_then(|f| f.get("id"))
            .and_then(|id| id.as_str())
            .ok_or_else(|| BoardError::FieldNotFound("Discovered From".to_string()))?;

        let mutation = r#"
        mutation UpdateProjectField($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
          updateProjectV2ItemFieldValue(
            input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: $value}
          ) {
            projectV2Item { id }
          }
        }
        "#;

        let variables = json!({
            "projectId": project_id,
            "itemId": project_item_id,
            "fieldId": field_id,
            "value": { "text": parent_number.to_string() }
        });

        self.client.execute(mutation, Some(variables)).await?;
        info!(
            "Marked #{} as discovered from #{}",
            issue_number, parent_number
        );
        Ok(true)
    }

    /// Get enabled agents list.
    pub fn get_enabled_agents(&self) -> &[String] {
        &self.config.enabled_agents
    }

    /// Get board configuration.
    pub fn get_config(&self) -> &BoardConfig {
        &self.config
    }

    /// Find approved issues using GitHub Search API.
    /// Returns issues with `[Approved][agent]` comments that may or may not be on the board.
    pub async fn find_approved_issues(&self, agent_name: &str) -> Result<Vec<ApprovedIssue>> {
        let (owner, repo) = self.parse_repository()?;

        info!("Finding approved issues for agent: {}", agent_name);

        // Pre-fetch all board issue numbers to avoid N+1 queries
        // This single query replaces potentially hundreds of get_issue calls
        let board_issue_numbers = self.get_board_issue_numbers().await?;
        info!(
            "Pre-fetched {} board issue numbers for membership check",
            board_issue_numbers.len()
        );

        // Build search query
        let search_query = format!(
            r#"repo:{}/{} is:issue is:open "[Approved][{}]" in:comments"#,
            owner, repo, agent_name
        );

        let mut approved_issues = Vec::new();
        let mut page = 1;

        loop {
            let page_str = page.to_string();
            let params = [
                ("q", search_query.as_str()),
                ("per_page", "100"),
                ("page", &page_str),
            ];

            let response = self
                .client
                .rest_get("/search/issues", Some(&params))
                .await?;

            let items = response
                .get("items")
                .and_then(|i| i.as_array())
                .map(|arr| arr.to_vec())
                .unwrap_or_default();

            if items.is_empty() {
                break;
            }

            // Check which issues are on the board (O(1) lookup instead of N queries)
            for item in &items {
                let number = item.get("number").and_then(|n| n.as_u64()).unwrap_or(0);
                let title = item
                    .get("title")
                    .and_then(|t| t.as_str())
                    .unwrap_or("")
                    .to_string();

                let on_board = board_issue_numbers.contains(&number);

                approved_issues.push(ApprovedIssue {
                    number,
                    title,
                    on_board,
                });
            }

            page += 1;
            // Safety limit: GitHub Search API max 1000 results (10 pages)
            if page > 10 {
                warn!("Reached max pagination limit (1000 results)");
                break;
            }
        }

        info!("Found {} approved issues", approved_issues.len());
        Ok(approved_issues)
    }

    /// Get all issue numbers on the board (for efficient membership checks).
    /// Uses pagination to fetch all items.
    async fn get_board_issue_numbers(&self) -> Result<std::collections::HashSet<u64>> {
        let project_id = self
            .project_id
            .as_ref()
            .ok_or_else(|| BoardError::Config("BoardManager not initialized".to_string()))?;

        let query = r#"
        query GetBoardIssueNumbers($projectId: ID!, $cursor: String) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100, after: $cursor) {
                pageInfo {
                  hasNextPage
                  endCursor
                }
                nodes {
                  content { ... on Issue { number } }
                }
              }
            }
          }
        }
        "#;

        let mut issue_numbers = std::collections::HashSet::new();
        let mut cursor: Option<String> = None;
        const MAX_PAGES: usize = 10;

        for page in 1..=MAX_PAGES {
            let variables = match &cursor {
                Some(c) => json!({ "projectId": project_id, "cursor": c }),
                None => json!({ "projectId": project_id, "cursor": null }),
            };

            let response = self.client.execute(query, Some(variables)).await?;

            let data = match response.data {
                Some(d) => d,
                None => break,
            };

            let items_data = data
                .get("node")
                .and_then(|n| n.get("items"))
                .ok_or_else(|| BoardError::GraphQL("Items not found".to_string()))?;

            let items = items_data
                .get("nodes")
                .and_then(|n| n.as_array())
                .ok_or_else(|| BoardError::GraphQL("Items nodes not found".to_string()))?;

            for item in items {
                if let Some(number) = item
                    .get("content")
                    .and_then(|c| c.get("number"))
                    .and_then(|n| n.as_u64())
                {
                    issue_numbers.insert(number);
                }
            }

            // Check for more pages
            let page_info = items_data.get("pageInfo");
            let has_next_page = page_info
                .and_then(|p| p.get("hasNextPage"))
                .and_then(|h| h.as_bool())
                .unwrap_or(false);

            if !has_next_page {
                break;
            }

            cursor = page_info
                .and_then(|p| p.get("endCursor"))
                .and_then(|c| c.as_str())
                .map(String::from);

            if cursor.is_none() || page == MAX_PAGES {
                break;
            }
        }

        Ok(issue_numbers)
    }

    /// Check if an issue has been approved by an authorized user.
    /// Returns (is_approved, approver).
    ///
    /// Uses pagination to check all comments (not just the last 100).
    pub async fn is_issue_approved(&self, issue_number: u64) -> Result<(bool, Option<String>)> {
        let (owner, repo) = self.parse_repository()?;

        // First, check the issue body
        let body_query = r#"
        query GetIssueBody($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            issue(number: $number) {
              body
              author { login }
            }
          }
        }
        "#;

        let variables = json!({
            "owner": owner,
            "repo": repo,
            "number": issue_number
        });

        let response = self.client.execute(body_query, Some(variables)).await?;

        let data = match response.data {
            Some(d) => d,
            None => return Ok((false, None)),
        };

        let issue_data = data.get("repository").and_then(|r| r.get("issue"));

        let issue_data = match issue_data {
            Some(i) => i,
            None => return Ok((false, None)),
        };

        // Check issue body first
        let body = issue_data
            .get("body")
            .and_then(|b| b.as_str())
            .unwrap_or("");
        let author = issue_data
            .get("author")
            .and_then(|a| a.get("login"))
            .and_then(|l| l.as_str())
            .unwrap_or("");

        if self.check_approval_trigger(body, author) {
            info!("Issue #{} approved by {} (in body)", issue_number, author);
            return Ok((true, Some(author.to_string())));
        }

        // Check comments with pagination (handles >100 comments)
        let comments_query = r#"
        query GetIssueComments($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
          repository(owner: $owner, name: $repo) {
            issue(number: $number) {
              comments(first: 100, after: $cursor) {
                pageInfo {
                  hasNextPage
                  endCursor
                }
                nodes {
                  body
                  author { login }
                }
              }
            }
          }
        }
        "#;

        let mut cursor: Option<String> = None;
        const MAX_COMMENT_PAGES: usize = 20; // Support up to 2000 comments

        for page in 1..=MAX_COMMENT_PAGES {
            let variables = json!({
                "owner": owner,
                "repo": repo,
                "number": issue_number,
                "cursor": cursor
            });

            let response = self.client.execute(comments_query, Some(variables)).await?;

            let data = match response.data {
                Some(d) => d,
                None => break,
            };

            let comments_data = data
                .get("repository")
                .and_then(|r| r.get("issue"))
                .and_then(|i| i.get("comments"));

            let comments_data = match comments_data {
                Some(c) => c,
                None => break,
            };

            let comments = comments_data.get("nodes").and_then(|n| n.as_array());

            if let Some(comments) = comments {
                for comment in comments {
                    let comment_body = comment.get("body").and_then(|b| b.as_str()).unwrap_or("");
                    let comment_author = comment
                        .get("author")
                        .and_then(|a| a.get("login"))
                        .and_then(|l| l.as_str())
                        .unwrap_or("");

                    if self.check_approval_trigger(comment_body, comment_author) {
                        info!(
                            "Issue #{} approved by {} (in comment, page {})",
                            issue_number, comment_author, page
                        );
                        return Ok((true, Some(comment_author.to_string())));
                    }
                }
            }

            // Check for more pages
            let page_info = comments_data.get("pageInfo");
            let has_next_page = page_info
                .and_then(|p| p.get("hasNextPage"))
                .and_then(|h| h.as_bool())
                .unwrap_or(false);

            if !has_next_page {
                break;
            }

            cursor = page_info
                .and_then(|p| p.get("endCursor"))
                .and_then(|c| c.as_str())
                .map(String::from);

            if cursor.is_none() || page == MAX_COMMENT_PAGES {
                warn!(
                    "Issue #{} has many comments, stopped at page {}",
                    issue_number, page
                );
                break;
            }
        }

        info!("Issue #{} not approved", issue_number);
        Ok((false, None))
    }

    /// Check if text contains a valid approval trigger from an authorized user.
    ///
    /// Username comparison is case-insensitive since GitHub usernames are case-insensitive.
    ///
    /// Uses cached allowed users and pre-compiled regex for performance.
    fn check_approval_trigger(&self, text: &str, author: &str) -> bool {
        if text.is_empty() || author.is_empty() {
            return false;
        }

        // Use cached allowed users (case-insensitive comparison)
        if !self.cached_allowed_users.contains(&author.to_lowercase()) {
            return false;
        }

        // Use pre-compiled regex pattern
        APPROVAL_PATTERN.is_match(text)
    }

    /// Add an issue to the project board with fields.
    pub async fn add_issue_to_board(
        &self,
        issue_number: u64,
        status: IssueStatus,
        priority: Option<IssuePriority>,
        issue_type: Option<IssueType>,
        agent: Option<&str>,
    ) -> Result<bool> {
        let project_id = self
            .project_id
            .as_ref()
            .ok_or_else(|| BoardError::Config("BoardManager not initialized".to_string()))?;

        let (owner, repo) = self.parse_repository()?;

        info!("Adding issue #{} to board", issue_number);

        // Step 1: Get the issue node ID
        let query = r#"
        query GetIssueId($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            issue(number: $number) { id }
          }
        }
        "#;

        let variables = json!({
            "owner": owner,
            "repo": repo,
            "number": issue_number
        });

        let response = self.client.execute(query, Some(variables)).await?;

        let data = response
            .data
            .ok_or_else(|| BoardError::IssueNotFound(issue_number))?;

        let issue_id = data
            .get("repository")
            .and_then(|r| r.get("issue"))
            .and_then(|i| i.get("id"))
            .and_then(|id| id.as_str())
            .ok_or_else(|| BoardError::IssueNotFound(issue_number))?;

        // Step 2: Add to project
        let mutation = r#"
        mutation AddToProject($projectId: ID!, $contentId: ID!) {
          addProjectV2ItemByContentId(input: {projectId: $projectId, contentId: $contentId}) {
            item { id }
          }
        }
        "#;

        let variables = json!({
            "projectId": project_id,
            "contentId": issue_id
        });

        let response = self.client.execute(mutation, Some(variables)).await?;

        let data = response
            .data
            .ok_or_else(|| BoardError::GraphQL("Failed to add issue to project".to_string()))?;

        let project_item_id = data
            .get("addProjectV2ItemByContentId")
            .and_then(|a| a.get("item"))
            .and_then(|i| i.get("id"))
            .and_then(|id| id.as_str())
            .ok_or_else(|| BoardError::GraphQL("Failed to get project item ID".to_string()))?;

        // Step 3: Set status field
        self.set_project_item_status(project_item_id, status)
            .await?;

        // Step 4: Set optional fields
        if let Some(p) = priority {
            self.set_project_item_priority(project_item_id, p).await?;
        }

        if let Some(t) = issue_type {
            self.set_project_item_type(project_item_id, t).await?;
        }

        if let Some(a) = agent {
            self.set_project_item_agent(project_item_id, a).await?;
        }

        info!("Added issue #{} to board", issue_number);
        Ok(true)
    }

    /// Set project item status.
    async fn set_project_item_status(&self, item_id: &str, status: IssueStatus) -> Result<()> {
        let project_id = self
            .project_id
            .as_ref()
            .ok_or_else(|| BoardError::Config("BoardManager not initialized".to_string()))?;

        // Get status field info
        let query = r#"
        query GetStatusField($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              field(name: "Status") {
                ... on ProjectV2SingleSelectField {
                  id
                  options { id name }
                }
              }
            }
          }
        }
        "#;

        let response = self
            .client
            .execute(query, Some(json!({ "projectId": project_id })))
            .await?;

        let data = response
            .data
            .ok_or_else(|| BoardError::FieldNotFound("Status".to_string()))?;

        let field = data
            .get("node")
            .and_then(|n| n.get("field"))
            .ok_or_else(|| BoardError::FieldNotFound("Status".to_string()))?;

        let field_id = field
            .get("id")
            .and_then(|id| id.as_str())
            .ok_or_else(|| BoardError::FieldNotFound("Status".to_string()))?;

        let options = field
            .get("options")
            .and_then(|o| o.as_array())
            .ok_or_else(|| BoardError::FieldNotFound("Status options".to_string()))?;

        let status_value = status.as_str();
        let option_id = options
            .iter()
            .find(|opt| opt.get("name").and_then(|n| n.as_str()) == Some(status_value))
            .and_then(|opt| opt.get("id"))
            .and_then(|id| id.as_str())
            .ok_or_else(|| {
                BoardError::InvalidFieldValue(status_value.to_string(), "Status".to_string())
            })?;

        // Update field
        let mutation = r#"
        mutation UpdateProjectField($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
          updateProjectV2ItemFieldValue(
            input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: $value}
          ) {
            projectV2Item { id }
          }
        }
        "#;

        let variables = json!({
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": field_id,
            "value": { "singleSelectOptionId": option_id }
        });

        self.client.execute(mutation, Some(variables)).await?;
        Ok(())
    }

    /// Set project item priority.
    async fn set_project_item_priority(
        &self,
        item_id: &str,
        priority: IssuePriority,
    ) -> Result<()> {
        self.set_single_select_field(item_id, "Priority", priority.as_str())
            .await
    }

    /// Set project item type.
    async fn set_project_item_type(&self, item_id: &str, issue_type: IssueType) -> Result<()> {
        self.set_single_select_field(item_id, "Type", issue_type.as_str())
            .await
    }

    /// Set project item agent.
    async fn set_project_item_agent(&self, item_id: &str, agent: &str) -> Result<()> {
        self.set_single_select_field(item_id, "Agent", agent).await
    }

    /// Generic single-select field setter.
    async fn set_single_select_field(
        &self,
        item_id: &str,
        field_name: &str,
        value: &str,
    ) -> Result<()> {
        let project_id = self
            .project_id
            .as_ref()
            .ok_or_else(|| BoardError::Config("BoardManager not initialized".to_string()))?;

        // Get field info
        let query = format!(
            r#"
        query GetField($projectId: ID!) {{
          node(id: $projectId) {{
            ... on ProjectV2 {{
              field(name: "{}") {{
                ... on ProjectV2SingleSelectField {{
                  id
                  options {{ id name }}
                }}
              }}
            }}
          }}
        }}
        "#,
            field_name
        );

        let response = self
            .client
            .execute(&query, Some(json!({ "projectId": project_id })))
            .await?;

        let data = match response.data {
            Some(d) => d,
            None => {
                debug!("Field {} not found, skipping", field_name);
                return Ok(());
            }
        };

        let field = match data.get("node").and_then(|n| n.get("field")) {
            Some(f) if !f.is_null() => f,
            _ => {
                debug!("Field {} not found, skipping", field_name);
                return Ok(());
            }
        };

        let field_id = match field.get("id").and_then(|id| id.as_str()) {
            Some(id) => id,
            None => {
                debug!("Field {} has no ID, skipping", field_name);
                return Ok(());
            }
        };

        let options = match field.get("options").and_then(|o| o.as_array()) {
            Some(o) => o,
            None => {
                debug!("Field {} has no options, skipping", field_name);
                return Ok(());
            }
        };

        let option_id = match options
            .iter()
            .find(|opt| opt.get("name").and_then(|n| n.as_str()) == Some(value))
            .and_then(|opt| opt.get("id"))
            .and_then(|id| id.as_str())
        {
            Some(id) => id,
            None => {
                debug!(
                    "Option {} not found in field {}, skipping",
                    value, field_name
                );
                return Ok(());
            }
        };

        let mutation = r#"
        mutation UpdateProjectField($projectId: ID!, $itemId: ID!, $fieldId: ID!, $value: ProjectV2FieldValue!) {
          updateProjectV2ItemFieldValue(
            input: {projectId: $projectId, itemId: $itemId, fieldId: $fieldId, value: $value}
          ) {
            projectV2Item { id }
          }
        }
        "#;

        let variables = json!({
            "projectId": project_id,
            "itemId": item_id,
            "fieldId": field_id,
            "value": { "singleSelectOptionId": option_id }
        });

        self.client.execute(mutation, Some(variables)).await?;
        Ok(())
    }

    // ===== Helper Methods =====

    /// Parse field values from a project item.
    fn parse_field_values(&self, item: &Value) -> HashMap<String, String> {
        let mut values = HashMap::new();

        let nodes = item
            .get("fieldValues")
            .and_then(|fv| fv.get("nodes"))
            .and_then(|n| n.as_array());

        if let Some(nodes) = nodes {
            for node in nodes {
                let field_name = node
                    .get("field")
                    .and_then(|f| f.get("name"))
                    .and_then(|n| n.as_str());

                if let Some(name) = field_name {
                    // Single select value
                    if let Some(value) = node.get("name").and_then(|n| n.as_str()) {
                        values.insert(name.to_string(), value.to_string());
                    }
                    // Text value
                    else if let Some(value) = node.get("text").and_then(|t| t.as_str()) {
                        values.insert(name.to_string(), value.to_string());
                    }
                }
            }
        }

        values
    }

    /// Parse issue metadata from field values.
    fn parse_issue_metadata(
        &self,
        field_values: &HashMap<String, String>,
    ) -> (
        IssueStatus,
        IssuePriority,
        Option<IssueType>,
        Option<String>,
        Vec<u64>,
    ) {
        let status = field_values
            .get(&self.config.get_field_name("status"))
            .and_then(|s| IssueStatus::from_str(s))
            .unwrap_or_default();

        let priority = field_values
            .get(&self.config.get_field_name("priority"))
            .and_then(|p| IssuePriority::from_str(p))
            .unwrap_or_default();

        let issue_type = field_values
            .get(&self.config.get_field_name("type"))
            .and_then(|t| IssueType::from_str(t));

        let agent = field_values
            .get(&self.config.get_field_name("agent"))
            .cloned();

        let blocked_by = field_values
            .get(&self.config.get_field_name("blocked_by"))
            .map(|s| s.split(',').filter_map(|n| n.trim().parse().ok()).collect())
            .unwrap_or_default();

        (status, priority, issue_type, agent, blocked_by)
    }

    /// Parse discovered_from field.
    fn parse_discovered_from(&self, field_values: &HashMap<String, String>) -> Option<u64> {
        field_values
            .get(&self.config.get_field_name("discovered_from"))
            .and_then(|s| s.trim().parse().ok())
    }

    /// Parse labels from content.
    fn parse_labels(&self, content: &Value) -> Vec<String> {
        content
            .get("labels")
            .and_then(|l| l.get("nodes"))
            .and_then(|n| n.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|l| {
                        l.get("name")
                            .and_then(|n| n.as_str())
                            .map(|s| s.to_string())
                    })
                    .collect()
            })
            .unwrap_or_default()
    }

    /// Create an Issue from project item data.
    #[allow(clippy::too_many_arguments)]
    fn create_issue_from_item(
        &self,
        item: &Value,
        content: &Value,
        status: IssueStatus,
        priority: IssuePriority,
        issue_type: Option<IssueType>,
        agent: Option<String>,
        blocked_by: Vec<u64>,
        discovered_from: Option<u64>,
    ) -> Result<Issue> {
        let number = content
            .get("number")
            .and_then(|n| n.as_u64())
            .ok_or_else(|| BoardError::GraphQL("Issue number not found".to_string()))?;

        let title = content
            .get("title")
            .and_then(|t| t.as_str())
            .unwrap_or("")
            .to_string();

        let body = content
            .get("body")
            .and_then(|b| b.as_str())
            .unwrap_or("")
            .to_string();

        let state = content
            .get("state")
            .and_then(|s| s.as_str())
            .unwrap_or("OPEN")
            .to_lowercase();

        let created_at = content
            .get("createdAt")
            .and_then(|t| t.as_str())
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
            .map(|dt| dt.with_timezone(&Utc));

        let updated_at = content
            .get("updatedAt")
            .and_then(|t| t.as_str())
            .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
            .map(|dt| dt.with_timezone(&Utc));

        let url = content
            .get("url")
            .and_then(|u| u.as_str())
            .map(|s| s.to_string());

        let labels = self.parse_labels(content);

        let project_item_id = item
            .get("id")
            .and_then(|id| id.as_str())
            .map(|s| s.to_string());

        Ok(Issue {
            number,
            title,
            body,
            state,
            status,
            priority,
            issue_type,
            size: None,
            agent,
            blocked_by,
            discovered_from,
            created_at,
            updated_at,
            url,
            labels,
            project_item_id,
        })
    }

    /// Get active claim for an issue.
    async fn get_active_claim(&self, issue_number: u64) -> Result<Option<AgentClaim>> {
        let (owner, repo) = self.parse_repository()?;

        let query = r#"
        query GetIssueComments($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            issue(number: $number) {
              comments(last: 50) {
                nodes {
                  body
                  createdAt
                }
              }
            }
          }
        }
        "#;

        let variables = json!({
            "owner": owner,
            "repo": repo,
            "number": issue_number
        });

        let response = self.client.execute(query, Some(variables)).await?;

        let data = match response.data {
            Some(d) => d,
            None => return Ok(None),
        };

        let comments = data
            .get("repository")
            .and_then(|r| r.get("issue"))
            .and_then(|i| i.get("comments"))
            .and_then(|c| c.get("nodes"))
            .and_then(|n| n.as_array());

        let comments = match comments {
            Some(c) => c,
            None => return Ok(None),
        };

        // Find most recent claim/release
        for comment in comments.iter().rev() {
            let body = comment.get("body").and_then(|b| b.as_str()).unwrap_or("");

            // Check for release (invalidates any prior claim)
            if body.contains(RELEASE_PREFIX) {
                return Ok(None);
            }

            // Check for claim or renewal
            if (body.contains(CLAIM_PREFIX) || body.contains(RENEWAL_PREFIX))
                && let Some(claim) = self.parse_claim_comment(body, issue_number)
            {
                return Ok(Some(claim));
            }
        }

        Ok(None)
    }

    /// Parse a claim comment into AgentClaim.
    fn parse_claim_comment(&self, body: &str, issue_number: u64) -> Option<AgentClaim> {
        // Parse agent name
        let agent = body
            .lines()
            .find(|l| l.starts_with("Agent:"))
            .and_then(|l| l.strip_prefix("Agent:"))
            .map(|s| s.trim().trim_matches('`').to_string())?;

        // Parse session ID
        let session_id = body
            .lines()
            .find(|l| l.starts_with("Session ID:"))
            .and_then(|l| l.strip_prefix("Session ID:"))
            .map(|s| s.trim().trim_matches('`').to_string())?;

        // Parse timestamp
        let timestamp_str = body
            .lines()
            .find(|l| l.starts_with("Started:") || l.starts_with("Renewed:"))
            .and_then(|l| {
                l.strip_prefix("Started:")
                    .or_else(|| l.strip_prefix("Renewed:"))
            })
            .map(|s| s.trim().trim_matches('`'))?;

        let timestamp = DateTime::parse_from_rfc3339(timestamp_str)
            .ok()
            .map(|dt| dt.with_timezone(&Utc))?;

        let renewed_at = if body.contains(RENEWAL_PREFIX) {
            Some(timestamp)
        } else {
            None
        };

        Some(AgentClaim {
            issue_number,
            agent,
            session_id,
            timestamp,
            renewed_at,
            released: false,
        })
    }

    /// Post a comment to an issue.
    async fn post_issue_comment(&self, issue_number: u64, body: &str) -> Result<()> {
        let (owner, repo) = self.parse_repository()?;

        // Get issue node ID
        let query = r#"
        query GetIssueId($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            issue(number: $number) { id }
          }
        }
        "#;

        let variables = json!({
            "owner": owner,
            "repo": repo,
            "number": issue_number
        });

        let response = self.client.execute(query, Some(variables)).await?;

        let data = response
            .data
            .ok_or_else(|| BoardError::IssueNotFound(issue_number))?;

        let issue_id = data
            .get("repository")
            .and_then(|r| r.get("issue"))
            .and_then(|i| i.get("id"))
            .and_then(|id| id.as_str())
            .ok_or_else(|| BoardError::IssueNotFound(issue_number))?;

        // Post comment
        let mutation = r#"
        mutation AddComment($subjectId: ID!, $body: String!) {
          addComment(input: {subjectId: $subjectId, body: $body}) {
            commentEdge { node { id } }
          }
        }
        "#;

        let variables = json!({
            "subjectId": issue_id,
            "body": body
        });

        self.client.execute(mutation, Some(variables)).await?;
        debug!("Posted comment to #{}", issue_number);
        Ok(())
    }

    /// Parse repository into owner and name.
    fn parse_repository(&self) -> Result<(String, String)> {
        let parts: Vec<&str> = self.config.repository.split('/').collect();
        if parts.len() != 2 {
            return Err(BoardError::Config(format!(
                "Invalid repository format: {}",
                self.config.repository
            )));
        }
        Ok((parts[0].to_string(), parts[1].to_string()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normalize_agent_name() {
        assert_eq!(BoardManager::normalize_agent_name("claude"), "Claude Code");
        assert_eq!(BoardManager::normalize_agent_name("CLAUDE"), "Claude Code");
        assert_eq!(BoardManager::normalize_agent_name("Unknown"), "Unknown");
    }

    #[test]
    fn test_parse_claim_comment() {
        let body = "**[Agent Claim]**\n\nAgent: `Claude Code`\nStarted: `2024-01-15T10:00:00Z`\nSession ID: `abc123`\n\nClaiming this issue.";

        // Create a minimal manager for testing
        let config = BoardConfig::default();
        let manager = BoardManager {
            client: GraphQLClient::new("test".to_string()).unwrap(),
            config,
            project_id: None,
            cached_allowed_users: std::collections::HashSet::new(),
        };

        let claim = manager.parse_claim_comment(body, 123);
        assert!(claim.is_some());
        let claim = claim.unwrap();
        assert_eq!(claim.agent, "Claude Code");
        assert_eq!(claim.session_id, "abc123");
        assert_eq!(claim.issue_number, 123);
    }
}
