//! Pure parsing and selection logic for project board data.
//!
//! Everything here operates on already-fetched GraphQL JSON so it can be
//! unit-tested without network access.

use chrono::{DateTime, Utc};
use serde_json::Value;
use std::collections::{HashMap, HashSet};

use crate::models::{BoardConfig, DependencyGraph, Issue, IssueRef, IssueStatus, same_agent};

/// Kind of a project field.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FieldKind {
    SingleSelect,
    Text,
    Other,
}

/// A project field definition.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProjectField {
    pub id: String,
    pub name: String,
    pub kind: FieldKind,
    /// `(option id, option name)` for single-select fields.
    pub options: Vec<(String, String)>,
}

impl ProjectField {
    /// Option ID for a value (case-insensitive match on the option name).
    pub fn option_id(&self, value: &str) -> Option<&str> {
        self.options
            .iter()
            .find(|(_, name)| name.eq_ignore_ascii_case(value.trim()))
            .map(|(id, _)| id.as_str())
    }

    /// Option names, for error messages.
    pub fn option_names(&self) -> Vec<&str> {
        self.options.iter().map(|(_, n)| n.as_str()).collect()
    }
}

/// All fields of a project, keyed by lowercase name.
#[derive(Debug, Clone, Default)]
pub struct ProjectFields {
    by_name: HashMap<String, ProjectField>,
}

impl ProjectFields {
    /// Parse `fields.nodes` from a ProjectV2 query.
    pub fn from_nodes(nodes: &[Value]) -> Self {
        let by_name = nodes
            .iter()
            .filter_map(|n| {
                let id = n.get("id")?.as_str()?.to_string();
                let name = n.get("name")?.as_str()?.to_string();
                let kind = match n.get("dataType").and_then(Value::as_str) {
                    Some("SINGLE_SELECT") => FieldKind::SingleSelect,
                    Some("TEXT") => FieldKind::Text,
                    _ if n.get("options").is_some() => FieldKind::SingleSelect,
                    _ => FieldKind::Other,
                };
                let options = n
                    .get("options")
                    .and_then(Value::as_array)
                    .map(|opts| {
                        opts.iter()
                            .filter_map(|o| {
                                Some((
                                    o.get("id")?.as_str()?.to_string(),
                                    o.get("name")?.as_str()?.to_string(),
                                ))
                            })
                            .collect()
                    })
                    .unwrap_or_default();
                Some((
                    name.to_lowercase(),
                    ProjectField {
                        id,
                        name,
                        kind,
                        options,
                    },
                ))
            })
            .collect();
        Self { by_name }
    }

    /// Look up a field by board name (case-insensitive).
    pub fn get(&self, name: &str) -> Option<&ProjectField> {
        self.by_name.get(&name.to_lowercase())
    }

    /// Number of fields defined on the project.
    pub fn field_count(&self) -> usize {
        self.by_name.len()
    }
}

/// Parse an item's `fieldValues.nodes` into `field name -> value`.
/// Single-select, text and number values are supported.
pub fn field_values(item: &Value) -> HashMap<String, String> {
    let Some(nodes) = item
        .get("fieldValues")
        .and_then(|fv| fv.get("nodes"))
        .and_then(Value::as_array)
    else {
        return HashMap::new();
    };

    nodes
        .iter()
        .filter_map(|node| {
            let field = node.get("field")?.get("name")?.as_str()?;
            let value = node
                .get("name")
                .and_then(Value::as_str)
                .map(String::from)
                .or_else(|| node.get("text").and_then(Value::as_str).map(String::from))
                .or_else(|| {
                    node.get("number")
                        .and_then(Value::as_f64)
                        .map(|n| n.to_string())
                })?;
            Some((field.to_lowercase(), value))
        })
        .collect()
}

/// Parse a list of issue numbers such as `"12, #13 14"`.
pub fn parse_number_list(s: &str) -> Vec<u64> {
    let mut out: Vec<u64> = Vec::new();
    for n in s
        .split(|c: char| c == ',' || c.is_whitespace())
        .filter_map(|t| t.trim().trim_start_matches('#').parse().ok())
    {
        if !out.contains(&n) {
            out.push(n);
        }
    }
    out
}

/// Format a list of issue numbers the way the board stores it.
pub fn format_number_list(numbers: &[u64]) -> String {
    numbers
        .iter()
        .map(u64::to_string)
        .collect::<Vec<_>>()
        .join(", ")
}

fn parse_time(v: Option<&Value>) -> Option<DateTime<Utc>> {
    v.and_then(Value::as_str)
        .and_then(|s| DateTime::parse_from_rfc3339(s).ok())
        .map(|dt| dt.with_timezone(&Utc))
}

fn str_field(v: &Value, key: &str) -> String {
    v.get(key)
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string()
}

/// Build an [`Issue`] from issue `content` plus its project `item` (which
/// carries `id` and `fieldValues`). Returns `None` when `content` is not an
/// issue (draft items and pull requests have no `number`/`state` pair).
pub fn issue_from_item(item: &Value, content: &Value, config: &BoardConfig) -> Option<Issue> {
    let number = content.get("number")?.as_u64()?;
    // Pull requests on the board also have numbers; the Issue fragment is the
    // only one that selects `state`, so its absence means "not an issue".
    let state = content.get("state")?.as_str()?.to_lowercase();
    let values = field_values(item);
    let get = |key: &str| values.get(&config.get_field_name(key).to_lowercase());

    let labels: Vec<String> = content
        .get("labels")
        .and_then(|l| l.get("nodes"))
        .and_then(Value::as_array)
        .map(|arr| {
            arr.iter()
                .filter_map(|l| l.get("name").and_then(Value::as_str).map(String::from))
                .collect()
        })
        .unwrap_or_default();

    let priority = get("priority")
        .and_then(|p| p.parse().ok())
        .or_else(|| config.priority_from_labels(&labels))
        .unwrap_or_default();
    let issue_type = get("type")
        .and_then(|t| t.parse().ok())
        .or_else(|| config.type_from_labels(&labels));

    Some(Issue {
        number,
        title: str_field(content, "title"),
        body: str_field(content, "body"),
        state,
        status: get("status")
            .and_then(|s| s.parse().ok())
            .unwrap_or_default(),
        priority,
        issue_type,
        size: get("size").and_then(|s| s.parse().ok()),
        agent: get("agent").cloned().filter(|a| !a.trim().is_empty()),
        blocked_by: get("blocked_by")
            .map(|s| parse_number_list(s))
            .unwrap_or_default(),
        discovered_from: get("discovered_from").and_then(|s| parse_number_list(s).first().copied()),
        created_at: parse_time(content.get("createdAt")),
        updated_at: parse_time(content.get("updatedAt")),
        url: content.get("url").and_then(Value::as_str).map(String::from),
        labels,
        project_item_id: item.get("id").and_then(Value::as_str).map(String::from),
    })
}

/// Parse a page of board item nodes into issues (non-issue items skipped).
pub fn issues_from_items(items: &[Value], config: &BoardConfig) -> Vec<Issue> {
    items
        .iter()
        .filter_map(|item| {
            let content = item.get("content").filter(|c| !c.is_null())?;
            issue_from_item(item, content, config)
        })
        .collect()
}

/// Filters for the ready-work query.
#[derive(Debug, Clone, Default)]
pub struct ReadyFilter {
    /// Only issues unassigned or assigned to this agent.
    pub agent: Option<String>,
    /// Only issues having at least one of these labels (case-insensitive).
    pub include_labels: Vec<String>,
    /// Exclude issues having any of these labels (in addition to config).
    pub exclude_labels: Vec<String>,
}

fn has_any_label(issue: &Issue, labels: &[String]) -> bool {
    issue
        .labels
        .iter()
        .any(|l| labels.iter().any(|x| x.eq_ignore_ascii_case(l)))
}

/// Whether every blocker of `issue` is resolved, given all board issues.
/// Blockers that are not on the board count as unresolved (fail safe).
pub fn blockers_resolved(issue: &Issue, by_number: &HashMap<u64, &Issue>) -> bool {
    issue.blocked_by.iter().all(|b| {
        by_number
            .get(b)
            .is_some_and(|blocker| blocker.resolves_dependency())
    })
}

/// Select ready work: open, status Todo, unblocked (or all blockers resolved),
/// not assigned to another agent, label filters applied. Sorted by priority,
/// then oldest first, then issue number.
pub fn select_ready(all: &[Issue], filter: &ReadyFilter, config: &BoardConfig) -> Vec<Issue> {
    let by_number: HashMap<u64, &Issue> = all.iter().map(|i| (i.number, i)).collect();

    let mut ready: Vec<Issue> = all
        .iter()
        .filter(|i| i.is_open() && i.status == IssueStatus::Todo)
        .filter(|i| match (&filter.agent, &i.agent) {
            (Some(wanted), Some(assigned)) => same_agent(wanted, assigned),
            _ => true,
        })
        .filter(|i| !has_any_label(i, &config.exclude_labels))
        .filter(|i| !has_any_label(i, &filter.exclude_labels))
        .filter(|i| filter.include_labels.is_empty() || has_any_label(i, &filter.include_labels))
        .filter(|i| blockers_resolved(i, &by_number))
        .cloned()
        .collect();

    ready.sort_by_key(|i| {
        (
            i.priority,
            i.created_at.unwrap_or(DateTime::<Utc>::MAX_UTC),
            i.number,
        )
    });
    ready
}

/// Build the dependency graph of `number` from all board issues.
pub fn dependency_graph(number: u64, all: &[Issue]) -> Option<DependencyGraph> {
    let by_number: HashMap<u64, &Issue> = all.iter().map(|i| (i.number, i)).collect();
    let issue = *by_number.get(&number)?;

    let (found, missing): (Vec<u64>, Vec<u64>) = issue
        .blocked_by
        .iter()
        .partition(|b| by_number.contains_key(b));

    let refs = |pred: &dyn Fn(&Issue) -> bool| -> Vec<IssueRef> {
        let mut v: Vec<IssueRef> = all.iter().filter(|i| pred(i)).map(IssueRef::from).collect();
        v.sort_by_key(|r| r.number);
        v
    };

    Some(DependencyGraph {
        issue: IssueRef::from(issue),
        blocked_by: found.iter().map(|b| IssueRef::from(by_number[b])).collect(),
        missing_blockers: missing,
        blocks: refs(&|i| i.blocked_by.contains(&number)),
        children: refs(&|i| i.discovered_from == Some(number)),
        parent: issue
            .discovered_from
            .and_then(|p| by_number.get(&p))
            .map(|p| IssueRef::from(*p)),
        ready: blockers_resolved(issue, &by_number),
    })
}

/// Issue numbers present on the board.
pub fn issue_numbers(items: &[Value]) -> HashSet<u64> {
    items
        .iter()
        .filter_map(|i| i.get("content")?.get("number")?.as_u64())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::IssuePriority;
    use serde_json::json;

    fn config() -> BoardConfig {
        let mut c = BoardConfig {
            exclude_labels: vec!["wontfix".into()],
            ..Default::default()
        };
        c.priority_labels.insert("high".into(), vec!["bug".into()]);
        c
    }

    fn item(number: u64, status: &str, extra: &[(&str, &str)], labels: &[&str]) -> Value {
        let mut fv = vec![json!({ "name": status, "field": { "name": "Status" } })];
        for (field, value) in extra {
            fv.push(json!({ "text": value, "name": value, "field": { "name": field } }));
        }
        json!({
            "id": format!("ITEM_{number}"),
            "fieldValues": { "nodes": fv },
            "content": {
                "number": number,
                "title": format!("Issue {number}"),
                "body": "",
                "state": "OPEN",
                "createdAt": format!("2024-01-{:02}T00:00:00Z", number.min(28)),
                "labels": { "nodes": labels.iter().map(|l| json!({ "name": l })).collect::<Vec<_>>() }
            }
        })
    }

    fn issues(items: &[Value]) -> Vec<Issue> {
        issues_from_items(items, &config())
    }

    #[test]
    fn parses_project_fields() {
        let nodes = vec![
            json!({ "id": "F1", "name": "Status", "dataType": "SINGLE_SELECT",
                    "options": [{ "id": "O1", "name": "Todo" }, { "id": "O2", "name": "In Progress" }] }),
            json!({ "id": "F2", "name": "Blocked By", "dataType": "TEXT" }),
            json!({}),
        ];
        let fields = ProjectFields::from_nodes(&nodes);
        assert_eq!(fields.field_count(), 2);
        let status = fields.get("status").unwrap();
        assert_eq!(status.kind, FieldKind::SingleSelect);
        assert_eq!(status.option_id("in progress"), Some("O2"));
        assert_eq!(status.option_id("Done"), None);
        assert_eq!(fields.get("BLOCKED BY").unwrap().kind, FieldKind::Text);
    }

    #[test]
    fn parses_issue_from_item() {
        let it = item(
            5,
            "Todo",
            &[
                ("Agent", "Claude Code"),
                ("Blocked By", "#3, 4"),
                ("Estimated Size", "M"),
            ],
            &["bug"],
        );
        let issue = issue_from_item(&it, &it["content"], &config()).unwrap();
        assert_eq!(issue.number, 5);
        assert_eq!(issue.state, "open");
        assert_eq!(issue.status, IssueStatus::Todo);
        assert_eq!(issue.priority, IssuePriority::High); // from label fallback
        assert_eq!(issue.agent.as_deref(), Some("Claude Code"));
        assert_eq!(issue.blocked_by, vec![3, 4]);
        assert_eq!(issue.size, Some(crate::models::IssueSize::M));
        assert_eq!(issue.project_item_id.as_deref(), Some("ITEM_5"));
    }

    #[test]
    fn skips_draft_and_pr_items() {
        let items = vec![
            json!({ "id": "X", "content": null }),
            json!({ "id": "Y", "content": { "title": "draft" } }),
            json!({ "id": "Z", "content": { "number": 9 } }),
            item(1, "Todo", &[], &[]),
        ];
        let parsed = issues(&items);
        assert_eq!(parsed.len(), 1);
        assert_eq!(parsed[0].number, 1);
    }

    #[test]
    fn number_list_parsing() {
        assert_eq!(parse_number_list("12, #13 14,,x, 12"), vec![12, 13, 14]);
        assert!(parse_number_list("").is_empty());
        assert_eq!(format_number_list(&[1, 2]), "1, 2");
    }

    #[test]
    fn ready_selection_and_ordering() {
        let items = vec![
            item(1, "Todo", &[("Priority", "Low")], &[]),
            item(2, "Todo", &[("Priority", "Critical")], &[]),
            item(3, "In Progress", &[], &[]),
            item(4, "Todo", &[], &["wontfix"]),
            item(5, "Todo", &[("Agent", "Crush")], &[]),
            item(6, "Todo", &[("Agent", "Claude Code")], &[]),
            item(7, "Todo", &[], &["bug"]), // High via label
        ];
        let all = issues(&items);
        let filter = ReadyFilter {
            agent: Some("claude".into()),
            ..Default::default()
        };
        let ready: Vec<u64> = select_ready(&all, &filter, &config())
            .iter()
            .map(|i| i.number)
            .collect();
        assert_eq!(ready, vec![2, 7, 6, 1]);
    }

    #[test]
    fn ready_label_filters_case_insensitive() {
        let items = vec![
            item(1, "Todo", &[], &["Frontend"]),
            item(2, "Todo", &[], &["backend"]),
            item(3, "Todo", &[], &["frontend", "blocked-external"]),
        ];
        let filter = ReadyFilter {
            include_labels: vec!["frontend".into()],
            exclude_labels: vec!["Blocked-External".into()],
            ..Default::default()
        };
        let ready: Vec<u64> = select_ready(&issues(&items), &filter, &config())
            .iter()
            .map(|i| i.number)
            .collect();
        assert_eq!(ready, vec![1]);
    }

    #[test]
    fn resolved_blockers_do_not_block() {
        let mut closed = item(1, "Todo", &[], &[]);
        closed["content"]["state"] = json!("CLOSED");
        let items = vec![
            closed,
            item(2, "Done", &[], &[]),
            item(3, "Todo", &[], &[]),
            item(10, "Todo", &[("Blocked By", "1, 2")], &[]),
            item(11, "Todo", &[("Blocked By", "3")], &[]),
            item(12, "Todo", &[("Blocked By", "999")], &[]),
        ];
        let ready: Vec<u64> = select_ready(&issues(&items), &ReadyFilter::default(), &config())
            .iter()
            .map(|i| i.number)
            .collect();
        assert!(ready.contains(&10));
        assert!(!ready.contains(&11));
        assert!(!ready.contains(&12));
    }

    #[test]
    fn dependency_graph_relations() {
        let items = vec![
            item(1, "Todo", &[("Discovered From", "5")], &[]),
            item(2, "Done", &[], &[]),
            item(3, "Todo", &[("Blocked By", "1")], &[]),
            item(4, "Todo", &[("Discovered From", "1")], &[]),
            item(5, "Todo", &[], &[]),
        ];
        let mut all = issues(&items);
        all[0].blocked_by = vec![2, 77];
        let g = dependency_graph(1, &all).unwrap();
        assert_eq!(
            g.blocked_by.iter().map(|r| r.number).collect::<Vec<_>>(),
            vec![2]
        );
        assert_eq!(g.missing_blockers, vec![77]);
        assert_eq!(
            g.blocks.iter().map(|r| r.number).collect::<Vec<_>>(),
            vec![3]
        );
        assert_eq!(
            g.children.iter().map(|r| r.number).collect::<Vec<_>>(),
            vec![4]
        );
        assert_eq!(g.parent.as_ref().map(|p| p.number), Some(5));
        assert!(!g.ready);
        assert!(dependency_graph(42, &all).is_none());
    }

    #[test]
    fn collects_board_numbers() {
        let items = vec![item(1, "Todo", &[], &[]), json!({ "content": null })];
        assert_eq!(issue_numbers(&items), HashSet::from([1]));
    }
}
