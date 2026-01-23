//! Hook installation and management.
//!
//! Installs detours on Vulkan functions to intercept rendering.

pub mod vulkan;

use crate::log::vlog;

/// Install all hooks.
///
/// # Safety
/// Must be called from a thread where the target modules are loaded.
pub unsafe fn install() -> Result<(), String> {
    vlog!("Installing hooks...");
    vulkan::install()?;
    vlog!("All hooks installed");
    Ok(())
}

/// Remove all hooks.
///
/// # Safety
/// Must be called during DLL detach.
pub unsafe fn remove() {
    vlog!("Removing hooks...");
    vulkan::remove();
    vlog!("All hooks removed");
}
