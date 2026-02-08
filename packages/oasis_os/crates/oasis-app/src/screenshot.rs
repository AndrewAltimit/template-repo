//! Screenshot capture tool for PSIX visual comparison.
//!
//! Renders the OASIS_OS UI in several states and saves PNG screenshots
//! to `screenshots/` next to the repo root. Compare these against
//! `Psixpsp.png` to iterate on the visual design.
//!
//! Usage:
//!   cargo run -p oasis-app --bin oasis-screenshot
//!
//! Output:
//!   screenshots/01_dashboard.png   -- Main dashboard view
//!   screenshots/02_media_tab.png   -- AUDIO media tab selected
//!   screenshots/03_mods_tab.png    -- MODS top tab selected
//!   screenshots/04_terminal.png    -- Terminal mode

use std::fs;
use std::path::Path;

use oasis_backend_sdl::SdlBackend;
use oasis_core::backend::{Color, SdiBackend};
use oasis_core::bottombar::{BottomBar, MediaTab};
use oasis_core::config::OasisConfig;
use oasis_core::cursor::{self, CursorState};
use oasis_core::dashboard::{DashboardConfig, DashboardState, discover_apps};
use oasis_core::platform::DesktopPlatform;
use oasis_core::platform::{PowerService, TimeService};
use oasis_core::sdi::SdiRegistry;
use oasis_core::skin::Skin;
use oasis_core::statusbar::StatusBar;
use oasis_core::vfs::MemoryVfs;
use oasis_core::wallpaper;

fn main() -> anyhow::Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let config = OasisConfig::default();
    let w = config.screen_width;
    let h = config.screen_height;

    let mut backend = SdlBackend::new("OASIS Screenshot", w, h)?;
    backend.init(w, h)?;

    let skin = Skin::from_toml(
        include_str!("../../../skins/classic/skin.toml"),
        include_str!("../../../skins/classic/layout.toml"),
        include_str!("../../../skins/classic/features.toml"),
    )?;

    let platform = DesktopPlatform::new();
    let mut vfs = MemoryVfs::new();
    populate_demo_vfs(&mut vfs);

    let apps = discover_apps(&vfs, "/apps", Some("OASISOS"))?;
    let dash_config = DashboardConfig::from_features(&skin.features);
    let dashboard = DashboardState::new(dash_config, apps);
    let mut status_bar = StatusBar::new();
    let mut bottom_bar = BottomBar::new();
    bottom_bar.total_pages = dashboard.page_count();

    let mut sdi = SdiRegistry::new();
    skin.apply_layout(&mut sdi);

    // Wallpaper.
    let wallpaper_tex = {
        let wp_data = wallpaper::generate_gradient(w, h);
        backend.load_texture(w, h, &wp_data)?
    };
    {
        let obj = sdi.create("wallpaper");
        obj.x = 0;
        obj.y = 0;
        obj.w = w;
        obj.h = h;
        obj.texture = Some(wallpaper_tex);
        obj.z = -1000;
    }

    // Mouse cursor (position it near center for the screenshot).
    let mut mouse_cursor = CursorState::new(w, h);
    {
        let (cursor_pixels, cw, ch) = cursor::generate_cursor_pixels();
        let cursor_tex = backend.load_texture(cw, ch, &cursor_pixels)?;
        mouse_cursor.update_sdi(&mut sdi);
        if let Ok(obj) = sdi.get_mut("mouse_cursor") {
            obj.texture = Some(cursor_tex);
        }
    }
    mouse_cursor.set_position(240, 136);

    // Update system info once.
    let time = platform.now().ok();
    let power = platform.power_info().ok();
    status_bar.update_info(time.as_ref(), power.as_ref());

    // Create output directory.
    let out_dir = Path::new("screenshots");
    fs::create_dir_all(out_dir)?;

    // -- Screenshot 1: Dashboard --
    dashboard.update_sdi(&mut sdi);
    status_bar.update_sdi(&mut sdi);
    bottom_bar.update_sdi(&mut sdi);
    mouse_cursor.update_sdi(&mut sdi);
    render_and_save(
        &mut backend,
        &mut sdi,
        w,
        h,
        out_dir.join("01_dashboard.png"),
    )?;
    log::info!("Saved 01_dashboard.png");

    // -- Screenshot 2: AUDIO media tab --
    bottom_bar.active_tab = MediaTab::Audio;
    dashboard.hide_sdi(&mut sdi);
    status_bar.update_sdi(&mut sdi);
    bottom_bar.update_sdi(&mut sdi);
    update_media_page(&mut sdi, &bottom_bar);
    mouse_cursor.update_sdi(&mut sdi);
    render_and_save(
        &mut backend,
        &mut sdi,
        w,
        h,
        out_dir.join("02_media_tab.png"),
    )?;
    log::info!("Saved 02_media_tab.png");

    // -- Screenshot 3: MODS top tab --
    bottom_bar.active_tab = MediaTab::None;
    status_bar.active_tab = oasis_core::statusbar::TopTab::Mods;
    hide_media_page(&mut sdi);
    dashboard.update_sdi(&mut sdi);
    status_bar.update_sdi(&mut sdi);
    bottom_bar.update_sdi(&mut sdi);
    mouse_cursor.update_sdi(&mut sdi);
    render_and_save(
        &mut backend,
        &mut sdi,
        w,
        h,
        out_dir.join("03_mods_tab.png"),
    )?;
    log::info!("Saved 03_mods_tab.png");

    // -- Screenshot 4: Terminal mode --
    dashboard.hide_sdi(&mut sdi);
    StatusBar::hide_sdi(&mut sdi);
    BottomBar::hide_sdi(&mut sdi);
    hide_media_page(&mut sdi);
    setup_terminal_objects(
        &mut sdi,
        &[
            "OASIS_OS v0.1.0 -- Type 'help' for commands".to_string(),
            "F1=terminal  F2=on-screen keyboard  Escape=quit".to_string(),
            String::new(),
            "> status".to_string(),
            "System: OASIS_OS v0.1.0  CPU: 333MHz  Battery: 75%".to_string(),
        ],
        "/home/user",
        "ls",
    );
    mouse_cursor.update_sdi(&mut sdi);
    render_and_save(
        &mut backend,
        &mut sdi,
        w,
        h,
        out_dir.join("04_terminal.png"),
    )?;
    log::info!("Saved 04_terminal.png");

    backend.shutdown()?;

    println!("Screenshots saved to screenshots/");
    println!("Compare against Psixpsp.png at the repo root.");
    Ok(())
}

/// Render the current SDI scene and save a PNG screenshot.
fn render_and_save(
    backend: &mut SdlBackend,
    sdi: &mut SdiRegistry,
    w: u32,
    h: u32,
    path: std::path::PathBuf,
) -> anyhow::Result<()> {
    backend.clear(Color::rgb(10, 10, 18))?;
    sdi.draw(backend)?;
    backend.swap_buffers()?;

    // Need to render again after swap so read_pixels gets the presented frame.
    backend.clear(Color::rgb(10, 10, 18))?;
    sdi.draw(backend)?;

    let pixels = backend.read_pixels(0, 0, w, h)?;
    save_png(&path, w, h, &pixels)?;
    Ok(())
}

/// Save RGBA pixel data as a PNG file.
fn save_png(path: &Path, width: u32, height: u32, rgba: &[u8]) -> anyhow::Result<()> {
    let file = fs::File::create(path)?;
    let writer = std::io::BufWriter::new(file);
    let mut encoder = png::Encoder::new(writer, width, height);
    encoder.set_color(png::ColorType::Rgba);
    encoder.set_depth(png::BitDepth::Eight);
    let mut writer = encoder.write_header()?;
    writer.write_image_data(rgba)?;
    Ok(())
}

fn update_media_page(sdi: &mut SdiRegistry, bottom_bar: &BottomBar) {
    let page_name = "media_page_text";
    if !sdi.contains(page_name) {
        let obj = sdi.create(page_name);
        obj.font_size = 14;
        obj.text_color = Color::rgb(160, 200, 180);
        obj.w = 0;
        obj.h = 0;
    }
    if let Ok(obj) = sdi.get_mut(page_name) {
        obj.x = 160;
        obj.y = 120;
        obj.visible = true;
        obj.text = Some(format!("[ {} Page ]", bottom_bar.active_tab.label()));
    }
}

fn hide_media_page(sdi: &mut SdiRegistry) {
    for name in &["media_page_text", "media_page_hint"] {
        if let Ok(obj) = sdi.get_mut(name) {
            obj.visible = false;
        }
    }
}

fn setup_terminal_objects(
    sdi: &mut SdiRegistry,
    output_lines: &[String],
    cwd: &str,
    input_buf: &str,
) {
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

    let max_lines = 12;
    for i in 0..max_lines {
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

fn populate_demo_vfs(vfs: &mut MemoryVfs) {
    use oasis_core::vfs::Vfs;

    vfs.mkdir("/home").unwrap();
    vfs.mkdir("/home/user").unwrap();
    vfs.mkdir("/etc").unwrap();
    vfs.mkdir("/tmp").unwrap();
    vfs.write("/home/user/readme.txt", b"Welcome to OASIS_OS!")
        .unwrap();
    vfs.write("/etc/hostname", b"oasis").unwrap();
    vfs.write("/etc/version", b"0.1.0").unwrap();

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

    vfs.mkdir("/home/user/music").unwrap();
    vfs.mkdir("/home/user/photos").unwrap();
}
