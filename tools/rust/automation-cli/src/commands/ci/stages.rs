//! CI stage catalog: every stage name the CLI accepts, and what it maps to.

use std::fmt;

use anyhow::{Result, bail};

/// Rust workspaces that have their own CI stage prefix.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Workspace {
    EconomicAgents,
    McpCore,
    Bioforge,
    TamperBriefcase,
    SleeperAgents,
    McpSpriteSheet,
}

impl Workspace {
    pub const ALL: [Workspace; 6] = [
        Workspace::EconomicAgents,
        Workspace::McpCore,
        Workspace::Bioforge,
        Workspace::TamperBriefcase,
        Workspace::SleeperAgents,
        Workspace::McpSpriteSheet,
    ];

    /// Workspace directory relative to the project root.
    pub fn path(self) -> &'static str {
        match self {
            Workspace::EconomicAgents => "packages/economic_agents",
            Workspace::McpCore => "tools/mcp/mcp_core_rust",
            Workspace::Bioforge => "packages/bioforge",
            Workspace::TamperBriefcase => "packages/tamper_briefcase",
            Workspace::SleeperAgents => "packages/sleeper_agents",
            Workspace::McpSpriteSheet => "tools/mcp/mcp_sprite_sheet",
        }
    }
}

impl fmt::Display for Workspace {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Workspace::EconomicAgents => "Economic Agents",
            Workspace::McpCore => "MCP Core Rust",
            Workspace::Bioforge => "BioForge",
            Workspace::TamperBriefcase => "Tamper Briefcase",
            Workspace::SleeperAgents => "Sleeper Agents",
            Workspace::McpSpriteSheet => "MCP Sprite Sheet",
        })
    }
}

/// Crates in `tools/rust/` that make up the wrapper guard (git-guard, gh-validator).
pub const WRAPPER_CRATES: [&str; 3] = ["wrapper-common", "git-guard", "gh-validator"];

/// Groups of independent crates that are discovered and iterated over.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IterGroup {
    /// The wrapper-guard crates in `tools/rust/` ([`WRAPPER_CRATES`]).
    Wrapper,
    /// Every Rust crate in `tools/mcp/` except those with dedicated stages.
    McpServers,
    /// Every other crate in `tools/rust/` (standalone CLI tools).
    Tools,
}

impl IterGroup {
    pub const ALL: [IterGroup; 3] = [IterGroup::Wrapper, IterGroup::McpServers, IterGroup::Tools];

    /// Directory scanned for crates.
    pub fn base_dir(self) -> &'static str {
        match self {
            IterGroup::Wrapper | IterGroup::Tools => "tools/rust",
            IterGroup::McpServers => "tools/mcp",
        }
    }

    /// Whether a crate directory name found under [`Self::base_dir`] belongs
    /// to this group.
    pub fn includes(self, name: &str) -> bool {
        match self {
            IterGroup::Wrapper => WRAPPER_CRATES.contains(&name),
            IterGroup::Tools => !WRAPPER_CRATES.contains(&name),
            // mcp_core_rust and mcp_bioforge are covered by mcp-* / bio-* stages.
            IterGroup::McpServers => !["mcp_core_rust", "mcp_bioforge"].contains(&name),
        }
    }
}

impl fmt::Display for IterGroup {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            IterGroup::Wrapper => "wrapper",
            IterGroup::McpServers => "MCP servers",
            IterGroup::Tools => "standalone tools",
        })
    }
}

/// A cargo operation applied to a crate or workspace.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CargoOp {
    Fmt,
    Clippy,
    Test,
    Build,
}

impl CargoOp {
    /// The fmt -> clippy -> test sequence used by every `*-full` stage.
    pub const FULL: [CargoOp; 3] = [CargoOp::Fmt, CargoOp::Clippy, CargoOp::Test];

    /// Cargo arguments. `workspace` adds `--workspace` for multi-crate
    /// workspaces; `extra` is appended to `test` only.
    pub fn cargo_args<'a>(self, workspace: bool, extra: &[&'a str]) -> Vec<&'a str> {
        let ws: &[&str] = if workspace { &["--workspace"] } else { &[] };
        let mut args: Vec<&str> = match self {
            CargoOp::Fmt => return vec!["fmt", "--all", "--", "--check"],
            CargoOp::Clippy => {
                let mut a = vec!["clippy"];
                a.extend_from_slice(ws);
                a.extend_from_slice(&["--all-targets", "--", "-D", "warnings"]);
                return a;
            },
            CargoOp::Build => {
                let mut a = vec!["build"];
                a.extend_from_slice(ws);
                a.push("--all-targets");
                return a;
            },
            CargoOp::Test => vec!["test"],
        };
        args.extend_from_slice(ws);
        args.extend_from_slice(extra);
        args
    }

    /// Human-readable plural noun ("format checks", "clippy lints", ...).
    pub fn noun(self) -> &'static str {
        match self {
            CargoOp::Fmt => "format checks",
            CargoOp::Clippy => "clippy lints",
            CargoOp::Test => "tests",
            CargoOp::Build => "builds",
        }
    }

    /// Present-participle verb for per-crate sub-headers.
    pub fn verb(self) -> &'static str {
        match self {
            CargoOp::Fmt => "Checking format",
            CargoOp::Clippy => "Linting",
            CargoOp::Test => "Testing",
            CargoOp::Build => "Building",
        }
    }
}

/// Every CI stage the system supports
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Stage {
    // Python stages
    Format,
    LintBasic,
    LintFull,
    Ruff,
    RuffFix,
    Bandit,
    Security,
    Test,
    YamlLint,
    JsonLint,
    LintShell,
    Autoformat,
    TestGaea2,
    TestAll,
    TestCorporateProxy,

    // Generic workspace stages
    Workspace(Workspace, CargoOp),
    WorkspaceDeny(Workspace),
    WorkspaceDoc(Workspace),
    WorkspaceCoverage(Workspace),
    WorkspaceFull(Workspace),

    // BioForge special (includes the MCP BioForge server)
    Bio(CargoOp),
    BioFull,

    // Tamper Briefcase special (per-crate to skip aarch64-only crates)
    Tamper(CargoOp),
    TamperFull,

    // Iterator group stages
    Iter(IterGroup, CargoOp),
    IterFull(IterGroup),

    // Composite
    Full,
    RustAll,
}

/// A titled group of stage names, used for `ci list` and validation.
pub struct StageGroup {
    pub title: &'static str,
    pub names: &'static [&'static str],
}

/// The authoritative list of stage names, grouped for display.
/// `every_catalog_name_parses` guarantees each one is accepted by [`Stage::parse`].
pub const CATALOG: &[StageGroup] = &[
    StageGroup {
        title: "Python",
        names: &[
            "format",
            "lint-basic",
            "lint-full",
            "lint-shell",
            "ruff",
            "ruff-fix",
            "bandit",
            "security",
            "test",
            "test-gaea2",
            "test-all",
            "test-corporate-proxy",
            "yaml-lint",
            "json-lint",
            "autoformat",
            "full",
        ],
    },
    StageGroup {
        title: "Rust (economic_agents)",
        names: &[
            "econ-fmt",
            "econ-clippy",
            "econ-test",
            "econ-build",
            "econ-deny",
            "econ-doc",
            "econ-coverage",
            "econ-full",
        ],
    },
    StageGroup {
        title: "Rust (mcp_core_rust)",
        names: &[
            "mcp-fmt",
            "mcp-clippy",
            "mcp-test",
            "mcp-build",
            "mcp-deny",
            "mcp-doc",
            "mcp-full",
        ],
    },
    StageGroup {
        title: "Rust (bioforge + mcp_bioforge)",
        names: &[
            "bio-fmt",
            "bio-clippy",
            "bio-test",
            "bio-build",
            "bio-deny",
            "bio-full",
        ],
    },
    StageGroup {
        title: "Rust (sleeper_agents CLI)",
        names: &[
            "sleeper-fmt",
            "sleeper-clippy",
            "sleeper-test",
            "sleeper-build",
            "sleeper-deny",
            "sleeper-full",
        ],
    },
    StageGroup {
        title: "Rust (tamper_briefcase)",
        names: &[
            "tamper-fmt",
            "tamper-clippy",
            "tamper-test",
            "tamper-build",
            "tamper-deny",
            "tamper-full",
        ],
    },
    StageGroup {
        title: "Rust (mcp_sprite_sheet)",
        names: &[
            "sprite-fmt",
            "sprite-clippy",
            "sprite-test",
            "sprite-build",
            "sprite-full",
        ],
    },
    StageGroup {
        title: "Rust (wrapper guard: wrapper-common, git-guard, gh-validator)",
        names: &[
            "wrapper-fmt",
            "wrapper-clippy",
            "wrapper-test",
            "wrapper-full",
        ],
    },
    StageGroup {
        title: "Rust (every tools/mcp/* server without a dedicated stage)",
        names: &[
            "mcp-servers-fmt",
            "mcp-servers-clippy",
            "mcp-servers-test",
            "mcp-servers-full",
        ],
    },
    StageGroup {
        title: "Rust (every other tools/rust/* crate)",
        names: &["tools-fmt", "tools-clippy", "tools-test", "tools-full"],
    },
    StageGroup {
        title: "Composite",
        names: &["full", "rust-all", "rust-full"],
    },
];

/// Iterate over every distinct stage name in the catalog.
pub fn all_stage_names() -> impl Iterator<Item = &'static str> {
    let mut seen = std::collections::HashSet::new();
    CATALOG
        .iter()
        .flat_map(|g| g.names.iter().copied())
        .filter(move |n| seen.insert(*n))
}

/// Split `<prefix>-<op>` for the generic cargo ops.
fn split_op(name: &str) -> Option<(&str, &str)> {
    for suffix in [
        "fmt", "clippy", "test", "build", "deny", "doc", "coverage", "full",
    ] {
        if let Some(prefix) = name.strip_suffix(suffix).and_then(|p| p.strip_suffix('-')) {
            return Some((prefix, suffix));
        }
    }
    None
}

fn cargo_op(op: &str) -> Option<CargoOp> {
    Some(match op {
        "fmt" => CargoOp::Fmt,
        "clippy" => CargoOp::Clippy,
        "test" => CargoOp::Test,
        "build" => CargoOp::Build,
        _ => return None,
    })
}

impl Stage {
    pub fn parse(name: &str) -> Result<Self> {
        if let Some(stage) = Self::parse_python_or_composite(name) {
            return Ok(stage);
        }
        if let Some(stage) = split_op(name).and_then(|(p, op)| Self::parse_rust(p, op)) {
            return Ok(stage);
        }
        let hint = suggest(name)
            .map(|s| format!("\nDid you mean `{s}`?"))
            .unwrap_or_default();
        bail!("unknown stage: {name}{hint}\nRun `automation-cli ci list` for available stages")
    }

    fn parse_python_or_composite(name: &str) -> Option<Self> {
        Some(match name {
            "format" => Stage::Format,
            "lint-basic" => Stage::LintBasic,
            "lint-full" => Stage::LintFull,
            "ruff" => Stage::Ruff,
            "ruff-fix" => Stage::RuffFix,
            "bandit" => Stage::Bandit,
            "security" => Stage::Security,
            "test" => Stage::Test,
            "yaml-lint" => Stage::YamlLint,
            "json-lint" => Stage::JsonLint,
            "lint-shell" => Stage::LintShell,
            "autoformat" => Stage::Autoformat,
            "test-gaea2" => Stage::TestGaea2,
            "test-all" => Stage::TestAll,
            "test-corporate-proxy" => Stage::TestCorporateProxy,
            "full" => Stage::Full,
            // `rust-full` is the name used throughout the docs (AGENTS.md etc.).
            "rust-all" | "rust-full" => Stage::RustAll,
            _ => return None,
        })
    }

    fn parse_rust(prefix: &str, op: &str) -> Option<Self> {
        let ws = match prefix {
            "econ" => Some(Workspace::EconomicAgents),
            "mcp" => Some(Workspace::McpCore),
            "sleeper" => Some(Workspace::SleeperAgents),
            "sprite" => Some(Workspace::McpSpriteSheet),
            _ => None,
        };
        if let Some(ws) = ws {
            return Self::parse_workspace(ws, op);
        }
        match (prefix, op) {
            ("bio", "full") => Some(Stage::BioFull),
            ("bio", "deny") => Some(Stage::WorkspaceDeny(Workspace::Bioforge)),
            // fmt/clippy/test/build run on both the bioforge workspace and tools/mcp/mcp_bioforge.
            ("bio", op) => cargo_op(op).map(Stage::Bio),
            ("tamper", "full") => Some(Stage::TamperFull),
            ("tamper", "deny") => Some(Stage::WorkspaceDeny(Workspace::TamperBriefcase)),
            ("tamper", "fmt") => Some(Stage::Workspace(Workspace::TamperBriefcase, CargoOp::Fmt)),
            ("tamper", op) => cargo_op(op).map(Stage::Tamper),
            (group, op) => {
                let group = match group {
                    "wrapper" => IterGroup::Wrapper,
                    "mcp-servers" => IterGroup::McpServers,
                    "tools" => IterGroup::Tools,
                    _ => return None,
                };
                match op {
                    "full" => Some(Stage::IterFull(group)),
                    "fmt" | "clippy" | "test" => cargo_op(op).map(|o| Stage::Iter(group, o)),
                    _ => None,
                }
            },
        }
    }

    fn parse_workspace(ws: Workspace, op: &str) -> Option<Self> {
        // Only the stages that have historically existed are accepted, so that
        // e.g. `sprite-deny` fails loudly instead of running against a
        // workspace without a deny.toml.
        let allowed: &[&str] = match ws {
            Workspace::EconomicAgents => &[
                "fmt", "clippy", "test", "build", "deny", "doc", "coverage", "full",
            ],
            Workspace::McpCore => &["fmt", "clippy", "test", "build", "deny", "doc", "full"],
            Workspace::SleeperAgents => &["fmt", "clippy", "test", "build", "deny", "full"],
            Workspace::McpSpriteSheet => &["fmt", "clippy", "test", "build", "full"],
            Workspace::Bioforge | Workspace::TamperBriefcase => &[],
        };
        if !allowed.contains(&op) {
            return None;
        }
        Some(match op {
            "deny" => Stage::WorkspaceDeny(ws),
            "doc" => Stage::WorkspaceDoc(ws),
            "coverage" => Stage::WorkspaceCoverage(ws),
            "full" => Stage::WorkspaceFull(ws),
            other => Stage::Workspace(ws, cargo_op(other)?),
        })
    }
}

/// Closest catalog stage name within a small edit distance, for typo hints.
pub fn suggest(name: &str) -> Option<&'static str> {
    all_stage_names()
        .map(|candidate| (levenshtein(name, candidate), candidate))
        .filter(|(d, _)| *d <= 3)
        .min_by_key(|(d, _)| *d)
        .map(|(_, c)| c)
}

fn levenshtein(a: &str, b: &str) -> usize {
    let b: Vec<char> = b.chars().collect();
    let mut prev: Vec<usize> = (0..=b.len()).collect();
    for (i, ca) in a.chars().enumerate() {
        let mut cur = vec![i + 1; b.len() + 1];
        for (j, cb) in b.iter().enumerate() {
            let cost = usize::from(ca != *cb);
            cur[j + 1] = (prev[j] + cost).min(prev[j + 1] + 1).min(cur[j] + 1);
        }
        prev = cur;
    }
    prev[b.len()]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_catalog_name_parses() {
        for name in all_stage_names() {
            assert!(
                Stage::parse(name).is_ok(),
                "catalog stage `{name}` does not parse"
            );
        }
    }

    #[test]
    fn rust_full_is_alias_for_rust_all() {
        assert_eq!(Stage::parse("rust-full").unwrap(), Stage::RustAll);
        assert_eq!(Stage::parse("rust-all").unwrap(), Stage::RustAll);
    }

    #[test]
    fn representative_mappings() {
        assert_eq!(
            Stage::parse("econ-coverage").unwrap(),
            Stage::WorkspaceCoverage(Workspace::EconomicAgents)
        );
        assert_eq!(
            Stage::parse("bio-clippy").unwrap(),
            Stage::Bio(CargoOp::Clippy)
        );
        assert_eq!(Stage::parse("bio-test").unwrap(), Stage::Bio(CargoOp::Test));
        assert_eq!(
            Stage::parse("tamper-fmt").unwrap(),
            Stage::Workspace(Workspace::TamperBriefcase, CargoOp::Fmt)
        );
        assert_eq!(
            Stage::parse("tamper-test").unwrap(),
            Stage::Tamper(CargoOp::Test)
        );
        assert_eq!(
            Stage::parse("mcp-servers-fmt").unwrap(),
            Stage::Iter(IterGroup::McpServers, CargoOp::Fmt)
        );
        assert_eq!(
            Stage::parse("mcp-fmt").unwrap(),
            Stage::Workspace(Workspace::McpCore, CargoOp::Fmt)
        );
        assert_eq!(
            Stage::parse("tools-full").unwrap(),
            Stage::IterFull(IterGroup::Tools)
        );
    }

    #[test]
    fn rejects_unsupported_combinations() {
        for bad in [
            "sprite-deny",
            "sleeper-doc",
            "wrapper-build",
            "tools-deny",
            "bio-doc",
            "nope",
            "",
            "-fmt",
            "econ-",
        ] {
            assert!(Stage::parse(bad).is_err(), "`{bad}` should be rejected");
        }
    }

    #[test]
    fn unknown_stage_suggests_close_match() {
        let err = Stage::parse("lint-ful").unwrap_err().to_string();
        assert!(err.contains("Did you mean `lint-full`"), "{err}");
        assert_eq!(suggest("zzzzzzzzzzzz"), None);
    }

    #[test]
    fn catalog_names_are_unique_within_groups() {
        for g in CATALOG {
            let mut names: Vec<_> = g.names.to_vec();
            names.sort_unstable();
            names.dedup();
            assert_eq!(names.len(), g.names.len(), "duplicate in group {}", g.title);
        }
    }

    #[test]
    fn iter_groups_partition_tools_rust() {
        for name in ["git-guard", "gh-validator", "wrapper-common"] {
            assert!(IterGroup::Wrapper.includes(name));
            assert!(!IterGroup::Tools.includes(name));
        }
        for name in ["automation-cli", "pr-monitor", "some-future-crate"] {
            assert!(!IterGroup::Wrapper.includes(name));
            assert!(IterGroup::Tools.includes(name));
        }
        assert!(!IterGroup::McpServers.includes("mcp_core_rust"));
        assert!(!IterGroup::McpServers.includes("mcp_bioforge"));
        assert!(IterGroup::McpServers.includes("mcp_sprite_sheet"));
    }

    #[test]
    fn cargo_args_shapes() {
        assert_eq!(
            CargoOp::Fmt.cargo_args(true, &["x"]),
            ["fmt", "--all", "--", "--check"]
        );
        assert_eq!(
            CargoOp::Clippy.cargo_args(true, &[]),
            [
                "clippy",
                "--workspace",
                "--all-targets",
                "--",
                "-D",
                "warnings"
            ]
        );
        assert_eq!(
            CargoOp::Clippy.cargo_args(false, &[]),
            ["clippy", "--all-targets", "--", "-D", "warnings"]
        );
        assert_eq!(
            CargoOp::Test.cargo_args(true, &["--", "--nocapture"]),
            ["test", "--workspace", "--", "--nocapture"]
        );
        assert_eq!(
            CargoOp::Build.cargo_args(false, &["ignored"]),
            ["build", "--all-targets"]
        );
    }

    #[test]
    fn levenshtein_basics() {
        assert_eq!(levenshtein("", "abc"), 3);
        assert_eq!(levenshtein("kitten", "sitting"), 3);
        assert_eq!(levenshtein("same", "same"), 0);
    }
}
