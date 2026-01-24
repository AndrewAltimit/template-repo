//! In-game keyboard input handler.
//!
//! Polls for hotkey presses and sends IPC commands to the video daemon.
//! Runs in a background thread spawned during DLL initialization.

use crate::log::vlog;
use crate::SHUTDOWN;
use itk_ipc::IpcChannel;
use itk_protocol::{encode, MessageType, VideoLoad, VideoPause, VideoPlay, VideoSeek};
use std::path::PathBuf;
use std::sync::atomic::Ordering;
use std::thread;
use std::time::Duration;
use windows::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState;

/// IPC channel name to connect to the daemon.
const CLIENT_CHANNEL: &str = "nms_cockpit_client";

/// Polling interval for keyboard state.
const POLL_INTERVAL: Duration = Duration::from_millis(50);

/// Seek step in milliseconds.
const SEEK_STEP_MS: u64 = 10_000;

/// Virtual key codes for hotkeys.
const VK_F5: i32 = 0x74;
const VK_F6: i32 = 0x75;
const VK_F7: i32 = 0x76;
const VK_F8: i32 = 0x77;

/// Start the input handler thread.
pub fn start() {
    thread::spawn(|| {
        vlog!("Input handler starting");
        input_loop();
        vlog!("Input handler stopped");
    });
}

/// Main input polling loop.
fn input_loop() {
    let mut prev_f5 = false;
    let mut prev_f6 = false;
    let mut prev_f7 = false;
    let mut prev_f8 = false;
    let mut playing = false;
    let mut position_ms: u64 = 0;

    // Lazily connected IPC channel
    let mut ipc: Option<Box<dyn IpcChannel>> = None;

    loop {
        if SHUTDOWN.load(Ordering::Acquire) {
            break;
        }

        thread::sleep(POLL_INTERVAL);

        // Read current key states (bit 15 = currently pressed)
        let f5 = is_key_down(VK_F5);
        let f6 = is_key_down(VK_F6);
        let f7 = is_key_down(VK_F7);
        let f8 = is_key_down(VK_F8);

        // Detect key-down edges
        if f5 && !prev_f5 {
            vlog!("F5: Load video");
            if let Some(channel) = ensure_connected(&mut ipc) {
                let path = find_video_path();
                vlog!("Loading: {}", path);
                let cmd = VideoLoad {
                    source: path,
                    start_position_ms: 0,
                    autoplay: true,
                };
                send_command(channel, MessageType::VideoLoad, &cmd);
                playing = true;
                position_ms = 0;
            }
        }

        if f6 && !prev_f6 {
            if let Some(channel) = ensure_connected(&mut ipc) {
                if playing {
                    vlog!("F6: Pause");
                    let cmd = VideoPause {};
                    send_command(channel, MessageType::VideoPause, &cmd);
                    playing = false;
                } else {
                    vlog!("F6: Play");
                    let cmd = VideoPlay {
                        from_position_ms: None,
                    };
                    send_command(channel, MessageType::VideoPlay, &cmd);
                    playing = true;
                }
            }
        }

        if f7 && !prev_f7 {
            if let Some(channel) = ensure_connected(&mut ipc) {
                position_ms = position_ms.saturating_sub(SEEK_STEP_MS);
                vlog!("F7: Seek back to {}ms", position_ms);
                let cmd = VideoSeek { position_ms };
                send_command(channel, MessageType::VideoSeek, &cmd);
            }
        }

        if f8 && !prev_f8 {
            if let Some(channel) = ensure_connected(&mut ipc) {
                position_ms += SEEK_STEP_MS;
                vlog!("F8: Seek forward to {}ms", position_ms);
                let cmd = VideoSeek { position_ms };
                send_command(channel, MessageType::VideoSeek, &cmd);
            }
        }

        prev_f5 = f5;
        prev_f6 = f6;
        prev_f7 = f7;
        prev_f8 = f8;
    }
}

/// Check if a key is currently pressed.
fn is_key_down(vk: i32) -> bool {
    unsafe { GetAsyncKeyState(vk) & (0x8000u16 as i16) != 0 }
}

/// Ensure IPC connection is established. Reconnects on failure.
fn ensure_connected<'a>(ipc: &'a mut Option<Box<dyn IpcChannel>>) -> Option<&'a dyn IpcChannel> {
    // Check if existing connection is still good
    if let Some(ref channel) = ipc {
        if channel.is_connected() {
            return ipc.as_deref();
        }
        vlog!("IPC disconnected, reconnecting...");
    }

    // Try to connect
    match itk_ipc::connect(CLIENT_CHANNEL) {
        Ok(channel) => {
            vlog!("Connected to daemon IPC ({})", CLIENT_CHANNEL);
            *ipc = Some(Box::new(channel));
            ipc.as_deref()
        }
        Err(e) => {
            vlog!("IPC connect failed: {} (is daemon running?)", e);
            *ipc = None;
            None
        }
    }
}

/// Send an encoded ITK protocol command.
fn send_command<T: serde::Serialize>(channel: &dyn IpcChannel, msg_type: MessageType, payload: &T) {
    match encode(msg_type, payload) {
        Ok(data) => {
            if let Err(e) = channel.send(&data) {
                vlog!("IPC send failed: {}", e);
            }
        }
        Err(e) => {
            vlog!("Protocol encode failed: {}", e);
        }
    }
}

/// Find the video file path.
///
/// Checks in order:
/// 1. `nms_video.txt` sidecar file (contains a path on the first line)
/// 2. `nms_video.mp4` next to the DLL
/// 3. Falls back to a hardcoded default
fn find_video_path() -> String {
    let dll_dir = get_dll_directory();

    // Check for sidecar config file
    let config_path = dll_dir.join("nms_video.txt");
    if config_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&config_path) {
            let path = content.trim().to_string();
            if !path.is_empty() {
                return path;
            }
        }
    }

    // Check for video file next to DLL
    let video_path = dll_dir.join("nms_video.mp4");
    if video_path.exists() {
        return video_path.to_string_lossy().to_string();
    }

    // Fallback
    vlog!("No video found at {:?}, using default path", video_path);
    video_path.to_string_lossy().to_string()
}

/// Get the directory containing this DLL.
fn get_dll_directory() -> PathBuf {
    use windows::core::PCSTR;
    use windows::Win32::System::LibraryLoader::{GetModuleFileNameA, GetModuleHandleA};

    unsafe {
        let dll_name = b"nms_cockpit_injector.dll\0";
        let handle = GetModuleHandleA(PCSTR(dll_name.as_ptr()));

        if let Ok(handle) = handle {
            let mut buf = [0u8; 512];
            let len = GetModuleFileNameA(handle, &mut buf);
            if len > 0 {
                let path_str = std::str::from_utf8(&buf[..len as usize]).unwrap_or("");
                if let Some(parent) = std::path::Path::new(path_str).parent() {
                    return parent.to_path_buf();
                }
            }
        }
    }

    // Fallback to current directory
    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}
