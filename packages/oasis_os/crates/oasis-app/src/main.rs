//! OASIS_OS desktop entry point.
//!
//! Loads the Classic skin, discovers apps from a demo VFS, displays the
//! icon grid dashboard, and handles cursor navigation with D-pad input.
//! Press Enter to switch to terminal mode; press Escape/Cancel to quit.

use anyhow::Result;

use oasis_backend_sdl::SdlBackend;
use oasis_core::backend::{Color, InputBackend, SdiBackend};
use oasis_core::config::OasisConfig;
use oasis_core::dashboard::{DashboardConfig, DashboardState, discover_apps};
use oasis_core::input::{Button, InputEvent, Trigger};
use oasis_core::sdi::SdiRegistry;
use oasis_core::skin::Skin;
use oasis_core::terminal::{CommandOutput, CommandRegistry, Environment, register_builtins};
use oasis_core::vfs::MemoryVfs;

/// Maximum lines visible in the terminal output area.
const MAX_OUTPUT_LINES: usize = 12;

/// The two UI modes the demo supports.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Mode {
    Dashboard,
    Terminal,
}

fn main() -> Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let config = OasisConfig::default();
    log::info!(
        "Starting OASIS_OS ({}x{})",
        config.screen_width,
        config.screen_height,
    );

    let mut backend = SdlBackend::new(
        &config.window_title,
        config.screen_width,
        config.screen_height,
    )?;
    backend.init(config.screen_width, config.screen_height)?;

    // Load Classic skin from embedded TOML strings.
    let skin = Skin::from_toml(
        include_str!("../../../skins/classic/skin.toml"),
        include_str!("../../../skins/classic/layout.toml"),
        include_str!("../../../skins/classic/features.toml"),
    )?;
    log::info!(
        "Loaded skin: {} v{}",
        skin.manifest.name,
        skin.manifest.version
    );

    // Set up VFS with demo content + apps.
    let mut vfs = MemoryVfs::new();
    populate_demo_vfs(&mut vfs);

    // Discover apps.
    let apps = discover_apps(&vfs, "/apps", Some("OASISOS"))?;
    log::info!("Discovered {} apps", apps.len());

    // Set up dashboard.
    let dash_config = DashboardConfig::from_features(
        &skin.features,
        skin.manifest.screen_width,
        skin.manifest.screen_height,
    );
    let mut dashboard = DashboardState::new(dash_config, apps);

    // Set up command interpreter.
    let mut cmd_reg = CommandRegistry::new();
    register_builtins(&mut cmd_reg);

    // Terminal state.
    let mut cwd = "/".to_string();
    let mut input_buf = String::new();
    let mut output_lines: Vec<String> = vec![
        "OASIS_OS v0.1.0 -- Type 'help' for commands".to_string(),
        "Press F1 to return to dashboard".to_string(),
        String::new(),
    ];

    // Set up scene graph and apply skin layout.
    let mut sdi = SdiRegistry::new();
    skin.apply_layout(&mut sdi);

    let mut mode = Mode::Dashboard;
    let bg_color = Color::rgb(10, 10, 18);

    'running: loop {
        let events = backend.poll_events();
        for event in &events {
            match event {
                InputEvent::Quit => break 'running,
                InputEvent::ButtonPress(Button::Cancel) => break 'running,

                // Mode switching.
                InputEvent::ButtonPress(Button::Confirm) if mode == Mode::Dashboard => {
                    if let Some(app) = dashboard.selected_app() {
                        log::info!("Selected app: {}", app.title);
                    }
                },
                InputEvent::ButtonPress(Button::Start) => {
                    // F1 toggles between dashboard and terminal.
                    mode = match mode {
                        Mode::Dashboard => Mode::Terminal,
                        Mode::Terminal => Mode::Dashboard,
                    };
                },

                // Dashboard input.
                InputEvent::ButtonPress(btn) if mode == Mode::Dashboard => match btn {
                    Button::Up | Button::Down | Button::Left | Button::Right => {
                        dashboard.handle_input(btn);
                    },
                    _ => {},
                },
                InputEvent::TriggerPress(Trigger::Right) if mode == Mode::Dashboard => {
                    dashboard.next_page();
                },
                InputEvent::TriggerPress(Trigger::Left) if mode == Mode::Dashboard => {
                    dashboard.prev_page();
                },

                // Terminal input.
                InputEvent::TextInput(ch) if mode == Mode::Terminal => {
                    input_buf.push(*ch);
                },
                InputEvent::ButtonPress(Button::Confirm) if mode == Mode::Terminal => {
                    let line = input_buf.clone();
                    input_buf.clear();
                    if !line.is_empty() {
                        output_lines.push(format!("> {line}"));
                        let mut env = Environment {
                            cwd: cwd.clone(),
                            vfs: &mut vfs,
                        };
                        match cmd_reg.execute(&line, &mut env) {
                            Ok(CommandOutput::Text(text)) => {
                                for l in text.lines() {
                                    output_lines.push(l.to_string());
                                }
                            },
                            Ok(CommandOutput::Table { headers, rows }) => {
                                output_lines.push(headers.join(" | "));
                                for row in &rows {
                                    output_lines.push(row.join(" | "));
                                }
                            },
                            Ok(CommandOutput::Clear) => output_lines.clear(),
                            Ok(CommandOutput::None) => {},
                            Err(e) => output_lines.push(format!("error: {e}")),
                        }
                        cwd = env.cwd;
                    }
                    while output_lines.len() > MAX_OUTPUT_LINES {
                        output_lines.remove(0);
                    }
                },
                InputEvent::ButtonPress(Button::Square) if mode == Mode::Terminal => {
                    input_buf.pop();
                },

                _ => {},
            }
        }

        // Update SDI based on active mode.
        match mode {
            Mode::Dashboard => {
                // Show dashboard chrome, hide terminal objects.
                set_terminal_visible(&mut sdi, false);
                dashboard.update_sdi(&mut sdi);
            },
            Mode::Terminal => {
                // Hide dashboard icons, show terminal.
                hide_dashboard_objects(&mut sdi, &dashboard);
                setup_terminal_objects(&mut sdi, &output_lines, &cwd, &input_buf);
            },
        }

        backend.clear(bg_color)?;
        sdi.draw(&mut backend)?;
        backend.swap_buffers()?;
    }

    backend.shutdown()?;
    log::info!("OASIS_OS shut down cleanly");
    Ok(())
}

/// Create demo VFS content including fake apps.
fn populate_demo_vfs(vfs: &mut MemoryVfs) {
    use oasis_core::vfs::Vfs;

    vfs.mkdir("/home").unwrap();
    vfs.mkdir("/home/user").unwrap();
    vfs.mkdir("/etc").unwrap();
    vfs.mkdir("/tmp").unwrap();
    vfs.write(
        "/home/user/readme.txt",
        b"Welcome to OASIS_OS!\nType 'help' for available commands.",
    )
    .unwrap();
    vfs.write("/etc/hostname", b"oasis").unwrap();
    vfs.write("/etc/version", b"0.1.0").unwrap();

    // Create demo app directories (no real PBP files -- discovery will use
    // directory names as titles, which is the fallback behavior).
    vfs.mkdir("/apps").unwrap();
    for name in &[
        "File Manager",
        "Settings",
        "Network",
        "Terminal",
        "Music Player",
        "Photo Viewer",
        "Package Manager",
        "System Monitor",
    ] {
        vfs.mkdir(&format!("/apps/{name}")).unwrap();
    }
}

/// Hide dashboard-specific SDI objects.
fn hide_dashboard_objects(sdi: &mut SdiRegistry, dashboard: &DashboardState) {
    let per_page = dashboard.config.icons_per_page as usize;
    for i in 0..per_page {
        let name = format!("icon_{i}");
        if let Ok(obj) = sdi.get_mut(&name) {
            obj.visible = false;
        }
    }
    if let Ok(obj) = sdi.get_mut("cursor_highlight") {
        obj.visible = false;
    }
    if let Ok(obj) = sdi.get_mut("page_indicator") {
        obj.visible = false;
    }
    if let Ok(obj) = sdi.get_mut("status_title") {
        obj.visible = false;
    }
}

/// Set terminal-mode SDI objects visible/hidden.
fn set_terminal_visible(sdi: &mut SdiRegistry, visible: bool) {
    if let Ok(obj) = sdi.get_mut("terminal_bg") {
        obj.visible = visible;
    }
    for i in 0..MAX_OUTPUT_LINES {
        let name = format!("term_line_{i}");
        if let Ok(obj) = sdi.get_mut(&name) {
            obj.visible = visible;
        }
    }
    if let Ok(obj) = sdi.get_mut("term_input_bg") {
        obj.visible = visible;
    }
    if let Ok(obj) = sdi.get_mut("term_prompt") {
        obj.visible = visible;
    }
}

/// Create/update terminal-mode SDI objects.
fn setup_terminal_objects(
    sdi: &mut SdiRegistry,
    output_lines: &[String],
    cwd: &str,
    input_buf: &str,
) {
    // Terminal background.
    if !sdi.contains("terminal_bg") {
        let obj = sdi.create("terminal_bg");
        obj.x = 4;
        obj.y = 26;
        obj.w = 472;
        obj.h = 220;
        obj.color = Color::rgb(12, 12, 20);
    }
    if let Ok(obj) = sdi.get_mut("terminal_bg") {
        obj.visible = true;
    }

    // Output lines.
    for i in 0..MAX_OUTPUT_LINES {
        let name = format!("term_line_{i}");
        if !sdi.contains(&name) {
            let obj = sdi.create(&name);
            obj.x = 8;
            obj.y = 28 + (i as i32) * 16;
            obj.font_size = 12;
            obj.text_color = Color::rgb(0, 200, 0);
            obj.w = 0;
            obj.h = 0;
        }
        if let Ok(obj) = sdi.get_mut(&name) {
            obj.text = output_lines.get(i).cloned();
            obj.visible = true;
        }
    }

    // Input area.
    if !sdi.contains("term_input_bg") {
        let obj = sdi.create("term_input_bg");
        obj.x = 4;
        obj.y = 248;
        obj.w = 472;
        obj.h = 20;
        obj.color = Color::rgb(20, 20, 35);
    }
    if let Ok(obj) = sdi.get_mut("term_input_bg") {
        obj.visible = true;
    }

    if !sdi.contains("term_prompt") {
        let obj = sdi.create("term_prompt");
        obj.x = 8;
        obj.y = 250;
        obj.font_size = 12;
        obj.text_color = Color::rgb(100, 200, 255);
        obj.w = 0;
        obj.h = 0;
    }
    if let Ok(obj) = sdi.get_mut("term_prompt") {
        obj.text = Some(format!("{cwd}> {input_buf}_"));
        obj.visible = true;
    }
}
