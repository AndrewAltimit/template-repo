//! Window manager.
//!
//! Enables skins that present multiple movable, resizable, overlapping
//! windows. The WM is a consumer of the SDI API -- it creates, positions,
//! and manipulates groups of SDI objects to simulate windowed interfaces.
//! SDI remains a flat, dumb scene graph; the WM is the smart layer on top.

pub mod hit_test;
pub mod manager;
pub mod window;

pub use hit_test::{ButtonKind, HitRegion, ResizeEdge};
pub use manager::{WindowManager, WmEvent};
pub use window::{Geometry, Window, WindowConfig, WindowId, WindowState, WindowType, WmTheme};
