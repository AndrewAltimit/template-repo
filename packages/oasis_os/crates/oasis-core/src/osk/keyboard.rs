//! On-screen keyboard state and rendering.

use crate::backend::Color;
use crate::input::Button;
use crate::sdi::SdiRegistry;

/// Keyboard input mode.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OskMode {
    /// Lowercase letters.
    Alpha,
    /// Uppercase letters.
    AlphaUpper,
    /// Numbers and symbols.
    NumSymbol,
}

/// Configuration for the on-screen keyboard layout.
#[derive(Debug, Clone)]
pub struct OskConfig {
    /// Grid columns.
    pub cols: usize,
    /// Screen position (top-left).
    pub x: i32,
    pub y: i32,
    /// Cell size in pixels.
    pub cell_w: u32,
    pub cell_h: u32,
    /// Title displayed above the keyboard.
    pub title: String,
}

impl Default for OskConfig {
    fn default() -> Self {
        Self {
            cols: 10,
            x: 20,
            y: 100,
            cell_w: 40,
            cell_h: 32,
            title: "Input".to_string(),
        }
    }
}

/// Character grids for each mode.
const ALPHA_LOWER: &[char] = &[
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's',
    't', 'u', 'v', 'w', 'x', 'y', 'z', ' ', '.', ',', '!',
];

const ALPHA_UPPER: &[char] = &[
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S',
    'T', 'U', 'V', 'W', 'X', 'Y', 'Z', ' ', '.', ',', '!',
];

const NUM_SYMBOL: &[char] = &[
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '@', '#', '$', '%', '&', '*', '(', ')', '-',
    '_', '=', '+', '[', ']', '{', '}', '/', '\\', ':', ';',
];

/// Runtime state for the software on-screen keyboard.
#[derive(Debug)]
pub struct OskState {
    pub config: OskConfig,
    /// Current keyboard mode.
    pub mode: OskMode,
    /// Cursor position in the character grid.
    pub cursor: usize,
    /// The text buffer being edited.
    pub buffer: String,
    /// Whether the OSK is currently active/visible.
    pub active: bool,
    /// Whether the user confirmed or cancelled (`None` = still editing).
    pub result: Option<bool>,
}

impl OskState {
    /// Create a new OSK with the given config and initial text.
    pub fn new(config: OskConfig, initial: &str) -> Self {
        Self {
            config,
            mode: OskMode::Alpha,
            cursor: 0,
            buffer: initial.to_string(),
            active: true,
            result: None,
        }
    }

    /// Get the character grid for the current mode.
    fn chars(&self) -> &'static [char] {
        match self.mode {
            OskMode::Alpha => ALPHA_LOWER,
            OskMode::AlphaUpper => ALPHA_UPPER,
            OskMode::NumSymbol => NUM_SYMBOL,
        }
    }

    /// Number of rows in the current grid.
    pub fn rows(&self) -> usize {
        self.chars().len().div_ceil(self.config.cols)
    }

    /// Handle a button press. Returns `true` if the OSK consumed the input.
    pub fn handle_input(&mut self, button: &Button) -> bool {
        if !self.active {
            return false;
        }

        let chars = self.chars();
        let cols = self.config.cols;
        let len = chars.len();

        match button {
            Button::Right => {
                self.cursor = (self.cursor + 1) % len;
            },
            Button::Left => {
                if self.cursor == 0 {
                    self.cursor = len - 1;
                } else {
                    self.cursor -= 1;
                }
            },
            Button::Down => {
                let next = self.cursor + cols;
                if next < len {
                    self.cursor = next;
                }
            },
            Button::Up => {
                if self.cursor >= cols {
                    self.cursor -= cols;
                }
            },
            Button::Confirm => {
                // Type the selected character.
                if self.cursor < len {
                    self.buffer.push(chars[self.cursor]);
                }
            },
            Button::Square => {
                // Backspace.
                self.buffer.pop();
            },
            Button::Triangle => {
                // Cycle mode.
                self.mode = match self.mode {
                    OskMode::Alpha => OskMode::AlphaUpper,
                    OskMode::AlphaUpper => OskMode::NumSymbol,
                    OskMode::NumSymbol => OskMode::Alpha,
                };
                // Clamp cursor to new grid size.
                let new_len = self.chars().len();
                if self.cursor >= new_len {
                    self.cursor = new_len - 1;
                }
            },
            Button::Start => {
                // Confirm input.
                self.result = Some(true);
                self.active = false;
            },
            Button::Cancel => {
                // Cancel input.
                self.result = Some(false);
                self.active = false;
            },
            _ => return false,
        }
        true
    }

    /// Get the confirmed text, if the user pressed Start.
    pub fn confirmed_text(&self) -> Option<&str> {
        match self.result {
            Some(true) => Some(&self.buffer),
            _ => None,
        }
    }

    /// Whether the user cancelled.
    pub fn is_cancelled(&self) -> bool {
        self.result == Some(false)
    }

    /// Render the OSK to SDI objects.
    pub fn update_sdi(&self, sdi: &mut SdiRegistry) {
        let chars = self.chars();
        let cols = self.config.cols;
        let rows = self.rows();

        // Background.
        let bg_name = "osk_bg";
        if !sdi.contains(bg_name) {
            sdi.create(bg_name);
        }
        if let Ok(obj) = sdi.get_mut(bg_name) {
            obj.x = self.config.x - 4;
            obj.y = self.config.y - 24;
            obj.w = (cols as u32) * self.config.cell_w + 8;
            obj.h = (rows as u32) * self.config.cell_h + 48;
            obj.color = Color::rgba(20, 20, 40, 220);
            obj.visible = self.active;
        }

        // Title.
        let title_name = "osk_title";
        if !sdi.contains(title_name) {
            sdi.create(title_name);
        }
        if let Ok(obj) = sdi.get_mut(title_name) {
            obj.text = Some(self.config.title.clone());
            obj.x = self.config.x;
            obj.y = self.config.y - 20;
            obj.font_size = 12;
            obj.text_color = Color::WHITE;
            obj.w = 0;
            obj.h = 0;
            obj.visible = self.active;
        }

        // Input buffer display.
        let buf_name = "osk_buffer";
        if !sdi.contains(buf_name) {
            sdi.create(buf_name);
        }
        if let Ok(obj) = sdi.get_mut(buf_name) {
            obj.text = Some(format!("{}|", self.buffer));
            obj.x = self.config.x;
            obj.y = self.config.y + (rows as i32) * self.config.cell_h as i32 + 4;
            obj.font_size = 12;
            obj.text_color = Color::rgb(100, 200, 255);
            obj.w = 0;
            obj.h = 0;
            obj.visible = self.active;
        }

        // Character grid cells.
        for (i, &ch) in chars.iter().enumerate() {
            let name = format!("osk_key_{i}");
            if !sdi.contains(&name) {
                sdi.create(&name);
            }
            if let Ok(obj) = sdi.get_mut(&name) {
                let col = (i % cols) as i32;
                let row = (i / cols) as i32;
                obj.x = self.config.x + col * self.config.cell_w as i32;
                obj.y = self.config.y + row * self.config.cell_h as i32;
                obj.w = self.config.cell_w - 2;
                obj.h = self.config.cell_h - 2;
                obj.text = Some(ch.to_string());
                obj.font_size = 14;
                obj.text_color = Color::WHITE;
                obj.visible = self.active;

                if i == self.cursor {
                    obj.color = Color::rgb(60, 100, 180);
                } else {
                    obj.color = Color::rgb(40, 40, 60);
                }
            }
        }

        // Mode indicator.
        let mode_name = "osk_mode";
        if !sdi.contains(mode_name) {
            sdi.create(mode_name);
        }
        if let Ok(obj) = sdi.get_mut(mode_name) {
            let mode_text = match self.mode {
                OskMode::Alpha => "abc",
                OskMode::AlphaUpper => "ABC",
                OskMode::NumSymbol => "123",
            };
            obj.text = Some(format!("[{mode_text}] Triangle=mode Start=OK Cancel=back"));
            obj.x = self.config.x;
            obj.y = self.config.y + (rows as i32) * self.config.cell_h as i32 + 20;
            obj.font_size = 10;
            obj.text_color = Color::rgb(150, 150, 180);
            obj.w = 0;
            obj.h = 0;
            obj.visible = self.active;
        }
    }

    /// Hide all OSK-related SDI objects.
    pub fn hide_sdi(&self, sdi: &mut SdiRegistry) {
        let osk_names = ["osk_bg", "osk_title", "osk_buffer", "osk_mode"];
        for name in &osk_names {
            if let Ok(obj) = sdi.get_mut(name) {
                obj.visible = false;
            }
        }
        for i in 0..self.chars().len() {
            let name = format!("osk_key_{i}");
            if let Ok(obj) = sdi.get_mut(&name) {
                obj.visible = false;
            }
        }
    }
}
