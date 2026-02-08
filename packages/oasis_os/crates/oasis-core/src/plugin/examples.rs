//! Built-in example plugins demonstrating the plugin API.
//!
//! These serve as both functional examples and integration tests for the
//! plugin system. They are statically linked and can be registered via
//! `register_builtin_plugins()`.

use crate::error::{OasisError, Result};
use crate::terminal::{Command, CommandOutput, Environment};

use super::traits::{Plugin, PluginHost, PluginInfo};

// ---------------------------------------------------------------------------
// HelloPlugin -- simplest possible plugin
// ---------------------------------------------------------------------------

/// A minimal plugin that registers a single "hello" command.
pub struct HelloPlugin;

impl Plugin for HelloPlugin {
    fn info(&self) -> PluginInfo {
        PluginInfo::new("hello", "1.0.0")
            .with_author("OASIS_OS")
            .with_description("Hello world example plugin")
    }

    fn init(&mut self, host: &mut PluginHost<'_>) -> Result<()> {
        host.commands.register(Box::new(HelloCmd));
        Ok(())
    }

    fn update(&mut self, _host: &mut PluginHost<'_>) -> Result<()> {
        Ok(())
    }

    fn shutdown(&mut self, _host: &mut PluginHost<'_>) -> Result<()> {
        // Command remains registered (CommandRegistry doesn't support removal).
        // In a real implementation, the registry would track plugin ownership.
        Ok(())
    }
}

struct HelloCmd;
impl Command for HelloCmd {
    fn name(&self) -> &str {
        "hello"
    }
    fn description(&self) -> &str {
        "Say hello (example plugin)"
    }
    fn usage(&self) -> &str {
        "hello [name]"
    }
    fn execute(&self, args: &[&str], _env: &mut Environment<'_>) -> Result<CommandOutput> {
        let name = if args.is_empty() { "World" } else { args[0] };
        Ok(CommandOutput::Text(format!("Hello, {name}!")))
    }
}

// ---------------------------------------------------------------------------
// ClockWidgetPlugin -- creates an SDI clock widget + command
// ---------------------------------------------------------------------------

/// Plugin that creates a clock display widget in the SDI scene graph
/// and registers a "pclock" command.
pub struct ClockWidgetPlugin {
    /// Whether the widget has been created.
    widget_created: bool,
}

impl ClockWidgetPlugin {
    pub fn new() -> Self {
        Self {
            widget_created: false,
        }
    }
}

impl Default for ClockWidgetPlugin {
    fn default() -> Self {
        Self::new()
    }
}

const CLOCK_WIDGET_NAME: &str = "plugin_clock";

impl Plugin for ClockWidgetPlugin {
    fn info(&self) -> PluginInfo {
        PluginInfo::new("clock-widget", "1.0.0")
            .with_author("OASIS_OS")
            .with_description("Clock display widget and pclock command")
    }

    fn init(&mut self, host: &mut PluginHost<'_>) -> Result<()> {
        // Create an SDI object for the clock display.
        let obj = host.sdi.create(CLOCK_WIDGET_NAME);
        obj.x = 380;
        obj.y = 4;
        obj.w = 96;
        obj.h = 16;
        obj.text = Some("00:00:00".to_string());
        obj.font_size = 10;
        obj.visible = true;
        self.widget_created = true;

        // Register the pclock command.
        host.commands.register(Box::new(PclockCmd));
        Ok(())
    }

    fn update(&mut self, host: &mut PluginHost<'_>) -> Result<()> {
        if !self.widget_created {
            return Ok(());
        }
        // Update the clock text. On a real system this would read the time
        // service. For now, we just confirm the widget exists.
        if let Ok(obj) = host.sdi.get_mut(CLOCK_WIDGET_NAME) {
            // In a real implementation, we'd format the current time here.
            // For testing, just ensure the widget is accessible.
            let _ = obj.text.as_ref();
        }
        Ok(())
    }

    fn shutdown(&mut self, host: &mut PluginHost<'_>) -> Result<()> {
        if self.widget_created {
            let _ = host.sdi.destroy(CLOCK_WIDGET_NAME);
            self.widget_created = false;
        }
        Ok(())
    }
}

struct PclockCmd;
impl Command for PclockCmd {
    fn name(&self) -> &str {
        "pclock"
    }
    fn description(&self) -> &str {
        "Show clock widget status (clock-widget plugin)"
    }
    fn usage(&self) -> &str {
        "pclock [show|hide]"
    }
    fn execute(&self, args: &[&str], _env: &mut Environment<'_>) -> Result<CommandOutput> {
        let subcmd = args.first().copied().unwrap_or("status");
        match subcmd {
            "show" => Ok(CommandOutput::Text("Clock widget: visible".to_string())),
            "hide" => Ok(CommandOutput::Text("Clock widget: hidden".to_string())),
            _ => Ok(CommandOutput::Text(
                "Clock widget plugin active. Use 'pclock show' or 'pclock hide'.".to_string(),
            )),
        }
    }
}

// ---------------------------------------------------------------------------
// NotepadPlugin -- VFS-backed notepad with read/write commands
// ---------------------------------------------------------------------------

/// Plugin that provides a simple notepad backed by VFS files.
/// Demonstrates VFS interaction from a plugin.
pub struct NotepadPlugin;

const NOTEPAD_DIR: &str = "/var/notepad";

impl Plugin for NotepadPlugin {
    fn info(&self) -> PluginInfo {
        PluginInfo::new("notepad", "1.0.0")
            .with_author("OASIS_OS")
            .with_description("Simple notepad with VFS-backed notes")
    }

    fn init(&mut self, host: &mut PluginHost<'_>) -> Result<()> {
        // Ensure the notepad directory exists.
        if !host.vfs.exists(NOTEPAD_DIR) {
            // Create parent directories if needed.
            if !host.vfs.exists("/var") {
                host.vfs.mkdir("/var")?;
            }
            host.vfs.mkdir(NOTEPAD_DIR)?;
        }
        host.commands.register(Box::new(NoteCmd));
        Ok(())
    }

    fn update(&mut self, _host: &mut PluginHost<'_>) -> Result<()> {
        Ok(())
    }

    fn shutdown(&mut self, _host: &mut PluginHost<'_>) -> Result<()> {
        // Notes persist in VFS -- don't delete them on shutdown.
        Ok(())
    }
}

struct NoteCmd;
impl Command for NoteCmd {
    fn name(&self) -> &str {
        "note"
    }
    fn description(&self) -> &str {
        "Read/write notes (notepad plugin)"
    }
    fn usage(&self) -> &str {
        "note [list|read <name>|write <name> <text>]"
    }
    fn execute(&self, args: &[&str], env: &mut Environment<'_>) -> Result<CommandOutput> {
        let subcmd = args.first().copied().unwrap_or("list");

        match subcmd {
            "list" => {
                if !env.vfs.exists(NOTEPAD_DIR) {
                    return Ok(CommandOutput::Text("(no notes)".to_string()));
                }
                let entries = env.vfs.readdir(NOTEPAD_DIR)?;
                if entries.is_empty() {
                    return Ok(CommandOutput::Text("(no notes)".to_string()));
                }
                let mut lines = Vec::new();
                lines.push("Notes:".to_string());
                for e in &entries {
                    lines.push(format!("  {}", e.name));
                }
                Ok(CommandOutput::Text(lines.join("\n")))
            },
            "read" => {
                let name = args.get(1).copied().unwrap_or("");
                if name.is_empty() {
                    return Err(OasisError::Command("usage: note read <name>".to_string()));
                }
                let path = format!("{NOTEPAD_DIR}/{name}");
                let data = env.vfs.read(&path)?;
                let text = String::from_utf8_lossy(&data).into_owned();
                Ok(CommandOutput::Text(text))
            },
            "write" => {
                let name = args.get(1).copied().unwrap_or("");
                if name.is_empty() || args.len() < 3 {
                    return Err(OasisError::Command(
                        "usage: note write <name> <text...>".to_string(),
                    ));
                }
                let text = args[2..].join(" ");
                let path = format!("{NOTEPAD_DIR}/{name}");
                env.vfs.write(&path, text.as_bytes())?;
                Ok(CommandOutput::Text(format!("Note '{name}' saved.")))
            },
            _ => Err(OasisError::Command(format!(
                "unknown subcommand: {subcmd}\nusage: note [list|read <name>|write <name> <text>]"
            ))),
        }
    }
}

/// Register all built-in example plugins.
pub fn register_builtin_plugins(manager: &mut super::PluginManager) {
    manager.register_static(Box::new(HelloPlugin));
    manager.register_static(Box::new(ClockWidgetPlugin::new()));
    manager.register_static(Box::new(NotepadPlugin));
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::plugin::manager::PluginManager;
    use crate::sdi::SdiRegistry;
    use crate::terminal::CommandRegistry;
    use crate::vfs::{MemoryVfs, Vfs};

    fn setup() -> (PluginManager, SdiRegistry, MemoryVfs, CommandRegistry) {
        let mut mgr = PluginManager::new();
        register_builtin_plugins(&mut mgr);
        (
            mgr,
            SdiRegistry::new(),
            MemoryVfs::new(),
            CommandRegistry::new(),
        )
    }

    #[test]
    fn register_builtin_count() {
        let (mgr, _, _, _) = setup();
        assert_eq!(mgr.count(), 3);
    }

    #[test]
    fn hello_plugin_registers_command() {
        let (mut mgr, mut sdi, mut vfs, mut cmds) = setup();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        match cmds.execute("hello", &mut env).unwrap() {
            CommandOutput::Text(s) => assert_eq!(s, "Hello, World!"),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn hello_plugin_with_name() {
        let (mut mgr, mut sdi, mut vfs, mut cmds) = setup();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        match cmds.execute("hello OASIS", &mut env).unwrap() {
            CommandOutput::Text(s) => assert_eq!(s, "Hello, OASIS!"),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn clock_widget_creates_sdi() {
        let (mut mgr, mut sdi, mut vfs, mut cmds) = setup();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        assert!(sdi.contains("plugin_clock"));
        let obj = sdi.get("plugin_clock").unwrap();
        assert_eq!(obj.x, 380);
        assert!(obj.text.is_some());
    }

    #[test]
    fn clock_widget_update() {
        let (mut mgr, mut sdi, mut vfs, mut cmds) = setup();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();
        mgr.update_all(&mut sdi, &mut vfs, &mut cmds).unwrap();
        // Widget should still exist after update.
        assert!(sdi.contains("plugin_clock"));
    }

    #[test]
    fn clock_widget_cleanup_on_shutdown() {
        let (mut mgr, mut sdi, mut vfs, mut cmds) = setup();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();
        assert!(sdi.contains("plugin_clock"));

        mgr.shutdown_all(&mut sdi, &mut vfs, &mut cmds).unwrap();
        assert!(!sdi.contains("plugin_clock"));
    }

    #[test]
    fn pclock_command() {
        let (mut mgr, mut sdi, mut vfs, mut cmds) = setup();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        match cmds.execute("pclock", &mut env).unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("plugin active")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn notepad_creates_directory() {
        let (mut mgr, mut sdi, mut vfs, mut cmds) = setup();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();
        assert!(vfs.exists("/var/notepad"));
    }

    #[test]
    fn notepad_write_and_read() {
        let (mut mgr, mut sdi, mut vfs, mut cmds) = setup();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        // Write a note.
        match cmds
            .execute("note write todo Fix the bug", &mut env)
            .unwrap()
        {
            CommandOutput::Text(s) => assert!(s.contains("saved")),
            _ => panic!("expected text"),
        }

        // Read it back.
        match cmds.execute("note read todo", &mut env).unwrap() {
            CommandOutput::Text(s) => assert_eq!(s, "Fix the bug"),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn notepad_list_notes() {
        let (mut mgr, mut sdi, mut vfs, mut cmds) = setup();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        // Initially empty.
        match cmds.execute("note list", &mut env).unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("no notes")),
            _ => panic!("expected text"),
        }

        // Write a note and list again.
        cmds.execute("note write memo Remember to test", &mut env)
            .unwrap();
        match cmds.execute("note list", &mut env).unwrap() {
            CommandOutput::Text(s) => assert!(s.contains("memo")),
            _ => panic!("expected text"),
        }
    }

    #[test]
    fn notepad_read_missing() {
        let (mut mgr, mut sdi, mut vfs, mut cmds) = setup();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        assert!(cmds.execute("note read nonexistent", &mut env).is_err());
    }

    #[test]
    fn notepad_notes_persist_after_shutdown() {
        let (mut mgr, mut sdi, mut vfs, mut cmds) = setup();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        // Write a note.
        let mut env = Environment {
            cwd: "/".to_string(),
            vfs: &mut vfs,
            power: None,
            time: None,
            usb: None,
        };
        cmds.execute("note write test Hello", &mut env).unwrap();

        // Shutdown plugins.
        mgr.shutdown_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        // Note file should still exist in VFS.
        assert!(vfs.exists("/var/notepad/test"));
    }
}
