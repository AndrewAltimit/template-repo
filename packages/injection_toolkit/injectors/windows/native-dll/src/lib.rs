//! # ITK Native DLL Injector Template (Windows)
//!
//! Template for creating injectable DLLs on Windows.
//!
//! ## Injection Methods
//!
//! This DLL can be injected via:
//! - LoadLibrary injection
//! - Manual mapping
//! - Mod frameworks (Reloaded-II, MelonLoader, etc.)
//!
//! ## Customization
//!
//! 1. Implement `on_attach()` to set up your hooks and IPC connection
//! 2. Use a hooking library (detours, minhook) for function hooking
//! 3. Send state updates via the IPC channel

use std::sync::OnceLock;
use windows::Win32::Foundation::{BOOL, HINSTANCE, TRUE};
use windows::Win32::System::SystemServices::{DLL_PROCESS_ATTACH, DLL_PROCESS_DETACH};

static IPC_CHANNEL: OnceLock<itk_ipc::NamedPipeClient> = OnceLock::new();

/// DLL entry point
#[unsafe(no_mangle)]
pub extern "system" fn DllMain(
    _hinst: HINSTANCE,
    reason: u32,
    _reserved: *mut std::ffi::c_void,
) -> BOOL {
    match reason {
        DLL_PROCESS_ATTACH => {
            // Spawn a thread for initialization to avoid loader lock issues
            std::thread::spawn(|| {
                on_attach();
            });
        }
        DLL_PROCESS_DETACH => {
            on_detach();
        }
        _ => {}
    }
    TRUE
}

/// Called when DLL is attached to process
fn on_attach() {
    // Connect to daemon
    match itk_ipc::connect("itk_injector") {
        Ok(channel) => {
            let _ = IPC_CHANNEL.set(channel);
            log("[ITK] Connected to daemon");
        }
        Err(e) => {
            log(&format!("[ITK] Failed to connect to daemon: {:?}", e));
        }
    }

    // TODO: Set up your hooks here
    // Example with a hypothetical hooking library:
    // unsafe {
    //     hooks::install_hook("kernel32.dll", "CreateFileW", my_create_file_hook);
    // }
}

/// Called when DLL is detached from process
fn on_detach() {
    // TODO: Clean up hooks
    log("[ITK] Detaching");
}

/// Send a state update to the daemon
pub fn send_state_event(event_type: &str, data: &str) {
    if let Some(channel) = IPC_CHANNEL.get() {
        let event = itk_protocol::StateEvent {
            app_id: "itk_app".to_string(),
            event_type: event_type.to_string(),
            timestamp_ms: now_ms(),
            data: data.to_string(),
        };

        if let Ok(encoded) = itk_protocol::encode(itk_protocol::MessageType::StateEvent, &event) {
            let _ = channel.send(&encoded);
        }
    }
}

/// Send a screen rect update
pub fn send_screen_rect(x: f32, y: f32, width: f32, height: f32) {
    if let Some(channel) = IPC_CHANNEL.get() {
        let rect = itk_protocol::ScreenRect {
            x,
            y,
            width,
            height,
            rotation: 0.0,
            visible: true,
        };

        if let Ok(encoded) = itk_protocol::encode(itk_protocol::MessageType::ScreenRect, &rect) {
            let _ = channel.send(&encoded);
        }
    }
}

fn now_ms() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

/// Simple logging (OutputDebugString on Windows)
fn log(msg: &str) {
    #[cfg(debug_assertions)]
    {
        use std::ffi::CString;
        if let Ok(c_msg) = CString::new(msg) {
            unsafe {
                windows::Win32::System::Diagnostics::Debug::OutputDebugStringA(
                    windows::core::PCSTR(c_msg.as_ptr() as *const _),
                );
            }
        }
    }
    let _ = msg; // Suppress unused warning in release
}
