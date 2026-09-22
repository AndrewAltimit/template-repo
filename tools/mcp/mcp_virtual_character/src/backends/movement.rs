//! Parsing and validation of movement / avatar parameter maps.
//!
//! `send_animation` and sequence `movement` events pass a free-form
//! `parameters` object. These helpers turn it into typed commands up front so
//! that bad input (strings where numbers are expected, NaN, unknown value
//! types) is reported as an error instead of being silently ignored.

use serde_json::Value;
use std::collections::HashMap;

use super::adapter::{BackendError, BackendResult};
use crate::constants::{DEFAULT_MOVEMENT_DURATION, MAX_MOVEMENT_DURATION};

/// Keys in `parameters` that are movement controls.
pub const MOVEMENT_KEYS: &[&str] = &[
    "move_forward",
    "move_right",
    "look_horizontal",
    "look_vertical",
    "jump",
    "crouch",
    "run",
    "duration",
];

/// Maximum number of custom avatar parameters in one command.
pub const MAX_AVATAR_PARAMS: usize = 64;

/// A validated movement command.
#[derive(Debug, Clone, PartialEq, Default)]
pub struct MovementCommand {
    /// `/input/Vertical` (-1..1).
    pub forward: Option<f32>,
    /// `/input/Horizontal` (-1..1).
    pub right: Option<f32>,
    /// `/input/LookHorizontal` turn rate (-1..1).
    pub look_horizontal: Option<f32>,
    /// `/input/LookVertical` (-1..1).
    pub look_vertical: Option<f32>,
    /// `/input/Run`.
    pub run: Option<bool>,
    /// Pulse `/input/Jump`.
    pub jump: bool,
    /// `/input/Crouch`.
    pub crouch: Option<bool>,
    /// Seconds after which continuous axes are reset to 0.
    pub duration: f64,
}

impl MovementCommand {
    /// True if any continuous axis is non-zero (needs an auto-stop timer).
    pub fn has_motion(&self) -> bool {
        [
            self.forward,
            self.right,
            self.look_horizontal,
            self.look_vertical,
        ]
        .iter()
        .any(|v| v.is_some_and(|x| x != 0.0))
    }
}

/// A typed value for a custom avatar parameter.
#[derive(Debug, Clone, PartialEq)]
pub enum AvatarParamValue {
    Int(i32),
    Float(f32),
    Bool(bool),
}

fn axis(params: &HashMap<String, Value>, key: &str) -> BackendResult<Option<f32>> {
    match params.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::Number(n)) => {
            let v = n.as_f64().ok_or_else(|| {
                BackendError::InvalidParameter(format!("{key} must be a finite number"))
            })?;
            if !v.is_finite() {
                return Err(BackendError::InvalidParameter(format!(
                    "{key} must be a finite number"
                )));
            }
            Ok(Some(v.clamp(-1.0, 1.0) as f32))
        },
        Some(other) => Err(BackendError::InvalidParameter(format!(
            "{key} must be a number between -1 and 1, got {other}"
        ))),
    }
}

fn flag(params: &HashMap<String, Value>, key: &str) -> BackendResult<Option<bool>> {
    match params.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::Bool(b)) => Ok(Some(*b)),
        Some(Value::Number(n)) if n.as_f64() == Some(0.0) => Ok(Some(false)),
        Some(Value::Number(n)) if n.as_f64() == Some(1.0) => Ok(Some(true)),
        Some(other) => Err(BackendError::InvalidParameter(format!(
            "{key} must be a boolean, got {other}"
        ))),
    }
}

/// Parse the movement portion of a `parameters` map.
///
/// Returns `Ok(None)` if the map contains no movement keys.
pub fn parse_movement(params: &HashMap<String, Value>) -> BackendResult<Option<MovementCommand>> {
    if !MOVEMENT_KEYS
        .iter()
        .any(|k| *k != "duration" && params.contains_key(*k))
    {
        return Ok(None);
    }

    let duration = match params.get("duration") {
        None | Some(Value::Null) => DEFAULT_MOVEMENT_DURATION,
        Some(Value::Number(n)) => {
            let d = n.as_f64().unwrap_or(f64::NAN);
            if !d.is_finite() || d <= 0.0 {
                return Err(BackendError::InvalidParameter(
                    "duration must be a positive number of seconds".to_string(),
                ));
            }
            d.min(MAX_MOVEMENT_DURATION)
        },
        Some(other) => {
            return Err(BackendError::InvalidParameter(format!(
                "duration must be a number, got {other}"
            )))
        },
    };

    Ok(Some(MovementCommand {
        forward: axis(params, "move_forward")?,
        right: axis(params, "move_right")?,
        look_horizontal: axis(params, "look_horizontal")?,
        look_vertical: axis(params, "look_vertical")?,
        run: flag(params, "run")?,
        jump: flag(params, "jump")?.unwrap_or(false),
        crouch: flag(params, "crouch")?,
        duration,
    }))
}

/// Validate an OSC parameter name (no whitespace or OSC pattern characters).
pub fn validate_param_name(name: &str) -> BackendResult<()> {
    let bad = name.is_empty()
        || name.len() > 128
        || name.starts_with('/')
        || name.contains("..")
        || name
            .chars()
            .any(|c| c.is_whitespace() || c.is_control() || "#*,?[]{}".contains(c));
    if bad {
        Err(BackendError::InvalidParameter(format!(
            "invalid parameter name '{name}'"
        )))
    } else {
        Ok(())
    }
}

/// Parse `parameters.avatar_params` into typed values.
pub fn parse_avatar_params(
    params: &HashMap<String, Value>,
) -> BackendResult<Vec<(String, AvatarParamValue)>> {
    let Some(raw) = params.get("avatar_params") else {
        return Ok(Vec::new());
    };
    let Value::Object(map) = raw else {
        return Err(BackendError::InvalidParameter(
            "avatar_params must be an object of name -> number/bool".to_string(),
        ));
    };
    if map.len() > MAX_AVATAR_PARAMS {
        return Err(BackendError::InvalidParameter(format!(
            "too many avatar_params ({} > {MAX_AVATAR_PARAMS})",
            map.len()
        )));
    }
    let mut out = Vec::with_capacity(map.len());
    for (name, value) in map {
        validate_param_name(name)?;
        let v = match value {
            Value::Bool(b) => AvatarParamValue::Bool(*b),
            Value::Number(n) => {
                if let Some(i) = n.as_i64() {
                    let i = i32::try_from(i).map_err(|_| {
                        BackendError::InvalidParameter(format!("{name} is out of i32 range"))
                    })?;
                    AvatarParamValue::Int(i)
                } else {
                    let f = n.as_f64().unwrap_or(f64::NAN);
                    if !f.is_finite() {
                        return Err(BackendError::InvalidParameter(format!(
                            "{name} must be finite"
                        )));
                    }
                    AvatarParamValue::Float(f as f32)
                }
            },
            other => {
                return Err(BackendError::InvalidParameter(format!(
                    "avatar_params.{name} must be a number or boolean, got {other}"
                )))
            },
        };
        out.push((name.clone(), v));
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn map(v: Value) -> HashMap<String, Value> {
        serde_json::from_value(v).unwrap()
    }

    #[test]
    fn no_movement_keys_yields_none() {
        assert_eq!(parse_movement(&map(json!({}))).unwrap(), None);
        assert_eq!(
            parse_movement(&map(json!({"avatar_params": {"VRCEmote": 3}}))).unwrap(),
            None
        );
        // duration alone is not a movement command.
        assert_eq!(parse_movement(&map(json!({"duration": 3}))).unwrap(), None);
    }

    #[test]
    fn movement_is_clamped_and_defaults_applied() {
        let m = parse_movement(&map(json!({"move_forward": 2.5, "look_horizontal": -0.5})))
            .unwrap()
            .unwrap();
        assert_eq!(m.forward, Some(1.0));
        assert_eq!(m.look_horizontal, Some(-0.5));
        assert_eq!(m.duration, DEFAULT_MOVEMENT_DURATION);
        assert!(m.has_motion());
    }

    #[test]
    fn movement_rejects_bad_types() {
        assert!(parse_movement(&map(json!({"move_forward": "fast"}))).is_err());
        assert!(parse_movement(&map(json!({"jump": "yes"}))).is_err());
        assert!(parse_movement(&map(json!({"move_right": 0.5, "duration": -1}))).is_err());
        assert!(parse_movement(&map(json!({"move_right": 0.5, "duration": "2"}))).is_err());
    }

    #[test]
    fn movement_duration_capped_and_flags_parsed() {
        let m = parse_movement(&map(
            json!({"jump": true, "run": 1, "crouch": false, "duration": 1000}),
        ))
        .unwrap()
        .unwrap();
        assert!(m.jump);
        assert_eq!(m.run, Some(true));
        assert_eq!(m.crouch, Some(false));
        assert_eq!(m.duration, MAX_MOVEMENT_DURATION);
        assert!(!m.has_motion());
    }

    #[test]
    fn avatar_params_parse() {
        let p = parse_avatar_params(&map(
            json!({"avatar_params": {"VRCEmote": 4, "Blush": 0.5, "Hat": true}}),
        ))
        .unwrap();
        assert!(p.contains(&("VRCEmote".to_string(), AvatarParamValue::Int(4))));
        assert!(p.contains(&("Blush".to_string(), AvatarParamValue::Float(0.5))));
        assert!(p.contains(&("Hat".to_string(), AvatarParamValue::Bool(true))));
    }

    #[test]
    fn avatar_params_reject_bad_input() {
        assert!(parse_avatar_params(&map(json!({"avatar_params": 5}))).is_err());
        assert!(parse_avatar_params(&map(json!({"avatar_params": {"a b": 1}}))).is_err());
        assert!(parse_avatar_params(&map(json!({"avatar_params": {"x": "str"}}))).is_err());
        assert!(parse_avatar_params(&map(json!({"avatar_params": {"/input/Jump": 1}}))).is_err());
        assert!(
            parse_avatar_params(&map(json!({"avatar_params": {"big": 10_000_000_000_i64}})))
                .is_err()
        );
    }

    #[test]
    fn param_names() {
        assert!(validate_param_name("VRCEmote").is_ok());
        assert!(validate_param_name("Menu/Toggle_1").is_ok());
        assert!(validate_param_name("").is_err());
        assert!(validate_param_name("a*").is_err());
        assert!(validate_param_name("../x").is_err());
    }
}
