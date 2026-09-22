//! Tool trait and related types for MCP servers.

use async_trait::async_trait;
use futures::FutureExt;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use std::panic::AssertUnwindSafe;
use std::sync::Arc;
use tracing::error;

use crate::error::{MCPError, Result};

/// Content types that can be returned from a tool
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum Content {
    /// Text content
    Text {
        /// The text content
        text: String,
    },
    /// Image content (base64 encoded)
    Image {
        /// Base64 encoded image data
        data: String,
        /// MIME type of the image
        #[serde(rename = "mimeType")]
        mime_type: String,
    },
    /// Reference to a resource the client can fetch.
    ///
    /// Sent to MCP clients as a `resource_link` content block whose `name` is
    /// the last path segment of `uri`.
    Resource {
        /// URI of the resource
        uri: String,
        /// MIME type of the resource
        #[serde(rename = "mimeType")]
        mime_type: String,
    },
}

impl Content {
    /// Create text content
    pub fn text(text: impl Into<String>) -> Self {
        Self::Text { text: text.into() }
    }

    /// Create text content from a serializable value (JSON formatted)
    pub fn json<T: Serialize>(value: &T) -> Result<Self> {
        let text = serde_json::to_string_pretty(value)?;
        Ok(Self::text(text))
    }

    /// Create image content from already base64-encoded data.
    pub fn image(base64_data: impl Into<String>, mime_type: impl Into<String>) -> Self {
        Self::Image {
            data: base64_data.into(),
            mime_type: mime_type.into(),
        }
    }

    /// Create image content from raw bytes (base64-encodes them).
    ///
    /// ```
    /// use mcp_core::Content;
    /// let c = Content::image_bytes(b"hi", "image/png");
    /// assert_eq!(c, Content::image("aGk=", "image/png"));
    /// ```
    pub fn image_bytes(bytes: &[u8], mime_type: impl Into<String>) -> Self {
        Self::image(base64_encode(bytes), mime_type)
    }

    /// Create a resource reference (sent as an MCP `resource_link`).
    pub fn resource(uri: impl Into<String>, mime_type: impl Into<String>) -> Self {
        Self::Resource {
            uri: uri.into(),
            mime_type: mime_type.into(),
        }
    }

    /// The text of a [`Content::Text`] block, `None` for other kinds.
    pub fn as_text(&self) -> Option<&str> {
        match self {
            Self::Text { text } => Some(text),
            _ => None,
        }
    }
}

/// Result of a tool execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolResult {
    /// Content returned by the tool
    pub content: Vec<Content>,
    /// Whether the result represents an error
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    #[serde(rename = "isError")]
    pub is_error: bool,
}

impl ToolResult {
    /// Create a successful result with text content
    pub fn text(text: impl Into<String>) -> Self {
        Self {
            content: vec![Content::text(text)],
            is_error: false,
        }
    }

    /// Create a successful result with JSON content
    pub fn json<T: Serialize>(value: &T) -> Result<Self> {
        Ok(Self {
            content: vec![Content::json(value)?],
            is_error: false,
        })
    }

    /// Create an error result
    pub fn error(message: impl Into<String>) -> Self {
        Self {
            content: vec![Content::text(message)],
            is_error: true,
        }
    }

    /// Create an error result whose body is a JSON document (e.g. a structured
    /// `{"status": "error", ...}` payload the model can inspect).
    pub fn json_error<T: Serialize>(value: &T) -> Result<Self> {
        Ok(Self {
            content: vec![Content::json(value)?],
            is_error: true,
        })
    }

    /// Create a result with multiple content items
    pub fn with_content(content: Vec<Content>) -> Self {
        Self {
            content,
            is_error: false,
        }
    }

    /// Text of the first [`Content::Text`] block, if any.
    pub fn first_text(&self) -> Option<&str> {
        self.content.iter().find_map(Content::as_text)
    }

    /// All text blocks concatenated (non-text blocks are skipped). Mostly
    /// useful in tests.
    pub fn text_content(&self) -> String {
        self.content.iter().filter_map(Content::as_text).collect()
    }
}

/// Tool schema information for MCP protocol
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolSchema {
    /// Tool name
    pub name: String,
    /// Tool description
    pub description: String,
    /// JSON Schema for input parameters
    #[serde(rename = "inputSchema")]
    pub input_schema: Value,
}

/// Optional behavioural hints about a tool (MCP `ToolAnnotations`).
///
/// All fields are hints for the client UI and the model; clients must not rely
/// on them for security decisions.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ToolAnnotations {
    /// Human-readable title
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub title: Option<String>,
    /// The tool does not modify its environment
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub read_only_hint: Option<bool>,
    /// The tool may perform destructive updates (meaningful when not read-only)
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub destructive_hint: Option<bool>,
    /// Repeated calls with the same arguments have no additional effect
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub idempotent_hint: Option<bool>,
    /// The tool interacts with an open world of external entities
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub open_world_hint: Option<bool>,
}

impl ToolAnnotations {
    /// Annotations for a tool that only reads state.
    pub fn read_only() -> Self {
        Self {
            read_only_hint: Some(true),
            ..Self::default()
        }
    }

    /// Annotations for a tool that may destroy or overwrite data.
    pub fn destructive() -> Self {
        Self {
            read_only_hint: Some(false),
            destructive_hint: Some(true),
            ..Self::default()
        }
    }
}

/// A single MCP tool that can be executed.
///
/// # Errors
///
/// Returning `Err` from [`execute`](Tool::execute) is reported to the client as
/// a tool execution error (`isError: true` with the error text), which lets the
/// model read the message and retry. Use [`MCPError::InvalidParameters`] for bad
/// arguments. [`crate::args`] has typed helpers that produce those errors.
///
/// # Panic boundary and interior state
///
/// `tools/call` runs [`Tool::execute`] inside a `catch_unwind` boundary
/// (see [`ToolRegistry::call`]), so a panic becomes an `isError` result rather
/// than crashing the server. One caveat: a panic that unwinds while a
/// `std::sync::Mutex`/`RwLock` in the tool's state is locked **poisons** that
/// lock, so every later `.lock()` returns `PoisonError` and the tool degrades
/// to permanent failure. Prefer poison-free primitives for shared tool state:
/// `tokio::sync::Mutex`/`RwLock` (used by the servers in this repo) or the
/// `std::sync::atomic` types.
///
/// # Cancellation
///
/// Over STDIO, a client `notifications/cancelled` drops the `execute` future at
/// its next `.await`. Tools that spawn detached work should not assume they run
/// to completion.
#[async_trait]
pub trait Tool: Send + Sync {
    /// Get the tool's unique name
    fn name(&self) -> &str;

    /// Get the tool's description
    fn description(&self) -> &str;

    /// Get the JSON Schema for the tool's parameters
    fn schema(&self) -> Value;

    /// Execute the tool with the given arguments
    async fn execute(&self, args: Value) -> Result<ToolResult>;

    /// Get the full tool schema for MCP protocol
    fn tool_schema(&self) -> ToolSchema {
        ToolSchema {
            name: self.name().to_string(),
            description: self.description().to_string(),
            input_schema: self.schema(),
        }
    }

    /// Optional human-readable display name (MCP `title`). Defaults to none.
    fn title(&self) -> Option<&str> {
        None
    }

    /// Optional behavioural hints (MCP `annotations`). Defaults to none.
    fn annotations(&self) -> Option<ToolAnnotations> {
        None
    }
}

/// Type alias for a boxed tool
pub type BoxedTool = Arc<dyn Tool>;

/// Registry for managing MCP tools.
///
/// Tools are kept sorted by name, so listings are deterministic across runs
/// (which keeps `tools/list` output stable for client-side prompt caching).
#[derive(Default, Clone)]
pub struct ToolRegistry {
    tools: BTreeMap<String, BoxedTool>,
}

impl std::fmt::Debug for ToolRegistry {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ToolRegistry")
            .field("tools", &self.names())
            .finish()
    }
}

impl ToolRegistry {
    /// Create a new empty tool registry
    pub fn new() -> Self {
        Self::default()
    }

    /// Register a tool in the registry.
    ///
    /// A tool with the same name replaces the earlier registration (a warning
    /// is logged, since this is almost always a copy-paste mistake).
    pub fn register<T: Tool + 'static>(&mut self, tool: T) {
        self.register_boxed(Arc::new(tool));
    }

    /// Register a boxed tool in the registry
    pub fn register_boxed(&mut self, tool: BoxedTool) {
        let name = tool.name().to_string();
        if let Some(previous) = self.tools.insert(name, tool) {
            tracing::warn!(
                "Tool registered twice; the later registration wins: {}",
                previous.name()
            );
        }
    }

    /// Get a tool by name
    pub fn get(&self, name: &str) -> Option<&BoxedTool> {
        self.tools.get(name)
    }

    /// List all registered tools (sorted by name)
    pub fn list(&self) -> Vec<ToolSchema> {
        self.tools.values().map(|t| t.tool_schema()).collect()
    }

    /// Get tool names (sorted)
    pub fn names(&self) -> Vec<&str> {
        self.tools.keys().map(String::as_str).collect()
    }

    /// Iterate over the registered tools in name order.
    pub fn iter(&self) -> impl Iterator<Item = &BoxedTool> {
        self.tools.values()
    }

    /// Check if a tool exists
    pub fn contains(&self, name: &str) -> bool {
        self.tools.contains_key(name)
    }

    /// Get the number of registered tools
    pub fn len(&self) -> usize {
        self.tools.len()
    }

    /// Check if the registry is empty
    pub fn is_empty(&self) -> bool {
        self.tools.is_empty()
    }

    /// Execute a tool by name inside a panic boundary.
    ///
    /// - Unknown name: `Err(MCPError::ToolNotFound)`.
    /// - The tool returns `Err`: that error is passed through unchanged.
    /// - The tool panics: the panic is caught, logged, and turned into an
    ///   `Ok` error result (`is_error: true`) so the caller keeps running.
    ///
    /// Every transport (JSON-RPC, simple HTTP API, REST) goes through this.
    pub async fn call(&self, name: &str, args: Value) -> Result<ToolResult> {
        let tool = self
            .get(name)
            .ok_or_else(|| MCPError::ToolNotFound(name.to_string()))?;
        call_guarded(tool.as_ref(), args).await
    }
}

/// Run `tool.execute(args)`, converting a panic into an error [`ToolResult`].
pub(crate) async fn call_guarded(tool: &dyn Tool, args: Value) -> Result<ToolResult> {
    // A buggy tool that panics on malformed/untrusted arguments must not take
    // down the whole server (or the connection task). The panic is converted
    // into an MCP tool error result (`isError: true`), which is the
    // spec-recommended way to surface execution failures.
    match AssertUnwindSafe(tool.execute(args)).catch_unwind().await {
        Ok(result) => result,
        Err(panic) => {
            let msg = panic_message(panic.as_ref());
            error!("Tool '{}' panicked during execution: {}", tool.name(), msg);
            Ok(ToolResult::error(format!(
                "Tool '{}' panicked during execution: {}",
                tool.name(),
                msg
            )))
        },
    }
}

/// Extract a human-readable message from a caught panic payload.
fn panic_message(payload: &(dyn std::any::Any + Send)) -> String {
    if let Some(s) = payload.downcast_ref::<&str>() {
        (*s).to_string()
    } else if let Some(s) = payload.downcast_ref::<String>() {
        s.clone()
    } else {
        "unknown panic".to_string()
    }
}

/// Standard (RFC 4648, padded) base64 encoding.
pub(crate) fn base64_encode(bytes: &[u8]) -> String {
    const ALPHABET: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::with_capacity(bytes.len().div_ceil(3) * 4);
    for chunk in bytes.chunks(3) {
        let b = [
            chunk[0],
            chunk.get(1).copied().unwrap_or(0),
            chunk.get(2).copied().unwrap_or(0),
        ];
        let n = (u32::from(b[0]) << 16) | (u32::from(b[1]) << 8) | u32::from(b[2]);
        let sextet = |shift: u32| char::from(ALPHABET[((n >> shift) & 0x3f) as usize]);
        out.push(sextet(18));
        out.push(sextet(12));
        out.push(if chunk.len() > 1 { sextet(6) } else { '=' });
        out.push(if chunk.len() > 2 { sextet(0) } else { '=' });
    }
    out
}

/// Builder for creating tools with closures (useful for simple tools)
pub struct FnTool<F>
where
    F: Fn(Value) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<ToolResult>> + Send>>
        + Send
        + Sync,
{
    name: String,
    description: String,
    schema: Value,
    handler: F,
}

impl<F> FnTool<F>
where
    F: Fn(Value) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<ToolResult>> + Send>>
        + Send
        + Sync,
{
    /// Create a new function-based tool
    pub fn new(
        name: impl Into<String>,
        description: impl Into<String>,
        schema: Value,
        handler: F,
    ) -> Self {
        Self {
            name: name.into(),
            description: description.into(),
            schema,
            handler,
        }
    }
}

#[async_trait]
impl<F> Tool for FnTool<F>
where
    F: Fn(Value) -> std::pin::Pin<Box<dyn std::future::Future<Output = Result<ToolResult>> + Send>>
        + Send
        + Sync,
{
    fn name(&self) -> &str {
        &self.name
    }

    fn description(&self) -> &str {
        &self.description
    }

    fn schema(&self) -> Value {
        self.schema.clone()
    }

    async fn execute(&self, args: Value) -> Result<ToolResult> {
        (self.handler)(args).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    struct EchoTool;

    #[async_trait]
    impl Tool for EchoTool {
        fn name(&self) -> &str {
            "echo"
        }

        fn description(&self) -> &str {
            "Echo the input message"
        }

        fn schema(&self) -> Value {
            json!({
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo"
                    }
                },
                "required": ["message"]
            })
        }

        async fn execute(&self, args: Value) -> Result<ToolResult> {
            let message = args
                .get("message")
                .and_then(|v| v.as_str())
                .unwrap_or("no message");
            Ok(ToolResult::text(format!("Echo: {message}")))
        }
    }

    struct Named(&'static str);

    #[async_trait]
    impl Tool for Named {
        fn name(&self) -> &str {
            self.0
        }
        fn description(&self) -> &str {
            ""
        }
        fn schema(&self) -> Value {
            json!({"type": "object"})
        }
        async fn execute(&self, _args: Value) -> Result<ToolResult> {
            if self.0 == "panics" {
                panic!("kaboom");
            }
            Err(MCPError::invalid_params("nope"))
        }
    }

    #[test]
    fn test_tool_registry() {
        let mut registry = ToolRegistry::new();
        registry.register(EchoTool);

        assert!(registry.contains("echo"));
        assert_eq!(registry.len(), 1);

        let tools = registry.list();
        assert_eq!(tools.len(), 1);
        assert_eq!(tools[0].name, "echo");
    }

    #[test]
    fn registry_listing_is_sorted() {
        let mut registry = ToolRegistry::new();
        for n in ["zeta", "alpha", "mid"] {
            registry.register(Named(n));
        }
        assert_eq!(registry.names(), vec!["alpha", "mid", "zeta"]);
        let listed: Vec<_> = registry.list().into_iter().map(|t| t.name).collect();
        assert_eq!(listed, vec!["alpha", "mid", "zeta"]);
        assert_eq!(registry.iter().count(), 3);
    }

    #[test]
    fn duplicate_registration_replaces() {
        let mut registry = ToolRegistry::new();
        registry.register(Named("a"));
        registry.register(Named("a"));
        assert_eq!(registry.len(), 1);
    }

    #[tokio::test]
    async fn test_tool_execution() {
        let tool = EchoTool;
        let result = tool.execute(json!({"message": "hello"})).await.unwrap();

        assert!(!result.is_error);
        assert_eq!(result.content.len(), 1);
        assert_eq!(result.first_text(), Some("Echo: hello"));
    }

    #[tokio::test]
    async fn registry_call_handles_missing_error_and_panic() {
        let mut registry = ToolRegistry::new();
        registry.register(Named("errs"));
        registry.register(Named("panics"));

        let missing = registry.call("missing", json!({})).await.unwrap_err();
        assert!(matches!(missing, MCPError::ToolNotFound(_)));

        let err = registry.call("errs", json!({})).await.unwrap_err();
        assert!(matches!(err, MCPError::InvalidParameters(_)));

        let panicked = registry.call("panics", json!({})).await.unwrap();
        assert!(panicked.is_error);
        assert!(panicked.text_content().contains("kaboom"));
    }

    #[test]
    fn base64_matches_rfc4648_vectors() {
        let cases: [(&[u8], &str); 7] = [
            (b"", ""),
            (b"f", "Zg=="),
            (b"fo", "Zm8="),
            (b"foo", "Zm9v"),
            (b"foob", "Zm9vYg=="),
            (b"fooba", "Zm9vYmE="),
            (b"foobar", "Zm9vYmFy"),
        ];
        for (input, expected) in cases {
            assert_eq!(base64_encode(input), expected);
        }
        assert_eq!(base64_encode(&[0xff, 0xfe, 0xfd]), "//79");
    }

    #[test]
    fn content_helpers() {
        assert_eq!(Content::text("a").as_text(), Some("a"));
        assert_eq!(Content::image("x", "image/png").as_text(), None);
        let r = ToolResult::with_content(vec![
            Content::text("a"),
            Content::resource("file:///x", "text/plain"),
            Content::text("b"),
        ]);
        assert_eq!(r.first_text(), Some("a"));
        assert_eq!(r.text_content(), "ab");
        let e = ToolResult::json_error(&json!({"status": "error"})).unwrap();
        assert!(e.is_error);
    }

    #[test]
    fn annotations_serialize_camel_case_and_skip_none() {
        let v = serde_json::to_value(ToolAnnotations::read_only()).unwrap();
        assert_eq!(v, json!({"readOnlyHint": true}));
        let v = serde_json::to_value(ToolAnnotations::destructive()).unwrap();
        assert_eq!(v, json!({"readOnlyHint": false, "destructiveHint": true}));
    }
}
