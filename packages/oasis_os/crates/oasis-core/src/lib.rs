//! OASIS_OS core framework.
//!
//! Platform-agnostic embeddable OS framework providing a scene graph (SDI),
//! backend abstraction traits, input event pipeline, configuration, and
//! error types. This crate has zero platform dependencies.

pub mod agent;
pub mod apps;
pub mod audio;
pub mod backend;
pub mod bottombar;
pub mod config;
pub mod cursor;
pub mod dashboard;
pub mod error;
pub mod input;
pub mod net;
pub mod osk;
pub mod pbp;
pub mod platform;
pub mod plugin;
pub mod script;
pub mod sdi;
pub mod skin;
pub mod statusbar;
pub mod terminal;
pub mod theme;
pub mod transfer;
pub mod transition;
pub mod update;
pub mod vfs;
pub mod wallpaper;
pub mod wm;
