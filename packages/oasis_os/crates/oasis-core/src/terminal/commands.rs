//! Built-in commands for the OASIS_OS terminal.

use crate::error::{OasisError, Result};
use crate::terminal::interpreter::{Command, CommandOutput, CommandRegistry, Environment};
use crate::vfs::EntryKind;

/// Register all built-in commands into a registry.
pub fn register_builtins(reg: &mut CommandRegistry) {
    reg.register(Box::new(HelpCmd));
    reg.register(Box::new(LsCmd));
    reg.register(Box::new(CdCmd));
    reg.register(Box::new(PwdCmd));
    reg.register(Box::new(CatCmd));
    reg.register(Box::new(MkdirCmd));
    reg.register(Box::new(RmCmd));
    reg.register(Box::new(EchoCmd));
    reg.register(Box::new(ClearCmd));
    reg.register(Box::new(StatusCmd));
    reg.register(Box::new(TouchCmd));
}

// ---------------------------------------------------------------------------
// help
// ---------------------------------------------------------------------------

struct HelpCmd;
impl Command for HelpCmd {
    fn name(&self) -> &str {
        "help"
    }
    fn description(&self) -> &str {
        "List available commands"
    }
    fn usage(&self) -> &str {
        "help"
    }
    fn execute(&self, _args: &[&str], _env: &mut Environment<'_>) -> Result<CommandOutput> {
        // We can't access the registry from here, so we return a static list.
        // The caller wraps this with the actual registry listing.
        // Instead, produce a marker that the registry intercepts.
        Ok(CommandOutput::Text(
            "Use 'help' at the terminal for a list of commands.".to_string(),
        ))
    }
}

// ---------------------------------------------------------------------------
// ls
// ---------------------------------------------------------------------------

struct LsCmd;
impl Command for LsCmd {
    fn name(&self) -> &str {
        "ls"
    }
    fn description(&self) -> &str {
        "List directory contents"
    }
    fn usage(&self) -> &str {
        "ls [path]"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let path = if args.is_empty() {
            env.cwd.clone()
        } else {
            resolve_path(&env.cwd, args[0])
        };
        let entries = env.vfs.readdir(&path)?;
        if entries.is_empty() {
            return Ok(CommandOutput::Text("(empty)".to_string()));
        }
        let mut lines = Vec::new();
        for e in &entries {
            let suffix = if e.kind == EntryKind::Directory {
                "/"
            } else {
                ""
            };
            lines.push(format!("{}{suffix}", e.name));
        }
        Ok(CommandOutput::Text(lines.join("\n")))
    }
}

// ---------------------------------------------------------------------------
// cd
// ---------------------------------------------------------------------------

struct CdCmd;
impl Command for CdCmd {
    fn name(&self) -> &str {
        "cd"
    }
    fn description(&self) -> &str {
        "Change working directory"
    }
    fn usage(&self) -> &str {
        "cd <path>"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let target = if args.is_empty() {
            "/".to_string()
        } else {
            resolve_path(&env.cwd, args[0])
        };
        // Verify it exists and is a directory.
        let meta = env.vfs.stat(&target)?;
        if meta.kind != EntryKind::Directory {
            return Err(OasisError::Command(format!("not a directory: {target}")));
        }
        env.cwd = target;
        Ok(CommandOutput::None)
    }
}

// ---------------------------------------------------------------------------
// pwd
// ---------------------------------------------------------------------------

struct PwdCmd;
impl Command for PwdCmd {
    fn name(&self) -> &str {
        "pwd"
    }
    fn description(&self) -> &str {
        "Print working directory"
    }
    fn usage(&self) -> &str {
        "pwd"
    }
    fn execute(&self, _args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        Ok(CommandOutput::Text(env.cwd.clone()))
    }
}

// ---------------------------------------------------------------------------
// cat
// ---------------------------------------------------------------------------

struct CatCmd;
impl Command for CatCmd {
    fn name(&self) -> &str {
        "cat"
    }
    fn description(&self) -> &str {
        "Display file contents"
    }
    fn usage(&self) -> &str {
        "cat <file>"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        if args.is_empty() {
            return Err(OasisError::Command("usage: cat <file>".to_string()));
        }
        let path = resolve_path(&env.cwd, args[0]);
        let data = env.vfs.read(&path)?;
        let text = String::from_utf8_lossy(&data).into_owned();
        Ok(CommandOutput::Text(text))
    }
}

// ---------------------------------------------------------------------------
// mkdir
// ---------------------------------------------------------------------------

struct MkdirCmd;
impl Command for MkdirCmd {
    fn name(&self) -> &str {
        "mkdir"
    }
    fn description(&self) -> &str {
        "Create a directory"
    }
    fn usage(&self) -> &str {
        "mkdir <path>"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        if args.is_empty() {
            return Err(OasisError::Command("usage: mkdir <path>".to_string()));
        }
        let path = resolve_path(&env.cwd, args[0]);
        env.vfs.mkdir(&path)?;
        Ok(CommandOutput::None)
    }
}

// ---------------------------------------------------------------------------
// rm
// ---------------------------------------------------------------------------

struct RmCmd;
impl Command for RmCmd {
    fn name(&self) -> &str {
        "rm"
    }
    fn description(&self) -> &str {
        "Remove a file or empty directory"
    }
    fn usage(&self) -> &str {
        "rm <path>"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        if args.is_empty() {
            return Err(OasisError::Command("usage: rm <path>".to_string()));
        }
        let path = resolve_path(&env.cwd, args[0]);
        env.vfs.remove(&path)?;
        Ok(CommandOutput::None)
    }
}

// ---------------------------------------------------------------------------
// echo
// ---------------------------------------------------------------------------

struct EchoCmd;
impl Command for EchoCmd {
    fn name(&self) -> &str {
        "echo"
    }
    fn description(&self) -> &str {
        "Print text"
    }
    fn usage(&self) -> &str {
        "echo [text...]"
    }
    fn execute(&self, args: &[&str], _env: &mut Environment<'_>) -> Result<CommandOutput> {
        Ok(CommandOutput::Text(args.join(" ")))
    }
}

// ---------------------------------------------------------------------------
// clear
// ---------------------------------------------------------------------------

struct ClearCmd;
impl Command for ClearCmd {
    fn name(&self) -> &str {
        "clear"
    }
    fn description(&self) -> &str {
        "Clear terminal output"
    }
    fn usage(&self) -> &str {
        "clear"
    }
    fn execute(&self, _args: &[&str], _env: &mut Environment<'_>) -> Result<CommandOutput> {
        Ok(CommandOutput::Clear)
    }
}

// ---------------------------------------------------------------------------
// status
// ---------------------------------------------------------------------------

struct StatusCmd;
impl Command for StatusCmd {
    fn name(&self) -> &str {
        "status"
    }
    fn description(&self) -> &str {
        "Show system status"
    }
    fn usage(&self) -> &str {
        "status"
    }
    fn execute(&self, _args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let mut lines = Vec::new();
        lines.push("OASIS_OS v0.1.0".to_string());
        lines.push(format!("cwd: {}", env.cwd));
        // Count files in VFS root.
        match env.vfs.readdir("/") {
            Ok(entries) => lines.push(format!("root entries: {}", entries.len())),
            Err(_) => lines.push("root entries: (error reading)".to_string()),
        }
        Ok(CommandOutput::Text(lines.join("\n")))
    }
}

// ---------------------------------------------------------------------------
// touch
// ---------------------------------------------------------------------------

struct TouchCmd;
impl Command for TouchCmd {
    fn name(&self) -> &str {
        "touch"
    }
    fn description(&self) -> &str {
        "Create an empty file"
    }
    fn usage(&self) -> &str {
        "touch <file>"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        if args.is_empty() {
            return Err(OasisError::Command("usage: touch <file>".to_string()));
        }
        let path = resolve_path(&env.cwd, args[0]);
        if !env.vfs.exists(&path) {
            env.vfs.write(&path, &[])?;
        }
        Ok(CommandOutput::None)
    }
}

// ---------------------------------------------------------------------------
// Path resolution helper
// ---------------------------------------------------------------------------

/// Resolve a possibly-relative path against the current working directory.
/// Absolute paths (starting with `/`) are returned as-is. Relative paths are
/// joined to `cwd`. `..` and `.` components are resolved.
fn resolve_path(cwd: &str, input: &str) -> String {
    let raw = if input.starts_with('/') {
        input.to_string()
    } else if cwd == "/" {
        format!("/{input}")
    } else {
        format!("{cwd}/{input}")
    };

    // Resolve `.` and `..` components.
    let mut parts: Vec<&str> = Vec::new();
    for component in raw.split('/') {
        match component {
            "" | "." => {},
            ".." => {
                parts.pop();
            },
            other => parts.push(other),
        }
    }

    if parts.is_empty() {
        "/".to_string()
    } else {
        format!("/{}", parts.join("/"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::vfs::{MemoryVfs, Vfs};

    fn setup() -> (CommandRegistry, MemoryVfs) {
        let mut reg = CommandRegistry::new();
        register_builtins(&mut reg);
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/home").unwrap();
        vfs.mkdir("/home/user").unwrap();
        vfs.write("/home/user/readme.txt", b"Hello OASIS").unwrap();
        (reg, vfs)
    }

    fn exec(
        reg: &CommandRegistry,
        vfs: &mut MemoryVfs,
        cwd: &mut String,
        line: &str,
    ) -> Result<CommandOutput> {
        let mut env = Environment {
            cwd: cwd.clone(),
            vfs,
        };
        let result = reg.execute(line, &mut env);
        *cwd = env.cwd;
        result
    }

    #[test]
    fn pwd_shows_cwd() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/home".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "pwd").unwrap() {
            CommandOutput::Text(s) => assert_eq!(s, "/home"),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn ls_root() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "ls").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("home")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn ls_with_path() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "ls /home/user").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("readme.txt")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn cd_and_pwd() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        exec(&reg, &mut vfs, &mut cwd, "cd /home/user").unwrap();
        assert_eq!(cwd, "/home/user");
    }

    #[test]
    fn cd_relative() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/home".to_string();
        exec(&reg, &mut vfs, &mut cwd, "cd user").unwrap();
        assert_eq!(cwd, "/home/user");
    }

    #[test]
    fn cd_dotdot() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/home/user".to_string();
        exec(&reg, &mut vfs, &mut cwd, "cd ..").unwrap();
        assert_eq!(cwd, "/home");
    }

    #[test]
    fn cat_file() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "cat /home/user/readme.txt").unwrap() {
            CommandOutput::Text(s) => assert_eq!(s, "Hello OASIS"),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn cat_no_args() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        assert!(exec(&reg, &mut vfs, &mut cwd, "cat").is_err());
    }

    #[test]
    fn mkdir_creates_dir() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        exec(&reg, &mut vfs, &mut cwd, "mkdir /tmp").unwrap();
        assert!(vfs.exists("/tmp"));
    }

    #[test]
    fn rm_removes_file() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        exec(&reg, &mut vfs, &mut cwd, "rm /home/user/readme.txt").unwrap();
        assert!(!vfs.exists("/home/user/readme.txt"));
    }

    #[test]
    fn echo_output() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "echo hello world").unwrap() {
            CommandOutput::Text(s) => assert_eq!(s, "hello world"),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn clear_returns_clear() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "clear").unwrap() {
            CommandOutput::Clear => {},
            _ => panic!("expected Clear"),
        }
    }

    #[test]
    fn status_shows_info() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "status").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("OASIS_OS"));
                assert!(s.contains("cwd: /"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn touch_creates_file() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        exec(&reg, &mut vfs, &mut cwd, "mkdir /tmp").unwrap();
        exec(&reg, &mut vfs, &mut cwd, "touch /tmp/new.txt").unwrap();
        assert!(vfs.exists("/tmp/new.txt"));
        assert_eq!(vfs.read("/tmp/new.txt").unwrap(), b"");
    }

    #[test]
    fn resolve_path_absolute() {
        assert_eq!(resolve_path("/any", "/foo/bar"), "/foo/bar");
    }

    #[test]
    fn resolve_path_relative() {
        assert_eq!(resolve_path("/home", "user"), "/home/user");
    }

    #[test]
    fn resolve_path_dotdot() {
        assert_eq!(resolve_path("/a/b/c", "../../x"), "/a/x");
    }

    #[test]
    fn resolve_path_root_relative() {
        assert_eq!(resolve_path("/", "foo"), "/foo");
    }
}
