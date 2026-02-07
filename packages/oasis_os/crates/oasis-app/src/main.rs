//! OASIS_OS desktop entry point.
//!
//! Creates an SDL2 window, initializes the SDI scene graph with a terminal
//! UI, sets up the VFS and command interpreter, and runs the main loop.

use anyhow::Result;

use oasis_backend_sdl::SdlBackend;
use oasis_core::backend::{Color, InputBackend, SdiBackend};
use oasis_core::config::OasisConfig;
use oasis_core::input::InputEvent;
use oasis_core::sdi::SdiRegistry;
use oasis_core::terminal::{CommandOutput, CommandRegistry, Environment, register_builtins};
use oasis_core::vfs::MemoryVfs;

/// Maximum lines visible in the output area.
const MAX_OUTPUT_LINES: usize = 12;

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

    // Set up VFS with demo content.
    let mut vfs = MemoryVfs::new();
    populate_demo_vfs(&mut vfs);

    // Set up command interpreter.
    let mut cmd_reg = CommandRegistry::new();
    register_builtins(&mut cmd_reg);

    // Terminal state.
    let mut cwd = "/".to_string();
    let mut input_buf = String::new();
    let mut output_lines: Vec<String> = vec![
        "OASIS_OS v0.1.0 -- Type 'help' for commands".to_string(),
        String::new(),
    ];

    // Set up scene graph.
    let mut sdi = SdiRegistry::new();
    setup_terminal_scene(&mut sdi);

    // Main loop.
    let bg_color = Color::rgb(10, 10, 18);
    'running: loop {
        // Poll input.
        let events = backend.poll_events();
        for event in &events {
            match event {
                InputEvent::Quit => break 'running,
                InputEvent::ButtonPress(oasis_core::input::Button::Cancel) => break 'running,
                InputEvent::TextInput(ch) => {
                    input_buf.push(*ch);
                },
                InputEvent::ButtonPress(oasis_core::input::Button::Confirm) => {
                    // Execute command.
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
                            Ok(CommandOutput::Clear) => {
                                output_lines.clear();
                            },
                            Ok(CommandOutput::None) => {},
                            Err(e) => {
                                output_lines.push(format!("error: {e}"));
                            },
                        }
                        cwd = env.cwd;
                    }
                    // Trim output buffer.
                    while output_lines.len() > MAX_OUTPUT_LINES {
                        output_lines.remove(0);
                    }
                },
                InputEvent::ButtonPress(oasis_core::input::Button::Square) => {
                    // Backspace (Tab key mapped to Square in SDL backend).
                    input_buf.pop();
                },
                _ => {},
            }
        }

        // Update SDI text objects from terminal state.
        update_terminal_display(&mut sdi, &output_lines, &cwd, &input_buf);

        // Render.
        backend.clear(bg_color)?;
        sdi.draw(&mut backend)?;
        backend.swap_buffers()?;
    }

    backend.shutdown()?;
    log::info!("OASIS_OS shut down cleanly");
    Ok(())
}

/// Create demo VFS content for the terminal to browse.
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
}

/// Set up the terminal-style SDI scene.
fn setup_terminal_scene(sdi: &mut SdiRegistry) {
    // Title bar.
    {
        let obj = sdi.create("titlebar");
        obj.x = 0;
        obj.y = 0;
        obj.w = 480;
        obj.h = 20;
        obj.color = Color::rgb(30, 60, 90);
    }

    // Title text (placeholder -- draw_text is a no-op in SDL backend currently).
    {
        let obj = sdi.create("title_text");
        obj.x = 8;
        obj.y = 2;
        obj.w = 0;
        obj.h = 0;
        obj.text = Some("OASIS_OS Terminal".to_string());
        obj.font_size = 14;
        obj.text_color = Color::WHITE;
    }

    // Output area background.
    {
        let obj = sdi.create("output_bg");
        obj.x = 4;
        obj.y = 22;
        obj.w = 472;
        obj.h = 220;
        obj.color = Color::rgb(15, 15, 25);
    }

    // Output text lines (pre-create slots).
    for i in 0..MAX_OUTPUT_LINES {
        let obj = sdi.create(format!("output_{i}"));
        obj.x = 8;
        obj.y = 24 + (i as i32) * 16;
        obj.w = 0;
        obj.h = 0;
        obj.text = None;
        obj.font_size = 12;
        obj.text_color = Color::rgb(0, 200, 0);
    }

    // Input area background.
    {
        let obj = sdi.create("input_bg");
        obj.x = 4;
        obj.y = 246;
        obj.w = 472;
        obj.h = 22;
        obj.color = Color::rgb(25, 25, 40);
    }

    // Prompt + input text.
    {
        let obj = sdi.create("prompt");
        obj.x = 8;
        obj.y = 248;
        obj.w = 0;
        obj.h = 0;
        obj.text = Some("/> ".to_string());
        obj.font_size = 12;
        obj.text_color = Color::rgb(100, 200, 255);
    }
}

/// Update SDI text objects from current terminal state.
fn update_terminal_display(
    sdi: &mut SdiRegistry,
    output_lines: &[String],
    cwd: &str,
    input_buf: &str,
) {
    // Update output lines.
    for i in 0..MAX_OUTPUT_LINES {
        let name = format!("output_{i}");
        if let Ok(obj) = sdi.get_mut(&name) {
            obj.text = output_lines.get(i).cloned();
        }
    }

    // Update prompt with cwd.
    if let Ok(obj) = sdi.get_mut("prompt") {
        obj.text = Some(format!("{cwd}> {input_buf}_"));
    }
}
