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
        // Semi-transparent background bar (PSIX uses thin dark bar).
        if !sdi.contains("bar_bottom") {
            let obj = sdi.create("bar_bottom");
            obj.x = 0;
            obj.y = BAR_Y;
            obj.w = SCREEN_W;
            obj.h = BAR_H;
            obj.color = Color::rgba(0, 0, 0, 140);
            obj.overlay = true;
            obj.z = 900;
        }
        if let Ok(obj) = sdi.get_mut("bar_bottom") {
            obj.visible = true;
        }

        // URL label on the left (PSIX: "HTTP://PSIXONLINE.COM").
        ensure_bottom_text(sdi, "bar_url", 6, BAR_Y + 7, 8);
        if let Ok(obj) = sdi.get_mut("bar_url") {
            obj.text = Some("HTTP://OASIS.LOCAL".to_string());
            obj.text_color = Color::rgb(180, 180, 180);
        }

        // Shoulder button divider (center area).
        ensure_bottom_text(sdi, "bar_shoulder_l", 180, BAR_Y + 7, 8);
        if let Ok(obj) = sdi.get_mut("bar_shoulder_l") {
            obj.text = None;
            obj.visible = false;
        }

        ensure_bottom_text(sdi, "bar_shoulder_r", 196, BAR_Y + 7, 8);
        if let Ok(obj) = sdi.get_mut("bar_shoulder_r") {
            obj.text = None;
            obj.visible = false;
        }

        // Media category tabs (right side, PSIX-style outlined buttons).
        let tab_w = 50;
        let tab_gap = 4;
        let total_tabs_w =
            MediaTab::TABS.len() as i32 * tab_w + (MediaTab::TABS.len() as i32 - 1) * tab_gap;
        let tab_x_start = SCREEN_W as i32 - total_tabs_w - 10;

        let tab_h = 18i32;
        for (i, tab) in MediaTab::TABS.iter().enumerate() {
            let x = tab_x_start + (i as i32) * (tab_w + tab_gap);
            let ty = BAR_Y + 3;

            let border_alpha: u8 = if *tab == self.active_tab { 180 } else { 60 };
            let border_color = Color::rgba(255, 255, 255, border_alpha);

            // Thin outlined border (top, bottom, left, right edges).
            ensure_bar_border(
                sdi,
                &format!("bar_btab_bt_{i}"),
                x,
                ty,
                tab_w as u32,
                1,
                border_color,
            );
            ensure_bar_border(
                sdi,
                &format!("bar_btab_bb_{i}"),
                x,
                ty + tab_h - 1,
                tab_w as u32,
                1,
                border_color,
            );
            ensure_bar_border(
                sdi,
                &format!("bar_btab_bl_{i}"),
                x,
                ty,
                1,
                tab_h as u32,
                border_color,
            );
            ensure_bar_border(
                sdi,
                &format!("bar_btab_br_{i}"),
                x + tab_w - 1,
                ty,
                1,
                tab_h as u32,
                border_color,
            );

            // Subtle fill for active tab only.
            let bg_name = format!("bar_btab_bg_{i}");
            if !sdi.contains(&bg_name) {
                let obj = sdi.create(&bg_name);
                obj.overlay = true;
                obj.z = 901;
            }
            if let Ok(obj) = sdi.get_mut(&bg_name) {
                obj.x = x + 1;
                obj.y = ty + 1;
                obj.w = (tab_w - 2) as u32;
                obj.h = (tab_h - 2) as u32;
                obj.visible = true;
                obj.color = if *tab == self.active_tab {
                    Color::rgba(255, 255, 255, 25)
                } else {
                    Color::rgba(0, 0, 0, 0)
                };
            }

            // Tab text (centered in the bordered area).
            let name = format!("bar_btab_{i}");
            let label = tab.label();
            let text_w = label.len() as i32 * 8;
            let tx = x + (tab_w - text_w) / 2;
            ensure_bottom_text(sdi, &name, tx.max(x + 2), BAR_Y + 7, 8);
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.text = Some(label.to_string());
                obj.text_color = if *tab == self.active_tab {
                    Color::WHITE
                } else {
                    Color::rgb(180, 180, 180)
                };
            }
        }

        // USB / page indicator (center, between URL and tabs).
        let indicator_x = 200;
        ensure_bottom_text(sdi, "bar_usb", indicator_x, BAR_Y + 7, 8);
        if let Ok(obj) = sdi.get_mut("bar_usb") {
            obj.text = Some("USB".to_string());
            obj.text_color = Color::rgb(120, 120, 120);
        }

        // Page dots (small squares near center).
        let dots_x = indicator_x + 40;
        for i in 0..self.total_pages.min(4) {
            let name = format!("bar_page_{i}");
            if !sdi.contains(&name) {
                let obj = sdi.create(&name);
                obj.overlay = true;
                obj.z = 901;
            }
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.x = dots_x + (i as i32) * 12;
                obj.y = BAR_Y + 8;
                obj.w = 8;
                obj.h = 8;
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
            "bar_shoulder_l",
            "bar_shoulder_r",
            "bar_url",
            "bar_usb",
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

/// Helper: create a thin border SDI object for the bottom bar.
fn ensure_bar_border(
    sdi: &mut SdiRegistry,
    name: &str,
    x: i32,
    y: i32,
    w: u32,
    h: u32,
    color: Color,
) {
    if !sdi.contains(name) {
        let obj = sdi.create(name);
        obj.overlay = true;
        obj.z = 901;
    }
    if let Ok(obj) = sdi.get_mut(name) {
        obj.x = x;
        obj.y = y;
        obj.w = w;
        obj.h = h;
        obj.color = color;
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
