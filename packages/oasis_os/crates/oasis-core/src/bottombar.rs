//! PSIX-style bottom bar -- footer with media category tabs and page dots.
//!
//! Occupies the bottom 24 pixels of the 480x272 screen (y=248-272).
//! Displays shoulder button hints, media category tabs (Audio/Video/Image/File),
//! USB indicator, and virtual desktop page dots.

use crate::backend::Color;
use crate::sdi::SdiRegistry;

/// Screen width for layout calculations.
const SCREEN_W: u32 = 480;
/// Bottom bar Y position.
const BAR_Y: i32 = 248;
/// Bottom bar height.
const BAR_H: u32 = 24;

/// Media category tabs (cycled with R trigger).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MediaTab {
    /// No media tab selected -- dashboard is visible.
    None,
    /// Audio player page.
    Audio,
    /// Video player page.
    Video,
    /// Image viewer page.
    Image,
    /// File browser page.
    File,
}

impl MediaTab {
    /// Cycle to the next tab.
    pub fn next(self) -> Self {
        match self {
            Self::None => Self::Audio,
            Self::Audio => Self::Video,
            Self::Video => Self::Image,
            Self::Image => Self::File,
            Self::File => Self::None,
        }
    }

    /// Display label for the tab.
    pub fn label(self) -> &'static str {
        match self {
            Self::None => "",
            Self::Audio => "AUDIO",
            Self::Video => "VIDEO",
            Self::Image => "IMAGE",
            Self::File => "FILE",
        }
    }

    /// All selectable tabs in order (excluding None).
    pub const TABS: &[MediaTab] = &[
        MediaTab::Audio,
        MediaTab::Video,
        MediaTab::Image,
        MediaTab::File,
    ];
}

/// Runtime state for the bottom bar.
#[derive(Debug)]
pub struct BottomBar {
    /// Currently selected media tab.
    pub active_tab: MediaTab,
    /// Current dashboard page (0-based).
    pub current_page: usize,
    /// Total number of dashboard pages.
    pub total_pages: usize,
    /// Whether L trigger is visually pressed.
    pub l_pressed: bool,
    /// Whether R trigger is visually pressed.
    pub r_pressed: bool,
}

impl BottomBar {
    /// Create a new bottom bar.
    pub fn new() -> Self {
        Self {
            active_tab: MediaTab::None,
            current_page: 0,
            total_pages: 1,
            l_pressed: false,
            r_pressed: false,
        }
    }

    /// Cycle to the next media tab.
    pub fn next_tab(&mut self) {
        self.active_tab = self.active_tab.next();
    }

    /// Synchronize SDI objects to reflect current bottom bar state.
    pub fn update_sdi(&self, sdi: &mut SdiRegistry) {
        // Semi-transparent background bar (PSIX: very subtle dark overlay).
        if !sdi.contains("bar_bottom") {
            let obj = sdi.create("bar_bottom");
            obj.x = 0;
            obj.y = BAR_Y;
            obj.w = SCREEN_W;
            obj.h = BAR_H;
            obj.color = Color::rgba(0, 0, 0, 80);
            obj.overlay = true;
            obj.z = 900;
        }
        if let Ok(obj) = sdi.get_mut("bar_bottom") {
            obj.visible = true;
        }

        // URL label on the left (PSIX: "HTTP://PSIXONLINE.COM").
        ensure_bottom_text(sdi, "bar_url", 6, BAR_Y + 8, 8);
        if let Ok(obj) = sdi.get_mut("bar_url") {
            obj.text = Some("HTTP://OASIS.LOCAL".to_string());
            obj.text_color = Color::rgb(200, 200, 200);
        }

        // PSIX-style metallic container around URL area (left bezel).
        let url_bx = 2i32;
        let url_bw = 180u32;
        let bz_y = BAR_Y + 2;
        let bz_h = BAR_H - 4;
        ensure_bezel(sdi, "bar_url_bezel", url_bx, bz_y, url_bw, bz_h);

        // PSIX-style pipe-separated media category tabs (right side).
        // Layout: "AUDIO | VIDEO | IMAGE | FILE" with thin pipe separators.
        let char_w = 8i32;
        let pipe_gap = 6i32;
        let tab_labels: Vec<&str> = MediaTab::TABS.iter().map(|t| t.label()).collect();

        // Calculate total width of "LABEL | LABEL | LABEL | LABEL".
        let labels_w: i32 = tab_labels.iter().map(|l| l.len() as i32 * char_w).sum();
        let pipes_w = (tab_labels.len() as i32 - 1) * (pipe_gap * 2 + char_w);
        let total_w = labels_w + pipes_w;
        let tabs_x = SCREEN_W as i32 - total_w - 12;

        // Metallic container around tab group (right bezel).
        let tab_bx = tabs_x - 8;
        let tab_bw = (total_w + 16) as u32;
        ensure_bezel(sdi, "bar_tab_bezel", tab_bx, bz_y, tab_bw, bz_h);

        let mut cx = tabs_x;
        for (i, tab) in MediaTab::TABS.iter().enumerate() {
            let label = tab.label();

            // Tab text.
            let name = format!("bar_btab_{i}");
            ensure_bottom_text(sdi, &name, cx, BAR_Y + 8, 8);
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.text = Some(label.to_string());
                obj.text_color = if *tab == self.active_tab {
                    Color::WHITE
                } else {
                    Color::rgb(170, 170, 170)
                };
            }
            cx += label.len() as i32 * char_w;

            // Pipe separator (except after last tab).
            if i < MediaTab::TABS.len() - 1 {
                cx += pipe_gap;
                let pipe_name = format!("bar_bpipe_{i}");
                ensure_bottom_text(sdi, &pipe_name, cx, BAR_Y + 8, 8);
                if let Ok(obj) = sdi.get_mut(&pipe_name) {
                    obj.text = Some("|".to_string());
                    obj.text_color = Color::rgba(255, 255, 255, 80);
                }
                cx += char_w + pipe_gap;
            }
        }

        // Hide old outlined border objects (from previous style).
        for i in 0..4 {
            for prefix in &[
                "bar_btab_bg_",
                "bar_btab_bt_",
                "bar_btab_bb_",
                "bar_btab_bl_",
                "bar_btab_br_",
            ] {
                let name = format!("{prefix}{i}");
                if let Ok(obj) = sdi.get_mut(&name) {
                    obj.visible = false;
                }
            }
        }

        // USB indicator (center-bottom area, PSIX style).
        let usb_x = tabs_x - 50;
        ensure_bottom_text(sdi, "bar_usb", usb_x, BAR_Y + 8, 8);
        if let Ok(obj) = sdi.get_mut("bar_usb") {
            obj.text = Some("USB".to_string());
            obj.text_color = Color::rgb(140, 140, 140);
        }

        // Page dots (small squares near USB indicator).
        let dots_x = usb_x - (self.total_pages.min(4) as i32) * 12 - 8;
        for i in 0..self.total_pages.min(4) {
            let name = format!("bar_page_{i}");
            if !sdi.contains(&name) {
                let obj = sdi.create(&name);
                obj.overlay = true;
                obj.z = 901;
            }
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.x = dots_x + (i as i32) * 12;
                obj.y = BAR_Y + 9;
                obj.w = 6;
                obj.h = 6;
                obj.visible = true;
                obj.color = if i == self.current_page {
                    Color::rgba(255, 255, 255, 200)
                } else {
                    Color::rgba(255, 255, 255, 50)
                };
            }
        }
        for i in self.total_pages.min(4)..4 {
            let name = format!("bar_page_{i}");
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.visible = false;
            }
        }
    }

    /// Hide all bottom bar SDI objects.
    pub fn hide_sdi(sdi: &mut SdiRegistry) {
        let names = [
            "bar_bottom",
            "bar_url",
            "bar_usb",
            "bar_url_bezel",
            "bar_url_bezel_t",
            "bar_url_bezel_b",
            "bar_tab_bezel",
            "bar_tab_bezel_t",
            "bar_tab_bezel_b",
        ];
        for name in &names {
            if let Ok(obj) = sdi.get_mut(name) {
                obj.visible = false;
            }
        }
        for i in 0..4 {
            for prefix in &[
                "bar_btab_",
                "bar_btab_bg_",
                "bar_page_",
                "bar_btab_bt_",
                "bar_btab_bb_",
                "bar_btab_bl_",
                "bar_btab_br_",
                "bar_bpipe_",
            ] {
                let name = format!("{prefix}{i}");
                if let Ok(obj) = sdi.get_mut(&name) {
                    obj.visible = false;
                }
            }
        }
    }
}

impl Default for BottomBar {
    fn default() -> Self {
        Self::new()
    }
}

/// Helper: create a metallic bezel (dark fill + lighter top edge + darker bottom edge).
fn ensure_bezel(sdi: &mut SdiRegistry, name: &str, x: i32, y: i32, w: u32, h: u32) {
    // Main dark fill.
    if !sdi.contains(name) {
        let obj = sdi.create(name);
        obj.overlay = true;
        obj.z = 900;
    }
    if let Ok(obj) = sdi.get_mut(name) {
        obj.x = x;
        obj.y = y;
        obj.w = w;
        obj.h = h;
        obj.color = Color::rgba(0, 0, 0, 60);
        obj.visible = true;
    }
    // Top highlight edge.
    let top_name = format!("{name}_t");
    if !sdi.contains(&top_name) {
        let obj = sdi.create(&top_name);
        obj.overlay = true;
        obj.z = 901;
    }
    if let Ok(obj) = sdi.get_mut(&top_name) {
        obj.x = x;
        obj.y = y;
        obj.w = w;
        obj.h = 1;
        obj.color = Color::rgba(255, 255, 255, 50);
        obj.visible = true;
    }
    // Bottom shadow edge.
    let bot_name = format!("{name}_b");
    if !sdi.contains(&bot_name) {
        let obj = sdi.create(&bot_name);
        obj.overlay = true;
        obj.z = 901;
    }
    if let Ok(obj) = sdi.get_mut(&bot_name) {
        obj.x = x;
        obj.y = y + h as i32 - 1;
        obj.w = w;
        obj.h = 1;
        obj.color = Color::rgba(0, 0, 0, 80);
        obj.visible = true;
    }
}

/// Helper: create a text-only overlay SDI object for the bottom bar, and restore visibility.
fn ensure_bottom_text(sdi: &mut SdiRegistry, name: &str, x: i32, y: i32, size: u16) {
    if !sdi.contains(name) {
        let obj = sdi.create(name);
        obj.x = x;
        obj.y = y;
        obj.font_size = size;
        obj.text_color = Color::WHITE;
        obj.w = 0;
        obj.h = 0;
        obj.overlay = true;
        obj.z = 902;
    }
    if let Ok(obj) = sdi.get_mut(name) {
        obj.visible = true;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn media_tab_cycle() {
        let mut bar = BottomBar::new();
        assert_eq!(bar.active_tab, MediaTab::None);
        bar.next_tab();
        assert_eq!(bar.active_tab, MediaTab::Audio);
        bar.next_tab();
        assert_eq!(bar.active_tab, MediaTab::Video);
        bar.next_tab();
        assert_eq!(bar.active_tab, MediaTab::Image);
        bar.next_tab();
        assert_eq!(bar.active_tab, MediaTab::File);
        bar.next_tab();
        assert_eq!(bar.active_tab, MediaTab::None);
    }

    #[test]
    fn update_sdi_creates_objects() {
        let bar = BottomBar::new();
        let mut sdi = SdiRegistry::new();
        bar.update_sdi(&mut sdi);
        assert!(sdi.contains("bar_bottom"));
        assert!(sdi.contains("bar_url"));
        assert!(sdi.contains("bar_btab_0"));
        assert!(sdi.contains("bar_btab_1"));
        assert!(sdi.contains("bar_btab_2"));
        assert!(sdi.contains("bar_btab_3"));
        // Pipe separators between tabs.
        assert!(sdi.contains("bar_bpipe_0"));
        assert!(sdi.contains("bar_bpipe_1"));
        assert!(sdi.contains("bar_bpipe_2"));
    }

    #[test]
    fn page_dots_visibility() {
        let mut bar = BottomBar::new();
        bar.total_pages = 3;
        bar.current_page = 1;
        let mut sdi = SdiRegistry::new();
        bar.update_sdi(&mut sdi);

        // Pages 0-2 should be visible, page 3 should not exist yet (or hidden).
        assert!(sdi.get("bar_page_0").unwrap().visible);
        assert!(sdi.get("bar_page_1").unwrap().visible);
        assert!(sdi.get("bar_page_2").unwrap().visible);
    }

    #[test]
    fn bar_is_overlay() {
        let bar = BottomBar::new();
        let mut sdi = SdiRegistry::new();
        bar.update_sdi(&mut sdi);
        assert!(sdi.get("bar_bottom").unwrap().overlay);
    }
}
