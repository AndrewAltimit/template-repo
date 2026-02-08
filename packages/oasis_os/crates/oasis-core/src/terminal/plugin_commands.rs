//! Plugin management commands for the terminal.
//!
//! Provides `plugin list`, `plugin load`, and `plugin unload` commands.
//! These read the plugin manager state from a VFS-based status file
//! since the command interpreter does not have direct access to the
//! plugin manager (it lives in the app layer).

use crate::error::{OasisError, Result};
use crate::terminal::{Command, CommandOutput, Environment};

/// Path where the plugin manager writes its status for the terminal to read.
pub const PLUGIN_STATUS_PATH: &str = "/var/plugin/status";
/// Path where the terminal writes plugin load/unload requests.
pub const PLUGIN_REQUEST_PATH: &str = "/var/plugin/request";

pub struct PluginCmd;
impl Command for PluginCmd {
    fn name(&self) -> &str {
        "plugin"
    }
    fn description(&self) -> &str {
        "Manage plugins"
    }
    fn usage(&self) -> &str {
        "plugin [list|load <name>|unload <name>]"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let subcmd = args.first().copied().unwrap_or("list");

        match subcmd {
            "list" => {
                if env.vfs.exists(PLUGIN_STATUS_PATH) {
                    let data = env.vfs.read(PLUGIN_STATUS_PATH)?;
                    let text = String::from_utf8_lossy(&data).into_owned();
                    if text.trim().is_empty() {
                        Ok(CommandOutput::Text("(no plugins loaded)".to_string()))
                    } else {
                        Ok(CommandOutput::Text(format!("Loaded Plugins:\n{text}")))
                    }
                } else {
                    Ok(CommandOutput::Text(
                        "(plugin status not available)".to_string(),
                    ))
                }
            },
            "load" => {
                let name = args.get(1).copied().unwrap_or("");
                if name.is_empty() {
                    return Err(OasisError::Command("usage: plugin load <name>".to_string()));
                }
                let request = format!("load {name}");
                env.vfs.write(PLUGIN_REQUEST_PATH, request.as_bytes())?;
                Ok(CommandOutput::Text(format!(
                    "Plugin load request queued: {name}"
                )))
            },
            "unload" => {
                let name = args.get(1).copied().unwrap_or("");
                if name.is_empty() {
                    return Err(OasisError::Command(
                        "usage: plugin unload <name>".to_string(),
                    ));
                }
                let request = format!("unload {name}");
                env.vfs.write(PLUGIN_REQUEST_PATH, request.as_bytes())?;
                Ok(CommandOutput::Text(format!(
                    "Plugin unload request queued: {name}"
                )))
            },
            _ => Err(OasisError::Command(format!(
                "unknown subcommand: {subcmd}\nusage: plugin [list|load <name>|unload <name>]"
            ))),
        }
    }
}

/// Register plugin management commands into a registry.
pub fn register_plugin_commands(reg: &mut crate::terminal::CommandRegistry) {
    reg.register(Box::new(PluginCmd));
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::terminal::{CommandOutput, CommandRegistry, Environment};
    use crate::vfs::{MemoryVfs, Vfs};

    fn setup() -> (CommandRegistry, MemoryVfs) {
        let mut reg = CommandRegistry::new();
        register_plugin_commands(&mut reg);
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/var").unwrap();
        vfs.mkdir("/var/plugin").unwrap();
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

    #[test]
    fn plugin_list_no_status() {
        let mut reg = CommandRegistry::new();
        register_plugin_commands(&mut reg);
        let mut vfs = MemoryVfs::new();
        match exec(&reg, &mut vfs, "plugin list").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("not available")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn plugin_list_with_status() {
        let (reg, mut vfs) = setup();
        vfs.write(
            PLUGIN_STATUS_PATH,
            b"  hello (1.0.0) [active]\n  clock-widget (1.0.0) [active]",
        )
        .unwrap();
        match exec(&reg, &mut vfs, "plugin list").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("hello"));
                assert!(s.contains("clock-widget"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn plugin_list_empty() {
        let (reg, mut vfs) = setup();
        vfs.write(PLUGIN_STATUS_PATH, b"").unwrap();
        match exec(&reg, &mut vfs, "plugin list").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no plugins")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn plugin_list_default() {
        let (reg, mut vfs) = setup();
        vfs.write(PLUGIN_STATUS_PATH, b"test (1.0) [active]")
            .unwrap();
        match exec(&reg, &mut vfs, "plugin").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("test")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn plugin_load() {
        let (reg, mut vfs) = setup();
        match exec(&reg, &mut vfs, "plugin load hello").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("hello")),
            _ => panic!("expected text"),
        }
        let data = vfs.read(PLUGIN_REQUEST_PATH).unwrap();
        assert_eq!(data, b"load hello");
    }

    #[test]
    fn plugin_load_no_name() {
        let (reg, mut vfs) = setup();
        assert!(exec(&reg, &mut vfs, "plugin load").is_err());
    }

    #[test]
    fn plugin_unload() {
        let (reg, mut vfs) = setup();
        match exec(&reg, &mut vfs, "plugin unload hello").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("hello")),
            _ => panic!("expected text"),
        }
        let data = vfs.read(PLUGIN_REQUEST_PATH).unwrap();
        assert_eq!(data, b"unload hello");
    }

    #[test]
    fn plugin_unload_no_name() {
        let (reg, mut vfs) = setup();
        assert!(exec(&reg, &mut vfs, "plugin unload").is_err());
    }

    #[test]
    fn plugin_unknown_subcommand() {
        let (reg, mut vfs) = setup();
        assert!(exec(&reg, &mut vfs, "plugin badcmd").is_err());
    }
}
