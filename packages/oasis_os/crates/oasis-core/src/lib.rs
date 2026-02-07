//! OASIS_OS core framework.
//!
//! Platform-agnostic embeddable OS framework providing a scene graph (SDI),
//! backend abstraction traits, input event pipeline, configuration, and
//! error types. This crate has zero platform dependencies.

pub mod backend;
pub mod config;
pub mod dashboard;
pub mod error;
pub mod input;
pub mod pbp;
pub mod sdi;
pub mod skin;
pub mod terminal;
pub mod vfs;
