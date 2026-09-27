//! Trust levels and login classification.

use std::collections::HashSet;

use serde::{Deserialize, Serialize};

use crate::TrustConfig;

/// Trust levels for comment authors, highest authority first.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum TrustLevel {
    /// `security.agent_admins`: may direct agent implementation.
    Admin,
    /// `security.trusted_sources`: vetted automation and reviewers.
    Trusted,
    /// Everyone else: consider but verify.
    Community,
}

impl TrustLevel {
    /// All levels, highest authority first.
    pub const ALL: [TrustLevel; 3] = [
        TrustLevel::Admin,
        TrustLevel::Trusted,
        TrustLevel::Community,
    ];

    /// Lowercase name (also the serde representation).
    pub fn as_str(self) -> &'static str {
        match self {
            TrustLevel::Admin => "admin",
            TrustLevel::Trusted => "trusted",
            TrustLevel::Community => "community",
        }
    }
}

impl std::fmt::Display for TrustLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.as_str())
    }
}

/// Normalize a configured login: trimmed and lowercased (GitHub logins are
/// case-insensitive). Blank entries yield `None` so they can never match an
/// empty or missing author.
pub fn normalize_login(login: &str) -> Option<String> {
    let trimmed = login.trim();
    (!trimmed.is_empty()).then(|| trimmed.to_lowercase())
}

/// Case-insensitive login classifier built from a [`TrustConfig`].
#[derive(Debug, Clone, Default)]
pub struct TrustPolicy {
    admins: HashSet<String>,
    /// Trusted sources that are not also admins.
    trusted: HashSet<String>,
}

impl TrustPolicy {
    pub fn new(config: &TrustConfig) -> Self {
        let admins: HashSet<String> = config
            .agent_admins
            .iter()
            .filter_map(|s| normalize_login(s))
            .collect();
        let trusted = config
            .trusted_sources
            .iter()
            .filter_map(|s| normalize_login(s))
            .filter(|s| !admins.contains(s))
            .collect();
        Self { admins, trusted }
    }

    /// Trust level of `login`. The login itself is matched exactly apart
    /// from case (it is not trimmed).
    pub fn level(&self, login: &str) -> TrustLevel {
        let lower = login.to_lowercase();
        if self.admins.contains(&lower) {
            TrustLevel::Admin
        } else if self.trusted.contains(&lower) {
            TrustLevel::Trusted
        } else {
            TrustLevel::Community
        }
    }

    pub fn is_admin(&self, login: &str) -> bool {
        self.level(login) == TrustLevel::Admin
    }

    /// Admin or trusted source.
    pub fn is_trusted_or_admin(&self, login: &str) -> bool {
        self.level(login) != TrustLevel::Community
    }

    /// Normalized admin logins.
    pub fn admins(&self) -> &HashSet<String> {
        &self.admins
    }

    /// Normalized trusted-source logins, excluding admins.
    pub fn trusted(&self) -> &HashSet<String> {
        &self.trusted
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn policy(admins: &[&str], trusted: &[&str]) -> TrustPolicy {
        TrustPolicy::new(&TrustConfig {
            agent_admins: admins.iter().map(|s| s.to_string()).collect(),
            trusted_sources: trusted.iter().map(|s| s.to_string()).collect(),
        })
    }

    #[test]
    fn levels_are_case_insensitive() {
        let p = policy(&["AdminUser"], &["BotUser"]);
        for name in ["AdminUser", "adminuser", "ADMINUSER"] {
            assert_eq!(p.level(name), TrustLevel::Admin);
        }
        for name in ["BotUser", "botuser", "BOTUSER"] {
            assert_eq!(p.level(name), TrustLevel::Trusted);
        }
        assert_eq!(p.level("stranger"), TrustLevel::Community);
    }

    #[test]
    fn admin_outranks_trusted_source() {
        let p = policy(&["admin_user"], &["bot_user", "Admin_User"]);
        assert_eq!(p.level("admin_user"), TrustLevel::Admin);
        assert!(p.trusted().contains("bot_user"));
        assert!(!p.trusted().contains("admin_user"));
        assert!(p.is_trusted_or_admin("admin_user"));
        assert!(p.is_trusted_or_admin("bot_user"));
        assert!(!p.is_trusted_or_admin("someone"));
        assert!(p.is_admin("ADMIN_USER"));
        assert!(!p.is_admin("bot_user"));
    }

    #[test]
    fn entries_are_trimmed_and_blank_entries_never_match() {
        let p = policy(&["", "  ", " Owner "], &[" Renovate[bot] ", ""]);
        assert_eq!(p.level("owner"), TrustLevel::Admin);
        assert_eq!(p.level("renovate[bot]"), TrustLevel::Trusted);
        assert_eq!(p.level(""), TrustLevel::Community);
        assert_eq!(p.level("  "), TrustLevel::Community);
        // The queried login is not trimmed.
        assert_eq!(p.level(" owner"), TrustLevel::Community);
        assert_eq!(p.admins().len(), 1);
    }

    #[test]
    fn empty_policy_elevates_nobody() {
        let p = TrustPolicy::default();
        assert_eq!(p.level("AndrewAltimit"), TrustLevel::Community);
    }

    #[test]
    fn level_names_and_serde() {
        assert_eq!(TrustLevel::Community.to_string(), "community");
        assert_eq!(
            serde_json::to_string(&TrustLevel::Admin).unwrap(),
            "\"admin\""
        );
        assert_eq!(
            TrustLevel::ALL.map(TrustLevel::as_str),
            ["admin", "trusted", "community"]
        );
    }
}
