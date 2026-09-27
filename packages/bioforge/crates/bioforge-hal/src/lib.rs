//! Hardware abstraction layer for BioForge.
//!
//! Provides async driver traits and mock implementations for all physical
//! subsystems: syringe/peristaltic pumps, Peltier thermal control, XY gantry
//! motion, Pi Camera imaging, and environmental sensors.
//!
//! Only mock drivers exist today (for development and CI). Real drivers for
//! the Raspberry Pi (GPIO/SPI/I2C) are planned and will add their hardware
//! dependencies when implemented.

pub mod camera;
pub mod motion;
pub mod pumps;
pub mod sensors;
pub mod thermal;
