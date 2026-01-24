//! In-game keyboard input handler.
//!
//! Polls for hotkey presses and sends IPC commands to the video daemon.
//! Runs in a background thread spawned during DLL initialization.

use crate::log::vlog;
use crate::{OVERLAY_VISIBLE, SHUTDOWN};
use itk_ipc::IpcChannel;
use itk_protocol::{encode, MessageType, VideoLoad, VideoPause, VideoPlay, VideoSeek};
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
const VK_F9: i32 = 0x78;

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
    let mut prev_f9 = false;
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
        let f9 = is_key_down(VK_F9);

        // Detect key-down edges
        if f5 && !prev_f5 {
            let was_visible = OVERLAY_VISIBLE.fetch_xor(true, Ordering::Relaxed);
            let now_visible = !was_visible;
            vlog!("F5: Overlay {}", if now_visible { "ON" } else { "OFF" });
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

        if f9 && !prev_f9 {
            vlog!("F9: Load from clipboard");
            if let Some(url) = read_clipboard_text() {
                let url = url.trim().to_string();
                if !url.is_empty() {
                    vlog!("Loading URL: {}", url);
                    if let Some(channel) = ensure_connected(&mut ipc) {
                        let cmd = VideoLoad {
                            source: url,
                            start_position_ms: 0,
                            autoplay: true,
                        };
                        send_command(channel, MessageType::VideoLoad, &cmd);
                        playing = true;
                        position_ms = 0;
                    }
                } else {
                    vlog!("Clipboard is empty");
                }
            } else {
                vlog!("Failed to read clipboard");
            }
        }

        prev_f5 = f5;
        prev_f6 = f6;
        prev_f7 = f7;
        prev_f8 = f8;
        prev_f9 = f9;
    }
}

/// Check if a key is currently pressed.
fn is_key_down(vk: i32) -> bool {
    unsafe { GetAsyncKeyState(vk) & (0x8000u16 as i16) != 0 }
}

/// Read unicode text from the Windows clipboard.
fn read_clipboard_text() -> Option<String> {
    use windows::Win32::System::DataExchange::{CloseClipboard, GetClipboardData, OpenClipboard};
    use windows::Win32::System::Memory::{GlobalLock, GlobalUnlock};

    const CF_UNICODETEXT: u32 = 13;

    unsafe {
        // Open the clipboard (no window owner)
        if OpenClipboard(None).is_err() {
            return None;
        }

        let result = (|| -> Option<String> {
            // Get the clipboard data as unicode text
            let handle = GetClipboardData(CF_UNICODETEXT).ok()?;

            // The HANDLE from GetClipboardData is actually an HGLOBAL
            let hglobal = windows::Win32::Foundation::HGLOBAL(handle.0 as _);

            // Lock the global memory to get a pointer
            let ptr = GlobalLock(hglobal);
            if ptr.is_null() {
                return None;
            }

            // Read the null-terminated wide string
            let wstr = ptr as *const u16;
            let mut len = 0usize;
            while *wstr.add(len) != 0 {
                len += 1;
                // Safety bound
                if len > 65536 {
                    break;
                }
            }

            let slice = std::slice::from_raw_parts(wstr, len);
            let text = String::from_utf16_lossy(slice);

            let _ = GlobalUnlock(hglobal);
            Some(text)
        })();

        let _ = CloseClipboard();
        result
    }
}

/// Ensure IPC connection is established. Reconnects on failure.
fn ensure_connected(ipc: &mut Option<Box<dyn IpcChannel>>) -> Option<&dyn IpcChannel> {
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
