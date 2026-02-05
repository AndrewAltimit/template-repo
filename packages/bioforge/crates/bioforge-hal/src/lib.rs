//! Hardware abstraction layer for BioForge.
//!
//! Provides async driver traits and mock implementations for all physical
//! subsystems: syringe/peristaltic pumps, Peltier thermal control, XY gantry
//! motion, Pi Camera imaging, and environmental sensors.
//!
//! On aarch64 targets, real implementations use `rppal` for GPIO/SPI/I2C.
//! On other targets, only mock drivers are available (for development and CI).

pub mod camera;
pub mod motion;
pub mod pumps;
pub mod sensors;
pub mod thermal;
