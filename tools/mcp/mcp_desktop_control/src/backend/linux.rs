//! Linux X11 backend using the pure-Rust `x11rb` protocol implementation.
//!
//! * Windows: `_NET_CLIENT_LIST` (EWMH window managers), falling back to the
//!   root's mapped, titled children when no window manager is running (e.g.
//!   a bare Xvfb). Window management uses EWMH client messages when the WM
//!   advertises support, and plain ICCCM requests otherwise.
//! * Screens: RandR 1.3 (`GetScreenResourcesCurrent`, which unlike
//!   `GetScreenResources` does not trigger a slow hardware re-probe).
//! * Capture: `GetImage` on the root window.
//! * Input: XTEST fake input. Keys are resolved through the server's live
//!   keyboard mapping, so any layout works; characters missing from the layout
//!   are typed by temporarily binding them to a spare keycode (the technique
//!   `xdotool` uses), and the binding is removed afterwards.

use std::thread::sleep;
use std::time::Duration;

use image::RgbaImage;
use x11rb::connection::{Connection, RequestConnection};
use x11rb::errors::{ConnectionError, ReplyError};
use x11rb::protocol::ErrorKind;
use x11rb::protocol::randr::{self, ConnectionExt as _};
use x11rb::protocol::xproto::{
    Atom, AtomEnum, BUTTON_PRESS_EVENT, BUTTON_RELEASE_EVENT, ClientMessageEvent,
    ConfigureWindowAux, ConnectionExt as _, EventMask, ImageFormat, ImageOrder, InputFocus,
    KEY_PRESS_EVENT, KEY_RELEASE_EVENT, MOTION_NOTIFY_EVENT, MapState, StackMode, Window,
    WindowClass,
};
use x11rb::protocol::xtest::{self, ConnectionExt as _};
use x11rb::rust_connection::RustConnection;
use x11rb::{CURRENT_TIME, NONE};

use super::{DesktopBackend, DesktopError, DesktopResult};
use crate::imaging::{PixelLayout, framebuffer_to_rgba};
use crate::keys::{
    Key, KeyStroke, Keymap, NamedKey, char_to_keysym, key_to_keysym, named_to_keysym,
};
use crate::types::{MouseButton, Rect, ScreenInfo, ScrollDirection, TypeReport, WindowInfo};

x11rb::atom_manager! {
    /// Atoms used by the backend, interned once at connect time.
    Atoms: AtomsCookie {
        _NET_SUPPORTED,
        _NET_SUPPORTING_WM_CHECK,
        _NET_WM_NAME,
        _NET_CLIENT_LIST,
        _NET_ACTIVE_WINDOW,
        _NET_WM_STATE,
        _NET_WM_STATE_HIDDEN,
        _NET_WM_STATE_MAXIMIZED_HORZ,
        _NET_WM_STATE_MAXIMIZED_VERT,
        _NET_CLOSE_WINDOW,
        _NET_MOVERESIZE_WINDOW,
        _NET_WM_PID,
        WM_CHANGE_STATE,
        WM_PROTOCOLS,
        WM_DELETE_WINDOW,
        WM_STATE,
        UTF8_STRING,
    }
}

/// `_NET_WM_STATE` actions.
const NET_WM_STATE_REMOVE: u32 = 0;
const NET_WM_STATE_ADD: u32 = 1;
/// EWMH source indication "pager / direct user action": exempt from
/// focus-stealing prevention.
const SOURCE_PAGER: u32 = 2;
/// ICCCM IconicState.
const ICONIC_STATE: u32 = 3;
/// Keysym of Shift_L.
const SHIFT_KEYSYM: u32 = 0xffe1;
/// Pause after rebinding the scratch keycode so clients process MappingNotify.
const REMAP_SETTLE: Duration = Duration::from_millis(25);

/// Map a request-send error. Only I/O failures mean the connection is dead.
fn conn_err(e: ConnectionError) -> DesktopError {
    match e {
        ConnectionError::IoError(_) | ConnectionError::UnknownError => {
            DesktopError::Disconnected(e.to_string())
        },
        other => DesktopError::OperationFailed(format!("X11 request failed: {other}")),
    }
}

/// Map a reply error.
fn reply_err(e: ReplyError) -> DesktopError {
    match e {
        ReplyError::ConnectionError(c) => conn_err(c),
        ReplyError::X11Error(x) => {
            DesktopError::OperationFailed(format!("X11 error {:?}", x.error_kind))
        },
    }
}

/// Map a reply error for a request about a specific window.
fn window_err(id: Window, e: ReplyError) -> DesktopError {
    match e {
        ReplyError::X11Error(ref x)
            if matches!(x.error_kind, ErrorKind::Window | ErrorKind::Drawable) =>
        {
            DesktopError::WindowNotFound(id.to_string())
        },
        other => reply_err(other),
    }
}

fn clamp_i16(v: i32) -> i16 {
    // Clamped into range first, so the conversion cannot fail.
    i16::try_from(v.clamp(i32::from(i16::MIN), i32::from(i16::MAX))).unwrap_or(0)
}

/// X11 backend holding one connection for the server's lifetime.
pub struct X11Backend {
    conn: RustConnection,
    root: Window,
    atoms: Atoms,
    layout: PixelLayout,
    min_keycode: u8,
    max_keycode: u8,
    has_xtest: bool,
    has_randr: bool,
    display: String,
}

impl X11Backend {
    /// Connect to `$DISPLAY`.
    pub fn connect() -> DesktopResult<Self> {
        let display = std::env::var("DISPLAY").unwrap_or_default();
        let (conn, screen_num) = RustConnection::connect(None).map_err(|e| {
            DesktopError::NotAvailable(format!(
                "cannot connect to X display '{display}': {e} (is DISPLAY set and the X \
                 socket/Xauthority accessible?)"
            ))
        })?;
        let setup = conn.setup();
        let root = setup
            .roots
            .get(screen_num)
            .map(|s| s.root)
            .ok_or_else(|| DesktopError::NotAvailable(format!("no X screen {screen_num}")))?;
        let layout = if setup.image_byte_order == ImageOrder::LSB_FIRST {
            PixelLayout::Bgrx
        } else {
            PixelLayout::Xrgb
        };
        let (min_keycode, max_keycode) = (setup.min_keycode, setup.max_keycode);
        let atoms = Atoms::new(&conn)
            .map_err(conn_err)?
            .reply()
            .map_err(reply_err)?;
        let has_ext = |name: &'static str| {
            conn.extension_information(name)
                .map(|i| i.is_some())
                .unwrap_or(false)
        };
        let has_xtest = has_ext(xtest::X11_EXTENSION_NAME);
        let has_randr = has_ext(randr::X11_EXTENSION_NAME)
            && conn
                .randr_query_version(1, 3)
                .ok()
                .and_then(|c| c.reply().ok())
                .is_some_and(|v| (v.major_version, v.minor_version) >= (1, 3));
        Ok(Self {
            conn,
            root,
            atoms,
            layout,
            min_keycode,
            max_keycode,
            has_xtest,
            has_randr,
            display,
        })
    }

    // -- Helpers ----------------------------------------------------------

    /// Flush queued requests and discard queued events/errors (errors from
    /// unchecked requests would otherwise accumulate forever, since this
    /// client never processes events).
    fn flush(&self) -> DesktopResult<()> {
        self.conn.flush().map_err(conn_err)?;
        while let Ok(Some(_)) = self.conn.poll_for_event() {}
        Ok(())
    }

    /// Round-trip so that all previous requests have been processed.
    fn sync(&self) -> DesktopResult<()> {
        self.conn
            .get_input_focus()
            .map_err(conn_err)?
            .reply()
            .map_err(reply_err)?;
        self.flush()
    }

    fn require_xtest(&self) -> DesktopResult<()> {
        if self.has_xtest {
            Ok(())
        } else {
            Err(DesktopError::Unsupported(
                "the X server lacks the XTEST extension, so input cannot be simulated".into(),
            ))
        }
    }

    fn fake(&self, event: u8, detail: u8, x: i16, y: i16) -> DesktopResult<()> {
        self.conn
            .xtest_fake_input(event, detail, CURRENT_TIME, self.root, x, y, 0)
            .map_err(conn_err)?;
        Ok(())
    }

    /// 32-bit property values.
    fn prop32(&self, window: Window, prop: Atom, ty: impl Into<Atom>) -> Option<Vec<u32>> {
        let reply = self
            .conn
            .get_property(false, window, prop, ty, 0, 4096)
            .ok()?
            .reply()
            .ok()?;
        reply.value32().map(Iterator::collect)
    }

    fn supported(&self) -> Vec<Atom> {
        self.prop32(self.root, self.atoms._NET_SUPPORTED, AtomEnum::ATOM)
            .unwrap_or_default()
    }

    /// The EWMH window manager's check window, if a compliant WM is running.
    fn wm_check_window(&self) -> Option<Window> {
        let w = *self
            .prop32(
                self.root,
                self.atoms._NET_SUPPORTING_WM_CHECK,
                AtomEnum::WINDOW,
            )?
            .first()?;
        (w != NONE && self.conn.get_geometry(w).ok()?.reply().is_ok()).then_some(w)
    }

    fn wm_name(&self) -> Option<String> {
        self.wm_check_window().map(|w| self.window_title(w))
    }

    fn parse_id(id: &str) -> DesktopResult<Window> {
        id.parse::<Window>()
            .ok()
            .filter(|w| *w != NONE)
            .ok_or_else(|| DesktopError::WindowNotFound(id.to_string()))
    }

    /// Parse an id and check the window exists.
    fn window(&self, id: &str) -> DesktopResult<Window> {
        let w = Self::parse_id(id)?;
        self.conn
            .get_geometry(w)
            .map_err(conn_err)?
            .reply()
            .map_err(|e| window_err(w, e))?;
        Ok(w)
    }

    /// Send an EWMH/ICCCM client message to the root window.
    fn send_root_message(&self, window: Window, ty: Atom, data: [u32; 5]) -> DesktopResult<()> {
        let event = ClientMessageEvent::new(32, window, ty, data);
        self.conn
            .send_event(
                false,
                self.root,
                EventMask::SUBSTRUCTURE_REDIRECT | EventMask::SUBSTRUCTURE_NOTIFY,
                event,
            )
            .map_err(conn_err)?
            .check()
            .map_err(reply_err)?;
        self.flush()
    }

    fn window_title(&self, w: Window) -> String {
        let get = |prop: Atom, ty: Atom| {
            self.conn
                .get_property(false, w, prop, ty, 0, 1024)
                .ok()?
                .reply()
                .ok()
                .filter(|r| !r.value.is_empty())
        };
        if let Some(r) = get(self.atoms._NET_WM_NAME, self.atoms.UTF8_STRING) {
            return String::from_utf8_lossy(&r.value).into_owned();
        }
        match get(AtomEnum::WM_NAME.into(), AtomEnum::ANY.into()) {
            // STRING is Latin-1: every byte is its own code point.
            Some(r) if r.type_ == Atom::from(AtomEnum::STRING) => {
                r.value.iter().map(|&b| char::from(b)).collect()
            },
            Some(r) => String::from_utf8_lossy(&r.value).into_owned(),
            None => String::new(),
        }
    }

    fn window_info(&self, w: Window) -> DesktopResult<WindowInfo> {
        let geom = self
            .conn
            .get_geometry(w)
            .map_err(conn_err)?
            .reply()
            .map_err(|e| window_err(w, e))?;
        let attrs = self
            .conn
            .get_window_attributes(w)
            .map_err(conn_err)?
            .reply()
            .map_err(|e| window_err(w, e))?;
        // Geometry is relative to the parent (the WM frame); translate to root.
        let pos = self
            .conn
            .translate_coordinates(w, self.root, 0, 0)
            .map_err(conn_err)?
            .reply()
            .map_err(|e| window_err(w, e))?;
        let states = self
            .prop32(w, self.atoms._NET_WM_STATE, AtomEnum::ATOM)
            .unwrap_or_default();
        let iconic = self
            .prop32(w, self.atoms.WM_STATE, self.atoms.WM_STATE)
            .and_then(|v| v.first().copied())
            == Some(ICONIC_STATE);
        let minimized = iconic || states.contains(&self.atoms._NET_WM_STATE_HIDDEN);
        let maximized = states.contains(&self.atoms._NET_WM_STATE_MAXIMIZED_HORZ)
            && states.contains(&self.atoms._NET_WM_STATE_MAXIMIZED_VERT);
        let pid = self
            .prop32(w, self.atoms._NET_WM_PID, AtomEnum::CARDINAL)
            .and_then(|v| v.first().copied())
            .filter(|p| *p != 0);
        // Only meaningful when the server shares our PID namespace.
        let process_name = pid.and_then(|p| {
            std::fs::read_to_string(format!("/proc/{p}/comm"))
                .ok()
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
        });
        Ok(WindowInfo {
            id: w.to_string(),
            title: self.window_title(w),
            process_name,
            pid,
            // Report the outer rectangle (including the X border), matching
            // what ConfigureWindow positions and what xwininfo reports.
            x: i32::from(pos.dst_x) - i32::from(geom.border_width),
            y: i32::from(pos.dst_y) - i32::from(geom.border_width),
            width: u32::from(geom.width) + 2 * u32::from(geom.border_width),
            height: u32::from(geom.height) + 2 * u32::from(geom.border_width),
            visible: attrs.map_state == MapState::VIEWABLE && !minimized,
            minimized,
            maximized,
        })
    }

    /// Top-level windows when no EWMH window manager maintains a client list.
    fn fallback_toplevels(&self) -> DesktopResult<Vec<Window>> {
        let tree = self
            .conn
            .query_tree(self.root)
            .map_err(conn_err)?
            .reply()
            .map_err(reply_err)?;
        Ok(tree
            .children
            .into_iter()
            .filter(|&w| {
                self.conn
                    .get_window_attributes(w)
                    .ok()
                    .and_then(|c| c.reply().ok())
                    .is_some_and(|a| !a.override_redirect && a.class == WindowClass::INPUT_OUTPUT)
                    && !self.window_title(w).is_empty()
            })
            .collect())
    }

    fn keymap(&self) -> DesktopResult<Keymap> {
        let count = self
            .max_keycode
            .saturating_sub(self.min_keycode)
            .saturating_add(1);
        let reply = self
            .conn
            .get_keyboard_mapping(self.min_keycode, count)
            .map_err(conn_err)?
            .reply()
            .map_err(reply_err)?;
        Ok(Keymap::from_mapping(
            self.min_keycode,
            reply.keysyms_per_keycode,
            &reply.keysyms,
        ))
    }

    /// Bind `keysym` to `keycode` on both shift levels (0 = unbind).
    fn bind_keycode(&self, km: &Keymap, keycode: u8, keysym: u32) -> DesktopResult<()> {
        let per = km.keysyms_per_keycode.max(1);
        let mut syms = vec![0u32; usize::from(per)];
        syms[0] = keysym;
        if let Some(s) = syms.get_mut(1) {
            *s = keysym;
        }
        self.conn
            .change_keyboard_mapping(1, keycode, per, &syms)
            .map_err(conn_err)?
            .check()
            .map_err(reply_err)?;
        self.sync()
    }

    fn tap(&self, stroke: KeyStroke, shift: Option<u8>) -> DesktopResult<()> {
        let shift = if stroke.shift { shift } else { None };
        if let Some(s) = shift {
            self.fake(KEY_PRESS_EVENT, s, 0, 0)?;
        }
        self.fake(KEY_PRESS_EVENT, stroke.keycode, 0, 0)?;
        self.fake(KEY_RELEASE_EVENT, stroke.keycode, 0, 0)?;
        if let Some(s) = shift {
            self.fake(KEY_RELEASE_EVENT, s, 0, 0)?;
        }
        self.flush()
    }

    fn randr_screens(&self) -> Option<Vec<ScreenInfo>> {
        if !self.has_randr {
            return None;
        }
        let res = self
            .conn
            .randr_get_screen_resources_current(self.root)
            .ok()?
            .reply()
            .ok()?;
        let primary = self
            .conn
            .randr_get_output_primary(self.root)
            .ok()
            .and_then(|c| c.reply().ok())
            .map(|r| r.output)
            .unwrap_or(NONE);
        let mut screens: Vec<ScreenInfo> = Vec::new();
        for crtc in res.crtcs {
            let Some(info) = self
                .conn
                .randr_get_crtc_info(crtc, res.config_timestamp)
                .ok()
                .and_then(|c| c.reply().ok())
            else {
                continue;
            };
            if info.mode == NONE || info.width == 0 || info.height == 0 {
                continue;
            }
            let (x, y) = (i32::from(info.x), i32::from(info.y));
            let (width, height) = (u32::from(info.width), u32::from(info.height));
            // Mirrored outputs share a CRTC area; list the area once.
            if screens
                .iter()
                .any(|s| (s.x, s.y, s.width, s.height) == (x, y, width, height))
            {
                continue;
            }
            let id = u32::try_from(screens.len()).unwrap_or(u32::MAX);
            let name = info
                .outputs
                .first()
                .and_then(|o| {
                    self.conn
                        .randr_get_output_info(*o, res.config_timestamp)
                        .ok()?
                        .reply()
                        .ok()
                })
                .map(|o| String::from_utf8_lossy(&o.name).into_owned())
                .unwrap_or_else(|| format!("screen-{id}"));
            screens.push(ScreenInfo {
                id,
                name,
                x,
                y,
                width,
                height,
                is_primary: primary != NONE && info.outputs.contains(&primary),
                scale: 1.0,
            });
        }
        if !screens.is_empty() && !screens.iter().any(|s| s.is_primary) {
            screens[0].is_primary = true;
        }
        (!screens.is_empty()).then_some(screens)
    }
}

impl DesktopBackend for X11Backend {
    fn platform_name(&self) -> &'static str {
        "x11"
    }

    fn diagnostics(&self) -> serde_json::Value {
        serde_json::json!({
            "display": self.display,
            "window_manager": self.wm_name(),
            "xtest": self.has_xtest,
            "randr_1_3": self.has_randr,
            "pixel_layout": format!("{:?}", self.layout),
        })
    }

    fn list_windows(&self) -> DesktopResult<Vec<WindowInfo>> {
        let ids = match self
            .prop32(self.root, self.atoms._NET_CLIENT_LIST, AtomEnum::WINDOW)
            .filter(|l| !l.is_empty())
        {
            Some(list) => list,
            None => self.fallback_toplevels()?,
        };
        // Windows can disappear between listing and querying; skip those.
        let windows = ids
            .into_iter()
            .filter_map(|w| match self.window_info(w) {
                Ok(info) => Some(Ok(info)),
                Err(DesktopError::Disconnected(m)) => Some(Err(DesktopError::Disconnected(m))),
                Err(_) => None,
            })
            .collect::<DesktopResult<Vec<_>>>()?;
        self.flush()?;
        Ok(windows)
    }

    fn get_active_window(&self) -> DesktopResult<Option<WindowInfo>> {
        let mut active = self
            .prop32(self.root, self.atoms._NET_ACTIVE_WINDOW, AtomEnum::WINDOW)
            .and_then(|v| v.first().copied())
            .filter(|w| *w != NONE);
        if active.is_none() && self.wm_check_window().is_none() {
            // No EWMH WM: use the input focus, climbing to the top-level window.
            let focus = self
                .conn
                .get_input_focus()
                .map_err(conn_err)?
                .reply()
                .map_err(reply_err)?
                .focus;
            let mut w = focus;
            // Focus value 1 is PointerRoot.
            while w != NONE && w != self.root && w != 1 {
                let Some(tree) = self.conn.query_tree(w).ok().and_then(|c| c.reply().ok()) else {
                    break;
                };
                if tree.parent == self.root {
                    active = Some(w);
                    break;
                }
                w = tree.parent;
            }
        }
        match active {
            Some(w) => Ok(self.window_info(w).ok()),
            None => Ok(None),
        }
    }

    fn focus_window(&self, id: &str) -> DesktopResult<()> {
        let w = self.window(id)?;
        if self.wm_check_window().is_some() {
            // Activation also de-iconifies the window.
            self.send_root_message(
                w,
                self.atoms._NET_ACTIVE_WINDOW,
                [SOURCE_PAGER, CURRENT_TIME, NONE, 0, 0],
            )
        } else {
            self.conn.map_window(w).map_err(conn_err)?;
            self.conn
                .configure_window(w, &ConfigureWindowAux::new().stack_mode(StackMode::ABOVE))
                .map_err(conn_err)?;
            self.conn
                .set_input_focus(InputFocus::PARENT, w, CURRENT_TIME)
                .map_err(conn_err)?
                .check()
                .map_err(|e| window_err(w, e))?;
            self.flush()
        }
    }

    fn move_window(&self, id: &str, x: i32, y: i32) -> DesktopResult<()> {
        let w = self.window(id)?;
        if self
            .supported()
            .contains(&self.atoms._NET_MOVERESIZE_WINDOW)
        {
            // Flags: x and y present, window gravity, source = pager.
            let flags = (1 << 8) | (1 << 9) | (SOURCE_PAGER << 12);
            // Coordinates are signed values carried in CARD32 fields.
            self.send_root_message(
                w,
                self.atoms._NET_MOVERESIZE_WINDOW,
                [flags, x as u32, y as u32, 0, 0],
            )
        } else {
            self.conn
                .configure_window(w, &ConfigureWindowAux::new().x(x).y(y))
                .map_err(conn_err)?
                .check()
                .map_err(|e| window_err(w, e))?;
            self.flush()
        }
    }

    fn resize_window(&self, id: &str, width: u32, height: u32) -> DesktopResult<()> {
        let w = self.window(id)?;
        if self
            .supported()
            .contains(&self.atoms._NET_MOVERESIZE_WINDOW)
        {
            // Flags: width and height present, window gravity, source = pager.
            let flags = (1 << 10) | (1 << 11) | (SOURCE_PAGER << 12);
            self.send_root_message(
                w,
                self.atoms._NET_MOVERESIZE_WINDOW,
                [flags, 0, 0, width, height],
            )
        } else {
            self.conn
                .configure_window(w, &ConfigureWindowAux::new().width(width).height(height))
                .map_err(conn_err)?
                .check()
                .map_err(|e| window_err(w, e))?;
            self.flush()
        }
    }

    fn minimize_window(&self, id: &str) -> DesktopResult<()> {
        let w = self.window(id)?;
        if self.wm_check_window().is_some() {
            // ICCCM 4.1.4: ask the WM to iconify.
            self.send_root_message(w, self.atoms.WM_CHANGE_STATE, [ICONIC_STATE, 0, 0, 0, 0])
        } else {
            // Without a WM there is no iconic state; hiding is the closest.
            self.conn
                .unmap_window(w)
                .map_err(conn_err)?
                .check()
                .map_err(|e| window_err(w, e))?;
            self.flush()
        }
    }

    fn maximize_window(&self, id: &str) -> DesktopResult<()> {
        let w = self.window(id)?;
        let supported = self.supported();
        if !supported.contains(&self.atoms._NET_WM_STATE_MAXIMIZED_HORZ) {
            return Err(DesktopError::Unsupported(
                "maximizing requires an EWMH window manager (none detected); use \
                 move_window + resize_window instead"
                    .into(),
            ));
        }
        self.send_root_message(
            w,
            self.atoms._NET_WM_STATE,
            [
                NET_WM_STATE_ADD,
                self.atoms._NET_WM_STATE_MAXIMIZED_HORZ,
                self.atoms._NET_WM_STATE_MAXIMIZED_VERT,
                SOURCE_PAGER,
                0,
            ],
        )
    }

    fn restore_window(&self, id: &str) -> DesktopResult<()> {
        let w = self.window(id)?;
        // ICCCM: mapping an iconic window returns it to NormalState (the WM
        // receives this as a MapRequest).
        self.conn
            .map_window(w)
            .map_err(conn_err)?
            .check()
            .map_err(|e| window_err(w, e))?;
        if self
            .supported()
            .contains(&self.atoms._NET_WM_STATE_MAXIMIZED_HORZ)
        {
            self.send_root_message(
                w,
                self.atoms._NET_WM_STATE,
                [
                    NET_WM_STATE_REMOVE,
                    self.atoms._NET_WM_STATE_MAXIMIZED_HORZ,
                    self.atoms._NET_WM_STATE_MAXIMIZED_VERT,
                    SOURCE_PAGER,
                    0,
                ],
            )?;
        }
        if self.wm_check_window().is_some() {
            self.send_root_message(
                w,
                self.atoms._NET_ACTIVE_WINDOW,
                [SOURCE_PAGER, CURRENT_TIME, NONE, 0, 0],
            )?;
        }
        self.flush()
    }

    fn close_window(&self, id: &str) -> DesktopResult<()> {
        let w = self.window(id)?;
        if self.supported().contains(&self.atoms._NET_CLOSE_WINDOW) {
            return self.send_root_message(
                w,
                self.atoms._NET_CLOSE_WINDOW,
                [CURRENT_TIME, SOURCE_PAGER, 0, 0, 0],
            );
        }
        // No EWMH support: ask the client directly via WM_DELETE_WINDOW.
        let protocols = self
            .prop32(w, self.atoms.WM_PROTOCOLS, AtomEnum::ATOM)
            .unwrap_or_default();
        if !protocols.contains(&self.atoms.WM_DELETE_WINDOW) {
            return Err(DesktopError::Unsupported(format!(
                "window {id} does not support WM_DELETE_WINDOW and no EWMH window manager is \
                 running; refusing to kill the client"
            )));
        }
        let event = ClientMessageEvent::new(
            32,
            w,
            self.atoms.WM_PROTOCOLS,
            [self.atoms.WM_DELETE_WINDOW, CURRENT_TIME, 0, 0, 0],
        );
        self.conn
            .send_event(false, w, EventMask::NO_EVENT, event)
            .map_err(conn_err)?
            .check()
            .map_err(|e| window_err(w, e))?;
        self.flush()
    }

    fn list_screens(&self) -> DesktopResult<Vec<ScreenInfo>> {
        if let Some(screens) = self.randr_screens() {
            return Ok(screens);
        }
        let desk = self.virtual_screen()?;
        Ok(vec![ScreenInfo {
            id: 0,
            name: "default".to_string(),
            x: desk.x,
            y: desk.y,
            width: desk.width,
            height: desk.height,
            is_primary: true,
            scale: 1.0,
        }])
    }

    fn virtual_screen(&self) -> DesktopResult<Rect> {
        // Queried live: the root size changes when monitors are reconfigured.
        let g = self
            .conn
            .get_geometry(self.root)
            .map_err(conn_err)?
            .reply()
            .map_err(reply_err)?;
        Ok(Rect::new(0, 0, u32::from(g.width), u32::from(g.height)))
    }

    fn capture_region(&self, rect: Rect) -> DesktopResult<RgbaImage> {
        let bad = |what: &str| {
            DesktopError::ScreenshotFailed(format!("capture {what} out of X11 range: {rect:?}"))
        };
        let x = i16::try_from(rect.x).map_err(|_| bad("x"))?;
        let y = i16::try_from(rect.y).map_err(|_| bad("y"))?;
        let w = u16::try_from(rect.width).map_err(|_| bad("width"))?;
        let h = u16::try_from(rect.height).map_err(|_| bad("height"))?;
        let image = self
            .conn
            .get_image(ImageFormat::Z_PIXMAP, self.root, x, y, w, h, !0)
            .map_err(conn_err)?
            .reply()
            .map_err(|e| DesktopError::ScreenshotFailed(format!("GetImage failed: {e:?}")))?;
        let format = self
            .conn
            .setup()
            .pixmap_formats
            .iter()
            .find(|f| f.depth == image.depth)
            .ok_or_else(|| {
                DesktopError::ScreenshotFailed(format!(
                    "no pixmap format for depth {}",
                    image.depth
                ))
            })?;
        if format.bits_per_pixel != 32 {
            return Err(DesktopError::ScreenshotFailed(format!(
                "unsupported pixel format: depth {} at {} bits per pixel (only 32bpp \
                 TrueColor displays are supported)",
                image.depth, format.bits_per_pixel
            )));
        }
        let pad = usize::from(format.scanline_pad.max(8));
        let row_bits = usize::from(w) * 32;
        let stride = row_bits.div_ceil(pad) * pad / 8;
        framebuffer_to_rgba(&image.data, u32::from(w), u32::from(h), stride, self.layout)
            .map_err(DesktopError::ScreenshotFailed)
    }

    fn capture_window(&self, id: &str) -> DesktopResult<(RgbaImage, Rect)> {
        let w = Self::parse_id(id)?;
        let info = self.window_info(w)?;
        if !info.visible {
            return Err(DesktopError::ScreenshotFailed(format!(
                "window {id} is not viewable (minimized or unmapped); restore it first"
            )));
        }
        let rect = Rect::new(info.x, info.y, info.width, info.height)
            .intersect(&self.virtual_screen()?)
            .ok_or_else(|| {
                DesktopError::ScreenshotFailed(format!("window {id} is entirely off-screen"))
            })?;
        Ok((self.capture_region(rect)?, rect))
    }

    fn mouse_position(&self) -> DesktopResult<(i32, i32)> {
        let reply = self
            .conn
            .query_pointer(self.root)
            .map_err(conn_err)?
            .reply()
            .map_err(reply_err)?;
        Ok((i32::from(reply.root_x), i32::from(reply.root_y)))
    }

    fn move_mouse(&self, x: i32, y: i32) -> DesktopResult<()> {
        self.require_xtest()?;
        // XTEST motion (unlike WarpPointer) produces real device events, which
        // applications using XInput2 raw events also see.
        self.fake(MOTION_NOTIFY_EVENT, 0, clamp_i16(x), clamp_i16(y))?;
        self.flush()
    }

    fn mouse_button(&self, button: MouseButton, down: bool) -> DesktopResult<()> {
        self.require_xtest()?;
        let detail = match button {
            MouseButton::Left => 1,
            MouseButton::Middle => 2,
            MouseButton::Right => 3,
        };
        let event = if down {
            BUTTON_PRESS_EVENT
        } else {
            BUTTON_RELEASE_EVENT
        };
        self.fake(event, detail, 0, 0)?;
        self.flush()
    }

    fn scroll(&self, direction: ScrollDirection, amount: i32) -> DesktopResult<()> {
        self.require_xtest()?;
        // Buttons 4/5 = up/down, 6/7 = left/right.
        let button = match (direction, amount > 0) {
            (ScrollDirection::Vertical, false) => 4,
            (ScrollDirection::Vertical, true) => 5,
            (ScrollDirection::Horizontal, false) => 6,
            (ScrollDirection::Horizontal, true) => 7,
        };
        for _ in 0..amount.unsigned_abs() {
            self.fake(BUTTON_PRESS_EVENT, button, 0, 0)?;
            self.fake(BUTTON_RELEASE_EVENT, button, 0, 0)?;
        }
        self.flush()
    }

    fn key(&self, key: Key, down: bool) -> DesktopResult<()> {
        self.require_xtest()?;
        let km = self.keymap()?;
        let stroke = km.lookup(key_to_keysym(key)).ok_or_else(|| {
            DesktopError::InvalidInput(match key {
                Key::Char(c) => format!(
                    "'{c}' is not on the current keyboard layout; use type_text to enter it"
                ),
                Key::Named(n) => format!("{n:?} is not mapped on the current keyboard layout"),
            })
        })?;
        // Named keys are pressed as-is; characters on a shifted level get
        // Shift wrapped around them.
        let shift = match key {
            Key::Char(_) if stroke.shift => km.lookup(SHIFT_KEYSYM).map(|s| s.keycode),
            _ => None,
        };
        if down {
            if let Some(s) = shift {
                self.fake(KEY_PRESS_EVENT, s, 0, 0)?;
            }
            self.fake(KEY_PRESS_EVENT, stroke.keycode, 0, 0)?;
        } else {
            self.fake(KEY_RELEASE_EVENT, stroke.keycode, 0, 0)?;
            if let Some(s) = shift {
                self.fake(KEY_RELEASE_EVENT, s, 0, 0)?;
            }
        }
        self.flush()
    }

    fn type_text(&self, text: &str, interval_ms: u64) -> DesktopResult<TypeReport> {
        self.require_xtest()?;
        let km = self.keymap()?;
        let shift = km.lookup(SHIFT_KEYSYM).map(|s| s.keycode);
        let scratch = km.spare_keycode();
        let mut bound: Option<u32> = None;
        let mut report = TypeReport::default();
        let delay = Duration::from_millis(interval_ms);

        let mut result = Ok(());
        let mut chars = text.chars().peekable();
        while let Some(c) = chars.next() {
            if c == '\r' && chars.peek() == Some(&'\n') {
                continue;
            }
            if c.is_control() && !matches!(c, '\n' | '\r' | '\t') {
                report.skipped.push(c);
                continue;
            }
            let keysym = match c {
                '\n' | '\r' => named_to_keysym(NamedKey::Enter),
                c => char_to_keysym(c),
            };
            let step = if let Some(stroke) = km.lookup(keysym) {
                self.tap(stroke, shift)
            } else if let Some(kc) = scratch {
                let bind = if bound == Some(keysym) {
                    Ok(())
                } else {
                    bound = Some(keysym);
                    self.bind_keycode(&km, kc, keysym)
                        .map(|()| sleep(REMAP_SETTLE))
                };
                bind.and_then(|()| {
                    self.tap(
                        KeyStroke {
                            keycode: kc,
                            shift: false,
                        },
                        None,
                    )
                })
                .map(|()| sleep(REMAP_SETTLE))
            } else {
                report.skipped.push(c);
                continue;
            };
            if let Err(e) = step {
                result = Err(e);
                break;
            }
            report.typed += 1;
            if interval_ms > 0 && chars.peek().is_some() {
                sleep(delay);
            }
        }

        // Always remove the temporary binding.
        if let (Some(kc), Some(_)) = (scratch, bound) {
            let restored = self.bind_keycode(&km, kc, 0);
            if result.is_ok() {
                result = restored;
            }
        }
        result.map(|()| report)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn clamp_i16_saturates() {
        assert_eq!(clamp_i16(5), 5);
        assert_eq!(clamp_i16(-40_000), i16::MIN);
        assert_eq!(clamp_i16(i32::MAX), i16::MAX);
    }

    #[test]
    fn parse_id_rejects_zero_and_garbage() {
        assert_eq!(X11Backend::parse_id("123").unwrap(), 123);
        assert!(X11Backend::parse_id("0").is_err());
        assert!(X11Backend::parse_id("abc").is_err());
        assert!(X11Backend::parse_id("99999999999").is_err());
    }

    #[test]
    fn io_errors_mean_disconnected() {
        let e = conn_err(ConnectionError::IoError(std::io::Error::other(
            "broken pipe",
        )));
        assert!(matches!(e, DesktopError::Disconnected(_)));
        let e = conn_err(ConnectionError::UnsupportedExtension);
        assert!(matches!(e, DesktopError::OperationFailed(_)));
    }

    /// Live smoke test against a real display; skipped unless
    /// `MCP_DESKTOP_X11_TEST=1` and `DISPLAY` are set. Read-only: it never
    /// moves the pointer or sends keys.
    #[test]
    fn live_read_only_smoke() {
        if std::env::var("MCP_DESKTOP_X11_TEST").as_deref() != Ok("1") {
            return;
        }
        let b = X11Backend::connect().expect("connect");
        let desk = b.virtual_screen().unwrap();
        assert!(desk.width > 0 && desk.height > 0);
        assert!(!b.list_screens().unwrap().is_empty());
        b.list_windows().unwrap();
        b.mouse_position().unwrap();
        let img = b
            .capture_region(Rect::new(0, 0, desk.width.min(64), desk.height.min(64)))
            .unwrap();
        assert!(img.width() > 0);
        assert!(b.keymap().unwrap().lookup(0x61).is_some());
    }
}
