//! Plugin lifecycle manager.
//!
//! Manages registration, initialization, per-frame updates, and shutdown
//! of plugins. Supports static registration (built-in plugins) and
//! manifest-based discovery from the VFS.

use serde::Deserialize;

use crate::error::{OasisError, Result};
use crate::sdi::SdiRegistry;
use crate::terminal::CommandRegistry;
use crate::vfs::Vfs;

use super::traits::{Plugin, PluginHost, PluginInfo, PluginState};

/// A loaded plugin with its runtime state.
struct LoadedPlugin {
    plugin: Box<dyn Plugin>,
    state: PluginState,
}

/// Plugin manifest from a TOML file in the VFS.
#[derive(Debug, Clone, Deserialize)]
pub struct PluginManifest {
    /// Plugin name.
    pub name: String,
    /// Plugin version.
    #[serde(default)]
    pub version: String,
    /// Plugin author.
    #[serde(default)]
    pub author: String,
    /// One-line description.
    #[serde(default)]
    pub description: String,
    /// Path to the shared library (relative to plugin directory).
    #[serde(default)]
    pub library: String,
    /// Whether to auto-load on startup.
    #[serde(default)]
    pub auto_load: bool,
}

/// Manages the plugin lifecycle.
pub struct PluginManager {
    plugins: Vec<LoadedPlugin>,
}

impl PluginManager {
    /// Create a new empty plugin manager.
    pub fn new() -> Self {
        Self {
            plugins: Vec::new(),
        }
    }

    /// Register a static (built-in) plugin.
    ///
    /// The plugin is added in `Registered` state and must be initialized
    /// via `init_all()` or `init_plugin()`.
    pub fn register_static(&mut self, plugin: Box<dyn Plugin>) {
        self.plugins.push(LoadedPlugin {
            plugin,
            state: PluginState::Registered,
        });
    }

    /// Initialize all registered (but not yet active) plugins.
    pub fn init_all(
        &mut self,
        sdi: &mut SdiRegistry,
        vfs: &mut dyn Vfs,
        commands: &mut CommandRegistry,
    ) -> Result<()> {
        let mut host = PluginHost { sdi, vfs, commands };
        for loaded in &mut self.plugins {
            if loaded.state == PluginState::Registered {
                loaded.plugin.init(&mut host)?;
                loaded.state = PluginState::Active;
            }
        }
        Ok(())
    }

    /// Initialize a single plugin by name.
    pub fn init_plugin(
        &mut self,
        name: &str,
        sdi: &mut SdiRegistry,
        vfs: &mut dyn Vfs,
        commands: &mut CommandRegistry,
    ) -> Result<()> {
        let mut host = PluginHost { sdi, vfs, commands };
        let loaded = self
            .plugins
            .iter_mut()
            .find(|p| p.plugin.info().name == name)
            .ok_or_else(|| OasisError::Plugin(format!("plugin not found: {name}")))?;
        if loaded.state != PluginState::Registered {
            return Err(OasisError::Plugin(format!(
                "plugin '{name}' is already {}",
                if loaded.state == PluginState::Active {
                    "active"
                } else {
                    "stopped"
                }
            )));
        }
        loaded.plugin.init(&mut host)?;
        loaded.state = PluginState::Active;
        Ok(())
    }

    /// Call `update()` on all active plugins.
    pub fn update_all(
        &mut self,
        sdi: &mut SdiRegistry,
        vfs: &mut dyn Vfs,
        commands: &mut CommandRegistry,
    ) -> Result<()> {
        let mut host = PluginHost { sdi, vfs, commands };
        for loaded in &mut self.plugins {
            if loaded.state == PluginState::Active {
                loaded.plugin.update(&mut host)?;
            }
        }
        Ok(())
    }

    /// Shutdown all active plugins.
    pub fn shutdown_all(
        &mut self,
        sdi: &mut SdiRegistry,
        vfs: &mut dyn Vfs,
        commands: &mut CommandRegistry,
    ) -> Result<()> {
        let mut host = PluginHost { sdi, vfs, commands };
        for loaded in &mut self.plugins {
            if loaded.state == PluginState::Active {
                loaded.plugin.shutdown(&mut host)?;
                loaded.state = PluginState::Stopped;
            }
        }
        Ok(())
    }

    /// Shutdown and remove a plugin by name.
    pub fn unload(
        &mut self,
        name: &str,
        sdi: &mut SdiRegistry,
        vfs: &mut dyn Vfs,
        commands: &mut CommandRegistry,
    ) -> Result<()> {
        let idx = self
            .plugins
            .iter()
            .position(|p| p.plugin.info().name == name)
            .ok_or_else(|| OasisError::Plugin(format!("plugin not found: {name}")))?;

        let loaded = &mut self.plugins[idx];
        if loaded.state == PluginState::Active {
            let mut host = PluginHost { sdi, vfs, commands };
            loaded.plugin.shutdown(&mut host)?;
        }
        self.plugins.remove(idx);
        Ok(())
    }

    /// List all plugins with their info and state.
    pub fn list(&self) -> Vec<(PluginInfo, PluginState)> {
        self.plugins
            .iter()
            .map(|p| (p.plugin.info(), p.state))
            .collect()
    }

    /// Return the number of loaded plugins.
    pub fn count(&self) -> usize {
        self.plugins.len()
    }

    /// Return the number of active plugins.
    pub fn active_count(&self) -> usize {
        self.plugins
            .iter()
            .filter(|p| p.state == PluginState::Active)
            .count()
    }

    /// Check if a plugin with the given name is loaded.
    pub fn is_loaded(&self, name: &str) -> bool {
        self.plugins.iter().any(|p| p.plugin.info().name == name)
    }

    /// Discover plugin manifests from the VFS plugin directory.
    ///
    /// Scans `/etc/oasis-os/plugins/` for `plugin.toml` files and returns
    /// their parsed manifests. This does NOT load the plugins -- it only
    /// discovers what's available.
    pub fn discover_manifests(vfs: &mut dyn Vfs) -> Vec<PluginManifest> {
        let plugin_dir = "/etc/oasis-os/plugins";
        if !vfs.exists(plugin_dir) {
            return Vec::new();
        }
        let entries = match vfs.readdir(plugin_dir) {
            Ok(e) => e,
            Err(_) => return Vec::new(),
        };

        let mut manifests = Vec::new();
        for entry in &entries {
            if entry.kind == crate::vfs::EntryKind::Directory {
                let manifest_path = format!("{plugin_dir}/{}/plugin.toml", entry.name);
                if vfs.exists(&manifest_path) {
                    if let Ok(data) = vfs.read(&manifest_path) {
                        let toml_str = String::from_utf8_lossy(&data);
                        if let Ok(manifest) = toml::from_str::<PluginManifest>(&toml_str) {
                            manifests.push(manifest);
                        }
                    }
                }
            }
        }
        manifests
    }
}

impl Default for PluginManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::plugin::traits::{Plugin, PluginHost, PluginInfo};
    use crate::sdi::SdiRegistry;
    use crate::terminal::CommandRegistry;
    use crate::vfs::{MemoryVfs, Vfs};

    /// Minimal test plugin that tracks lifecycle calls.
    struct TestPlugin {
        init_called: bool,
        update_count: u32,
        shutdown_called: bool,
    }

    impl TestPlugin {
        fn new() -> Self {
            Self {
                init_called: false,
                update_count: 0,
                shutdown_called: false,
            }
        }
    }

    impl Plugin for TestPlugin {
        fn info(&self) -> PluginInfo {
            PluginInfo::new("test-plugin", "1.0.0")
                .with_author("Test")
                .with_description("A test plugin")
        }
        fn init(&mut self, _host: &mut PluginHost<'_>) -> Result<()> {
            self.init_called = true;
            Ok(())
        }
        fn update(&mut self, _host: &mut PluginHost<'_>) -> Result<()> {
            self.update_count += 1;
            Ok(())
        }
        fn shutdown(&mut self, _host: &mut PluginHost<'_>) -> Result<()> {
            self.shutdown_called = true;
            Ok(())
        }
    }

    /// Plugin that creates an SDI object during init.
    struct SdiPlugin;
    impl Plugin for SdiPlugin {
        fn info(&self) -> PluginInfo {
            PluginInfo::new("sdi-plugin", "1.0.0")
        }
        fn init(&mut self, host: &mut PluginHost<'_>) -> Result<()> {
            let obj = host.sdi.create("plugin_widget");
            obj.x = 10;
            obj.y = 20;
            Ok(())
        }
        fn update(&mut self, _host: &mut PluginHost<'_>) -> Result<()> {
            Ok(())
        }
        fn shutdown(&mut self, host: &mut PluginHost<'_>) -> Result<()> {
            let _ = host.sdi.destroy("plugin_widget");
            Ok(())
        }
    }

    #[test]
    fn register_and_init() {
        let mut mgr = PluginManager::new();
        mgr.register_static(Box::new(TestPlugin::new()));
        assert_eq!(mgr.count(), 1);
        assert_eq!(mgr.active_count(), 0);

        let mut sdi = SdiRegistry::new();
        let mut vfs = MemoryVfs::new();
        let mut cmds = CommandRegistry::new();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();
        assert_eq!(mgr.active_count(), 1);
    }

    #[test]
    fn update_active_plugins() {
        let mut mgr = PluginManager::new();
        mgr.register_static(Box::new(TestPlugin::new()));

        let mut sdi = SdiRegistry::new();
        let mut vfs = MemoryVfs::new();
        let mut cmds = CommandRegistry::new();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        mgr.update_all(&mut sdi, &mut vfs, &mut cmds).unwrap();
        mgr.update_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        let plugins = mgr.list();
        assert_eq!(plugins.len(), 1);
        assert_eq!(plugins[0].1, PluginState::Active);
    }

    #[test]
    fn shutdown_all_plugins() {
        let mut mgr = PluginManager::new();
        mgr.register_static(Box::new(TestPlugin::new()));

        let mut sdi = SdiRegistry::new();
        let mut vfs = MemoryVfs::new();
        let mut cmds = CommandRegistry::new();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();
        mgr.shutdown_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        let plugins = mgr.list();
        assert_eq!(plugins[0].1, PluginState::Stopped);
        assert_eq!(mgr.active_count(), 0);
    }

    #[test]
    fn unload_plugin() {
        let mut mgr = PluginManager::new();
        mgr.register_static(Box::new(TestPlugin::new()));

        let mut sdi = SdiRegistry::new();
        let mut vfs = MemoryVfs::new();
        let mut cmds = CommandRegistry::new();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();
        assert!(mgr.is_loaded("test-plugin"));

        mgr.unload("test-plugin", &mut sdi, &mut vfs, &mut cmds)
            .unwrap();
        assert!(!mgr.is_loaded("test-plugin"));
        assert_eq!(mgr.count(), 0);
    }

    #[test]
    fn unload_missing_plugin() {
        let mut mgr = PluginManager::new();
        let mut sdi = SdiRegistry::new();
        let mut vfs = MemoryVfs::new();
        let mut cmds = CommandRegistry::new();
        assert!(
            mgr.unload("nonexistent", &mut sdi, &mut vfs, &mut cmds)
                .is_err()
        );
    }

    #[test]
    fn plugin_creates_sdi_objects() {
        let mut mgr = PluginManager::new();
        mgr.register_static(Box::new(SdiPlugin));

        let mut sdi = SdiRegistry::new();
        let mut vfs = MemoryVfs::new();
        let mut cmds = CommandRegistry::new();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        assert!(sdi.contains("plugin_widget"));
        let obj = sdi.get("plugin_widget").unwrap();
        assert_eq!(obj.x, 10);
        assert_eq!(obj.y, 20);
    }

    #[test]
    fn plugin_cleans_up_sdi_on_shutdown() {
        let mut mgr = PluginManager::new();
        mgr.register_static(Box::new(SdiPlugin));

        let mut sdi = SdiRegistry::new();
        let mut vfs = MemoryVfs::new();
        let mut cmds = CommandRegistry::new();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();
        assert!(sdi.contains("plugin_widget"));

        mgr.shutdown_all(&mut sdi, &mut vfs, &mut cmds).unwrap();
        assert!(!sdi.contains("plugin_widget"));
    }

    #[test]
    fn init_plugin_by_name() {
        let mut mgr = PluginManager::new();
        mgr.register_static(Box::new(TestPlugin::new()));
        mgr.register_static(Box::new(SdiPlugin));

        let mut sdi = SdiRegistry::new();
        let mut vfs = MemoryVfs::new();
        let mut cmds = CommandRegistry::new();

        // Only init one plugin.
        mgr.init_plugin("test-plugin", &mut sdi, &mut vfs, &mut cmds)
            .unwrap();
        assert_eq!(mgr.active_count(), 1);
        assert!(!sdi.contains("plugin_widget")); // SdiPlugin not initialized.
    }

    #[test]
    fn init_already_active_fails() {
        let mut mgr = PluginManager::new();
        mgr.register_static(Box::new(TestPlugin::new()));

        let mut sdi = SdiRegistry::new();
        let mut vfs = MemoryVfs::new();
        let mut cmds = CommandRegistry::new();
        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        assert!(
            mgr.init_plugin("test-plugin", &mut sdi, &mut vfs, &mut cmds)
                .is_err()
        );
    }

    #[test]
    fn list_plugins() {
        let mut mgr = PluginManager::new();
        mgr.register_static(Box::new(TestPlugin::new()));
        mgr.register_static(Box::new(SdiPlugin));

        let list = mgr.list();
        assert_eq!(list.len(), 2);
        assert_eq!(list[0].0.name, "test-plugin");
        assert_eq!(list[0].1, PluginState::Registered);
        assert_eq!(list[1].0.name, "sdi-plugin");
    }

    #[test]
    fn discover_manifests_empty() {
        let mut vfs = MemoryVfs::new();
        let manifests = PluginManager::discover_manifests(&mut vfs);
        assert!(manifests.is_empty());
    }

    #[test]
    fn discover_manifests_from_vfs() {
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/etc").unwrap();
        vfs.mkdir("/etc/oasis-os").unwrap();
        vfs.mkdir("/etc/oasis-os/plugins").unwrap();
        vfs.mkdir("/etc/oasis-os/plugins/my-plugin").unwrap();
        vfs.write(
            "/etc/oasis-os/plugins/my-plugin/plugin.toml",
            br#"
name = "my-plugin"
version = "2.0"
author = "Test"
description = "A discovered plugin"
library = "libmyplugin.so"
auto_load = true
"#,
        )
        .unwrap();

        let manifests = PluginManager::discover_manifests(&mut vfs);
        assert_eq!(manifests.len(), 1);
        assert_eq!(manifests[0].name, "my-plugin");
        assert_eq!(manifests[0].version, "2.0");
        assert!(manifests[0].auto_load);
    }

    #[test]
    fn multiple_plugins_lifecycle() {
        let mut mgr = PluginManager::new();
        mgr.register_static(Box::new(TestPlugin::new()));
        mgr.register_static(Box::new(SdiPlugin));
        assert_eq!(mgr.count(), 2);

        let mut sdi = SdiRegistry::new();
        let mut vfs = MemoryVfs::new();
        let mut cmds = CommandRegistry::new();

        mgr.init_all(&mut sdi, &mut vfs, &mut cmds).unwrap();
        assert_eq!(mgr.active_count(), 2);
        assert!(sdi.contains("plugin_widget"));

        mgr.update_all(&mut sdi, &mut vfs, &mut cmds).unwrap();

        mgr.unload("sdi-plugin", &mut sdi, &mut vfs, &mut cmds)
            .unwrap();
        assert_eq!(mgr.count(), 1);
        assert!(!sdi.contains("plugin_widget"));
        assert_eq!(mgr.active_count(), 1);

        mgr.shutdown_all(&mut sdi, &mut vfs, &mut cmds).unwrap();
        assert_eq!(mgr.active_count(), 0);
    }
}
