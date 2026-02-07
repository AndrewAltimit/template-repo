//! Skin system -- data-driven configuration of visual and behavioral personality.
//!
//! A skin is a TOML manifest referencing layout definitions, theme colors, and
//! feature flags. The core framework interprets skins at runtime.

mod loader;

pub use loader::{Skin, SkinFeatures, SkinLayout, SkinManifest, SkinObjectDef};
