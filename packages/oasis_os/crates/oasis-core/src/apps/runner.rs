//! App screen runner with title bar and scrollable content.

use crate::backend::{Color, SdiBackend};
use crate::dashboard::AppEntry;
use crate::input::Button;
use crate::sdi::SdiRegistry;
use crate::vfs::{EntryKind, Vfs};

/// Maximum lines visible in the app content area.
const MAX_VISIBLE_LINES: usize = 13;

/// Action returned by the app after handling input.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AppAction {
    /// App consumed the input, no mode change needed.
    None,
    /// User wants to exit this app and return to dashboard.
    Exit,
    /// App wants to switch to terminal mode.
    SwitchToTerminal,
}

/// Runtime state for a launched application screen.
#[derive(Debug)]
pub struct AppRunner {
    /// App display title.
    pub title: String,
    /// App path in VFS.
    pub path: String,
    /// Content lines displayed in the app area.
    pub lines: Vec<String>,
    /// Scroll offset (first visible line index).
    pub scroll: usize,
    /// Current directory for file-manager navigation.
    pub browse_dir: Option<String>,
    /// Path of the file currently being viewed (file viewer mode).
    pub viewing_file: Option<String>,
    /// Selected line index (relative to visible area).
    pub cursor: usize,
}

impl AppRunner {
    /// Launch an app from its dashboard entry.
    pub fn launch(app: &AppEntry, vfs: &dyn Vfs) -> Self {
        let title = app.title.clone();
        let path = app.path.clone();
        let mut runner = Self {
            title: title.clone(),
            path,
            lines: Vec::new(),
            scroll: 0,
            browse_dir: None,
            viewing_file: None,
            cursor: 0,
        };
        runner.init_content(&title, vfs);
        runner
    }

    /// Generate initial content based on the app title.
    fn init_content(&mut self, title: &str, vfs: &dyn Vfs) {
        match title {
            "File Manager" => {
                self.browse_dir = Some("/".to_string());
                self.lines = list_directory(vfs, "/");
            },
            "Settings" => {
                self.lines = vec![
                    "OASIS_OS Settings".to_string(),
                    "".to_string(),
                    "  Screen:     480 x 272".to_string(),
                    "  Skin:       Classic".to_string(),
                    "  Audio:      Enabled".to_string(),
                    "  Network:    Enabled".to_string(),
                    "  Terminal:   Enabled".to_string(),
                    "  Plugins:    Enabled".to_string(),
                    "".to_string(),
                    "(Settings are read-only in this build)".to_string(),
                ];
            },
            "Network" => {
                self.lines = vec![
                    "Network Status".to_string(),
                    "".to_string(),
                    "  Interface:  lo (loopback)".to_string(),
                    "  Status:     Active".to_string(),
                    "  Address:    127.0.0.1".to_string(),
                    "".to_string(),
                    "  Remote:     Not connected".to_string(),
                    "  Listener:   Not running".to_string(),
                    "".to_string(),
                    "Use terminal 'listen' and 'connect'".to_string(),
                    "commands for remote access.".to_string(),
                ];
            },
            "Music Player" => {
                let dir = "/home/user/music";
                self.browse_dir = Some(dir.to_string());
                if vfs.exists(dir) {
                    self.lines = list_directory(vfs, dir);
                } else {
                    self.lines = vec![
                        "(Music directory not found)".to_string(),
                        "".to_string(),
                        "Create /home/user/music/ and add files.".to_string(),
                    ];
                }
            },
            "Photo Viewer" => {
                let dir = "/home/user/photos";
                self.browse_dir = Some(dir.to_string());
                if vfs.exists(dir) {
                    self.lines = list_directory(vfs, dir);
                } else {
                    self.lines = vec![
                        "(Photos directory not found)".to_string(),
                        "".to_string(),
                        "Create /home/user/photos/ and add files.".to_string(),
                    ];
                }
            },
            "Package Manager" => {
                self.lines = vec![
                    "Package Manager".to_string(),
                    "".to_string(),
                    "Installed packages:".to_string(),
                    "  oasis-core      0.1.0  (system)".to_string(),
                    "  oasis-sdl       0.1.0  (backend)".to_string(),
                    "  classic-skin    1.0.0  (skin)".to_string(),
                    "".to_string(),
                    "No updates available.".to_string(),
                ];
            },
            "System Monitor" => {
                self.lines = vec![
                    "System Monitor".to_string(),
                    "".to_string(),
                    "  Platform:   Desktop (SDL2)".to_string(),
                    "  Backend:    SDL2 accelerated".to_string(),
                    "  VFS:        MemoryVfs".to_string(),
                    "  Uptime:     (not tracked)".to_string(),
                    "".to_string(),
                    "  CPU:        --".to_string(),
                    "  Memory:     --".to_string(),
                    "  Battery:    N/A (desktop)".to_string(),
                ];
            },
            _ => {
                self.lines = vec![
                    format!("{title}"),
                    "".to_string(),
                    "(No content available for this app)".to_string(),
                ];
            },
        }
    }

    /// Handle input while the app is active.
    pub fn handle_input(&mut self, button: &Button, vfs: &dyn Vfs) -> AppAction {
        match button {
            Button::Cancel => {
                // If viewing a file, go back to directory listing.
                if self.viewing_file.is_some() {
                    self.viewing_file = None;
                    self.scroll = 0;
                    self.cursor = 0;
                    // Refresh directory listing.
                    if let Some(ref dir) = self.browse_dir {
                        self.lines = list_directory(vfs, dir);
                    }
                    return AppAction::None;
                }
                AppAction::Exit
            },
            Button::Up => {
                if self.cursor > 0 {
                    self.cursor -= 1;
                } else if self.scroll > 0 {
                    self.scroll -= 1;
                }
                AppAction::None
            },
            Button::Down => {
                let visible = self.visible_count();
                if self.cursor + 1 < visible {
                    self.cursor += 1;
                } else if self.scroll + MAX_VISIBLE_LINES < self.lines.len() {
                    self.scroll += 1;
                }
                AppAction::None
            },
            Button::Confirm => {
                // In file manager, enter selected directory or view file.
                if self.browse_dir.is_some() && self.viewing_file.is_none() {
                    self.enter_selected(vfs);
                }
                // Terminal app redirects to terminal mode.
                if self.title == "Terminal" {
                    return AppAction::SwitchToTerminal;
                }
                AppAction::None
            },
            _ => AppAction::None,
        }
    }

    /// Render app content directly into a windowed content area.
    ///
    /// Unlike `update_sdi()` which creates named SDI objects for full-screen
    /// display, this method draws directly into the clip region provided by the
    /// window manager's `draw_with_clips` callback.
    pub fn draw_windowed(
        &self,
        cx: i32,
        cy: i32,
        cw: u32,
        ch: u32,
        backend: &mut dyn SdiBackend,
    ) -> crate::error::Result<()> {
        // Content background.
        backend.fill_rect(cx, cy, cw, ch, Color::rgb(12, 12, 20))?;

        // Title row with dir/file suffix.
        let dir_suffix = if let Some(ref file) = self.viewing_file {
            format!("  [{file}]")
        } else {
            self.browse_dir
                .as_deref()
                .map(|d| format!("  [{d}]"))
                .unwrap_or_default()
        };
        let title_text = format!("{}{dir_suffix}", self.title);
        backend.draw_text(&title_text, cx + 4, cy + 2, 12, Color::WHITE)?;

        // Separator line.
        backend.fill_rect(cx, cy + 18, cw, 1, Color::rgb(60, 60, 80))?;

        // Content lines.
        let max_lines = ((ch as i32 - 24) / 16).max(0) as usize;
        let visible = self.lines.len().saturating_sub(self.scroll).min(max_lines);
        for i in 0..visible {
            let line_idx = self.scroll + i;
            let line = &self.lines[line_idx];
            let prefix = if i == self.cursor { "> " } else { "  " };
            let text = format!("{prefix}{line}");
            let text_color = if i == self.cursor {
                Color::rgb(100, 200, 255)
            } else {
                Color::rgb(180, 180, 200)
            };
            let y = cy + 22 + i as i32 * 16;
            backend.draw_text(&text, cx + 4, y, 12, text_color)?;
        }

        // Scroll indicator at bottom-left.
        let scroll_text = if self.lines.len() > max_lines {
            format!(
                "[{}/{}]  Cancel=back",
                self.scroll + 1,
                self.lines.len().saturating_sub(max_lines) + 1,
            )
        } else {
            "Cancel=back".to_string()
        };
        let scroll_y = cy + ch as i32 - 14;
        backend.draw_text(
            &scroll_text,
            cx + 4,
            scroll_y,
            10,
            Color::rgb(100, 100, 130),
        )?;

        Ok(())
    }

    /// Number of currently visible content lines.
    fn visible_count(&self) -> usize {
        let remaining = self.lines.len().saturating_sub(self.scroll);
        remaining.min(MAX_VISIBLE_LINES)
    }

    /// File manager / photo viewer: enter directory or open file.
    fn enter_selected(&mut self, vfs: &dyn Vfs) {
        let abs_idx = self.scroll + self.cursor;
        let Some(line) = self.lines.get(abs_idx) else {
            return;
        };
        let line = line.trim().to_string();

        let Some(ref dir) = self.browse_dir else {
            return;
        };

        if line == ".." {
            // Go up.
            let parent = if dir == "/" {
                "/".to_string()
            } else {
                let trimmed = dir.trim_end_matches('/');
                match trimmed.rfind('/') {
                    Some(0) => "/".to_string(),
                    Some(pos) => trimmed[..pos].to_string(),
                    None => "/".to_string(),
                }
            };
            self.browse_dir = Some(parent.clone());
            self.lines = list_directory(vfs, &parent);
            self.scroll = 0;
            self.cursor = 0;
        } else if line.ends_with('/') {
            // Enter subdirectory.
            let name = &line[..line.len() - 1];
            let new_dir = if dir == "/" {
                format!("/{name}")
            } else {
                format!("{dir}/{name}")
            };
            self.browse_dir = Some(new_dir.clone());
            self.lines = list_directory(vfs, &new_dir);
            self.scroll = 0;
            self.cursor = 0;
        } else {
            // It's a file -- extract the filename (strip size suffix).
            let file_name = line.split("  (").next().unwrap_or(&line);
            let file_path = if dir == "/" {
                format!("/{file_name}")
            } else {
                format!("{dir}/{file_name}")
            };
            self.open_file(vfs, &file_path);
        }
    }

    /// Open a file and display its contents.
    /// Dispatches to app-specific viewers for Music Player and Photo Viewer.
    pub fn open_file(&mut self, vfs: &dyn Vfs, path: &str) {
        // Only open files that actually exist in the VFS.
        if !vfs.exists(path) {
            return;
        }
        self.viewing_file = Some(path.to_string());
        self.scroll = 0;
        self.cursor = 0;

        let data = match vfs.read(path) {
            Ok(d) => d,
            Err(e) => {
                self.lines = vec![
                    format!("Error reading file: {e}"),
                    "Cancel=back".to_string(),
                ];
                return;
            },
        };

        self.lines = match self.title.as_str() {
            "Music Player" => view_audio_file(path, &data),
            "Photo Viewer" => view_image_file(path, &data),
            _ => view_generic_file(path, &data),
        };
    }

    /// Render the app screen to SDI objects.
    pub fn update_sdi(&self, sdi: &mut SdiRegistry) {
        // Full-screen background.
        if !sdi.contains("app_bg") {
            sdi.create("app_bg");
        }
        if let Ok(obj) = sdi.get_mut("app_bg") {
            obj.x = 0;
            obj.y = 0;
            obj.w = 480;
            obj.h = 272;
            obj.color = Color::rgb(12, 12, 20);
            obj.visible = true;
            obj.z = 100;
        }

        // Title bar background.
        if !sdi.contains("app_title_bg") {
            sdi.create("app_title_bg");
        }
        if let Ok(obj) = sdi.get_mut("app_title_bg") {
            obj.x = 0;
            obj.y = 0;
            obj.w = 480;
            obj.h = 22;
            obj.color = Color::rgb(30, 50, 90);
            obj.visible = true;
            obj.z = 101;
        }

        // Title text.
        if !sdi.contains("app_title_text") {
            sdi.create("app_title_text");
        }
        if let Ok(obj) = sdi.get_mut("app_title_text") {
            let dir_suffix = if let Some(ref file) = self.viewing_file {
                format!("  [{file}]")
            } else {
                self.browse_dir
                    .as_deref()
                    .map(|d| format!("  [{d}]"))
                    .unwrap_or_default()
            };
            obj.text = Some(format!("{}{dir_suffix}", self.title));
            obj.x = 8;
            obj.y = 4;
            obj.font_size = 12;
            obj.text_color = Color::WHITE;
            obj.w = 0;
            obj.h = 0;
            obj.visible = true;
            obj.z = 102;
        }

        // Content lines.
        for i in 0..MAX_VISIBLE_LINES {
            let name = format!("app_line_{i}");
            if !sdi.contains(&name) {
                sdi.create(&name);
            }
            if let Ok(obj) = sdi.get_mut(&name) {
                let line_idx = self.scroll + i;
                if line_idx < self.lines.len() {
                    let prefix = if i == self.cursor { "> " } else { "  " };
                    obj.text = Some(format!("{prefix}{}", self.lines[line_idx]));
                    obj.visible = true;
                } else {
                    obj.text = None;
                    obj.visible = false;
                }
                obj.x = 8;
                obj.y = 26 + (i as i32) * 18;
                obj.font_size = 12;
                obj.text_color = if i == self.cursor {
                    Color::rgb(100, 200, 255)
                } else {
                    Color::rgb(180, 180, 200)
                };
                obj.w = 0;
                obj.h = 0;
                obj.z = 102;
            }
        }

        // Scroll indicator.
        if !sdi.contains("app_scroll") {
            sdi.create("app_scroll");
        }
        if let Ok(obj) = sdi.get_mut("app_scroll") {
            if self.lines.len() > MAX_VISIBLE_LINES {
                obj.text = Some(format!(
                    "[{}/{}]  Cancel=back",
                    self.scroll + 1,
                    self.lines.len().saturating_sub(MAX_VISIBLE_LINES) + 1,
                ));
            } else {
                obj.text = Some("Cancel=back".to_string());
            }
            obj.x = 8;
            obj.y = 258;
            obj.font_size = 10;
            obj.text_color = Color::rgb(100, 100, 130);
            obj.w = 0;
            obj.h = 0;
            obj.visible = true;
            obj.z = 102;
        }
    }

    /// Hide all app-related SDI objects.
    pub fn hide_sdi(sdi: &mut SdiRegistry) {
        let fixed = ["app_bg", "app_title_bg", "app_title_text", "app_scroll"];
        for name in &fixed {
            if let Ok(obj) = sdi.get_mut(name) {
                obj.visible = false;
            }
        }
        for i in 0..MAX_VISIBLE_LINES {
            let name = format!("app_line_{i}");
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.visible = false;
            }
        }
    }
}

/// View an audio file: parse headers and show track metadata.
fn view_audio_file(path: &str, data: &[u8]) -> Vec<String> {
    let filename = path.rsplit('/').next().unwrap_or(path);
    let mut lines = vec![format!("=== Now Viewing: {filename} ==="), String::new()];

    let size_kb = data.len() / 1024;
    let ext = filename.rsplit('.').next().unwrap_or("").to_lowercase();

    // Detect format and parse headers.
    if data.len() >= 4 && &data[..4] == b"RIFF" && data.len() >= 44 && &data[8..12] == b"WAVE" {
        // WAV file -- parse header.
        let channels = u16::from_le_bytes([data[22], data[23]]);
        let sample_rate = u32::from_le_bytes([data[24], data[25], data[26], data[27]]);
        let bits = u16::from_le_bytes([data[34], data[35]]);
        let data_size = if data.len() >= 44 {
            u32::from_le_bytes([data[40], data[41], data[42], data[43]])
        } else {
            0
        };
        let duration_secs = if sample_rate > 0 && channels > 0 && bits > 0 {
            data_size as f64 / (sample_rate as f64 * channels as f64 * (bits as f64 / 8.0))
        } else {
            0.0
        };

        lines.push("  Format:       WAV (PCM audio)".to_string());
        lines.push(format!("  Sample Rate:  {sample_rate} Hz"));
        lines.push(format!("  Channels:     {channels}"));
        lines.push(format!("  Bit Depth:    {bits}-bit"));
        lines.push(format!("  Duration:     {duration_secs:.1}s"));
        lines.push(format!("  File Size:    {size_kb} KB"));
    } else if data.len() >= 3 && (data[..2] == [0xFF, 0xFB] || data[..3] == *b"ID3") {
        // MP3 file.
        lines.push("  Format:       MP3 (MPEG audio)".to_string());
        lines.push(format!("  File Size:    {size_kb} KB"));

        // Try to extract ID3v2 title/artist.
        if data.len() > 10 && &data[..3] == b"ID3" {
            let id3_info = parse_id3v2_basic(data);
            if let Some(title) = id3_info.0 {
                lines.push(format!("  Title:        {title}"));
            }
            if let Some(artist) = id3_info.1 {
                lines.push(format!("  Artist:       {artist}"));
            }
        }

        // Rough duration estimate from file size (128kbps average).
        let est_secs = (data.len() as f64) / (128.0 * 1024.0 / 8.0);
        lines.push(format!("  Duration:     ~{est_secs:.0}s (estimated)"));
    } else {
        lines.push(format!("  Format:       {ext} audio"));
        lines.push(format!("  File Size:    {size_kb} KB"));
    }

    lines.push(String::new());
    lines.push("----------------------------------".to_string());
    lines.push(String::new());
    lines.push("  To play in terminal:".to_string());
    lines.push("    music play".to_string());
    lines.push("    music pause / music stop".to_string());
    lines.push("    music vol <0-100>".to_string());
    lines.push(String::new());
    lines.push("Cancel=back to library".to_string());
    lines
}

/// Try to extract title and artist from an ID3v2 tag.
/// Returns (Option<title>, Option<artist>).
fn parse_id3v2_basic(data: &[u8]) -> (Option<String>, Option<String>) {
    if data.len() < 10 || &data[..3] != b"ID3" {
        return (None, None);
    }
    let header_size = ((data[6] as usize & 0x7F) << 21)
        | ((data[7] as usize & 0x7F) << 14)
        | ((data[8] as usize & 0x7F) << 7)
        | (data[9] as usize & 0x7F);
    let end = (10 + header_size).min(data.len());

    let mut title = None;
    let mut artist = None;
    let mut pos = 10;

    while pos + 10 < end {
        let frame_id = &data[pos..pos + 4];
        let frame_size =
            u32::from_be_bytes([data[pos + 4], data[pos + 5], data[pos + 6], data[pos + 7]])
                as usize;
        if frame_size == 0 || pos + 10 + frame_size > end {
            break;
        }
        let frame_data = &data[pos + 10..pos + 10 + frame_size];
        // Skip encoding byte, extract as lossy UTF-8.
        let text = if frame_data.len() > 1 {
            String::from_utf8_lossy(&frame_data[1..])
                .trim_matches('\0')
                .to_string()
        } else {
            String::new()
        };

        if frame_id == b"TIT2" && !text.is_empty() {
            title = Some(text);
        } else if frame_id == b"TPE1" && !text.is_empty() {
            artist = Some(text);
        }

        pos += 10 + frame_size;
    }

    (title, artist)
}

/// View an image file: parse headers and show image metadata.
fn view_image_file(path: &str, data: &[u8]) -> Vec<String> {
    let filename = path.rsplit('/').next().unwrap_or(path);
    let mut lines = vec![format!("=== Photo: {filename} ==="), String::new()];

    let size_kb = data.len() / 1024;

    if data.len() >= 24 && &data[..8] == b"\x89PNG\r\n\x1a\n" {
        // PNG -- IHDR is at offset 8 (4 len + 4 type + data).
        let w = u32::from_be_bytes([data[16], data[17], data[18], data[19]]);
        let h = u32::from_be_bytes([data[20], data[21], data[22], data[23]]);
        let bit_depth = data[24];
        let color_type = data[25];
        let color_name = match color_type {
            0 => "Grayscale",
            2 => "RGB",
            3 => "Indexed",
            4 => "Grayscale+Alpha",
            6 => "RGBA",
            _ => "Unknown",
        };

        lines.push("  Format:       PNG".to_string());
        lines.push(format!("  Dimensions:   {w} x {h} pixels"));
        lines.push(format!("  Color:        {color_name} ({bit_depth}-bit)"));
        lines.push(format!("  File Size:    {size_kb} KB"));
    } else if data.len() >= 2 && data[..2] == [0xFF, 0xD8] {
        // JPEG.
        let (w, h) = parse_jpeg_dimensions(data);
        lines.push("  Format:       JPEG".to_string());
        if w > 0 && h > 0 {
            lines.push(format!("  Dimensions:   {w} x {h} pixels"));
        }
        lines.push(format!("  File Size:    {size_kb} KB"));
    } else if data.len() >= 6 && (&data[..4] == b"GIF8") {
        // GIF.
        let w = u16::from_le_bytes([data[6], data[7]]);
        let h = u16::from_le_bytes([data[8], data[9]]);
        lines.push("  Format:       GIF".to_string());
        lines.push(format!("  Dimensions:   {w} x {h} pixels"));
        lines.push(format!("  File Size:    {size_kb} KB"));
    } else if data.len() >= 12 && &data[..4] == b"RIFF" && &data[8..12] == b"WEBP" {
        // WebP.
        lines.push("  Format:       WebP".to_string());
        lines.push(format!("  File Size:    {size_kb} KB"));
    } else {
        let ext = filename.rsplit('.').next().unwrap_or("").to_lowercase();
        lines.push(format!("  Format:       {ext} image"));
        lines.push(format!("  File Size:    {size_kb} KB"));
    }

    lines.push(String::new());
    lines.push("----------------------------------".to_string());
    lines.push(String::new());
    lines.push("  (Image preview not available".to_string());
    lines.push("   in text mode)".to_string());
    lines.push(String::new());
    lines.push("Cancel=back to gallery".to_string());
    lines
}

/// Try to extract JPEG image dimensions from SOF markers.
fn parse_jpeg_dimensions(data: &[u8]) -> (u16, u16) {
    let mut pos = 2;
    while pos + 4 < data.len() {
        if data[pos] != 0xFF {
            break;
        }
        let marker = data[pos + 1];
        // SOF0..SOF3 markers contain dimensions.
        if (0xC0..=0xC3).contains(&marker) && pos + 9 < data.len() {
            let h = u16::from_be_bytes([data[pos + 5], data[pos + 6]]);
            let w = u16::from_be_bytes([data[pos + 7], data[pos + 8]]);
            return (w, h);
        }
        if marker == 0xD9 || marker == 0xDA {
            break; // End of headers.
        }
        let seg_len = u16::from_be_bytes([data[pos + 2], data[pos + 3]]) as usize;
        pos += 2 + seg_len;
    }
    (0, 0)
}

/// Generic file viewer: text content or hex dump.
fn view_generic_file(path: &str, data: &[u8]) -> Vec<String> {
    let filename = path.rsplit('/').next().unwrap_or(path);
    let mut lines = vec![format!("--- {filename} ---"), String::new()];

    let is_text = data.len() < 64 * 1024 && std::str::from_utf8(data).is_ok();
    if is_text {
        let text = String::from_utf8_lossy(data);
        for line in text.lines() {
            lines.push(line.to_string());
        }
        if data.is_empty() {
            lines.push("(empty file)".to_string());
        }
    } else {
        lines.push(format!("Binary file  ({} bytes)", data.len()));
        lines.push(String::new());
        for (i, chunk) in data.chunks(16).enumerate().take(8) {
            let hex: Vec<String> = chunk.iter().map(|b| format!("{b:02x}")).collect();
            let ascii: String = chunk
                .iter()
                .map(|&b| {
                    if (0x20..=0x7e).contains(&b) {
                        b as char
                    } else {
                        '.'
                    }
                })
                .collect();
            lines.push(format!("{:04x}  {:<48}  {ascii}", i * 16, hex.join(" ")));
        }
        if data.len() > 128 {
            lines.push(format!("... ({} more bytes)", data.len() - 128));
        }
    }

    lines.push(String::new());
    lines.push("Cancel=back".to_string());
    lines
}

/// List a VFS directory, returning display lines.
fn list_directory(vfs: &dyn Vfs, path: &str) -> Vec<String> {
    let mut lines = Vec::new();

    // Parent link (unless at root).
    if path != "/" {
        lines.push("..".to_string());
    }

    match vfs.readdir(path) {
        Ok(entries) => {
            // Directories first, then files.
            let mut dirs: Vec<_> = entries
                .iter()
                .filter(|e| e.kind == EntryKind::Directory)
                .collect();
            let mut files: Vec<_> = entries
                .iter()
                .filter(|e| e.kind == EntryKind::File)
                .collect();
            dirs.sort_by(|a, b| a.name.cmp(&b.name));
            files.sort_by(|a, b| a.name.cmp(&b.name));

            for d in &dirs {
                lines.push(format!("{}/", d.name));
            }
            for f in &files {
                let size = f.size;
                if size >= 1024 {
                    lines.push(format!("{}  ({} KB)", f.name, size / 1024));
                } else {
                    lines.push(format!("{}  ({size} B)", f.name));
                }
            }

            if dirs.is_empty() && files.is_empty() {
                lines.push("(empty directory)".to_string());
            }
        },
        Err(e) => {
            lines.push(format!("Error reading directory: {e}"));
        },
    }

    lines
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::backend::Color;
    use crate::dashboard::AppEntry;
    use crate::vfs::MemoryVfs;

    fn make_app(title: &str) -> AppEntry {
        AppEntry {
            title: title.to_string(),
            path: format!("/apps/{title}"),
            icon_png: Vec::new(),
            color: Color::rgb(100, 100, 100),
        }
    }

    fn setup_vfs() -> MemoryVfs {
        use crate::vfs::Vfs;
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/home").unwrap();
        vfs.mkdir("/home/user").unwrap();
        vfs.mkdir("/home/user/music").unwrap();
        vfs.mkdir("/home/user/photos").unwrap();
        vfs.mkdir("/etc").unwrap();
        vfs.mkdir("/tmp").unwrap();
        vfs.write("/home/user/readme.txt", b"Hello!").unwrap();
        vfs.write("/etc/hostname", b"oasis").unwrap();
        // Sample music tracks.
        vfs.write(
            "/home/user/music/ambient_dawn.mp3",
            b"fake-mp3-data-ambient",
        )
        .unwrap();
        vfs.write(
            "/home/user/music/nightfall_theme.mp3",
            b"fake-mp3-data-nightfall",
        )
        .unwrap();
        // Sample photo.
        vfs.write("/home/user/photos/sunset.png", b"\x89PNG\r\n\x1a\nfake-png")
            .unwrap();
        vfs
    }

    #[test]
    fn launch_file_manager() {
        let vfs = setup_vfs();
        let runner = AppRunner::launch(&make_app("File Manager"), &vfs);
        assert_eq!(runner.title, "File Manager");
        assert!(runner.browse_dir.is_some());
        assert!(!runner.lines.is_empty());
        // Root should list etc, home, tmp directories.
        assert!(runner.lines.iter().any(|l| l.contains("home")));
    }

    #[test]
    fn launch_settings() {
        let vfs = setup_vfs();
        let runner = AppRunner::launch(&make_app("Settings"), &vfs);
        assert!(runner.lines.iter().any(|l| l.contains("480")));
    }

    #[test]
    fn launch_generic_app() {
        let vfs = setup_vfs();
        let runner = AppRunner::launch(&make_app("Unknown App"), &vfs);
        assert!(runner.lines.iter().any(|l| l.contains("No content")));
    }

    #[test]
    fn file_manager_navigate_down() {
        let vfs = setup_vfs();
        let mut runner = AppRunner::launch(&make_app("File Manager"), &vfs);
        assert_eq!(runner.cursor, 0);
        runner.handle_input(&Button::Down, &vfs);
        assert_eq!(runner.cursor, 1);
    }

    #[test]
    fn file_manager_enter_directory() {
        let vfs = setup_vfs();
        let mut runner = AppRunner::launch(&make_app("File Manager"), &vfs);
        // Find the "home/" entry and navigate to it.
        let home_idx = runner
            .lines
            .iter()
            .position(|l| l.starts_with("home"))
            .expect("home/ should be in listing");
        runner.cursor = home_idx;
        runner.handle_input(&Button::Confirm, &vfs);
        assert_eq!(runner.browse_dir.as_deref(), Some("/home"));
        assert!(runner.lines.iter().any(|l| l.contains("user")));
    }

    #[test]
    fn file_manager_go_up() {
        let vfs = setup_vfs();
        let mut runner = AppRunner::launch(&make_app("File Manager"), &vfs);
        // Enter /home first.
        let home_idx = runner
            .lines
            .iter()
            .position(|l| l.starts_with("home"))
            .expect("home/ should be in listing");
        runner.cursor = home_idx;
        runner.handle_input(&Button::Confirm, &vfs);
        assert_eq!(runner.browse_dir.as_deref(), Some("/home"));

        // Now go back up via ".."
        runner.cursor = 0; // ".." is always first line in non-root.
        runner.handle_input(&Button::Confirm, &vfs);
        assert_eq!(runner.browse_dir.as_deref(), Some("/"));
    }

    #[test]
    fn cancel_exits_app() {
        let vfs = setup_vfs();
        let mut runner = AppRunner::launch(&make_app("Settings"), &vfs);
        let action = runner.handle_input(&Button::Cancel, &vfs);
        assert_eq!(action, AppAction::Exit);
    }

    #[test]
    fn terminal_app_switches_mode() {
        let vfs = setup_vfs();
        let mut runner = AppRunner::launch(&make_app("Terminal"), &vfs);
        let action = runner.handle_input(&Button::Confirm, &vfs);
        assert_eq!(action, AppAction::SwitchToTerminal);
    }

    #[test]
    fn scroll_down_when_content_exceeds_view() {
        let vfs = setup_vfs();
        let mut runner = AppRunner::launch(&make_app("Settings"), &vfs);
        // Settings has ~10 lines, visible is 13, so no scroll needed.
        // But test the mechanism by adding more lines.
        for i in 0..20 {
            runner.lines.push(format!("Extra line {i}"));
        }
        // Move cursor to bottom of visible area.
        for _ in 0..MAX_VISIBLE_LINES - 1 {
            runner.handle_input(&Button::Down, &vfs);
        }
        assert_eq!(runner.cursor, MAX_VISIBLE_LINES - 1);
        // Next down should scroll.
        runner.handle_input(&Button::Down, &vfs);
        assert_eq!(runner.scroll, 1);
    }

    #[test]
    fn update_sdi_creates_objects() {
        let vfs = setup_vfs();
        let runner = AppRunner::launch(&make_app("Settings"), &vfs);
        let mut sdi = SdiRegistry::new();
        runner.update_sdi(&mut sdi);
        assert!(sdi.contains("app_bg"));
        assert!(sdi.contains("app_title_bg"));
        assert!(sdi.contains("app_title_text"));
        assert!(sdi.contains("app_line_0"));
        assert!(sdi.contains("app_scroll"));
    }

    #[test]
    fn hide_sdi_hides_objects() {
        let vfs = setup_vfs();
        let runner = AppRunner::launch(&make_app("Settings"), &vfs);
        let mut sdi = SdiRegistry::new();
        runner.update_sdi(&mut sdi);
        AppRunner::hide_sdi(&mut sdi);
        assert!(!sdi.get("app_bg").unwrap().visible);
        assert!(!sdi.get("app_title_bg").unwrap().visible);
    }

    #[test]
    fn list_directory_root() {
        let vfs = setup_vfs();
        let lines = list_directory(&vfs, "/");
        // Root has no ".." entry.
        assert!(!lines.iter().any(|l| l == ".."));
        // Should have directories.
        assert!(lines.iter().any(|l| l.starts_with("home")));
    }

    #[test]
    fn list_directory_shows_sizes() {
        let vfs = setup_vfs();
        let lines = list_directory(&vfs, "/home/user");
        // readme.txt is 6 bytes.
        assert!(
            lines
                .iter()
                .any(|l| l.contains("readme.txt") && l.contains("6 B"))
        );
    }

    #[test]
    fn file_manager_open_file() {
        let vfs = setup_vfs();
        let mut runner = AppRunner::launch(&make_app("File Manager"), &vfs);
        // Navigate to /home/user.
        let home_idx = runner
            .lines
            .iter()
            .position(|l| l.starts_with("home"))
            .unwrap();
        runner.cursor = home_idx;
        runner.handle_input(&Button::Confirm, &vfs);
        let user_idx = runner
            .lines
            .iter()
            .position(|l| l.starts_with("user"))
            .unwrap();
        runner.cursor = user_idx;
        runner.handle_input(&Button::Confirm, &vfs);
        // Now select readme.txt.
        let file_idx = runner
            .lines
            .iter()
            .position(|l| l.contains("readme.txt"))
            .unwrap();
        runner.cursor = file_idx;
        runner.handle_input(&Button::Confirm, &vfs);
        // Should be in file viewer mode.
        assert!(runner.viewing_file.is_some());
        assert!(runner.lines.iter().any(|l| l.contains("Hello!")));
    }

    #[test]
    fn file_viewer_cancel_returns_to_dir() {
        let vfs = setup_vfs();
        let mut runner = AppRunner::launch(&make_app("File Manager"), &vfs);
        // Navigate to /home/user and open readme.txt.
        let home_idx = runner
            .lines
            .iter()
            .position(|l| l.starts_with("home"))
            .unwrap();
        runner.cursor = home_idx;
        runner.handle_input(&Button::Confirm, &vfs);
        let user_idx = runner
            .lines
            .iter()
            .position(|l| l.starts_with("user"))
            .unwrap();
        runner.cursor = user_idx;
        runner.handle_input(&Button::Confirm, &vfs);
        let file_idx = runner
            .lines
            .iter()
            .position(|l| l.contains("readme.txt"))
            .unwrap();
        runner.cursor = file_idx;
        runner.handle_input(&Button::Confirm, &vfs);
        assert!(runner.viewing_file.is_some());
        // Cancel should return to directory, not exit app.
        let action = runner.handle_input(&Button::Cancel, &vfs);
        assert_eq!(action, AppAction::None);
        assert!(runner.viewing_file.is_none());
        assert!(runner.lines.iter().any(|l| l.contains("readme.txt")));
    }

    #[test]
    fn file_viewer_binary_file() {
        use crate::vfs::Vfs;
        let mut vfs = setup_vfs();
        vfs.write("/home/user/data.bin", &[0x00, 0x01, 0xFF, 0xFE, 0x80])
            .unwrap();
        let mut runner = AppRunner::launch(&make_app("File Manager"), &vfs);
        runner.browse_dir = Some("/home/user".to_string());
        runner.lines = list_directory(&vfs, "/home/user");
        let file_idx = runner
            .lines
            .iter()
            .position(|l| l.contains("data.bin"))
            .unwrap();
        runner.cursor = file_idx;
        runner.handle_input(&Button::Confirm, &vfs);
        assert!(runner.viewing_file.is_some());
        // Generic viewer shows hex dump for binary.
        assert!(runner.lines.iter().any(|l| l.contains("Binary file")));
        assert!(runner.lines.iter().any(|l| l.contains("00 01 ff fe")));
    }

    #[test]
    fn view_audio_wav_metadata() {
        // Minimal valid WAV header (44 bytes).
        let mut wav = Vec::new();
        wav.extend_from_slice(b"RIFF");
        wav.extend_from_slice(&36u32.to_le_bytes()); // file size - 8
        wav.extend_from_slice(b"WAVEfmt ");
        wav.extend_from_slice(&16u32.to_le_bytes()); // chunk size
        wav.extend_from_slice(&1u16.to_le_bytes()); // PCM
        wav.extend_from_slice(&2u16.to_le_bytes()); // channels
        wav.extend_from_slice(&44100u32.to_le_bytes()); // sample rate
        wav.extend_from_slice(&176400u32.to_le_bytes()); // byte rate
        wav.extend_from_slice(&4u16.to_le_bytes()); // block align
        wav.extend_from_slice(&16u16.to_le_bytes()); // bits per sample
        wav.extend_from_slice(b"data");
        wav.extend_from_slice(&0u32.to_le_bytes()); // data size

        let lines = view_audio_file("/music/test.wav", &wav);
        assert!(lines.iter().any(|l| l.contains("WAV")));
        assert!(lines.iter().any(|l| l.contains("44100")));
        assert!(lines.iter().any(|l| l.contains("2")));
        assert!(lines.iter().any(|l| l.contains("16-bit")));
    }

    #[test]
    fn view_audio_mp3_metadata() {
        // Fake MP3 with sync bytes.
        let data = vec![0xFF, 0xFB, 0x90, 0x00, 0x00];
        let lines = view_audio_file("/music/song.mp3", &data);
        assert!(lines.iter().any(|l| l.contains("MP3")));
        assert!(lines.iter().any(|l| l.contains("music play")));
    }

    #[test]
    fn view_image_png_metadata() {
        // Minimal PNG: 8-byte signature + IHDR chunk.
        let mut png = Vec::new();
        png.extend_from_slice(b"\x89PNG\r\n\x1a\n"); // signature
        png.extend_from_slice(&13u32.to_be_bytes()); // IHDR length
        png.extend_from_slice(b"IHDR");
        png.extend_from_slice(&480u32.to_be_bytes()); // width
        png.extend_from_slice(&272u32.to_be_bytes()); // height
        png.push(8); // bit depth
        png.push(6); // color type (RGBA)
        png.extend_from_slice(&[0, 0, 0]); // compression, filter, interlace

        let lines = view_image_file("/photos/test.png", &png);
        assert!(lines.iter().any(|l| l.contains("PNG")));
        assert!(lines.iter().any(|l| l.contains("480 x 272")));
        assert!(lines.iter().any(|l| l.contains("RGBA")));
    }

    #[test]
    fn view_image_jpeg_metadata() {
        // Minimal JPEG with SOF0 marker.
        let data = vec![
            0xFF, 0xD8, // SOI
            0xFF, 0xC0, // SOF0
            0x00, 0x0B, // length
            0x08, // precision
            0x01, 0x10, // height = 272
            0x01, 0xE0, // width = 480
            0x03, // components
            0x01, 0x22, 0x00,
        ];
        let lines = view_image_file("/photos/pic.jpg", &data);
        assert!(lines.iter().any(|l| l.contains("JPEG")));
        assert!(lines.iter().any(|l| l.contains("480 x 272")));
    }

    #[test]
    fn music_player_lists_tracks() {
        let vfs = setup_vfs();
        let runner = AppRunner::launch(&make_app("Music Player"), &vfs);
        assert!(runner.browse_dir.is_some());
        // Uses list_directory, so ".." is first, then files.
        assert!(runner.lines.iter().any(|l| l.contains("ambient_dawn")));
        assert!(runner.lines.iter().any(|l| l.contains("nightfall_theme")));
    }

    #[test]
    fn music_player_open_track() {
        let vfs = setup_vfs();
        let mut runner = AppRunner::launch(&make_app("Music Player"), &vfs);
        let track_idx = runner
            .lines
            .iter()
            .position(|l| l.contains("ambient_dawn"))
            .unwrap();
        runner.cursor = track_idx;
        runner.handle_input(&Button::Confirm, &vfs);
        // Should open audio viewer with track info and playback hints.
        assert!(runner.viewing_file.is_some());
        assert!(runner.lines.iter().any(|l| l.contains("Now Viewing")));
        assert!(runner.lines.iter().any(|l| l.contains("music play")));
    }

    #[test]
    fn music_player_empty() {
        use crate::vfs::Vfs;
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/home").unwrap();
        vfs.mkdir("/home/user").unwrap();
        // Music dir doesn't exist.
        let runner = AppRunner::launch(&make_app("Music Player"), &vfs);
        assert!(
            runner
                .lines
                .iter()
                .any(|l| l.contains("Music directory not found"))
        );
    }

    #[test]
    fn photo_viewer_lists_photos() {
        let vfs = setup_vfs();
        let runner = AppRunner::launch(&make_app("Photo Viewer"), &vfs);
        assert!(runner.browse_dir.is_some());
        assert!(runner.lines.iter().any(|l| l.contains("sunset.png")));
    }

    #[test]
    fn photo_viewer_open_image() {
        let vfs = setup_vfs();
        let mut runner = AppRunner::launch(&make_app("Photo Viewer"), &vfs);
        // Find sunset.png and open it.
        let photo_idx = runner
            .lines
            .iter()
            .position(|l| l.contains("sunset.png"))
            .unwrap();
        runner.cursor = photo_idx;
        runner.handle_input(&Button::Confirm, &vfs);
        // Photo viewer shows image metadata.
        assert!(runner.viewing_file.is_some());
        assert!(runner.lines.iter().any(|l| l.contains("Photo:")));
    }

    #[test]
    fn photo_viewer_cancel_from_view() {
        let vfs = setup_vfs();
        let mut runner = AppRunner::launch(&make_app("Photo Viewer"), &vfs);
        let photo_idx = runner
            .lines
            .iter()
            .position(|l| l.contains("sunset.png"))
            .unwrap();
        runner.cursor = photo_idx;
        runner.handle_input(&Button::Confirm, &vfs);
        assert!(runner.viewing_file.is_some());
        // Cancel returns to photo list.
        let action = runner.handle_input(&Button::Cancel, &vfs);
        assert_eq!(action, AppAction::None);
        assert!(runner.viewing_file.is_none());
        assert!(runner.lines.iter().any(|l| l.contains("sunset.png")));
    }

    #[test]
    fn photo_viewer_empty_dir() {
        use crate::vfs::Vfs;
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/home").unwrap();
        vfs.mkdir("/home/user").unwrap();
        vfs.mkdir("/home/user/photos").unwrap();
        let runner = AppRunner::launch(&make_app("Photo Viewer"), &vfs);
        // Empty dir shows "(empty directory)" via list_directory.
        assert!(runner.lines.iter().any(|l| l.contains("empty directory")));
    }

    #[test]
    fn open_file_skips_nonexistent() {
        let vfs = setup_vfs();
        let mut runner = AppRunner::launch(&make_app("File Manager"), &vfs);
        runner.open_file(&vfs, "/does/not/exist.txt");
        // Should not switch to viewer mode.
        assert!(runner.viewing_file.is_none());
    }
}
