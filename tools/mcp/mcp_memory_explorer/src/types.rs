//! Data types shared by the explorer engine and the MCP tool layer.
//!
//! Everything in this module is platform independent and free of I/O, so the
//! value encoding/decoding rules (which are easy to get subtly wrong) are unit
//! tested directly.

use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

/// Information about a running process.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ProcessInfo {
    pub name: String,
    pub pid: u32,
}

/// Information about a loaded module (EXE/DLL on Windows, mapped ELF/PE file on Linux).
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ModuleInfo {
    pub name: String,
    pub base_address: u64,
    pub size: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
}

impl ModuleInfo {
    /// Exclusive end address of the module image (saturating).
    pub fn end(&self) -> u64 {
        self.base_address.saturating_add(self.size)
    }

    /// Whether `address` falls inside this module's image.
    pub fn contains(&self, address: u64) -> bool {
        address >= self.base_address && address < self.end()
    }
}

/// A committed, contiguous range of the target's virtual address space.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct MemoryRegion {
    pub base: u64,
    pub size: u64,
    pub readable: bool,
    pub writable: bool,
    pub executable: bool,
    /// Backing kind: `image`, `mapped`, `private`, or `unknown`.
    pub kind: String,
}

impl MemoryRegion {
    /// Exclusive end address of the region (saturating).
    pub fn end(&self) -> u64 {
        self.base.saturating_add(self.size)
    }
}

/// One hop of a resolved pointer chain.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PointerStep {
    /// Address the pointer was read from.
    pub read_from: u64,
    /// Pointer value found there.
    pub pointer: u64,
    /// Offset added to the pointer.
    pub offset: i64,
    /// `pointer + offset`: the address used by the next step.
    pub result: u64,
}

/// Result of resolving a pointer chain.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PointerChain {
    pub base_address: u64,
    pub offsets: Vec<i64>,
    pub final_address: u64,
    pub steps: Vec<PointerStep>,
}

/// An address being watched for changes.
#[derive(Debug, Clone)]
pub struct WatchedAddress {
    pub address: u64,
    pub size: usize,
    pub label: String,
    pub last_value: Option<Vec<u8>>,
    pub value_type: ValueType,
}

/// Result of reading a watch.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WatchResult {
    pub label: String,
    pub address: String,
    #[serde(rename = "type")]
    pub value_type: ValueType,
    pub value: Value,
    pub raw_hex: String,
    pub changed: bool,
    /// Previous decoded value, present only when `changed` is true.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub previous_value: Option<Value>,
    /// Read/decode error for this watch (other watches are still reported).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

/// Memory dump result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryDump {
    pub address: String,
    /// Number of bytes actually dumped (may be less than requested).
    pub size: usize,
    pub requested: usize,
    /// True when the read stopped early at an unreadable page.
    pub truncated: bool,
    pub data: String,
}

/// Attachment result.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AttachResult {
    pub attached: bool,
    pub process_name: String,
    pub pid: u32,
    pub base_address: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub main_module: Option<String>,
    pub module_count: usize,
    pub is_32bit: bool,
    /// Other processes with the same name (pass `pid` to pick one).
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub other_matching_pids: Vec<u32>,
}

/// Explorer status.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExplorerStatus {
    pub attached: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub process: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pid: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub is_32bit: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub process_alive: Option<bool>,
    pub watches: Vec<String>,
    /// Number of scans (`scan_pattern` / `find_value`) run in this session.
    pub recent_scans: usize,
    /// Candidates retained from the last `find_value` for `refine_value`.
    pub scan_candidates: usize,
    pub platform: &'static str,
    pub memory_access_supported: bool,
}

/// Supported data types for memory reading, watching and value search.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case", try_from = "String")]
pub enum ValueType {
    #[default]
    Bytes,
    Int8,
    Int16,
    Int32,
    Int64,
    Uint8,
    Uint16,
    Uint32,
    Uint64,
    Float,
    Double,
    /// NUL-terminated UTF-8/ANSI string.
    String,
    /// NUL-terminated UTF-16LE string (Windows `wchar_t*`).
    Wstring,
    /// Pointer sized for the target (4 bytes for 32-bit, 8 for 64-bit).
    Pointer,
    Vector3,
    Vector4,
    Matrix4x4,
}

/// Canonical names of every [`ValueType`], for error messages and schemas.
pub const VALUE_TYPE_NAMES: &[&str] = &[
    "bytes",
    "int8",
    "int16",
    "int32",
    "int64",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "float",
    "double",
    "string",
    "wstring",
    "pointer",
    "vector3",
    "vector4",
    "matrix4x4",
];

/// Types accepted by `find_value` / `refine_value` (fixed-size scalars).
pub const SCALAR_TYPE_NAMES: &[&str] = &[
    "int8", "int16", "int32", "int64", "uint8", "uint16", "uint32", "uint64", "float", "double",
    "pointer",
];

impl std::str::FromStr for ValueType {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        let t = match s.trim().to_ascii_lowercase().as_str() {
            "bytes" | "byte_array" | "raw" => Self::Bytes,
            "int8" | "i8" => Self::Int8,
            "int16" | "i16" | "short" => Self::Int16,
            "int32" | "i32" | "int" => Self::Int32,
            "int64" | "i64" | "long" => Self::Int64,
            "uint8" | "u8" | "byte" => Self::Uint8,
            "uint16" | "u16" => Self::Uint16,
            "uint32" | "u32" => Self::Uint32,
            "uint64" | "u64" => Self::Uint64,
            "float" | "f32" | "float32" => Self::Float,
            "double" | "f64" | "float64" => Self::Double,
            "string" | "str" | "cstring" => Self::String,
            "wstring" | "wstr" | "utf16" => Self::Wstring,
            "pointer" | "ptr" => Self::Pointer,
            "vector3" | "vec3" => Self::Vector3,
            "vector4" | "vec4" => Self::Vector4,
            "matrix4x4" | "matrix" | "mat4" => Self::Matrix4x4,
            _ => {
                return Err(format!(
                    "Unknown value type '{}'. Valid types: {}",
                    s,
                    VALUE_TYPE_NAMES.join(", ")
                ));
            },
        };
        Ok(t)
    }
}

impl TryFrom<String> for ValueType {
    type Error = String;

    fn try_from(s: String) -> Result<Self, Self::Error> {
        s.parse()
    }
}

impl ValueType {
    /// Canonical lowercase name.
    pub fn name(self) -> &'static str {
        match self {
            Self::Bytes => "bytes",
            Self::Int8 => "int8",
            Self::Int16 => "int16",
            Self::Int32 => "int32",
            Self::Int64 => "int64",
            Self::Uint8 => "uint8",
            Self::Uint16 => "uint16",
            Self::Uint32 => "uint32",
            Self::Uint64 => "uint64",
            Self::Float => "float",
            Self::Double => "double",
            Self::String => "string",
            Self::Wstring => "wstring",
            Self::Pointer => "pointer",
            Self::Vector3 => "vector3",
            Self::Vector4 => "vector4",
            Self::Matrix4x4 => "matrix4x4",
        }
    }

    /// Size in bytes for fixed-size types; `None` for variable-size types
    /// (`bytes`, `string`, `wstring`) whose size comes from the caller.
    pub fn fixed_size(self, is_32bit: bool) -> Option<usize> {
        Some(match self {
            Self::Int8 | Self::Uint8 => 1,
            Self::Int16 | Self::Uint16 => 2,
            Self::Int32 | Self::Uint32 | Self::Float => 4,
            Self::Int64 | Self::Uint64 | Self::Double => 8,
            Self::Pointer => {
                if is_32bit {
                    4
                } else {
                    8
                }
            },
            Self::Vector3 => 12,
            Self::Vector4 => 16,
            Self::Matrix4x4 => 64,
            Self::Bytes | Self::String | Self::Wstring => return None,
        })
    }

    /// Whether this type can be searched for with `find_value`.
    pub fn is_scalar(self) -> bool {
        matches!(
            self,
            Self::Int8
                | Self::Int16
                | Self::Int32
                | Self::Int64
                | Self::Uint8
                | Self::Uint16
                | Self::Uint32
                | Self::Uint64
                | Self::Float
                | Self::Double
                | Self::Pointer
        )
    }

    /// Whether this is a floating point scalar (supports tolerance matching).
    pub fn is_float(self) -> bool {
        matches!(self, Self::Float | Self::Double)
    }

    /// Decode little-endian `data` as this type into a JSON value.
    ///
    /// Fixed-size types require at least [`Self::fixed_size`] bytes; a short
    /// buffer (e.g. a read that stopped at an unreadable page) is an error, never
    /// a panic.
    pub fn decode(self, data: &[u8], is_32bit: bool) -> Result<Value, String> {
        if let Some(need) = self.fixed_size(is_32bit)
            && data.len() < need
        {
            return Err(format!(
                "need {} bytes to decode {} but only {} were readable",
                need,
                self.name(),
                data.len()
            ));
        }
        Ok(match self {
            Self::Bytes => json!(hex_encode(data)),
            Self::Int8 => json!(data[0] as i8),
            Self::Int16 => json!(i16::from_le_bytes(arr(data))),
            Self::Int32 => json!(i32::from_le_bytes(arr(data))),
            Self::Int64 => json!(i64::from_le_bytes(arr(data))),
            Self::Uint8 => json!(data[0]),
            Self::Uint16 => json!(u16::from_le_bytes(arr(data))),
            Self::Uint32 => json!(u32::from_le_bytes(arr(data))),
            Self::Uint64 => json!(u64::from_le_bytes(arr(data))),
            Self::Float => f32_json(f32::from_le_bytes(arr(data))),
            Self::Double => f64_json(f64::from_le_bytes(arr(data))),
            Self::String => {
                let end = data.iter().position(|&b| b == 0).unwrap_or(data.len());
                json!(String::from_utf8_lossy(&data[..end]))
            },
            Self::Wstring => {
                let units: Vec<u16> = data
                    .as_chunks::<2>()
                    .0
                    .iter()
                    .map(|c| u16::from_le_bytes(*c))
                    .take_while(|&u| u != 0)
                    .collect();
                json!(String::from_utf16_lossy(&units))
            },
            Self::Pointer => json!(format!("{:#x}", read_pointer_le(data, is_32bit))),
            Self::Vector3 => {
                let f = floats::<3>(data);
                json!({"x": f32_json(f[0]), "y": f32_json(f[1]), "z": f32_json(f[2])})
            },
            Self::Vector4 => {
                let f = floats::<4>(data);
                json!({
                    "x": f32_json(f[0]), "y": f32_json(f[1]),
                    "z": f32_json(f[2]), "w": f32_json(f[3])
                })
            },
            Self::Matrix4x4 => {
                let f = floats::<16>(data);
                let rows: Vec<Value> = f
                    .as_chunks::<4>()
                    .0
                    .iter()
                    .map(|r| Value::Array(r.iter().map(|&v| f32_json(v)).collect()))
                    .collect();
                Value::Array(rows)
            },
        })
    }

    /// Decode a scalar as `f64` for numeric comparisons (`refine_value`).
    /// Returns `None` for non-scalar types or short buffers.
    pub fn scalar_as_f64(self, data: &[u8], is_32bit: bool) -> Option<f64> {
        if data.len() < self.fixed_size(is_32bit)? {
            return None;
        }
        Some(match self {
            Self::Int8 => data[0] as i8 as f64,
            Self::Int16 => i16::from_le_bytes(arr(data)) as f64,
            Self::Int32 => i32::from_le_bytes(arr(data)) as f64,
            Self::Int64 => i64::from_le_bytes(arr(data)) as f64,
            Self::Uint8 => data[0] as f64,
            Self::Uint16 => u16::from_le_bytes(arr(data)) as f64,
            Self::Uint32 => u32::from_le_bytes(arr(data)) as f64,
            Self::Uint64 => u64::from_le_bytes(arr(data)) as f64,
            Self::Float => f32::from_le_bytes(arr(data)) as f64,
            Self::Double => f64::from_le_bytes(arr(data)),
            Self::Pointer => read_pointer_le(data, is_32bit) as f64,
            _ => return None,
        })
    }
}

/// What a value search compares memory against.
#[derive(Debug, Clone, PartialEq)]
pub enum SearchTarget {
    /// Match these exact little-endian bytes.
    Exact(Vec<u8>),
    /// Match a float/double within `tolerance` of `target` (inclusive).
    Approx {
        value_type: ValueType,
        target: f64,
        tolerance: f64,
    },
}

impl SearchTarget {
    /// Build a search target from a user supplied JSON value.
    ///
    /// Integers accept JSON integers, integral floats, and decimal or `0x` hex
    /// strings (strings allow exact 64-bit values that JSON numbers cannot
    /// carry precisely). The value is range-checked against the type instead of
    /// being silently truncated/saturated.
    pub fn from_json(
        value_type: ValueType,
        value: &Value,
        tolerance: Option<f64>,
        is_32bit: bool,
    ) -> Result<Self, String> {
        if !value_type.is_scalar() {
            return Err(format!(
                "type '{}' cannot be searched; use one of: {}",
                value_type.name(),
                SCALAR_TYPE_NAMES.join(", ")
            ));
        }
        if value_type.is_float() {
            let v = json_to_f64(value)?;
            if !v.is_finite() {
                return Err("search value must be a finite number".into());
            }
            match tolerance {
                Some(t) if t < 0.0 || !t.is_finite() => {
                    Err("tolerance must be a finite, non-negative number".into())
                },
                Some(t) if t > 0.0 => Ok(Self::Approx {
                    value_type,
                    target: v,
                    tolerance: t,
                }),
                _ => Ok(Self::Exact(if value_type == ValueType::Float {
                    (v as f32).to_le_bytes().to_vec()
                } else {
                    v.to_le_bytes().to_vec()
                })),
            }
        } else {
            if tolerance.is_some_and(|t| t != 0.0) {
                return Err("tolerance is only supported for float/double searches".into());
            }
            let v = json_to_i128(value)?;
            Ok(Self::Exact(encode_int(value_type, v, is_32bit)?))
        }
    }

    /// Number of bytes a match spans.
    pub fn width(&self) -> usize {
        match self {
            Self::Exact(b) => b.len(),
            Self::Approx { value_type, .. } => value_type.fixed_size(false).unwrap_or(4),
        }
    }

    /// Whether `data` (at least [`Self::width`] bytes) matches.
    pub fn matches(&self, data: &[u8]) -> bool {
        match self {
            Self::Exact(b) => data.len() >= b.len() && &data[..b.len()] == b.as_slice(),
            Self::Approx {
                value_type,
                target,
                tolerance,
            } => value_type
                .scalar_as_f64(data, false)
                .is_some_and(|v| v.is_finite() && (v - target).abs() <= *tolerance),
        }
    }
}

/// Encode an integer as `value_type`, rejecting out-of-range values.
fn encode_int(value_type: ValueType, v: i128, is_32bit: bool) -> Result<Vec<u8>, String> {
    let out_of_range = || {
        format!(
            "value {} is out of range for type '{}'",
            v,
            value_type.name()
        )
    };
    macro_rules! enc {
        ($t:ty) => {
            <$t>::try_from(v)
                .map_err(|_| out_of_range())?
                .to_le_bytes()
                .to_vec()
        };
    }
    Ok(match value_type {
        ValueType::Int8 => enc!(i8),
        ValueType::Int16 => enc!(i16),
        ValueType::Int32 => enc!(i32),
        ValueType::Int64 => enc!(i64),
        ValueType::Uint8 => enc!(u8),
        ValueType::Uint16 => enc!(u16),
        ValueType::Uint32 => enc!(u32),
        ValueType::Uint64 => enc!(u64),
        ValueType::Pointer if is_32bit => enc!(u32),
        ValueType::Pointer => enc!(u64),
        _ => return Err(format!("'{}' is not an integer type", value_type.name())),
    })
}

/// Parse a JSON number or numeric string into an `f64`.
pub fn json_to_f64(value: &Value) -> Result<f64, String> {
    match value {
        Value::Number(n) => n
            .as_f64()
            .ok_or_else(|| format!("'{}' is not a valid number", n)),
        Value::String(s) => s
            .trim()
            .parse::<f64>()
            .map_err(|_| format!("'{}' is not a valid number", s)),
        other => Err(format!("expected a number, got {}", other)),
    }
}

/// Parse a JSON integer, integral float, or decimal/hex string into an `i128`.
pub fn json_to_i128(value: &Value) -> Result<i128, String> {
    match value {
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i as i128)
            } else if let Some(u) = n.as_u64() {
                Ok(u as i128)
            } else {
                let f = n.as_f64().unwrap_or(f64::NAN);
                if f.is_finite() && f.fract() == 0.0 && f.abs() < 2f64.powi(63) {
                    Ok(f as i128)
                } else {
                    Err(format!("'{}' is not an integer", n))
                }
            }
        },
        Value::String(s) => crate::address::parse_signed_number(s)
            .map_err(|_| format!("'{}' is not a valid integer", s)),
        other => Err(format!("expected an integer, got {}", other)),
    }
}

/// Lowercase hex encoding without separators.
pub fn hex_encode(data: &[u8]) -> String {
    use std::fmt::Write;
    let mut s = String::with_capacity(data.len() * 2);
    for b in data {
        let _ = write!(s, "{:02x}", b);
    }
    s
}

/// Read a little-endian pointer of the target's width from the start of `data`.
/// Caller guarantees `data` holds at least 4 (32-bit) or 8 (64-bit) bytes.
pub fn read_pointer_le(data: &[u8], is_32bit: bool) -> u64 {
    if is_32bit {
        u32::from_le_bytes(arr(data)) as u64
    } else {
        u64::from_le_bytes(arr(data))
    }
}

/// Copy the first `N` bytes into an array. Callers check the length first.
fn arr<const N: usize>(data: &[u8]) -> [u8; N] {
    let mut out = [0u8; N];
    out.copy_from_slice(&data[..N]);
    out
}

fn floats<const N: usize>(data: &[u8]) -> [f32; N] {
    let mut out = [0f32; N];
    for (i, v) in out.iter_mut().enumerate() {
        *v = f32::from_le_bytes(arr(&data[i * 4..]));
    }
    out
}

/// JSON for an `f32` using its shortest round-trip representation, so `1234.56f32`
/// renders as `1234.56` instead of `1234.56005859375`. Non-finite values become
/// strings (`"NaN"`, `"inf"`, `"-inf"`) because JSON has no representation for them.
pub fn f32_json(v: f32) -> Value {
    if v.is_finite() {
        format!("{}", v)
            .parse::<f64>()
            .map(|f| json!(f))
            .unwrap_or_else(|_| json!(v as f64))
    } else {
        json!(v.to_string())
    }
}

/// JSON for an `f64`; non-finite values become strings.
pub fn f64_json(v: f64) -> Value {
    if v.is_finite() {
        json!(v)
    } else {
        json!(v.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_value_types_and_aliases() {
        assert_eq!("FLOAT".parse::<ValueType>().unwrap(), ValueType::Float);
        assert_eq!("f64".parse::<ValueType>().unwrap(), ValueType::Double);
        assert_eq!("ptr".parse::<ValueType>().unwrap(), ValueType::Pointer);
        assert_eq!(
            "matrix4x4".parse::<ValueType>().unwrap(),
            ValueType::Matrix4x4
        );
        let err = "quaternion".parse::<ValueType>().unwrap_err();
        assert!(err.contains("Valid types"));
        for name in VALUE_TYPE_NAMES {
            let t: ValueType = name.parse().unwrap();
            assert_eq!(t.name(), *name);
        }
    }

    #[test]
    fn serde_roundtrip_uses_canonical_names() {
        let v = serde_json::to_value(ValueType::Matrix4x4).unwrap();
        assert_eq!(v, json!("matrix4x4"));
        let t: ValueType = serde_json::from_value(json!("I32")).unwrap();
        assert_eq!(t, ValueType::Int32);
        assert!(serde_json::from_value::<ValueType>(json!("nope")).is_err());
    }

    #[test]
    fn decode_scalars() {
        assert_eq!(
            ValueType::Int32
                .decode(&(-5i32).to_le_bytes(), false)
                .unwrap(),
            json!(-5)
        );
        assert_eq!(
            ValueType::Uint16.decode(&[0x34, 0x12], false).unwrap(),
            json!(0x1234)
        );
        assert_eq!(
            ValueType::Float
                .decode(&1234.56f32.to_le_bytes(), false)
                .unwrap(),
            json!(1234.56)
        );
        assert_eq!(
            ValueType::Float
                .decode(&f32::NAN.to_le_bytes(), false)
                .unwrap(),
            json!("NaN")
        );
        assert_eq!(
            ValueType::Pointer
                .decode(&0xdead_beefu32.to_le_bytes(), true)
                .unwrap(),
            json!("0xdeadbeef")
        );
        assert_eq!(
            ValueType::Pointer
                .decode(&0x7ff6_0000_1000u64.to_le_bytes(), false)
                .unwrap(),
            json!("0x7ff600001000")
        );
    }

    #[test]
    fn decode_short_buffer_is_error_not_panic() {
        for t in [
            ValueType::Int64,
            ValueType::Double,
            ValueType::Vector3,
            ValueType::Matrix4x4,
            ValueType::Pointer,
        ] {
            assert!(t.decode(&[1, 2, 3], false).is_err(), "{:?}", t);
        }
        // Variable-size types accept anything, including empty.
        assert_eq!(ValueType::Bytes.decode(&[], false).unwrap(), json!(""));
        assert_eq!(ValueType::String.decode(&[], false).unwrap(), json!(""));
        assert_eq!(
            ValueType::Wstring.decode(&[0x41], false).unwrap(),
            json!("")
        );
    }

    #[test]
    fn decode_strings() {
        assert_eq!(
            ValueType::String.decode(b"hello\0junk", false).unwrap(),
            json!("hello")
        );
        let w: Vec<u8> = "Hi!"
            .encode_utf16()
            .chain([0u16, 0x41])
            .flat_map(|u| u.to_le_bytes())
            .collect();
        assert_eq!(ValueType::Wstring.decode(&w, false).unwrap(), json!("Hi!"));
    }

    #[test]
    fn decode_vectors_and_matrix() {
        let bytes: Vec<u8> = (0..16)
            .flat_map(|i| (i as f32).to_le_bytes())
            .collect::<Vec<_>>();
        assert_eq!(
            ValueType::Vector3.decode(&bytes, false).unwrap(),
            json!({"x": 0.0, "y": 1.0, "z": 2.0})
        );
        let m = ValueType::Matrix4x4.decode(&bytes, false).unwrap();
        assert_eq!(m[1], json!([4.0, 5.0, 6.0, 7.0]));
        assert_eq!(m[3][3], json!(15.0));
    }

    #[test]
    fn fixed_sizes() {
        assert_eq!(ValueType::Pointer.fixed_size(true), Some(4));
        assert_eq!(ValueType::Pointer.fixed_size(false), Some(8));
        assert_eq!(ValueType::Matrix4x4.fixed_size(false), Some(64));
        assert_eq!(ValueType::Bytes.fixed_size(false), None);
    }

    #[test]
    fn search_target_int_range_checked() {
        let t = SearchTarget::from_json(ValueType::Int32, &json!(100), None, false).unwrap();
        assert_eq!(t, SearchTarget::Exact(100i32.to_le_bytes().to_vec()));

        // Out of range must not silently saturate.
        assert!(SearchTarget::from_json(ValueType::Uint8, &json!(256), None, false).is_err());
        assert!(SearchTarget::from_json(ValueType::Uint32, &json!(-1), None, false).is_err());
        // Non-integral float for an int type is rejected.
        assert!(SearchTarget::from_json(ValueType::Int32, &json!(1.5), None, false).is_err());
        // Integral float is accepted.
        assert!(SearchTarget::from_json(ValueType::Int32, &json!(7.0), None, false).is_ok());
        // Hex strings allow exact 64-bit values.
        let t =
            SearchTarget::from_json(ValueType::Uint64, &json!("0xFFFFFFFFFFFFFFFF"), None, false)
                .unwrap();
        assert_eq!(t, SearchTarget::Exact(vec![0xff; 8]));
        // Tolerance on ints is an error.
        assert!(SearchTarget::from_json(ValueType::Int32, &json!(1), Some(1.0), false).is_err());
    }

    #[test]
    fn search_target_pointer_width_follows_bitness() {
        let t = SearchTarget::from_json(ValueType::Pointer, &json!("0x1000"), None, true).unwrap();
        assert_eq!(t.width(), 4);
        assert!(
            SearchTarget::from_json(ValueType::Pointer, &json!("0x1_0000_0000"), None, true)
                .is_err()
        );
    }

    #[test]
    fn search_target_float_tolerance() {
        let t = SearchTarget::from_json(ValueType::Float, &json!(100.0), Some(0.5), false).unwrap();
        assert!(t.matches(&100.4f32.to_le_bytes()));
        assert!(!t.matches(&100.6f32.to_le_bytes()));
        assert!(!t.matches(&f32::NAN.to_le_bytes()));

        let exact = SearchTarget::from_json(ValueType::Double, &json!(2.5), None, false).unwrap();
        assert!(exact.matches(&2.5f64.to_le_bytes()));
        assert_eq!(exact.width(), 8);

        assert!(SearchTarget::from_json(ValueType::Float, &json!(1.0), Some(-1.0), false).is_err());
        assert!(SearchTarget::from_json(ValueType::Bytes, &json!(1), None, false).is_err());
    }

    #[test]
    fn module_contains() {
        let m = ModuleInfo {
            name: "a".into(),
            base_address: 0x1000,
            size: 0x100,
            path: None,
        };
        assert!(m.contains(0x1000));
        assert!(m.contains(0x10ff));
        assert!(!m.contains(0x1100));
    }
}
