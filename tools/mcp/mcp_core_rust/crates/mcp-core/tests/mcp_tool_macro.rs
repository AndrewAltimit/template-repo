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
