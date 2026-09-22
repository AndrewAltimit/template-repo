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
use schemars::r#gen::SchemaSettings;
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
            s.option_add_null_type = false;
            s.option_nullable = false;
            s.meta_schema = None;
        })
        .into_generator();
    let root = generator.into_root_schema_for::<T>();
    let mut value =
        serde_json::to_value(root).unwrap_or_else(|_| Value::Object(Default::default()));
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
