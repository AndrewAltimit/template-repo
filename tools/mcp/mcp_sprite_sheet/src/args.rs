//! Typed, panic-free tool-argument parsing.
//!
//! Tools deserialize their arguments into `#[derive(Deserialize)]` structs via
//! [`parse`]. Errors carry the JSON path of the offending field (for example
//! `pixels[3].x: integer 300 is out of range for u8`) and surface as
//! `InvalidParameters`.
//!
//! MCP clients (and LLMs) are not always precise about JSON types, so the
//! helpers here are deliberately lenient where it is unambiguous:
//! integers may arrive as integral floats (`3.0`) or numeric strings (`"3"`),
//! booleans as `"true"`/`"false"`, and nested objects/arrays as JSON-encoded
//! strings. Out-of-range values are errors, never silently wrapped.

use mcp_core::error::MCPError;
use serde::Deserialize;
use serde::de::{DeserializeOwned, Deserializer, Error as _};
use serde_json::Value;

/// Parse tool arguments into `T`, mapping failures to `InvalidParameters`.
pub fn parse<T: DeserializeOwned>(args: Value) -> Result<T, MCPError> {
    let args = if args.is_null() {
        Value::Object(Default::default())
    } else {
        args
    };
    serde_path_to_error::deserialize(args).map_err(|e| {
        let path = e.path().to_string();
        if path.is_empty() || path == "." {
            MCPError::InvalidParameters(e.inner().to_string())
        } else {
            MCPError::InvalidParameters(format!("{path}: {}", e.inner()))
        }
    })
}

/// Interpret a JSON value as an integer (int, integral float, or numeric string).
pub fn value_as_i64(v: &Value) -> Option<i64> {
    match v {
        Value::Number(n) => n.as_i64().or_else(|| {
            n.as_f64()
                .filter(|f| f.fract() == 0.0 && f.abs() < 9.0e15)
                .map(|f| f as i64)
        }),
        Value::String(s) => {
            let s = s.trim();
            s.parse::<i64>().ok().or_else(|| {
                s.parse::<f64>()
                    .ok()
                    .filter(|f| f.fract() == 0.0 && f.abs() < 9.0e15)
                    .map(|f| f as i64)
            })
        },
        _ => None,
    }
}

fn to_int<T: TryFrom<i64>, E: serde::de::Error>(v: &Value) -> Result<T, E> {
    let n = value_as_i64(v).ok_or_else(|| E::custom(format!("expected an integer, got {v}")))?;
    T::try_from(n).map_err(|_| {
        let ty = std::any::type_name::<T>();
        E::custom(format!("integer {n} is out of range for {ty}"))
    })
}

/// Lenient integer field: `#[serde(deserialize_with = "args::int")]`.
pub fn int<'de, D: Deserializer<'de>, T: TryFrom<i64>>(d: D) -> Result<T, D::Error> {
    let v = Value::deserialize(d)?;
    to_int(&v)
}

/// Lenient optional integer: `#[serde(default, deserialize_with = "args::opt_int")]`.
pub fn opt_int<'de, D: Deserializer<'de>, T: TryFrom<i64>>(d: D) -> Result<Option<T>, D::Error> {
    let v = Value::deserialize(d)?;
    if v.is_null() {
        return Ok(None);
    }
    to_int(&v).map(Some)
}

fn to_bool<E: serde::de::Error>(v: &Value) -> Result<bool, E> {
    match v {
        Value::Bool(b) => Ok(*b),
        Value::String(s) if s.eq_ignore_ascii_case("true") => Ok(true),
        Value::String(s) if s.eq_ignore_ascii_case("false") => Ok(false),
        Value::Number(n) if n.as_i64() == Some(1) => Ok(true),
        Value::Number(n) if n.as_i64() == Some(0) => Ok(false),
        _ => Err(E::custom(format!("expected a boolean, got {v}"))),
    }
}

/// Lenient optional boolean: `#[serde(default, deserialize_with = "args::opt_bool")]`.
pub fn opt_bool<'de, D: Deserializer<'de>>(d: D) -> Result<Option<bool>, D::Error> {
    let v = Value::deserialize(d)?;
    if v.is_null() {
        return Ok(None);
    }
    to_bool(&v).map(Some)
}

/// Decode a nested value that may have been sent as a JSON-encoded string.
fn unstringify(v: Value) -> Value {
    if let Value::String(s) = &v {
        let t = s.trim_start();
        if (t.starts_with('{') || t.starts_with('['))
            && let Ok(parsed) = serde_json::from_str::<Value>(s)
        {
            return parsed;
        }
    }
    v
}

fn nested<T: DeserializeOwned, E: serde::de::Error>(v: Value) -> Result<T, E> {
    serde_path_to_error::deserialize(unstringify(v)).map_err(|e| {
        let p = e.path().to_string();
        if p.is_empty() || p == "." {
            E::custom(e.inner())
        } else {
            E::custom(format!("{p}: {}", e.inner()))
        }
    })
}

/// Nested object/array that may arrive JSON-encoded as a string.
pub fn json<'de, D: Deserializer<'de>, T: DeserializeOwned>(d: D) -> Result<T, D::Error> {
    nested(Value::deserialize(d)?)
}

/// Optional nested object/array that may arrive JSON-encoded as a string.
pub fn opt_json<'de, D: Deserializer<'de>, T: DeserializeOwned>(
    d: D,
) -> Result<Option<T>, D::Error> {
    let v = Value::deserialize(d)?;
    if v.is_null() {
        return Ok(None);
    }
    nested(v).map(Some)
}

/// A rectangle argument `{x, y, width, height}` (lenient integers).
#[derive(Debug, Clone, Copy, Deserialize)]
pub struct RegionArg {
    #[serde(deserialize_with = "int")]
    pub x: i64,
    #[serde(deserialize_with = "int")]
    pub y: i64,
    #[serde(deserialize_with = "int")]
    pub width: i64,
    #[serde(deserialize_with = "int")]
    pub height: i64,
}

impl From<RegionArg> for crate::engine::Region {
    fn from(r: RegionArg) -> Self {
        Self {
            x: r.x,
            y: r.y,
            width: r.width,
            height: r.height,
        }
    }
}

/// A pixel argument: `{x, y, color_index}` or the compact `[x, y, color_index]`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PixelArg {
    pub x: i64,
    pub y: i64,
    pub color_index: u8,
}

impl<'de> Deserialize<'de> for PixelArg {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let v = Value::deserialize(d)?;
        let (x, y, c) = match &v {
            Value::Array(a) if a.len() == 3 => (&a[0], &a[1], &a[2]),
            Value::Object(o) => {
                let get = |k: &str| {
                    o.get(k)
                        .ok_or_else(|| D::Error::custom(format!("missing field `{k}`")))
                };
                (get("x")?, get("y")?, get("color_index")?)
            },
            _ => {
                return Err(D::Error::custom(
                    "expected {x, y, color_index} or [x, y, color_index]",
                ));
            },
        };
        Ok(Self {
            x: to_int(x)?,
            y: to_int(y)?,
            color_index: to_int(c)
                .map_err(|e: D::Error| D::Error::custom(format!("color_index: {e}")))?,
        })
    }
}

/// A coordinate argument: `{x, y}` or `[x, y]`.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PointArg {
    pub x: i64,
    pub y: i64,
}

impl<'de> Deserialize<'de> for PointArg {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let v = Value::deserialize(d)?;
        let (x, y) = match &v {
            Value::Array(a) if a.len() == 2 => (&a[0], &a[1]),
            Value::Object(o) => match (o.get("x"), o.get("y")) {
                (Some(x), Some(y)) => (x, y),
                _ => return Err(D::Error::custom("point needs `x` and `y`")),
            },
            _ => return Err(D::Error::custom("expected {x, y} or [x, y]")),
        };
        Ok(Self {
            x: to_int(x)?,
            y: to_int(y)?,
        })
    }
}

/// An RGBA color given as `[r, g, b, a]` (or `[r, g, b]`, alpha 255).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Rgba(pub [u8; 4]);

impl<'de> Deserialize<'de> for Rgba {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let v = unstringify(Value::deserialize(d)?);
        let Value::Array(a) = &v else {
            return Err(D::Error::custom("expected [r, g, b] or [r, g, b, a]"));
        };
        if a.len() != 3 && a.len() != 4 {
            return Err(D::Error::custom(format!(
                "expected 3 or 4 channels, got {}",
                a.len()
            )));
        }
        let mut out = [0, 0, 0, 255];
        for (i, c) in a.iter().enumerate() {
            out[i] = to_int(c)?;
        }
        Ok(Self(out))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[derive(Debug, Deserialize)]
    #[allow(dead_code)]
    struct T {
        name: String,
        #[serde(deserialize_with = "int")]
        n: u8,
        #[serde(default, deserialize_with = "opt_int")]
        o: Option<i32>,
        #[serde(default, deserialize_with = "opt_bool")]
        b: Option<bool>,
        #[serde(default, deserialize_with = "opt_json")]
        pts: Option<Vec<PixelArg>>,
        #[serde(default, deserialize_with = "opt_json")]
        region: Option<RegionArg>,
    }

    #[test]
    fn lenient_numbers_and_bools() {
        let t: T = parse(json!({"name": "a", "n": "7", "o": 3.0, "b": "true"})).unwrap();
        assert_eq!((t.n, t.o, t.b), (7, Some(3), Some(true)));
    }

    #[test]
    fn out_of_range_is_error_with_path() {
        let e = parse::<T>(json!({"name": "a", "n": 300}))
            .unwrap_err()
            .to_string();
        assert!(e.contains("n:") && e.contains("300"), "{e}");
        let e = parse::<T>(json!({"name": "a", "n": 1.5}))
            .unwrap_err()
            .to_string();
        assert!(e.contains("integer"), "{e}");
    }

    #[test]
    fn missing_field_mentions_name() {
        let e = parse::<T>(json!({"n": 1})).unwrap_err().to_string();
        assert!(e.contains("name"), "{e}");
        // Null args behave like {}.
        let e = parse::<T>(Value::Null).unwrap_err().to_string();
        assert!(e.contains("name"), "{e}");
    }

    #[test]
    fn pixels_in_both_forms_and_stringified() {
        let t: T = parse(json!({
            "name": "a", "n": 1,
            "pts": [[1, 2, 3], {"x": "4", "y": 5, "color_index": 6}]
        }))
        .unwrap();
        let pts = t.pts.unwrap();
        assert_eq!(
            pts[1],
            PixelArg {
                x: 4,
                y: 5,
                color_index: 6
            }
        );
        let t: T = parse(json!({"name": "a", "n": 1, "pts": "[[0,0,1]]"})).unwrap();
        assert_eq!(t.pts.unwrap().len(), 1);
        let e = parse::<T>(json!({"name": "a", "n": 1, "pts": [[0, 0, 999]]}))
            .unwrap_err()
            .to_string();
        assert!(e.contains("pts") && e.contains("color_index"), "{e}");
    }

    #[test]
    fn region_stringified_object() {
        let t: T = parse(json!({
            "name": "a", "n": 1,
            "region": "{\"x\": 1, \"y\": 2, \"width\": 3, \"height\": 4}"
        }))
        .unwrap();
        assert_eq!(t.region.unwrap().height, 4);
    }

    #[test]
    fn rgba_forms() {
        let c: Rgba = serde_json::from_value(json!([1, 2, 3])).unwrap();
        assert_eq!(c.0, [1, 2, 3, 255]);
        assert!(serde_json::from_value::<Rgba>(json!([1, 2])).is_err());
        assert!(serde_json::from_value::<Rgba>(json!([1, 2, 3, 256])).is_err());
    }
}
