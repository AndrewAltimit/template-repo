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
use crate::theme;

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
    /// Uses PSIX-style layout: icons on the left side with generous spacing.
    pub fn from_features(features: &SkinFeatures) -> Self {
        let cols = features.grid_cols;
        let rows = features.grid_rows;
        // PSIX places icons on the left ~half of the screen, sparsely.
        let grid_padding_x = 16u32;
        let grid_padding_y = 6u32;
        let cell_w = 110u32; // Wide cells for larger icons + labels.
        let cell_h = (theme::CONTENT_H - 2 * grid_padding_y) / rows;
        Self {
            grid_cols: cols,
            grid_rows: rows,
            icons_per_page: features.icons_per_page,
            max_pages: features.dashboard_pages,
            grid_x: grid_padding_x as i32,
            grid_y: (theme::CONTENT_TOP + grid_padding_y) as i32,
            cell_w,
            cell_h,
            cursor_pad: 3,
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
    /// Creates/updates: PSIX-style document icons (white page with colored accent,
    /// folded corner, and app graphic), text label below each, and cursor highlight.
    pub fn update_sdi(&self, sdi: &mut SdiRegistry) {
        let cols = self.config.grid_cols as usize;
        let page_apps = self.current_page_apps();

        let icon_w = theme::ICON_W;
        let icon_h = theme::ICON_H;
        let stripe_h = theme::ICON_STRIPE_H;
        let fold_size = theme::ICON_FOLD_SIZE;
        let text_pad = theme::ICON_LABEL_PAD;
        let gfx_pad = theme::ICON_GFX_PAD;
        let gfx_w = icon_w - 2 * gfx_pad;
        let gfx_h = theme::ICON_GFX_H;

        let per_page = self.config.icons_per_page as usize;
        for i in 0..per_page {
            let outline_name = format!("icon_outline_{i}");
            let icon_name = format!("icon_{i}");
            let stripe_name = format!("icon_stripe_{i}");
            let fold_name = format!("icon_fold_{i}");
            let gfx_name = format!("icon_gfx_{i}");
            let label_name = format!("icon_label_{i}");
            let shadow_name = format!("icon_shadow_{i}");

            for name in [
                &outline_name,
                &icon_name,
                &stripe_name,
                &fold_name,
                &gfx_name,
                &label_name,
                &shadow_name,
            ] {
                if !sdi.contains(name) {
                    sdi.create(name);
                }
            }

            let col = (i % cols) as i32;
            let row = (i / cols) as i32;
            let cell_x = self.config.grid_x + col * self.config.cell_w as i32;
            let cell_y = self.config.grid_y + row * self.config.cell_h as i32;
            let ix = cell_x + (self.config.cell_w as i32 - icon_w as i32) / 2;
            let iy = cell_y + 4;

            if i < page_apps.len() {
                // Drop shadow behind document (offset down-right).
                if let Ok(obj) = sdi.get_mut(&shadow_name) {
                    obj.x = ix + 2;
                    obj.y = iy + 3;
                    obj.w = icon_w + 2;
                    obj.h = icon_h + 1;
                    obj.visible = true;
                    obj.color = theme::ICON_SHADOW_COLOR;
                    obj.text = None;
                }

                // White border/outline (1px larger than icon on each side).
                if let Ok(obj) = sdi.get_mut(&outline_name) {
                    obj.x = ix - 1;
                    obj.y = iy - 1;
                    obj.w = icon_w + 2;
                    obj.h = icon_h + 2;
                    obj.visible = true;
                    obj.color = theme::ICON_OUTLINE_COLOR;
                    obj.text = None;
                }

                // White document page body (bright, like paper).
                if let Ok(obj) = sdi.get_mut(&icon_name) {
                    obj.x = ix;
                    obj.y = iy;
                    obj.w = icon_w;
                    obj.h = icon_h;
                    obj.visible = true;
                    obj.color = theme::ICON_BODY_COLOR;
                    obj.text = None;
                }

                // Colored stripe at top of document (app accent color).
                if let Ok(obj) = sdi.get_mut(&stripe_name) {
                    obj.x = ix;
                    obj.y = iy;
                    obj.w = icon_w - fold_size;
                    obj.h = stripe_h;
                    obj.visible = true;
                    obj.color = page_apps[i].color;
                    obj.text = None;
                }

                // Folded corner (top-right) -- lighter crease to simulate fold.
                if let Ok(obj) = sdi.get_mut(&fold_name) {
                    obj.x = ix + icon_w as i32 - fold_size as i32;
                    obj.y = iy;
                    obj.w = fold_size;
                    obj.h = fold_size;
                    obj.visible = true;
                    obj.color = theme::ICON_FOLD_COLOR;
                    obj.text = None;
                }

                // Colored app graphic on the document body (PSIX-style icon image).
                if let Ok(obj) = sdi.get_mut(&gfx_name) {
                    obj.x = ix + gfx_pad as i32;
                    obj.y = iy + stripe_h as i32 + 3;
                    obj.w = gfx_w;
                    obj.h = gfx_h;
                    obj.visible = true;
                    // Vibrant version of the app accent color for the graphic.
                    let c = page_apps[i].color;
                    obj.color = Color::rgba(
                        c.r.saturating_add(30),
                        c.g.saturating_add(10),
                        c.b.saturating_add(30),
                        200,
                    );
                    obj.text = None;
                }

                // Label below the document icon.
                if let Ok(obj) = sdi.get_mut(&label_name) {
                    obj.x = cell_x;
                    obj.y = iy + icon_h as i32 + text_pad;
                    obj.w = 0;
                    obj.h = 0;
                    obj.font_size = 8;
                    obj.text = Some(page_apps[i].title.clone());
                    obj.text_color = theme::ICON_LABEL_COLOR;
                    obj.visible = true;
                }
            } else {
                for name in [
                    &outline_name,
                    &icon_name,
                    &stripe_name,
                    &fold_name,
                    &gfx_name,
                    &label_name,
                    &shadow_name,
                ] {
                    if let Ok(obj) = sdi.get_mut(name) {
                        obj.visible = false;
                    }
                }
            }
        }

        // Cursor highlight (translucent white glow around selected icon).
        let cursor_name = "cursor_highlight";
        if !sdi.contains(cursor_name) {
            sdi.create(cursor_name);
        }
        if let Ok(cursor) = sdi.get_mut(cursor_name) {
            if !page_apps.is_empty() {
                let sel_col = (self.selected % cols) as i32;
                let sel_row = (self.selected / cols) as i32;
                let pad = self.config.cursor_pad;
                let cell_x = self.config.grid_x + sel_col * self.config.cell_w as i32;
                let cell_y = self.config.grid_y + sel_row * self.config.cell_h as i32;
                let ix = cell_x + (self.config.cell_w as i32 - icon_w as i32) / 2;
                let iy = cell_y + 4;
                cursor.x = ix - pad;
                cursor.y = iy - pad;
                cursor.w = icon_w + (pad * 2) as u32;
                cursor.h = icon_h + (pad * 2) as u32;
                cursor.color = theme::CURSOR_COLOR;
                cursor.visible = true;
                cursor.overlay = true;
            } else {
                cursor.visible = false;
            }
        }
    }

    /// Hide all dashboard SDI objects.
    pub fn hide_sdi(&self, sdi: &mut SdiRegistry) {
        let per_page = self.config.icons_per_page as usize;
        for i in 0..per_page {
            for prefix in &[
                "icon_",
                "icon_label_",
                "icon_outline_",
                "icon_stripe_",
                "icon_fold_",
                "icon_gfx_",
                "icon_shadow_",
            ] {
                let name = format!("{prefix}{i}");
                if let Ok(obj) = sdi.get_mut(&name) {
                    obj.visible = false;
                }
            }
        }
        if let Ok(obj) = sdi.get_mut("cursor_highlight") {
            obj.visible = false;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> DashboardConfig {
        DashboardConfig {
            grid_cols: 2,
            grid_rows: 2,
            icons_per_page: 4,
            max_pages: 4,
            grid_x: 16,
            grid_y: 48,
            cell_w: 110,
            cell_h: 95,
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
        let dash = DashboardState::new(test_config(), test_apps(6));
        assert_eq!(dash.page_count(), 2);
    }

    #[test]
    fn page_count_exact() {
        let dash = DashboardState::new(test_config(), test_apps(4));
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
        let mut dash = DashboardState::new(test_config(), test_apps(4));
        dash.handle_input(&Button::Down);
        assert_eq!(dash.selected, 2); // Moved down one row (2 cols).
    }

    #[test]
    fn navigate_up() {
        let mut dash = DashboardState::new(test_config(), test_apps(4));
        dash.selected = 3;
        dash.handle_input(&Button::Up);
        assert_eq!(dash.selected, 1);
    }

    #[test]
    fn next_page_wraps() {
        let mut dash = DashboardState::new(test_config(), test_apps(6));
        assert_eq!(dash.page, 0);
        dash.next_page();
        assert_eq!(dash.page, 1);
        dash.next_page();
        assert_eq!(dash.page, 0); // Wraps (2 pages).
    }

    #[test]
    fn prev_page_wraps() {
        let mut dash = DashboardState::new(test_config(), test_apps(6));
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
        assert!(sdi.contains("icon_label_0"));
        assert!(sdi.contains("icon_label_1"));
        assert!(sdi.contains("cursor_highlight"));
    }

    #[test]
    fn selected_clamps_on_page_switch() {
        let mut dash = DashboardState::new(test_config(), test_apps(5));
        // 5 apps, 4 per page: page 0 has 4, page 1 has 1.
        dash.selected = 3; // Last on page 0.
        dash.next_page();
        // Page 1 has only 1 app, so selected should clamp to 0.
        assert_eq!(dash.selected, 0);
    }
}
