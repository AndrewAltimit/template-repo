//! Scripting engine for command automation.
//!
//! Reads script files from the VFS and executes them line-by-line through
//! the command registry. Script format: one command per line, `#` comments,
//! blank lines skipped. Provides `run`, `cron`, and `startup` commands.

use crate::error::{OasisError, Result};
use crate::terminal::{Command, CommandOutput, CommandRegistry, Environment};

/// VFS paths for scripting configuration.
pub const STARTUP_SCRIPT_PATH: &str = "/etc/startup.sh";
pub const CRON_DIR: &str = "/etc/cron";

/// Parse a script file into executable lines.
///
/// Filters out comments (`#`), blank lines, and trims whitespace.
pub fn parse_script(source: &str) -> Vec<String> {
    source
        .lines()
        .map(|l| l.trim())
        .filter(|l| !l.is_empty() && !l.starts_with('#'))
        .map(|l| l.to_string())
        .collect()
}

/// Execute a script from VFS, returning collected output.
pub fn run_script(
    path: &str,
    registry: &CommandRegistry,
    env: &mut Environment<'_>,
) -> Result<Vec<String>> {
    let data = env.vfs.read(path)?;
    let source = String::from_utf8_lossy(&data);
    let lines = parse_script(&source);
    let mut output = Vec::new();

    for (i, line) in lines.iter().enumerate() {
        match registry.execute(line, env) {
            Ok(CommandOutput::Text(text)) => {
                for l in text.lines() {
                    output.push(l.to_string());
                }
            },
            Ok(CommandOutput::Table { headers, rows }) => {
                output.push(headers.join(" | "));
                for row in &rows {
                    output.push(row.join(" | "));
                }
            },
            Ok(CommandOutput::Clear) => output.push("(clear)".to_string()),
            Ok(CommandOutput::None) => {},
            Ok(CommandOutput::ListenToggle { .. } | CommandOutput::RemoteConnect { .. }) => {
                output.push("(network command skipped in script)".to_string());
            },
            Err(e) => {
                output.push(format!("error at line {}: {e}", i + 1));
            },
        }
    }

    Ok(output)
}

/// Execute the startup script if it exists.
pub fn run_startup(registry: &CommandRegistry, env: &mut Environment<'_>) -> Result<Vec<String>> {
    if !env.vfs.exists(STARTUP_SCRIPT_PATH) {
        return Ok(vec!["(no startup script configured)".to_string()]);
    }
    run_script(STARTUP_SCRIPT_PATH, registry, env)
}

// ---------------------------------------------------------------------------
// Terminal commands
// ---------------------------------------------------------------------------

/// `run <path>` -- execute a script file.
pub struct RunCmd;

impl Command for RunCmd {
    fn name(&self) -> &str {
        "run"
    }
    fn description(&self) -> &str {
        "Execute a script file"
    }
    fn usage(&self) -> &str {
        "run <path>"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let path = args
            .first()
            .copied()
            .ok_or_else(|| OasisError::Command("usage: run <path>".to_string()))?;

        // Resolve relative paths against cwd.
        let full_path = if path.starts_with('/') {
            path.to_string()
        } else if env.cwd == "/" {
            format!("/{path}")
        } else {
            format!("{}/{path}", env.cwd)
        };

        if !env.vfs.exists(&full_path) {
            return Err(OasisError::Command(format!(
                "script not found: {full_path}"
            )));
        }

        // We need a reference to the registry, but we're inside a Command.
        // The `run` command reads the script and returns it as text output.
        // The caller (main loop or script engine) can execute it.
        let data = env.vfs.read(&full_path)?;
        let source = String::from_utf8_lossy(&data);
        let lines = parse_script(&source);

        if lines.is_empty() {
            return Ok(CommandOutput::Text("(empty script)".to_string()));
        }

        // Return the parsed commands as a listing (actual execution happens
        // through run_script() at the app level).
        let mut output = format!("Script: {full_path} ({} commands)\n", lines.len());
        for line in &lines {
            output.push_str(&format!("  {line}\n"));
        }
        output.push_str("(use run_script() API for execution)");
        Ok(CommandOutput::Text(output))
    }
}

/// `cron` -- manage scheduled scripts.
pub struct CronCmd;

impl Command for CronCmd {
    fn name(&self) -> &str {
        "cron"
    }
    fn description(&self) -> &str {
        "Manage scheduled scripts"
    }
    fn usage(&self) -> &str {
        "cron [list|add <name> <path>|remove <name>]"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let subcmd = args.first().copied().unwrap_or("list");

        match subcmd {
            "list" => {
                if !env.vfs.exists(CRON_DIR) {
                    return Ok(CommandOutput::Text("(no cron jobs configured)".to_string()));
                }
                let entries = env.vfs.readdir(CRON_DIR)?;
                if entries.is_empty() {
                    return Ok(CommandOutput::Text("(no cron jobs configured)".to_string()));
                }
                let mut output = String::from("Scheduled scripts:\n");
                for entry in &entries {
                    let path = format!("{CRON_DIR}/{}", entry.name);
                    let data = env.vfs.read(&path).unwrap_or_default();
                    let target = String::from_utf8_lossy(&data);
                    output.push_str(&format!("  {} -> {}\n", entry.name, target.trim()));
                }
                Ok(CommandOutput::Text(output))
            },
            "add" => {
                let name = args
                    .get(1)
                    .copied()
                    .ok_or_else(|| OasisError::Command("usage: cron add <name> <path>".into()))?;
                let path = args
                    .get(2)
                    .copied()
                    .ok_or_else(|| OasisError::Command("usage: cron add <name> <path>".into()))?;

                if !env.vfs.exists(CRON_DIR) {
                    env.vfs.mkdir(CRON_DIR)?;
                }
                let entry_path = format!("{CRON_DIR}/{name}");
                env.vfs.write(&entry_path, path.as_bytes())?;
                Ok(CommandOutput::Text(format!(
                    "Cron job '{name}' added: {path}"
                )))
            },
            "remove" => {
                let name = args
                    .get(1)
                    .copied()
                    .ok_or_else(|| OasisError::Command("usage: cron remove <name>".into()))?;
                let entry_path = format!("{CRON_DIR}/{name}");
                if env.vfs.exists(&entry_path) {
                    env.vfs.remove(&entry_path)?;
                    Ok(CommandOutput::Text(format!("Cron job '{name}' removed")))
                } else {
                    Err(OasisError::Command(format!("cron job not found: {name}")))
                }
            },
            _ => Err(OasisError::Command(format!(
                "unknown subcommand: {subcmd}\nusage: {}",
                self.usage()
            ))),
        }
    }
}

/// `startup` -- configure the startup script.
pub struct StartupCmd;

impl Command for StartupCmd {
    fn name(&self) -> &str {
        "startup"
    }
    fn description(&self) -> &str {
        "Configure the startup script"
    }
    fn usage(&self) -> &str {
        "startup [show|set <path>|clear]"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let subcmd = args.first().copied().unwrap_or("show");

        match subcmd {
            "show" => {
                if env.vfs.exists(STARTUP_SCRIPT_PATH) {
                    let data = env.vfs.read(STARTUP_SCRIPT_PATH)?;
                    let text = String::from_utf8_lossy(&data).into_owned();
                    if text.trim().is_empty() {
                        Ok(CommandOutput::Text("(startup script is empty)".to_string()))
                    } else {
                        Ok(CommandOutput::Text(format!(
                            "Startup script ({STARTUP_SCRIPT_PATH}):\n{text}"
                        )))
                    }
                } else {
                    Ok(CommandOutput::Text(
                        "(no startup script configured)".to_string(),
                    ))
                }
            },
            "set" => {
                let path = args
                    .get(1)
                    .copied()
                    .ok_or_else(|| OasisError::Command("usage: startup set <path>".to_string()))?;
                // Copy the script to the startup path.
                if !env.vfs.exists(path) {
                    return Err(OasisError::Command(format!("file not found: {path}")));
                }
                let data = env.vfs.read(path)?;
                env.vfs.write(STARTUP_SCRIPT_PATH, &data)?;
                Ok(CommandOutput::Text(format!(
                    "Startup script set to: {path}"
                )))
            },
            "clear" => {
                if env.vfs.exists(STARTUP_SCRIPT_PATH) {
                    env.vfs.remove(STARTUP_SCRIPT_PATH)?;
                }
                Ok(CommandOutput::Text("Startup script cleared".to_string()))
            },
            _ => Err(OasisError::Command(format!(
                "unknown subcommand: {subcmd}\nusage: {}",
                self.usage()
            ))),
        }
    }
}

/// Register scripting commands.
pub fn register_script_commands(reg: &mut CommandRegistry) {
    reg.register(Box::new(RunCmd));
    reg.register(Box::new(CronCmd));
    reg.register(Box::new(StartupCmd));
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::terminal::CommandRegistry;
    use crate::vfs::{MemoryVfs, Vfs};

    fn setup() -> (CommandRegistry, MemoryVfs) {
        let mut reg = CommandRegistry::new();
        crate::terminal::register_builtins(&mut reg);
        register_script_commands(&mut reg);
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/etc").unwrap();
        vfs.mkdir("/tmp").unwrap();
        vfs.mkdir("/home").unwrap();
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
    fn parse_script_filters_comments_and_blanks() {
        let src = "# This is a comment\necho hello\n\n# Another comment\necho world\n";
        let lines = parse_script(src);
        assert_eq!(lines, vec!["echo hello", "echo world"]);
    }

    #[test]
    fn parse_script_trims() {
        let src = "  echo hello  \n  ls  \n";
        let lines = parse_script(src);
        assert_eq!(lines, vec!["echo hello", "ls"]);
    }

    #[test]
    fn parse_script_empty() {
        assert!(parse_script("").is_empty());
        assert!(parse_script("# only comments\n# here\n").is_empty());
    }

    #[test]
    fn run_script_executes_commands() {
        let (reg, mut vfs) = setup();
        vfs.write("/tmp/test.sh", b"# test script\necho hello\necho world")
            .unwrap();
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        let output = run_script("/tmp/test.sh", &reg, &mut env).unwrap();
        assert_eq!(output, vec!["hello", "world"]);
    }

    #[test]
    fn run_script_reports_errors() {
        let (reg, mut vfs) = setup();
        vfs.write("/tmp/bad.sh", b"nonexistent_command\necho ok")
            .unwrap();
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        let output = run_script("/tmp/bad.sh", &reg, &mut env).unwrap();
        assert!(output[0].contains("error at line 1"));
        assert_eq!(output[1], "ok");
    }

    #[test]
    fn run_cmd_missing_path() {
        let (reg, mut vfs) = setup();
        assert!(exec(&reg, &mut vfs, "run").is_err());
    }

    #[test]
    fn run_cmd_file_not_found() {
        let (reg, mut vfs) = setup();
        assert!(exec(&reg, &mut vfs, "run /tmp/nope.sh").is_err());
    }

    #[test]
    fn run_cmd_shows_listing() {
        let (reg, mut vfs) = setup();
        vfs.write("/tmp/demo.sh", b"echo hello\nls\n").unwrap();
        match exec(&reg, &mut vfs, "run /tmp/demo.sh").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("2 commands"));
                assert!(s.contains("echo hello"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn cron_list_empty() {
        let (reg, mut vfs) = setup();
        match exec(&reg, &mut vfs, "cron list").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no cron")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn cron_add_and_list() {
        let (reg, mut vfs) = setup();
        vfs.write("/tmp/job.sh", b"echo cron").unwrap();
        exec(&reg, &mut vfs, "cron add myjob /tmp/job.sh").unwrap();
        match exec(&reg, &mut vfs, "cron list").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("myjob"));
                assert!(s.contains("/tmp/job.sh"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn cron_remove() {
        let (reg, mut vfs) = setup();
        exec(&reg, &mut vfs, "cron add myjob /tmp/job.sh").unwrap();
        exec(&reg, &mut vfs, "cron remove myjob").unwrap();
        match exec(&reg, &mut vfs, "cron list").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no cron")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn cron_remove_nonexistent() {
        let (reg, mut vfs) = setup();
        assert!(exec(&reg, &mut vfs, "cron remove nope").is_err());
    }

    #[test]
    fn startup_show_empty() {
        let (reg, mut vfs) = setup();
        match exec(&reg, &mut vfs, "startup show").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no startup")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn startup_set_and_show() {
        let (reg, mut vfs) = setup();
        vfs.write("/tmp/init.sh", b"echo booting\nstatus").unwrap();
        exec(&reg, &mut vfs, "startup set /tmp/init.sh").unwrap();
        match exec(&reg, &mut vfs, "startup show").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("echo booting"));
                assert!(s.contains("status"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn startup_clear() {
        let (reg, mut vfs) = setup();
        vfs.write("/tmp/init.sh", b"echo boot").unwrap();
        exec(&reg, &mut vfs, "startup set /tmp/init.sh").unwrap();
        exec(&reg, &mut vfs, "startup clear").unwrap();
        match exec(&reg, &mut vfs, "startup show").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no startup")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn startup_set_missing_file() {
        let (reg, mut vfs) = setup();
        assert!(exec(&reg, &mut vfs, "startup set /tmp/nope.sh").is_err());
    }

    #[test]
    fn run_startup_no_script() {
        let (reg, mut vfs) = setup();
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        let output = run_startup(&reg, &mut env).unwrap();
        assert!(output[0].contains("no startup"));
    }

    #[test]
    fn run_startup_with_script() {
        let (reg, mut vfs) = setup();
        vfs.write(STARTUP_SCRIPT_PATH, b"echo booted").unwrap();
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        let output = run_startup(&reg, &mut env).unwrap();
        assert_eq!(output, vec!["booted"]);
    }
}
