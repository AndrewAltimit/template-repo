//! Derive tool input schemas from Rust types.
//!
//! Hand-written `json!` schemas drift from the code that parses the arguments.
//! Deriving [`schemars::JsonSchema`] on the same struct you pass to
//! [`parse_args`](crate::args::parse_args) keeps the two in lock-step:
//!
//! ```
//! use mcp_core::schema::schema_for;
//! use mcp_core::schemars::{self, JsonSchema};
//! use serde::Deserialize;
//!
//! #[derive(Deserialize, JsonSchema)]
//! struct SearchArgs {
//!     /// Free-text query
//!     query: String,
//!     /// Maximum number of results
//!     limit: Option<u32>,
//! }
//!
//! let schema = schema_for::<SearchArgs>();
//! assert_eq!(schema["type"], "object");
//! assert_eq!(schema["required"], serde_json::json!(["query"]));
//! assert_eq!(schema["properties"]["query"]["description"], "Free-text query");
//! assert!(schema.get("$schema").is_none());
//! ```
//!
//! If the server crate does not depend on `schemars` directly, point the derive
//! at the re-export with `#[schemars(crate = "mcp_core::schemars")]`.

use schemars::JsonSchema;
use schemars::generate::SchemaSettings;
use serde_json::Value;

/// Generate an MCP-friendly JSON Schema for `T`.
///
/// Subschemas are inlined (no `$ref`/`definitions` for non-recursive types),
/// `Option<T>` fields are optional rather than `["T", "null"]`, and the
/// `$schema`/`title` metadata keys are dropped since MCP clients ignore them.
pub fn schema_for<T: JsonSchema>() -> Value {
    let generator = SchemaSettings::draft07()
        .with(|s| {
            s.inline_subschemas = true;
            s.meta_schema = None;
        })
        .into_generator();
    let mut value = generator.into_root_schema_for::<T>().to_value();
    // schemars 1.x always marks `Option<T>` as nullable; MCP tool arguments
    // express optionality by omission instead.
    strip_null(&mut value);
    if let Some(obj) = value.as_object_mut() {
        obj.remove("title");
        obj.remove("$schema");
        // MCP requires `inputSchema.type == "object"`; unit structs and
        // `()` produce an empty schema otherwise.
        if !obj.contains_key("type") && !obj.contains_key("$ref") {
            obj.insert("type".into(), Value::String("object".into()));
        }
    }
    value
}

/// Recursively remove the `null` alternatives schemars adds for `Option<T>`:
/// `"type": ["T", "null"]` becomes `"type": "T"`, `null` is dropped from
/// `enum` lists, and an `anyOf` wrapper with a `{"type": "null"}` branch is
/// collapsed into its remaining branch.
fn strip_null(value: &mut Value) {
    match value {
        Value::Array(items) => items.iter_mut().for_each(strip_null),
        Value::Object(obj) => {
            obj.values_mut().for_each(strip_null);
            if let Some(Value::Array(types)) = obj.get_mut("type") {
                if types.len() > 1 {
                    types.retain(|t| t != "null");
                }
                if types.len() == 1 {
                    let only = types.remove(0);
                    obj.insert("type".into(), only);
                }
            }
            if let Some(Value::Array(variants)) = obj.get_mut("enum")
                && variants.len() > 1
            {
                variants.retain(|v| !v.is_null());
            }
            let is_null_branch = |v: &Value| v.get("type").is_some_and(|t| t == "null");
            if let Some(Value::Array(branches)) = obj.get_mut("anyOf")
                && branches.len() > 1
                && branches.iter().any(is_null_branch)
            {
                branches.retain(|b| !is_null_branch(b));
                if branches.len() == 1
                    && let Some(Value::Object(inner)) = branches.pop()
                {
                    obj.remove("anyOf");
                    for (k, v) in inner {
                        obj.entry(k).or_insert(v);
                    }
                }
            }
        },
        _ => {},
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use schemars::JsonSchema;
    use serde::Deserialize;
    use serde_json::json;

    #[allow(dead_code)]
    #[derive(Deserialize, JsonSchema)]
    #[serde(rename_all = "snake_case")]
    enum Mode {
        Fast,
        Thorough,
    }

    #[allow(dead_code)]
    #[derive(Deserialize, JsonSchema)]
    struct Inner {
        x: i32,
    }

    #[allow(dead_code)]
    #[derive(Deserialize, JsonSchema)]
    struct Args {
        name: String,
        mode: Option<Mode>,
        inner: Inner,
        inner_opt: Option<Inner>,
        limit: Option<u32>,
        tags: Vec<String>,
    }

    #[test]
    fn nested_types_are_inlined() {
        let s = schema_for::<Args>();
        assert!(s.get("definitions").is_none(), "{s}");
        assert_eq!(
            s["properties"]["inner"]["properties"]["x"]["type"],
            "integer"
        );
        assert_eq!(s["properties"]["mode"]["enum"], json!(["fast", "thorough"]));
        assert_eq!(s["properties"]["mode"]["type"], "string");
        assert_eq!(
            s["properties"]["limit"],
            json!({"type": "integer", "format": "uint32", "minimum": 0})
        );
        assert!(s["properties"]["inner_opt"].get("anyOf").is_none(), "{s}");
        assert_eq!(s["properties"]["inner_opt"]["type"], "object");
        assert_eq!(s["properties"]["tags"]["items"]["type"], "string");
        let mut required: Vec<_> = s["required"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| v.as_str().unwrap().to_string())
            .collect();
        required.sort();
        assert_eq!(required, vec!["inner", "name", "tags"]);
    }

    #[allow(dead_code)]
    #[derive(Deserialize, JsonSchema)]
    struct Empty {}

    #[test]
    fn empty_struct_is_object() {
        let s = schema_for::<Empty>();
        assert_eq!(s["type"], "object");
    }
}
