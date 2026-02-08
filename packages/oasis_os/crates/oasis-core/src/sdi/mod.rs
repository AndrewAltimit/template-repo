//! SDI -- Simple Display Interface.
//!
//! The scene-graph engine at the center of OASIS_OS. SDI manages named UI
//! objects with position, size, alpha, z-order, and optional texture data
//! through a flat registry. It is deliberately simple: no DOM, no layout
//! engine, no retained-mode GUI framework. Just a collection of named,
//! positionable, blittable objects with z-ordering and alpha blending.

pub mod helpers;
pub mod object;
pub mod registry;

pub use object::SdiObject;
pub use registry::SdiRegistry;
