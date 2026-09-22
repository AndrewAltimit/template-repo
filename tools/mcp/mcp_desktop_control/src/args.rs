//! Typed, panic-free argument parsing for the MCP tools.
//!
//! Every tool deserializes its JSON arguments into a struct defined here.
//! Missing required fields, wrong types and out-of-range values become a
//! clear `InvalidParameters` error instead of being silently defaulted or
//! truncated (the previous hand-rolled `as i32` casts wrapped around).
//!
//! Integers are accepted leniently as JSON integers, integral floats
//! (`100.0`) or numeric strings (`"100"`), because LLM clients produce all
//! three.

use serde::de::{DeserializeOwned, Error as _};
use serde::{Deserialize, Deserializer};
use serde_json::Value;

use crate::types::{KeyModifier, MouseButton, ScrollDirection};

/// Maximum characters accepted by `type_text`.
pub const MAX_TEXT_CHARS: usize = 10_000;
/// Maximum per-character delay for `type_text`.
pub const MAX_INTERVAL_MS: u64 = 1_000;
/// Maximum drag duration.
pub const MAX_DRAG_MS: u64 = 10_000;
/// Maximum clicks per `click_mouse` call.
pub const MAX_CLICKS: u32 = 10;
/// Maximum scroll notches per call.
pub const MAX_SCROLL: i32 = 100;
/// Maximum keys in one hotkey chord.
pub const MAX_HOTKEY_KEYS: usize = 8;
/// Largest window dimension accepted by `resize_window` (X11 protocol limit).
pub const MAX_WINDOW_DIM: u32 = 32_767;
/// Smallest `max_dimension` accepted for screenshot downscaling.
pub const MIN_MAX_DIMENSION: u32 = 16;

/// Deserialize tool arguments; `null` is treated as `{}`.
pub fn parse<T: DeserializeOwned>(args: Value) -> Result<T, String> {
    let args = if args.is_null() {
        Value::Object(Default::default())
    } else {
        args
    };
    serde_json::from_value(args).map_err(|e| e.to_string())
}

// ---------------------------------------------------------------------------
// Lenient scalar helpers
// ---------------------------------------------------------------------------

fn value_to_i64<E: serde::de::Error>(v: &Value) -> Result<i64, E> {
    match v {
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i)
            } else if let Some(f) = n.as_f64().filter(|f| f.fract() == 0.0 && f.abs() < 9.0e15) {
                // Integral and well inside the exactly-representable range.
                Ok(f as i64)
            } else {
                Err(E::custom(format!("expected an integer, got {n}")))
            }
        },
        Value::String(s) => s
            .trim()
            .parse::<i64>()
            .map_err(|_| E::custom(format!("expected an integer, got \"{s}\""))),
        other => Err(E::custom(format!("expected an integer, got {other}"))),
    }
}

fn int<'de, D, T>(d: D) -> Result<T, D::Error>
where
    D: Deserializer<'de>,
    T: TryFrom<i64>,
{
    let v = Value::deserialize(d)?;
    let i = value_to_i64::<D::Error>(&v)?;
    T::try_from(i).map_err(|_| D::Error::custom(format!("integer {i} is out of range")))
}

fn opt_int<'de, D, T>(d: D) -> Result<Option<T>, D::Error>
where
    D: Deserializer<'de>,
    T: TryFrom<i64>,
{
    match Option::<Value>::deserialize(d)? {
        None | Some(Value::Null) => Ok(None),
        Some(v) => {
            let i = value_to_i64::<D::Error>(&v)?;
            T::try_from(i)
                .map(Some)
                .map_err(|_| D::Error::custom(format!("integer {i} is out of range")))
        },
    }
}

/// Optional boolean; `null` means "use the default", strings "true"/"false" are
/// accepted.
fn opt_bool<'de, D: Deserializer<'de>>(d: D) -> Result<Option<bool>, D::Error> {
    match Value::deserialize(d)? {
        Value::Bool(b) => Ok(Some(b)),
        Value::String(s) if s.eq_ignore_ascii_case("true") => Ok(Some(true)),
        Value::String(s) if s.eq_ignore_ascii_case("false") => Ok(Some(false)),
        Value::Null => Ok(None),
        other => Err(D::Error::custom(format!("expected a boolean, got {other}"))),
    }
}

/// Window ids are decimal strings; integers and `0x`-prefixed hex (as printed
/// by `xdotool`/`wmctrl`) are accepted and normalized to decimal.
fn window_id<'de, D: Deserializer<'de>>(d: D) -> Result<String, D::Error> {
    let raw = match Value::deserialize(d)? {
        Value::String(s) => s.trim().to_string(),
        Value::Number(n) if n.is_u64() => n.to_string(),
        other => {
            return Err(D::Error::custom(format!(
                "window_id must be a string from list_windows, got {other}"
            )));
        },
    };
    let parsed = if let Some(hex) = raw.strip_prefix("0x").or_else(|| raw.strip_prefix("0X")) {
        u64::from_str_radix(hex, 16).ok()
    } else {
        raw.parse::<u64>().ok()
    };
    match parsed {
        Some(0) | None => Err(D::Error::custom(format!(
            "invalid window_id '{raw}': expected a non-zero id as returned by list_windows"
        ))),
        Some(id) => Ok(id.to_string()),
    }
}

fn default_clicks() -> u32 {
    1
}

fn default_drag_ms() -> u64 {
    500
}

fn default_interval_ms() -> u64 {
    50
}

// ---------------------------------------------------------------------------
// Argument structs
// ---------------------------------------------------------------------------

/// `list_windows`
#[derive(Debug, Deserialize)]
pub struct ListWindowsArgs {
    pub title_filter: Option<String>,
    #[serde(default, deserialize_with = "opt_bool")]
    visible_only: Option<bool>,
}

impl ListWindowsArgs {
    /// Only visible windows (default: true).
    pub fn visible_only(&self) -> bool {
        self.visible_only.unwrap_or(true)
    }
}

/// Tools that take only a window id.
#[derive(Debug, Deserialize)]
pub struct WindowArgs {
    #[serde(deserialize_with = "window_id")]
    pub window_id: String,
}

/// `move_window`
#[derive(Debug, Deserialize)]
pub struct MoveWindowArgs {
    #[serde(deserialize_with = "window_id")]
    pub window_id: String,
    #[serde(deserialize_with = "int")]
    pub x: i32,
    #[serde(deserialize_with = "int")]
    pub y: i32,
}

/// `resize_window`
#[derive(Debug, Deserialize)]
pub struct ResizeWindowArgs {
    #[serde(deserialize_with = "window_id")]
    pub window_id: String,
    #[serde(deserialize_with = "int")]
    pub width: u32,
    #[serde(deserialize_with = "int")]
    pub height: u32,
}

impl ResizeWindowArgs {
    pub fn validate(&self) -> Result<(), String> {
        for (name, v) in [("width", self.width), ("height", self.height)] {
            if !(1..=MAX_WINDOW_DIM).contains(&v) {
                return Err(format!(
                    "{name} must be between 1 and {MAX_WINDOW_DIM}, got {v}"
                ));
            }
        }
        Ok(())
    }
}

/// Options shared by all screenshot tools.
#[derive(Debug, Deserialize)]
pub struct ScreenshotOptions {
    /// File to write, relative to (or inside) the output directory.
    pub output_path: Option<String>,
    /// Also return the PNG inline as MCP image content.
    #[serde(default, deserialize_with = "opt_bool")]
    return_image: Option<bool>,
    /// Downscale so neither side exceeds this many pixels.
    #[serde(default, deserialize_with = "opt_int")]
    pub max_dimension: Option<u32>,
}

impl ScreenshotOptions {
    /// Return the PNG inline (default: false).
    pub fn return_image(&self) -> bool {
        self.return_image.unwrap_or(false)
    }

    pub fn validate(&self) -> Result<(), String> {
        match self.max_dimension {
            Some(m) if m < MIN_MAX_DIMENSION => Err(format!(
                "max_dimension must be at least {MIN_MAX_DIMENSION}, got {m}"
            )),
            _ => Ok(()),
        }
    }
}

/// `screenshot_screen`
#[derive(Debug, Deserialize)]
pub struct ScreenshotScreenArgs {
    #[serde(default, deserialize_with = "opt_int")]
    pub screen_id: Option<u32>,
    #[serde(flatten)]
    pub opts: ScreenshotOptions,
}

/// `screenshot_window`
#[derive(Debug, Deserialize)]
pub struct ScreenshotWindowArgs {
    #[serde(deserialize_with = "window_id")]
    pub window_id: String,
    #[serde(flatten)]
    pub opts: ScreenshotOptions,
}

/// `screenshot_region`
#[derive(Debug, Deserialize)]
pub struct ScreenshotRegionArgs {
    #[serde(deserialize_with = "int")]
    pub x: i32,
    #[serde(deserialize_with = "int")]
    pub y: i32,
    #[serde(deserialize_with = "int")]
    pub width: u32,
    #[serde(deserialize_with = "int")]
    pub height: u32,
    #[serde(flatten)]
    pub opts: ScreenshotOptions,
}

/// `move_mouse`
#[derive(Debug, Deserialize)]
pub struct MoveMouseArgs {
    #[serde(deserialize_with = "int")]
    pub x: i32,
    #[serde(deserialize_with = "int")]
    pub y: i32,
    #[serde(default, deserialize_with = "opt_bool")]
    relative: Option<bool>,
}

impl MoveMouseArgs {
    /// Move relative to the current position (default: false).
    pub fn relative(&self) -> bool {
        self.relative.unwrap_or(false)
    }
}

/// Optional `x`/`y` pair: both or neither.
pub fn optional_point(x: Option<i32>, y: Option<i32>) -> Result<Option<(i32, i32)>, String> {
    match (x, y) {
        (Some(x), Some(y)) => Ok(Some((x, y))),
        (None, None) => Ok(None),
        _ => Err("x and y must be given together (or both omitted)".to_string()),
    }
}

/// `click_mouse`
#[derive(Debug, Deserialize)]
pub struct ClickMouseArgs {
    #[serde(default)]
    pub button: MouseButton,
    #[serde(default, deserialize_with = "opt_int")]
    pub x: Option<i32>,
    #[serde(default, deserialize_with = "opt_int")]
    pub y: Option<i32>,
    #[serde(default = "default_clicks", deserialize_with = "int")]
    pub clicks: u32,
}

impl ClickMouseArgs {
    pub fn validate(&self) -> Result<Option<(i32, i32)>, String> {
        if !(1..=MAX_CLICKS).contains(&self.clicks) {
            return Err(format!(
                "clicks must be between 1 and {MAX_CLICKS}, got {}",
                self.clicks
            ));
        }
        optional_point(self.x, self.y)
    }
}

/// `drag_mouse`
#[derive(Debug, Deserialize)]
pub struct DragMouseArgs {
    #[serde(deserialize_with = "int")]
    pub start_x: i32,
    #[serde(deserialize_with = "int")]
    pub start_y: i32,
    #[serde(deserialize_with = "int")]
    pub end_x: i32,
    #[serde(deserialize_with = "int")]
    pub end_y: i32,
    #[serde(default)]
    pub button: MouseButton,
    #[serde(default = "default_drag_ms", deserialize_with = "int")]
    pub duration_ms: u64,
}

impl DragMouseArgs {
    pub fn validate(&self) -> Result<(), String> {
        if self.duration_ms > MAX_DRAG_MS {
            return Err(format!(
                "duration_ms must be at most {MAX_DRAG_MS}, got {}",
                self.duration_ms
            ));
        }
        Ok(())
    }
}

/// `scroll_mouse`
#[derive(Debug, Deserialize)]
pub struct ScrollMouseArgs {
    #[serde(deserialize_with = "int")]
    pub amount: i32,
    #[serde(default)]
    pub direction: ScrollDirection,
    #[serde(default, deserialize_with = "opt_int")]
    pub x: Option<i32>,
    #[serde(default, deserialize_with = "opt_int")]
    pub y: Option<i32>,
}

impl ScrollMouseArgs {
    pub fn validate(&self) -> Result<Option<(i32, i32)>, String> {
        if !(-MAX_SCROLL..=MAX_SCROLL).contains(&self.amount) {
            return Err(format!(
                "amount must be between -{MAX_SCROLL} and {MAX_SCROLL}, got {}",
                self.amount
            ));
        }
        optional_point(self.x, self.y)
    }
}

/// `type_text`
#[derive(Debug, Deserialize)]
pub struct TypeTextArgs {
    pub text: String,
    #[serde(default = "default_interval_ms", deserialize_with = "int")]
    pub interval_ms: u64,
}

impl TypeTextArgs {
    pub fn validate(&self) -> Result<(), String> {
        let n = self.text.chars().count();
        if n > MAX_TEXT_CHARS {
            return Err(format!(
                "text is {n} characters; at most {MAX_TEXT_CHARS} are allowed per call"
            ));
        }
        if self.interval_ms > MAX_INTERVAL_MS {
            return Err(format!(
                "interval_ms must be at most {MAX_INTERVAL_MS}, got {}",
                self.interval_ms
            ));
        }
        Ok(())
    }
}

/// `send_key`
#[derive(Debug, Deserialize)]
pub struct SendKeyArgs {
    pub key: String,
    #[serde(default)]
    pub modifiers: Option<Vec<KeyModifier>>,
}

/// `send_hotkey`
#[derive(Debug, Deserialize)]
pub struct SendHotkeyArgs {
    pub keys: Vec<String>,
}

impl SendHotkeyArgs {
    pub fn validate(&self) -> Result<(), String> {
        if self.keys.is_empty() {
            return Err("'keys' must contain at least one key".to_string());
        }
        if self.keys.len() > MAX_HOTKEY_KEYS {
            return Err(format!(
                "'keys' may contain at most {MAX_HOTKEY_KEYS} keys, got {}",
                self.keys.len()
            ));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn integers_are_lenient_but_range_checked() {
        let a: MoveMouseArgs = parse(json!({"x": 10, "y": "20"})).unwrap();
        assert_eq!((a.x, a.y), (10, 20));
        let a: MoveMouseArgs = parse(json!({"x": 10.0, "y": -5})).unwrap();
        assert_eq!((a.x, a.y), (10, -5));
        assert!(parse::<MoveMouseArgs>(json!({"x": 10.5, "y": 0})).is_err());
        let err = parse::<MoveMouseArgs>(json!({"x": 99_999_999_999i64, "y": 0})).unwrap_err();
        assert!(err.contains("out of range"), "{err}");
        let err = parse::<MoveMouseArgs>(json!({"x": 1})).unwrap_err();
        assert!(err.contains("missing field `y`"), "{err}");
        assert!(parse::<MoveMouseArgs>(json!({"x": true, "y": 0})).is_err());
    }

    #[test]
    fn negative_sizes_are_rejected() {
        let err = parse::<ResizeWindowArgs>(json!({"window_id": "5", "width": -1, "height": 10}))
            .unwrap_err();
        assert!(err.contains("out of range"), "{err}");
        let a: ResizeWindowArgs =
            parse(json!({"window_id": "5", "width": 0, "height": 10})).unwrap();
        assert!(a.validate().is_err());
        let a: ResizeWindowArgs =
            parse(json!({"window_id": "5", "width": 800, "height": 600})).unwrap();
        assert!(a.validate().is_ok());
    }

    #[test]
    fn window_ids_are_normalized() {
        let a: WindowArgs = parse(json!({"window_id": "0x1e00007"})).unwrap();
        assert_eq!(a.window_id, "31457287");
        let a: WindowArgs = parse(json!({"window_id": 12345})).unwrap();
        assert_eq!(a.window_id, "12345");
        let a: WindowArgs = parse(json!({"window_id": " 77 "})).unwrap();
        assert_eq!(a.window_id, "77");
        for bad in [json!("abc"), json!("0"), json!(-3), json!(""), json!(null)] {
            assert!(
                parse::<WindowArgs>(json!({"window_id": bad})).is_err(),
                "{bad} should be rejected"
            );
        }
        assert!(parse::<WindowArgs>(json!({})).is_err());
    }

    #[test]
    fn defaults_apply() {
        let a: ListWindowsArgs = parse(Value::Null).unwrap();
        assert!(a.visible_only());
        let a: ListWindowsArgs = parse(json!({"visible_only": null})).unwrap();
        assert!(a.visible_only());
        let a: ListWindowsArgs = parse(json!({"visible_only": false})).unwrap();
        assert!(!a.visible_only());
        assert!(a.title_filter.is_none());
        let a: ClickMouseArgs = parse(json!({})).unwrap();
        assert_eq!(a.button, MouseButton::Left);
        assert_eq!(a.clicks, 1);
        assert_eq!(a.validate().unwrap(), None);
        let a: DragMouseArgs =
            parse(json!({"start_x": 0, "start_y": 0, "end_x": 1, "end_y": 1})).unwrap();
        assert_eq!(a.duration_ms, 500);
        let a: TypeTextArgs = parse(json!({"text": "hi"})).unwrap();
        assert_eq!(a.interval_ms, 50);
        let a: ScreenshotScreenArgs = parse(json!({})).unwrap();
        assert!(!a.opts.return_image());
        assert!(a.screen_id.is_none());
    }

    #[test]
    fn invalid_enum_values_are_errors_not_silently_dropped() {
        let err = parse::<ClickMouseArgs>(json!({"button": "fourth"})).unwrap_err();
        assert!(err.contains("Invalid mouse button"), "{err}");
        let err =
            parse::<SendKeyArgs>(json!({"key": "a", "modifiers": ["ctrl", "hyper"]})).unwrap_err();
        assert!(err.contains("Invalid modifier"), "{err}");
        let err = parse::<SendHotkeyArgs>(json!({"keys": ["ctrl", 5]})).unwrap_err();
        assert!(err.contains("invalid type"), "{err}");
        let a: ScrollMouseArgs = parse(json!({"amount": 3, "direction": "HORIZONTAL"})).unwrap();
        assert_eq!(a.direction, ScrollDirection::Horizontal);
    }

    #[test]
    fn range_validation() {
        let a: ClickMouseArgs = parse(json!({"clicks": 11})).unwrap();
        assert!(a.validate().is_err());
        let a: ClickMouseArgs = parse(json!({"clicks": 0})).unwrap();
        assert!(a.validate().is_err());
        let a: ClickMouseArgs = parse(json!({"x": 5})).unwrap();
        assert!(a.validate().unwrap_err().contains("together"));
        let a: ScrollMouseArgs = parse(json!({"amount": 1000})).unwrap();
        assert!(a.validate().is_err());
        let a: DragMouseArgs = parse(
            json!({"start_x": 0, "start_y": 0, "end_x": 1, "end_y": 1, "duration_ms": 60000}),
        )
        .unwrap();
        assert!(a.validate().is_err());
        let a: TypeTextArgs = parse(json!({"text": "x".repeat(MAX_TEXT_CHARS + 1)})).unwrap();
        assert!(a.validate().is_err());
        let a: TypeTextArgs = parse(json!({"text": "ok", "interval_ms": 5000})).unwrap();
        assert!(a.validate().is_err());
        let a: SendHotkeyArgs = parse(json!({"keys": []})).unwrap();
        assert!(a.validate().is_err());
        let a: ScreenshotScreenArgs = parse(json!({"max_dimension": 4})).unwrap();
        assert!(a.opts.validate().is_err());
    }

    #[test]
    fn booleans_accept_strings() {
        let a: MoveMouseArgs = parse(json!({"x": 1, "y": 1, "relative": "true"})).unwrap();
        assert!(a.relative());
        assert!(parse::<MoveMouseArgs>(json!({"x": 1, "y": 1, "relative": "maybe"})).is_err());
    }
}
