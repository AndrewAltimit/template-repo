//! PSIX-style bottom bar -- footer with media category tabs and page dots.
//!
//! Occupies the bottom 24 pixels of the 480x272 screen (y=248-272).
//! Displays URL label, USB indicator, media category tabs, page dots,
//! and shoulder button hints.

use crate::sdi::SdiRegistry;
use crate::sdi::helpers::{
    BezelStyle, ensure_border, ensure_chrome_bezel, ensure_text, hide_bezel, hide_objects,
};
use crate::theme;

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
        let bar_y = theme::BOTTOMBAR_Y;
        let bar_h = theme::BOTTOMBAR_H;
        let screen_w = theme::SCREEN_W;
        let char_w = theme::CHAR_W;

        // Semi-transparent background bar.
        if !sdi.contains("bar_bottom") {
            let obj = sdi.create("bar_bottom");
            obj.x = 0;
            obj.y = bar_y;
            obj.w = screen_w;
            obj.h = bar_h;
            obj.color = theme::BAR_BG;
            obj.overlay = true;
            obj.z = 900;
        }
        if let Ok(obj) = sdi.get_mut("bar_bottom") {
            obj.visible = true;
        }

        // Thin separator line at top of bottom bar.
        ensure_border(
            sdi,
            "bar_bottom_line",
            0,
            bar_y,
            screen_w,
            1,
            theme::SEPARATOR_COLOR,
        );

        // URL label on the left.
        ensure_text(
            sdi,
            "bar_url",
            8,
            bar_y + 8,
            theme::FONT_SMALL,
            theme::URL_COLOR,
        );
        if let Ok(obj) = sdi.get_mut("bar_url") {
            obj.text = Some("HTTP://OASIS.LOCAL".to_string());
        }

        // Chrome bezel around URL area.
        let url_bx = 2i32;
        let url_bw = 190u32;
        let bz_y = bar_y + 2;
        let bz_h = bar_h - 4;
        ensure_chrome_bezel(
            sdi,
            "bar_url_bezel",
            url_bx,
            bz_y,
            url_bw,
            bz_h,
            &BezelStyle::chrome(),
        );

        // Media category tabs (pipe-separated).
        let tab_labels: Vec<&str> = MediaTab::TABS.iter().map(|t| t.label()).collect();
        let labels_w: i32 = tab_labels.iter().map(|l| l.len() as i32 * char_w).sum();
        let pipes_w = (tab_labels.len() as i32 - 1) * (theme::PIPE_GAP * 2 + char_w);
        let total_w = labels_w + pipes_w;
        let tabs_x = screen_w as i32 - total_w - theme::R_HINT_W - 8;

        // Chrome bezel around tab group.
        let tab_bx = tabs_x - 6;
        let tab_bw = (total_w + theme::R_HINT_W + 14) as u32;
        ensure_chrome_bezel(
            sdi,
            "bar_tab_bezel",
            tab_bx,
            bz_y,
            tab_bw,
            bz_h,
            &BezelStyle::chrome(),
        );

        let mut cx = tabs_x;
        for (i, tab) in MediaTab::TABS.iter().enumerate() {
            let label = tab.label();
            let name = format!("bar_btab_{i}");

            let color = if *tab == self.active_tab {
                theme::MEDIA_TAB_ACTIVE
            } else {
                theme::MEDIA_TAB_INACTIVE
            };
            ensure_text(sdi, &name, cx, bar_y + 8, theme::FONT_SMALL, color);
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.text = Some(label.to_string());
                obj.text_color = color;
            }
            cx += label.len() as i32 * char_w;

            // Pipe separator (except after last tab).
            if i < MediaTab::TABS.len() - 1 {
                cx += theme::PIPE_GAP;
                let pipe_name = format!("bar_bpipe_{i}");
                ensure_text(
                    sdi,
                    &pipe_name,
                    cx,
                    bar_y + 8,
                    theme::FONT_SMALL,
                    theme::PIPE_COLOR,
                );
                if let Ok(obj) = sdi.get_mut(&pipe_name) {
                    obj.text = Some("|".to_string());
                }
                cx += char_w + theme::PIPE_GAP;
            }
        }

        // "R>" shoulder button hint on far right.
        ensure_text(
            sdi,
            "bar_r_hint",
            screen_w as i32 - theme::R_HINT_W,
            bar_y + 8,
            theme::FONT_SMALL,
            theme::R_HINT_COLOR,
        );
        if let Ok(obj) = sdi.get_mut("bar_r_hint") {
            obj.text = Some("R>".to_string());
        }

        // USB indicator (between bezels).
        let usb_x = url_bx + url_bw as i32 + 14;
        ensure_text(
            sdi,
            "bar_usb",
            usb_x,
            bar_y + 8,
            theme::FONT_SMALL,
            theme::USB_COLOR,
        );
        if let Ok(obj) = sdi.get_mut("bar_usb") {
            obj.text = Some("USB".to_string());
        }

        // Page dots.
        let dots_x = usb_x + 36;
        let max_dots = theme::MAX_PAGE_DOTS;
        for i in 0..self.total_pages.min(max_dots) {
            let name = format!("bar_page_{i}");
            if !sdi.contains(&name) {
                let obj = sdi.create(&name);
                obj.overlay = true;
                obj.z = 901;
            }
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.x = dots_x + (i as i32) * 12;
                obj.y = bar_y + 9;
                obj.w = 6;
                obj.h = 6;
                obj.visible = true;
                obj.color = if i == self.current_page {
                    theme::PAGE_DOT_ACTIVE
                } else {
                    theme::PAGE_DOT_INACTIVE
                };
            }
        }
        for i in self.total_pages.min(max_dots)..max_dots {
            let name = format!("bar_page_{i}");
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.visible = false;
            }
        }
    }

    /// Hide all bottom bar SDI objects.
    pub fn hide_sdi(sdi: &mut SdiRegistry) {
        hide_objects(
            sdi,
            &[
                "bar_bottom",
                "bar_bottom_line",
                "bar_url",
                "bar_usb",
                "bar_r_hint",
            ],
        );
        hide_bezel(sdi, "bar_url_bezel");
        hide_bezel(sdi, "bar_tab_bezel");
        for i in 0..MediaTab::TABS.len() {
            for prefix in &["bar_btab_", "bar_bpipe_", "bar_page_"] {
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
