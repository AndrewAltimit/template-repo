//! Centralized UI theme and layout constants.
//!
//! All magic numbers for colors, spacing, and screen layout live here
//! so they can be changed in one place and stay consistent across modules.

use crate::backend::Color;

// -- Screen geometry ----------------------------------------------------------

/// Virtual screen width (PSP native).
pub const SCREEN_W: u32 = 480;
/// Virtual screen height (PSP native).
pub const SCREEN_H: u32 = 272;

/// Status bar height at top of screen.
pub const STATUSBAR_H: u32 = 24;
/// Tab row height immediately below status bar.
pub const TAB_ROW_H: u32 = 18;
/// Bottom bar height at bottom of screen.
pub const BOTTOMBAR_H: u32 = 24;

/// Y origin for the bottom bar.
pub const BOTTOMBAR_Y: i32 = (SCREEN_H - BOTTOMBAR_H) as i32;

/// Content area top (below status bar + tab row).
pub const CONTENT_TOP: u32 = STATUSBAR_H + TAB_ROW_H;
/// Content area height (between tab row and bottom bar).
pub const CONTENT_H: u32 = SCREEN_H - CONTENT_TOP - BOTTOMBAR_H;

// -- Font metrics -------------------------------------------------------------

/// Bitmap font character width (8x8 pixel font).
pub const CHAR_W: i32 = 8;
/// Small font size used for bar labels.
pub const FONT_SMALL: u16 = 8;

// -- Status bar tab layout ----------------------------------------------------

/// X offset where top tabs start (after the "OSS" label).
pub const TAB_START_X: i32 = 34;
/// Width of each top tab box.
pub const TAB_W: i32 = 45;
/// Height of each top tab box.
pub const TAB_H: i32 = 16;
/// Horizontal gap between top tabs.
pub const TAB_GAP: i32 = 4;

// -- Bottom bar layout --------------------------------------------------------

/// Pipe gap between media category labels (pixels).
pub const PIPE_GAP: i32 = 5;
/// Maximum number of page dots displayed.
pub const MAX_PAGE_DOTS: usize = 4;
/// Width reserved for the "R>" shoulder hint.
pub const R_HINT_W: i32 = 28;

// -- Colors -------------------------------------------------------------------

/// Semi-transparent black for status/bottom bar backgrounds.
pub const BAR_BG: Color = Color::rgba(0, 0, 0, 90);
/// Status bar background (slightly less opaque).
pub const STATUSBAR_BG: Color = Color::rgba(0, 0, 0, 80);
/// Thin separator line color.
pub const SEPARATOR_COLOR: Color = Color::rgba(255, 255, 255, 50);
/// Battery/power info text color (green tint).
pub const BATTERY_COLOR: Color = Color::rgb(120, 255, 120);
/// Version label color.
pub const VERSION_COLOR: Color = Color::WHITE;
/// Clock text color.
pub const CLOCK_COLOR: Color = Color::WHITE;
/// URL text color in bottom bar.
pub const URL_COLOR: Color = Color::rgb(200, 200, 200);
/// USB indicator text color.
pub const USB_COLOR: Color = Color::rgb(140, 140, 140);
/// Active tab border alpha (bright white).
pub const TAB_ACTIVE_ALPHA: u8 = 180;
/// Inactive tab border alpha (dim).
pub const TAB_INACTIVE_ALPHA: u8 = 60;
/// Active tab fill color (very subtle white).
pub const TAB_ACTIVE_FILL: Color = Color::rgba(255, 255, 255, 30);
/// Inactive tab fill color (fully transparent).
pub const TAB_INACTIVE_FILL: Color = Color::rgba(0, 0, 0, 0);
/// Active media tab text color.
pub const MEDIA_TAB_ACTIVE: Color = Color::WHITE;
/// Inactive media tab text color.
pub const MEDIA_TAB_INACTIVE: Color = Color::rgb(170, 170, 170);
/// Pipe separator color between media tabs.
pub const PIPE_COLOR: Color = Color::rgba(255, 255, 255, 60);
/// "R>" shoulder hint color.
pub const R_HINT_COLOR: Color = Color::rgba(255, 255, 255, 140);
/// Category label (OSS/MSO) color.
pub const CATEGORY_LABEL_COLOR: Color = Color::rgb(220, 220, 220);
/// Page dot active color.
pub const PAGE_DOT_ACTIVE: Color = Color::rgba(255, 255, 255, 200);
/// Page dot inactive color.
pub const PAGE_DOT_INACTIVE: Color = Color::rgba(255, 255, 255, 50);

// -- Icon theme ---------------------------------------------------------------

/// Document icon width.
pub const ICON_W: u32 = 42;
/// Document icon height.
pub const ICON_H: u32 = 52;
/// Colored stripe height at top of document icon.
pub const ICON_STRIPE_H: u32 = 12;
/// Folded corner size.
pub const ICON_FOLD_SIZE: u32 = 10;
/// App graphic height on document body.
pub const ICON_GFX_H: u32 = 22;
/// App graphic horizontal padding inside icon.
pub const ICON_GFX_PAD: u32 = 4;
/// Gap between icon bottom and label text.
pub const ICON_LABEL_PAD: i32 = 4;
/// Document body color (white paper).
pub const ICON_BODY_COLOR: Color = Color::rgb(250, 250, 248);
/// Folded corner color.
pub const ICON_FOLD_COLOR: Color = Color::rgb(210, 210, 205);
/// Icon white outline color.
pub const ICON_OUTLINE_COLOR: Color = Color::rgba(255, 255, 255, 180);
/// Icon drop shadow color.
pub const ICON_SHADOW_COLOR: Color = Color::rgba(0, 0, 0, 70);
/// Icon label text color.
pub const ICON_LABEL_COLOR: Color = Color::rgba(255, 255, 255, 230);
/// Cursor highlight color.
pub const CURSOR_COLOR: Color = Color::rgba(255, 255, 255, 50);

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn layout_fits_screen() {
        assert_eq!(CONTENT_TOP + CONTENT_H + BOTTOMBAR_H, SCREEN_H);
    }

    #[test]
    fn bottombar_y_consistent() {
        assert_eq!(BOTTOMBAR_Y, (SCREEN_H - BOTTOMBAR_H) as i32);
    }
}
