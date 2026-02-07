use std::fmt;

use anyhow::{Result, bail};

/// Workspaces that have their own CI prefix
#[derive(Debug, Clone)]
pub enum Workspace {
    EconomicAgents,
    McpCore,
    Bioforge,
    TamperBriefcase,
    OasisOs,
}

impl Workspace {
    pub fn path(&self) -> &str {
        match self {
            Workspace::EconomicAgents => "packages/economic_agents",
            Workspace::McpCore => "tools/mcp/mcp_core_rust",
            Workspace::Bioforge => "packages/bioforge",
            Workspace::TamperBriefcase => "packages/tamper_briefcase",
            Workspace::OasisOs => "packages/oasis_os",
        }
    }
}

impl fmt::Display for Workspace {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Workspace::EconomicAgents => write!(f, "Economic Agents"),
            Workspace::McpCore => write!(f, "MCP Core Rust"),
            Workspace::Bioforge => write!(f, "BioForge"),
            Workspace::TamperBriefcase => write!(f, "Tamper Briefcase"),
            Workspace::OasisOs => write!(f, "OASIS_OS"),
        }
    }
}

/// Groups of crates that are iterated over
#[derive(Debug, Clone)]
pub enum IterGroup {
    Wrapper,
    McpServers,
    Tools,
}

impl IterGroup {
    /// Returns (base_dir, skip_list) for the group
    pub fn config(&self) -> (&str, Vec<&str>) {
        match self {
            IterGroup::Wrapper => (
                "tools/rust",
                vec![
                    "automation-cli",
                    "board-manager",
                    "code-parser",
                    "code-review-processor",
                    "github-agents-cli",
                    "markdown-link-checker",
                    "mcp-code-quality",
                    "pr-monitor",
                ],
            ),
            IterGroup::McpServers => ("tools/mcp", vec!["mcp_core_rust", "mcp_bioforge"]),
            IterGroup::Tools => (
                "tools/rust",
                vec!["wrapper-common", "git-guard", "gh-validator"],
            ),
        }
    }
}

impl fmt::Display for IterGroup {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            IterGroup::Wrapper => write!(f, "wrapper"),
            IterGroup::McpServers => write!(f, "MCP servers"),
            IterGroup::Tools => write!(f, "standalone tools"),
        }
    }
}

/// Every CI stage the system supports
#[derive(Debug, Clone)]
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

    // Rust injection_toolkit stages
    RustFmt,
    RustClippy,
    RustTest,
    RustBuild,
    RustDeny,
    RustFull,

    // Rust nightly stages
    RustLoom,
    RustMiri,
    RustCrossLinux,
    RustCrossWindows,
    RustAdvanced,

    // Generic workspace stages
    WorkspaceFmt(Workspace),
    WorkspaceClippy(Workspace),
    WorkspaceTest(Workspace),
    WorkspaceBuild(Workspace),
    WorkspaceDeny(Workspace),
    WorkspaceDoc(Workspace),
    WorkspaceCoverage(Workspace),
    WorkspaceFull(Workspace),

    // BioForge special (includes MCP server)
    BioFmt,
    BioClippy,
    BioBuild,
    BioFull,

    // Tamper Briefcase special (aarch64 exclusions)
    TamperClippy,
    TamperTest,
    TamperBuild,
    TamperFull,

    // OASIS_OS special (SDL2 not in CI container -- test/clippy/build only oasis-core)
    OasisClippy,
    OasisTest,
    OasisBuild,
    OasisFull,

    // Iterator group stages
    IterFmt(IterGroup),
    IterClippy(IterGroup),
    IterTest(IterGroup),
    IterFull(IterGroup),

    // Composite
    Full,
    RustAll,
}

impl Stage {
    pub fn parse(name: &str) -> Result<Self> {
        Ok(match name {
            // Python
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

            // Rust injection_toolkit
            "rust-fmt" => Stage::RustFmt,
            "rust-clippy" => Stage::RustClippy,
            "rust-test" => Stage::RustTest,
            "rust-build" => Stage::RustBuild,
            "rust-deny" => Stage::RustDeny,
            "rust-full" => Stage::RustFull,

            // Rust nightly
            "rust-loom" => Stage::RustLoom,
            "rust-miri" => Stage::RustMiri,
            "rust-cross-linux" => Stage::RustCrossLinux,
            "rust-cross-windows" => Stage::RustCrossWindows,
            "rust-advanced" => Stage::RustAdvanced,

            // Economic agents
            "econ-fmt" => Stage::WorkspaceFmt(Workspace::EconomicAgents),
            "econ-clippy" => Stage::WorkspaceClippy(Workspace::EconomicAgents),
            "econ-test" => Stage::WorkspaceTest(Workspace::EconomicAgents),
            "econ-build" => Stage::WorkspaceBuild(Workspace::EconomicAgents),
            "econ-deny" => Stage::WorkspaceDeny(Workspace::EconomicAgents),
            "econ-doc" => Stage::WorkspaceDoc(Workspace::EconomicAgents),
            "econ-coverage" => Stage::WorkspaceCoverage(Workspace::EconomicAgents),
            "econ-full" => Stage::WorkspaceFull(Workspace::EconomicAgents),

            // MCP core
            "mcp-fmt" => Stage::WorkspaceFmt(Workspace::McpCore),
            "mcp-clippy" => Stage::WorkspaceClippy(Workspace::McpCore),
            "mcp-test" => Stage::WorkspaceTest(Workspace::McpCore),
            "mcp-build" => Stage::WorkspaceBuild(Workspace::McpCore),
            "mcp-deny" => Stage::WorkspaceDeny(Workspace::McpCore),
            "mcp-doc" => Stage::WorkspaceDoc(Workspace::McpCore),
            "mcp-full" => Stage::WorkspaceFull(Workspace::McpCore),

            // BioForge
            "bio-fmt" => Stage::BioFmt,
            "bio-clippy" => Stage::BioClippy,
            "bio-test" => Stage::WorkspaceTest(Workspace::Bioforge),
            "bio-build" => Stage::BioBuild,
            "bio-deny" => Stage::WorkspaceDeny(Workspace::Bioforge),
            "bio-full" => Stage::BioFull,

            // Tamper Briefcase
            "tamper-fmt" => Stage::WorkspaceFmt(Workspace::TamperBriefcase),
            "tamper-clippy" => Stage::TamperClippy,
            "tamper-test" => Stage::TamperTest,
            "tamper-build" => Stage::TamperBuild,
            "tamper-deny" => Stage::WorkspaceDeny(Workspace::TamperBriefcase),
            "tamper-full" => Stage::TamperFull,

            // OASIS_OS (SDL2 crates excluded from CI -- no libsdl2-dev in container)
            "oasis-fmt" => Stage::WorkspaceFmt(Workspace::OasisOs),
            "oasis-clippy" => Stage::OasisClippy,
            "oasis-test" => Stage::OasisTest,
            "oasis-build" => Stage::OasisBuild,
            "oasis-deny" => Stage::WorkspaceDeny(Workspace::OasisOs),
            "oasis-full" => Stage::OasisFull,

            // Wrapper
            "wrapper-fmt" => Stage::IterFmt(IterGroup::Wrapper),
            "wrapper-clippy" => Stage::IterClippy(IterGroup::Wrapper),
            "wrapper-test" => Stage::IterTest(IterGroup::Wrapper),
            "wrapper-full" => Stage::IterFull(IterGroup::Wrapper),

            // MCP servers
            "mcp-servers-fmt" => Stage::IterFmt(IterGroup::McpServers),
            "mcp-servers-clippy" => Stage::IterClippy(IterGroup::McpServers),
            "mcp-servers-test" => Stage::IterTest(IterGroup::McpServers),
            "mcp-servers-full" => Stage::IterFull(IterGroup::McpServers),

            // Standalone tools
            "tools-fmt" => Stage::IterFmt(IterGroup::Tools),
            "tools-clippy" => Stage::IterClippy(IterGroup::Tools),
            "tools-test" => Stage::IterTest(IterGroup::Tools),
            "tools-full" => Stage::IterFull(IterGroup::Tools),

            // Composite
            "full" => Stage::Full,
            "rust-all" => Stage::RustAll,

            other => {
                bail!("unknown stage: {other}\nRun `automation-cli ci list` for available stages")
            },
        })
    }
}
