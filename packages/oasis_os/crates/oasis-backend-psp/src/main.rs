//! PSP entry point for OASIS_OS.
//!
//! PSIX-style dashboard with document icons, tabbed status bar, chrome bezel
//! bottom bar, and terminal mode. Layout matches the desktop `oasis-app`
//! renderer with identical theme constants and icon composition.

#![no_std]
#![no_main]

extern crate alloc;

use alloc::format;
use alloc::string::{String, ToString};
use alloc::vec;
use alloc::vec::Vec;

use oasis_backend_psp::{
    AudioPlayer, Button, Color, FileEntry, InputEvent, PspBackend, StatusBarInfo, SystemInfo,
    TextureId, Trigger, CURSOR_H, CURSOR_W, SCREEN_HEIGHT, SCREEN_WIDTH,
};

psp::module_kernel!("OASIS_OS", 1, 0);

// ---------------------------------------------------------------------------
// Theme constants (matching oasis-core/src/theme.rs)
// ---------------------------------------------------------------------------

// Bar geometry.
const STATUSBAR_H: u32 = 24;
const TAB_ROW_H: u32 = 18;
const BOTTOMBAR_H: u32 = 24;
const BOTTOMBAR_Y: i32 = (SCREEN_HEIGHT - BOTTOMBAR_H) as i32;
const CONTENT_TOP: u32 = STATUSBAR_H + TAB_ROW_H;
const CONTENT_H: u32 = SCREEN_HEIGHT - CONTENT_TOP - BOTTOMBAR_H;

// Font metrics.
const CHAR_W: i32 = 8;

// Status bar tab layout.
const TAB_START_X: i32 = 34;
const TAB_W: i32 = 45;
const TAB_H: i32 = 16;
const TAB_GAP: i32 = 4;

// Bottom bar layout.
const PIPE_GAP: i32 = 5;
const R_HINT_W: i32 = 28;

// Icon theme.
const ICON_W: u32 = 42;
const ICON_H: u32 = 52;
const ICON_STRIPE_H: u32 = 12;
const ICON_FOLD_SIZE: u32 = 10;
const ICON_GFX_H: u32 = 22;
const ICON_GFX_PAD: u32 = 4;
const ICON_LABEL_PAD: i32 = 4;

// Dashboard grid (2 columns, 2 rows per page).
const GRID_COLS: usize = 2;
const GRID_ROWS: usize = 2;
const GRID_PAD_X: i32 = 16;
const GRID_PAD_Y: i32 = 6;
const CELL_W: i32 = 110;
const CELL_H: i32 = (CONTENT_H as i32 - 2 * GRID_PAD_Y) / GRID_ROWS as i32;
const ICONS_PER_PAGE: usize = GRID_COLS * GRID_ROWS;
const CURSOR_PAD: i32 = 3;

// Colors -- bar backgrounds.
const STATUSBAR_BG: Color = Color::rgba(0, 0, 0, 80);
const BAR_BG: Color = Color::rgba(0, 0, 0, 90);
const SEPARATOR: Color = Color::rgba(255, 255, 255, 50);

// Colors -- status bar.
const BATTERY_CLR: Color = Color::rgb(120, 255, 120);
const CATEGORY_CLR: Color = Color::rgb(220, 220, 220);
const TAB_ACTIVE_FILL: Color = Color::rgba(255, 255, 255, 30);

// Colors -- bottom bar.
const URL_CLR: Color = Color::rgb(200, 200, 200);
const USB_CLR: Color = Color::rgb(140, 140, 140);
const MEDIA_ACTIVE: Color = Color::WHITE;
const MEDIA_INACTIVE: Color = Color::rgb(170, 170, 170);
const PIPE_CLR: Color = Color::rgba(255, 255, 255, 60);
const R_HINT_CLR: Color = Color::rgba(255, 255, 255, 140);
const DOT_ACTIVE: Color = Color::rgba(255, 255, 255, 200);
const DOT_INACTIVE: Color = Color::rgba(255, 255, 255, 50);

// Colors -- chrome bezel.
const BEZEL_FILL: Color = Color::rgba(160, 170, 180, 80);
const BEZEL_TOP: Color = Color::rgba(255, 255, 255, 120);
const BEZEL_BOTTOM: Color = Color::rgba(60, 70, 80, 140);
const BEZEL_LEFT: Color = Color::rgba(255, 255, 255, 80);
const BEZEL_RIGHT: Color = Color::rgba(80, 90, 100, 120);

// Colors -- icons.
const BODY_CLR: Color = Color::rgb(250, 250, 248);
const FOLD_CLR: Color = Color::rgb(210, 210, 205);
const OUTLINE_CLR: Color = Color::rgba(255, 255, 255, 180);
const SHADOW_CLR: Color = Color::rgba(0, 0, 0, 70);
const LABEL_CLR: Color = Color::rgba(255, 255, 255, 230);
const HIGHLIGHT_CLR: Color = Color::rgba(255, 255, 255, 50);

// Terminal.
const MAX_OUTPUT_LINES: usize = 20;
const TERM_INPUT_Y: i32 = BOTTOMBAR_Y - 14;

// File manager.
const FM_VISIBLE_ROWS: usize = 18;
const FM_ROW_H: i32 = 11;
const FM_START_Y: i32 = CONTENT_TOP as i32 + 14;

// ---------------------------------------------------------------------------
// App entries (matching oasis-core FALLBACK_COLORS)
// ---------------------------------------------------------------------------

struct AppEntry {
    title: &'static str,
    color: Color,
}

static APPS: &[AppEntry] = &[
    AppEntry { title: "File Manager", color: Color::rgb(70, 130, 180) },
    AppEntry { title: "Settings",     color: Color::rgb(60, 179, 113) },
    AppEntry { title: "Network",      color: Color::rgb(218, 165, 32) },
    AppEntry { title: "Terminal",     color: Color::rgb(178, 102, 178) },
    AppEntry { title: "Music Player", color: Color::rgb(205, 92, 92) },
    AppEntry { title: "Photo Viewer", color: Color::rgb(100, 149, 237) },
    AppEntry { title: "Package Mgr",  color: Color::rgb(70, 130, 180) },
    AppEntry { title: "Sys Monitor",  color: Color::rgb(60, 179, 113) },
];

// ---------------------------------------------------------------------------
// Top tabs (cycled with L trigger)
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq)]
enum TopTab {
    Apps,
    Mods,
    Net,
}

impl TopTab {
    fn label(self) -> &'static str {
        match self {
            Self::Apps => "APPS",
            Self::Mods => "MODS",
            Self::Net => "NET",
        }
    }

    fn next(self) -> Self {
        match self {
            Self::Apps => Self::Mods,
            Self::Mods => Self::Net,
            Self::Net => Self::Apps,
        }
    }

    const ALL: &[TopTab] = &[TopTab::Apps, TopTab::Mods, TopTab::Net];
}

// ---------------------------------------------------------------------------
// Media tabs (cycled with R trigger)
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq)]
enum MediaTab {
    None,
    Audio,
    Video,
    Image,
    File,
}

impl MediaTab {
    fn next(self) -> Self {
        match self {
            Self::None => Self::Audio,
            Self::Audio => Self::Video,
            Self::Video => Self::Image,
            Self::Image => Self::File,
            Self::File => Self::None,
        }
    }

    const LABELS: &[&str] = &["AUDIO", "VIDEO", "IMAGE", "FILE"];
    const TABS: &[MediaTab] = &[MediaTab::Audio, MediaTab::Video, MediaTab::Image, MediaTab::File];
}

// ---------------------------------------------------------------------------
// Modes
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq)]
enum Mode {
    Dashboard,
    Terminal,
    FileManager,
    PhotoViewer,
    MusicPlayer,
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

fn psp_main() {
    psp::enable_home_button();

    let mut backend = PspBackend::new();
    backend.init();

    // Register exception handler (kernel mode) for crash diagnostics.
    oasis_backend_psp::register_exception_handler();

    // Set maximum clock speed (333/333/166).
    oasis_backend_psp::set_clock(333, 333, 166);

    // Query static hardware info (kernel mode, once at startup).
    let sysinfo = SystemInfo::query();
    psp::dprintln!(
        "OASIS_OS: CPU {}MHz, Bus {}MHz, ME {}MHz",
        sysinfo.cpu_mhz, sysinfo.bus_mhz, sysinfo.me_mhz,
    );

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
    let mut page: usize = 0;
    let mut top_tab = TopTab::Apps;
    let mut media_tab = MediaTab::None;

    let total_pages = if APPS.is_empty() {
        1
    } else {
        (APPS.len() + ICONS_PER_PAGE - 1) / ICONS_PER_PAGE
    };

    // Terminal state.
    let vol_info = backend.volatile_mem_info();
    let mut term_lines: Vec<String> = vec![
        String::from("OASIS_OS v0.1.0 [PSP] (kernel mode)"),
        format!(
            "CPU: {}MHz  Bus: {}MHz  ME: {}MHz",
            sysinfo.cpu_mhz, sysinfo.bus_mhz, sysinfo.me_mhz,
        ),
        if let Some((total, _)) = vol_info {
            format!("Texture cache: {} KB volatile RAM claimed", total / 1024)
        } else {
            String::from("Texture cache: main heap only (PSP-1000)")
        },
        String::from("Type 'help' for commands. Start=toggle terminal."),
        String::new(),
    ];
    let mut term_input = String::new();

    // File manager state.
    let mut fm_path = String::from("ms0:/");
    let mut fm_entries: Vec<FileEntry> = Vec::new();
    let mut fm_selected: usize = 0;
    let mut fm_scroll: usize = 0;
    let mut fm_loaded = false;

    // Photo viewer state.
    let mut pv_path = String::from("ms0:/");
    let mut pv_entries: Vec<FileEntry> = Vec::new();
    let mut pv_selected: usize = 0;
    let mut pv_scroll: usize = 0;
    let mut pv_loaded = false;
    let mut pv_viewing = false;
    let mut pv_tex: Option<TextureId> = None;
    let mut pv_img_w: u32 = 0;
    let mut pv_img_h: u32 = 0;

    // Music player state.
    let mut mp_path = String::from("ms0:/");
    let mut mp_entries: Vec<FileEntry> = Vec::new();
    let mut mp_selected: usize = 0;
    let mut mp_scroll: usize = 0;
    let mut mp_loaded = false;
    let mut mp_file_name = String::new();
    let mut audio_player = AudioPlayer::new();
    audio_player.init();

    // Register power callback for sleep/wake handling.
    oasis_backend_psp::register_power_callback();

    loop {
        // Prevent idle auto-suspend while running.
        oasis_backend_psp::power_tick();

        // Check if we resumed from sleep.
        if oasis_backend_psp::check_power_resumed() {
            term_lines.push(String::from("[Power] Resumed from sleep"));
        }
        let events = backend.poll_events();
        for event in &events {
            match event {
                InputEvent::Quit => return,

                InputEvent::ButtonPress(Button::Start) => {
                    mode = match mode {
                        Mode::Dashboard => Mode::Terminal,
                        Mode::Terminal => Mode::Dashboard,
                        Mode::FileManager => Mode::Dashboard,
                        Mode::PhotoViewer => Mode::Dashboard,
                        Mode::MusicPlayer => Mode::Dashboard,
                    };
                }

                // -- Dashboard input --
                InputEvent::ButtonPress(Button::Up) if mode == Mode::Dashboard => {
                    if selected >= GRID_COLS {
                        selected -= GRID_COLS;
                    }
                }
                InputEvent::ButtonPress(Button::Down) if mode == Mode::Dashboard => {
                    let page_start = page * ICONS_PER_PAGE;
                    let page_count =
                        APPS.len().saturating_sub(page_start).min(ICONS_PER_PAGE);
                    if selected + GRID_COLS < page_count {
                        selected += GRID_COLS;
                    }
                }
                InputEvent::ButtonPress(Button::Left) if mode == Mode::Dashboard => {
                    let page_start = page * ICONS_PER_PAGE;
                    let page_count =
                        APPS.len().saturating_sub(page_start).min(ICONS_PER_PAGE);
                    if selected == 0 {
                        selected = if page_count > 0 { page_count - 1 } else { 0 };
                    } else {
                        selected -= 1;
                    }
                }
                InputEvent::ButtonPress(Button::Right) if mode == Mode::Dashboard => {
                    let page_start = page * ICONS_PER_PAGE;
                    let page_count =
                        APPS.len().saturating_sub(page_start).min(ICONS_PER_PAGE);
                    selected = (selected + 1) % page_count.max(1);
                }
                InputEvent::ButtonPress(Button::Confirm) if mode == Mode::Dashboard => {
                    let idx = page * ICONS_PER_PAGE + selected;
                    if idx < APPS.len() {
                        let app = &APPS[idx];
                        match app.title {
                            "Terminal" => {
                                mode = Mode::Terminal;
                            }
                            "File Manager" => {
                                mode = Mode::FileManager;
                                fm_loaded = false;
                            }
                            "Photo Viewer" => {
                                mode = Mode::PhotoViewer;
                                pv_viewing = false;
                                pv_loaded = false;
                            }
                            "Music Player" => {
                                mode = Mode::MusicPlayer;
                                mp_loaded = false;
                            }
                            _ => {
                                term_lines.push(format!("Launched: {}", app.title));
                            }
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Select) if mode == Mode::Dashboard => {
                    page = (page + 1) % total_pages;
                    let page_start = page * ICONS_PER_PAGE;
                    let page_count =
                        APPS.len().saturating_sub(page_start).min(ICONS_PER_PAGE);
                    if selected >= page_count && page_count > 0 {
                        selected = page_count - 1;
                    }
                }

                // Trigger cycling.
                InputEvent::TriggerPress(Trigger::Left) if mode == Mode::Dashboard => {
                    top_tab = top_tab.next();
                }
                InputEvent::TriggerPress(Trigger::Right) if mode == Mode::Dashboard => {
                    media_tab = media_tab.next();
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

                // -- File manager input --
                InputEvent::ButtonPress(Button::Up) if mode == Mode::FileManager => {
                    if fm_selected > 0 {
                        fm_selected -= 1;
                        if fm_selected < fm_scroll {
                            fm_scroll = fm_selected;
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Down) if mode == Mode::FileManager => {
                    if fm_selected + 1 < fm_entries.len() {
                        fm_selected += 1;
                        let visible = FM_VISIBLE_ROWS;
                        if fm_selected >= fm_scroll + visible {
                            fm_scroll = fm_selected - visible + 1;
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Confirm) if mode == Mode::FileManager => {
                    // Enter directory.
                    if fm_selected < fm_entries.len() && fm_entries[fm_selected].is_dir {
                        let dir_name = fm_entries[fm_selected].name.clone();
                        if fm_path.ends_with('/') {
                            fm_path = format!("{}{}", fm_path, dir_name);
                        } else {
                            fm_path = format!("{}/{}", fm_path, dir_name);
                        }
                        fm_loaded = false;
                    }
                }
                InputEvent::ButtonPress(Button::Cancel) if mode == Mode::FileManager => {
                    // Go up one directory (pop last path segment).
                    if let Some(pos) = fm_path.rfind('/') {
                        if pos > 0 && !fm_path[..pos].ends_with(':') {
                            fm_path.truncate(pos);
                        } else if fm_path.len() > pos + 1 {
                            fm_path.truncate(pos + 1);
                        } else {
                            // Already at root, go back to dashboard.
                            mode = Mode::Dashboard;
                        }
                        fm_loaded = false;
                    } else {
                        mode = Mode::Dashboard;
                    }
                }
                InputEvent::ButtonPress(Button::Triangle) if mode == Mode::FileManager => {
                    mode = Mode::Dashboard;
                }

                // -- Photo viewer input --
                InputEvent::ButtonPress(Button::Up) if mode == Mode::PhotoViewer && !pv_viewing => {
                    if pv_selected > 0 {
                        pv_selected -= 1;
                        if pv_selected < pv_scroll {
                            pv_scroll = pv_selected;
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Down) if mode == Mode::PhotoViewer && !pv_viewing => {
                    if pv_selected + 1 < pv_entries.len() {
                        pv_selected += 1;
                        if pv_selected >= pv_scroll + FM_VISIBLE_ROWS {
                            pv_scroll = pv_selected - FM_VISIBLE_ROWS + 1;
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Confirm) if mode == Mode::PhotoViewer && !pv_viewing => {
                    if pv_selected < pv_entries.len() {
                        let entry = &pv_entries[pv_selected];
                        if entry.is_dir {
                            let dir_name = entry.name.clone();
                            if pv_path.ends_with('/') {
                                pv_path = format!("{}{}", pv_path, dir_name);
                            } else {
                                pv_path = format!("{}/{}", pv_path, dir_name);
                            }
                            pv_loaded = false;
                        } else {
                            // Load and decode JPEG.
                            let file_path = if pv_path.ends_with('/') {
                                format!("{}{}", pv_path, entry.name)
                            } else {
                                format!("{}/{}", pv_path, entry.name)
                            };
                            if let Some((w, h, rgba)) = oasis_backend_psp::decode_jpeg(
                                &oasis_backend_psp::read_file(&file_path).unwrap_or_default(),
                                SCREEN_WIDTH as i32,
                                SCREEN_HEIGHT as i32,
                            ) {
                                // Free previous texture if any.
                                if let Some(old) = pv_tex.take() {
                                    backend.destroy_texture(old);
                                }
                                pv_tex = backend.load_texture(w, h, &rgba);
                                pv_img_w = w;
                                pv_img_h = h;
                                pv_viewing = true;
                            } else {
                                term_lines.push(format!("Failed to decode: {}", entry.name));
                            }
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Cancel) if mode == Mode::PhotoViewer => {
                    if pv_viewing {
                        pv_viewing = false;
                    } else if let Some(pos) = pv_path.rfind('/') {
                        if pos > 0 && !pv_path[..pos].ends_with(':') {
                            pv_path.truncate(pos);
                        } else if pv_path.len() > pos + 1 {
                            pv_path.truncate(pos + 1);
                        } else {
                            mode = Mode::Dashboard;
                        }
                        pv_loaded = false;
                    } else {
                        mode = Mode::Dashboard;
                    }
                }
                InputEvent::ButtonPress(Button::Triangle) if mode == Mode::PhotoViewer => {
                    if pv_viewing {
                        pv_viewing = false;
                    } else {
                        mode = Mode::Dashboard;
                    }
                }

                // -- Music player input --
                InputEvent::ButtonPress(Button::Up) if mode == Mode::MusicPlayer && !audio_player.is_playing() => {
                    if mp_selected > 0 {
                        mp_selected -= 1;
                        if mp_selected < mp_scroll {
                            mp_scroll = mp_selected;
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Down) if mode == Mode::MusicPlayer && !audio_player.is_playing() => {
                    if mp_selected + 1 < mp_entries.len() {
                        mp_selected += 1;
                        if mp_selected >= mp_scroll + FM_VISIBLE_ROWS {
                            mp_scroll = mp_selected - FM_VISIBLE_ROWS + 1;
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Confirm) if mode == Mode::MusicPlayer => {
                    if audio_player.is_playing() {
                        // Toggle pause.
                        audio_player.toggle_pause();
                    } else if mp_selected < mp_entries.len() {
                        let entry = &mp_entries[mp_selected];
                        if entry.is_dir {
                            let dir_name = entry.name.clone();
                            if mp_path.ends_with('/') {
                                mp_path = format!("{}{}", mp_path, dir_name);
                            } else {
                                mp_path = format!("{}/{}", mp_path, dir_name);
                            }
                            mp_loaded = false;
                        } else {
                            // Load and play MP3.
                            let file_path = if mp_path.ends_with('/') {
                                format!("{}{}", mp_path, entry.name)
                            } else {
                                format!("{}/{}", mp_path, entry.name)
                            };
                            mp_file_name = entry.name.clone();
                            if audio_player.load_and_play(&file_path) {
                                term_lines.push(format!("Playing: {}", entry.name));
                            } else {
                                term_lines.push(format!("Failed to play: {}", entry.name));
                            }
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Square) if mode == Mode::MusicPlayer => {
                    // Stop playback.
                    audio_player.stop();
                }
                InputEvent::ButtonPress(Button::Cancel) if mode == Mode::MusicPlayer => {
                    if audio_player.is_playing() {
                        audio_player.stop();
                    }
                    if let Some(pos) = mp_path.rfind('/') {
                        if pos > 0 && !mp_path[..pos].ends_with(':') {
                            mp_path.truncate(pos);
                        } else if mp_path.len() > pos + 1 {
                            mp_path.truncate(pos + 1);
                        } else {
                            mode = Mode::Dashboard;
                        }
                        mp_loaded = false;
                    } else {
                        mode = Mode::Dashboard;
                    }
                }
                InputEvent::ButtonPress(Button::Triangle) if mode == Mode::MusicPlayer => {
                    mode = Mode::Dashboard;
                    // Audio keeps playing in background.
                }

                _ => {}
            }
        }

        // -- Render --
        let status = StatusBarInfo::poll();

        backend.clear(Color::BLACK);

        // Wallpaper.
        backend.blit(wallpaper_tex, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT);

        // Lazy-load directory entries for browser modes.
        if mode == Mode::FileManager && !fm_loaded {
            fm_entries = oasis_backend_psp::list_directory(&fm_path);
            fm_selected = 0;
            fm_scroll = 0;
            fm_loaded = true;
        }
        if mode == Mode::PhotoViewer && !pv_loaded && !pv_viewing {
            let all = oasis_backend_psp::list_directory(&pv_path);
            pv_entries = all
                .into_iter()
                .filter(|e| {
                    e.is_dir || {
                        let lower: String = e.name.chars().map(|c| c.to_ascii_lowercase()).collect();
                        lower.ends_with(".jpg") || lower.ends_with(".jpeg")
                    }
                })
                .collect();
            pv_selected = 0;
            pv_scroll = 0;
            pv_loaded = true;
        }
        if mode == Mode::MusicPlayer && !mp_loaded && !audio_player.is_playing() {
            let all = oasis_backend_psp::list_directory(&mp_path);
            mp_entries = all
                .into_iter()
                .filter(|e| {
                    e.is_dir || {
                        let lower: String = e.name.chars().map(|c| c.to_ascii_lowercase()).collect();
                        lower.ends_with(".mp3")
                    }
                })
                .collect();
            mp_selected = 0;
            mp_scroll = 0;
            mp_loaded = true;
        }

        // Pump audio decode each frame.
        audio_player.update();

        match mode {
            Mode::Dashboard => {
                draw_dashboard(&mut backend, selected, page);
            }
            Mode::Terminal => {
                draw_terminal(&mut backend, &term_lines, &term_input);
            }
            Mode::FileManager => {
                draw_file_manager(
                    &mut backend,
                    &fm_path,
                    &fm_entries,
                    fm_selected,
                    fm_scroll,
                );
            }
            Mode::PhotoViewer => {
                if pv_viewing {
                    draw_photo_view(&mut backend, pv_tex, pv_img_w, pv_img_h);
                } else {
                    draw_photo_browser(
                        &mut backend,
                        &pv_path,
                        &pv_entries,
                        pv_selected,
                        pv_scroll,
                    );
                }
            }
            Mode::MusicPlayer => {
                if audio_player.is_playing() {
                    draw_music_player(
                        &mut backend,
                        &mp_file_name,
                        &audio_player,
                    );
                } else {
                    draw_music_browser(
                        &mut backend,
                        &mp_path,
                        &mp_entries,
                        mp_selected,
                        mp_scroll,
                    );
                }
            }
        }

        // Status bar + bottom bar (always visible, drawn on top).
        draw_status_bar(&mut backend, top_tab, &status);
        draw_bottom_bar(&mut backend, media_tab, page, total_pages);

        // Cursor.
        let (cx, cy) = backend.cursor_pos();
        backend.blit(cursor_tex, cx, cy, CURSOR_W, CURSOR_H);

        backend.swap_buffers();
    }
}

// ---------------------------------------------------------------------------
// Dashboard rendering
// ---------------------------------------------------------------------------

fn draw_dashboard(backend: &mut PspBackend, selected: usize, page: usize) {
    let page_start = page * ICONS_PER_PAGE;
    let page_end = (page_start + ICONS_PER_PAGE).min(APPS.len());
    let page_count = page_end - page_start;

    for i in 0..page_count {
        let app = &APPS[page_start + i];
        let col = (i % GRID_COLS) as i32;
        let row = (i / GRID_COLS) as i32;
        let cell_x = GRID_PAD_X + col * CELL_W;
        let cell_y = CONTENT_TOP as i32 + GRID_PAD_Y + row * CELL_H;
        let ix = cell_x + (CELL_W - ICON_W as i32) / 2;
        let iy = cell_y + 4;

        draw_icon(backend, app, ix, iy);

        // Label below icon (left-aligned at cell edge).
        let label_y = iy + ICON_H as i32 + ICON_LABEL_PAD;
        backend.draw_text(app.title, cell_x, label_y, 8, LABEL_CLR);
    }

    // Cursor highlight around selected icon.
    if page_count > 0 && selected < page_count {
        let sel_col = (selected % GRID_COLS) as i32;
        let sel_row = (selected / GRID_COLS) as i32;
        let cell_x = GRID_PAD_X + sel_col * CELL_W;
        let cell_y = CONTENT_TOP as i32 + GRID_PAD_Y + sel_row * CELL_H;
        let ix = cell_x + (CELL_W - ICON_W as i32) / 2;
        let iy = cell_y + 4;
        backend.fill_rect(
            ix - CURSOR_PAD,
            iy - CURSOR_PAD,
            ICON_W + CURSOR_PAD as u32 * 2,
            ICON_H + CURSOR_PAD as u32 * 2,
            HIGHLIGHT_CLR,
        );
    }
}

/// Draw a PSIX document-style icon with 6 layers:
/// shadow, outline, body, stripe, fold, app graphic.
fn draw_icon(backend: &mut PspBackend, app: &AppEntry, ix: i32, iy: i32) {
    // 1. Drop shadow (offset +2, +3).
    backend.fill_rect(ix + 2, iy + 3, ICON_W + 2, ICON_H + 1, SHADOW_CLR);

    // 2. White outline (-1, -1, +2, +2).
    backend.fill_rect(ix - 1, iy - 1, ICON_W + 2, ICON_H + 2, OUTLINE_CLR);

    // 3. Document body (white paper).
    backend.fill_rect(ix, iy, ICON_W, ICON_H, BODY_CLR);

    // 4. Colored stripe at top (width = ICON_W - FOLD_SIZE).
    backend.fill_rect(ix, iy, ICON_W - ICON_FOLD_SIZE, ICON_STRIPE_H, app.color);

    // 5. Folded corner (top-right).
    backend.fill_rect(
        ix + ICON_W as i32 - ICON_FOLD_SIZE as i32,
        iy,
        ICON_FOLD_SIZE,
        ICON_FOLD_SIZE,
        FOLD_CLR,
    );

    // 6. App graphic (vibrant accent color).
    let gfx_w = ICON_W - 2 * ICON_GFX_PAD;
    let c = app.color;
    let gfx_color = Color::rgba(
        c.r.saturating_add(30),
        c.g.saturating_add(10),
        c.b.saturating_add(30),
        200,
    );
    backend.fill_rect(
        ix + ICON_GFX_PAD as i32,
        iy + ICON_STRIPE_H as i32 + 3,
        gfx_w,
        ICON_GFX_H,
        gfx_color,
    );
}

// ---------------------------------------------------------------------------
// Status bar rendering
// ---------------------------------------------------------------------------

fn draw_status_bar(backend: &mut PspBackend, active_tab: TopTab, status: &StatusBarInfo) {
    // Semi-transparent background.
    backend.fill_rect(0, 0, SCREEN_WIDTH, STATUSBAR_H, STATUSBAR_BG);

    // Separator line at bottom of status bar.
    backend.fill_rect(0, STATUSBAR_H as i32 - 1, SCREEN_WIDTH, 1, SEPARATOR);

    // Battery / power info (left side).
    let bat_label = if status.battery_percent >= 0 {
        if status.battery_charging {
            format!("CHG {}%", status.battery_percent)
        } else {
            format!("BAT {}%", status.battery_percent)
        }
    } else if status.ac_power {
        String::from("AC")
    } else {
        String::from("---")
    };
    let bat_color = if status.battery_charging || status.ac_power {
        BATTERY_CLR
    } else if status.battery_percent < 20 {
        Color::rgb(255, 80, 80)
    } else {
        BATTERY_CLR
    };
    backend.draw_text(&bat_label, 6, 7, 8, bat_color);

    // WiFi + USB indicators (center-left).
    let wifi_label = if status.wifi_on { "WiFi" } else { "----" };
    let wifi_color = if status.wifi_on {
        Color::rgb(100, 200, 255)
    } else {
        Color::rgb(100, 100, 100)
    };
    backend.draw_text(wifi_label, 96, 7, 8, wifi_color);

    let usb_color = if status.usb_connected {
        Color::rgb(200, 200, 200)
    } else {
        Color::rgb(100, 100, 100)
    };
    backend.draw_text("USB", 140, 7, 8, usb_color);

    // Version label (center).
    backend.draw_text("OASIS v0.1", 200, 7, 8, Color::WHITE);

    // Real time clock (right side).
    let time_label = format!("{:02}:{:02}", status.hour, status.minute);
    backend.draw_text(&time_label, 420, 7, 8, Color::WHITE);

    // "OSS" category label before tabs.
    backend.draw_text("OSS", 6, STATUSBAR_H as i32 + 3, 8, CATEGORY_CLR);

    // Tab row with outlined borders.
    let tab_y = STATUSBAR_H as i32;
    for (i, tab) in TopTab::ALL.iter().enumerate() {
        let x = TAB_START_X + (i as i32) * (TAB_W + TAB_GAP);
        let alpha = if *tab == active_tab { 180u8 } else { 60u8 };
        let border = Color::rgba(255, 255, 255, alpha);

        // Four border edges.
        backend.fill_rect(x, tab_y, TAB_W as u32, 1, border);
        backend.fill_rect(x, tab_y + TAB_H - 1, TAB_W as u32, 1, border);
        backend.fill_rect(x, tab_y, 1, TAB_H as u32, border);
        backend.fill_rect(x + TAB_W - 1, tab_y, 1, TAB_H as u32, border);

        // Active tab fill.
        if *tab == active_tab {
            backend.fill_rect(
                x + 1,
                tab_y + 1,
                (TAB_W - 2) as u32,
                (TAB_H - 2) as u32,
                TAB_ACTIVE_FILL,
            );
        }

        // Tab label (centered in box).
        let label = tab.label();
        let text_w = label.len() as i32 * CHAR_W;
        let tx = x + (TAB_W - text_w) / 2;
        let text_color = if *tab == active_tab {
            Color::WHITE
        } else {
            Color::rgb(160, 160, 160)
        };
        backend.draw_text(label, tx.max(x + 2), tab_y + 4, 8, text_color);
    }
}

// ---------------------------------------------------------------------------
// Bottom bar rendering
// ---------------------------------------------------------------------------

fn draw_bottom_bar(
    backend: &mut PspBackend,
    active_media: MediaTab,
    current_page: usize,
    total_pages: usize,
) {
    let bar_y = BOTTOMBAR_Y;

    // Semi-transparent background.
    backend.fill_rect(0, bar_y, SCREEN_WIDTH, BOTTOMBAR_H, BAR_BG);

    // Separator line at top of bottom bar.
    backend.fill_rect(0, bar_y, SCREEN_WIDTH, 1, SEPARATOR);

    // Chrome bezel around URL area.
    let url_bx = 2i32;
    let url_bw = 190u32;
    let bz_y = bar_y + 2;
    let bz_h = BOTTOMBAR_H - 4;
    draw_chrome_bezel(backend, url_bx, bz_y, url_bw, bz_h);

    // URL text.
    backend.draw_text("HTTP://OASIS.LOCAL", 8, bar_y + 8, 8, URL_CLR);

    // USB indicator (between bezels).
    let usb_x = url_bx + url_bw as i32 + 14;
    backend.draw_text("USB", usb_x, bar_y + 8, 8, USB_CLR);

    // Page dots.
    let dots_x = usb_x + 36;
    let max_dots = 4usize;
    for i in 0..total_pages.min(max_dots) {
        let color = if i == current_page {
            DOT_ACTIVE
        } else {
            DOT_INACTIVE
        };
        backend.fill_rect(dots_x + (i as i32) * 12, bar_y + 9, 6, 6, color);
    }

    // Media category tabs with pipe separators.
    let labels_w: i32 = MediaTab::LABELS.iter().map(|l| l.len() as i32 * CHAR_W).sum();
    let pipes_w = (MediaTab::LABELS.len() as i32 - 1) * (PIPE_GAP * 2 + CHAR_W);
    let total_w = labels_w + pipes_w;
    let tabs_x = SCREEN_WIDTH as i32 - total_w - R_HINT_W - 8;

    // Chrome bezel around tab group.
    let tab_bx = tabs_x - 6;
    let tab_bw = (total_w + R_HINT_W + 14) as u32;
    draw_chrome_bezel(backend, tab_bx, bz_y, tab_bw, bz_h);

    let mut cx = tabs_x;
    for (i, label) in MediaTab::LABELS.iter().enumerate() {
        let tab = MediaTab::TABS[i];
        let color = if tab == active_media {
            MEDIA_ACTIVE
        } else {
            MEDIA_INACTIVE
        };
        backend.draw_text(label, cx, bar_y + 8, 8, color);
        cx += label.len() as i32 * CHAR_W;

        // Pipe separator (except after last tab).
        if i < MediaTab::LABELS.len() - 1 {
            cx += PIPE_GAP;
            backend.draw_text("|", cx, bar_y + 8, 8, PIPE_CLR);
            cx += CHAR_W + PIPE_GAP;
        }
    }

    // "R>" shoulder button hint.
    backend.draw_text("R>", SCREEN_WIDTH as i32 - R_HINT_W, bar_y + 8, 8, R_HINT_CLR);
}

/// Draw a chrome/metallic bezel (fill + 4 edges).
fn draw_chrome_bezel(backend: &mut PspBackend, x: i32, y: i32, w: u32, h: u32) {
    backend.fill_rect(x, y, w, h, BEZEL_FILL);
    backend.fill_rect(x, y, w, 1, BEZEL_TOP);
    backend.fill_rect(x, y + h as i32 - 1, w, 1, BEZEL_BOTTOM);
    backend.fill_rect(x, y, 1, h, BEZEL_LEFT);
    backend.fill_rect(x + w as i32 - 1, y, 1, h, BEZEL_RIGHT);
}

// ---------------------------------------------------------------------------
// Terminal rendering
// ---------------------------------------------------------------------------

fn draw_terminal(backend: &mut PspBackend, lines: &[String], input: &str) {
    // Semi-transparent background over content area.
    let bg = Color::rgba(0, 0, 0, 180);
    backend.fill_rect(0, CONTENT_TOP as i32, SCREEN_WIDTH, CONTENT_H, bg);

    // Output lines (bottom-aligned, most recent visible).
    let visible_start = if lines.len() > MAX_OUTPUT_LINES {
        lines.len() - MAX_OUTPUT_LINES
    } else {
        0
    };
    for (i, line) in lines[visible_start..].iter().enumerate() {
        let y = CONTENT_TOP as i32 + 4 + i as i32 * 9;
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
// File manager rendering
// ---------------------------------------------------------------------------

fn draw_file_manager(
    backend: &mut PspBackend,
    path: &str,
    entries: &[FileEntry],
    selected: usize,
    scroll: usize,
) {
    // Semi-transparent background over content area.
    let bg = Color::rgba(0, 0, 0, 200);
    backend.fill_rect(0, CONTENT_TOP as i32, SCREEN_WIDTH, CONTENT_H, bg);

    // Path header.
    backend.draw_text(path, 4, CONTENT_TOP as i32 + 3, 8, Color::rgb(100, 200, 255));

    // Column headers.
    let header_y = CONTENT_TOP as i32 + 3;
    backend.draw_text("SIZE", 400, header_y, 8, Color::rgb(160, 160, 160));

    // Separator.
    backend.fill_rect(
        0,
        FM_START_Y - 2,
        SCREEN_WIDTH,
        1,
        Color::rgba(255, 255, 255, 40),
    );

    if entries.is_empty() {
        backend.draw_text("(empty directory)", 8, FM_START_Y, 8, Color::rgb(140, 140, 140));
        return;
    }

    let end = (scroll + FM_VISIBLE_ROWS).min(entries.len());
    for i in scroll..end {
        let entry = &entries[i];
        let row = (i - scroll) as i32;
        let y = FM_START_Y + row * FM_ROW_H;

        // Selection highlight.
        if i == selected {
            backend.fill_rect(0, y - 1, SCREEN_WIDTH, FM_ROW_H as u32, Color::rgba(80, 120, 200, 100));
        }

        // Icon prefix: [D] for dirs, [F] for files.
        let (prefix, prefix_clr) = if entry.is_dir {
            ("[D]", Color::rgb(255, 220, 80))
        } else {
            ("[F]", Color::rgb(180, 180, 180))
        };
        backend.draw_text(prefix, 4, y, 8, prefix_clr);

        // Name (truncated to fit).
        let name_color = if entry.is_dir {
            Color::rgb(120, 220, 255)
        } else {
            Color::WHITE
        };
        let max_name_chars = 44;
        let display_name = if entry.name.len() > max_name_chars {
            let truncated: String = entry.name.chars().take(max_name_chars - 2).collect();
            format!("{}..", truncated)
        } else {
            entry.name.clone()
        };
        backend.draw_text(&display_name, 32, y, 8, name_color);

        // Size (right-aligned, files only).
        if !entry.is_dir {
            let size_str = oasis_backend_psp::format_size(entry.size);
            let size_x = 480 - (size_str.len() as i32 * 8) - 4;
            backend.draw_text(&size_str, size_x, y, 8, Color::rgb(180, 180, 180));
        }
    }

    // Scroll indicator.
    if entries.len() > FM_VISIBLE_ROWS {
        let ratio = selected as f32 / (entries.len() - 1).max(1) as f32;
        let track_h = CONTENT_H as i32 - 16;
        let dot_y = FM_START_Y + (ratio * track_h as f32) as i32;
        backend.fill_rect(SCREEN_WIDTH as i32 - 4, dot_y, 3, 8, Color::rgba(255, 255, 255, 120));
    }
}

// ---------------------------------------------------------------------------
// Photo viewer rendering
// ---------------------------------------------------------------------------

/// Draw the photo file browser (same layout as file manager, filtered for images).
fn draw_photo_browser(
    backend: &mut PspBackend,
    path: &str,
    entries: &[FileEntry],
    selected: usize,
    scroll: usize,
) {
    let bg = Color::rgba(0, 0, 0, 200);
    backend.fill_rect(0, CONTENT_TOP as i32, SCREEN_WIDTH, CONTENT_H, bg);

    // Title.
    backend.draw_text("PHOTO VIEWER", 4, CONTENT_TOP as i32 + 3, 8, Color::rgb(100, 149, 237));
    backend.draw_text(path, 110, CONTENT_TOP as i32 + 3, 8, Color::rgb(160, 160, 160));

    backend.fill_rect(0, FM_START_Y - 2, SCREEN_WIDTH, 1, Color::rgba(255, 255, 255, 40));

    if entries.is_empty() {
        backend.draw_text("No images found (.jpg/.jpeg)", 8, FM_START_Y, 8, Color::rgb(140, 140, 140));
        return;
    }

    let end = (scroll + FM_VISIBLE_ROWS).min(entries.len());
    for i in scroll..end {
        let entry = &entries[i];
        let row = (i - scroll) as i32;
        let y = FM_START_Y + row * FM_ROW_H;

        if i == selected {
            backend.fill_rect(0, y - 1, SCREEN_WIDTH, FM_ROW_H as u32, Color::rgba(80, 120, 200, 100));
        }

        let (prefix, prefix_clr) = if entry.is_dir {
            ("[D]", Color::rgb(255, 220, 80))
        } else {
            ("[I]", Color::rgb(100, 200, 255))
        };
        backend.draw_text(prefix, 4, y, 8, prefix_clr);

        let name_color = if entry.is_dir {
            Color::rgb(120, 220, 255)
        } else {
            Color::WHITE
        };
        let max_name_chars = 44;
        let display_name = if entry.name.len() > max_name_chars {
            let truncated: String = entry.name.chars().take(max_name_chars - 2).collect();
            format!("{}..", truncated)
        } else {
            entry.name.clone()
        };
        backend.draw_text(&display_name, 32, y, 8, name_color);

        if !entry.is_dir {
            let size_str = oasis_backend_psp::format_size(entry.size);
            let size_x = 480 - (size_str.len() as i32 * 8) - 4;
            backend.draw_text(&size_str, size_x, y, 8, Color::rgb(180, 180, 180));
        }
    }
}

/// Display a decoded photo scaled to fit the screen.
fn draw_photo_view(
    backend: &mut PspBackend,
    tex: Option<TextureId>,
    img_w: u32,
    img_h: u32,
) {
    backend.fill_rect(0, CONTENT_TOP as i32, SCREEN_WIDTH, CONTENT_H, Color::BLACK);

    if let Some(t) = tex {
        // Scale to fit within content area, preserving aspect ratio.
        let max_w = SCREEN_WIDTH;
        let max_h = CONTENT_H;
        let scale_w = max_w as f32 / img_w as f32;
        let scale_h = max_h as f32 / img_h as f32;
        let scale = if scale_w < scale_h { scale_w } else { scale_h };
        let draw_w = (img_w as f32 * scale) as u32;
        let draw_h = (img_h as f32 * scale) as u32;
        let draw_x = ((max_w - draw_w) / 2) as i32;
        let draw_y = CONTENT_TOP as i32 + ((max_h - draw_h) / 2) as i32;

        backend.blit(t, draw_x, draw_y, draw_w, draw_h);
    } else {
        backend.draw_text("Failed to load image", 160, 130, 8, Color::rgb(255, 80, 80));
    }
}

// ---------------------------------------------------------------------------
// Music player rendering
// ---------------------------------------------------------------------------

/// Draw the music file browser.
fn draw_music_browser(
    backend: &mut PspBackend,
    path: &str,
    entries: &[FileEntry],
    selected: usize,
    scroll: usize,
) {
    let bg = Color::rgba(0, 0, 0, 200);
    backend.fill_rect(0, CONTENT_TOP as i32, SCREEN_WIDTH, CONTENT_H, bg);

    // Title.
    backend.draw_text("MUSIC PLAYER", 4, CONTENT_TOP as i32 + 3, 8, Color::rgb(205, 92, 92));
    backend.draw_text(path, 110, CONTENT_TOP as i32 + 3, 8, Color::rgb(160, 160, 160));

    backend.fill_rect(0, FM_START_Y - 2, SCREEN_WIDTH, 1, Color::rgba(255, 255, 255, 40));

    if entries.is_empty() {
        backend.draw_text("No MP3 files found", 8, FM_START_Y, 8, Color::rgb(140, 140, 140));
        return;
    }

    let end = (scroll + FM_VISIBLE_ROWS).min(entries.len());
    for i in scroll..end {
        let entry = &entries[i];
        let row = (i - scroll) as i32;
        let y = FM_START_Y + row * FM_ROW_H;

        if i == selected {
            backend.fill_rect(0, y - 1, SCREEN_WIDTH, FM_ROW_H as u32, Color::rgba(200, 80, 80, 100));
        }

        let (prefix, prefix_clr) = if entry.is_dir {
            ("[D]", Color::rgb(255, 220, 80))
        } else {
            ("[M]", Color::rgb(205, 92, 92))
        };
        backend.draw_text(prefix, 4, y, 8, prefix_clr);

        let name_color = if entry.is_dir {
            Color::rgb(120, 220, 255)
        } else {
            Color::WHITE
        };
        let max_name_chars = 44;
        let display_name = if entry.name.len() > max_name_chars {
            let truncated: String = entry.name.chars().take(max_name_chars - 2).collect();
            format!("{}..", truncated)
        } else {
            entry.name.clone()
        };
        backend.draw_text(&display_name, 32, y, 8, name_color);

        if !entry.is_dir {
            let size_str = oasis_backend_psp::format_size(entry.size);
            let size_x = 480 - (size_str.len() as i32 * 8) - 4;
            backend.draw_text(&size_str, size_x, y, 8, Color::rgb(180, 180, 180));
        }
    }
}

/// Draw the now-playing music player UI.
fn draw_music_player(
    backend: &mut PspBackend,
    file_name: &str,
    player: &AudioPlayer,
) {
    let bg = Color::rgba(0, 0, 0, 210);
    backend.fill_rect(0, CONTENT_TOP as i32, SCREEN_WIDTH, CONTENT_H, bg);

    let cx = SCREEN_WIDTH as i32 / 2;
    let title_color = Color::rgb(255, 200, 200);
    let info_color = Color::rgb(180, 180, 180);

    // Album art placeholder (colored rectangle).
    let art_size: u32 = 80;
    let art_x = cx - art_size as i32 / 2;
    let art_y = CONTENT_TOP as i32 + 20;
    backend.fill_rect(art_x, art_y, art_size, art_size, Color::rgb(205, 92, 92));
    backend.fill_rect(art_x + 2, art_y + 2, art_size - 4, art_size - 4, Color::rgb(60, 30, 30));
    backend.draw_text("MP3", art_x + 22, art_y + 34, 8, Color::rgb(205, 92, 92));

    // Track name (centered, truncated).
    let max_chars = 50;
    let display_name = if file_name.len() > max_chars {
        let truncated: String = file_name.chars().take(max_chars - 2).collect();
        format!("{}..", truncated)
    } else {
        file_name.to_string()
    };
    let name_x = cx - (display_name.len() as i32 * 8) / 2;
    backend.draw_text(&display_name, name_x, art_y + art_size as i32 + 12, 8, title_color);

    // Format info.
    let info = format!(
        "{}Hz  {}kbps  {}ch",
        player.sample_rate,
        player.bitrate,
        player.channels,
    );
    let info_x = cx - (info.len() as i32 * 8) / 2;
    backend.draw_text(&info, info_x, art_y + art_size as i32 + 26, 8, info_color);

    // Playback status.
    let status = if player.is_paused() { "PAUSED" } else { "PLAYING" };
    let status_clr = if player.is_paused() {
        Color::rgb(255, 200, 80)
    } else {
        Color::rgb(120, 255, 120)
    };
    let status_x = cx - (status.len() as i32 * 8) / 2;
    backend.draw_text(status, status_x, art_y + art_size as i32 + 44, 8, status_clr);

    // Controls hint.
    let hint = "X:Pause  []:Stop  O:Back";
    let hint_x = cx - (hint.len() as i32 * 8) / 2;
    backend.draw_text(hint, hint_x, BOTTOMBAR_Y - 16, 8, Color::rgb(140, 140, 140));
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
            String::from("  help       - Show this message"),
            String::from("  status     - System status"),
            String::from("  ls [path]  - List directory"),
            String::from("  clock      - Show/set CPU frequency"),
            String::from("  clock 333  - Set max (333/333/166)"),
            String::from("  clock 266  - Set balanced (266/266/133)"),
            String::from("  clock 222  - Set power save (222/222/111)"),
            String::from("  clear      - Clear terminal"),
            String::from("  version    - Show version"),
            String::from("  about      - About OASIS_OS"),
        ],
        "status" => {
            let status = StatusBarInfo::poll();
            let bat = if status.battery_percent >= 0 {
                format!("Battery: {}%{}", status.battery_percent,
                    if status.battery_charging { " (charging)" } else { "" })
            } else {
                String::from("Battery: N/A")
            };
            vec![
                String::from("OASIS_OS v0.1.0 [PSP] (kernel mode)"),
                String::from("Platform: mipsel-sony-psp"),
                String::from("Display: 480x272 RGBA8888"),
                String::from("Backend: sceGu hardware"),
                format!("CPU: {}MHz  Bus: {}MHz",
                    unsafe { psp::sys::scePowerGetCpuClockFrequency() },
                    unsafe { psp::sys::scePowerGetBusClockFrequency() }),
                bat,
                format!("WiFi: {}  USB: {}",
                    if status.wifi_on { "ON" } else { "OFF" },
                    if status.usb_connected { "connected" } else { "---" }),
                format!("Time: {:02}:{:02}", status.hour, status.minute),
            ]
        }
        "clock" => {
            let cpu = unsafe { psp::sys::scePowerGetCpuClockFrequency() };
            let bus = unsafe { psp::sys::scePowerGetBusClockFrequency() };
            vec![format!("Current: CPU {}MHz, Bus {}MHz", cpu, bus)]
        }
        "clock 333" => {
            let ret = oasis_backend_psp::set_clock(333, 333, 166);
            if ret >= 0 {
                vec![String::from("Clock set: 333/333/166 (max performance)")]
            } else {
                vec![format!("Failed to set clock: {}", ret)]
            }
        }
        "clock 266" => {
            let ret = oasis_backend_psp::set_clock(266, 266, 133);
            if ret >= 0 {
                vec![String::from("Clock set: 266/266/133 (balanced)")]
            } else {
                vec![format!("Failed to set clock: {}", ret)]
            }
        }
        "clock 222" => {
            let ret = oasis_backend_psp::set_clock(222, 222, 111);
            if ret >= 0 {
                vec![String::from("Clock set: 222/222/111 (power save)")]
            } else {
                vec![format!("Failed to set clock: {}", ret)]
            }
        }
        _ if trimmed.starts_with("ls") => {
            let path = trimmed.strip_prefix("ls").unwrap().trim();
            let dir = if path.is_empty() { "ms0:/" } else { path };
            let entries = oasis_backend_psp::list_directory(dir);
            if entries.is_empty() {
                vec![format!("(empty or cannot open: {})", dir)]
            } else {
                let mut out = vec![format!("{}  ({} entries)", dir, entries.len())];
                for e in entries.iter().take(30) {
                    if e.is_dir {
                        out.push(format!("  [D] {}/", e.name));
                    } else {
                        out.push(format!("  [F] {}  {}", e.name, oasis_backend_psp::format_size(e.size)));
                    }
                }
                if entries.len() > 30 {
                    out.push(format!("  ... and {} more", entries.len() - 30));
                }
                out
            }
        }
        "version" => vec![String::from("OASIS_OS v0.1.0")],
        "about" => vec![
            String::from("OASIS_OS -- Embeddable OS Framework"),
            String::from("PSP backend with GU rendering (kernel mode)"),
        ],
        "clear" => vec![],
        _ => vec![format!("Unknown command: {}", trimmed)],
    }
}
