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
        // Background bar (green-tinted to match PSIX style).
        if !sdi.contains("bar_bottom") {
            let obj = sdi.create("bar_bottom");
            obj.x = 0;
            obj.y = BAR_Y;
            obj.w = SCREEN_W;
            obj.h = BAR_H;
            obj.color = Color::rgba(20, 50, 40, 220);
            obj.overlay = true;
            obj.z = 900;
        }
        if let Ok(obj) = sdi.get_mut("bar_bottom") {
            obj.visible = true;
        }

        // URL/label on the left (PSIX shows a URL-like identifier).
        ensure_bottom_text(sdi, "bar_url", 6, BAR_Y + 6, 8);
        if let Ok(obj) = sdi.get_mut("bar_url") {
            obj.text = Some("OASIS://HOME".to_string());
            obj.text_color = Color::rgb(120, 160, 140);
        }

        // Shoulder button hints (positioned after URL).
        ensure_bottom_text(sdi, "bar_shoulder_l", 110, BAR_Y + 5, 9);
        if let Ok(obj) = sdi.get_mut("bar_shoulder_l") {
            obj.text = Some("L".to_string());
            obj.text_color = if self.l_pressed {
                Color::WHITE
            } else {
                Color::rgb(80, 120, 100)
            };
        }

        ensure_bottom_text(sdi, "bar_shoulder_r", 126, BAR_Y + 5, 9);
        if let Ok(obj) = sdi.get_mut("bar_shoulder_r") {
            obj.text = Some("R".to_string());
            obj.text_color = if self.r_pressed {
                Color::WHITE
            } else {
                Color::rgb(80, 120, 100)
            };
        }

        // Media category tabs.
        let tab_x_start = 150;
        let tab_w = 55;
        for (i, tab) in MediaTab::TABS.iter().enumerate() {
            let x = tab_x_start + (i as i32) * (tab_w + 4);

            // Tab background (PSIX-style: active tab has white outline look).
            let bg_name = format!("bar_btab_bg_{i}");
            if !sdi.contains(&bg_name) {
                let obj = sdi.create(&bg_name);
                obj.y = BAR_Y + 2;
                obj.h = 20;
                obj.overlay = true;
                obj.z = 901;
            }
            if let Ok(obj) = sdi.get_mut(&bg_name) {
                obj.x = x - 2;
                obj.w = tab_w as u32 + 4;
                obj.visible = true;
                obj.color = if *tab == self.active_tab {
                    Color::rgba(60, 120, 80, 180)
                } else {
                    Color::rgba(0, 0, 0, 0)
                };
            }

            // Tab text.
            let name = format!("bar_btab_{i}");
            ensure_bottom_text(sdi, &name, x, BAR_Y + 6, 9);
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.text = Some(tab.label().to_string());
                obj.text_color = if *tab == self.active_tab {
                    Color::WHITE
                } else {
                    Color::rgb(90, 130, 110)
                };
            }
        }

        // Page dots (VDM indicator).
        let dots_x = 410;
        for i in 0..self.total_pages.min(4) {
            let name = format!("bar_page_{i}");
            if !sdi.contains(&name) {
                let obj = sdi.create(&name);
                obj.overlay = true;
                obj.z = 901;
            }
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.x = dots_x + (i as i32) * 14;
                obj.y = BAR_Y + 7;
                obj.w = 10;
                obj.h = 10;
                obj.visible = true;
                obj.color = if i == self.current_page {
                    Color::rgb(100, 150, 220)
                } else {
                    Color::rgb(50, 60, 80)
                };
            }
        }
        // Hide unused dots.
        for i in self.total_pages.min(4)..4 {
            let name = format!("bar_page_{i}");
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.visible = false;
            }
        }
    }

    /// Hide all bottom bar SDI objects.
    pub fn hide_sdi(sdi: &mut SdiRegistry) {
        let names = ["bar_bottom", "bar_shoulder_l", "bar_shoulder_r", "bar_url"];
        for name in &names {
            if let Ok(obj) = sdi.get_mut(name) {
                obj.visible = false;
            }
        }
        for i in 0..4 {
            for prefix in &["bar_btab_", "bar_btab_bg_", "bar_page_"] {
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
        assert!(sdi.contains("bar_shoulder_l"));
        assert!(sdi.contains("bar_shoulder_r"));
        assert!(sdi.contains("bar_btab_0"));
        assert!(sdi.contains("bar_btab_1"));
        assert!(sdi.contains("bar_btab_2"));
        assert!(sdi.contains("bar_btab_3"));
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
