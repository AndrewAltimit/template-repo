//! Logging via OutputDebugString for DLL injection context.
//!
//! Uses Windows OutputDebugStringA which can be captured by DebugView.

/// Log a message via OutputDebugStringA (visible in DebugView/debugger).
pub fn debug_log(msg: &str) {
    let prefixed = format!("[NMS-VIDEO] {}\0", msg);
    unsafe {
        windows::Win32::System::Diagnostics::Debug::OutputDebugStringA(
            windows::core::PCSTR(prefixed.as_ptr()),
        );
    }
}

/// Formatted logging macro.
macro_rules! vlog {
    ($($arg:tt)*) => {
        $crate::log::debug_log(&format!($($arg)*))
    };
}

pub(crate) use vlog;
