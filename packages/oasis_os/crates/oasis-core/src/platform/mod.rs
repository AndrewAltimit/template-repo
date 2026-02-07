//! Platform service abstractions.
//!
//! Traits for hardware/OS services that differ across platforms (PSP, Linux,
//! UE5). The `DesktopPlatform` provides a default implementation using
//! `std` facilities for development and Pi deployment.

mod services;

pub use services::{
    BatteryState, CpuClock, DesktopPlatform, OskResult, OskService, Platform, PowerInfo,
    PowerService, SystemTime, TimeService, UsbService, UsbState,
};

#[cfg(test)]
mod tests;
