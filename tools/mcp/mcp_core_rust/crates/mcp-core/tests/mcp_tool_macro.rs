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
