//! Skin system -- data-driven configuration of visual and behavioral personality.
//!
//! A skin is a TOML manifest referencing layout definitions, theme colors,
//! feature flags, strings, and optional corrupted modifiers. The core
//! framework interprets skins at runtime. Skins can be hot-swapped.

pub mod builtin;
pub mod corrupted;
mod loader;
pub mod strings;
pub mod theme;

pub use corrupted::{CorruptedModifiers, SimpleRng};
pub use loader::{Skin, SkinFeatures, SkinLayout, SkinManifest, SkinObjectDef};
pub use strings::SkinStrings;
pub use theme::{SkinTheme, WmThemeOverrides};
