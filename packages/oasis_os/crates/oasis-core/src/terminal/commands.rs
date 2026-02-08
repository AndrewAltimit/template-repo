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
    // Phase 4: file browser commands.
    reg.register(Box::new(CpCmd));
    reg.register(Box::new(MvCmd));
    reg.register(Box::new(FindCmd));
    // Phase 4: system commands using platform services.
    reg.register(Box::new(PowerCmd));
    reg.register(Box::new(ClockCmd));
    reg.register(Box::new(MemoryCmd));
    reg.register(Box::new(UsbCmd));
    // Phase 5: remote terminal commands.
    reg.register(Box::new(ListenCmd));
    reg.register(Box::new(RemoteCmd));
    reg.register(Box::new(HostsCmd));
    // Phase 11: audio commands.
    crate::terminal::register_audio_commands(reg);
    // Phase 12: scripting, update, and transfer commands.
    crate::script::register_script_commands(reg);
    crate::update::register_update_commands(reg);
    crate::transfer::register_transfer_commands(reg);
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
// cp
// ---------------------------------------------------------------------------

struct CpCmd;
impl Command for CpCmd {
    fn name(&self) -> &str {
        "cp"
    }
    fn description(&self) -> &str {
        "Copy a file"
    }
    fn usage(&self) -> &str {
        "cp <src> <dst>"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        if args.len() < 2 {
            return Err(OasisError::Command("usage: cp <src> <dst>".to_string()));
        }
        let src = resolve_path(&env.cwd, args[0]);
        let dst = resolve_path(&env.cwd, args[1]);
        let data = env.vfs.read(&src)?;
        env.vfs.write(&dst, &data)?;
        Ok(CommandOutput::None)
    }
}

// ---------------------------------------------------------------------------
// mv
// ---------------------------------------------------------------------------

struct MvCmd;
impl Command for MvCmd {
    fn name(&self) -> &str {
        "mv"
    }
    fn description(&self) -> &str {
        "Move/rename a file"
    }
    fn usage(&self) -> &str {
        "mv <src> <dst>"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        if args.len() < 2 {
            return Err(OasisError::Command("usage: mv <src> <dst>".to_string()));
        }
        let src = resolve_path(&env.cwd, args[0]);
        let dst = resolve_path(&env.cwd, args[1]);
        let data = env.vfs.read(&src)?;
        env.vfs.write(&dst, &data)?;
        env.vfs.remove(&src)?;
        Ok(CommandOutput::None)
    }
}

// ---------------------------------------------------------------------------
// find
// ---------------------------------------------------------------------------

struct FindCmd;
impl Command for FindCmd {
    fn name(&self) -> &str {
        "find"
    }
    fn description(&self) -> &str {
        "Find files by name pattern"
    }
    fn usage(&self) -> &str {
        "find [path] <pattern>"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let (root, pattern) = match args.len() {
            0 => {
                return Err(OasisError::Command(
                    "usage: find [path] <pattern>".to_string(),
                ));
            },
            1 => (env.cwd.clone(), args[0]),
            _ => (resolve_path(&env.cwd, args[0]), args[1]),
        };
        let mut results = Vec::new();
        find_recursive(env.vfs, &root, pattern, &mut results)?;
        if results.is_empty() {
            Ok(CommandOutput::Text("(no matches)".to_string()))
        } else {
            Ok(CommandOutput::Text(results.join("\n")))
        }
    }
}

/// Recursively search for files matching a simple substring pattern.
fn find_recursive(
    vfs: &mut dyn crate::vfs::Vfs,
    dir: &str,
    pattern: &str,
    results: &mut Vec<String>,
) -> Result<()> {
    let entries = vfs.readdir(dir)?;
    for entry in &entries {
        let full = if dir == "/" {
            format!("/{}", entry.name)
        } else {
            format!("{}/{}", dir, entry.name)
        };
        if entry.name.contains(pattern) {
            results.push(full.clone());
        }
        if entry.kind == EntryKind::Directory {
            find_recursive(vfs, &full, pattern, results)?;
        }
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// power
// ---------------------------------------------------------------------------

struct PowerCmd;
impl Command for PowerCmd {
    fn name(&self) -> &str {
        "power"
    }
    fn description(&self) -> &str {
        "Show power/battery status"
    }
    fn usage(&self) -> &str {
        "power"
    }
    fn execute(&self, _args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let Some(power) = env.power else {
            return Ok(CommandOutput::Text(
                "power: no platform service available".to_string(),
            ));
        };
        let info = power.power_info()?;
        let mut lines = Vec::new();
        lines.push(format!("State: {:?}", info.state));
        match info.battery_percent {
            Some(pct) => lines.push(format!("Battery: {pct}%")),
            None => lines.push("Battery: N/A".to_string()),
        }
        if let Some(mins) = info.battery_minutes {
            lines.push(format!("Remaining: {mins} min"));
        }
        if info.cpu.current_mhz > 0 {
            lines.push(format!(
                "CPU: {} MHz (max {} MHz)",
                info.cpu.current_mhz, info.cpu.max_mhz
            ));
        }
        Ok(CommandOutput::Text(lines.join("\n")))
    }
}

// ---------------------------------------------------------------------------
// clock
// ---------------------------------------------------------------------------

struct ClockCmd;
impl Command for ClockCmd {
    fn name(&self) -> &str {
        "clock"
    }
    fn description(&self) -> &str {
        "Show current time and uptime"
    }
    fn usage(&self) -> &str {
        "clock"
    }
    fn execute(&self, _args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let Some(time) = env.time else {
            return Ok(CommandOutput::Text(
                "clock: no platform service available".to_string(),
            ));
        };
        let now = time.now()?;
        let uptime = time.uptime_secs()?;
        let hours = uptime / 3600;
        let mins = (uptime % 3600) / 60;
        let secs = uptime % 60;
        let mut lines = Vec::new();
        lines.push(format!("Time: {now}"));
        lines.push(format!("Uptime: {hours}h {mins}m {secs}s"));
        Ok(CommandOutput::Text(lines.join("\n")))
    }
}

// ---------------------------------------------------------------------------
// memory
// ---------------------------------------------------------------------------

struct MemoryCmd;
impl Command for MemoryCmd {
    fn name(&self) -> &str {
        "memory"
    }
    fn description(&self) -> &str {
        "Show memory usage"
    }
    fn usage(&self) -> &str {
        "memory"
    }
    fn execute(&self, _args: &[&str], _env: &mut Environment<'_>) -> Result<CommandOutput> {
        // On desktop/Pi, report process RSS if /proc/self/status is readable.
        // On PSP, this would query sceKernelTotalFreeMemSize().
        let mut lines = Vec::new();
        lines.push("OASIS_OS memory info".to_string());
        #[cfg(target_os = "linux")]
        {
            if let Ok(status) = std::fs::read_to_string("/proc/self/status") {
                for line in status.lines() {
                    if line.starts_with("VmRSS:") || line.starts_with("VmSize:") {
                        lines.push(line.trim().to_string());
                    }
                }
            }
        }
        #[cfg(not(target_os = "linux"))]
        {
            lines.push("(detailed memory info not available on this platform)".to_string());
        }
        Ok(CommandOutput::Text(lines.join("\n")))
    }
}

// ---------------------------------------------------------------------------
// usb
// ---------------------------------------------------------------------------

struct UsbCmd;
impl Command for UsbCmd {
    fn name(&self) -> &str {
        "usb"
    }
    fn description(&self) -> &str {
        "Show USB status"
    }
    fn usage(&self) -> &str {
        "usb"
    }
    fn execute(&self, _args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let Some(usb) = env.usb else {
            return Ok(CommandOutput::Text(
                "usb: no platform service available".to_string(),
            ));
        };
        let state = usb.usb_state()?;
        Ok(CommandOutput::Text(format!("USB: {state}")))
    }
}

// ---------------------------------------------------------------------------
// listen
// ---------------------------------------------------------------------------

struct ListenCmd;
impl Command for ListenCmd {
    fn name(&self) -> &str {
        "listen"
    }
    fn description(&self) -> &str {
        "Start/stop remote terminal listener"
    }
    fn usage(&self) -> &str {
        "listen [port|stop]"
    }
    fn execute(&self, args: &[&str], _env: &mut Environment<'_>) -> Result<CommandOutput> {
        if args.is_empty() {
            return Ok(CommandOutput::ListenToggle { port: 9000 });
        }
        if args[0] == "stop" {
            return Ok(CommandOutput::ListenToggle { port: 0 });
        }
        match args[0].parse::<u16>() {
            Ok(port) => Ok(CommandOutput::ListenToggle { port }),
            Err(_) => Err(OasisError::Command("usage: listen [port|stop]".to_string())),
        }
    }
}

// ---------------------------------------------------------------------------
// remote
// ---------------------------------------------------------------------------

struct RemoteCmd;
impl Command for RemoteCmd {
    fn name(&self) -> &str {
        "remote"
    }
    fn description(&self) -> &str {
        "Connect to a remote host"
    }
    fn usage(&self) -> &str {
        "remote <host|addr:port>"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        if args.is_empty() {
            return Err(OasisError::Command(
                "usage: remote <host|addr:port>".to_string(),
            ));
        }
        let target = args[0];

        // Try addr:port format.
        if let Some((addr, port_str)) = target.rsplit_once(':') {
            if let Ok(port) = port_str.parse::<u16>() {
                return Ok(CommandOutput::RemoteConnect {
                    address: addr.to_string(),
                    port,
                    psk: None,
                });
            }
        }

        // Look up saved host from VFS config.
        let hosts_path = "/etc/hosts.toml";
        if env.vfs.exists(hosts_path) {
            let data = env.vfs.read(hosts_path)?;
            let toml_str = String::from_utf8_lossy(&data);
            if let Ok(hosts) = crate::net::parse_hosts(&toml_str) {
                for host in &hosts {
                    if host.name == target {
                        return Ok(CommandOutput::RemoteConnect {
                            address: host.address.clone(),
                            port: host.port,
                            psk: host.psk.clone(),
                        });
                    }
                }
            }
        }

        Err(OasisError::Command(format!(
            "unknown host: {target}  (use addr:port or configure in /etc/hosts.toml)"
        )))
    }
}

// ---------------------------------------------------------------------------
// hosts
// ---------------------------------------------------------------------------

struct HostsCmd;
impl Command for HostsCmd {
    fn name(&self) -> &str {
        "hosts"
    }
    fn description(&self) -> &str {
        "List saved remote hosts"
    }
    fn usage(&self) -> &str {
        "hosts"
    }
    fn execute(&self, _args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let hosts_path = "/etc/hosts.toml";
        if !env.vfs.exists(hosts_path) {
            return Ok(CommandOutput::Text(
                "(no hosts configured -- create /etc/hosts.toml)".to_string(),
            ));
        }
        let data = env.vfs.read(hosts_path)?;
        let toml_str = String::from_utf8_lossy(&data);
        let hosts = crate::net::parse_hosts(&toml_str)?;
        if hosts.is_empty() {
            return Ok(CommandOutput::Text("(no hosts defined)".to_string()));
        }
        let mut lines = Vec::new();
        for h in &hosts {
            lines.push(format!(
                "  {} -> {}:{} ({})",
                h.name, h.address, h.port, h.protocol
            ));
        }
        Ok(CommandOutput::Text(format!(
            "Saved hosts:\n{}",
            lines.join("\n")
        )))
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
            power: None,
            time: None,
            usb: None,
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

    // --- Phase 4: file browser commands ---

    #[test]
    fn cp_copies_file() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        exec(
            &reg,
            &mut vfs,
            &mut cwd,
            "cp /home/user/readme.txt /home/user/copy.txt",
        )
        .unwrap();
        assert!(vfs.exists("/home/user/copy.txt"));
        assert_eq!(vfs.read("/home/user/copy.txt").unwrap(), b"Hello OASIS");
        // Original still exists.
        assert!(vfs.exists("/home/user/readme.txt"));
    }

    #[test]
    fn cp_no_args() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        assert!(exec(&reg, &mut vfs, &mut cwd, "cp").is_err());
    }

    #[test]
    fn mv_moves_file() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        exec(
            &reg,
            &mut vfs,
            &mut cwd,
            "mv /home/user/readme.txt /home/moved.txt",
        )
        .unwrap();
        assert!(!vfs.exists("/home/user/readme.txt"));
        assert!(vfs.exists("/home/moved.txt"));
        assert_eq!(vfs.read("/home/moved.txt").unwrap(), b"Hello OASIS");
    }

    #[test]
    fn mv_no_args() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        assert!(exec(&reg, &mut vfs, &mut cwd, "mv").is_err());
    }

    #[test]
    fn find_by_name() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "find / readme").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("/home/user/readme.txt")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn find_no_matches() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "find / zzzzz").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no matches")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn find_no_args() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        assert!(exec(&reg, &mut vfs, &mut cwd, "find").is_err());
    }

    // --- Phase 4: system commands ---

    #[test]
    fn power_no_platform() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "power").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no platform")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn power_with_platform() {
        let (reg, mut vfs) = setup();
        let platform = crate::platform::DesktopPlatform::new();
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: Some(&platform),
            time: None,
            usb: None,
        };
        match reg.execute("power", &mut env).unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("NoBattery")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn clock_no_platform() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "clock").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no platform")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn clock_with_platform() {
        let (reg, mut vfs) = setup();
        let platform = crate::platform::DesktopPlatform::new();
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: Some(&platform),
            usb: None,
        };
        match reg.execute("clock", &mut env).unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("Time:"));
                assert!(s.contains("Uptime:"));
            },
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn memory_shows_info() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "memory").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("OASIS_OS memory")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn usb_no_platform() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "usb").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no platform")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn usb_with_platform() {
        let (reg, mut vfs) = setup();
        let platform = crate::platform::DesktopPlatform::new();
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: Some(&platform),
        };
        match reg.execute("usb", &mut env).unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("unsupported")),
            _ => panic!("expected text"),
        }
    }

    // --- Phase 5: remote terminal commands ---

    #[test]
    fn listen_default_port() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "listen").unwrap() {
            CommandOutput::ListenToggle { port } => assert_eq!(port, 9000),
            _ => panic!("expected ListenToggle"),
        }
    }

    #[test]
    fn listen_custom_port() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "listen 8080").unwrap() {
            CommandOutput::ListenToggle { port } => assert_eq!(port, 8080),
            _ => panic!("expected ListenToggle"),
        }
    }

    #[test]
    fn listen_stop() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "listen stop").unwrap() {
            CommandOutput::ListenToggle { port } => assert_eq!(port, 0),
            _ => panic!("expected ListenToggle"),
        }
    }

    #[test]
    fn remote_addr_port() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "remote 192.168.0.50:9000").unwrap() {
            CommandOutput::RemoteConnect { address, port, psk } => {
                assert_eq!(address, "192.168.0.50");
                assert_eq!(port, 9000);
                assert!(psk.is_none());
            },
            _ => panic!("expected RemoteConnect"),
        }
    }

    #[test]
    fn remote_saved_host() {
        let (reg, mut vfs) = setup();
        use crate::vfs::Vfs;
        vfs.mkdir("/etc").unwrap();
        vfs.write(
            "/etc/hosts.toml",
            br#"
[[host]]
name = "myserver"
address = "10.0.0.1"
port = 8080
psk = "secret"
"#,
        )
        .unwrap();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "remote myserver").unwrap() {
            CommandOutput::RemoteConnect { address, port, psk } => {
                assert_eq!(address, "10.0.0.1");
                assert_eq!(port, 8080);
                assert_eq!(psk, Some("secret".to_string()));
            },
            _ => panic!("expected RemoteConnect"),
        }
    }

    #[test]
    fn remote_unknown_host() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        assert!(exec(&reg, &mut vfs, &mut cwd, "remote unknown").is_err());
    }

    #[test]
    fn remote_no_args() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        assert!(exec(&reg, &mut vfs, &mut cwd, "remote").is_err());
    }

    #[test]
    fn hosts_no_config() {
        let (reg, mut vfs) = setup();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "hosts").unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no hosts configured")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn hosts_with_config() {
        let (reg, mut vfs) = setup();
        use crate::vfs::Vfs;
        vfs.mkdir("/etc").unwrap();
        vfs.write(
            "/etc/hosts.toml",
            br#"
[[host]]
name = "server1"
address = "1.2.3.4"
port = 9000

[[host]]
name = "server2"
address = "5.6.7.8"
port = 22
protocol = "raw-tcp"
"#,
        )
        .unwrap();
        let mut cwd = "/".to_string();
        match exec(&reg, &mut vfs, &mut cwd, "hosts").unwrap() {
            CommandOutput::Text(s) => {
                assert!(s.contains("server1"));
                assert!(s.contains("server2"));
                assert!(s.contains("1.2.3.4"));
            },
            _ => panic!("expected text"),
        }
    }
}
