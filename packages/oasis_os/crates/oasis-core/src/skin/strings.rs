//! Skin strings -- user-facing text for menus, prompts, and messages.
//!
//! All displayed text is skin-configurable via `strings.toml`. This enables
//! different personas (military-style for Tactical, hacker-style for Terminal,
//! garbled for Corrupted) without code changes.

use serde::Deserialize;

/// User-facing text strings for a skin.
#[derive(Debug, Clone, Deserialize)]
pub struct SkinStrings {
    /// Boot sequence text lines (displayed during startup animation).
    #[serde(default)]
    pub boot_text: Vec<String>,
    /// Terminal prompt format. Use `{cwd}` as placeholder for current directory.
    #[serde(default = "default_prompt")]
    pub prompt_format: String,
    /// Display title shown in the status bar or window title.
    #[serde(default = "default_title")]
    pub title: String,
    /// Label for the "home" or main menu page.
    #[serde(default = "default_home_label")]
    pub home_label: String,
    /// Error prefix shown before command errors.
    #[serde(default = "default_error_prefix")]
    pub error_prefix: String,
    /// Shutdown message.
    #[serde(default = "default_shutdown")]
    pub shutdown_message: String,
    /// Welcome message shown after boot.
    #[serde(default = "default_welcome")]
    pub welcome_message: String,
}

fn default_prompt() -> String {
    "$> ".to_string()
}
fn default_title() -> String {
    "OASIS_OS".to_string()
}
fn default_home_label() -> String {
    "Home".to_string()
}
fn default_error_prefix() -> String {
    "error: ".to_string()
}
fn default_shutdown() -> String {
    "System halted.".to_string()
}
fn default_welcome() -> String {
    "Welcome to OASIS_OS.".to_string()
}

impl Default for SkinStrings {
    fn default() -> Self {
        Self {
            boot_text: Vec::new(),
            prompt_format: default_prompt(),
            title: default_title(),
            home_label: default_home_label(),
            error_prefix: default_error_prefix(),
            shutdown_message: default_shutdown(),
            welcome_message: default_welcome(),
        }
    }
}

impl SkinStrings {
    /// Format the prompt with the current working directory substituted.
    pub fn format_prompt(&self, cwd: &str) -> String {
        self.prompt_format.replace("{cwd}", cwd)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_strings() {
        let s = SkinStrings::default();
        assert_eq!(s.prompt_format, "$> ");
        assert_eq!(s.title, "OASIS_OS");
        assert!(s.boot_text.is_empty());
    }

    #[test]
    fn format_prompt_substitution() {
        let s = SkinStrings {
            prompt_format: "{cwd} $ ".to_string(),
            ..SkinStrings::default()
        };
        assert_eq!(s.format_prompt("/home"), "/home $ ");
    }

    #[test]
    fn format_prompt_no_placeholder() {
        let s = SkinStrings {
            prompt_format: "root# ".to_string(),
            ..SkinStrings::default()
        };
        assert_eq!(s.format_prompt("/whatever"), "root# ");
    }

    #[test]
    fn deserialize_from_toml() {
        let toml = r#"
boot_text = ["Initializing...", "Loading modules...", "Ready."]
prompt_format = "root@tactical:{cwd}# "
title = "TACTICAL COMMAND"
welcome_message = "TACTICAL SYSTEM ONLINE"
"#;
        let s: SkinStrings = toml::from_str(toml).unwrap();
        assert_eq!(s.boot_text.len(), 3);
        assert_eq!(s.prompt_format, "root@tactical:{cwd}# ");
        assert_eq!(s.title, "TACTICAL COMMAND");
        assert_eq!(s.welcome_message, "TACTICAL SYSTEM ONLINE");
        // Defaults for unspecified fields.
        assert_eq!(s.error_prefix, "error: ");
    }
}
