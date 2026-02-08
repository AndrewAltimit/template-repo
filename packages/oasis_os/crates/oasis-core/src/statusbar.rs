//! PSIX-style status bar -- top bar with version, clock, battery, and tabs.
//!
//! Occupies the top 24 pixels of the 480x272 screen. Creates and updates
//! SDI objects to display system status and top-level navigation tabs.

use crate::backend::Color;
use crate::platform::{BatteryState, PowerInfo, SystemTime};
use crate::sdi::SdiRegistry;

/// Screen width for layout calculations.
const SCREEN_W: u32 = 480;
/// Status bar height.
const BAR_H: u32 = 24;

/// Top-level tabs (cycled with L trigger).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TopTab {
    /// Main dashboard (app grid).
    Apps,
    /// Module / plugin manager.
    Mods,
    /// Network status.
    Net,
}

impl TopTab {
    /// Cycle to the next tab.
    pub fn next(self) -> Self {
        match self {
            Self::Apps => Self::Mods,
            Self::Mods => Self::Net,
            Self::Net => Self::Apps,
        }
    }

    /// Display label for the tab.
    pub fn label(self) -> &'static str {
        match self {
            Self::Apps => "APPS",
            Self::Mods => "MODS",
            Self::Net => "NET",
        }
    }

    /// All tabs in order.
    pub const ALL: &[TopTab] = &[TopTab::Apps, TopTab::Mods, TopTab::Net];
}

/// Month names for date display.
const MONTHS: [&str; 12] = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
];

/// Runtime state for the top status bar.
#[derive(Debug)]
pub struct StatusBar {
    /// Currently selected top tab.
    pub active_tab: TopTab,
    /// Cached clock string (updated each frame).
    clock_text: String,
    /// Cached date string.
    date_text: String,
    /// Cached battery string.
    battery_text: String,
    /// Cached CPU frequency string.
    cpu_text: String,
}

impl StatusBar {
    /// Create a new status bar with default state.
    pub fn new() -> Self {
        Self {
            active_tab: TopTab::Apps,
            clock_text: "00:00".to_string(),
            date_text: String::new(),
            battery_text: String::new(),
            cpu_text: String::new(),
        }
    }

    /// Cycle to the next top tab.
    pub fn next_tab(&mut self) {
        self.active_tab = self.active_tab.next();
    }

    /// Update cached system info strings.
    pub fn update_info(&mut self, time: Option<&SystemTime>, power: Option<&PowerInfo>) {
        if let Some(t) = time {
            self.clock_text = format!("{:02}:{:02}", t.hour, t.minute);
            let month_name = if t.month >= 1 && t.month <= 12 {
                MONTHS[(t.month - 1) as usize]
            } else {
                "???"
            };
            self.date_text = format!("{month_name} {}, {}", t.day, t.year);
        }
        if let Some(p) = power {
            self.battery_text = match p.state {
                BatteryState::NoBattery => "AC".to_string(),
                BatteryState::Full => "FULL".to_string(),
                _ => {
                    let pct = p.battery_percent.unwrap_or(0);
                    let icon = match pct {
                        0..=20 => "[|    ]",
                        21..=40 => "[||   ]",
                        41..=60 => "[|||  ]",
                        61..=80 => "[|||| ]",
                        _ => "[|||||]",
                    };
                    format!("{pct}% {icon}")
                },
            };
            if p.cpu.current_mhz > 0 {
                self.cpu_text = format!("{}MHz", p.cpu.current_mhz);
            } else {
                self.cpu_text.clear();
            }
        }
    }

    /// Synchronize SDI objects to reflect current status bar state.
    pub fn update_sdi(&self, sdi: &mut SdiRegistry) {
        // Semi-transparent background bar (PSIX uses very transparent black).
        if !sdi.contains("bar_top") {
            let obj = sdi.create("bar_top");
            obj.x = 0;
            obj.y = 0;
            obj.w = SCREEN_W;
            obj.h = BAR_H;
            obj.color = Color::rgba(0, 0, 0, 80);
            obj.overlay = true;
            obj.z = 900;
        }
        if let Ok(obj) = sdi.get_mut("bar_top") {
            obj.visible = true;
        }

        // Thin line separator below status bar (PSIX has a visible edge).
        ensure_border(
            sdi,
            "bar_top_line",
            0,
            BAR_H as i32 - 1,
            SCREEN_W,
            1,
            Color::rgba(255, 255, 255, 40),
        );

        // Battery + CPU info (left side, PSIX style: "100% [icon] 265 MHz").
        ensure_text_object(sdi, "bar_battery", 6, 7, 8, Color::rgb(120, 255, 120));
        if let Ok(obj) = sdi.get_mut("bar_battery") {
            let mut info = self.battery_text.clone();
            if !self.cpu_text.is_empty() {
                info = format!("{info}  {}", self.cpu_text);
            }
            obj.text = Some(info);
            obj.overlay = true;
            obj.z = 901;
        }

        // Version label (center area, PSIX: "Version 1.1 Public").
        ensure_text_object(sdi, "bar_version", 180, 7, 8, Color::WHITE);
        if let Ok(obj) = sdi.get_mut("bar_version") {
            obj.text = Some("Version 0.1".to_string());
            obj.overlay = true;
            obj.z = 901;
        }

        // Clock + date (right side, PSIX: "11:20 November 23, 2024").
        ensure_text_object(sdi, "bar_clock", 290, 7, 8, Color::rgb(255, 255, 255));
        if let Ok(obj) = sdi.get_mut("bar_clock") {
            if self.date_text.is_empty() {
                obj.text = Some(self.clock_text.clone());
            } else {
                obj.text = Some(format!("{} {}", self.clock_text, self.date_text));
            }
            obj.overlay = true;
            obj.z = 901;
        }

        // "MSO"-style label before tabs (PSIX shows "MSO" as a category label).
        ensure_text_object(
            sdi,
            "bar_mso",
            6,
            BAR_H as i32 + 3,
            8,
            Color::rgb(220, 220, 220),
        );
        if let Ok(obj) = sdi.get_mut("bar_mso") {
            obj.text = Some("OSS".to_string());
            obj.overlay = true;
            obj.z = 902;
        }

        // Tab row (PSIX-style thin outlined borders around each tab label).
        let tab_x_start = 34;
        let tab_w: i32 = 45;
        let tab_h: i32 = 16;
        let tab_gap = 4;
        let tab_y = BAR_H as i32;
        for (i, tab) in TopTab::ALL.iter().enumerate() {
            let name = format!("bar_tab_{i}");
            let x = tab_x_start + (i as i32) * (tab_w + tab_gap);

            let border_alpha: u8 = if *tab == self.active_tab { 180 } else { 60 };
            let border_color = Color::rgba(255, 255, 255, border_alpha);

            // Top edge.
            ensure_border(
                sdi,
                &format!("bar_tab_bt_{i}"),
                x,
                tab_y,
                tab_w as u32,
                1,
                border_color,
            );
            // Bottom edge.
            ensure_border(
                sdi,
                &format!("bar_tab_bb_{i}"),
                x,
                tab_y + tab_h - 1,
                tab_w as u32,
                1,
                border_color,
            );
            // Left edge.
            ensure_border(
                sdi,
                &format!("bar_tab_bl_{i}"),
                x,
                tab_y,
                1,
                tab_h as u32,
                border_color,
            );
            // Right edge.
            ensure_border(
                sdi,
                &format!("bar_tab_br_{i}"),
                x + tab_w - 1,
                tab_y,
                1,
                tab_h as u32,
                border_color,
            );

            // Fill for active tab only (very subtle).
            let bg_name = format!("bar_tab_bg_{i}");
            if !sdi.contains(&bg_name) {
                let obj = sdi.create(&bg_name);
                obj.overlay = true;
                obj.z = 901;
            }
            if let Ok(obj) = sdi.get_mut(&bg_name) {
                obj.x = x + 1;
                obj.y = tab_y + 1;
                obj.w = (tab_w - 2) as u32;
                obj.h = (tab_h - 2) as u32;
                obj.visible = true;
                obj.color = if *tab == self.active_tab {
                    Color::rgba(255, 255, 255, 30)
                } else {
                    Color::rgba(0, 0, 0, 0)
                };
            }

            // Tab text.
            let tx = x + (tab_w - (tab.label().len() as i32 * 8)) / 2;
            ensure_text_object(sdi, &name, tx.max(x + 2), tab_y + 4, 8, Color::WHITE);
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.text = Some(tab.label().to_string());
                obj.overlay = true;
                obj.z = 902;
                obj.text_color = if *tab == self.active_tab {
                    Color::WHITE
                } else {
                    Color::rgb(160, 160, 160)
                };
            }
        }

        // Hide CPU text object (merged into battery display).
        if let Ok(obj) = sdi.get_mut("bar_cpu") {
            obj.visible = false;
        }
    }

    /// Hide all status bar SDI objects.
    pub fn hide_sdi(sdi: &mut SdiRegistry) {
        let names = [
            "bar_top",
            "bar_top_line",
            "bar_version",
            "bar_clock",
            "bar_battery",
            "bar_cpu",
            "bar_mso",
        ];
        for name in &names {
            if let Ok(obj) = sdi.get_mut(name) {
                obj.visible = false;
            }
        }
        for i in 0..TopTab::ALL.len() {
            for prefix in &[
                "bar_tab_",
                "bar_tab_bg_",
                "bar_tab_bt_",
                "bar_tab_bb_",
                "bar_tab_bl_",
                "bar_tab_br_",
            ] {
                let name = format!("{prefix}{i}");
                if let Ok(obj) = sdi.get_mut(&name) {
                    obj.visible = false;
                }
            }
        }
    }
}

impl Default for StatusBar {
    fn default() -> Self {
        Self::new()
    }
}

/// Helper: create a thin border SDI object (1px line segment).
fn ensure_border(sdi: &mut SdiRegistry, name: &str, x: i32, y: i32, w: u32, h: u32, color: Color) {
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

/// Helper: create a text-only SDI object if it doesn't exist, and restore visibility.
fn ensure_text_object(sdi: &mut SdiRegistry, name: &str, x: i32, y: i32, size: u16, color: Color) {
    if !sdi.contains(name) {
        let obj = sdi.create(name);
        obj.x = x;
        obj.y = y;
        obj.font_size = size;
        obj.text_color = color;
        obj.w = 0;
        obj.h = 0;
    }
    if let Ok(obj) = sdi.get_mut(name) {
        obj.visible = true;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tab_cycle() {
        let mut bar = StatusBar::new();
        assert_eq!(bar.active_tab, TopTab::Apps);
        bar.next_tab();
        assert_eq!(bar.active_tab, TopTab::Mods);
        bar.next_tab();
        assert_eq!(bar.active_tab, TopTab::Net);
        bar.next_tab();
        assert_eq!(bar.active_tab, TopTab::Apps);
    }

    #[test]
    fn update_info_clock() {
        let mut bar = StatusBar::new();
        let time = SystemTime {
            year: 2025,
            month: 6,
            day: 15,
            hour: 14,
            minute: 30,
            second: 0,
        };
        bar.update_info(Some(&time), None);
        assert_eq!(bar.clock_text, "14:30");
    }

    #[test]
    fn update_info_battery() {
        let mut bar = StatusBar::new();
        let power = PowerInfo {
            battery_percent: Some(75),
            battery_minutes: None,
            state: BatteryState::Discharging,
            cpu: crate::platform::CpuClock {
                current_mhz: 333,
                max_mhz: 333,
            },
        };
        bar.update_info(None, Some(&power));
        assert!(bar.battery_text.contains("75%"));
        assert_eq!(bar.cpu_text, "333MHz");
    }

    #[test]
    fn update_info_no_battery() {
        let mut bar = StatusBar::new();
        let power = PowerInfo {
            battery_percent: None,
            battery_minutes: None,
            state: BatteryState::NoBattery,
            cpu: crate::platform::CpuClock {
                current_mhz: 0,
                max_mhz: 0,
            },
        };
        bar.update_info(None, Some(&power));
        assert_eq!(bar.battery_text, "AC");
        assert!(bar.cpu_text.is_empty());
    }

    #[test]
    fn update_sdi_creates_objects() {
        let bar = StatusBar::new();
        let mut sdi = SdiRegistry::new();
        bar.update_sdi(&mut sdi);
        assert!(sdi.contains("bar_top"));
        assert!(sdi.contains("bar_version"));
        assert!(sdi.contains("bar_clock"));
        assert!(sdi.contains("bar_tab_0"));
        assert!(sdi.contains("bar_tab_1"));
        assert!(sdi.contains("bar_tab_2"));
    }

    #[test]
    fn bar_top_is_overlay() {
        let bar = StatusBar::new();
        let mut sdi = SdiRegistry::new();
        bar.update_sdi(&mut sdi);
        assert!(sdi.get("bar_top").unwrap().overlay);
    }
}
