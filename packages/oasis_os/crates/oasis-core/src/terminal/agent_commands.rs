//! Commands for the agent-terminal skin.
//!
//! These commands are registered in addition to the standard builtins when
//! the `agent-terminal` skin is active. They provide agent management,
//! MCP tool browsing, tamper monitoring, board interaction, CI triggering,
//! and system health display.

use crate::agent::health::SystemHealth;
use crate::agent::mcp::McpRegistry;
use crate::agent::status::AgentRegistry;
use crate::agent::tamper;
use crate::error::{OasisError, Result};
use crate::terminal::interpreter::{Command, CommandOutput, Environment};

// ---------------------------------------------------------------------------
// agent -- list/query AI agent status
// ---------------------------------------------------------------------------

pub struct AgentCmd;
impl Command for AgentCmd {
    fn name(&self) -> &str {
        "agent"
    }
    fn description(&self) -> &str {
        "List or query AI agent status"
    }
    fn usage(&self) -> &str {
        "agent [list|status <name>]"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let agents_path = "/etc/agents.toml";
        let registry = if env.vfs.exists(agents_path) {
            let data = env.vfs.read(agents_path)?;
            let toml_str = String::from_utf8_lossy(&data);
            AgentRegistry::from_toml(&toml_str)?
        } else {
            return Ok(CommandOutput::Text(
                "(no agents configured -- create /etc/agents.toml)".to_string(),
            ));
        };

        let subcmd = args.first().copied().unwrap_or("list");

        match subcmd {
            "list" => {
                if registry.is_empty() {
                    return Ok(CommandOutput::Text("(no agents defined)".to_string()));
                }
                let mut lines = Vec::new();
                lines.push("Configured Agents:".to_string());
                for a in registry.agents() {
                    lines.push(format!(
                        "  {} ({}) via {} -- {}",
                        a.name, a.kind, a.transport, a.availability
                    ));
                }
                Ok(CommandOutput::Text(lines.join("\n")))
            },
            "status" => {
                let name = args.get(1).copied().unwrap_or("");
                if name.is_empty() {
                    return Err(OasisError::Command(
                        "usage: agent status <name>".to_string(),
                    ));
                }
                match registry.find(name) {
                    Some(a) => Ok(CommandOutput::Text(format!(
                        "{} ({})\n  Transport: {}\n  Address:   {}\n  Status:    {}",
                        a.name, a.kind, a.transport, a.address, a.availability
                    ))),
                    None => Err(OasisError::Command(format!("unknown agent: {name}"))),
                }
            },
            _ => Err(OasisError::Command(format!(
                "unknown subcommand: {subcmd}\nusage: agent [list|status <name>]"
            ))),
        }
    }
}

// ---------------------------------------------------------------------------
// mcp -- browse and invoke MCP tools
// ---------------------------------------------------------------------------

pub struct McpCmd;
impl Command for McpCmd {
    fn name(&self) -> &str {
        "mcp"
    }
    fn description(&self) -> &str {
        "Browse and invoke MCP tools"
    }
    fn usage(&self) -> &str {
        "mcp [list|<server> <tool> [args...]]"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let mcp_path = "/etc/mcp.toml";
        let registry = if env.vfs.exists(mcp_path) {
            let data = env.vfs.read(mcp_path)?;
            let toml_str = String::from_utf8_lossy(&data);
            McpRegistry::from_toml(&toml_str)?
        } else {
            return Ok(CommandOutput::Text(
                "(no MCP servers configured -- create /etc/mcp.toml)".to_string(),
            ));
        };

        let subcmd = args.first().copied().unwrap_or("list");

        match subcmd {
            "list" => {
                if registry.server_count() == 0 {
                    return Ok(CommandOutput::Text("(no MCP servers defined)".to_string()));
                }
                let mut lines = Vec::new();
                lines.push(format!(
                    "MCP Servers: {} ({} tools)",
                    registry.server_count(),
                    registry.tool_count()
                ));
                for server in registry.servers() {
                    lines.push(format!(
                        "\n  {} ({} @ {})",
                        server.name, server.transport, server.address
                    ));
                    for tool in &server.tools {
                        lines.push(format!("    - {} : {}", tool.name, tool.description));
                    }
                }
                Ok(CommandOutput::Text(lines.join("\n")))
            },
            server_name => {
                let tool_name = args.get(1).copied().unwrap_or("");
                if tool_name.is_empty() {
                    // Show tools for this server.
                    match registry.find_server(server_name) {
                        Some(server) => {
                            let mut lines = Vec::new();
                            lines.push(format!(
                                "{} ({} @ {})",
                                server.name, server.transport, server.address
                            ));
                            if server.tools.is_empty() {
                                lines.push("  (no tools registered)".to_string());
                            } else {
                                for tool in &server.tools {
                                    lines.push(format!("  - {} : {}", tool.name, tool.description));
                                }
                            }
                            Ok(CommandOutput::Text(lines.join("\n")))
                        },
                        None => Err(OasisError::Command(format!(
                            "unknown MCP server: {server_name}"
                        ))),
                    }
                } else {
                    // Attempt to invoke a tool (display info -- actual invocation
                    // requires network, which the interpreter doesn't own).
                    match registry.find_tool(server_name, tool_name) {
                        Some(tool) => {
                            let tool_args = if args.len() > 2 {
                                args[2..].join(" ")
                            } else {
                                "(none)".to_string()
                            };
                            Ok(CommandOutput::Text(format!(
                                "MCP invoke: {server_name}.{}\n  Description: {}\n  Arguments: {tool_args}\n  (tool invocation requires network transport -- queued for execution)",
                                tool.name, tool.description
                            )))
                        },
                        None => Err(OasisError::Command(format!(
                            "unknown tool: {server_name}.{tool_name}"
                        ))),
                    }
                }
            },
        }
    }
}

// ---------------------------------------------------------------------------
// tamper -- display tamper system status
// ---------------------------------------------------------------------------

pub struct TamperCmd;
impl Command for TamperCmd {
    fn name(&self) -> &str {
        "tamper"
    }
    fn description(&self) -> &str {
        "Show tamper detection status"
    }
    fn usage(&self) -> &str {
        "tamper [status|arm|disarm]"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let subcmd = args.first().copied().unwrap_or("status");

        match subcmd {
            "status" => {
                let status = tamper::read_tamper_status(env.vfs);
                let mut lines = Vec::new();
                lines.push("Tamper System".to_string());
                lines.push(format!(
                    "  State: {} {}",
                    status.state,
                    status.state.indicator()
                ));
                if !status.raw.is_empty() {
                    lines.push(format!("  Raw:   {}", status.raw.trim()));
                }
                Ok(CommandOutput::Text(lines.join("\n")))
            },
            "arm" => {
                // Write arm request to gate FIFO.
                tamper::request_disarm(env.vfs, "ARM")?;
                Ok(CommandOutput::Text(
                    "Arm request sent to tamper-gate.".to_string(),
                ))
            },
            "disarm" => {
                // Disarm requires a challenge response; for now, send the command.
                tamper::request_disarm(env.vfs, "DISARM")?;
                Ok(CommandOutput::Text(
                    "Disarm request sent to tamper-gate.".to_string(),
                ))
            },
            _ => Err(OasisError::Command(format!(
                "unknown subcommand: {subcmd}\nusage: tamper [status|arm|disarm]"
            ))),
        }
    }
}

// ---------------------------------------------------------------------------
// board -- GitHub Projects board interaction
// ---------------------------------------------------------------------------

pub struct BoardCmd;
impl Command for BoardCmd {
    fn name(&self) -> &str {
        "board"
    }
    fn description(&self) -> &str {
        "Query GitHub Projects board"
    }
    fn usage(&self) -> &str {
        "board [query|claim <n>|release <n>]"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let subcmd = args.first().copied().unwrap_or("query");

        match subcmd {
            "query" => {
                // Read board cache from VFS if available.
                let board_path = "/var/board/ready.txt";
                if env.vfs.exists(board_path) {
                    let data = env.vfs.read(board_path)?;
                    let text = String::from_utf8_lossy(&data).into_owned();
                    if text.trim().is_empty() {
                        Ok(CommandOutput::Text(
                            "Board: no ready work items.".to_string(),
                        ))
                    } else {
                        Ok(CommandOutput::Text(format!("Ready Work:\n{text}")))
                    }
                } else {
                    Ok(CommandOutput::Text(
                        "(board data not available -- run board-manager sync)".to_string(),
                    ))
                }
            },
            "claim" => {
                let issue = args
                    .get(1)
                    .copied()
                    .unwrap_or("")
                    .parse::<u32>()
                    .map_err(|_| {
                        OasisError::Command("usage: board claim <issue_number>".to_string())
                    })?;
                // Write claim request to VFS.
                let claim_path = "/var/board/claim";
                env.vfs.write(claim_path, format!("{issue}").as_bytes())?;
                Ok(CommandOutput::Text(format!(
                    "Claim request written for issue #{issue}."
                )))
            },
            "release" => {
                let issue = args
                    .get(1)
                    .copied()
                    .unwrap_or("")
                    .parse::<u32>()
                    .map_err(|_| {
                        OasisError::Command("usage: board release <issue_number>".to_string())
                    })?;
                let release_path = "/var/board/release";
                env.vfs.write(release_path, format!("{issue}").as_bytes())?;
                Ok(CommandOutput::Text(format!(
                    "Release request written for issue #{issue}."
                )))
            },
            _ => Err(OasisError::Command(format!(
                "unknown subcommand: {subcmd}\nusage: board [query|claim <n>|release <n>]"
            ))),
        }
    }
}

// ---------------------------------------------------------------------------
// ci -- trigger CI stages
// ---------------------------------------------------------------------------

pub struct CiCmd;
impl Command for CiCmd {
    fn name(&self) -> &str {
        "ci"
    }
    fn description(&self) -> &str {
        "Trigger CI pipeline stages"
    }
    fn usage(&self) -> &str {
        "ci run <stage>"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        if args.first().copied() != Some("run") {
            return Err(OasisError::Command("usage: ci run <stage>".to_string()));
        }
        let stage = args.get(1).copied().unwrap_or("");
        if stage.is_empty() {
            return Err(OasisError::Command("usage: ci run <stage>".to_string()));
        }

        // Write CI request to VFS for the app layer to pick up.
        let ci_path = "/var/ci/request";
        env.vfs.write(ci_path, stage.as_bytes())?;
        Ok(CommandOutput::Text(format!(
            "CI stage '{stage}' queued for execution."
        )))
    }
}

// ---------------------------------------------------------------------------
// health -- system health metrics
// ---------------------------------------------------------------------------

pub struct HealthCmd;
impl Command for HealthCmd {
    fn name(&self) -> &str {
        "health"
    }
    fn description(&self) -> &str {
        "Show system health metrics"
    }
    fn usage(&self) -> &str {
        "health"
    }
    fn execute(&self, _args: &[&str], _env: &mut Environment<'_>) -> Result<CommandOutput> {
        let health = SystemHealth::collect();
        Ok(CommandOutput::Text(health.format()))
    }
}

/// Register all agent-terminal commands into a registry.
///
/// Call this in addition to `register_builtins()` when the agent-terminal
/// skin is active.
pub fn register_agent_commands(reg: &mut crate::terminal::CommandRegistry) {
    reg.register(Box::new(AgentCmd));
    reg.register(Box::new(McpCmd));
    reg.register(Box::new(TamperCmd));
    reg.register(Box::new(BoardCmd));
    reg.register(Box::new(CiCmd));
    reg.register(Box::new(HealthCmd));
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::terminal::interpreter::{CommandRegistry, Environment};
    use crate::vfs::{MemoryVfs, Vfs};

    fn setup_agent_env() -> (CommandRegistry, MemoryVfs) {
        let mut reg = CommandRegistry::new();
        crate::terminal::register_builtins(&mut reg);
        register_agent_commands(&mut reg);

        let mut vfs = MemoryVfs::new();
        // Set up agent config.
        vfs.mkdir("/etc").unwrap();
        vfs.write(
            "/etc/agents.toml",
            br#"
[[agent]]
name = "Claude Code"
kind = "claude"
transport = "cli"
address = "/usr/local/bin/claude"

[[agent]]
name = "Gemini CLI"
kind = "gemini"
transport = "mcp"
address = "localhost:8001"
"#,
        )
        .unwrap();

        // Set up MCP config.
        vfs.write(
            "/etc/mcp.toml",
            br#"
[[server]]
name = "code-quality"
transport = "stdio"
address = "/usr/local/bin/mcp-code-quality"
tools = [
    { name = "lint", description = "Run code linting" },
    { name = "run_tests", description = "Run pytest tests" },
]
"#,
        )
        .unwrap();

        (reg, vfs)
    }

    fn exec(reg: &CommandRegistry, vfs: &mut MemoryVfs, line: &str) -> Result<CommandOutput> {
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs,
            power: None,
            time: None,
            usb: None,
        };
        reg.execute(line, &mut env)
    }

    // --- agent command ---

    #[test]
    fn agent_list() {
        let (reg, mut vfs) = setup_agent_env();
        match exec(&reg, &mut vfs, "agent list").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("Claude Code"));
                assert!(s.contains("Gemini CLI"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn agent_list_default() {
        let (reg, mut vfs) = setup_agent_env();
        match exec(&reg, &mut vfs, "agent").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("Claude Code")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn agent_status_by_name() {
        let (reg, mut vfs) = setup_agent_env();
        match exec(&reg, &mut vfs, "agent status claude").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("Claude Code"));
                assert!(s.contains("CLI"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn agent_status_unknown() {
        let (reg, mut vfs) = setup_agent_env();
        assert!(exec(&reg, &mut vfs, "agent status nonexistent").is_err());
    }

    #[test]
    fn agent_no_config() {
        let mut reg = CommandRegistry::new();
        register_agent_commands(&mut reg);
        let mut vfs = MemoryVfs::new();
        match exec(&reg, &mut vfs, "agent").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no agents configured")),
            _ => panic!("expected text"),
        }
    }

    // --- mcp command ---

    #[test]
    fn mcp_list() {
        let (reg, mut vfs) = setup_agent_env();
        match exec(&reg, &mut vfs, "mcp list").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("code-quality"));
                assert!(s.contains("lint"));
                assert!(s.contains("run_tests"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn mcp_server_tools() {
        let (reg, mut vfs) = setup_agent_env();
        match exec(&reg, &mut vfs, "mcp code-quality").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("lint"));
                assert!(s.contains("run_tests"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn mcp_invoke_tool() {
        let (reg, mut vfs) = setup_agent_env();
        match exec(&reg, &mut vfs, "mcp code-quality lint /src").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("MCP invoke"));
                assert!(s.contains("code-quality.lint"));
                assert!(s.contains("/src"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn mcp_unknown_server() {
        let (reg, mut vfs) = setup_agent_env();
        assert!(exec(&reg, &mut vfs, "mcp nonexistent").is_err());
    }

    #[test]
    fn mcp_unknown_tool() {
        let (reg, mut vfs) = setup_agent_env();
        assert!(exec(&reg, &mut vfs, "mcp code-quality nonexistent").is_err());
    }

    #[test]
    fn mcp_no_config() {
        let mut reg = CommandRegistry::new();
        register_agent_commands(&mut reg);
        let mut vfs = MemoryVfs::new();
        match exec(&reg, &mut vfs, "mcp").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no MCP servers configured")),
            _ => panic!("expected text"),
        }
    }

    // --- tamper command ---

    #[test]
    fn tamper_status_no_file() {
        let (reg, mut vfs) = setup_agent_env();
        match exec(&reg, &mut vfs, "tamper status").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("UNKNOWN"));
                assert!(s.contains("[?]"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn tamper_status_armed() {
        let (reg, mut vfs) = setup_agent_env();
        vfs.mkdir("/sys").unwrap();
        vfs.mkdir("/sys/tamper").unwrap();
        vfs.write("/sys/tamper/state", b"armed").unwrap();
        match exec(&reg, &mut vfs, "tamper").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("ARMED"));
                assert!(s.contains("[ARMED]"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn tamper_arm() {
        let (reg, mut vfs) = setup_agent_env();
        vfs.mkdir("/sys").unwrap();
        vfs.mkdir("/sys/tamper").unwrap();
        match exec(&reg, &mut vfs, "tamper arm").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("Arm request")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn tamper_disarm() {
        let (reg, mut vfs) = setup_agent_env();
        vfs.mkdir("/sys").unwrap();
        vfs.mkdir("/sys/tamper").unwrap();
        match exec(&reg, &mut vfs, "tamper disarm").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("Disarm request")),
            _ => panic!("expected text"),
        }
    }

    // --- board command ---

    #[test]
    fn board_query_no_data() {
        let (reg, mut vfs) = setup_agent_env();
        match exec(&reg, &mut vfs, "board query").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("not available")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn board_query_with_data() {
        let (reg, mut vfs) = setup_agent_env();
        vfs.mkdir("/var").unwrap();
        vfs.mkdir("/var/board").unwrap();
        vfs.write(
            "/var/board/ready.txt",
            b"#142 [Todo] Fix auth edge case\n#147 [Todo] Add rate limiting",
        )
        .unwrap();
        match exec(&reg, &mut vfs, "board query").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("#142"));
                assert!(s.contains("#147"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn board_claim() {
        let (reg, mut vfs) = setup_agent_env();
        vfs.mkdir("/var").unwrap();
        vfs.mkdir("/var/board").unwrap();
        match exec(&reg, &mut vfs, "board claim 142").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("#142")),
            _ => panic!("expected text"),
        }
        // Verify claim file was written.
        assert_eq!(vfs.read("/var/board/claim").unwrap(), b"142");
    }

    #[test]
    fn board_claim_bad_number() {
        let (reg, mut vfs) = setup_agent_env();
        assert!(exec(&reg, &mut vfs, "board claim abc").is_err());
    }

    #[test]
    fn board_release() {
        let (reg, mut vfs) = setup_agent_env();
        vfs.mkdir("/var").unwrap();
        vfs.mkdir("/var/board").unwrap();
        match exec(&reg, &mut vfs, "board release 142").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("#142")),
            _ => panic!("expected text"),
        }
    }

    // --- ci command ---

    #[test]
    fn ci_run_stage() {
        let (reg, mut vfs) = setup_agent_env();
        vfs.mkdir("/var").unwrap();
        vfs.mkdir("/var/ci").unwrap();
        match exec(&reg, &mut vfs, "ci run full").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("full")),
            _ => panic!("expected text"),
        }
        assert_eq!(vfs.read("/var/ci/request").unwrap(), b"full");
    }

    #[test]
    fn ci_no_subcommand() {
        let (reg, mut vfs) = setup_agent_env();
        assert!(exec(&reg, &mut vfs, "ci").is_err());
    }

    #[test]
    fn ci_run_no_stage() {
        let (reg, mut vfs) = setup_agent_env();
        assert!(exec(&reg, &mut vfs, "ci run").is_err());
    }

    // --- health command ---

    #[test]
    fn health_shows_info() {
        let (reg, mut vfs) = setup_agent_env();
        match exec(&reg, &mut vfs, "health").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("System Health")),
            _ => panic!("expected text"),
        }
    }
}
