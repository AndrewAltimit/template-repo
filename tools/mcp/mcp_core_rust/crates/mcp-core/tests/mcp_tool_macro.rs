use std::sync::Arc;
use std::sync::atomic::{AtomicI64, Ordering};

use mcp_core::tool::{Content, Tool};
use mcp_macros::mcp_tool;
use serde_json::json;

#[mcp_tool(description = "Echo the input message a number of times")]
async fn echo(
    #[mcp(description = "Message to echo")] message: String,
    #[mcp(description = "Repeat count", default = 1)] count: i64,
    #[mcp(description = "Optional suffix")] suffix: Option<String>,
) -> Result<String, anyhow::Error> {
    let mut out = message.repeat(count as usize);
    if let Some(s) = suffix {
        out.push_str(&s);
    }
    Ok(out)
}

#[mcp_tool(description = "Return the offset, defaulting to a negative value")]
async fn offset(
    #[mcp(description = "Offset to return", default = -1)] value: i64,
) -> Result<i64, anyhow::Error> {
    Ok(value)
}

fn result_text(r: &mcp_core::tool::ToolResult) -> String {
    match &r.content[0] {
        Content::Text { text } => text.clone(),
        _ => panic!("expected text content"),
    }
}

#[tokio::test]
async fn schema_marks_required_and_optional_correctly() {
    let schema = EchoTool.schema();
    let required = schema["required"].as_array().unwrap();
    // `message` is required; `count` has a default and `suffix` is Option -> optional.
    assert_eq!(required.len(), 1);
    assert_eq!(required[0], "message");
    assert_eq!(schema["properties"]["count"]["type"], "integer");
    assert_eq!(schema["properties"]["suffix"]["type"], "string");
}

#[tokio::test]
async fn uses_default_when_arg_absent() {
    let r = EchoTool.execute(json!({"message": "ab"})).await.unwrap();
    assert!(!r.is_error);
    // default count = 1, no suffix -> "ab" (JSON-encoded string)
    assert!(result_text(&r).contains("ab"));
}

#[tokio::test]
async fn deserializes_typed_args() {
    let r = EchoTool
        .execute(json!({"message": "x", "count": 3, "suffix": "!"}))
        .await
        .unwrap();
    assert!(result_text(&r).contains("xxx!"));
}

#[tokio::test]
async fn missing_required_arg_is_clean_error() {
    let err = EchoTool.execute(json!({})).await.unwrap_err();
    assert!(
        err.to_string()
            .contains("Missing required parameter: message")
    );
}

#[tokio::test]
async fn wrong_type_is_clean_error_not_panic() {
    // count should be an integer; passing a string must yield InvalidParameters,
    // not a panic.
    let err = EchoTool
        .execute(json!({"message": "x", "count": "not a number"}))
        .await
        .unwrap_err();
    assert!(err.to_string().contains("Invalid parameter 'count'"));
}

#[tokio::test]
async fn negative_literal_default_is_applied() {
    // `default = -1` parses as a unary expression, not a `Lit`; the macro must
    // accept it and preserve the negative integer JSON type.
    let r = OffsetTool.execute(json!({})).await.unwrap();
    assert!(!r.is_error);
    assert!(result_text(&r).contains("-1"));
}

// --- Stateful tools (#[mcp(state)]) -------------------------------------

/// A shared counter standing in for real injected state (a store, HTTP client,
/// job registry, ...). State types must be `Clone`.
type Counter = Arc<AtomicI64>;

#[mcp_tool(description = "Add an amount to a shared counter and return the total")]
async fn add(
    #[mcp(state)] counter: Counter,
    #[mcp(description = "Amount to add")] amount: i64,
) -> Result<i64, anyhow::Error> {
    Ok(counter.fetch_add(amount, Ordering::SeqCst) + amount)
}

#[tokio::test]
async fn state_param_is_excluded_from_schema() {
    let counter: Counter = Arc::new(AtomicI64::new(0));
    let tool = AddTool::new(counter);
    let schema = tool.schema();
    // `counter` is injected state, so only `amount` is in the schema.
    assert!(schema["properties"].get("counter").is_none());
    assert!(schema["properties"].get("amount").is_some());
    assert_eq!(schema["required"].as_array().unwrap(), &[json!("amount")]);
}

#[tokio::test]
async fn state_is_injected_and_shared_across_calls() {
    let counter: Counter = Arc::new(AtomicI64::new(0));
    let tool = AddTool::new(Arc::clone(&counter));

    let r1 = tool.execute(json!({"amount": 3})).await.unwrap();
    assert!(result_text(&r1).contains('3'));
    let r2 = tool.execute(json!({"amount": 4})).await.unwrap();
    assert!(result_text(&r2).contains('7'));
    // The injected state persisted across both calls.
    assert_eq!(counter.load(Ordering::SeqCst), 7);
}

// --- Return-type handling, docs, defaults ---------------------------------

/// Greets someone by name.
///
/// The doc comment doubles as the tool description.
#[mcp_tool]
async fn greet(
    #[mcp(description = "Who to greet")] r#type: String,
    #[mcp(description = "Page size", default = 10)] limit: Option<u32>,
) -> Result<String, std::convert::Infallible> {
    Ok(format!("hello {} (limit={limit:?})", r#type))
}

#[tokio::test]
async fn doc_comment_is_description_and_string_is_plain_text() {
    assert_eq!(
        GreetTool.description(),
        "Greets someone by name.\n\nThe doc comment doubles as the tool description."
    );
    // Raw identifiers use their plain name as the JSON key.
    let schema = GreetTool.schema();
    assert!(schema["properties"].get("type").is_some());
    assert_eq!(schema["required"], json!(["type"]));
    // Defaults are advertised in the schema, unsigned ints get a minimum.
    assert_eq!(schema["properties"]["limit"]["default"], 10);
    assert_eq!(schema["properties"]["limit"]["minimum"], 0);

    let r = GreetTool.execute(json!({"type": "bob"})).await.unwrap();
    // `Result<String, _>` is returned verbatim, not as a JSON-quoted string;
    // and `default` applies to `Option<T>` parameters too.
    assert_eq!(result_text(&r), "hello bob (limit=Some(10))");

    // Explicit null counts as absent.
    let r = GreetTool
        .execute(json!({"type": "amy", "limit": null}))
        .await
        .unwrap();
    assert_eq!(result_text(&r), "hello amy (limit=Some(10))");
}

#[mcp_tool(name = "make.image", description = "Return an image block")]
async fn make_image() -> Result<mcp_core::ToolResult, String> {
    Ok(mcp_core::ToolResult::with_content(vec![
        Content::text("here"),
        Content::image_bytes(b"png", "image/png"),
    ]))
}

#[mcp_tool(description = "Do nothing successfully")]
async fn noop() -> Result<(), String> {
    Ok(())
}

#[mcp_tool(description = "Always fails")]
async fn always_fails(#[mcp(description = "Reason")] reason: String) -> Result<i32, String> {
    Err(format!("failed because {reason}"))
}

#[tokio::test]
async fn tool_result_and_unit_returns() {
    // `name` override with a dot still yields a valid struct identifier.
    let tool = MakeImageTool;
    assert_eq!(tool.name(), "make.image");
    let r = tool.execute(json!({})).await.unwrap();
    assert_eq!(r.content.len(), 2);
    assert_eq!(r.content[1], Content::image("cG5n", "image/png"));

    let r = NoopTool.execute(json!({})).await.unwrap();
    assert_eq!(result_text(&r), "OK");
    // A tool with no parameters has an empty object schema.
    assert_eq!(
        NoopTool.schema(),
        json!({"type": "object", "properties": {}, "required": []})
    );
}

#[tokio::test]
async fn err_becomes_error_result() {
    let r = AlwaysFailsTool
        .execute(json!({"reason": "tests"}))
        .await
        .unwrap();
    assert!(r.is_error);
    assert_eq!(result_text(&r), "failed because tests");
}

#[tokio::test]
async fn macro_tools_work_through_the_protocol_handler() {
    let mut tools = mcp_core::ToolRegistry::new();
    tools.register(EchoTool);
    let handler = mcp_core::transport::MCPHandler::new("t", "1", tools);
    let resp = handler
        .handle_message(
            json!({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "echo", "arguments": {"count": 2}}}),
            None,
        )
        .await
        .unwrap();
    // Missing required argument -> tool error result the model can read.
    assert_eq!(resp["result"]["isError"], true);
    assert!(
        resp["result"]["content"][0]["text"]
            .as_str()
            .unwrap()
            .contains("Missing required parameter: message")
    );
}
