//! Shared JSON value parsing helpers for MCP tool arguments.

use serde_json::Value;

/// Parse a JSON value as u32, handling integer, float, signed, and string representations.
pub fn json_as_u32(v: &Value) -> Option<u32> {
    v.as_u64()
        .map(|n| n as u32)
        .or_else(|| v.as_i64().map(|n| n as u32))
        .or_else(|| v.as_f64().map(|f| f as u32))
        .or_else(|| v.as_str().and_then(|s| s.parse::<u32>().ok()))
}

/// Parse a JSON value as i32, handling integer, float, and string representations.
pub fn json_as_i32(v: &Value) -> Option<i32> {
    v.as_i64()
        .map(|n| n as i32)
        .or_else(|| v.as_u64().map(|n| n as i32))
        .or_else(|| v.as_f64().map(|f| f as i32))
        .or_else(|| v.as_str().and_then(|s| s.parse::<i32>().ok()))
}

/// Parse a JSON value as u8, handling integer, float, and string representations.
pub fn json_as_u8(v: &Value) -> Option<u8> {
    json_as_u32(v).and_then(|n| u8::try_from(n).ok())
}
