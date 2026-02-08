//! Built-in skin definitions.
//!
//! Each skin is defined as embedded TOML constants. These provide functional
//! skins out of the box without requiring external skin directories.

use crate::error::Result;

use super::loader::Skin;

// ---------------------------------------------------------------------------
// Terminal skin: full-screen green-on-black command line.
// ---------------------------------------------------------------------------

const TERMINAL_MANIFEST: &str = r#"
name = "terminal"
version = "1.0"
author = "OASIS_OS"
description = "Full-screen command line terminal with CRT aesthetic"
screen_width = 480
screen_height = 272
"#;

const TERMINAL_LAYOUT: &str = r##"
[terminal_bg]
x = 0
y = 0
w = 480
h = 272
color = "#000000"

[terminal_output]
x = 4
y = 4
w = 472
h = 252
color = "#00000000"
text = ""
font_size = 8
text_color = "#00CC00"

[terminal_prompt]
x = 4
y = 256
w = 472
h = 12
color = "#00000000"
text = "$> "
font_size = 8
text_color = "#00FF00"
"##;

const TERMINAL_FEATURES: &str = r#"
dashboard = false
terminal = true
file_browser = true
window_manager = false
"#;

const TERMINAL_THEME: &str = r##"
background = "#000000"
primary = "#00FF00"
secondary = "#003300"
text = "#00CC00"
dim_text = "#006600"
status_bar = "#001A00"
prompt = "#00FF00"
output = "#00CC00"
error = "#FF3333"
"##;

const TERMINAL_STRINGS: &str = r#"
boot_text = [
    "OASIS_OS v2.2 [terminal]",
    "Initializing subsystems...",
    "Network: standby",
    "VFS: mounted",
    "Ready.",
]
prompt_format = "$> "
title = "OASIS_OS Terminal"
welcome_message = "Type 'help' for available commands."
error_prefix = "error: "
shutdown_message = "Connection closed."
"#;

// ---------------------------------------------------------------------------
// Tactical skin: restricted military-style command console.
// ---------------------------------------------------------------------------

const TACTICAL_MANIFEST: &str = r#"
name = "tactical"
version = "1.0"
author = "OASIS_OS"
description = "Stripped-down tactical command console"
screen_width = 480
screen_height = 272
"#;

const TACTICAL_LAYOUT: &str = r##"
[status_bar]
x = 0
y = 0
w = 480
h = 16
color = "#1A1A1A"
text = "TACTICAL COMMAND SYSTEM"
font_size = 8
text_color = "#808080"

[separator]
x = 0
y = 16
w = 480
h = 1
color = "#333333"

[terminal_bg]
x = 0
y = 17
w = 480
h = 255
color = "#0A0A0A"

[terminal_output]
x = 4
y = 20
w = 472
h = 236
color = "#00000000"
text = ""
font_size = 8
text_color = "#AAAAAA"

[terminal_prompt]
x = 4
y = 256
w = 472
h = 12
color = "#00000000"
text = "cmd> "
font_size = 8
text_color = "#CC8800"

[status_left]
x = 4
y = 1
w = 200
h = 14
color = "#00000000"
text = "STATUS: ONLINE"
font_size = 8
text_color = "#00AA00"

[status_right]
x = 330
y = 1
w = 146
h = 14
color = "#00000000"
text = "CLEARANCE: ALPHA"
font_size = 8
text_color = "#CC8800"
"##;

const TACTICAL_FEATURES: &str = r#"
dashboard = false
terminal = true
file_browser = true
window_manager = false
command_categories = ["system", "file", "network"]
"#;

const TACTICAL_THEME: &str = r##"
background = "#0A0A0A"
primary = "#CC8800"
secondary = "#333333"
text = "#AAAAAA"
dim_text = "#666666"
status_bar = "#1A1A1A"
prompt = "#CC8800"
output = "#AAAAAA"
error = "#CC3333"
"##;

const TACTICAL_STRINGS: &str = r#"
boot_text = [
    "TACTICAL COMMAND SYSTEM v2.2",
    "Clearance level: ALPHA",
    "Secure channel established.",
    "Awaiting input.",
]
prompt_format = "cmd> "
title = "TACTICAL COMMAND"
home_label = "COMMAND"
welcome_message = "Tactical system online. Awaiting orders."
error_prefix = "ERR: "
shutdown_message = "Secure channel terminated."
"#;

// ---------------------------------------------------------------------------
// Corrupted skin: garbled Terminal variant with glitch effects.
// ---------------------------------------------------------------------------

const CORRUPTED_MANIFEST: &str = r#"
name = "corrupted"
version = "1.0"
author = "OASIS_OS"
description = "Damaged terminal with visual corruption and garbled output"
screen_width = 480
screen_height = 272
"#;

const CORRUPTED_LAYOUT: &str = r##"
[terminal_bg]
x = 0
y = 0
w = 480
h = 272
color = "#050005"

[glitch_overlay]
x = 0
y = 0
w = 480
h = 272
color = "#FF000008"
alpha = 20

[terminal_output]
x = 4
y = 4
w = 472
h = 252
color = "#00000000"
text = ""
font_size = 8
text_color = "#CC00CC"

[terminal_prompt]
x = 4
y = 256
w = 472
h = 12
color = "#00000000"
text = "?> "
font_size = 8
text_color = "#FF00FF"
"##;

const CORRUPTED_FEATURES: &str = r#"
dashboard = false
terminal = true
file_browser = true
window_manager = false
corrupted = true
"#;

const CORRUPTED_THEME: &str = r##"
background = "#050005"
primary = "#FF00FF"
secondary = "#330033"
text = "#CC00CC"
dim_text = "#660066"
status_bar = "#1A001A"
prompt = "#FF00FF"
output = "#CC00CC"
error = "#FF3333"
"##;

const CORRUPTED_STRINGS: &str = r#"
boot_text = [
    "O@S!S_OS v?.? [c0rrupt3d]",
    "W4RNING: syst3m int3grity compromis3d",
    "M0dules: [DAMAGED]",
    "VFS: m0unt3d (errors detected)",
    "R3ady... maybe.",
]
prompt_format = "?> "
title = "???_OS"
welcome_message = "Syst3m unst4ble. Proc33d with c4ution."
error_prefix = "3RR: "
shutdown_message = "signal l0st..."
"#;

const CORRUPTED_MODIFIERS: &str = r#"
position_jitter = 2
alpha_flicker_chance = 0.15
alpha_flicker_min = 60
text_garble_chance = 0.08
intensity = 1.0
"#;

// ---------------------------------------------------------------------------
// Desktop skin: WM-enabled with taskbar and windowed apps.
// ---------------------------------------------------------------------------

const DESKTOP_MANIFEST: &str = r#"
name = "desktop"
version = "1.0"
author = "OASIS_OS"
description = "Desktop-style interface with window manager and taskbar"
screen_width = 800
screen_height = 600
"#;

const DESKTOP_LAYOUT: &str = r##"
[desktop_bg]
x = 0
y = 0
w = 800
h = 600
color = "#1A1A2D"

[taskbar_bg]
x = 0
y = 568
w = 800
h = 32
color = "#222233"

[taskbar_separator]
x = 0
y = 567
w = 800
h = 1
color = "#444466"

[start_button]
x = 4
y = 572
w = 60
h = 24
color = "#3264C8"
text = "Start"
font_size = 10
text_color = "#FFFFFF"

[clock_display]
x = 730
y = 572
w = 66
h = 24
color = "#00000000"
text = "00:00"
font_size = 10
text_color = "#AAAACC"
"##;

const DESKTOP_FEATURES: &str = r#"
dashboard = false
terminal = true
file_browser = true
window_manager = true
"#;

const DESKTOP_THEME: &str = r##"
background = "#1A1A2D"
primary = "#3264C8"
secondary = "#444466"
text = "#FFFFFF"
dim_text = "#8888AA"
status_bar = "#222233"
prompt = "#00FF00"
output = "#CCCCCC"
error = "#FF4444"

[wm_theme]
titlebar_height = 24
border_width = 1
titlebar_active = "#3264C8"
titlebar_inactive = "#555566"
titlebar_text = "#FFFFFF"
frame_color = "#333344"
content_bg = "#1E1E2E"
btn_close = "#C83232"
btn_minimize = "#C8B432"
btn_maximize = "#32C832"
button_size = 16
resize_handle_size = 6
titlebar_font_size = 12
"##;

const DESKTOP_STRINGS: &str = r#"
boot_text = [
    "OASIS_OS v2.2 [desktop]",
    "Loading desktop environment...",
    "Window manager: active",
    "Ready.",
]
prompt_format = "{cwd} $ "
title = "OASIS Desktop"
home_label = "Desktop"
welcome_message = "Welcome to OASIS Desktop."
error_prefix = "error: "
shutdown_message = "Desktop session ended."
"#;

/// Load the Terminal skin.
pub fn terminal_skin() -> Result<Skin> {
    Skin::from_toml_full(
        TERMINAL_MANIFEST,
        TERMINAL_LAYOUT,
        TERMINAL_FEATURES,
        TERMINAL_THEME,
        TERMINAL_STRINGS,
    )
}

/// Load the Tactical skin.
pub fn tactical_skin() -> Result<Skin> {
    Skin::from_toml_full(
        TACTICAL_MANIFEST,
        TACTICAL_LAYOUT,
        TACTICAL_FEATURES,
        TACTICAL_THEME,
        TACTICAL_STRINGS,
    )
}

/// Load the Corrupted skin.
pub fn corrupted_skin() -> Result<Skin> {
    Skin::from_toml_corrupted(
        CORRUPTED_MANIFEST,
        CORRUPTED_LAYOUT,
        CORRUPTED_FEATURES,
        CORRUPTED_THEME,
        CORRUPTED_STRINGS,
        CORRUPTED_MODIFIERS,
    )
}

// ---------------------------------------------------------------------------
// Agent Terminal skin: briefcase field terminal for AI agent management.
// ---------------------------------------------------------------------------

const AGENT_TERMINAL_MANIFEST: &str = r#"
name = "agent-terminal"
version = "1.0"
author = "OASIS_OS"
description = "Briefcase field terminal for AI agent management"
screen_width = 480
screen_height = 272
"#;

const AGENT_TERMINAL_LAYOUT: &str = r##"
[status_bar]
x = 0
y = 0
w = 480
h = 18
color = "#0A1A2A"
text = "AGENT TERMINAL"
font_size = 8
text_color = "#00CCCC"

[tamper_indicator]
x = 380
y = 1
w = 96
h = 16
color = "#00000000"
text = "[?]"
font_size = 8
text_color = "#808080"

[separator_top]
x = 0
y = 18
w = 480
h = 1
color = "#006666"

[agent_panel]
x = 0
y = 19
w = 240
h = 80
color = "#0D1F2D"
text = "Agents: (loading...)"
font_size = 8
text_color = "#00AAAA"

[session_panel]
x = 240
y = 19
w = 240
h = 80
color = "#0D1F2D"
text = "Sessions: (none)"
font_size = 8
text_color = "#00AAAA"

[panel_divider]
x = 239
y = 19
w = 1
h = 80
color = "#006666"

[separator_mid]
x = 0
y = 99
w = 480
h = 1
color = "#006666"

[health_bar]
x = 0
y = 100
w = 480
h = 16
color = "#0A1520"
text = "CPU: -- | MEM: -- | NET: --"
font_size = 8
text_color = "#668888"

[separator_term]
x = 0
y = 116
w = 480
h = 1
color = "#006666"

[terminal_bg]
x = 0
y = 117
w = 480
h = 143
color = "#060D15"

[terminal_output]
x = 4
y = 120
w = 472
h = 124
color = "#00000000"
text = ""
font_size = 8
text_color = "#00BBBB"

[terminal_prompt]
x = 4
y = 256
w = 472
h = 12
color = "#00000000"
text = "agent> "
font_size = 8
text_color = "#00FFCC"
"##;

const AGENT_TERMINAL_FEATURES: &str = r#"
dashboard = false
terminal = true
file_browser = true
window_manager = false
command_categories = ["agent", "mcp", "system", "file", "network"]
"#;

const AGENT_TERMINAL_THEME: &str = r##"
background = "#060D15"
primary = "#00CCCC"
secondary = "#006666"
text = "#00BBBB"
dim_text = "#336666"
status_bar = "#0A1A2A"
prompt = "#00FFCC"
output = "#00BBBB"
error = "#FF4444"
"##;

const AGENT_TERMINAL_STRINGS: &str = r#"
boot_text = [
    "OASIS_OS v2.2 [agent-terminal]",
    "Briefcase secure terminal initializing...",
    "Loading agent registry...",
    "MCP servers: scanning...",
    "Tamper system: reading state...",
    "Remote terminal: standby",
    "Ready.",
]
prompt_format = "agent> "
title = "Agent Terminal"
home_label = "AGENTS"
welcome_message = "Briefcase agent terminal online. Type 'help' for commands."
error_prefix = "ERR: "
shutdown_message = "Agent terminal session ended."
"#;

/// Load the Agent Terminal skin.
pub fn agent_terminal_skin() -> Result<Skin> {
    Skin::from_toml_full(
        AGENT_TERMINAL_MANIFEST,
        AGENT_TERMINAL_LAYOUT,
        AGENT_TERMINAL_FEATURES,
        AGENT_TERMINAL_THEME,
        AGENT_TERMINAL_STRINGS,
    )
}

/// Load the Desktop skin.
pub fn desktop_skin() -> Result<Skin> {
    Skin::from_toml_full(
        DESKTOP_MANIFEST,
        DESKTOP_LAYOUT,
        DESKTOP_FEATURES,
        DESKTOP_THEME,
        DESKTOP_STRINGS,
    )
}

/// Load a built-in skin by name.
pub fn load_builtin(name: &str) -> Result<Skin> {
    match name {
        "terminal" => terminal_skin(),
        "tactical" => tactical_skin(),
        "corrupted" => corrupted_skin(),
        "desktop" => desktop_skin(),
        "agent-terminal" => agent_terminal_skin(),
        _ => Err(crate::error::OasisError::Config(format!(
            "unknown built-in skin: {name}"
        ))),
    }
}

/// List available built-in skin names.
pub fn builtin_names() -> &'static [&'static str] {
    &[
        "terminal",
        "tactical",
        "corrupted",
        "desktop",
        "agent-terminal",
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::sdi::SdiRegistry;

    #[test]
    fn terminal_skin_loads() {
        let skin = terminal_skin().unwrap();
        assert_eq!(skin.manifest.name, "terminal");
        assert!(!skin.features.dashboard);
        assert!(skin.features.terminal);
        assert!(!skin.features.window_manager);
        assert!(skin.corrupted_modifiers.is_none());
        assert_eq!(skin.strings.prompt_format, "$> ");
    }

    #[test]
    fn terminal_skin_applies_layout() {
        let skin = terminal_skin().unwrap();
        let mut sdi = SdiRegistry::new();
        skin.apply_layout(&mut sdi);
        assert!(sdi.contains("terminal_bg"));
        assert!(sdi.contains("terminal_output"));
        assert!(sdi.contains("terminal_prompt"));
    }

    #[test]
    fn tactical_skin_loads() {
        let skin = tactical_skin().unwrap();
        assert_eq!(skin.manifest.name, "tactical");
        assert!(!skin.features.dashboard);
        assert!(skin.features.terminal);
        assert!(!skin.features.window_manager);
        assert!(!skin.features.command_categories.is_empty());
        assert_eq!(skin.strings.prompt_format, "cmd> ");
    }

    #[test]
    fn tactical_skin_has_status_elements() {
        let skin = tactical_skin().unwrap();
        let mut sdi = SdiRegistry::new();
        skin.apply_layout(&mut sdi);
        assert!(sdi.contains("status_bar"));
        assert!(sdi.contains("status_left"));
        assert!(sdi.contains("status_right"));
    }

    #[test]
    fn corrupted_skin_loads() {
        let skin = corrupted_skin().unwrap();
        assert_eq!(skin.manifest.name, "corrupted");
        assert!(skin.features.corrupted);
        assert!(skin.corrupted_modifiers.is_some());
        let mods = skin.corrupted_modifiers.as_ref().unwrap();
        assert_eq!(mods.position_jitter, 2);
        assert!(mods.text_garble_chance > 0.0);
    }

    #[test]
    fn corrupted_skin_has_glitch_overlay() {
        let skin = corrupted_skin().unwrap();
        let mut sdi = SdiRegistry::new();
        skin.apply_layout(&mut sdi);
        assert!(sdi.contains("glitch_overlay"));
    }

    #[test]
    fn desktop_skin_loads() {
        let skin = desktop_skin().unwrap();
        assert_eq!(skin.manifest.name, "desktop");
        assert!(skin.features.window_manager);
        assert!(!skin.features.dashboard);
        assert_eq!(skin.manifest.screen_width, 800);
        assert_eq!(skin.manifest.screen_height, 600);
    }

    #[test]
    fn desktop_skin_has_wm_theme() {
        let skin = desktop_skin().unwrap();
        let wm = skin.theme.build_wm_theme();
        assert_eq!(wm.titlebar_height, 24);
        assert_eq!(wm.button_size, 16);
    }

    #[test]
    fn desktop_skin_has_taskbar() {
        let skin = desktop_skin().unwrap();
        let mut sdi = SdiRegistry::new();
        skin.apply_layout(&mut sdi);
        assert!(sdi.contains("taskbar_bg"));
        assert!(sdi.contains("start_button"));
        assert!(sdi.contains("clock_display"));
    }

    #[test]
    fn load_builtin_all_names() {
        for name in builtin_names() {
            let skin = load_builtin(name).unwrap();
            assert_eq!(skin.manifest.name, *name);
        }
    }

    #[test]
    fn load_builtin_unknown_fails() {
        assert!(load_builtin("nonexistent").is_err());
    }

    #[test]
    fn swap_between_builtin_skins() {
        let terminal = terminal_skin().unwrap();
        let desktop = desktop_skin().unwrap();

        let mut sdi = SdiRegistry::new();
        terminal.apply_layout(&mut sdi);
        assert!(sdi.contains("terminal_bg"));
        assert!(sdi.contains("terminal_prompt"));

        let _new = Skin::swap(&terminal, desktop, &mut sdi);
        // Terminal-only objects removed, desktop objects created.
        assert!(!sdi.contains("terminal_bg"));
        assert!(!sdi.contains("terminal_prompt"));
        assert!(sdi.contains("desktop_bg"));
        assert!(sdi.contains("taskbar_bg"));
    }

    #[test]
    fn all_skins_have_boot_text() {
        for name in builtin_names() {
            let skin = load_builtin(name).unwrap();
            assert!(
                !skin.strings.boot_text.is_empty(),
                "{name} skin should have boot text"
            );
        }
    }

    #[test]
    fn all_skins_have_prompt() {
        for name in builtin_names() {
            let skin = load_builtin(name).unwrap();
            assert!(
                !skin.strings.prompt_format.is_empty(),
                "{name} skin should have prompt format"
            );
        }
    }

    #[test]
    fn agent_terminal_skin_loads() {
        let skin = agent_terminal_skin().unwrap();
        assert_eq!(skin.manifest.name, "agent-terminal");
        assert!(!skin.features.dashboard);
        assert!(skin.features.terminal);
        assert!(skin.features.file_browser);
        assert!(!skin.features.window_manager);
        assert!(!skin.features.command_categories.is_empty());
        assert!(
            skin.features
                .command_categories
                .contains(&"agent".to_string())
        );
        assert!(
            skin.features
                .command_categories
                .contains(&"mcp".to_string())
        );
        assert_eq!(skin.strings.prompt_format, "agent> ");
    }

    #[test]
    fn agent_terminal_skin_has_panels() {
        let skin = agent_terminal_skin().unwrap();
        let mut sdi = SdiRegistry::new();
        skin.apply_layout(&mut sdi);
        assert!(sdi.contains("status_bar"));
        assert!(sdi.contains("agent_panel"));
        assert!(sdi.contains("session_panel"));
        assert!(sdi.contains("tamper_indicator"));
        assert!(sdi.contains("health_bar"));
        assert!(sdi.contains("terminal_output"));
        assert!(sdi.contains("terminal_prompt"));
    }

    #[test]
    fn agent_terminal_theme_colors() {
        let skin = agent_terminal_skin().unwrap();
        let bg = skin.theme.background_color();
        // Teal-ish dark background.
        assert_eq!(bg.r, 6);
        assert_eq!(bg.g, 13);
    }

    #[test]
    fn swap_terminal_to_agent_terminal() {
        let terminal = terminal_skin().unwrap();
        let agent = agent_terminal_skin().unwrap();

        let mut sdi = SdiRegistry::new();
        terminal.apply_layout(&mut sdi);
        assert!(sdi.contains("terminal_bg"));

        let _new = Skin::swap(&terminal, agent, &mut sdi);
        // Agent terminal has its own terminal_bg plus dashboard panels.
        assert!(sdi.contains("agent_panel"));
        assert!(sdi.contains("tamper_indicator"));
        assert!(sdi.contains("health_bar"));
    }
}
