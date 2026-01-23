//! Hook installation and management.
//!
//! Installs detours on Vulkan functions and optionally hooks
//! OpenVR's IVRCompositor::Submit for VR rendering.

pub mod openvr;
pub mod vulkan;

use crate::log::vlog;

/// Install all hooks.
///
/// # Safety
/// Must be called from a thread where the target modules are loaded.
pub unsafe fn install() -> Result<(), String> {
    vlog!("Installing hooks...");

    // Vulkan hooks (required)
    vulkan::install()?;

    // OpenVR hooks (optional - only if VR is active)
    match openvr::try_install() {
        Ok(true) => vlog!("VR hooks installed"),
        Ok(false) => vlog!("VR not active, skipping VR hooks"),
        Err(e) => vlog!("VR hook failed (non-fatal): {}", e),
    }

    vlog!("All hooks installed");
    Ok(())
}

/// Remove all hooks.
///
/// # Safety
/// Must be called during DLL detach.
pub unsafe fn remove() {
    vlog!("Removing hooks...");
    openvr::remove();
    vulkan::remove();
    vlog!("All hooks removed");
}
