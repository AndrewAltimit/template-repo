//! Parsing and loading of the `security` section of `.agents.yaml`.

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::{TrustPolicy, normalize_login, source};

/// File name of the agent configuration.
pub const AGENTS_CONFIG_FILE: &str = ".agents.yaml";

/// The `security` trust lists, as written in the config file.
///
/// Both lists must be YAML sequences of strings; a scalar or a non-string
/// item is a parse error (a missing or `null` list is empty). Normalization (trim, lowercase, drop
/// blanks) happens in [`TrustPolicy`].
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct TrustConfig {
    #[serde(default)]
    pub agent_admins: Vec<String>,
    #[serde(default)]
    pub trusted_sources: Vec<String>,
}

/// What [`TrustConfig::load`] does when the config cannot be used.
///
/// The consumers intentionally differ; picking one is part of each call
/// site's security model.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Fallback {
    /// Fail closed: a missing, unreadable or invalid file is an error.
    /// Empty lists are accepted (nobody is elevated).
    Error,
    /// A missing file means empty lists (nobody is elevated); an unreadable
    /// or invalid file is an error.
    EmptyIfMissing,
    /// A missing, unreadable or invalid file, or one without any admin,
    /// yields [`TrustConfig::builtin_default`]. Problems other than a
    /// missing file are reported through the `warn` callback.
    BuiltinDefaults,
}

/// Errors from parsing or loading a [`TrustConfig`].
#[derive(Debug)]
pub enum TrustError {
    NotFound(PathBuf),
    Read {
        path: PathBuf,
        source: std::io::Error,
    },
    Parse {
        path: Option<PathBuf>,
        source: serde_yaml::Error,
    },
    NoAdmins {
        path: Option<PathBuf>,
    },
}

impl TrustError {
    fn at(self, p: &Path) -> Self {
        match self {
            TrustError::Parse { source, .. } => TrustError::Parse {
                path: Some(p.to_path_buf()),
                source,
            },
            TrustError::NoAdmins { .. } => TrustError::NoAdmins {
                path: Some(p.to_path_buf()),
            },
            other => other,
        }
    }
}

impl std::fmt::Display for TrustError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TrustError::NotFound(p) => {
                write!(f, "security config file not found: {}", p.display())
            },
            TrustError::Read { path, source } => {
                write!(f, "failed to read {}: {source}", path.display())
            },
            TrustError::Parse {
                path: Some(p),
                source,
            } => write!(f, "failed to parse {}: {source}", p.display()),
            TrustError::Parse { path: None, source } => write!(f, "invalid YAML ({source})"),
            TrustError::NoAdmins { path: Some(p) } => write!(
                f,
                "{}: security.agent_admins is empty or missing",
                p.display()
            ),
            TrustError::NoAdmins { path: None } => {
                f.write_str("security.agent_admins is empty or missing")
            },
        }
    }
}

impl std::error::Error for TrustError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            TrustError::Read { source, .. } => Some(source),
            TrustError::Parse { source, .. } => Some(source),
            _ => None,
        }
    }
}

/// Top-level `.agents.yaml` shape (only the part we need).
#[derive(Deserialize)]
struct AgentsYaml {
    #[serde(default)]
    security: TrustConfig,
}

impl TrustConfig {
    /// Parse the `security` section from `.agents.yaml` text. A document
    /// without a `security` key yields empty lists.
    pub fn from_yaml_str(content: &str) -> Result<Self, TrustError> {
        serde_yaml::from_str::<AgentsYaml>(content)
            .map(|doc| doc.security)
            .map_err(|source| TrustError::Parse { path: None, source })
    }

    /// Built-in lists used by [`Fallback::BuiltinDefaults`]: the repository
    /// maintainer as the only admin and GitHub Actions as a trusted source.
    pub fn builtin_default() -> Self {
        Self {
            agent_admins: vec!["AndrewAltimit".to_string()],
            trusted_sources: vec!["github-actions[bot]".to_string()],
        }
    }

    /// Reject a config whose admin list has no usable (non-blank) entry.
    pub fn require_admins(self) -> Result<Self, TrustError> {
        if self
            .agent_admins
            .iter()
            .any(|a| normalize_login(a).is_some())
        {
            Ok(self)
        } else {
            Err(TrustError::NoAdmins { path: None })
        }
    }

    /// Classifier for these lists.
    pub fn policy(&self) -> TrustPolicy {
        TrustPolicy::new(self)
    }

    /// Normalized admins followed by trusted sources, deduplicated, in
    /// file order.
    pub fn trusted_logins(&self) -> Vec<String> {
        let mut out: Vec<String> = Vec::new();
        for login in self
            .agent_admins
            .iter()
            .chain(&self.trusted_sources)
            .filter_map(|s| normalize_login(s))
        {
            if !out.contains(&login) {
                out.push(login);
            }
        }
        out
    }

    /// Load `path` with the given [`Fallback`] policy.
    ///
    /// The file is read through [`source::read_trusted_file`], so in a
    /// pull-request workflow a PR that modifies it gets the base-branch
    /// version. `warn` receives human-readable diagnostics.
    pub fn load(
        path: &Path,
        fallback: Fallback,
        warn: &mut dyn FnMut(&str),
    ) -> Result<Self, TrustError> {
        let content = match source::read_trusted_file(path, warn) {
            Ok(c) => Ok(c),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                return match fallback {
                    Fallback::Error => Err(TrustError::NotFound(path.to_path_buf())),
                    Fallback::EmptyIfMissing => Ok(Self::default()),
                    Fallback::BuiltinDefaults => Ok(Self::builtin_default()),
                };
            },
            Err(source) => Err(TrustError::Read {
                path: path.to_path_buf(),
                source,
            }),
        };
        let parsed = content
            .and_then(|c| Self::from_yaml_str(&c))
            .map_err(|e| e.at(path));
        match fallback {
            Fallback::BuiltinDefaults => {
                match parsed.and_then(|c| c.require_admins().map_err(|e| e.at(path))) {
                    Ok(c) => Ok(c),
                    Err(e) => {
                        warn(&format!("{e}; using built-in default trust lists"));
                        Ok(Self::builtin_default())
                    },
                }
            },
            Fallback::Error | Fallback::EmptyIfMissing => parsed,
        }
    }
}

/// Find [`AGENTS_CONFIG_FILE`] in `start` or any of its ancestors.
pub fn find_config_file(start: &Path) -> Option<PathBuf> {
    start
        .ancestors()
        .map(|dir| dir.join(AGENTS_CONFIG_FILE))
        .find(|p| p.is_file())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::TrustLevel;

    fn no_warn() -> impl FnMut(&str) {
        |m: &str| panic!("unexpected warning: {m}")
    }

    #[test]
    fn parses_security_section() {
        let yaml = "security:\n  agent_admins: [Alice]\n  trusted_sources: [bot]\n  \
                    enabled: true\nother: 1\n";
        let c = TrustConfig::from_yaml_str(yaml).unwrap();
        assert_eq!(c.agent_admins, vec!["Alice"]);
        assert_eq!(c.trusted_sources, vec!["bot"]);
        let p = c.policy();
        assert_eq!(p.level("ALICE"), TrustLevel::Admin);
        assert_eq!(p.level("Bot"), TrustLevel::Trusted);
    }

    #[test]
    fn missing_section_or_lists_are_empty() {
        assert_eq!(
            TrustConfig::from_yaml_str("other: 1\n").unwrap(),
            TrustConfig::default()
        );
        assert_eq!(
            TrustConfig::from_yaml_str("security: {}\n").unwrap(),
            TrustConfig::default()
        );
        // An explicit null list is empty (serde_yaml semantics).
        assert_eq!(
            TrustConfig::from_yaml_str("security:\n  agent_admins:\n").unwrap(),
            TrustConfig::default()
        );
    }

    #[test]
    fn malformed_lists_are_rejected() {
        for yaml in [
            // Scalar instead of a list (fail closed rather than guessing).
            "security:\n  agent_admins: solo\n",
            "security:\n  agent_admins: 5\n",
            // Non-string item: not silently dropped.
            "security:\n  agent_admins: [alice, [nested]]\n",
            "security:\n  trusted_sources: {a: b}\n",
            "security: [a]\n",
            ": : :\n  - [",
        ] {
            assert!(TrustConfig::from_yaml_str(yaml).is_err(), "{yaml:?}");
        }
    }

    #[test]
    fn require_admins_ignores_blank_entries() {
        assert!(TrustConfig::default().require_admins().is_err());
        let blank = TrustConfig {
            agent_admins: vec!["  ".into()],
            ..Default::default()
        };
        assert!(blank.require_admins().is_err());
        assert!(TrustConfig::builtin_default().require_admins().is_ok());
    }

    #[test]
    fn trusted_logins_are_normalized_and_deduplicated() {
        let c = TrustConfig {
            agent_admins: vec!["Admin".into(), " ".into()],
            trusted_sources: vec!["github-actions[bot]".into(), "ADMIN".into()],
        };
        assert_eq!(c.trusted_logins(), ["admin", "github-actions[bot]"]);
    }

    #[test]
    fn builtin_default_levels() {
        let p = TrustConfig::builtin_default().policy();
        assert_eq!(p.level("andrewaltimit"), TrustLevel::Admin);
        assert_eq!(p.level("github-actions[bot]"), TrustLevel::Trusted);
        assert_eq!(p.level("someone"), TrustLevel::Community);
    }

    #[test]
    fn load_missing_file_per_fallback() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(AGENTS_CONFIG_FILE);
        assert!(matches!(
            TrustConfig::load(&path, Fallback::Error, &mut no_warn()),
            Err(TrustError::NotFound(_))
        ));
        assert_eq!(
            TrustConfig::load(&path, Fallback::EmptyIfMissing, &mut no_warn()).unwrap(),
            TrustConfig::default()
        );
        assert_eq!(
            TrustConfig::load(&path, Fallback::BuiltinDefaults, &mut no_warn()).unwrap(),
            TrustConfig::builtin_default()
        );
    }

    #[test]
    fn load_invalid_file_per_fallback() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(AGENTS_CONFIG_FILE);
        std::fs::write(&path, "security:\n  agent_admins: 5\n").unwrap();
        let err = TrustConfig::load(&path, Fallback::Error, &mut no_warn()).unwrap_err();
        assert!(err.to_string().contains("failed to parse"), "{err}");
        assert!(TrustConfig::load(&path, Fallback::EmptyIfMissing, &mut no_warn()).is_err());

        let mut warnings = Vec::new();
        let c = TrustConfig::load(&path, Fallback::BuiltinDefaults, &mut |m: &str| {
            warnings.push(m.to_string())
        })
        .unwrap();
        assert_eq!(c, TrustConfig::builtin_default());
        assert_eq!(warnings.len(), 1);
        assert!(warnings[0].contains("built-in default"), "{warnings:?}");
    }

    #[test]
    fn load_without_admins_per_fallback() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(AGENTS_CONFIG_FILE);
        std::fs::write(&path, "security:\n  trusted_sources: [bot]\n").unwrap();
        // Fail-closed consumers accept empty admins: nobody is elevated.
        let c = TrustConfig::load(&path, Fallback::Error, &mut no_warn()).unwrap();
        assert!(c.agent_admins.is_empty());
        assert_eq!(c.policy().level("bot"), TrustLevel::Trusted);
        // BuiltinDefaults treats "no admin" as unusable.
        let mut warned = false;
        let c = TrustConfig::load(&path, Fallback::BuiltinDefaults, &mut |m: &str| {
            warned = m.contains("agent_admins");
        })
        .unwrap();
        assert!(warned);
        assert_eq!(c, TrustConfig::builtin_default());
    }

    #[test]
    fn load_valid_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(AGENTS_CONFIG_FILE);
        std::fs::write(&path, "security:\n  agent_admins: [Owner]\n").unwrap();
        for fb in [
            Fallback::Error,
            Fallback::EmptyIfMissing,
            Fallback::BuiltinDefaults,
        ] {
            let c = TrustConfig::load(&path, fb, &mut no_warn()).unwrap();
            assert_eq!(c.agent_admins, vec!["Owner"]);
        }
    }

    #[test]
    fn find_config_file_searches_ancestors() {
        let dir = tempfile::tempdir().unwrap();
        let nested = dir.path().join("a/b");
        std::fs::create_dir_all(&nested).unwrap();
        assert_eq!(find_config_file(&nested), None);
        std::fs::write(dir.path().join(AGENTS_CONFIG_FILE), "").unwrap();
        assert_eq!(
            find_config_file(&nested),
            Some(dir.path().join(AGENTS_CONFIG_FILE))
        );
    }
}
