//! Claim comments: formatting, parsing and conflict resolution.
//!
//! Claims live as structured issue comments so they are auditable and need
//! no extra storage. The active claim is reconstructed by replaying the
//! comment history in chronological order ([`resolve_active_claim`]):
//!
//! - A claim is accepted only if no other unexpired claim is active at that
//!   moment. When two agents claim concurrently, the first comment wins and
//!   the later one is ignored, so both sides reach the same verdict.
//! - A renewal refreshes the active claim if it comes from the same agent.
//! - A release clears the active claim.
//!
//! Only comments by authorized authors (`security.agent_admins` and
//! `security.trusted_sources`) are replayed; see [`events_from_nodes`].

use chrono::{DateTime, Utc};
use serde_json::Value;
use std::collections::HashSet;
use tracing::debug;

use crate::approval::author_key;
use crate::models::{AgentClaim, ReleaseReason, same_agent};

/// Claim comment marker.
pub const CLAIM_PREFIX: &str = "**[Agent Claim]**";
/// Renewal comment marker.
pub const RENEWAL_PREFIX: &str = "**[Claim Renewal]**";
/// Release comment marker.
pub const RELEASE_PREFIX: &str = "**[Agent Release]**";

/// Build a claim comment body.
pub fn claim_comment(agent: &str, session_id: &str, now: DateTime<Utc>, timeout: i64) -> String {
    format!(
        "{}\n\nAgent: `{}`\nStarted: `{}`\nSession ID: `{}`\n\n\
         Claiming this issue for implementation. If this agent goes MIA, \
         this claim expires after {} hours.",
        CLAIM_PREFIX,
        agent,
        now.to_rfc3339(),
        session_id,
        timeout / 3600
    )
}

/// Build a renewal comment body.
pub fn renewal_comment(agent: &str, session_id: &str, now: DateTime<Utc>) -> String {
    format!(
        "{}\n\nAgent: `{}`\nRenewed: `{}`\nSession ID: `{}`\n\n\
         Claim renewed - still actively working on this issue.",
        RENEWAL_PREFIX,
        agent,
        now.to_rfc3339(),
        session_id
    )
}

/// Build a release comment body. `reason` is free text so the janitor can
/// record `stale_claim`, which is not a user-selectable [`ReleaseReason`].
pub fn release_comment(agent: &str, reason: &str, now: DateTime<Utc>, note: &str) -> String {
    format!(
        "{}\n\nAgent: `{}`\nReleased: `{}`\nReason: `{}`\n\n{}",
        RELEASE_PREFIX,
        agent,
        now.to_rfc3339(),
        reason,
        note
    )
}

/// Standard release comment for a [`ReleaseReason`].
pub fn release_comment_for(agent: &str, reason: ReleaseReason, now: DateTime<Utc>) -> String {
    release_comment(agent, reason.as_str(), now, "Work claim released.")
}

/// Kind of claim-related comment.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EventKind {
    Claim,
    Renewal,
    Release,
}

/// A parsed claim-related comment.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClaimEvent {
    pub kind: EventKind,
    pub agent: String,
    pub session_id: Option<String>,
    pub at: DateTime<Utc>,
}

/// Extract the backtick-quoted value from a `Key: \`value\`` line.
fn field<'a>(body: &'a str, key: &str) -> Option<&'a str> {
    body.lines()
        .find_map(|l| l.trim_start().strip_prefix(key))
        .map(|v| v.trim().trim_matches('`').trim())
        .filter(|v| !v.is_empty())
}

fn parse_time(s: &str) -> Option<DateTime<Utc>> {
    DateTime::parse_from_rfc3339(s)
        .ok()
        .map(|dt| dt.with_timezone(&Utc))
}

/// Parse one comment into a claim event.
///
/// `created_at` is the server-side comment timestamp; it is preferred over the
/// timestamp written in the body because it cannot be forged or skewed.
pub fn parse_event(body: &str, created_at: Option<DateTime<Utc>>) -> Option<ClaimEvent> {
    let (kind, time_key) = if body.contains(RELEASE_PREFIX) {
        (EventKind::Release, "Released:")
    } else if body.contains(RENEWAL_PREFIX) {
        (EventKind::Renewal, "Renewed:")
    } else if body.contains(CLAIM_PREFIX) {
        (EventKind::Claim, "Started:")
    } else {
        return None;
    };

    let agent = field(body, "Agent:")?.to_string();
    let session_id = field(body, "Session ID:").map(String::from);
    if kind != EventKind::Release && session_id.is_none() {
        return None;
    }
    let at = created_at.or_else(|| field(body, time_key).and_then(parse_time))?;

    Some(ClaimEvent {
        kind,
        agent,
        session_id,
        at,
    })
}

/// Parse GraphQL comment nodes (`{ body, createdAt, author }`) into events,
/// in the order given.
///
/// Only comments by `authorized` authors (normalized with
/// [`crate::approval::author_key`]) count. Anyone can post text that looks
/// like a claim, so claim, renewal and release comments from other authors
/// are logged at debug level and ignored.
pub fn events_from_nodes(nodes: &[Value], authorized: &HashSet<String>) -> Vec<ClaimEvent> {
    nodes
        .iter()
        .filter_map(|c| {
            let body = c.get("body").and_then(Value::as_str)?;
            let created = c
                .get("createdAt")
                .and_then(Value::as_str)
                .and_then(parse_time);
            let event = parse_event(body, created)?;
            match author_key(c) {
                Some(key) if authorized.contains(&key) => Some(event),
                author => {
                    debug!(
                        "Ignoring {:?} comment by unauthorized author {:?}",
                        event.kind, author
                    );
                    None
                },
            }
        })
        .collect()
}

/// Replay chronological events and return the active claim, if any.
///
/// Expiry is evaluated at each event's time to decide whether a new claim may
/// take over. The returned claim may itself be expired relative to "now";
/// callers decide what to do with stale claims.
pub fn resolve_active_claim(
    issue_number: u64,
    events: &[ClaimEvent],
    timeout_secs: i64,
) -> Option<AgentClaim> {
    let mut active: Option<AgentClaim> = None;

    for ev in events {
        match ev.kind {
            EventKind::Release => active = None,
            EventKind::Renewal => {
                if let Some(claim) = active.as_mut()
                    && same_agent(&claim.agent, &ev.agent)
                {
                    claim.renewed_at = Some(ev.at);
                }
            },
            EventKind::Claim => {
                let session = ev.session_id.clone().unwrap_or_default();
                match active.as_mut() {
                    // Same session re-posting its claim acts as a renewal.
                    Some(claim) if claim.session_id == session => claim.renewed_at = Some(ev.at),
                    // A different claimant loses while the current claim is live.
                    Some(claim) if !claim.is_expired_at(timeout_secs, ev.at) => {},
                    _ => {
                        active = Some(AgentClaim {
                            issue_number,
                            agent: ev.agent.clone(),
                            session_id: session,
                            timestamp: ev.at,
                            renewed_at: None,
                        });
                    },
                }
            },
        }
    }

    active
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t(s: &str) -> DateTime<Utc> {
        parse_time(s).unwrap()
    }

    fn ev(kind: EventKind, agent: &str, session: &str, at: &str) -> ClaimEvent {
        ClaimEvent {
            kind,
            agent: agent.into(),
            session_id: Some(session.into()),
            at: t(at),
        }
    }

    #[test]
    fn roundtrip_claim_comment() {
        let now = t("2024-01-15T10:00:00Z");
        let body = claim_comment("claude", "abc123", now, 86400);
        let e = parse_event(&body, None).unwrap();
        assert_eq!(e.kind, EventKind::Claim);
        assert_eq!(e.agent, "claude");
        assert_eq!(e.session_id.as_deref(), Some("abc123"));
        assert_eq!(e.at, now);
        assert!(body.contains("expires after 24 hours"));
    }

    #[test]
    fn parses_legacy_claim_format() {
        let body = "**[Agent Claim]**\n\nAgent: `Claude Code`\nStarted: `2024-01-15T10:00:00Z`\n\
                    Session ID: `abc123`\n\nClaiming this issue.";
        let e = parse_event(body, None).unwrap();
        assert_eq!(e.agent, "Claude Code");
        assert_eq!(e.session_id.as_deref(), Some("abc123"));
    }

    #[test]
    fn created_at_preferred_over_body_time() {
        let body = claim_comment("claude", "s", t("2000-01-01T00:00:00Z"), 3600);
        let server = t("2024-06-01T00:00:00Z");
        assert_eq!(parse_event(&body, Some(server)).unwrap().at, server);
    }

    #[test]
    fn release_and_renewal_parse() {
        let now = t("2024-01-15T10:00:00Z");
        let rel = release_comment_for("claude", ReleaseReason::Blocked, now);
        let e = parse_event(&rel, None).unwrap();
        assert_eq!(e.kind, EventKind::Release);
        assert!(rel.contains("Reason: `blocked`"));

        let ren = renewal_comment("claude", "s1", now);
        assert_eq!(parse_event(&ren, None).unwrap().kind, EventKind::Renewal);
    }

    #[test]
    fn unrelated_or_malformed_comments_ignored() {
        assert!(parse_event("LGTM", None).is_none());
        // Claim without a session ID is malformed.
        assert!(
            parse_event(
                "**[Agent Claim]**\nAgent: `x`\nStarted: `2024-01-01T00:00:00Z`",
                None
            )
            .is_none()
        );
        // No usable timestamp at all.
        assert!(parse_event("**[Agent Claim]**\nAgent: `x`\nSession ID: `s`", None).is_none());
    }

    #[test]
    fn first_claim_wins_race() {
        let events = vec![
            ev(EventKind::Claim, "claude", "s1", "2024-01-01T00:00:00Z"),
            ev(EventKind::Claim, "crush", "s2", "2024-01-01T00:00:01Z"),
        ];
        let claim = resolve_active_claim(7, &events, 3600).unwrap();
        assert_eq!(claim.session_id, "s1");
        assert_eq!(claim.agent, "claude");
        assert_eq!(claim.issue_number, 7);
    }

    #[test]
    fn expired_claim_can_be_taken_over() {
        let events = vec![
            ev(EventKind::Claim, "claude", "s1", "2024-01-01T00:00:00Z"),
            ev(EventKind::Claim, "crush", "s2", "2024-01-01T05:00:00Z"),
        ];
        let claim = resolve_active_claim(1, &events, 3600).unwrap();
        assert_eq!(claim.session_id, "s2");
    }

    #[test]
    fn renewal_extends_claim_and_blocks_takeover() {
        let events = vec![
            ev(EventKind::Claim, "claude", "s1", "2024-01-01T00:00:00Z"),
            ev(
                EventKind::Renewal,
                "Claude Code",
                "s1",
                "2024-01-01T00:50:00Z",
            ),
            ev(EventKind::Claim, "crush", "s2", "2024-01-01T01:30:00Z"),
        ];
        let claim = resolve_active_claim(1, &events, 3600).unwrap();
        assert_eq!(claim.session_id, "s1");
        assert_eq!(claim.renewed_at, Some(t("2024-01-01T00:50:00Z")));
    }

    #[test]
    fn renewal_by_other_agent_ignored() {
        let events = vec![
            ev(EventKind::Claim, "claude", "s1", "2024-01-01T00:00:00Z"),
            ev(EventKind::Renewal, "crush", "s2", "2024-01-01T00:30:00Z"),
        ];
        let claim = resolve_active_claim(1, &events, 3600).unwrap();
        assert_eq!(claim.renewed_at, None);
    }

    #[test]
    fn release_clears_claim() {
        let events = vec![
            ev(EventKind::Claim, "claude", "s1", "2024-01-01T00:00:00Z"),
            ev(EventKind::Release, "claude", "", "2024-01-01T00:10:00Z"),
        ];
        assert!(resolve_active_claim(1, &events, 3600).is_none());

        let reclaimed = vec![
            events[0].clone(),
            events[1].clone(),
            ev(EventKind::Claim, "crush", "s2", "2024-01-01T00:20:00Z"),
        ];
        assert_eq!(
            resolve_active_claim(1, &reclaimed, 3600).unwrap().agent,
            "crush"
        );
    }

    #[test]
    fn events_from_graphql_nodes() {
        let body = claim_comment("claude", "s1", t("2024-01-01T00:00:00Z"), 3600);
        let nodes = vec![
            serde_json::json!({ "body": "hello", "createdAt": "2024-01-01T00:00:00Z",
                                "author": { "login": "AndrewAltimit" } }),
            serde_json::json!({ "body": body, "createdAt": "2024-01-02T00:00:00Z",
                                "author": { "__typename": "User", "login": "AndrewAltimit" } }),
        ];
        let events = events_from_nodes(&nodes, &authorized());
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].at, t("2024-01-02T00:00:00Z"));
    }

    fn authorized() -> HashSet<String> {
        ["andrewaltimit", "github-actions[bot]"]
            .into_iter()
            .map(String::from)
            .collect()
    }

    fn node(body: String, at: &str, typename: &str, login: &str) -> Value {
        serde_json::json!({
            "body": body,
            "createdAt": at,
            "author": { "__typename": typename, "login": login }
        })
    }

    #[test]
    fn spoofed_claim_from_unauthorized_user_ignored() {
        let now = t("2024-01-01T00:00:00Z");
        let nodes = vec![
            // Attacker posts a claim first to squat on the issue.
            node(
                claim_comment("claude", "evil", now, 3600),
                "2024-01-01T00:00:00Z",
                "User",
                "mallory",
            ),
            // Legitimate claim posted with the admin token.
            node(
                claim_comment("claude", "s1", now, 3600),
                "2024-01-01T00:01:00Z",
                "User",
                "AndrewAltimit",
            ),
        ];
        let events = events_from_nodes(&nodes, &authorized());
        assert_eq!(events.len(), 1);
        let claim = resolve_active_claim(1, &events, 3600).unwrap();
        assert_eq!(claim.session_id, "s1");
    }

    #[test]
    fn spoofed_release_and_renewal_ignored() {
        let now = t("2024-01-01T00:00:00Z");
        let nodes = vec![
            node(
                claim_comment("claude", "s1", now, 3600),
                "2024-01-01T00:00:00Z",
                "User",
                "andrewaltimit",
            ),
            node(
                release_comment_for("claude", ReleaseReason::Completed, now),
                "2024-01-01T00:05:00Z",
                "User",
                "mallory",
            ),
            node(
                renewal_comment("claude", "s1", now),
                "2024-01-01T00:06:00Z",
                "User",
                "mallory",
            ),
        ];
        let events = events_from_nodes(&nodes, &authorized());
        let claim = resolve_active_claim(1, &events, 3600).unwrap();
        assert_eq!(claim.session_id, "s1");
        assert_eq!(claim.renewed_at, None);
    }

    #[test]
    fn bot_claims_authorized_via_bot_suffix() {
        let now = t("2024-01-01T00:00:00Z");
        let body = claim_comment("claude", "s1", now, 3600);
        // GraphQL reports the Actions bot as login `github-actions`, typename Bot.
        let bot = node(
            body.clone(),
            "2024-01-01T00:00:00Z",
            "Bot",
            "github-actions",
        );
        assert_eq!(events_from_nodes(&[bot], &authorized()).len(), 1);
        // A human account with the same login is not the bot.
        let human = node(
            body.clone(),
            "2024-01-01T00:00:00Z",
            "User",
            "github-actions",
        );
        assert!(events_from_nodes(&[human], &authorized()).is_empty());
        // Missing / deleted author is never authorized.
        let ghost = serde_json::json!({ "body": body, "createdAt": "2024-01-01T00:00:00Z",
                                        "author": null });
        assert!(events_from_nodes(&[ghost], &authorized()).is_empty());
    }

    #[test]
    fn author_matching_is_case_insensitive() {
        let now = t("2024-01-01T00:00:00Z");
        let n = node(
            claim_comment("claude", "s1", now, 3600),
            "2024-01-01T00:00:00Z",
            "User",
            "ANDREWALTIMIT",
        );
        assert_eq!(events_from_nodes(&[n], &authorized()).len(), 1);
    }
}
