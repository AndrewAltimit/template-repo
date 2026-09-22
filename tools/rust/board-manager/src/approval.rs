//! Approval trigger detection.
//!
//! An issue is approved only by an `[Approved][Agent]` trigger in the issue
//! body or a comment, written by an allowed approver (project owner,
//! repository owner, or `security.agent_admins` in `.agents.yaml`). Other
//! `[Action][Agent]` keywords (`[Review]`, `[Close]`, `[Summarize]`,
//! `[Debug]`, ...) are not approvals. When an agent is requested, the trigger
//! must name that agent (case-insensitive; `claude` also matches
//! `Claude Code`).
//!
//! Checks for many issues are batched into a single GraphQL query using
//! aliases, which avoids one round trip per issue.

use regex::Regex;
use serde_json::Value;
use std::collections::HashSet;
use std::fmt::Write as _;
use std::sync::LazyLock;

use crate::models::same_agent;

/// Matches `[Approved][Agent Name]`, capturing the agent name.
static APPROVAL_PATTERN: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"(?i)\[Approved\]\[([\w\s-]+)\]").expect("approval regex is valid")
});

/// Maximum issues per batched approval query.
pub const APPROVAL_BATCH_SIZE: usize = 20;

/// Normalized identity of a comment author for allow-list checks.
///
/// Logins are lowercased. GraphQL reports GitHub App authors (e.g.
/// `github-actions`) with `__typename: "Bot"` and without the `[bot]`
/// suffix, so the suffix is re-added for bots. This keeps a human account
/// named `github-actions` distinct from `github-actions[bot]` in config.
pub fn author_key(node: &Value) -> Option<String> {
    let author = node.get("author").filter(|a| !a.is_null())?;
    let login = author.get("login")?.as_str()?.trim().to_lowercase();
    if login.is_empty() {
        return None;
    }
    let is_bot = author.get("__typename").and_then(Value::as_str) == Some("Bot");
    Some(if is_bot && !login.ends_with("[bot]") {
        format!("{login}[bot]")
    } else {
        login
    })
}

/// Who may approve, and for which agent.
#[derive(Debug, Clone, Copy)]
pub struct ApprovalPolicy<'a> {
    /// Allowed approvers (lowercase logins).
    pub approvers: &'a HashSet<String>,
    /// When set, the trigger must name this agent.
    pub agent: Option<&'a str>,
}

impl ApprovalPolicy<'_> {
    /// Whether `text` contains an `[Approved][..]` trigger naming the
    /// required agent (any agent when none is required).
    pub fn text_approves(&self, text: &str) -> bool {
        APPROVAL_PATTERN.captures_iter(text).any(|c| {
            let named = c[1].trim();
            self.agent.is_none_or(|wanted| same_agent(named, wanted))
        })
    }

    /// Whether `text` written by `author_key` (see [`author_key`]) approves.
    pub fn approves(&self, text: &str, author_key: &str) -> bool {
        !author_key.is_empty() && self.approvers.contains(author_key) && self.text_approves(text)
    }

    /// Approver login if a GraphQL node (`body`, `author`) approves.
    fn node_approver(&self, node: &Value) -> Option<String> {
        let body = node.get("body").and_then(Value::as_str).unwrap_or("");
        let key = author_key(node)?;
        self.approves(body, &key).then(|| {
            node.get("author")
                .and_then(|a| a.get("login"))
                .and_then(Value::as_str)
                .unwrap_or(&key)
                .to_string()
        })
    }

    /// First approver among GraphQL comment nodes.
    pub fn find_approver(&self, nodes: &[Value]) -> Option<String> {
        nodes.iter().find_map(|n| self.node_approver(n))
    }
}

/// Approval state of one issue from a batched query.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BatchApproval {
    /// Approved by this user.
    Approved(String),
    /// Not approved within all comments.
    NotApproved,
    /// Not approved in the first page, but more comments exist after cursor.
    NeedsMore(String),
    /// Issue does not exist (or is inaccessible).
    Missing,
}

/// Build a batched approval query for up to [`APPROVAL_BATCH_SIZE`] issues.
/// Issue numbers are integers, so interpolation is injection-safe.
pub fn batch_query(numbers: &[u64]) -> String {
    let mut q = String::from("query BatchApproval($owner: String!, $repo: String!) {\n");
    q.push_str("  repository(owner: $owner, name: $repo) {\n");
    for (i, n) in numbers.iter().enumerate() {
        let _ = writeln!(q, "    i{i}: issue(number: {n}) {{ ...ApprovalFields }}");
    }
    q.push_str("  }\n}\n");
    q.push_str(
        "fragment ApprovalFields on Issue {\n  body\n  author { __typename login }\n  \
         comments(first: 100) {\n    pageInfo { hasNextPage endCursor }\n    \
         nodes { body author { __typename login } }\n  }\n}\n",
    );
    q
}

/// Interpret a batched approval response, in the same order as `numbers`.
pub fn parse_batch(
    data: &Value,
    numbers: &[u64],
    policy: &ApprovalPolicy<'_>,
) -> Vec<(u64, BatchApproval)> {
    let repo = data.get("repository");
    numbers
        .iter()
        .enumerate()
        .map(|(i, &n)| {
            let issue = repo
                .and_then(|r| r.get(format!("i{i}")))
                .filter(|v| !v.is_null());
            let Some(issue) = issue else {
                return (n, BatchApproval::Missing);
            };
            if let Some(approver) = policy.node_approver(issue) {
                return (n, BatchApproval::Approved(approver));
            }
            let comments = issue.get("comments");
            let nodes = comments
                .and_then(|c| c.get("nodes"))
                .and_then(Value::as_array)
                .map(Vec::as_slice)
                .unwrap_or_default();
            if let Some(approver) = policy.find_approver(nodes) {
                return (n, BatchApproval::Approved(approver));
            }
            match next_cursor(comments) {
                Some(cursor) => (n, BatchApproval::NeedsMore(cursor)),
                None => (n, BatchApproval::NotApproved),
            }
        })
        .collect()
}

/// `endCursor` if a connection has another page.
pub fn next_cursor(connection: Option<&Value>) -> Option<String> {
    let info = connection?.get("pageInfo")?;
    if !info
        .get("hasNextPage")
        .and_then(Value::as_bool)
        .unwrap_or(false)
    {
        return None;
    }
    info.get("endCursor")
        .and_then(Value::as_str)
        .map(String::from)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn allowed() -> HashSet<String> {
        ["andrewaltimit".to_string()].into_iter().collect()
    }

    fn policy<'a>(approvers: &'a HashSet<String>, agent: Option<&'a str>) -> ApprovalPolicy<'a> {
        ApprovalPolicy { approvers, agent }
    }

    #[test]
    fn trigger_requires_allowed_author_and_pattern() {
        let a = allowed();
        let p = policy(&a, None);
        assert!(p.approves("[Approved][Claude]", "andrewaltimit"));
        assert!(p.approves("looks good [approved][claude] go", "andrewaltimit"));
        assert!(!p.approves("[Approved][Claude]", "random"));
        assert!(!p.approves("approved claude", "andrewaltimit"));
        assert!(!p.approves("", "andrewaltimit"));
        assert!(!p.approves("[Approved][Claude]", ""));
    }

    #[test]
    fn only_approved_keyword_counts() {
        let a = allowed();
        let p = policy(&a, None);
        for text in [
            "[Review][Claude]",
            "[Close][Claude]",
            "[Summarize][Claude]",
            "[Debug][Claude]",
            "[CONTINUE]",
            "[Approve][Claude]",
            "[Approved]",
        ] {
            assert!(!p.approves(text, "andrewaltimit"), "{text}");
        }
    }

    #[test]
    fn requested_agent_must_be_named() {
        let a = allowed();
        let claude = policy(&a, Some("claude"));
        assert!(claude.approves("[Approved][Claude]", "andrewaltimit"));
        assert!(claude.approves("[approved][CLAUDE]", "andrewaltimit"));
        assert!(claude.approves("[Approved][Claude Code]", "andrewaltimit"));
        assert!(!claude.approves("[Approved][Crush]", "andrewaltimit"));
        assert!(!claude.approves("[Approved][Gemini]", "andrewaltimit"));
        // Any trigger in the text may name the agent.
        assert!(claude.approves(
            "[Approved][Crush] and also [Approved][Claude]",
            "andrewaltimit"
        ));
        let display = policy(&a, Some("Claude Code"));
        assert!(display.approves("[Approved][claude]", "andrewaltimit"));
    }

    #[test]
    fn bot_authors_get_bot_suffix() {
        let bot = json!({ "author": { "__typename": "Bot", "login": "github-actions" } });
        assert_eq!(author_key(&bot).as_deref(), Some("github-actions[bot]"));
        let user = json!({ "author": { "__typename": "User", "login": "AndrewAltimit" } });
        assert_eq!(author_key(&user).as_deref(), Some("andrewaltimit"));
        let plain = json!({ "author": { "login": "X" } });
        assert_eq!(author_key(&plain).as_deref(), Some("x"));
        assert_eq!(author_key(&json!({ "author": null })), None);
        assert_eq!(author_key(&json!({})), None);
    }

    #[test]
    fn batch_query_uses_aliases() {
        let q = batch_query(&[12, 34]);
        assert!(q.contains("i0: issue(number: 12)"));
        assert!(q.contains("i1: issue(number: 34)"));
        assert!(q.contains("fragment ApprovalFields on Issue"));
        assert!(q.contains("__typename"));
    }

    #[test]
    fn parse_batch_classifies_each_issue() {
        let data = json!({
            "repository": {
                "i0": {
                    "body": "[Approved][Claude]",
                    "author": { "login": "AndrewAltimit" },
                    "comments": { "pageInfo": { "hasNextPage": false }, "nodes": [] }
                },
                "i1": {
                    "body": "plain",
                    "author": { "login": "someone" },
                    "comments": {
                        "pageInfo": { "hasNextPage": false },
                        "nodes": [
                            { "body": "[Approved][Claude]", "author": { "login": "someone" } },
                            { "body": "[Close][Claude]", "author": { "login": "andrewaltimit" } },
                            { "body": "[Approved][Claude]", "author": { "login": "andrewaltimit" } }
                        ]
                    }
                },
                "i2": {
                    "body": "plain",
                    "author": null,
                    "comments": {
                        "pageInfo": { "hasNextPage": true, "endCursor": "CUR" },
                        "nodes": [{ "body": "hi", "author": null }]
                    }
                },
                "i3": {
                    "body": "[Review][Claude]",
                    "author": { "login": "AndrewAltimit" },
                    "comments": { "pageInfo": { "hasNextPage": false }, "nodes": [] }
                },
                "i4": null,
                "i5": {
                    "body": "[Approved][Crush]",
                    "author": { "login": "AndrewAltimit" },
                    "comments": { "pageInfo": { "hasNextPage": false }, "nodes": [] }
                }
            }
        });
        let a = allowed();
        let result = parse_batch(&data, &[1, 2, 3, 4, 5, 6], &policy(&a, Some("claude")));
        assert_eq!(
            result,
            vec![
                (1, BatchApproval::Approved("AndrewAltimit".into())),
                (2, BatchApproval::Approved("andrewaltimit".into())),
                (3, BatchApproval::NeedsMore("CUR".into())),
                (4, BatchApproval::NotApproved),
                (5, BatchApproval::Missing),
                (6, BatchApproval::NotApproved),
            ]
        );

        // Without a required agent, [Approved][Crush] counts.
        let any = parse_batch(&data, &[1, 2, 3, 4, 5, 6], &policy(&a, None));
        assert_eq!(any[5].1, BatchApproval::Approved("AndrewAltimit".into()));
    }
}
