//! Command trait, registry, and dispatch logic.

use std::collections::HashMap;

use crate::error::{OasisError, Result};
use crate::platform::{PowerService, TimeService, UsbService};
use crate::vfs::Vfs;

/// Output produced by a command.
#[derive(Debug, Clone)]
pub enum CommandOutput {
    /// Plain text lines.
    Text(String),
    /// Tabular data (header row + data rows).
    Table {
        headers: Vec<String>,
        rows: Vec<Vec<String>>,
    },
    /// Command produced no visible output.
    None,
    /// Signal to clear the terminal output buffer.
    Clear,
    /// Signal to the app to start/stop the remote terminal listener.
    ListenToggle {
        /// Port to listen on (0 = stop).
        port: u16,
    },
    /// Signal to the app to connect to a remote host.
    RemoteConnect {
        address: String,
        port: u16,
        psk: Option<String>,
    },
}

/// Shared mutable environment passed to every command.
pub struct Environment<'a> {
    /// Current working directory (VFS path).
    pub cwd: String,
    /// The virtual file system.
    pub vfs: &'a mut dyn Vfs,
    /// Power service for battery/CPU queries.
    pub power: Option<&'a dyn PowerService>,
    /// Time service for clock/uptime queries.
    pub time: Option<&'a dyn TimeService>,
    /// USB service for status queries.
    pub usb: Option<&'a dyn UsbService>,
}

/// A single executable command.
pub trait Command {
    /// The command name (what the user types).
    fn name(&self) -> &str;

    /// One-line description for `help`.
    fn description(&self) -> &str;

    /// Usage string (e.g. "ls [path]").
    fn usage(&self) -> &str;

    /// Execute the command with the given arguments and environment.
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput>;
}

/// Registry of available commands with dispatch.
pub struct CommandRegistry {
    commands: HashMap<String, Box<dyn Command>>,
}

impl CommandRegistry {
    pub fn new() -> Self {
        Self {
            commands: HashMap::new(),
        }
    }

    /// Register a command. Replaces any existing command with the same name.
    pub fn register(&mut self, cmd: Box<dyn Command>) {
        self.commands.insert(cmd.name().to_string(), cmd);
    }

    /// Parse and execute a command line.
    pub fn execute(&self, line: &str, env: &mut Environment<'_>) -> Result<CommandOutput> {
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.is_empty() {
            return Ok(CommandOutput::None);
        }
        let name = parts[0];
        let args = &parts[1..];

        match self.commands.get(name) {
            Some(cmd) => cmd.execute(args, env),
            None => Err(OasisError::Command(format!("unknown command: {name}"))),
        }
    }

    /// Return a sorted list of (name, description) pairs.
    pub fn list_commands(&self) -> Vec<(&str, &str)> {
        let mut cmds: Vec<(&str, &str)> = self
            .commands
            .values()
            .map(|c| (c.name(), c.description()))
            .collect();
        cmds.sort_by_key(|(name, _)| *name);
        cmds
    }
}

impl Default for CommandRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::vfs::MemoryVfs;

    struct EchoCmd;
    impl Command for EchoCmd {
        fn name(&self) -> &str {
            "echo"
        }
        fn description(&self) -> &str {
            "Print arguments"
        }
        fn usage(&self) -> &str {
            "echo [text...]"
        }
        fn execute(&self, args: &[&str], _env: &mut Environment<'_>) -> Result<CommandOutput> {
            Ok(CommandOutput::Text(args.join(" ")))
        }
    }

    #[test]
    fn register_and_execute() {
        let mut reg = CommandRegistry::new();
        reg.register(Box::new(EchoCmd));

        let mut vfs = MemoryVfs::new();
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        match reg.execute("echo hello world", &mut env).unwrap() {
            CommandOutput::Text(s) => assert_eq!(s, "hello world"),
            _ => panic!("expected text output"),
        }
    }

    #[test]
    fn unknown_command() {
        let reg = CommandRegistry::new();
        let mut vfs = MemoryVfs::new();
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        assert!(reg.execute("nonexistent", &mut env).is_err());
    }

    #[test]
    fn empty_input() {
        let reg = CommandRegistry::new();
        let mut vfs = MemoryVfs::new();
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        match reg.execute("", &mut env).unwrap() {
            CommandOutput::None => {},
            _ => panic!("expected None for empty input"),
        }
    }

    #[test]
    fn list_commands_sorted() {
        let mut reg = CommandRegistry::new();
        reg.register(Box::new(EchoCmd));
        let cmds = reg.list_commands();
        assert_eq!(cmds.len(), 1);
        assert_eq!(cmds[0].0, "echo");
    }
}
