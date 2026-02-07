//! Classic skin dashboard -- PSP-style icon grid with cursor navigation.
//!
//! The dashboard manages a paginated icon grid, status bar, and cursor.
//! It creates and updates SDI objects based on its internal state.

mod discovery;

pub use discovery::{AppEntry, discover_apps};

use crate::backend::Color;
use crate::input::Button;
use crate::sdi::SdiRegistry;
use crate::skin::SkinFeatures;

/// Dashboard configuration derived from the skin's feature gates.
#[derive(Debug, Clone)]
pub struct DashboardConfig {
    pub grid_cols: u32,
    pub grid_rows: u32,
    pub icons_per_page: u32,
    pub max_pages: u32,
    /// Grid area origin and cell size (pixels).
    pub grid_x: i32,
    pub grid_y: i32,
    pub cell_w: u32,
    pub cell_h: u32,
    /// Cursor highlight size offset (drawn slightly larger than the icon).
    pub cursor_pad: i32,
}

impl DashboardConfig {
    /// Create a config from skin features and screen dimensions.
    pub fn from_features(features: &SkinFeatures, screen_w: u32, screen_h: u32) -> Self {
        let cols = features.grid_cols;
        let rows = features.grid_rows;
        let status_bar_h = 24u32;
        let padding = 10u32;
        let grid_area_w = screen_w - 2 * padding;
        let grid_area_h = screen_h - status_bar_h - 2 * padding;
        let cell_w = grid_area_w / cols;
        let cell_h = grid_area_h / rows;
        Self {
            grid_cols: cols,
            grid_rows: rows,
            icons_per_page: features.icons_per_page,
            max_pages: features.dashboard_pages,
            grid_x: padding as i32,
            grid_y: (status_bar_h + padding) as i32,
            cell_w,
            cell_h,
            cursor_pad: 4,
        }
    }
}

/// Runtime state for the icon grid dashboard.
#[derive(Debug)]
pub struct DashboardState {
    pub config: DashboardConfig,
    /// All discovered applications.
    pub apps: Vec<AppEntry>,
    /// Current page index (0-based).
    pub page: usize,
    /// Selected icon index within the current page (0-based).
    pub selected: usize,
}

impl DashboardState {
    /// Create a new dashboard with the given config and app list.
    pub fn new(config: DashboardConfig, apps: Vec<AppEntry>) -> Self {
        Self {
            config,
            apps,
            page: 0,
            selected: 0,
        }
    }

    /// Number of pages needed to show all apps.
    pub fn page_count(&self) -> usize {
        let per_page = self.config.icons_per_page as usize;
        if per_page == 0 || self.apps.is_empty() {
            return 1;
        }
        self.apps.len().div_ceil(per_page)
    }

    /// Apps visible on the current page.
    pub fn current_page_apps(&self) -> &[AppEntry] {
        let per_page = self.config.icons_per_page as usize;
        let start = self.page * per_page;
        let end = (start + per_page).min(self.apps.len());
        if start >= self.apps.len() {
            &[]
        } else {
            &self.apps[start..end]
        }
    }

    /// Handle a button press for cursor navigation.
    pub fn handle_input(&mut self, button: &Button) {
        let cols = self.config.grid_cols as usize;
        let page_apps = self.current_page_apps().len();
        if page_apps == 0 {
            return;
        }

        match button {
            Button::Right => {
                self.selected = (self.selected + 1) % page_apps;
            },
            Button::Left => {
                if self.selected == 0 {
                    self.selected = page_apps - 1;
                } else {
                    self.selected -= 1;
                }
            },
            Button::Down => {
                let next = self.selected + cols;
                if next < page_apps {
                    self.selected = next;
                }
            },
            Button::Up => {
                if self.selected >= cols {
                    self.selected -= cols;
                }
            },
            _ => {},
        }
    }

    /// Switch to the next page (wraps around).
    pub fn next_page(&mut self) {
        let count = self.page_count();
        self.page = (self.page + 1) % count;
        let page_apps = self.current_page_apps().len();
        if self.selected >= page_apps && page_apps > 0 {
            self.selected = page_apps - 1;
        }
    }

    /// Switch to the previous page (wraps around).
    pub fn prev_page(&mut self) {
        let count = self.page_count();
        if self.page == 0 {
            self.page = count - 1;
        } else {
            self.page -= 1;
        }
        let page_apps = self.current_page_apps().len();
        if self.selected >= page_apps && page_apps > 0 {
            self.selected = page_apps - 1;
        }
    }

    /// Get the currently selected app entry, if any.
    pub fn selected_app(&self) -> Option<&AppEntry> {
        self.current_page_apps().get(self.selected)
    }

    /// Synchronize SDI objects to reflect current dashboard state.
    /// Creates/updates: status bar text, icon grid cells, cursor highlight,
    /// page indicator.
    pub fn update_sdi(&self, sdi: &mut SdiRegistry) {
        let cols = self.config.grid_cols as usize;
        let page_apps = self.current_page_apps();

        // Icon grid cells.
        let per_page = self.config.icons_per_page as usize;
        for i in 0..per_page {
            let name = format!("icon_{i}");
            if !sdi.contains(&name) {
                sdi.create(&name);
            }
            if let Ok(obj) = sdi.get_mut(&name) {
                let col = (i % cols) as i32;
                let row = (i / cols) as i32;
                obj.x = self.config.grid_x + col * self.config.cell_w as i32 + 10;
                obj.y = self.config.grid_y + row * self.config.cell_h as i32 + 10;
                obj.w = self.config.cell_w - 20;
                obj.h = self.config.cell_h - 30;

                if i < page_apps.len() {
                    obj.visible = true;
                    obj.color = page_apps[i].color;
                    // Set text to app title.
                    obj.text = Some(page_apps[i].title.clone());
                    obj.font_size = 10;
                    obj.text_color = Color::WHITE;
                } else {
                    obj.visible = false;
                }
            }
        }

        // Cursor highlight.
        let cursor_name = "cursor_highlight";
        if !sdi.contains(cursor_name) {
            sdi.create(cursor_name);
        }
        if let Ok(cursor) = sdi.get_mut(cursor_name) {
            if !page_apps.is_empty() {
                let sel_col = (self.selected % cols) as i32;
                let sel_row = (self.selected / cols) as i32;
                let pad = self.config.cursor_pad;
                cursor.x = self.config.grid_x + sel_col * self.config.cell_w as i32 + 10 - pad;
                cursor.y = self.config.grid_y + sel_row * self.config.cell_h as i32 + 10 - pad;
                cursor.w = self.config.cell_w - 20 + (pad * 2) as u32;
                cursor.h = self.config.cell_h - 30 + (pad * 2) as u32;
                cursor.color = Color::rgba(255, 255, 255, 80);
                cursor.visible = true;
            } else {
                cursor.visible = false;
            }
        }

        // Page indicator text.
        let page_name = "page_indicator";
        if !sdi.contains(page_name) {
            sdi.create(page_name);
        }
        if let Ok(obj) = sdi.get_mut(page_name) {
            obj.text = Some(format!("Page {}/{}", self.page + 1, self.page_count()));
            obj.x = 200;
            obj.y = 256;
            obj.font_size = 10;
            obj.text_color = Color::rgb(150, 150, 180);
            obj.w = 0;
            obj.h = 0;
        }

        // Status bar: selected app title.
        let title_name = "status_title";
        if !sdi.contains(title_name) {
            sdi.create(title_name);
        }
        if let Ok(obj) = sdi.get_mut(title_name) {
            let title = self
                .selected_app()
                .map(|a| a.title.as_str())
                .unwrap_or("No apps");
            obj.text = Some(title.to_string());
            obj.x = 8;
            obj.y = 4;
            obj.font_size = 12;
            obj.text_color = Color::WHITE;
            obj.w = 0;
            obj.h = 0;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> DashboardConfig {
        DashboardConfig {
            grid_cols: 3,
            grid_rows: 2,
            icons_per_page: 6,
            max_pages: 3,
            grid_x: 10,
            grid_y: 34,
            cell_w: 150,
            cell_h: 110,
            cursor_pad: 4,
        }
    }

    fn test_apps(n: usize) -> Vec<AppEntry> {
        (0..n)
            .map(|i| AppEntry {
                title: format!("App {i}"),
                path: format!("/apps/app{i}"),
                icon_png: Vec::new(),
                color: Color::rgb(100, 100, 100),
            })
            .collect()
    }

    #[test]
    fn page_count_single() {
        let dash = DashboardState::new(test_config(), test_apps(3));
        assert_eq!(dash.page_count(), 1);
    }

    #[test]
    fn page_count_multiple() {
        let dash = DashboardState::new(test_config(), test_apps(10));
        assert_eq!(dash.page_count(), 2);
    }

    #[test]
    fn page_count_exact() {
        let dash = DashboardState::new(test_config(), test_apps(6));
        assert_eq!(dash.page_count(), 1);
    }

    #[test]
    fn page_count_empty() {
        let dash = DashboardState::new(test_config(), vec![]);
        assert_eq!(dash.page_count(), 1);
    }

    #[test]
    fn navigate_right_wraps() {
        let mut dash = DashboardState::new(test_config(), test_apps(3));
        dash.handle_input(&Button::Right);
        assert_eq!(dash.selected, 1);
        dash.handle_input(&Button::Right);
        assert_eq!(dash.selected, 2);
        dash.handle_input(&Button::Right);
        assert_eq!(dash.selected, 0); // Wraps.
    }

    #[test]
    fn navigate_left_wraps() {
        let mut dash = DashboardState::new(test_config(), test_apps(3));
        dash.handle_input(&Button::Left);
        assert_eq!(dash.selected, 2); // Wraps to last.
    }

    #[test]
    fn navigate_down() {
        let mut dash = DashboardState::new(test_config(), test_apps(6));
        dash.handle_input(&Button::Down);
        assert_eq!(dash.selected, 3); // Moved down one row (3 cols).
    }

    #[test]
    fn navigate_up() {
        let mut dash = DashboardState::new(test_config(), test_apps(6));
        dash.selected = 4;
        dash.handle_input(&Button::Up);
        assert_eq!(dash.selected, 1);
    }

    #[test]
    fn next_page_wraps() {
        let mut dash = DashboardState::new(test_config(), test_apps(10));
        assert_eq!(dash.page, 0);
        dash.next_page();
        assert_eq!(dash.page, 1);
        dash.next_page();
        assert_eq!(dash.page, 0); // Wraps (2 pages).
    }

    #[test]
    fn prev_page_wraps() {
        let mut dash = DashboardState::new(test_config(), test_apps(10));
        dash.prev_page();
        assert_eq!(dash.page, 1); // Wraps to last.
    }

    #[test]
    fn selected_app() {
        let dash = DashboardState::new(test_config(), test_apps(3));
        let app = dash.selected_app().unwrap();
        assert_eq!(app.title, "App 0");
    }

    #[test]
    fn update_sdi_creates_objects() {
        let dash = DashboardState::new(test_config(), test_apps(3));
        let mut sdi = SdiRegistry::new();
        dash.update_sdi(&mut sdi);
        assert!(sdi.contains("icon_0"));
        assert!(sdi.contains("icon_1"));
        assert!(sdi.contains("icon_2"));
        assert!(sdi.contains("cursor_highlight"));
        assert!(sdi.contains("page_indicator"));
        assert!(sdi.contains("status_title"));
    }

    #[test]
    fn selected_clamps_on_page_switch() {
        let mut dash = DashboardState::new(test_config(), test_apps(8));
        // 8 apps, 6 per page: page 0 has 6, page 1 has 2.
        dash.selected = 5; // Last on page 0.
        dash.next_page();
        // Page 1 has only 2 apps, so selected should clamp to 1.
        assert!(dash.selected <= 1);
    }
}
