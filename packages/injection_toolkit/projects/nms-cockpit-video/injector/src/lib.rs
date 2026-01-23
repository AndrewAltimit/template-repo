//! NMS Cockpit Video Player - Vulkan Texture Injector
//!
//! Injectable DLL that hooks NMS's Vulkan pipeline to render video frames
//! as a textured quad in the cockpit, visible to both desktop and VR users.

pub mod camera;
mod hooks;
mod log;
pub mod renderer;

use log::vlog;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::Duration;
use windows::Win32::Foundation::{BOOL, HINSTANCE, TRUE};
use windows::Win32::System::LibraryLoader::GetModuleHandleA;
use windows::Win32::System::SystemServices::{DLL_PROCESS_ATTACH, DLL_PROCESS_DETACH};

/// Whether the DLL has been initialized.
static INITIALIZED: AtomicBool = AtomicBool::new(false);

/// Whether shutdown has been requested.
static SHUTDOWN: AtomicBool = AtomicBool::new(false);

/// DLL entry point.
#[unsafe(no_mangle)]
pub extern "system" fn DllMain(
    _hinst: HINSTANCE,
    reason: u32,
    _reserved: *mut std::ffi::c_void,
) -> BOOL {
    match reason {
        DLL_PROCESS_ATTACH => {
            // Spawn init thread to avoid loader lock deadlock
            thread::spawn(|| {
                if let Err(e) = init() {
                    vlog!("Init failed: {}", e);
                }
            });
        }
        DLL_PROCESS_DETACH => {
            shutdown();
        }
        _ => {}
    }
    TRUE
}

/// Initialize the injector: wait for Vulkan, install hooks.
fn init() -> Result<(), String> {
    vlog!("Initializing...");

    // Wait for vulkan-1.dll to be loaded by the game
    wait_for_module("vulkan-1.dll", Duration::from_secs(30))?;
    vlog!("vulkan-1.dll found");

    // Install Vulkan hooks
    unsafe {
        hooks::install()?;
    }

    INITIALIZED.store(true, Ordering::Release);
    vlog!("Initialization complete");
    Ok(())
}

/// Wait for a DLL module to be loaded in the current process.
fn wait_for_module(name: &str, timeout: Duration) -> Result<(), String> {
    let start = std::time::Instant::now();
    let name_cstr = std::ffi::CString::new(name).map_err(|e| e.to_string())?;

    loop {
        let handle = unsafe {
            GetModuleHandleA(windows::core::PCSTR(name_cstr.as_ptr() as *const _))
        };

        if handle.is_ok() {
            return Ok(());
        }

        if start.elapsed() > timeout {
            return Err(format!("Timeout waiting for {}", name));
        }

        if SHUTDOWN.load(Ordering::Acquire) {
            return Err("Shutdown requested during init".to_string());
        }

        thread::sleep(Duration::from_millis(100));
    }
}

/// Clean shutdown: remove hooks.
fn shutdown() {
    SHUTDOWN.store(true, Ordering::Release);

    if INITIALIZED.load(Ordering::Acquire) {
        vlog!("Shutting down...");
        unsafe {
            hooks::remove();
        }
        vlog!("Shutdown complete");
    }
}
