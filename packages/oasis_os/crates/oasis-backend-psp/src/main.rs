//! PSP entry point for OASIS_OS.
//!
//! PSIX-style dashboard with document icons, tabbed status bar, chrome bezel
//! bottom bar, terminal mode, and windowed desktop mode with floating windows
//! managed by the oasis-core WindowManager.
//!
//! Audio playback and file I/O run on background threads to prevent frame drops.

#![feature(restricted_std)]
#![no_main]

use oasis_backend_psp::{
    AudioHandle, Button, Color, FileEntry, InputEvent, IoRequest, IoResponse, PspBackend,
    SdiBackend, SdiRegistry, StatusBarInfo, SystemInfo, TextureId, Trigger, WindowConfig,
    WindowManager, WindowType, WmEvent, WorkerCmd, CURSOR_H, CURSOR_W, SCREEN_HEIGHT,
    SCREEN_WIDTH,
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

// Desktop mode taskbar.
const TASKBAR_H: u32 = 14;

// ---------------------------------------------------------------------------
// App entries (matching oasis-core FALLBACK_COLORS)
// ---------------------------------------------------------------------------

struct AppEntry {
    id: &'static str,
    title: &'static str,
    color: Color,
}

static APPS: &[AppEntry] = &[
    AppEntry { id: "filemgr",  title: "File Manager", color: Color::rgb(70, 130, 180) },
    AppEntry { id: "settings", title: "Settings",     color: Color::rgb(60, 179, 113) },
    AppEntry { id: "network",  title: "Network",      color: Color::rgb(218, 165, 32) },
    AppEntry { id: "terminal", title: "Terminal",     color: Color::rgb(178, 102, 178) },
    AppEntry { id: "music",    title: "Music Player", color: Color::rgb(205, 92, 92) },
    AppEntry { id: "photos",   title: "Photo Viewer", color: Color::rgb(100, 149, 237) },
    AppEntry { id: "packages", title: "Package Mgr",  color: Color::rgb(70, 130, 180) },
    AppEntry { id: "sysmon",   title: "Sys Monitor",  color: Color::rgb(60, 179, 113) },
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
// App modes (Classic = full-screen, Desktop = windowed WM)
// ---------------------------------------------------------------------------

#[derive(Clone, Copy, PartialEq)]
enum AppMode {
    /// Classic PSIX full-screen dashboard (existing behavior, default).
    Classic,
    /// Windowed desktop mode with floating windows managed by WM.
    Desktop,
}

// Classic sub-modes (within AppMode::Classic).
#[derive(Clone, Copy, PartialEq)]
enum ClassicView {
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
        .load_texture_inner(SCREEN_WIDTH, SCREEN_HEIGHT, &wallpaper_data)
        .unwrap_or(TextureId(0));

    // Load cursor texture.
    let cursor_data = oasis_backend_psp::generate_cursor_pixels();
    let cursor_tex = backend
        .load_texture_inner(CURSOR_W, CURSOR_H, &cursor_data)
        .unwrap_or(TextureId(0));

    // -- Window Manager (Desktop mode) --
    let psp_theme = oasis_backend_psp::psp_wm_theme();
    let mut wm = WindowManager::with_theme(SCREEN_WIDTH, SCREEN_HEIGHT, psp_theme);
    let mut sdi = SdiRegistry::new();

    // -- App mode --
    let mut app_mode = AppMode::Classic;
    let mut classic_view = ClassicView::Dashboard;

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
        String::from("Type 'help' for commands. Start=terminal, Select=desktop."),
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

    // Music player state (background thread).
    let mut mp_path = String::from("ms0:/");
    let mut mp_entries: Vec<FileEntry> = Vec::new();
    let mut mp_selected: usize = 0;
    let mut mp_scroll: usize = 0;
    let mut mp_loaded = false;
    let mut mp_file_name = String::new();

    // Single background worker thread handles both audio and file I/O.
    let (audio, io) = oasis_backend_psp::spawn_worker();
    let mut pv_loading = false; // true while waiting for async texture load

    // Confirm button held state for pointer simulation.
    let mut _confirm_held = false;

    // Register power callback for sleep/wake handling.
    oasis_backend_psp::register_power_callback();

    loop {
        // Prevent idle auto-suspend while running.
        oasis_backend_psp::power_tick();

        // Check if we resumed from sleep.
        if oasis_backend_psp::check_power_resumed() {
            term_lines.push(String::from("[Power] Resumed from sleep"));
        }

        // -- Poll async I/O responses --
        while let Ok(resp) = io.rx.try_recv() {
            match resp {
                IoResponse::TextureReady {
                    path: _,
                    width,
                    height,
                    rgba,
                } => {
                    if pv_loading {
                        if let Some(old) = pv_tex.take() {
                            backend.destroy_texture_inner(old);
                        }
                        pv_tex = backend.load_texture_inner(width, height, &rgba);
                        pv_img_w = width;
                        pv_img_h = height;
                        pv_viewing = true;
                        pv_loading = false;
                    }
                }
                IoResponse::Error { path, msg } => {
                    term_lines.push(format!("I/O error: {} - {}", path, msg));
                    pv_loading = false;
                }
                IoResponse::FileReady { .. } => {}
            }
        }

        let events = backend.poll_events_inner();

        for event in &events {
            // -- Desktop mode: bridge analog stick + Confirm to pointer events --
            if app_mode == AppMode::Desktop {
                match event {
                    InputEvent::ButtonPress(Button::Confirm) => {
                        _confirm_held = true;
                        let (cx, cy) = backend.cursor_pos();
                        let ptr_event = InputEvent::PointerClick { x: cx, y: cy };
                        let wm_event = wm.handle_input(&ptr_event, &mut sdi);
                        handle_wm_event(
                            &wm_event,
                            &mut term_lines,
                            &mut classic_view,
                            &mut app_mode,
                            &mut wm,
                            &mut sdi,
                            page,
                        );
                    }
                    InputEvent::ButtonRelease(Button::Confirm) => {
                        _confirm_held = false;
                        let (cx, cy) = backend.cursor_pos();
                        let ptr_event = InputEvent::PointerRelease { x: cx, y: cy };
                        wm.handle_input(&ptr_event, &mut sdi);
                    }
                    InputEvent::CursorMove { x, y } => {
                        // Always forward cursor moves when in Desktop mode.
                        let move_event = InputEvent::CursorMove { x: *x, y: *y };
                        wm.handle_input(&move_event, &mut sdi);
                    }
                    InputEvent::ButtonPress(Button::Select) => {
                        // Toggle back to Classic mode.
                        app_mode = AppMode::Classic;
                        classic_view = ClassicView::Dashboard;
                    }
                    InputEvent::ButtonPress(Button::Triangle) => {
                        // Open app launcher: cycle through apps and open as windows.
                        let idx = page * ICONS_PER_PAGE + selected;
                        if idx < APPS.len() {
                            let app = &APPS[idx];
                            open_app_window(&mut wm, &mut sdi, app.id, app.title);
                        }
                    }
                    InputEvent::ButtonPress(Button::Start) => {
                        // Toggle terminal window.
                        open_app_window(&mut wm, &mut sdi, "terminal", "Terminal");
                    }
                    // Dashboard navigation works in Desktop mode too.
                    InputEvent::ButtonPress(Button::Up) => {
                        if selected >= GRID_COLS {
                            selected -= GRID_COLS;
                        }
                    }
                    InputEvent::ButtonPress(Button::Down) => {
                        let page_start = page * ICONS_PER_PAGE;
                        let page_count =
                            APPS.len().saturating_sub(page_start).min(ICONS_PER_PAGE);
                        if selected + GRID_COLS < page_count {
                            selected += GRID_COLS;
                        }
                    }
                    InputEvent::ButtonPress(Button::Left) => {
                        let page_start = page * ICONS_PER_PAGE;
                        let page_count =
                            APPS.len().saturating_sub(page_start).min(ICONS_PER_PAGE);
                        if selected == 0 {
                            selected = if page_count > 0 { page_count - 1 } else { 0 };
                        } else {
                            selected -= 1;
                        }
                    }
                    InputEvent::ButtonPress(Button::Right) => {
                        let page_start = page * ICONS_PER_PAGE;
                        let page_count =
                            APPS.len().saturating_sub(page_start).min(ICONS_PER_PAGE);
                        selected = (selected + 1) % page_count.max(1);
                    }
                    InputEvent::TriggerPress(Trigger::Left) => {
                        top_tab = top_tab.next();
                    }
                    InputEvent::TriggerPress(Trigger::Right) => {
                        media_tab = media_tab.next();
                    }
                    InputEvent::Quit => return,
                    _ => {}
                }
                continue; // Skip classic input handling.
            }

            // -- Classic mode input --
            match event {
                InputEvent::Quit => return,

                InputEvent::ButtonPress(Button::Start) => {
                    classic_view = match classic_view {
                        ClassicView::Dashboard => ClassicView::Terminal,
                        ClassicView::Terminal => ClassicView::Dashboard,
                        ClassicView::FileManager => ClassicView::Dashboard,
                        ClassicView::PhotoViewer => ClassicView::Dashboard,
                        ClassicView::MusicPlayer => ClassicView::Dashboard,
                    };
                }

                InputEvent::ButtonPress(Button::Select) if classic_view == ClassicView::Dashboard => {
                    // Toggle to Desktop mode.
                    app_mode = AppMode::Desktop;
                    psp::dprintln!("OASIS_OS: Switched to Desktop mode");
                }

                // -- Dashboard input --
                InputEvent::ButtonPress(Button::Up) if classic_view == ClassicView::Dashboard => {
                    if selected >= GRID_COLS {
                        selected -= GRID_COLS;
                    }
                }
                InputEvent::ButtonPress(Button::Down) if classic_view == ClassicView::Dashboard => {
                    let page_start = page * ICONS_PER_PAGE;
                    let page_count =
                        APPS.len().saturating_sub(page_start).min(ICONS_PER_PAGE);
                    if selected + GRID_COLS < page_count {
                        selected += GRID_COLS;
                    }
                }
                InputEvent::ButtonPress(Button::Left) if classic_view == ClassicView::Dashboard => {
                    let page_start = page * ICONS_PER_PAGE;
                    let page_count =
                        APPS.len().saturating_sub(page_start).min(ICONS_PER_PAGE);
                    if selected == 0 {
                        selected = if page_count > 0 { page_count - 1 } else { 0 };
                    } else {
                        selected -= 1;
                    }
                }
                InputEvent::ButtonPress(Button::Right) if classic_view == ClassicView::Dashboard => {
                    let page_start = page * ICONS_PER_PAGE;
                    let page_count =
                        APPS.len().saturating_sub(page_start).min(ICONS_PER_PAGE);
                    selected = (selected + 1) % page_count.max(1);
                }
                InputEvent::ButtonPress(Button::Confirm) if classic_view == ClassicView::Dashboard => {
                    let idx = page * ICONS_PER_PAGE + selected;
                    if idx < APPS.len() {
                        let app = &APPS[idx];
                        match app.title {
                            "Terminal" => {
                                classic_view = ClassicView::Terminal;
                            }
                            "File Manager" => {
                                classic_view = ClassicView::FileManager;
                                fm_loaded = false;
                            }
                            "Photo Viewer" => {
                                classic_view = ClassicView::PhotoViewer;
                                pv_viewing = false;
                                pv_loaded = false;
                            }
                            "Music Player" => {
                                classic_view = ClassicView::MusicPlayer;
                                mp_loaded = false;
                            }
                            _ => {
                                term_lines.push(format!("Launched: {}", app.title));
                            }
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Cancel) if classic_view == ClassicView::Dashboard => {
                    page = (page + 1) % total_pages;
                    let page_start = page * ICONS_PER_PAGE;
                    let page_count =
                        APPS.len().saturating_sub(page_start).min(ICONS_PER_PAGE);
                    if selected >= page_count && page_count > 0 {
                        selected = page_count - 1;
                    }
                }

                // Trigger cycling.
                InputEvent::TriggerPress(Trigger::Left) if classic_view == ClassicView::Dashboard => {
                    top_tab = top_tab.next();
                }
                InputEvent::TriggerPress(Trigger::Right) if classic_view == ClassicView::Dashboard => {
                    media_tab = media_tab.next();
                }

                // -- Terminal input --
                InputEvent::ButtonPress(Button::Confirm) if classic_view == ClassicView::Terminal => {
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
                InputEvent::ButtonPress(Button::Up) if classic_view == ClassicView::Terminal => {
                    term_lines.push(String::from("> help"));
                    let output = execute_command("help");
                    for line in output {
                        term_lines.push(line);
                    }
                }
                InputEvent::ButtonPress(Button::Down) if classic_view == ClassicView::Terminal => {
                    term_lines.push(String::from("> status"));
                    let output = execute_command("status");
                    for line in output {
                        term_lines.push(line);
                    }
                }

                // -- File manager input --
                InputEvent::ButtonPress(Button::Up) if classic_view == ClassicView::FileManager => {
                    if fm_selected > 0 {
                        fm_selected -= 1;
                        if fm_selected < fm_scroll {
                            fm_scroll = fm_selected;
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Down) if classic_view == ClassicView::FileManager => {
                    if fm_selected + 1 < fm_entries.len() {
                        fm_selected += 1;
                        if fm_selected >= fm_scroll + FM_VISIBLE_ROWS {
                            fm_scroll = fm_selected - FM_VISIBLE_ROWS + 1;
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Confirm) if classic_view == ClassicView::FileManager => {
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
                InputEvent::ButtonPress(Button::Cancel) if classic_view == ClassicView::FileManager => {
                    if let Some(pos) = fm_path.rfind('/') {
                        if pos > 0 && !fm_path[..pos].ends_with(':') {
                            fm_path.truncate(pos);
                        } else if fm_path.len() > pos + 1 {
                            fm_path.truncate(pos + 1);
                        } else {
                            classic_view = ClassicView::Dashboard;
                        }
                        fm_loaded = false;
                    } else {
                        classic_view = ClassicView::Dashboard;
                    }
                }
                InputEvent::ButtonPress(Button::Triangle) if classic_view == ClassicView::FileManager => {
                    classic_view = ClassicView::Dashboard;
                }

                // -- Photo viewer input --
                InputEvent::ButtonPress(Button::Up) if classic_view == ClassicView::PhotoViewer && !pv_viewing => {
                    if pv_selected > 0 {
                        pv_selected -= 1;
                        if pv_selected < pv_scroll {
                            pv_scroll = pv_selected;
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Down) if classic_view == ClassicView::PhotoViewer && !pv_viewing => {
                    if pv_selected + 1 < pv_entries.len() {
                        pv_selected += 1;
                        if pv_selected >= pv_scroll + FM_VISIBLE_ROWS {
                            pv_scroll = pv_selected - FM_VISIBLE_ROWS + 1;
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Confirm) if classic_view == ClassicView::PhotoViewer && !pv_viewing => {
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
                            // Async JPEG decode via background I/O thread.
                            let file_path = if pv_path.ends_with('/') {
                                format!("{}{}", pv_path, entry.name)
                            } else {
                                format!("{}/{}", pv_path, entry.name)
                            };
                            let _ = io.tx.send(WorkerCmd::Io(IoRequest::LoadTexture {
                                path: file_path,
                                max_w: SCREEN_WIDTH as i32,
                                max_h: SCREEN_HEIGHT as i32,
                            }));
                            pv_loading = true;
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Cancel) if classic_view == ClassicView::PhotoViewer => {
                    if pv_viewing {
                        pv_viewing = false;
                    } else if let Some(pos) = pv_path.rfind('/') {
                        if pos > 0 && !pv_path[..pos].ends_with(':') {
                            pv_path.truncate(pos);
                        } else if pv_path.len() > pos + 1 {
                            pv_path.truncate(pos + 1);
                        } else {
                            classic_view = ClassicView::Dashboard;
                        }
                        pv_loaded = false;
                    } else {
                        classic_view = ClassicView::Dashboard;
                    }
                }
                InputEvent::ButtonPress(Button::Triangle) if classic_view == ClassicView::PhotoViewer => {
                    if pv_viewing {
                        pv_viewing = false;
                    } else {
                        classic_view = ClassicView::Dashboard;
                    }
                }

                // -- Music player input --
                InputEvent::ButtonPress(Button::Up) if classic_view == ClassicView::MusicPlayer && !audio.is_playing() => {
                    if mp_selected > 0 {
                        mp_selected -= 1;
                        if mp_selected < mp_scroll {
                            mp_scroll = mp_selected;
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Down) if classic_view == ClassicView::MusicPlayer && !audio.is_playing() => {
                    if mp_selected + 1 < mp_entries.len() {
                        mp_selected += 1;
                        if mp_selected >= mp_scroll + FM_VISIBLE_ROWS {
                            mp_scroll = mp_selected - FM_VISIBLE_ROWS + 1;
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Confirm) if classic_view == ClassicView::MusicPlayer => {
                    if audio.is_playing() {
                        // Toggle pause via background thread.
                        if audio.is_paused() {
                            let _ = audio.tx.send(WorkerCmd::AudioResume);
                        } else {
                            let _ = audio.tx.send(WorkerCmd::AudioPause);
                        }
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
                            // Play MP3 via background thread.
                            let file_path = if mp_path.ends_with('/') {
                                format!("{}{}", mp_path, entry.name)
                            } else {
                                format!("{}/{}", mp_path, entry.name)
                            };
                            mp_file_name = entry.name.clone();
                            let _ = audio.tx.send(WorkerCmd::AudioLoadAndPlay(file_path));
                            term_lines.push(format!("Playing: {}", entry.name));
                        }
                    }
                }
                InputEvent::ButtonPress(Button::Square) if classic_view == ClassicView::MusicPlayer => {
                    let _ = audio.tx.send(WorkerCmd::AudioStop);
                }
                InputEvent::ButtonPress(Button::Cancel) if classic_view == ClassicView::MusicPlayer => {
                    let _ = audio.tx.send(WorkerCmd::AudioStop);
                    if let Some(pos) = mp_path.rfind('/') {
                        if pos > 0 && !mp_path[..pos].ends_with(':') {
                            mp_path.truncate(pos);
                        } else if mp_path.len() > pos + 1 {
                            mp_path.truncate(pos + 1);
                        } else {
                            classic_view = ClassicView::Dashboard;
                        }
                        mp_loaded = false;
                    } else {
                        classic_view = ClassicView::Dashboard;
                    }
                }
                InputEvent::ButtonPress(Button::Triangle) if classic_view == ClassicView::MusicPlayer => {
                    classic_view = ClassicView::Dashboard;
                    // Audio keeps playing in background.
                }

                _ => {}
            }
        }

        // -- Render --
        let status = StatusBarInfo::poll();

        backend.clear_inner(Color::BLACK);

        // Wallpaper.
        backend.blit_inner(wallpaper_tex, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT);

        match app_mode {
            AppMode::Classic => {
                // Lazy-load directory entries for browser modes.
                if classic_view == ClassicView::FileManager && !fm_loaded {
                    fm_entries = oasis_backend_psp::list_directory(&fm_path);
                    fm_selected = 0;
                    fm_scroll = 0;
                    fm_loaded = true;
                }
                if classic_view == ClassicView::PhotoViewer && !pv_loaded && !pv_viewing {
                    let all = oasis_backend_psp::list_directory(&pv_path);
                    pv_entries = all
                        .into_iter()
                        .filter(|e| {
                            e.is_dir || {
                                let lower: String =
                                    e.name.chars().map(|c| c.to_ascii_lowercase()).collect();
                                lower.ends_with(".jpg") || lower.ends_with(".jpeg")
                            }
                        })
                        .collect();
                    pv_selected = 0;
                    pv_scroll = 0;
                    pv_loaded = true;
                }
                if classic_view == ClassicView::MusicPlayer && !mp_loaded && !audio.is_playing() {
                    let all = oasis_backend_psp::list_directory(&mp_path);
                    mp_entries = all
                        .into_iter()
                        .filter(|e| {
                            e.is_dir || {
                                let lower: String =
                                    e.name.chars().map(|c| c.to_ascii_lowercase()).collect();
                                lower.ends_with(".mp3")
                            }
                        })
                        .collect();
                    mp_selected = 0;
                    mp_scroll = 0;
                    mp_loaded = true;
                }

                match classic_view {
                    ClassicView::Dashboard => {
                        draw_dashboard(&mut backend, selected, page);
                    }
                    ClassicView::Terminal => {
                        draw_terminal(&mut backend, &term_lines, &term_input);
                    }
                    ClassicView::FileManager => {
                        draw_file_manager(
                            &mut backend,
                            &fm_path,
                            &fm_entries,
                            fm_selected,
                            fm_scroll,
                        );
                    }
                    ClassicView::PhotoViewer => {
                        if pv_viewing {
                            draw_photo_view(&mut backend, pv_tex, pv_img_w, pv_img_h);
                        } else if pv_loading {
                            draw_loading_indicator(&mut backend, "Decoding image...");
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
                    ClassicView::MusicPlayer => {
                        if audio.is_playing() {
                            draw_music_player_threaded(&mut backend, &mp_file_name, &audio);
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
            }

            AppMode::Desktop => {
                // Draw dashboard icons behind windows.
                draw_dashboard(&mut backend, selected, page);

                // Draw WM chrome (frames, titlebars) + clipped content.
                let _ = wm.draw_with_clips(
                    &sdi,
                    &mut backend,
                    |window_id, cx, cy, cw, ch, be| {
                        // Downcast back to PspBackend for direct calls.
                        // Since draw_with_clips passes &mut dyn SdiBackend, we use
                        // the trait methods here (which return Result).
                        match window_id {
                            "terminal" => {
                                draw_terminal_windowed(
                                    &term_lines, &term_input, cx, cy, cw, ch, be,
                                )
                            }
                            "filemgr" => {
                                draw_filemgr_windowed(
                                    &fm_path, &fm_entries, fm_selected, fm_scroll, cx, cy,
                                    cw, ch, be,
                                )
                            }
                            "photos" => {
                                draw_photos_windowed(
                                    pv_tex, pv_img_w, pv_img_h, pv_viewing, cx, cy, cw, ch,
                                    be,
                                )
                            }
                            "music" => {
                                draw_music_windowed(
                                    &mp_file_name, &audio, cx, cy, cw, ch, be,
                                )
                            }
                            _ => Ok(()),
                        }
                    },
                );

                // Desktop mode taskbar at bottom.
                draw_desktop_taskbar(&mut backend, &wm);
            }
        }

        // Status bar + bottom bar (always visible, drawn on top).
        draw_status_bar(&mut backend, top_tab, &status);
        if app_mode == AppMode::Classic {
            draw_bottom_bar(&mut backend, media_tab, page, total_pages);
        }

        // Cursor (always on top).
        let (cx, cy) = backend.cursor_pos();
        backend.blit_inner(cursor_tex, cx, cy, CURSOR_W, CURSOR_H);

        backend.swap_buffers_inner();
    }
}

// ---------------------------------------------------------------------------
// Desktop mode helpers
// ---------------------------------------------------------------------------

/// Check if coordinates are over a dashboard icon, returning the global index.
fn hit_test_dashboard_icon(x: i32, y: i32, page: usize) -> Option<usize> {
    let page_start = page * ICONS_PER_PAGE;
    let page_end = (page_start + ICONS_PER_PAGE).min(APPS.len());
    for i in 0..(page_end - page_start) {
        let col = (i % GRID_COLS) as i32;
        let row = (i / GRID_COLS) as i32;
        let cell_x = GRID_PAD_X + col * CELL_W;
        let cell_y = CONTENT_TOP as i32 + GRID_PAD_Y + row * CELL_H;
        let ix = cell_x + (CELL_W - ICON_W as i32) / 2;
        let iy = cell_y + 4;
        if x >= ix
            && x < ix + ICON_W as i32
            && y >= iy
            && y < iy + ICON_H as i32 + ICON_LABEL_PAD + 10
        {
            return Some(page_start + i);
        }
    }
    None
}

/// Open an app as a floating window (or focus if already open).
fn open_app_window(wm: &mut WindowManager, sdi: &mut SdiRegistry, app_id: &str, title: &str) {
    if wm.get_window(app_id).is_some() {
        let _ = wm.focus_window(app_id, sdi);
        return;
    }
    let config = WindowConfig {
        id: app_id.to_string(),
        title: title.to_string(),
        x: None,
        y: Some(STATUSBAR_H as i32 + TAB_ROW_H as i32 + 2),
        width: 300,
        height: 180,
        window_type: WindowType::AppWindow,
    };
    let _ = wm.create_window(&config, sdi);
}

/// Handle WM events (window closed, desktop click opens apps, etc.).
fn handle_wm_event(
    event: &WmEvent,
    term_lines: &mut Vec<String>,
    _classic_view: &mut ClassicView,
    _app_mode: &mut AppMode,
    wm: &mut WindowManager,
    sdi: &mut SdiRegistry,
    page: usize,
) {
    match event {
        WmEvent::WindowClosed(id) => {
            term_lines.push(format!("[WM] Window closed: {}", id));
        }
        WmEvent::ContentClick(id, lx, ly) => {
            term_lines.push(format!("[WM] Click in {}: ({}, {})", id, lx, ly));
        }
        WmEvent::DesktopClick(x, y) => {
            if let Some(idx) = hit_test_dashboard_icon(*x, *y, page) {
                if idx < APPS.len() {
                    open_app_window(wm, sdi, APPS[idx].id, APPS[idx].title);
                }
            }
        }
        _ => {}
    }
}

/// Draw the desktop mode taskbar showing open windows.
fn draw_desktop_taskbar(backend: &mut PspBackend, wm: &WindowManager) {
    let bar_y = BOTTOMBAR_Y;
    backend.fill_rect_inner(0, bar_y, SCREEN_WIDTH, TASKBAR_H, Color::rgba(0, 0, 0, 160));
    backend.fill_rect_inner(0, bar_y, SCREEN_WIDTH, 1, Color::rgba(255, 255, 255, 40));

    let active_id = wm.active_window();
    let mut tx = 4i32;

    for app in APPS {
        if wm.get_window(app.id).is_some() {
            let is_active = active_id == Some(app.id);
            let label_clr = if is_active {
                Color::WHITE
            } else {
                Color::rgb(160, 160, 160)
            };
            if is_active {
                let label_w = (app.title.len() as i32 * 8 + 8) as u32;
                backend.fill_rect_inner(tx - 2, bar_y + 1, label_w, TASKBAR_H - 2, Color::rgba(60, 90, 160, 140));
            }
            backend.draw_text_inner(app.title, tx + 2, bar_y + 3, 8, label_clr);
            tx += app.title.len() as i32 * 8 + 12;
        }
    }
}

// ---------------------------------------------------------------------------
// Windowed content renderers (for draw_with_clips callback)
// ---------------------------------------------------------------------------

fn draw_terminal_windowed(
    lines: &[String],
    input: &str,
    cx: i32,
    cy: i32,
    cw: u32,
    ch: u32,
    be: &mut dyn SdiBackend,
) -> oasis_backend_psp::OasisResult<()> {
    let bg = Color::rgba(0, 0, 0, 200);
    be.fill_rect(cx, cy, cw, ch, bg)?;

    let max_lines = (ch as usize) / 9;
    let visible_start = if lines.len() > max_lines {
        lines.len() - max_lines
    } else {
        0
    };
    for (i, line) in lines[visible_start..].iter().enumerate() {
        let y = cy + 2 + i as i32 * 9;
        if y > cy + ch as i32 - 14 {
            break;
        }
        be.draw_text(line, cx + 2, y, 8, Color::rgb(0, 255, 0))?;
    }

    let prompt = format!("> {}_", input);
    be.draw_text(&prompt, cx + 2, cy + ch as i32 - 12, 8, Color::rgb(0, 255, 0))?;
    Ok(())
}

fn draw_filemgr_windowed(
    path: &str,
    entries: &[FileEntry],
    selected: usize,
    scroll: usize,
    cx: i32,
    cy: i32,
    cw: u32,
    ch: u32,
    be: &mut dyn SdiBackend,
) -> oasis_backend_psp::OasisResult<()> {
    be.fill_rect(cx, cy, cw, ch, Color::rgba(0, 0, 0, 200))?;
    be.draw_text(path, cx + 2, cy + 2, 8, Color::rgb(100, 200, 255))?;

    let max_rows = ((ch as i32 - 14) / FM_ROW_H) as usize;
    let end = (scroll + max_rows).min(entries.len());
    for i in scroll..end {
        let entry = &entries[i];
        let row = (i - scroll) as i32;
        let y = cy + 14 + row * FM_ROW_H;
        if i == selected {
            be.fill_rect(cx, y - 1, cw, FM_ROW_H as u32, Color::rgba(80, 120, 200, 100))?;
        }
        let (prefix, clr) = if entry.is_dir {
            ("[D]", Color::rgb(255, 220, 80))
        } else {
            ("[F]", Color::rgb(180, 180, 180))
        };
        be.draw_text(prefix, cx + 2, y, 8, clr)?;
        let name_clr = if entry.is_dir {
            Color::rgb(120, 220, 255)
        } else {
            Color::WHITE
        };
        be.draw_text(&entry.name, cx + 28, y, 8, name_clr)?;
    }
    Ok(())
}

fn draw_photos_windowed(
    tex: Option<TextureId>,
    img_w: u32,
    img_h: u32,
    viewing: bool,
    cx: i32,
    cy: i32,
    cw: u32,
    ch: u32,
    be: &mut dyn SdiBackend,
) -> oasis_backend_psp::OasisResult<()> {
    be.fill_rect(cx, cy, cw, ch, Color::BLACK)?;
    if viewing {
        if let Some(t) = tex {
            let scale_w = cw as f32 / img_w as f32;
            let scale_h = ch as f32 / img_h as f32;
            let scale = if scale_w < scale_h { scale_w } else { scale_h };
            let dw = (img_w as f32 * scale) as u32;
            let dh = (img_h as f32 * scale) as u32;
            let dx = cx + ((cw - dw) / 2) as i32;
            let dy = cy + ((ch - dh) / 2) as i32;
            be.blit(t, dx, dy, dw, dh)?;
        }
    } else {
        be.draw_text("Select photo from browser", cx + 4, cy + 4, 8, Color::rgb(160, 160, 160))?;
    }
    Ok(())
}

fn draw_music_windowed(
    file_name: &str,
    audio: &AudioHandle,
    cx: i32,
    cy: i32,
    cw: u32,
    ch: u32,
    be: &mut dyn SdiBackend,
) -> oasis_backend_psp::OasisResult<()> {
    be.fill_rect(cx, cy, cw, ch, Color::rgba(0, 0, 0, 210))?;

    if audio.is_playing() {
        let center_x = cx + cw as i32 / 2;
        be.draw_text(file_name, cx + 4, cy + 4, 8, Color::rgb(255, 200, 200))?;
        let info = format!(
            "{}Hz {}kbps {}ch",
            audio.sample_rate(),
            audio.bitrate(),
            audio.channels(),
        );
        let info_x = center_x - (info.len() as i32 * 8) / 2;
        be.draw_text(&info, info_x, cy + 18, 8, Color::rgb(180, 180, 180))?;
        let status = if audio.is_paused() { "PAUSED" } else { "PLAYING" };
        let status_clr = if audio.is_paused() {
            Color::rgb(255, 200, 80)
        } else {
            Color::rgb(120, 255, 120)
        };
        let status_x = center_x - (status.len() as i32 * 8) / 2;
        be.draw_text(status, status_x, cy + ch as i32 / 2, 8, status_clr)?;
    } else {
        be.draw_text("No track loaded", cx + 4, cy + 4, 8, Color::rgb(160, 160, 160))?;
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Loading indicator
// ---------------------------------------------------------------------------

fn draw_loading_indicator(backend: &mut PspBackend, msg: &str) {
    let bg = Color::rgba(0, 0, 0, 200);
    backend.fill_rect_inner(0, CONTENT_TOP as i32, SCREEN_WIDTH, CONTENT_H, bg);
    let cx = SCREEN_WIDTH as i32 / 2;
    let cy = CONTENT_TOP as i32 + CONTENT_H as i32 / 2;
    let text_x = cx - (msg.len() as i32 * 8) / 2;
    backend.draw_text_inner(msg, text_x, cy, 8, Color::rgb(200, 200, 200));
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
        backend.draw_text_inner(app.title, cell_x, label_y, 8, LABEL_CLR);
    }

    // Cursor highlight around selected icon.
    if page_count > 0 && selected < page_count {
        let sel_col = (selected % GRID_COLS) as i32;
        let sel_row = (selected / GRID_COLS) as i32;
        let cell_x = GRID_PAD_X + sel_col * CELL_W;
        let cell_y = CONTENT_TOP as i32 + GRID_PAD_Y + sel_row * CELL_H;
        let ix = cell_x + (CELL_W - ICON_W as i32) / 2;
        let iy = cell_y + 4;
        backend.fill_rect_inner(
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
    backend.fill_rect_inner(ix + 2, iy + 3, ICON_W + 2, ICON_H + 1, SHADOW_CLR);
    backend.fill_rect_inner(ix - 1, iy - 1, ICON_W + 2, ICON_H + 2, OUTLINE_CLR);
    backend.fill_rect_inner(ix, iy, ICON_W, ICON_H, BODY_CLR);
    backend.fill_rect_inner(ix, iy, ICON_W - ICON_FOLD_SIZE, ICON_STRIPE_H, app.color);
    backend.fill_rect_inner(
        ix + ICON_W as i32 - ICON_FOLD_SIZE as i32,
        iy,
        ICON_FOLD_SIZE,
        ICON_FOLD_SIZE,
        FOLD_CLR,
    );

    let gfx_w = ICON_W - 2 * ICON_GFX_PAD;
    let c = app.color;
    let gfx_color = Color::rgba(
        c.r.saturating_add(30),
        c.g.saturating_add(10),
        c.b.saturating_add(30),
        200,
    );
    backend.fill_rect_inner(
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
    backend.fill_rect_inner(0, 0, SCREEN_WIDTH, STATUSBAR_H, STATUSBAR_BG);
    backend.fill_rect_inner(0, STATUSBAR_H as i32 - 1, SCREEN_WIDTH, 1, SEPARATOR);

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
    backend.draw_text_inner(&bat_label, 6, 7, 8, bat_color);

    let wifi_label = if status.wifi_on { "WiFi" } else { "----" };
    let wifi_color = if status.wifi_on {
        Color::rgb(100, 200, 255)
    } else {
        Color::rgb(100, 100, 100)
    };
    backend.draw_text_inner(wifi_label, 96, 7, 8, wifi_color);

    let usb_color = if status.usb_connected {
        Color::rgb(200, 200, 200)
    } else {
        Color::rgb(100, 100, 100)
    };
    backend.draw_text_inner("USB", 140, 7, 8, usb_color);

    backend.draw_text_inner("OASIS v0.1", 200, 7, 8, Color::WHITE);

    let time_label = format!("{:02}:{:02}", status.hour, status.minute);
    backend.draw_text_inner(&time_label, 420, 7, 8, Color::WHITE);

    backend.draw_text_inner("OSS", 6, STATUSBAR_H as i32 + 3, 8, CATEGORY_CLR);

    let tab_y = STATUSBAR_H as i32;
    for (i, tab) in TopTab::ALL.iter().enumerate() {
        let x = TAB_START_X + (i as i32) * (TAB_W + TAB_GAP);
        let alpha = if *tab == active_tab { 180u8 } else { 60u8 };
        let border = Color::rgba(255, 255, 255, alpha);

        backend.fill_rect_inner(x, tab_y, TAB_W as u32, 1, border);
        backend.fill_rect_inner(x, tab_y + TAB_H - 1, TAB_W as u32, 1, border);
        backend.fill_rect_inner(x, tab_y, 1, TAB_H as u32, border);
        backend.fill_rect_inner(x + TAB_W - 1, tab_y, 1, TAB_H as u32, border);

        if *tab == active_tab {
            backend.fill_rect_inner(
                x + 1,
                tab_y + 1,
                (TAB_W - 2) as u32,
                (TAB_H - 2) as u32,
                TAB_ACTIVE_FILL,
            );
        }

        let label = tab.label();
        let text_w = label.len() as i32 * CHAR_W;
        let tx = x + (TAB_W - text_w) / 2;
        let text_color = if *tab == active_tab {
            Color::WHITE
        } else {
            Color::rgb(160, 160, 160)
        };
        backend.draw_text_inner(label, tx.max(x + 2), tab_y + 4, 8, text_color);
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

    backend.fill_rect_inner(0, bar_y, SCREEN_WIDTH, BOTTOMBAR_H, BAR_BG);
    backend.fill_rect_inner(0, bar_y, SCREEN_WIDTH, 1, SEPARATOR);

    let url_bx = 2i32;
    let url_bw = 190u32;
    let bz_y = bar_y + 2;
    let bz_h = BOTTOMBAR_H - 4;
    draw_chrome_bezel(backend, url_bx, bz_y, url_bw, bz_h);

    backend.draw_text_inner("HTTP://OASIS.LOCAL", 8, bar_y + 8, 8, URL_CLR);

    let usb_x = url_bx + url_bw as i32 + 14;
    backend.draw_text_inner("USB", usb_x, bar_y + 8, 8, USB_CLR);

    let dots_x = usb_x + 36;
    let max_dots = 4usize;
    for i in 0..total_pages.min(max_dots) {
        let color = if i == current_page {
            DOT_ACTIVE
        } else {
            DOT_INACTIVE
        };
        backend.fill_rect_inner(dots_x + (i as i32) * 12, bar_y + 9, 6, 6, color);
    }

    let labels_w: i32 = MediaTab::LABELS.iter().map(|l| l.len() as i32 * CHAR_W).sum();
    let pipes_w = (MediaTab::LABELS.len() as i32 - 1) * (PIPE_GAP * 2 + CHAR_W);
    let total_w = labels_w + pipes_w;
    let tabs_x = SCREEN_WIDTH as i32 - total_w - R_HINT_W - 8;

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
        backend.draw_text_inner(label, cx, bar_y + 8, 8, color);
        cx += label.len() as i32 * CHAR_W;

        if i < MediaTab::LABELS.len() - 1 {
            cx += PIPE_GAP;
            backend.draw_text_inner("|", cx, bar_y + 8, 8, PIPE_CLR);
            cx += CHAR_W + PIPE_GAP;
        }
    }

    backend.draw_text_inner("R>", SCREEN_WIDTH as i32 - R_HINT_W, bar_y + 8, 8, R_HINT_CLR);
}

/// Draw a chrome/metallic bezel (fill + 4 edges).
fn draw_chrome_bezel(backend: &mut PspBackend, x: i32, y: i32, w: u32, h: u32) {
    backend.fill_rect_inner(x, y, w, h, BEZEL_FILL);
    backend.fill_rect_inner(x, y, w, 1, BEZEL_TOP);
    backend.fill_rect_inner(x, y + h as i32 - 1, w, 1, BEZEL_BOTTOM);
    backend.fill_rect_inner(x, y, 1, h, BEZEL_LEFT);
    backend.fill_rect_inner(x + w as i32 - 1, y, 1, h, BEZEL_RIGHT);
}

// ---------------------------------------------------------------------------
// Terminal rendering (classic full-screen)
// ---------------------------------------------------------------------------

fn draw_terminal(backend: &mut PspBackend, lines: &[String], input: &str) {
    let bg = Color::rgba(0, 0, 0, 180);
    backend.fill_rect_inner(0, CONTENT_TOP as i32, SCREEN_WIDTH, CONTENT_H, bg);

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
        backend.draw_text_inner(line, 4, y, 8, Color::rgb(0, 255, 0));
    }

    let prompt = format!("> {}_", input);
    backend.draw_text_inner(&prompt, 4, TERM_INPUT_Y, 8, Color::rgb(0, 255, 0));
}

// ---------------------------------------------------------------------------
// File manager rendering (classic full-screen)
// ---------------------------------------------------------------------------

fn draw_file_manager(
    backend: &mut PspBackend,
    path: &str,
    entries: &[FileEntry],
    selected: usize,
    scroll: usize,
) {
    let bg = Color::rgba(0, 0, 0, 200);
    backend.fill_rect_inner(0, CONTENT_TOP as i32, SCREEN_WIDTH, CONTENT_H, bg);

    backend.draw_text_inner(path, 4, CONTENT_TOP as i32 + 3, 8, Color::rgb(100, 200, 255));

    let header_y = CONTENT_TOP as i32 + 3;
    backend.draw_text_inner("SIZE", 400, header_y, 8, Color::rgb(160, 160, 160));

    backend.fill_rect_inner(
        0,
        FM_START_Y - 2,
        SCREEN_WIDTH,
        1,
        Color::rgba(255, 255, 255, 40),
    );

    if entries.is_empty() {
        backend.draw_text_inner("(empty directory)", 8, FM_START_Y, 8, Color::rgb(140, 140, 140));
        return;
    }

    let end = (scroll + FM_VISIBLE_ROWS).min(entries.len());
    for i in scroll..end {
        let entry = &entries[i];
        let row = (i - scroll) as i32;
        let y = FM_START_Y + row * FM_ROW_H;

        if i == selected {
            backend.fill_rect_inner(0, y - 1, SCREEN_WIDTH, FM_ROW_H as u32, Color::rgba(80, 120, 200, 100));
        }

        let (prefix, prefix_clr) = if entry.is_dir {
            ("[D]", Color::rgb(255, 220, 80))
        } else {
            ("[F]", Color::rgb(180, 180, 180))
        };
        backend.draw_text_inner(prefix, 4, y, 8, prefix_clr);

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
        backend.draw_text_inner(&display_name, 32, y, 8, name_color);

        if !entry.is_dir {
            let size_str = oasis_backend_psp::format_size(entry.size);
            let size_x = 480 - (size_str.len() as i32 * 8) - 4;
            backend.draw_text_inner(&size_str, size_x, y, 8, Color::rgb(180, 180, 180));
        }
    }

    if entries.len() > FM_VISIBLE_ROWS {
        let ratio = selected as f32 / (entries.len() - 1).max(1) as f32;
        let track_h = CONTENT_H as i32 - 16;
        let dot_y = FM_START_Y + (ratio * track_h as f32) as i32;
        backend.fill_rect_inner(SCREEN_WIDTH as i32 - 4, dot_y, 3, 8, Color::rgba(255, 255, 255, 120));
    }
}

// ---------------------------------------------------------------------------
// Photo viewer rendering (classic full-screen)
// ---------------------------------------------------------------------------

fn draw_photo_browser(
    backend: &mut PspBackend,
    path: &str,
    entries: &[FileEntry],
    selected: usize,
    scroll: usize,
) {
    let bg = Color::rgba(0, 0, 0, 200);
    backend.fill_rect_inner(0, CONTENT_TOP as i32, SCREEN_WIDTH, CONTENT_H, bg);

    backend.draw_text_inner("PHOTO VIEWER", 4, CONTENT_TOP as i32 + 3, 8, Color::rgb(100, 149, 237));
    backend.draw_text_inner(path, 110, CONTENT_TOP as i32 + 3, 8, Color::rgb(160, 160, 160));

    backend.fill_rect_inner(0, FM_START_Y - 2, SCREEN_WIDTH, 1, Color::rgba(255, 255, 255, 40));

    if entries.is_empty() {
        backend.draw_text_inner("No images found (.jpg/.jpeg)", 8, FM_START_Y, 8, Color::rgb(140, 140, 140));
        return;
    }

    let end = (scroll + FM_VISIBLE_ROWS).min(entries.len());
    for i in scroll..end {
        let entry = &entries[i];
        let row = (i - scroll) as i32;
        let y = FM_START_Y + row * FM_ROW_H;

        if i == selected {
            backend.fill_rect_inner(0, y - 1, SCREEN_WIDTH, FM_ROW_H as u32, Color::rgba(80, 120, 200, 100));
        }

        let (prefix, prefix_clr) = if entry.is_dir {
            ("[D]", Color::rgb(255, 220, 80))
        } else {
            ("[I]", Color::rgb(100, 200, 255))
        };
        backend.draw_text_inner(prefix, 4, y, 8, prefix_clr);

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
        backend.draw_text_inner(&display_name, 32, y, 8, name_color);

        if !entry.is_dir {
            let size_str = oasis_backend_psp::format_size(entry.size);
            let size_x = 480 - (size_str.len() as i32 * 8) - 4;
            backend.draw_text_inner(&size_str, size_x, y, 8, Color::rgb(180, 180, 180));
        }
    }
}

fn draw_photo_view(
    backend: &mut PspBackend,
    tex: Option<TextureId>,
    img_w: u32,
    img_h: u32,
) {
    backend.fill_rect_inner(0, CONTENT_TOP as i32, SCREEN_WIDTH, CONTENT_H, Color::BLACK);

    if let Some(t) = tex {
        let max_w = SCREEN_WIDTH;
        let max_h = CONTENT_H;
        let scale_w = max_w as f32 / img_w as f32;
        let scale_h = max_h as f32 / img_h as f32;
        let scale = if scale_w < scale_h { scale_w } else { scale_h };
        let draw_w = (img_w as f32 * scale) as u32;
        let draw_h = (img_h as f32 * scale) as u32;
        let draw_x = ((max_w - draw_w) / 2) as i32;
        let draw_y = CONTENT_TOP as i32 + ((max_h - draw_h) / 2) as i32;

        backend.blit_inner(t, draw_x, draw_y, draw_w, draw_h);
    } else {
        backend.draw_text_inner("Failed to load image", 160, 130, 8, Color::rgb(255, 80, 80));
    }
}

// ---------------------------------------------------------------------------
// Music player rendering (classic full-screen, threaded audio)
// ---------------------------------------------------------------------------

fn draw_music_browser(
    backend: &mut PspBackend,
    path: &str,
    entries: &[FileEntry],
    selected: usize,
    scroll: usize,
) {
    let bg = Color::rgba(0, 0, 0, 200);
    backend.fill_rect_inner(0, CONTENT_TOP as i32, SCREEN_WIDTH, CONTENT_H, bg);

    backend.draw_text_inner("MUSIC PLAYER", 4, CONTENT_TOP as i32 + 3, 8, Color::rgb(205, 92, 92));
    backend.draw_text_inner(path, 110, CONTENT_TOP as i32 + 3, 8, Color::rgb(160, 160, 160));

    backend.fill_rect_inner(0, FM_START_Y - 2, SCREEN_WIDTH, 1, Color::rgba(255, 255, 255, 40));

    if entries.is_empty() {
        backend.draw_text_inner("No MP3 files found", 8, FM_START_Y, 8, Color::rgb(140, 140, 140));
        return;
    }

    let end = (scroll + FM_VISIBLE_ROWS).min(entries.len());
    for i in scroll..end {
        let entry = &entries[i];
        let row = (i - scroll) as i32;
        let y = FM_START_Y + row * FM_ROW_H;

        if i == selected {
            backend.fill_rect_inner(0, y - 1, SCREEN_WIDTH, FM_ROW_H as u32, Color::rgba(200, 80, 80, 100));
        }

        let (prefix, prefix_clr) = if entry.is_dir {
            ("[D]", Color::rgb(255, 220, 80))
        } else {
            ("[M]", Color::rgb(205, 92, 92))
        };
        backend.draw_text_inner(prefix, 4, y, 8, prefix_clr);

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
        backend.draw_text_inner(&display_name, 32, y, 8, name_color);

        if !entry.is_dir {
            let size_str = oasis_backend_psp::format_size(entry.size);
            let size_x = 480 - (size_str.len() as i32 * 8) - 4;
            backend.draw_text_inner(&size_str, size_x, y, 8, Color::rgb(180, 180, 180));
        }
    }
}

/// Draw the now-playing music player UI (using threaded AudioHandle).
fn draw_music_player_threaded(
    backend: &mut PspBackend,
    file_name: &str,
    audio: &AudioHandle,
) {
    let bg = Color::rgba(0, 0, 0, 210);
    backend.fill_rect_inner(0, CONTENT_TOP as i32, SCREEN_WIDTH, CONTENT_H, bg);

    let cx = SCREEN_WIDTH as i32 / 2;
    let title_color = Color::rgb(255, 200, 200);
    let info_color = Color::rgb(180, 180, 180);

    // Album art placeholder.
    let art_size: u32 = 80;
    let art_x = cx - art_size as i32 / 2;
    let art_y = CONTENT_TOP as i32 + 20;
    backend.fill_rect_inner(art_x, art_y, art_size, art_size, Color::rgb(205, 92, 92));
    backend.fill_rect_inner(art_x + 2, art_y + 2, art_size - 4, art_size - 4, Color::rgb(60, 30, 30));
    backend.draw_text_inner("MP3", art_x + 22, art_y + 34, 8, Color::rgb(205, 92, 92));

    // Track name.
    let max_chars = 50;
    let display_name = if file_name.len() > max_chars {
        let truncated: String = file_name.chars().take(max_chars - 2).collect();
        format!("{}..", truncated)
    } else {
        file_name.to_string()
    };
    let name_x = cx - (display_name.len() as i32 * 8) / 2;
    backend.draw_text_inner(&display_name, name_x, art_y + art_size as i32 + 12, 8, title_color);

    // Format info from atomic state.
    let info = format!(
        "{}Hz  {}kbps  {}ch",
        audio.sample_rate(),
        audio.bitrate(),
        audio.channels(),
    );
    let info_x = cx - (info.len() as i32 * 8) / 2;
    backend.draw_text_inner(&info, info_x, art_y + art_size as i32 + 26, 8, info_color);

    let status = if audio.is_paused() { "PAUSED" } else { "PLAYING" };
    let status_clr = if audio.is_paused() {
        Color::rgb(255, 200, 80)
    } else {
        Color::rgb(120, 255, 120)
    };
    let status_x = cx - (status.len() as i32 * 8) / 2;
    backend.draw_text_inner(status, status_x, art_y + art_size as i32 + 44, 8, status_clr);

    let hint = "X:Pause  []:Stop  O:Back";
    let hint_x = cx - (hint.len() as i32 * 8) / 2;
    backend.draw_text_inner(hint, hint_x, BOTTOMBAR_Y - 16, 8, Color::rgb(140, 140, 140));
}

// ---------------------------------------------------------------------------
// Simple command interpreter
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
            String::from("Floating windows + multiprocessing enabled"),
        ],
        "clear" => vec![],
        _ => vec![format!("Unknown command: {}", trimmed)],
    }
}
