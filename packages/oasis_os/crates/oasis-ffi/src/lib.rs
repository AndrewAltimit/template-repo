//! OASIS_OS C-ABI FFI boundary.
//!
//! Exports an opaque handle API for UE5 (or any C/C++ host) to create,
//! drive, and render OASIS_OS instances. All internal Rust state is behind
//! an opaque `OasisInstance` pointer. UE5 never sees Rust types.
//!
//! # Safety
//!
//! All `extern "C"` functions that take an `*mut OasisInstance` require a
//! valid, non-null handle previously returned by `oasis_create`. Passing
//! null or a freed handle is undefined behavior.

use std::collections::HashMap;
use std::ffi::{CStr, CString};
use std::os::raw::c_char;
use std::sync::Once;

use oasis_backend_ue5::{FfiInputBackend, Ue5Backend};
use oasis_core::backend::{InputBackend, SdiBackend};
use oasis_core::dashboard::{DashboardConfig, DashboardState, discover_apps};
use oasis_core::input::{Button, InputEvent, Trigger};
use oasis_core::platform::DesktopPlatform;
use oasis_core::sdi::SdiRegistry;
use oasis_core::skin::Skin;
use oasis_core::terminal::{CommandOutput, CommandRegistry, Environment, register_builtins};
use oasis_core::vfs::GameAssetVfs;

// ---------------------------------------------------------------------------
// C-compatible types and constants
// ---------------------------------------------------------------------------

/// Input event passed from C to Rust.
#[repr(C)]
pub struct OasisInputEvent {
    /// Event type (one of the `OASIS_EVENT_*` constants).
    pub event_type: u32,
    /// X coordinate (for cursor/pointer events).
    pub x: i32,
    /// Y coordinate (for cursor/pointer events).
    pub y: i32,
    /// Button/trigger code (for button/trigger events).
    pub key: u32,
    /// Unicode codepoint (for text input events).
    pub character: u32,
}

// Event types.
pub const OASIS_EVENT_CURSOR_MOVE: u32 = 1;
pub const OASIS_EVENT_BUTTON_PRESS: u32 = 2;
pub const OASIS_EVENT_BUTTON_RELEASE: u32 = 3;
pub const OASIS_EVENT_TRIGGER_PRESS: u32 = 4;
pub const OASIS_EVENT_TRIGGER_RELEASE: u32 = 5;
pub const OASIS_EVENT_TEXT_INPUT: u32 = 6;
pub const OASIS_EVENT_POINTER_CLICK: u32 = 7;
pub const OASIS_EVENT_POINTER_RELEASE: u32 = 8;
pub const OASIS_EVENT_FOCUS_GAINED: u32 = 9;
pub const OASIS_EVENT_FOCUS_LOST: u32 = 10;
pub const OASIS_EVENT_QUIT: u32 = 11;

// Button codes (match the `Button` enum order).
pub const OASIS_BUTTON_UP: u32 = 0;
pub const OASIS_BUTTON_DOWN: u32 = 1;
pub const OASIS_BUTTON_LEFT: u32 = 2;
pub const OASIS_BUTTON_RIGHT: u32 = 3;
pub const OASIS_BUTTON_CONFIRM: u32 = 4;
pub const OASIS_BUTTON_CANCEL: u32 = 5;
pub const OASIS_BUTTON_TRIANGLE: u32 = 6;
pub const OASIS_BUTTON_SQUARE: u32 = 7;
pub const OASIS_BUTTON_START: u32 = 8;
pub const OASIS_BUTTON_SELECT: u32 = 9;

// Trigger codes.
pub const OASIS_TRIGGER_LEFT: u32 = 0;
pub const OASIS_TRIGGER_RIGHT: u32 = 1;

// Callback event types.
pub const OASIS_CB_FILE_ACCESS: u32 = 1;
pub const OASIS_CB_COMMAND_EXEC: u32 = 2;
pub const OASIS_CB_APP_LAUNCH: u32 = 3;
pub const OASIS_CB_LOGIN: u32 = 4;
pub const OASIS_CB_NETWORK_SEND: u32 = 5;
pub const OASIS_CB_PLUGIN_LOAD: u32 = 6;

/// Callback function type: receives an event type and a null-terminated detail string.
pub type OasisCallback = extern "C" fn(event: u32, detail: *const c_char);

// ---------------------------------------------------------------------------
// Internal instance state
// ---------------------------------------------------------------------------

/// The full internal state of an OASIS_OS instance.
///
/// Opaque to C callers -- they only hold a `*mut OasisInstance`.
pub struct OasisInstance {
    backend: Ue5Backend,
    input: FfiInputBackend,
    sdi: SdiRegistry,
    cmd_reg: CommandRegistry,
    vfs: GameAssetVfs,
    platform: DesktopPlatform,
    #[allow(dead_code)]
    skin: Option<Skin>,
    dashboard: Option<DashboardState>,
    cwd: String,
    #[allow(dead_code)]
    output_lines: Vec<String>,
    callbacks: HashMap<u32, OasisCallback>,
    width: u32,
    height: u32,
}

impl OasisInstance {
    /// Fire a callback if registered.
    fn fire_callback(&self, event: u32, detail: &str) {
        if let Some(cb) = self.callbacks.get(&event) {
            if let Ok(c_detail) = CString::new(detail) {
                cb(event, c_detail.as_ptr());
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Helper: convert C string to Rust
// ---------------------------------------------------------------------------

/// # Safety
/// Caller must ensure `ptr` is null or a valid null-terminated C string.
unsafe fn c_str_to_str<'a>(ptr: *const c_char) -> Option<&'a str> {
    if ptr.is_null() {
        return None;
    }
    // SAFETY: caller guarantees valid null-terminated string.
    unsafe { CStr::from_ptr(ptr) }.to_str().ok()
}

fn button_from_code(code: u32) -> Option<Button> {
    match code {
        OASIS_BUTTON_UP => Some(Button::Up),
        OASIS_BUTTON_DOWN => Some(Button::Down),
        OASIS_BUTTON_LEFT => Some(Button::Left),
        OASIS_BUTTON_RIGHT => Some(Button::Right),
        OASIS_BUTTON_CONFIRM => Some(Button::Confirm),
        OASIS_BUTTON_CANCEL => Some(Button::Cancel),
        OASIS_BUTTON_TRIANGLE => Some(Button::Triangle),
        OASIS_BUTTON_SQUARE => Some(Button::Square),
        OASIS_BUTTON_START => Some(Button::Start),
        OASIS_BUTTON_SELECT => Some(Button::Select),
        _ => None,
    }
}

fn trigger_from_code(code: u32) -> Option<Trigger> {
    match code {
        OASIS_TRIGGER_LEFT => Some(Trigger::Left),
        OASIS_TRIGGER_RIGHT => Some(Trigger::Right),
        _ => None,
    }
}

// ---------------------------------------------------------------------------
// FFI functions
// ---------------------------------------------------------------------------

static INIT_LOGGER: Once = Once::new();

/// Create a new OASIS_OS instance.
///
/// `width` and `height` set the virtual screen resolution.
/// `skin_toml`, `layout_toml`, and `features_toml` are optional null-terminated
/// TOML strings. Pass null for any to use defaults.
///
/// Returns an opaque handle, or null on failure.
///
/// # Safety
///
/// String pointers must be null or valid null-terminated C strings.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn oasis_create(
    width: u32,
    height: u32,
    skin_toml: *const c_char,
    layout_toml: *const c_char,
    features_toml: *const c_char,
) -> *mut OasisInstance {
    INIT_LOGGER.call_once(|| {
        let _ = env_logger::try_init();
    });

    let skin_str = unsafe { c_str_to_str(skin_toml) };
    let layout_str = unsafe { c_str_to_str(layout_toml) };
    let features_str = unsafe { c_str_to_str(features_toml) };

    let mut backend = Ue5Backend::new(width, height);
    if backend.init(width, height).is_err() {
        return std::ptr::null_mut();
    }

    let input = FfiInputBackend::new();
    let mut sdi = SdiRegistry::new();
    let mut cmd_reg = CommandRegistry::new();
    register_builtins(&mut cmd_reg);

    let mut vfs = GameAssetVfs::new();
    vfs.add_base_dir("/home");
    vfs.add_base_dir("/etc");
    vfs.add_base_dir("/tmp");

    let platform = DesktopPlatform::new();

    // Try to load skin if all three TOML strings are provided.
    let skin = match (skin_str, layout_str, features_str) {
        (Some(s), Some(l), Some(f)) => Skin::from_toml(s, l, f).ok(),
        _ => None,
    };

    // Apply skin layout if available.
    let dashboard = if let Some(ref skin) = skin {
        skin.apply_layout(&mut sdi);
        let apps = discover_apps(&vfs, "/apps", None).unwrap_or_default();
        let dash_config = DashboardConfig::from_features(&skin.features);
        Some(DashboardState::new(dash_config, apps))
    } else {
        None
    };

    let instance = OasisInstance {
        backend,
        input,
        sdi,
        cmd_reg,
        vfs,
        platform,
        skin,
        dashboard,
        cwd: "/".to_string(),
        output_lines: Vec::new(),
        callbacks: HashMap::new(),
        width,
        height,
    };

    Box::into_raw(Box::new(instance))
}

/// Destroy an OASIS_OS instance and free its memory.
///
/// # Safety
///
/// `handle` must be a valid pointer returned by `oasis_create`, or null.
/// After this call, `handle` is invalid and must not be used.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn oasis_destroy(handle: *mut OasisInstance) {
    if !handle.is_null() {
        let mut instance = unsafe { Box::from_raw(handle) };
        let _ = instance.backend.shutdown();
        drop(instance);
    }
}

/// Advance the OS state by one frame.
///
/// Processes queued input events and updates the scene graph.
///
/// # Safety
///
/// `handle` must be a valid, non-null instance pointer.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn oasis_tick(handle: *mut OasisInstance, _delta_seconds: f32) {
    let Some(instance) = (unsafe { handle.as_mut() }) else {
        return;
    };

    // Process queued input events.
    let events = instance.input.poll_events();

    // Collect callback details to fire after releasing dashboard borrow.
    let mut pending_callbacks: Vec<(u32, String)> = Vec::new();

    for event in &events {
        match event {
            InputEvent::ButtonPress(btn) => {
                if let Some(ref mut dashboard) = instance.dashboard {
                    match btn {
                        Button::Up | Button::Down | Button::Left | Button::Right => {
                            dashboard.handle_input(btn);
                        },
                        Button::Confirm => {
                            if let Some(app) = dashboard.selected_app() {
                                pending_callbacks.push((OASIS_CB_APP_LAUNCH, app.title.clone()));
                            }
                        },
                        _ => {},
                    }
                }
            },
            InputEvent::TriggerPress(Trigger::Right) => {
                if let Some(ref mut dashboard) = instance.dashboard {
                    dashboard.next_page();
                }
            },
            InputEvent::TriggerPress(Trigger::Left) => {
                if let Some(ref mut dashboard) = instance.dashboard {
                    dashboard.prev_page();
                }
            },
            _ => {},
        }
    }

    // Fire pending callbacks outside the dashboard borrow scope.
    for (event, detail) in &pending_callbacks {
        instance.fire_callback(*event, detail);
    }

    // Update SDI.
    if let Some(ref dashboard) = instance.dashboard {
        dashboard.update_sdi(&mut instance.sdi);
    }

    // Render.
    let _ = instance
        .backend
        .clear(oasis_core::backend::Color::rgb(10, 10, 18));
    let _ = instance.sdi.draw(&mut instance.backend);
    let _ = instance.backend.swap_buffers();
}

/// Deliver an input event to the OS instance.
///
/// # Safety
///
/// `handle` must be valid and non-null. `event` must point to a valid
/// `OasisInputEvent`.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn oasis_send_input(
    handle: *mut OasisInstance,
    event: *const OasisInputEvent,
) {
    let Some(instance) = (unsafe { handle.as_mut() }) else {
        return;
    };
    let Some(evt) = (unsafe { event.as_ref() }) else {
        return;
    };

    let input_event = match evt.event_type {
        OASIS_EVENT_CURSOR_MOVE => Some(InputEvent::CursorMove { x: evt.x, y: evt.y }),
        OASIS_EVENT_BUTTON_PRESS => button_from_code(evt.key).map(InputEvent::ButtonPress),
        OASIS_EVENT_BUTTON_RELEASE => button_from_code(evt.key).map(InputEvent::ButtonRelease),
        OASIS_EVENT_TRIGGER_PRESS => trigger_from_code(evt.key).map(InputEvent::TriggerPress),
        OASIS_EVENT_TRIGGER_RELEASE => trigger_from_code(evt.key).map(InputEvent::TriggerRelease),
        OASIS_EVENT_TEXT_INPUT => char::from_u32(evt.character).map(InputEvent::TextInput),
        OASIS_EVENT_POINTER_CLICK => Some(InputEvent::PointerClick { x: evt.x, y: evt.y }),
        OASIS_EVENT_POINTER_RELEASE => Some(InputEvent::PointerRelease { x: evt.x, y: evt.y }),
        OASIS_EVENT_FOCUS_GAINED => Some(InputEvent::FocusGained),
        OASIS_EVENT_FOCUS_LOST => Some(InputEvent::FocusLost),
        OASIS_EVENT_QUIT => Some(InputEvent::Quit),
        _ => None,
    };

    if let Some(ie) = input_event {
        instance.input.push_event(ie);
    }
}

/// Get a pointer to the RGBA framebuffer.
///
/// Writes the buffer dimensions to `out_width` and `out_height` if non-null.
/// The returned pointer is valid until the next `oasis_tick` or `oasis_destroy`.
///
/// # Safety
///
/// `handle` must be valid. `out_width` and `out_height` may be null.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn oasis_get_buffer(
    handle: *mut OasisInstance,
    out_width: *mut u32,
    out_height: *mut u32,
) -> *const u8 {
    let Some(instance) = (unsafe { handle.as_ref() }) else {
        return std::ptr::null();
    };

    if let Some(w) = unsafe { out_width.as_mut() } {
        *w = instance.width;
    }
    if let Some(h) = unsafe { out_height.as_mut() } {
        *h = instance.height;
    }

    instance.backend.buffer().as_ptr()
}

/// Check whether the framebuffer has changed since the last read.
///
/// # Safety
///
/// `handle` must be valid and non-null.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn oasis_get_dirty(handle: *mut OasisInstance) -> bool {
    let Some(instance) = (unsafe { handle.as_mut() }) else {
        return false;
    };

    let dirty = instance.backend.is_dirty();
    if dirty {
        instance.backend.clear_dirty();
    }
    dirty
}

/// Execute a terminal command and return the output as a C string.
///
/// The caller must free the returned string with `oasis_free_string`.
/// Returns null on error.
///
/// # Safety
///
/// `handle` must be valid. `cmd` must be a valid null-terminated C string.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn oasis_send_command(
    handle: *mut OasisInstance,
    cmd: *const c_char,
) -> *mut c_char {
    let Some(instance) = (unsafe { handle.as_mut() }) else {
        return std::ptr::null_mut();
    };
    let Some(cmd_str) = (unsafe { c_str_to_str(cmd) }) else {
        return std::ptr::null_mut();
    };

    instance.fire_callback(OASIS_CB_COMMAND_EXEC, cmd_str);

    let mut env = Environment {
        cwd: instance.cwd.clone(),
        vfs: &mut instance.vfs,
        power: Some(&instance.platform),
        time: Some(&instance.platform),
        usb: Some(&instance.platform),
    };

    let output = match instance.cmd_reg.execute(cmd_str, &mut env) {
        Ok(CommandOutput::Text(text)) => text,
        Ok(CommandOutput::Table { headers, rows }) => {
            let mut out = headers.join(" | ");
            for row in &rows {
                out.push('\n');
                out.push_str(&row.join(" | "));
            }
            out
        },
        Ok(CommandOutput::Clear) => String::new(),
        Ok(CommandOutput::None) => String::new(),
        Ok(CommandOutput::ListenToggle { .. }) | Ok(CommandOutput::RemoteConnect { .. }) => {
            "Not available via FFI.".to_string()
        },
        Err(e) => format!("error: {e}"),
    };

    instance.cwd = env.cwd;

    CString::new(output)
        .map(|cs| cs.into_raw())
        .unwrap_or(std::ptr::null_mut())
}

/// Free a string previously returned by `oasis_send_command`.
///
/// # Safety
///
/// `ptr` must be a pointer returned by `oasis_send_command`, or null.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn oasis_free_string(ptr: *mut c_char) {
    if !ptr.is_null() {
        drop(unsafe { CString::from_raw(ptr) });
    }
}

/// Change the VFS root by populating the game asset VFS with content.
///
/// `path` is a virtual path prefix. Files should be added via
/// `oasis_send_command("write ...")` or the VFS will be pre-populated
/// by the host application before ticking.
///
/// This resets the current working directory to "/".
///
/// # Safety
///
/// `handle` must be valid. `path` must be a valid C string or null.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn oasis_set_vfs_root(handle: *mut OasisInstance, _path: *const c_char) {
    let Some(instance) = (unsafe { handle.as_mut() }) else {
        return;
    };
    // Reset to clean VFS state.
    instance.vfs = GameAssetVfs::new();
    instance.vfs.add_base_dir("/home");
    instance.vfs.add_base_dir("/etc");
    instance.vfs.add_base_dir("/tmp");
    instance.cwd = "/".to_string();
}

/// Register a callback for OS events.
///
/// `event` is one of the `OASIS_CB_*` constants.
/// `cb` is the function to call when the event fires.
///
/// # Safety
///
/// `handle` must be valid. `cb` must be a valid function pointer.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn oasis_register_callback(
    handle: *mut OasisInstance,
    event: u32,
    cb: OasisCallback,
) {
    let Some(instance) = (unsafe { handle.as_mut() }) else {
        return;
    };
    instance.callbacks.insert(event, cb);
}

/// Add a file to the instance's game asset VFS base layer.
///
/// Useful for pre-populating the VFS from the host application before
/// the first tick. The file is read-only from the terminal's perspective
/// (writes create overlay entries).
///
/// # Safety
///
/// `handle` must be valid. `path` and `data` must be valid pointers.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn oasis_add_vfs_file(
    handle: *mut OasisInstance,
    path: *const c_char,
    data: *const u8,
    data_len: u32,
) {
    let Some(instance) = (unsafe { handle.as_mut() }) else {
        return;
    };
    let Some(path_str) = (unsafe { c_str_to_str(path) }) else {
        return;
    };
    if data.is_null() {
        return;
    }
    let slice = unsafe { std::slice::from_raw_parts(data, data_len as usize) };
    instance.vfs.add_base_file(path_str, slice);
}

// ---------------------------------------------------------------------------
// Tests (Rust-side, exercising the FFI functions directly)
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn create_instance() -> *mut OasisInstance {
        unsafe {
            oasis_create(
                480,
                272,
                std::ptr::null(),
                std::ptr::null(),
                std::ptr::null(),
            )
        }
    }

    #[test]
    fn create_and_destroy() {
        let handle = create_instance();
        assert!(!handle.is_null());
        unsafe { oasis_destroy(handle) };
    }

    #[test]
    fn destroy_null_is_safe() {
        unsafe { oasis_destroy(std::ptr::null_mut()) };
    }

    #[test]
    fn tick_advances_state() {
        let handle = create_instance();
        unsafe { oasis_tick(handle, 0.016) };
        // Should be dirty after first tick.
        assert!(unsafe { oasis_get_dirty(handle) });
        // After reading dirty, should be clear.
        assert!(!unsafe { oasis_get_dirty(handle) });
        unsafe { oasis_destroy(handle) };
    }

    #[test]
    fn get_buffer_returns_valid_pointer() {
        let handle = create_instance();
        let mut w: u32 = 0;
        let mut h: u32 = 0;
        let ptr = unsafe { oasis_get_buffer(handle, &mut w, &mut h) };
        assert!(!ptr.is_null());
        assert_eq!(w, 480);
        assert_eq!(h, 272);
        unsafe { oasis_destroy(handle) };
    }

    #[test]
    fn send_command_help() {
        let handle = create_instance();
        let cmd = CString::new("help").unwrap();
        let result = unsafe { oasis_send_command(handle, cmd.as_ptr()) };
        assert!(!result.is_null());
        let output = unsafe { CStr::from_ptr(result) }.to_string_lossy();
        assert!(output.contains("help"));
        unsafe { oasis_free_string(result) };
        unsafe { oasis_destroy(handle) };
    }

    #[test]
    fn send_command_status() {
        let handle = create_instance();
        let cmd = CString::new("status").unwrap();
        let result = unsafe { oasis_send_command(handle, cmd.as_ptr()) };
        assert!(!result.is_null());
        let output = unsafe { CStr::from_ptr(result) }.to_string_lossy();
        assert!(output.contains("OASIS"));
        unsafe { oasis_free_string(result) };
        unsafe { oasis_destroy(handle) };
    }

    #[test]
    fn send_command_unknown() {
        let handle = create_instance();
        let cmd = CString::new("nonexistent_cmd").unwrap();
        let result = unsafe { oasis_send_command(handle, cmd.as_ptr()) };
        assert!(!result.is_null());
        let output = unsafe { CStr::from_ptr(result) }.to_string_lossy();
        assert!(output.contains("error"));
        unsafe { oasis_free_string(result) };
        unsafe { oasis_destroy(handle) };
    }

    #[test]
    fn send_input_button() {
        let handle = create_instance();
        let evt = OasisInputEvent {
            event_type: OASIS_EVENT_BUTTON_PRESS,
            x: 0,
            y: 0,
            key: OASIS_BUTTON_DOWN,
            character: 0,
        };
        unsafe { oasis_send_input(handle, &evt) };
        // Tick to process the event.
        unsafe { oasis_tick(handle, 0.016) };
        unsafe { oasis_destroy(handle) };
    }

    #[test]
    fn send_input_text() {
        let handle = create_instance();
        let evt = OasisInputEvent {
            event_type: OASIS_EVENT_TEXT_INPUT,
            x: 0,
            y: 0,
            key: 0,
            character: 'A' as u32,
        };
        unsafe { oasis_send_input(handle, &evt) };
        unsafe { oasis_tick(handle, 0.016) };
        unsafe { oasis_destroy(handle) };
    }

    #[test]
    fn set_vfs_root_resets() {
        let handle = create_instance();
        // Write a file via command.
        let cmd = CString::new("mkdir /tmp").unwrap();
        let result = unsafe { oasis_send_command(handle, cmd.as_ptr()) };
        unsafe { oasis_free_string(result) };

        // Reset VFS.
        unsafe { oasis_set_vfs_root(handle, std::ptr::null()) };

        // CWD should be reset.
        let instance = unsafe { &*handle };
        assert_eq!(instance.cwd, "/");

        unsafe { oasis_destroy(handle) };
    }

    #[test]
    fn add_vfs_file_and_read() {
        let handle = create_instance();
        let path = CString::new("/home/readme.txt").unwrap();
        let data = b"Welcome to the game!";
        unsafe { oasis_add_vfs_file(handle, path.as_ptr(), data.as_ptr(), data.len() as u32) };

        // Read the file via command.
        let cmd = CString::new("cat /home/readme.txt").unwrap();
        let result = unsafe { oasis_send_command(handle, cmd.as_ptr()) };
        assert!(!result.is_null());
        let output = unsafe { CStr::from_ptr(result) }.to_string_lossy();
        assert!(output.contains("Welcome to the game!"));
        unsafe { oasis_free_string(result) };
        unsafe { oasis_destroy(handle) };
    }

    #[test]
    fn register_callback_fires() {
        use std::sync::atomic::{AtomicU32, Ordering};
        static CALL_COUNT: AtomicU32 = AtomicU32::new(0);

        extern "C" fn test_cb(_event: u32, _detail: *const c_char) {
            CALL_COUNT.fetch_add(1, Ordering::SeqCst);
        }

        let handle = create_instance();
        unsafe { oasis_register_callback(handle, OASIS_CB_COMMAND_EXEC, test_cb) };

        CALL_COUNT.store(0, Ordering::SeqCst);

        let cmd = CString::new("help").unwrap();
        let result = unsafe { oasis_send_command(handle, cmd.as_ptr()) };
        unsafe { oasis_free_string(result) };

        assert!(CALL_COUNT.load(Ordering::SeqCst) > 0);
        unsafe { oasis_destroy(handle) };
    }

    #[test]
    fn free_string_null_is_safe() {
        unsafe { oasis_free_string(std::ptr::null_mut()) };
    }

    #[test]
    fn null_handle_operations_are_safe() {
        let null = std::ptr::null_mut();
        unsafe {
            oasis_tick(null, 0.016);
            oasis_send_input(null, std::ptr::null());
            let _ = oasis_get_buffer(null, std::ptr::null_mut(), std::ptr::null_mut());
            let _ = oasis_get_dirty(null);
            let _ = oasis_send_command(null, std::ptr::null());
            oasis_set_vfs_root(null, std::ptr::null());
            oasis_register_callback(null, 0, {
                extern "C" fn dummy(_: u32, _: *const c_char) {}
                dummy
            });
            oasis_add_vfs_file(null, std::ptr::null(), std::ptr::null(), 0);
        }
    }
}
