//! Linux X11 desktop control backend using x11rb.

use std::sync::Arc;
use std::time::Duration;

use image::ImageEncoder;
use tracing::warn;
use x11rb::connection::Connection;
use x11rb::protocol::randr::ConnectionExt as RandrExt;
use x11rb::protocol::xproto::{Atom, AtomEnum, ConnectionExt, EventMask, InputFocus, Window};
use x11rb::protocol::xtest::ConnectionExt as XTestExt;
use x11rb::rust_connection::RustConnection;

use super::{DesktopBackend, DesktopError, DesktopResult};
use crate::types::{KeyModifier, MouseButton, ScreenInfo, ScrollDirection, WindowInfo};

/// Linux X11 backend
pub struct LinuxBackend {
    conn: Arc<RustConnection>,
    screen_num: usize,
    root: Window,
    atoms: X11Atoms,
}

/// Cached X11 atoms
struct X11Atoms {
    net_wm_name: Atom,
    net_client_list: Atom,
    net_active_window: Atom,
    net_wm_state: Atom,
    net_wm_state_hidden: Atom,
    net_wm_state_maximized_horz: Atom,
    net_wm_state_maximized_vert: Atom,
    net_close_window: Atom,
    #[allow(dead_code)]
    net_moveresize_window: Atom,
    wm_name: Atom,
    #[allow(dead_code)]
    wm_delete_window: Atom,
    utf8_string: Atom,
}

impl LinuxBackend {
    /// Create a new Linux backend
    pub fn new() -> DesktopResult<Self> {
        // Connect to X11 display
        let (conn, screen_num) =
            RustConnection::connect(None).map_err(|e| DesktopError::NotAvailable(e.to_string()))?;

        let setup = conn.setup();
        let screen = &setup.roots[screen_num];
        let root = screen.root;

        // Get atoms
        let atoms = Self::get_atoms(&conn)?;

        Ok(Self {
            conn: Arc::new(conn),
            screen_num,
            root,
            atoms,
        })
    }

    fn get_atoms(conn: &RustConnection) -> DesktopResult<X11Atoms> {
        let atom_names = [
            "_NET_WM_NAME",
            "_NET_CLIENT_LIST",
            "_NET_ACTIVE_WINDOW",
            "_NET_WM_STATE",
            "_NET_WM_STATE_HIDDEN",
            "_NET_WM_STATE_MAXIMIZED_HORZ",
            "_NET_WM_STATE_MAXIMIZED_VERT",
            "_NET_CLOSE_WINDOW",
            "_NET_MOVERESIZE_WINDOW",
            "WM_NAME",
            "WM_DELETE_WINDOW",
            "UTF8_STRING",
        ];

        let cookies: Vec<_> = atom_names
            .iter()
            .map(|name| conn.intern_atom(false, name.as_bytes()))
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        let atoms: Vec<Atom> = cookies
            .into_iter()
            .map(|cookie| {
                cookie
                    .reply()
                    .map(|r| r.atom)
                    .unwrap_or(Atom::from(AtomEnum::NONE))
            })
            .collect();

        Ok(X11Atoms {
            net_wm_name: atoms[0],
            net_client_list: atoms[1],
            net_active_window: atoms[2],
            net_wm_state: atoms[3],
            net_wm_state_hidden: atoms[4],
            net_wm_state_maximized_horz: atoms[5],
            net_wm_state_maximized_vert: atoms[6],
            net_close_window: atoms[7],
            net_moveresize_window: atoms[8],
            wm_name: atoms[9],
            wm_delete_window: atoms[10],
            utf8_string: atoms[11],
        })
    }

    fn get_window_title(&self, window: Window) -> Option<String> {
        // Try _NET_WM_NAME first (UTF-8)
        if let Some(reply) = self
            .conn
            .get_property(
                false,
                window,
                self.atoms.net_wm_name,
                self.atoms.utf8_string,
                0,
                1024,
            )
            .ok()
            .and_then(|c| c.reply().ok())
            .filter(|r| !r.value.is_empty())
        {
            return String::from_utf8(reply.value).ok();
        }

        // Fall back to WM_NAME
        if let Some(reply) = self
            .conn
            .get_property(false, window, self.atoms.wm_name, AtomEnum::STRING, 0, 1024)
            .ok()
            .and_then(|c| c.reply().ok())
            .filter(|r| !r.value.is_empty())
        {
            return String::from_utf8_lossy(&reply.value).into_owned().into();
        }

        None
    }

    fn get_window_geometry(&self, window: Window) -> Option<(i32, i32, u32, u32)> {
        self.conn
            .get_geometry(window)
            .ok()
            .and_then(|c| c.reply().ok())
            .map(|geom| {
                (
                    geom.x as i32,
                    geom.y as i32,
                    geom.width as u32,
                    geom.height as u32,
                )
            })
    }

    fn get_window_state(&self, window: Window) -> (bool, bool, bool) {
        // Returns (visible, minimized, maximized)
        let mut minimized = false;
        let mut maximized_h = false;
        let mut maximized_v = false;

        if let Some(reply) = self
            .conn
            .get_property(
                false,
                window,
                self.atoms.net_wm_state,
                AtomEnum::ATOM,
                0,
                1024,
            )
            .ok()
            .and_then(|c| c.reply().ok())
        {
            let atoms: Vec<Atom> = reply.value32().map(Iterator::collect).unwrap_or_default();

            for atom in atoms {
                if atom == self.atoms.net_wm_state_hidden {
                    minimized = true;
                } else if atom == self.atoms.net_wm_state_maximized_horz {
                    maximized_h = true;
                } else if atom == self.atoms.net_wm_state_maximized_vert {
                    maximized_v = true;
                }
            }
        }

        let maximized = maximized_h && maximized_v;
        let visible = !minimized;

        (visible, minimized, maximized)
    }

    fn window_to_info(&self, window: Window) -> Option<WindowInfo> {
        let title = self.get_window_title(window)?;
        let (x, y, width, height) = self.get_window_geometry(window)?;
        let (visible, minimized, maximized) = self.get_window_state(window);

        Some(WindowInfo {
            id: window.to_string(),
            title,
            process_name: None, // Would need additional work to get PID
            x,
            y,
            width,
            height,
            visible,
            minimized,
            maximized,
        })
    }

    fn get_client_list(&self) -> Vec<Window> {
        self.conn
            .get_property(
                false,
                self.root,
                self.atoms.net_client_list,
                AtomEnum::WINDOW,
                0,
                1024,
            )
            .ok()
            .and_then(|c| c.reply().ok())
            .map(|reply| {
                reply
                    .value32()
                    .map(Iterator::collect::<Vec<Window>>)
                    .unwrap_or_default()
            })
            .unwrap_or_default()
    }

    fn parse_window_id(&self, window_id: &str) -> DesktopResult<Window> {
        window_id
            .parse::<u32>()
            .map_err(|_| DesktopError::WindowNotFound(window_id.to_string()))
    }

    fn send_client_message(
        &self,
        window: Window,
        message_type: Atom,
        data: [u32; 5],
    ) -> DesktopResult<()> {
        use x11rb::protocol::xproto::ClientMessageData;
        use x11rb::protocol::xproto::ClientMessageEvent;

        let event = ClientMessageEvent {
            response_type: 33, // ClientMessage
            format: 32,
            sequence: 0,
            window,
            type_: message_type,
            data: ClientMessageData::from(data),
        };

        self.conn
            .send_event(
                false,
                self.root,
                EventMask::SUBSTRUCTURE_REDIRECT | EventMask::SUBSTRUCTURE_NOTIFY,
                event,
            )
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        self.conn
            .flush()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        Ok(())
    }

    fn key_to_keycode(&self, key: &str) -> Option<u8> {
        // Basic key name to keycode mapping
        // This is a simplified mapping; a full implementation would use xkbcommon
        match key.to_lowercase().as_str() {
            "a" => Some(38),
            "b" => Some(56),
            "c" => Some(54),
            "d" => Some(40),
            "e" => Some(26),
            "f" => Some(41),
            "g" => Some(42),
            "h" => Some(43),
            "i" => Some(31),
            "j" => Some(44),
            "k" => Some(45),
            "l" => Some(46),
            "m" => Some(58),
            "n" => Some(57),
            "o" => Some(32),
            "p" => Some(33),
            "q" => Some(24),
            "r" => Some(27),
            "s" => Some(39),
            "t" => Some(28),
            "u" => Some(30),
            "v" => Some(55),
            "w" => Some(25),
            "x" => Some(53),
            "y" => Some(29),
            "z" => Some(52),
            "0" => Some(19),
            "1" => Some(10),
            "2" => Some(11),
            "3" => Some(12),
            "4" => Some(13),
            "5" => Some(14),
            "6" => Some(15),
            "7" => Some(16),
            "8" => Some(17),
            "9" => Some(18),
            "space" | " " => Some(65),
            "enter" | "return" => Some(36),
            "tab" => Some(23),
            "escape" | "esc" => Some(9),
            "backspace" => Some(22),
            "delete" | "del" => Some(119),
            "home" => Some(110),
            "end" => Some(115),
            "pageup" | "page_up" => Some(112),
            "pagedown" | "page_down" => Some(117),
            "left" => Some(113),
            "right" => Some(114),
            "up" => Some(111),
            "down" => Some(116),
            "f1" => Some(67),
            "f2" => Some(68),
            "f3" => Some(69),
            "f4" => Some(70),
            "f5" => Some(71),
            "f6" => Some(72),
            "f7" => Some(73),
            "f8" => Some(74),
            "f9" => Some(75),
            "f10" => Some(76),
            "f11" => Some(95),
            "f12" => Some(96),
            "ctrl" | "control" => Some(37),
            "alt" => Some(64),
            "shift" => Some(50),
            "super" | "win" | "meta" => Some(133),
            _ => None,
        }
    }

    fn modifier_to_keycode(&self, modifier: &KeyModifier) -> u8 {
        match modifier {
            KeyModifier::Ctrl => 37,
            KeyModifier::Alt => 64,
            KeyModifier::Shift => 50,
            KeyModifier::Win | KeyModifier::Super => 133,
        }
    }
}

impl DesktopBackend for LinuxBackend {
    fn platform_name(&self) -> &str {
        "linux"
    }

    fn is_available(&self) -> bool {
        // Connection exists, so we're available
        true
    }

    fn list_windows(
        &self,
        title_filter: Option<&str>,
        visible_only: bool,
    ) -> DesktopResult<Vec<WindowInfo>> {
        let windows = self.get_client_list();
        let mut result = Vec::new();

        for window in windows {
            if let Some(info) = self.window_to_info(window) {
                // Apply filters
                if visible_only && !info.visible {
                    continue;
                }
                if let Some(filter) = title_filter {
                    let filter_lower = filter.to_lowercase();
                    if !info.title.to_lowercase().contains(&filter_lower) {
                        continue;
                    }
                }
                result.push(info);
            }
        }

        Ok(result)
    }

    fn get_active_window(&self) -> DesktopResult<Option<WindowInfo>> {
        let reply = self
            .conn
            .get_property(
                false,
                self.root,
                self.atoms.net_active_window,
                AtomEnum::WINDOW,
                0,
                1,
            )
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?
            .reply()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        let window = reply
            .value32()
            .and_then(|mut iter| iter.next())
            .unwrap_or(0);

        if window == 0 {
            return Ok(None);
        }

        Ok(self.window_to_info(window))
    }

    fn focus_window(&self, window_id: &str) -> DesktopResult<bool> {
        let window = self.parse_window_id(window_id)?;

        // Send _NET_ACTIVE_WINDOW message
        let data = [1u32, 0, 0, 0, 0]; // Source = 1 (application)
        self.send_client_message(window, self.atoms.net_active_window, data)?;

        // Also try SetInputFocus as backup
        let _ = self
            .conn
            .set_input_focus(InputFocus::POINTER_ROOT, window, x11rb::CURRENT_TIME);

        self.conn
            .flush()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        Ok(true)
    }

    fn move_window(&self, window_id: &str, x: i32, y: i32) -> DesktopResult<bool> {
        let window = self.parse_window_id(window_id)?;

        // Use _NET_MOVERESIZE_WINDOW
        let flags = 0x0300u32; // StaticGravity, move
        let data = [flags, x as u32, y as u32, 0, 0];
        self.send_client_message(window, self.atoms.net_moveresize_window, data)?;

        Ok(true)
    }

    fn resize_window(&self, window_id: &str, width: u32, height: u32) -> DesktopResult<bool> {
        let window = self.parse_window_id(window_id)?;

        // Use _NET_MOVERESIZE_WINDOW
        let flags = 0x0C00u32; // StaticGravity, resize
        let data = [flags, 0, 0, width, height];
        self.send_client_message(window, self.atoms.net_moveresize_window, data)?;

        Ok(true)
    }

    fn minimize_window(&self, window_id: &str) -> DesktopResult<bool> {
        let window = self.parse_window_id(window_id)?;

        // Use XIconifyWindow equivalent
        self.conn
            .unmap_window(window)
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        // Also set _NET_WM_STATE_HIDDEN
        let data = [
            1u32,                           // _NET_WM_STATE_ADD
            self.atoms.net_wm_state_hidden, // property
            0,                              // no second property
            1,                              // source = normal application
            0,
        ];
        self.send_client_message(window, self.atoms.net_wm_state, data)?;

        Ok(true)
    }

    fn maximize_window(&self, window_id: &str) -> DesktopResult<bool> {
        let window = self.parse_window_id(window_id)?;

        // Add both MAXIMIZED_HORZ and MAXIMIZED_VERT
        let data = [
            1u32, // _NET_WM_STATE_ADD
            self.atoms.net_wm_state_maximized_horz,
            self.atoms.net_wm_state_maximized_vert,
            1, // source = normal application
            0,
        ];
        self.send_client_message(window, self.atoms.net_wm_state, data)?;

        Ok(true)
    }

    fn restore_window(&self, window_id: &str) -> DesktopResult<bool> {
        let window = self.parse_window_id(window_id)?;

        // Map the window first (in case it's minimized)
        self.conn
            .map_window(window)
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        // Remove HIDDEN state
        let data = [
            0u32,                           // _NET_WM_STATE_REMOVE
            self.atoms.net_wm_state_hidden, // property
            0,
            1, // source
            0,
        ];
        self.send_client_message(window, self.atoms.net_wm_state, data)?;

        // Remove MAXIMIZED states
        let data = [
            0u32, // _NET_WM_STATE_REMOVE
            self.atoms.net_wm_state_maximized_horz,
            self.atoms.net_wm_state_maximized_vert,
            1,
            0,
        ];
        self.send_client_message(window, self.atoms.net_wm_state, data)?;

        Ok(true)
    }

    fn close_window(&self, window_id: &str) -> DesktopResult<bool> {
        let window = self.parse_window_id(window_id)?;

        // Send _NET_CLOSE_WINDOW message
        let timestamp = x11rb::CURRENT_TIME;
        let data = [timestamp, 1, 0, 0, 0]; // source = 1 (application)
        self.send_client_message(window, self.atoms.net_close_window, data)?;

        Ok(true)
    }

    fn list_screens(&self) -> DesktopResult<Vec<ScreenInfo>> {
        // Use RandR to get screen information
        let resources = self
            .conn
            .randr_get_screen_resources(self.root)
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?
            .reply()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        let mut screens = Vec::new();

        for (idx, crtc) in resources.crtcs.iter().enumerate() {
            if let Ok(info) = self
                .conn
                .randr_get_crtc_info(*crtc, 0)
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?
                .reply()
                && info.width > 0
                && info.height > 0
            {
                screens.push(ScreenInfo {
                    id: idx as u32,
                    name: format!("Screen {}", idx),
                    x: info.x as i32,
                    y: info.y as i32,
                    width: info.width as u32,
                    height: info.height as u32,
                    is_primary: idx == 0,
                    scale: 1.0,
                });
            }
        }

        // If RandR didn't work, fall back to root window size
        if screens.is_empty() {
            let setup = self.conn.setup();
            let screen = &setup.roots[self.screen_num];
            screens.push(ScreenInfo {
                id: 0,
                name: "Primary".to_string(),
                x: 0,
                y: 0,
                width: screen.width_in_pixels as u32,
                height: screen.height_in_pixels as u32,
                is_primary: true,
                scale: 1.0,
            });
        }

        Ok(screens)
    }

    fn get_screen_size(&self) -> DesktopResult<(u32, u32)> {
        let setup = self.conn.setup();
        let screen = &setup.roots[self.screen_num];
        Ok((
            screen.width_in_pixels as u32,
            screen.height_in_pixels as u32,
        ))
    }

    fn screenshot_screen(&self, screen_id: Option<u32>) -> DesktopResult<Vec<u8>> {
        let screens = self.list_screens()?;
        let screen = screen_id
            .and_then(|id| screens.iter().find(|s| s.id == id))
            .or_else(|| screens.first())
            .ok_or_else(|| DesktopError::ScreenNotFound("No screens found".to_string()))?;

        self.screenshot_region(screen.x, screen.y, screen.width, screen.height)
    }

    fn screenshot_window(&self, window_id: &str) -> DesktopResult<Vec<u8>> {
        let window = self.parse_window_id(window_id)?;

        let geom = self
            .conn
            .get_geometry(window)
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?
            .reply()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        // Get window image
        let image = self
            .conn
            .get_image(
                x11rb::protocol::xproto::ImageFormat::Z_PIXMAP,
                window,
                0,
                0,
                geom.width,
                geom.height,
                !0,
            )
            .map_err(|e| DesktopError::ScreenshotFailed(e.to_string()))?
            .reply()
            .map_err(|e| DesktopError::ScreenshotFailed(e.to_string()))?;

        // Convert to PNG
        self.convert_to_png(
            &image.data,
            geom.width as u32,
            geom.height as u32,
            image.depth,
        )
    }

    fn screenshot_region(&self, x: i32, y: i32, width: u32, height: u32) -> DesktopResult<Vec<u8>> {
        // Get image from root window
        let image = self
            .conn
            .get_image(
                x11rb::protocol::xproto::ImageFormat::Z_PIXMAP,
                self.root,
                x as i16,
                y as i16,
                width as u16,
                height as u16,
                !0,
            )
            .map_err(|e| DesktopError::ScreenshotFailed(e.to_string()))?
            .reply()
            .map_err(|e| DesktopError::ScreenshotFailed(e.to_string()))?;

        // Convert to PNG
        self.convert_to_png(&image.data, width, height, image.depth)
    }

    fn get_mouse_position(&self) -> DesktopResult<(i32, i32)> {
        let reply = self
            .conn
            .query_pointer(self.root)
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?
            .reply()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        Ok((reply.root_x as i32, reply.root_y as i32))
    }

    fn move_mouse(&self, x: i32, y: i32, relative: bool) -> DesktopResult<bool> {
        let (dest_x, dest_y) = if relative {
            let (cur_x, cur_y) = self.get_mouse_position()?;
            (cur_x + x, cur_y + y)
        } else {
            (x, y)
        };

        self.conn
            .warp_pointer(
                self.root,
                self.root,
                0,
                0,
                0,
                0,
                dest_x as i16,
                dest_y as i16,
            )
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        self.conn
            .flush()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        Ok(true)
    }

    fn click_mouse(
        &self,
        button: MouseButton,
        x: Option<i32>,
        y: Option<i32>,
        clicks: u32,
    ) -> DesktopResult<bool> {
        // Move mouse if position specified
        if let (Some(x), Some(y)) = (x, y) {
            self.move_mouse(x, y, false)?;
        }

        let button_code = match button {
            MouseButton::Left => 1,
            MouseButton::Middle => 2,
            MouseButton::Right => 3,
        };

        for _ in 0..clicks {
            // Press
            self.conn
                .xtest_fake_input(4, button_code, 0, self.root, 0, 0, 0)
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
            self.conn
                .flush()
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

            std::thread::sleep(Duration::from_millis(10));

            // Release
            self.conn
                .xtest_fake_input(5, button_code, 0, self.root, 0, 0, 0)
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
            self.conn
                .flush()
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

            if clicks > 1 {
                std::thread::sleep(Duration::from_millis(50));
            }
        }

        Ok(true)
    }

    fn drag_mouse(
        &self,
        start_x: i32,
        start_y: i32,
        end_x: i32,
        end_y: i32,
        button: MouseButton,
        duration_ms: u64,
    ) -> DesktopResult<bool> {
        let button_code = match button {
            MouseButton::Left => 1,
            MouseButton::Middle => 2,
            MouseButton::Right => 3,
        };

        // Move to start position
        self.move_mouse(start_x, start_y, false)?;
        std::thread::sleep(Duration::from_millis(10));

        // Press button
        self.conn
            .xtest_fake_input(4, button_code, 0, self.root, 0, 0, 0)
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
        self.conn
            .flush()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        // Interpolate movement
        let steps = 20u32;
        let step_delay = Duration::from_millis(duration_ms / steps as u64);

        for i in 1..=steps {
            let t = i as f64 / steps as f64;
            let x = start_x as f64 + (end_x - start_x) as f64 * t;
            let y = start_y as f64 + (end_y - start_y) as f64 * t;

            self.conn
                .warp_pointer(self.root, self.root, 0, 0, 0, 0, x as i16, y as i16)
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
            self.conn
                .flush()
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

            std::thread::sleep(step_delay);
        }

        // Release button
        self.conn
            .xtest_fake_input(5, button_code, 0, self.root, 0, 0, 0)
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
        self.conn
            .flush()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        Ok(true)
    }

    fn scroll_mouse(
        &self,
        amount: i32,
        direction: ScrollDirection,
        x: Option<i32>,
        y: Option<i32>,
    ) -> DesktopResult<bool> {
        // Move mouse if position specified
        if let (Some(x), Some(y)) = (x, y) {
            self.move_mouse(x, y, false)?;
        }

        let (button_up, button_down) = match direction {
            ScrollDirection::Vertical => (4, 5), // Button 4/5 for vertical scroll
            ScrollDirection::Horizontal => (6, 7), // Button 6/7 for horizontal scroll
        };

        let button = if amount > 0 { button_down } else { button_up };
        let clicks = amount.unsigned_abs();

        for _ in 0..clicks {
            // Press
            self.conn
                .xtest_fake_input(4, button, 0, self.root, 0, 0, 0)
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
            // Release
            self.conn
                .xtest_fake_input(5, button, 0, self.root, 0, 0, 0)
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
            self.conn
                .flush()
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
        }

        Ok(true)
    }

    fn type_text(&self, text: &str, interval_ms: u64) -> DesktopResult<bool> {
        for c in text.chars() {
            let key_str = c.to_string();
            if let Some(keycode) = self.key_to_keycode(&key_str) {
                // Check if shift is needed
                let needs_shift = c.is_uppercase() || "!@#$%^&*()_+{}|:\"<>?~".contains(c);

                if needs_shift {
                    // Press shift
                    self.conn
                        .xtest_fake_input(2, 50, 0, self.root, 0, 0, 0)
                        .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
                }

                // Press and release key
                self.conn
                    .xtest_fake_input(2, keycode, 0, self.root, 0, 0, 0)
                    .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
                self.conn
                    .flush()
                    .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

                self.conn
                    .xtest_fake_input(3, keycode, 0, self.root, 0, 0, 0)
                    .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

                if needs_shift {
                    // Release shift
                    self.conn
                        .xtest_fake_input(3, 50, 0, self.root, 0, 0, 0)
                        .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
                }

                self.conn
                    .flush()
                    .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

                if interval_ms > 0 {
                    std::thread::sleep(Duration::from_millis(interval_ms));
                }
            } else {
                warn!("Unknown character for typing: {:?}", c);
            }
        }

        Ok(true)
    }

    fn send_key(&self, key: &str, modifiers: &[KeyModifier]) -> DesktopResult<bool> {
        let keycode = self
            .key_to_keycode(key)
            .ok_or_else(|| DesktopError::OperationFailed(format!("Unknown key: {}", key)))?;

        // Press modifiers
        for modifier in modifiers {
            let mod_keycode = self.modifier_to_keycode(modifier);
            self.conn
                .xtest_fake_input(2, mod_keycode, 0, self.root, 0, 0, 0)
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
        }

        // Press and release main key
        self.conn
            .xtest_fake_input(2, keycode, 0, self.root, 0, 0, 0)
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
        self.conn
            .flush()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        std::thread::sleep(Duration::from_millis(10));

        self.conn
            .xtest_fake_input(3, keycode, 0, self.root, 0, 0, 0)
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        // Release modifiers (in reverse order)
        for modifier in modifiers.iter().rev() {
            let mod_keycode = self.modifier_to_keycode(modifier);
            self.conn
                .xtest_fake_input(3, mod_keycode, 0, self.root, 0, 0, 0)
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
        }

        self.conn
            .flush()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        Ok(true)
    }

    fn send_hotkey(&self, keys: &[String]) -> DesktopResult<bool> {
        let keycodes: Vec<u8> = keys.iter().filter_map(|k| self.key_to_keycode(k)).collect();

        if keycodes.is_empty() {
            return Err(DesktopError::OperationFailed(
                "No valid keys in hotkey".to_string(),
            ));
        }

        // Press all keys
        for &keycode in &keycodes {
            self.conn
                .xtest_fake_input(2, keycode, 0, self.root, 0, 0, 0)
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
        }
        self.conn
            .flush()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        std::thread::sleep(Duration::from_millis(10));

        // Release all keys (in reverse order)
        for &keycode in keycodes.iter().rev() {
            self.conn
                .xtest_fake_input(3, keycode, 0, self.root, 0, 0, 0)
                .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;
        }
        self.conn
            .flush()
            .map_err(|e| DesktopError::OperationFailed(e.to_string()))?;

        Ok(true)
    }
}

impl LinuxBackend {
    /// Convert raw X11 image data to PNG
    fn convert_to_png(
        &self,
        data: &[u8],
        width: u32,
        height: u32,
        depth: u8,
    ) -> DesktopResult<Vec<u8>> {
        use image::{ImageBuffer, Rgba};

        // Assume BGRA format for 32-bit depth
        if depth != 24 && depth != 32 {
            return Err(DesktopError::ScreenshotFailed(format!(
                "Unsupported depth: {}",
                depth
            )));
        }

        let bytes_per_pixel = if depth == 32 { 4 } else { 3 };
        let expected_size = (width * height * bytes_per_pixel as u32) as usize;

        if data.len() < expected_size {
            return Err(DesktopError::ScreenshotFailed(format!(
                "Insufficient data: got {}, expected {}",
                data.len(),
                expected_size
            )));
        }

        let mut img: ImageBuffer<Rgba<u8>, Vec<u8>> = ImageBuffer::new(width, height);

        for y in 0..height {
            for x in 0..width {
                let idx = (y * width + x) as usize * bytes_per_pixel;
                let (r, g, b, a) = if depth == 32 {
                    // BGRA format
                    (data[idx + 2], data[idx + 1], data[idx], data[idx + 3])
                } else {
                    // BGR format
                    (data[idx + 2], data[idx + 1], data[idx], 255)
                };
                img.put_pixel(x, y, Rgba([r, g, b, a]));
            }
        }

        let mut png_data = Vec::new();
        let encoder = image::codecs::png::PngEncoder::new(&mut png_data);
        encoder
            .write_image(&img, width, height, image::ExtendedColorType::Rgba8)
            .map_err(|e: image::ImageError| DesktopError::ScreenshotFailed(e.to_string()))?;

        Ok(png_data)
    }
}
