//! Platform-agnostic input event types.
//!
//! Every backend maps its native input to these enums. The core framework
//! never sees raw platform input.

use serde::{Deserialize, Serialize};

/// A platform-agnostic input event.
#[derive(Debug, Clone, PartialEq)]
pub enum InputEvent {
    /// Cursor / analog stick moved to absolute position.
    CursorMove { x: i32, y: i32 },
    /// A face / d-pad button pressed.
    ButtonPress(Button),
    /// A face / d-pad button released.
    ButtonRelease(Button),
    /// Shoulder trigger pressed.
    TriggerPress(Trigger),
    /// Shoulder trigger released.
    TriggerRelease(Trigger),
    /// Character typed (on-screen keyboard or physical keyboard).
    TextInput(char),
    /// Backspace / delete-left.
    Backspace,
    /// Pointer click at absolute position (mouse or touch).
    PointerClick { x: i32, y: i32 },
    /// Pointer released.
    PointerRelease { x: i32, y: i32 },
    /// The OS instance gained focus.
    FocusGained,
    /// The OS instance lost focus.
    FocusLost,
    /// User requested quit (window close, etc.).
    Quit,
}

/// Buttons that map across all platforms.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Button {
    Up,
    Down,
    Left,
    Right,
    Confirm,
    Cancel,
    Triangle,
    Square,
    Start,
    Select,
}

/// Shoulder / trigger buttons.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Trigger {
    Left,
    Right,
}
