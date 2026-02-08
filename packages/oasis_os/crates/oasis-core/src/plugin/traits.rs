//! Plugin trait and host API definitions.
//!
//! Plugins extend OASIS_OS with new commands, UI elements, and behaviors.
//! They interact with the OS through a `PluginHost` that provides access
//! to the SDI scene graph, command registry, and virtual file system.

use crate::error::Result;
use crate::sdi::SdiRegistry;
use crate::terminal::CommandRegistry;
use crate::vfs::Vfs;

/// Metadata about a plugin.
#[derive(Debug, Clone)]
pub struct PluginInfo {
    /// Plugin name (unique identifier).
    pub name: String,
    /// Semantic version string.
    pub version: String,
    /// Plugin author.
    pub author: String,
    /// One-line description.
    pub description: String,
}

impl PluginInfo {
    /// Create a new `PluginInfo` with the given name and version.
    pub fn new(name: &str, version: &str) -> Self {
        Self {
            name: name.to_string(),
            version: version.to_string(),
            author: String::new(),
            description: String::new(),
        }
    }

    /// Builder method to set the author.
    pub fn with_author(mut self, author: &str) -> Self {
        self.author = author.to_string();
        self
    }

    /// Builder method to set the description.
    pub fn with_description(mut self, description: &str) -> Self {
        self.description = description.to_string();
        self
    }
}

/// Host-side context passed to plugins during lifecycle calls.
///
/// Provides access to OS services that plugins can use to register
/// commands, create UI elements, and read/write files.
pub struct PluginHost<'a> {
    /// SDI scene graph for creating/modifying UI elements.
    pub sdi: &'a mut SdiRegistry,
    /// Virtual file system for reading/writing files.
    pub vfs: &'a mut dyn Vfs,
    /// Command registry for registering new commands.
    pub commands: &'a mut CommandRegistry,
}

/// The plugin interface that all plugins must implement.
///
/// Lifecycle:
/// 1. `info()` -- called to get plugin metadata (before init)
/// 2. `init()` -- called once when the plugin is loaded
/// 3. `update()` -- called once per frame (optional work)
/// 4. `shutdown()` -- called when the plugin is unloaded
pub trait Plugin {
    /// Return plugin metadata.
    fn info(&self) -> PluginInfo;

    /// Initialize the plugin. Register commands, create SDI objects, etc.
    fn init(&mut self, host: &mut PluginHost<'_>) -> Result<()>;

    /// Per-frame update. Called once per main loop iteration.
    /// Most plugins can leave this as a no-op.
    fn update(&mut self, host: &mut PluginHost<'_>) -> Result<()>;

    /// Shutdown the plugin. Clean up SDI objects, deregister resources.
    fn shutdown(&mut self, host: &mut PluginHost<'_>) -> Result<()>;
}

/// Current state of a loaded plugin.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PluginState {
    /// Plugin is registered but not yet initialized.
    Registered,
    /// Plugin has been initialized and is running.
    Active,
    /// Plugin has been shut down.
    Stopped,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn plugin_info_builder() {
        let info = PluginInfo::new("test-plugin", "1.0.0")
            .with_author("Test Author")
            .with_description("A test plugin");
        assert_eq!(info.name, "test-plugin");
        assert_eq!(info.version, "1.0.0");
        assert_eq!(info.author, "Test Author");
        assert_eq!(info.description, "A test plugin");
    }

    #[test]
    fn plugin_info_defaults() {
        let info = PluginInfo::new("minimal", "0.1");
        assert_eq!(info.name, "minimal");
        assert!(info.author.is_empty());
        assert!(info.description.is_empty());
    }
}
