//! Tests for the on-screen keyboard module.

use super::*;
use crate::input::Button;
use crate::sdi::SdiRegistry;

fn default_osk() -> OskState {
    OskState::new(OskConfig::default(), "")
}

#[test]
fn initial_state() {
    let osk = default_osk();
    assert!(osk.active);
    assert_eq!(osk.cursor, 0);
    assert_eq!(osk.mode, OskMode::Alpha);
    assert!(osk.buffer.is_empty());
    assert!(osk.result.is_none());
}

#[test]
fn navigate_right_wraps() {
    let mut osk = default_osk();
    // Alpha grid has 30 chars.
    for _ in 0..29 {
        osk.handle_input(&Button::Right);
    }
    assert_eq!(osk.cursor, 29);
    osk.handle_input(&Button::Right);
    assert_eq!(osk.cursor, 0); // Wrapped.
}

#[test]
fn navigate_left_wraps() {
    let mut osk = default_osk();
    osk.handle_input(&Button::Left);
    assert_eq!(osk.cursor, 29); // Wrapped to last.
}

#[test]
fn navigate_down() {
    let mut osk = default_osk();
    // Default cols=10, so down moves by 10.
    osk.handle_input(&Button::Down);
    assert_eq!(osk.cursor, 10);
}

#[test]
fn navigate_up() {
    let mut osk = default_osk();
    osk.cursor = 15;
    osk.handle_input(&Button::Up);
    assert_eq!(osk.cursor, 5);
}

#[test]
fn type_character() {
    let mut osk = default_osk();
    // Cursor at 0 = 'a'.
    osk.handle_input(&Button::Confirm);
    assert_eq!(osk.buffer, "a");
    // Move right to 'b'.
    osk.handle_input(&Button::Right);
    osk.handle_input(&Button::Confirm);
    assert_eq!(osk.buffer, "ab");
}

#[test]
fn backspace() {
    let mut osk = OskState::new(OskConfig::default(), "hello");
    osk.handle_input(&Button::Square);
    assert_eq!(osk.buffer, "hell");
}

#[test]
fn cycle_mode() {
    let mut osk = default_osk();
    assert_eq!(osk.mode, OskMode::Alpha);
    osk.handle_input(&Button::Triangle);
    assert_eq!(osk.mode, OskMode::AlphaUpper);
    osk.handle_input(&Button::Triangle);
    assert_eq!(osk.mode, OskMode::NumSymbol);
    osk.handle_input(&Button::Triangle);
    assert_eq!(osk.mode, OskMode::Alpha);
}

#[test]
fn confirm_returns_text() {
    let mut osk = OskState::new(OskConfig::default(), "test");
    osk.handle_input(&Button::Start);
    assert!(!osk.active);
    assert_eq!(osk.confirmed_text(), Some("test"));
}

#[test]
fn cancel_sets_flag() {
    let mut osk = default_osk();
    osk.handle_input(&Button::Cancel);
    assert!(!osk.active);
    assert!(osk.is_cancelled());
    assert!(osk.confirmed_text().is_none());
}

#[test]
fn inactive_osk_ignores_input() {
    let mut osk = default_osk();
    osk.active = false;
    let consumed = osk.handle_input(&Button::Right);
    assert!(!consumed);
    assert_eq!(osk.cursor, 0);
}

#[test]
fn rows_calculation() {
    let osk = default_osk();
    // 30 chars / 10 cols = 3 rows.
    assert_eq!(osk.rows(), 3);
}

#[test]
fn update_sdi_creates_objects() {
    let osk = default_osk();
    let mut sdi = SdiRegistry::new();
    osk.update_sdi(&mut sdi);
    assert!(sdi.contains("osk_bg"));
    assert!(sdi.contains("osk_title"));
    assert!(sdi.contains("osk_buffer"));
    assert!(sdi.contains("osk_mode"));
    assert!(sdi.contains("osk_key_0"));
    assert!(sdi.contains("osk_key_29"));
}

#[test]
fn hide_sdi_hides_objects() {
    let osk = default_osk();
    let mut sdi = SdiRegistry::new();
    osk.update_sdi(&mut sdi);

    osk.hide_sdi(&mut sdi);
    let bg = sdi.get("osk_bg").unwrap();
    assert!(!bg.visible);
    let key = sdi.get("osk_key_0").unwrap();
    assert!(!key.visible);
}

#[test]
fn initial_text_preserved() {
    let osk = OskState::new(OskConfig::default(), "hello world");
    assert_eq!(osk.buffer, "hello world");
}

#[test]
fn upper_mode_types_uppercase() {
    let mut osk = default_osk();
    osk.handle_input(&Button::Triangle); // Switch to AlphaUpper
    osk.handle_input(&Button::Confirm); // Type 'A'
    assert_eq!(osk.buffer, "A");
}

#[test]
fn num_mode_types_digits() {
    let mut osk = default_osk();
    osk.handle_input(&Button::Triangle); // AlphaUpper
    osk.handle_input(&Button::Triangle); // NumSymbol
    osk.handle_input(&Button::Confirm); // Type '0'
    assert_eq!(osk.buffer, "0");
}
