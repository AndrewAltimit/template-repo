//! GitHub Projects v2 board manager with GraphQL operations.

use chrono::{DateTime, Utc};
use serde_json::{json, Value};
use std::collections::HashMap;
use tracing::{debug, info, warn};

use crate::client::GraphQLClient;
use crate::error::{BoardError, Result};
use crate::models::{
    AgentClaim, BoardConfig, Issue, IssuePriority, IssueStatus, IssueType, ReleaseReason,
};

/// Claim comment prefixes.
const CLAIM_PREFIX: &str = "**[Agent Claim]**";
const RENEWAL_PREFIX: &str = "**[Claim Renewal]**";
const RELEASE_PREFIX: &str = "**[Agent Release]**";

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
}

impl BoardManager {
    /// Create a new BoardManager.
    pub fn new(config: BoardConfig, token: String) -> Result<Self> {
        let client = GraphQLClient::new(token)?;
        Ok(Self {
            client,
            config,
            project_id: None,
        })
    }

    /// Initialize the manager by loading project metadata.
    pub async fn initialize(&mut self) -> Result<()> {
        self.project_id = Some(self.get_project_id().await?);
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
    pub async fn get_ready_work(&self, agent_name: Option<&str>, limit: usize) -> Result<Vec<Issue>> {
        let project_id = self.project_id.as_ref().ok_or_else(|| {
            BoardError::Config("BoardManager not initialized".to_string())
        })?;

        info!("Getting ready work (agent={:?}, limit={})", agent_name, limit);

        let query = r#"
        query GetProjectItems($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100) {
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

        let variables = json!({ "projectId": project_id });
        let response = self.client.execute(query, Some(variables)).await?;

        let data = response.data.ok_or_else(|| {
            BoardError::GraphQL("Failed to fetch project items".to_string())
        })?;

        let items = data
            .get("node")
            .and_then(|n| n.get("items"))
            .and_then(|i| i.get("nodes"))
            .and_then(|n| n.as_array())
            .ok_or_else(|| BoardError::GraphQL("Invalid response structure".to_string()))?;

        let normalized_agent = agent_name.map(Self::normalize_agent_name);
        let mut ready_issues = Vec::new();

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
            if labels.iter().any(|l| self.config.exclude_labels.contains(l)) {
                continue;
            }

            let issue = self.create_issue_from_item(
                item, content, status, priority, issue_type, assigned_agent, blocked_by, None,
            )?;

            ready_issues.push(issue);

            if ready_issues.len() >= limit {
                break;
            }
        }

        // Sort by priority
        ready_issues.sort_by_key(|issue| match issue.priority {
            IssuePriority::Critical => 0,
            IssuePriority::High => 1,
            IssuePriority::Medium => 2,
            IssuePriority::Low => 3,
        });

        info!("Found {} ready issues", ready_issues.len());
        Ok(ready_issues)
    }

    /// Get a specific issue by number.
    pub async fn get_issue(&self, issue_number: u64) -> Result<Option<Issue>> {
        let project_id = self.project_id.as_ref().ok_or_else(|| {
            BoardError::Config("BoardManager not initialized".to_string())
        })?;

        info!("Getting issue #{}", issue_number);

        let query = r#"
        query GetProjectItems($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100) {
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

        let variables = json!({ "projectId": project_id });
        let response = self.client.execute(query, Some(variables)).await?;

        let data = response.data.ok_or_else(|| {
            BoardError::GraphQL("Failed to fetch project items".to_string())
        })?;

        let items = data
            .get("node")
            .and_then(|n| n.get("items"))
            .and_then(|i| i.get("nodes"))
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
        info!("Claiming issue #{} by {} (session: {})", issue_number, agent_name, session_id);

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
        self.update_status(issue_number, IssueStatus::InProgress).await?;

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
                warn!("Cannot renew claim on #{}: no active claim by {}", issue_number, agent_name);
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
                self.update_status(issue_number, IssueStatus::Blocked).await?;
            }
            ReleaseReason::Abandoned | ReleaseReason::Error => {
                self.update_status(issue_number, IssueStatus::Todo).await?;
            }
        }

        info!("Released claim on #{} by {} (reason: {})", issue_number, agent_name, reason);
        Ok(())
    }

    /// Update issue status on board.
    pub async fn update_status(&self, issue_number: u64, status: IssueStatus) -> Result<bool> {
        let project_id = self.project_id.as_ref().ok_or_else(|| {
            BoardError::Config("BoardManager not initialized".to_string())
        })?;

        let query = r#"
        query GetProjectItem($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100) {
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

        let response = self.client.execute(query, Some(json!({ "projectId": project_id }))).await?;

        let data = response.data.ok_or_else(|| {
            BoardError::GraphQL("Failed to get project item".to_string())
        })?;

        let node = data.get("node").ok_or_else(|| {
            BoardError::GraphQL("Node not found".to_string())
        })?;

        // Find project item ID
        let items = node
            .get("items")
            .and_then(|i| i.get("nodes"))
            .and_then(|n| n.as_array())
            .ok_or_else(|| BoardError::GraphQL("Items not found".to_string()))?;

        let project_item_id = items
            .iter()
            .find(|item| {
                item.get("content")
                    .and_then(|c| c.get("number"))
                    .and_then(|n| n.as_u64())
                    == Some(issue_number)
            })
            .and_then(|item| item.get("id"))
            .and_then(|id| id.as_str())
            .ok_or_else(|| BoardError::IssueNotFound(issue_number))?;

        // Get field ID and option ID
        let field = node.get("field").ok_or_else(|| {
            BoardError::FieldNotFound("Status".to_string())
        })?;

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
        let project_id = self.project_id.as_ref().ok_or_else(|| {
            BoardError::Config("BoardManager not initialized".to_string())
        })?;

        info!("Adding blocker: #{} blocks #{}", blocker_number, issue_number);

        let query = r#"
        query GetProjectItemForBlocker($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100) {
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

        let response = self.client.execute(query, Some(json!({ "projectId": project_id }))).await?;

        let data = response.data.ok_or_else(|| {
            BoardError::GraphQL("Failed to get project item".to_string())
        })?;

        let node = data.get("node").ok_or_else(|| {
            BoardError::GraphQL("Node not found".to_string())
        })?;

        let items = node
            .get("items")
            .and_then(|i| i.get("nodes"))
            .and_then(|n| n.as_array())
            .ok_or_else(|| BoardError::GraphQL("Items not found".to_string()))?;

        // Find project item and current blocked_by value
        let mut project_item_id = None;
        let mut current_blocked_by = String::new();

        for item in items {
            let content = item.get("content");
            if content.and_then(|c| c.get("number")).and_then(|n| n.as_u64()) != Some(issue_number) {
                continue;
            }

            project_item_id = item.get("id").and_then(|id| id.as_str()).map(|s| s.to_string());

            // Find blocked_by field value
            if let Some(field_values) = item.get("fieldValues").and_then(|f| f.get("nodes")).and_then(|n| n.as_array()) {
                for fv in field_values {
                    let field_name = fv.get("field").and_then(|f| f.get("name")).and_then(|n| n.as_str());
                    if field_name == Some(self.config.get_field_name("blocked_by").as_str()) {
                        current_blocked_by = fv.get("text").and_then(|t| t.as_str()).unwrap_or("").to_string();
                    }
                }
            }
            break;
        }

        let project_item_id = project_item_id.ok_or_else(|| BoardError::IssueNotFound(issue_number))?;

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

        // Get field ID
        let field_id = node
            .get("field")
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
        info!("Added blocker: #{} now blocks #{}", blocker_number, issue_number);
        Ok(true)
    }

    /// Mark issue as discovered from parent.
    pub async fn mark_discovered_from(&self, issue_number: u64, parent_number: u64) -> Result<bool> {
        let project_id = self.project_id.as_ref().ok_or_else(|| {
            BoardError::Config("BoardManager not initialized".to_string())
        })?;

        info!("Marking #{} as discovered from #{}", issue_number, parent_number);

        let query = r#"
        query GetProjectItemForDiscovery($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              items(first: 100) {
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

        let response = self.client.execute(query, Some(json!({ "projectId": project_id }))).await?;

        let data = response.data.ok_or_else(|| {
            BoardError::GraphQL("Failed to get project item".to_string())
        })?;

        let node = data.get("node").ok_or_else(|| {
            BoardError::GraphQL("Node not found".to_string())
        })?;

        let items = node
            .get("items")
            .and_then(|i| i.get("nodes"))
            .and_then(|n| n.as_array())
            .ok_or_else(|| BoardError::GraphQL("Items not found".to_string()))?;

        let project_item_id = items
            .iter()
            .find(|item| {
                item.get("content")
                    .and_then(|c| c.get("number"))
                    .and_then(|n| n.as_u64())
                    == Some(issue_number)
            })
            .and_then(|item| item.get("id"))
            .and_then(|id| id.as_str())
            .ok_or_else(|| BoardError::IssueNotFound(issue_number))?;

        let field_id = node
            .get("field")
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
        info!("Marked #{} as discovered from #{}", issue_number, parent_number);
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
    ) -> (IssueStatus, IssuePriority, Option<IssueType>, Option<String>, Vec<u64>) {
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
            .map(|s| {
                s.split(',')
                    .filter_map(|n| n.trim().parse().ok())
                    .collect()
            })
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
                    .filter_map(|l| l.get("name").and_then(|n| n.as_str()).map(|s| s.to_string()))
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

        let data = response.data.ok_or_else(|| {
            BoardError::IssueNotFound(issue_number)
        })?;

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
        };

        let claim = manager.parse_claim_comment(body, 123);
        assert!(claim.is_some());
        let claim = claim.unwrap();
        assert_eq!(claim.agent, "Claude Code");
        assert_eq!(claim.session_id, "abc123");
        assert_eq!(claim.issue_number, 123);
    }
}
