//! Typed argument extraction for hand-written [`Tool`](crate::tool::Tool) impls.
//!
//! Tool arguments arrive as a raw [`serde_json::Value`]. Indexing it directly
//! (`args["limit"].as_u64().unwrap()`) panics or silently falls back on bad
//! input. The helpers here turn missing or wrong-typed arguments into
//! [`MCPError::InvalidParameters`] with a message naming the offending key, so
//! the model gets an actionable error.
//!
//! Two styles are supported:
//!
//! **Whole-struct** (preferred for tools with several parameters): derive
//! `Deserialize` + `JsonSchema` on an args struct, generate the input schema
//! with [`schema_for`](crate::schema::schema_for) and parse with [`parse_args`].
//!
//! ```
//! use mcp_core::args::parse_args;
//! use serde::Deserialize;
//! use serde_json::json;
//!
//! #[derive(Deserialize)]
//! struct SearchArgs {
//!     query: String,
//!     #[serde(default = "default_limit")]
//!     limit: u32,
//! }
//! fn default_limit() -> u32 { 10 }
//!
//! let a: SearchArgs = parse_args(json!({"query": "cats"})).unwrap();
//! assert_eq!((a.query.as_str(), a.limit), ("cats", 10));
//!
//! let err = parse_args::<SearchArgs>(json!({"limit": 5})).err().unwrap();
//! assert!(err.to_string().contains("missing field `query`"));
//! ```
//!
//! **Per-key** accessors via [`ArgsExt`]:
//!
//! ```
//! use mcp_core::args::ArgsExt;
//! use serde_json::json;
//!
//! let args = json!({"query": "cats", "limit": 5});
//! let query = args.required_str("query").unwrap();
//! let limit = args.optional_u64("limit").unwrap().unwrap_or(10);
//! let exact = args.optional_bool("exact").unwrap().unwrap_or(false);
//! assert_eq!((query, limit, exact), ("cats", 5, false));
//!
//! // Present but the wrong type is an error, not a silent default.
//! assert!(json!({"limit": "five"}).optional_u64("limit").is_err());
//! ```

use serde::de::DeserializeOwned;
use serde_json::Value;

use crate::error::{MCPError, Result};

/// Deserialize the whole argument object into `T`.
///
/// A `null` argument value (a client that sent no `arguments`) is treated as
/// an empty object, so structs whose fields are all optional still parse.
/// Errors become [`MCPError::InvalidParameters`] carrying serde's message
/// (e.g. ``missing field `query` `` or `invalid type: string "x", expected u32`).
pub fn parse_args<T: DeserializeOwned>(args: Value) -> Result<T> {
    let args = if args.is_null() {
        Value::Object(serde_json::Map::new())
    } else {
        args
    };
    serde_json::from_value(args).map_err(MCPError::invalid_params)
}

fn missing(key: &str) -> MCPError {
    MCPError::InvalidParameters(format!("Missing required parameter: {key}"))
}

fn wrong_type(key: &str, expected: &str) -> MCPError {
    MCPError::InvalidParameters(format!("Invalid parameter '{key}': expected {expected}"))
}

/// Present and not `null`.
fn present<'a>(args: &'a Value, key: &str) -> Option<&'a Value> {
    args.get(key).filter(|v| !v.is_null())
}

macro_rules! scalar_accessors {
    ($(($req:ident, $opt:ident, $ty:ty, $conv:expr, $expected:literal)),* $(,)?) => {
        $(
            #[doc = concat!("Required ", $expected, " argument `key`; missing, `null` or wrong-typed is an error.")]
            fn $req(&self, key: &str) -> Result<$ty> {
                self.$opt(key)?.ok_or_else(|| missing(key))
            }

            #[doc = concat!("Optional ", $expected, " argument `key`: `Ok(None)` when absent or `null`, an error when present with the wrong type.")]
            fn $opt(&self, key: &str) -> Result<Option<$ty>> {
                match present(self.as_value(), key) {
                    None => Ok(None),
                    Some(v) => {
                        let conv: fn(&Value) -> Option<$ty> = $conv;
                        conv(v).map(Some).ok_or_else(|| wrong_type(key, $expected))
                    },
                }
            }
        )*
    };
}

/// Typed accessors for tool arguments. Implemented for [`serde_json::Value`].
///
/// Every accessor treats an explicit `null` like an absent key.
pub trait ArgsExt {
    #[doc(hidden)]
    fn as_value(&self) -> &Value;

    /// Required string argument; missing, `null` or non-string is an error.
    fn required_str(&self, key: &str) -> Result<&str> {
        self.optional_str(key)?.ok_or_else(|| missing(key))
    }

    /// Optional string argument: `Ok(None)` when absent or `null`, an error
    /// when present but not a string.
    fn optional_str(&self, key: &str) -> Result<Option<&str>> {
        match present(self.as_value(), key) {
            None => Ok(None),
            Some(v) => v
                .as_str()
                .map(Some)
                .ok_or_else(|| wrong_type(key, "a string")),
        }
    }

    scalar_accessors!(
        (required_i64, optional_i64, i64, Value::as_i64, "an integer"),
        (
            required_u64,
            optional_u64,
            u64,
            Value::as_u64,
            "a non-negative integer"
        ),
        (required_f64, optional_f64, f64, Value::as_f64, "a number"),
        (
            required_bool,
            optional_bool,
            bool,
            Value::as_bool,
            "a boolean"
        ),
    );

    /// Required argument deserialized into any `T` (e.g. `Vec<String>`, an
    /// enum, a nested struct).
    fn required<T: DeserializeOwned>(&self, key: &str) -> Result<T> {
        self.optional(key)?.ok_or_else(|| missing(key))
    }

    /// Optional argument deserialized into any `T`: `Ok(None)` when absent or
    /// `null`, an error when present but not deserializable.
    fn optional<T: DeserializeOwned>(&self, key: &str) -> Result<Option<T>> {
        match present(self.as_value(), key) {
            None => Ok(None),
            Some(v) => T::deserialize(v).map(Some).map_err(|e| {
                MCPError::InvalidParameters(format!("Invalid parameter '{key}': {e}"))
            }),
        }
    }
}

impl ArgsExt for Value {
    fn as_value(&self) -> &Value {
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde::Deserialize;
    use serde_json::json;

    #[test]
    fn required_and_optional_strings() {
        let a = json!({"s": "x", "n": null, "i": 3});
        assert_eq!(a.required_str("s").unwrap(), "x");
        assert_eq!(a.optional_str("n").unwrap(), None);
        assert_eq!(a.optional_str("absent").unwrap(), None);
        let e = a.required_str("absent").unwrap_err().to_string();
        assert!(e.contains("Missing required parameter: absent"), "{e}");
        let e = a.required_str("i").unwrap_err().to_string();
        assert!(
            e.contains("Invalid parameter 'i': expected a string"),
            "{e}"
        );
    }

    #[test]
    fn numeric_accessors_are_strict() {
        let a = json!({"neg": -2, "pos": 7, "f": 1.5, "b": true});
        assert_eq!(a.required_i64("neg").unwrap(), -2);
        assert!(a.required_u64("neg").is_err());
        assert_eq!(a.required_u64("pos").unwrap(), 7);
        assert_eq!(a.required_f64("pos").unwrap(), 7.0);
        assert_eq!(a.required_f64("f").unwrap(), 1.5);
        assert!(a.required_i64("f").is_err());
        assert!(a.required_bool("b").unwrap());
        assert!(a.optional_bool("pos").is_err());
        assert_eq!(a.optional_i64("missing").unwrap(), None);
    }

    #[test]
    fn generic_accessors() {
        let a = json!({"tags": ["a", "b"], "bad": [1]});
        let tags: Vec<String> = a.required("tags").unwrap();
        assert_eq!(tags, vec!["a", "b"]);
        let none: Option<Vec<String>> = a.optional("nope").unwrap();
        assert!(none.is_none());
        let e = a.required::<Vec<String>>("bad").unwrap_err().to_string();
        assert!(e.contains("Invalid parameter 'bad'"), "{e}");
    }

    #[test]
    fn accessors_on_non_object_args() {
        // A client may send `null` or even a non-object; nothing panics.
        assert!(Value::Null.required_str("x").is_err());
        assert_eq!(json!([1, 2]).optional_u64("x").unwrap(), None);
    }

    #[derive(Debug, Deserialize)]
    struct Opts {
        #[serde(default)]
        verbose: bool,
    }

    #[test]
    fn parse_args_treats_null_as_empty_object() {
        let o: Opts = parse_args(Value::Null).unwrap();
        assert!(!o.verbose);
        let e = parse_args::<Opts>(json!({"verbose": "yes"})).unwrap_err();
        assert!(matches!(e, MCPError::InvalidParameters(_)));
    }
}
