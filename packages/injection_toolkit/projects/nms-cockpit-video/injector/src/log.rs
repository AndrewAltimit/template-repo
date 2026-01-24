//! Logging via OutputDebugString + file for DLL injection context.
//!
//! Uses Windows OutputDebugStringA which can be captured by DebugView,
//! and also writes to a log file for reliable post-mortem analysis.

use std::fs::OpenOptions;
use std::io::Write;
use std::sync::Mutex;

static LOG_FILE: Mutex<Option<String>> = Mutex::new(None);

/// Initialize the file log path (call once during init).
pub fn init_file_log() {
    if let Ok(mut path) = LOG_FILE.lock() {
        if path.is_none() {
            // Write log next to the DLL or in temp
            let log_path = std::env::temp_dir().join("nms_video_injector.log");
            *path = Some(log_path.to_string_lossy().into_owned());
            // Truncate on init
            if let Ok(mut f) = std::fs::File::create(&log_path) {
                let _ = writeln!(f, "[NMS-VIDEO] Log initialized");
            }
        }
    }
}

/// Log a message via OutputDebugStringA and to file.
pub fn debug_log(msg: &str) {
    let prefixed = format!("[NMS-VIDEO] {}\0", msg);
    unsafe {
        windows::Win32::System::Diagnostics::Debug::OutputDebugStringA(
            windows::core::PCSTR(prefixed.as_ptr()),
        );
    }

    // Also write to file
    if let Ok(guard) = LOG_FILE.lock() {
        if let Some(path) = guard.as_ref() {
            if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(path) {
                let _ = writeln!(f, "[NMS-VIDEO] {}", msg);
            }
        }
    }
}

/// Formatted logging macro.
macro_rules! vlog {
    ($($arg:tt)*) => {
        $crate::log::debug_log(&format!($($arg)*))
    };
}

pub(crate) use vlog;
