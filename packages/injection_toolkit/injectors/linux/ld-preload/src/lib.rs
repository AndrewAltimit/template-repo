//! # ITK LD_PRELOAD Injector Template
//!
//! Template for creating injectable shared libraries on Linux using LD_PRELOAD.
//!
//! ## Usage
//!
//! ```bash
//! LD_PRELOAD=/path/to/libitk_preload.so ./target_application
//! ```
//!
//! ## Customization
//!
//! 1. Implement `init()` to set up your hooks and IPC connection
//! 2. Use `dlsym(RTLD_NEXT, ...)` to hook functions
//! 3. Send state updates via the IPC channel

use itk_ipc::{IpcChannel, UnixSocketClient};
use std::sync::OnceLock;

static IPC_CHANNEL: OnceLock<UnixSocketClient> = OnceLock::new();

/// Called when the library is loaded (via constructor attribute)
///
/// This is where you should:
/// - Connect to the daemon via IPC
/// - Set up function hooks
/// - Initialize any state tracking
#[unsafe(no_mangle)]
pub extern "C" fn itk_init() {
    // Connect to daemon
    match itk_ipc::connect("itk_injector") {
        Ok(channel) => {
            let _ = IPC_CHANNEL.set(channel);
            // Log success (can't use tracing easily in injected context)
            eprintln!("[ITK] Connected to daemon");
        }
        Err(e) => {
            eprintln!("[ITK] Failed to connect to daemon: {:?}", e);
        }
    }
}

// Example: Hook a function by defining it with the same signature
//
// ```rust,ignore
// #[unsafe(no_mangle)]
// pub extern "C" fn target_function(arg: i32) -> i32 {
//     // Your pre-hook logic here
//
//     // Call the original function
//     type OrigFn = extern "C" fn(i32) -> i32;
//     let orig: OrigFn = unsafe {
//         std::mem::transmute(libc::dlsym(libc::RTLD_NEXT, b"target_function\0".as_ptr() as *const _))
//     };
//     let result = orig(arg);
//
//     // Your post-hook logic here
//
//     result
// }
// ```

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

fn now_ms() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

// Constructor attribute to call itk_init on library load
#[used]
#[unsafe(link_section = ".init_array")]
static INIT: extern "C" fn() = {
    extern "C" fn init() {
        itk_init();
    }
    init
};
