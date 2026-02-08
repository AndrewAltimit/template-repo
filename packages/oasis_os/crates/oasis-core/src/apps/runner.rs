//! App screen runner with title bar and scrollable content.

use crate::backend::Color;
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
                self.lines = build_music_player_content(vfs);
            },
            "Photo Viewer" => {
                self.browse_dir = Some("/home/user/photos".to_string());
                self.lines = build_photo_viewer_content(vfs);
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
                        if self.title == "Photo Viewer" {
                            self.lines = build_photo_viewer_content(vfs);
                        } else {
                            self.lines = list_directory(vfs, dir);
                        }
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
    fn open_file(&mut self, vfs: &dyn Vfs, path: &str) {
        self.viewing_file = Some(path.to_string());
        self.scroll = 0;
        self.cursor = 0;

        let mut lines = Vec::new();
        let filename = path.rsplit('/').next().unwrap_or(path);
        lines.push(format!("--- {filename} ---"));
        lines.push(String::new());

        match vfs.read(path) {
            Ok(data) => {
                // Check if the data looks like text (all bytes are printable ASCII/UTF-8).
                let is_text = data.len() < 64 * 1024 && std::str::from_utf8(&data).is_ok();
                if is_text {
                    let text = String::from_utf8_lossy(&data);
                    for line in text.lines() {
                        lines.push(line.to_string());
                    }
                    if data.is_empty() {
                        lines.push("(empty file)".to_string());
                    }
                } else {
                    lines.push(format!("Binary file  ({} bytes)", data.len()));
                    lines.push(String::new());
                    // Show first 8 lines of hex dump.
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
            },
            Err(e) => {
                lines.push(format!("Error reading file: {e}"));
            },
        }

        lines.push(String::new());
        lines.push("Cancel=back".to_string());
        self.lines = lines;
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

/// Build Music Player content by scanning /home/user/music/ in the VFS.
fn build_music_player_content(vfs: &dyn Vfs) -> Vec<String> {
    let mut lines = vec!["Music Player".to_string(), String::new()];

    let music_dir = "/home/user/music";
    let tracks = if vfs.exists(music_dir) {
        match vfs.readdir(music_dir) {
            Ok(entries) => {
                let mut files: Vec<_> = entries
                    .into_iter()
                    .filter(|e| e.kind == EntryKind::File)
                    .collect();
                files.sort_by(|a, b| a.name.cmp(&b.name));
                files
            },
            Err(_) => Vec::new(),
        }
    } else {
        Vec::new()
    };

    if tracks.is_empty() {
        lines.push("(No tracks found)".to_string());
        lines.push(String::new());
        lines.push("Place audio files in /home/user/music/".to_string());
    } else {
        lines.push(format!("{} track(s):", tracks.len()));
        lines.push(String::new());
        for (i, track) in tracks.iter().enumerate() {
            let size_kb = track.size / 1024;
            lines.push(format!("  {}. {}  ({size_kb} KB)", i + 1, track.name));
        }
    }

    lines.push(String::new());
    lines.push("Controls: music play/pause/next/prev".to_string());
    lines.push("          music vol <0-100>".to_string());
    lines
}

/// Build Photo Viewer content by scanning /home/user/photos/ in the VFS.
fn build_photo_viewer_content(vfs: &dyn Vfs) -> Vec<String> {
    let mut lines = Vec::new();

    let photos_dir = "/home/user/photos";
    let photos = if vfs.exists(photos_dir) {
        match vfs.readdir(photos_dir) {
            Ok(entries) => {
                let mut files: Vec<_> = entries
                    .into_iter()
                    .filter(|e| e.kind == EntryKind::File)
                    .collect();
                files.sort_by(|a, b| a.name.cmp(&b.name));
                files
            },
            Err(_) => Vec::new(),
        }
    } else {
        Vec::new()
    };

    if photos.is_empty() {
        lines.push("(No images found)".to_string());
        lines.push(String::new());
        lines.push("Place image files in /home/user/photos/".to_string());
    } else {
        lines.push(format!("{} image(s):", photos.len()));
        lines.push(String::new());
        for photo in &photos {
            let size_kb = photo.size / 1024;
            if size_kb > 0 {
                lines.push(format!("{}  ({size_kb} KB)", photo.name));
            } else {
                lines.push(format!("{}  ({} B)", photo.name, photo.size));
            }
        }
    }

    lines.push(String::new());
    lines.push("Confirm=view  Cancel=back".to_string());
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
        assert!(runner.lines.iter().any(|l| l.contains("Binary file")));
        assert!(runner.lines.iter().any(|l| l.contains("00 01 ff fe")));
    }

    #[test]
    fn music_player_lists_tracks() {
        let vfs = setup_vfs();
        let runner = AppRunner::launch(&make_app("Music Player"), &vfs);
        assert!(runner.lines.iter().any(|l| l.contains("2 track(s)")));
        assert!(runner.lines.iter().any(|l| l.contains("ambient_dawn")));
        assert!(runner.lines.iter().any(|l| l.contains("nightfall_theme")));
    }

    #[test]
    fn music_player_empty() {
        use crate::vfs::Vfs;
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/home").unwrap();
        vfs.mkdir("/home/user").unwrap();
        let runner = AppRunner::launch(&make_app("Music Player"), &vfs);
        assert!(runner.lines.iter().any(|l| l.contains("No tracks found")));
    }

    #[test]
    fn photo_viewer_lists_photos() {
        let vfs = setup_vfs();
        let runner = AppRunner::launch(&make_app("Photo Viewer"), &vfs);
        assert!(runner.lines.iter().any(|l| l.contains("1 image(s)")));
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
        // Photo files are binary, so should show hex dump.
        assert!(runner.viewing_file.is_some());
        assert!(runner.lines.iter().any(|l| l.contains("Binary file")));
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
    fn photo_viewer_empty() {
        use crate::vfs::Vfs;
        let mut vfs = MemoryVfs::new();
        vfs.mkdir("/home").unwrap();
        vfs.mkdir("/home/user").unwrap();
        vfs.mkdir("/home/user/photos").unwrap();
        let runner = AppRunner::launch(&make_app("Photo Viewer"), &vfs);
        assert!(runner.lines.iter().any(|l| l.contains("No images found")));
    }
}
