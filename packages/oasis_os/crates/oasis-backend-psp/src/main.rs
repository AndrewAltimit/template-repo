//! PSP entry point for OASIS_OS.
//!
//! Simplified main loop for the 480x272 PSP screen: dashboard with icon grid,
//! terminal mode, status bar, bottom bar with navigation hints, and mouse
//! cursor driven by the analog stick.

#![no_std]
#![no_main]

extern crate alloc;

use alloc::format;
use alloc::string::String;
use alloc::vec;
use alloc::vec::Vec;

use oasis_backend_psp::{
    Button, Color, InputEvent, PspBackend, TextureId, CURSOR_H, CURSOR_W, SCREEN_HEIGHT,
    SCREEN_WIDTH,
};

psp::module!("OASIS_OS", 1, 0);

// ---------------------------------------------------------------------------
// UI constants
// ---------------------------------------------------------------------------

/// Dashboard grid configuration.
const GRID_COLS: usize = 6;
const GRID_X: i32 = 20;
const GRID_Y: i32 = 30;
const CELL_W: i32 = 72;
const CELL_H: i32 = 72;
const ICON_SIZE: i32 = 48;
const ICON_PAD: i32 = (CELL_W - ICON_SIZE) / 2;

/// Maximum visible terminal output lines.
const MAX_OUTPUT_LINES: usize = 28;

/// Terminal input area Y position.
const TERM_INPUT_Y: i32 = (SCREEN_HEIGHT as i32) - 32;

// ---------------------------------------------------------------------------
// App icons (procedural)
// ---------------------------------------------------------------------------

struct AppEntry {
    title: &'static str,
    icon_color: Color,
}

static APPS: &[AppEntry] = &[
    AppEntry {
        title: "Terminal",
        icon_color: Color::rgb(40, 40, 40),
    },
    AppEntry {
        title: "Files",
        icon_color: Color::rgb(200, 180, 60),
    },
    AppEntry {
        title: "Network",
        icon_color: Color::rgb(60, 120, 200),
    },
    AppEntry {
        title: "Settings",
        icon_color: Color::rgb(140, 140, 140),
    },
    AppEntry {
        title: "Music",
        icon_color: Color::rgb(200, 60, 120),
    },
    AppEntry {
        title: "Photos",
        icon_color: Color::rgb(60, 180, 120),
    },
    AppEntry {
        title: "Remote",
        icon_color: Color::rgb(100, 60, 200),
    },
    AppEntry {
        title: "Script",
        icon_color: Color::rgb(180, 120, 60),
    },
    AppEntry {
        title: "Status",
        icon_color: Color::rgb(60, 160, 160),
    },
];

// ---------------------------------------------------------------------------
// Modes
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq)]
enum Mode {
    Dashboard,
    Terminal,
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

fn psp_main() {
    psp::enable_home_button();

    let mut backend = PspBackend::new();
    backend.init();

    // Load wallpaper texture.
    let wallpaper_data = oasis_backend_psp::generate_gradient(SCREEN_WIDTH, SCREEN_HEIGHT);
    let wallpaper_tex = backend
        .load_texture(SCREEN_WIDTH, SCREEN_HEIGHT, &wallpaper_data)
        .unwrap_or(TextureId(0));

    // Load cursor texture.
    let cursor_data = oasis_backend_psp::generate_cursor_pixels();
    let cursor_tex = backend
        .load_texture(CURSOR_W, CURSOR_H, &cursor_data)
        .unwrap_or(TextureId(0));

    let mut mode = Mode::Dashboard;
    let mut selected: usize = 0;

    // Terminal state.
    let mut term_lines: Vec<String> = vec![
        String::from("OASIS_OS v0.1.0 [PSP]"),
        String::from("Type 'help' for commands. Start=toggle terminal."),
        String::new(),
    ];
    let mut term_input = String::new();

    loop {
        let events = backend.poll_events();
        for event in &events {
            match event {
                InputEvent::Quit => return,

                InputEvent::ButtonPress(Button::Start) => {
                    mode = match mode {
                        Mode::Dashboard => Mode::Terminal,
                        Mode::Terminal => Mode::Dashboard,
                    };
                }

                // -- Dashboard input --
                InputEvent::ButtonPress(Button::Up) if mode == Mode::Dashboard => {
                    if selected >= GRID_COLS {
                        selected -= GRID_COLS;
                    }
                }
                InputEvent::ButtonPress(Button::Down) if mode == Mode::Dashboard => {
                    if selected + GRID_COLS < APPS.len() {
                        selected += GRID_COLS;
                    }
                }
                InputEvent::ButtonPress(Button::Left) if mode == Mode::Dashboard => {
                    if selected > 0 {
                        selected -= 1;
                    }
                }
                InputEvent::ButtonPress(Button::Right) if mode == Mode::Dashboard => {
                    if selected + 1 < APPS.len() {
                        selected += 1;
                    }
                }
                InputEvent::ButtonPress(Button::Confirm) if mode == Mode::Dashboard => {
                    if selected < APPS.len() {
                        let app = &APPS[selected];
                        if app.title == "Terminal" {
                            mode = Mode::Terminal;
                        } else {
                            term_lines.push(format!("Launched: {}", app.title));
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Cancel) if mode == Mode::Dashboard => {
                    // Home button exits on PSP; Cancel does nothing on dashboard.
                }

                // -- Terminal input --
                InputEvent::ButtonPress(Button::Confirm) if mode == Mode::Terminal => {
                    let cmd = term_input.clone();
                    term_lines.push(format!("> {}", cmd));
                    let output = execute_command(&cmd);
                    for line in output {
                        term_lines.push(line);
                    }
                    term_input.clear();
                    // Trim history.
                    while term_lines.len() > 200 {
                        term_lines.remove(0);
                    }
                }
                InputEvent::ButtonPress(Button::Up) if mode == Mode::Terminal => {
                    term_lines.push(String::from("> help"));
                    let output = execute_command("help");
                    for line in output {
                        term_lines.push(line);
                    }
                }
                InputEvent::ButtonPress(Button::Down) if mode == Mode::Terminal => {
                    term_lines.push(String::from("> status"));
                    let output = execute_command("status");
                    for line in output {
                        term_lines.push(line);
                    }
                }

                _ => {}
            }
        }

        // -- Render --
        backend.clear(Color::BLACK);

        // Wallpaper.
        backend.blit(wallpaper_tex, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT);

        match mode {
            Mode::Dashboard => {
                draw_dashboard(&mut backend, selected);
            }
            Mode::Terminal => {
                draw_terminal(&mut backend, &term_lines, &term_input);
            }
        }

        // Status bar and bottom bar.
        oasis_backend_psp::draw_status_bar(&mut backend, "OASIS v0.1");
        let hint = match mode {
            Mode::Dashboard => "X=Select  Start=Terminal  Home=Quit",
            Mode::Terminal => "Up=help  Down=status  Start=Dashboard",
        };
        oasis_backend_psp::draw_bottom_bar(&mut backend, hint);

        // Cursor.
        let (cx, cy) = backend.cursor_pos();
        backend.blit(cursor_tex, cx, cy, CURSOR_W, CURSOR_H);

        backend.swap_buffers();
    }
}

// ---------------------------------------------------------------------------
// Dashboard rendering
// ---------------------------------------------------------------------------

fn draw_dashboard(backend: &mut PspBackend, selected: usize) {
    for (i, app) in APPS.iter().enumerate() {
        let col = (i % GRID_COLS) as i32;
        let row = (i / GRID_COLS) as i32;
        let ix = GRID_X + col * CELL_W + ICON_PAD;
        let iy = GRID_Y + row * CELL_H + 4;

        // Icon background.
        backend.fill_rect(ix, iy, ICON_SIZE as u32, ICON_SIZE as u32, app.icon_color);

        // White outline if selected.
        if i == selected {
            let sel_color = Color::WHITE;
            backend.fill_rect(ix - 2, iy - 2, (ICON_SIZE + 4) as u32, 2, sel_color);
            backend.fill_rect(
                ix - 2,
                iy + ICON_SIZE,
                (ICON_SIZE + 4) as u32,
                2,
                sel_color,
            );
            backend.fill_rect(ix - 2, iy, 2, ICON_SIZE as u32, sel_color);
            backend.fill_rect(ix + ICON_SIZE, iy, 2, ICON_SIZE as u32, sel_color);
        }

        // First letter of title centered in the icon.
        if let Some(ch) = app.title.chars().next() {
            let letter = &alloc::string::ToString::to_string(&ch);
            let text_x = ix + (ICON_SIZE - 8) / 2;
            let text_y = iy + (ICON_SIZE - 8) / 2;
            backend.draw_text(letter, text_x, text_y, 8, Color::WHITE);
        }

        // Title below icon.
        let title_x = ix + (ICON_SIZE - app.title.len() as i32 * 8) / 2;
        let title_y = iy + ICON_SIZE + 4;
        backend.draw_text(app.title, title_x, title_y, 8, Color::WHITE);
    }
}

// ---------------------------------------------------------------------------
// Terminal rendering
// ---------------------------------------------------------------------------

fn draw_terminal(backend: &mut PspBackend, lines: &[String], input: &str) {
    // Semi-transparent background.
    let bg = Color::rgba(0, 0, 0, 180);
    backend.fill_rect(0, 18, SCREEN_WIDTH, SCREEN_HEIGHT - 36, bg);

    // Output lines (bottom-aligned, most recent visible).
    let visible_start = if lines.len() > MAX_OUTPUT_LINES {
        lines.len() - MAX_OUTPUT_LINES
    } else {
        0
    };
    for (i, line) in lines[visible_start..].iter().enumerate() {
        let y = 22 + i as i32 * 9;
        if y > TERM_INPUT_Y - 12 {
            break;
        }
        backend.draw_text(line, 4, y, 8, Color::rgb(0, 255, 0));
    }

    // Input line.
    let prompt = format!("> {}_", input);
    backend.draw_text(&prompt, 4, TERM_INPUT_Y, 8, Color::rgb(0, 255, 0));
}

// ---------------------------------------------------------------------------
// Simple command interpreter (no_std, no oasis-core)
// ---------------------------------------------------------------------------

fn execute_command(cmd: &str) -> Vec<String> {
    let trimmed = cmd.trim();
    if trimmed.is_empty() {
        return vec![];
    }
    match trimmed {
        "help" => vec![
            String::from("Available commands:"),
            String::from("  help    - Show this message"),
            String::from("  status  - System status"),
            String::from("  clear   - Clear terminal"),
            String::from("  version - Show version"),
            String::from("  about   - About OASIS_OS"),
        ],
        "status" => vec![
            String::from("OASIS_OS v0.1.0 [PSP]"),
            String::from("Platform: mipsel-sony-psp"),
            String::from("Display: 480x272 RGBA8888"),
            String::from("Backend: software framebuffer"),
        ],
        "version" => vec![String::from("OASIS_OS v0.1.0")],
        "about" => vec![
            String::from("OASIS_OS -- Embeddable OS Framework"),
            String::from("PSP backend with software rendering"),
            String::from("Originally ported from C (2006-2008)"),
        ],
        "clear" => vec![], // Caller should clear the line buffer.
        _ => vec![format!("Unknown command: {}", trimmed)],
    }
}
