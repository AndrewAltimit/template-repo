//! OpenRouter API agent for PR reviews.
//!
//! Calls the OpenRouter API directly (no CLI dependency) for code reviews.
//! Uses OPENROUTER_API_KEY for authentication.
//!
//! Optional tuning:
//! - `OPENROUTER_MAX_TOKENS`: completion budget (default 32768). Reasoning
//!   models spend part of this on hidden reasoning before writing content.
//! - `OPENROUTER_REASONING_EFFORT`: `minimal`/`low`/`medium`/`high`, or
//!   `none` (aliases `off`, `disabled`) to omit the `reasoning` param
//!   entirely (default `medium`).

use std::time::Duration;

use async_trait::async_trait;

use super::ReviewAgent;
use crate::error::{Error, Result};
use crate::utils::truncate_str;

/// Default model for OpenRouter reviews
const DEFAULT_MODEL: &str = "particle-ai/particle-1";

/// OpenRouter API endpoint
const OPENROUTER_API_URL: &str = "https://openrouter.ai/api/v1/chat/completions";

/// Overall request timeout (large reviews can take several minutes).
const REQUEST_TIMEOUT: Duration = Duration::from_secs(600);

/// Default completion budget. Reasoning models (particle-1 included) count
/// hidden reasoning tokens against `max_tokens`, so this must leave plenty of
/// headroom beyond the review text itself.
const DEFAULT_MAX_TOKENS: u32 = 32_768;

/// Default reasoning effort sent via OpenRouter's unified `reasoning` param.
const DEFAULT_REASONING_EFFORT: &str = "medium";

/// OpenRouter API agent for PR reviews
///
/// Calls the OpenRouter chat completions API directly, avoiding the need for
/// any CLI tool installation. Only requires OPENROUTER_API_KEY env var.
pub struct OpenRouterAgent {
    api_key: Option<String>,
    model: String,
    max_tokens: u32,
    /// `None` omits the `reasoning` param (OPENROUTER_REASONING_EFFORT=none).
    reasoning_effort: Option<String>,
    client: reqwest::Client,
}

impl OpenRouterAgent {
    /// Create a new OpenRouter agent
    pub fn new() -> Self {
        let api_key = std::env::var("OPENROUTER_API_KEY")
            .ok()
            .filter(|k| !k.trim().is_empty());
        if api_key.is_none() {
            tracing::debug!("OPENROUTER_API_KEY not set or empty");
        }

        let client = reqwest::Client::builder()
            .timeout(REQUEST_TIMEOUT)
            .connect_timeout(Duration::from_secs(30))
            .build()
            .unwrap_or_else(|_| reqwest::Client::new());

        Self {
            api_key,
            model: DEFAULT_MODEL.to_string(),
            max_tokens: max_tokens_from(std::env::var("OPENROUTER_MAX_TOKENS").ok().as_deref()),
            reasoning_effort: reasoning_effort_from(
                std::env::var("OPENROUTER_REASONING_EFFORT").ok().as_deref(),
            ),
            client,
        }
    }

    /// Create with custom model
    pub fn with_model(model: String) -> Self {
        let mut agent = Self::new();
        tracing::info!("Using OpenRouter model: {}", model);
        agent.model = model;
        agent
    }

    fn transient(detail: String) -> Error {
        Error::AgentExecutionFailed {
            name: "openrouter".to_string(),
            exit_code: 6,
            stdout: String::new(),
            stderr: format!("service unavailable (transient): {}", detail),
        }
    }

    /// Build the chat-completions request body.
    fn request_body(&self, prompt: &str) -> serde_json::Value {
        let mut body = serde_json::json!({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
            "temperature": 0.2
        });
        if let Some(effort) = &self.reasoning_effort {
            // `exclude` keeps the unused reasoning text out of the response
            // body; reasoning tokens still count against `max_tokens`.
            body["reasoning"] = serde_json::json!({"effort": effort, "exclude": true});
        }
        body
    }

    /// Call the OpenRouter API
    async fn call_api(&self, prompt: &str) -> Result<String> {
        let api_key = self
            .api_key
            .as_ref()
            .ok_or_else(|| Error::EnvNotSet("OPENROUTER_API_KEY".to_string()))?;

        tracing::info!(
            "Calling OpenRouter API with model: {} (max_tokens: {}, reasoning effort: {})",
            self.model,
            self.max_tokens,
            self.reasoning_effort
                .as_deref()
                .unwrap_or("provider default")
        );

        let request_body = self.request_body(prompt);

        let response = self
            .client
            .post(OPENROUTER_API_URL)
            .bearer_auth(api_key)
            .header(
                "HTTP-Referer",
                "https://github.com/AndrewAltimit/template-repo",
            )
            .header("X-Title", "PR Review Agent")
            .json(&request_body)
            .send()
            .await
            .map_err(|e| {
                if e.is_connect() || e.is_timeout() {
                    Self::transient(e.to_string())
                } else {
                    Error::Config(format!("OpenRouter API request failed: {}", e))
                }
            })?;

        let status = response.status();
        let body = response
            .text()
            .await
            .map_err(|e| Self::transient(format!("failed to read response body: {}", e)))?;

        if !status.is_success() {
            let snippet = truncate_str(body.trim(), 500);
            if matches!(status.as_u16(), 429 | 500 | 502 | 503 | 504) {
                return Err(Self::transient(format!("HTTP {} - {}", status, snippet)));
            }
            return Err(Error::Config(format!(
                "OpenRouter API returned HTTP {}: {}",
                status, snippet
            )));
        }

        extract_content(&body, self.max_tokens)
    }
}

/// Parse OPENROUTER_MAX_TOKENS, falling back to the default on bad input.
fn max_tokens_from(raw: Option<&str>) -> u32 {
    match raw.map(str::trim).filter(|v| !v.is_empty()) {
        None => DEFAULT_MAX_TOKENS,
        Some(v) => match v.parse::<u32>() {
            Ok(n) if (1..=1_000_000).contains(&n) => n,
            _ => {
                tracing::warn!(
                    "OPENROUTER_MAX_TOKENS={:?} is invalid; using {}",
                    v,
                    DEFAULT_MAX_TOKENS
                );
                DEFAULT_MAX_TOKENS
            },
        },
    }
}

/// Parse OPENROUTER_REASONING_EFFORT. `none`/`off`/`disabled` omits the param.
fn reasoning_effort_from(raw: Option<&str>) -> Option<String> {
    let v = raw
        .map(|v| v.trim().to_ascii_lowercase())
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| DEFAULT_REASONING_EFFORT.to_string());
    match v.as_str() {
        "none" | "off" | "disabled" => None,
        "minimal" | "low" | "medium" | "high" => Some(v),
        other => {
            tracing::warn!(
                "OPENROUTER_REASONING_EFFORT={:?} is invalid; using {}",
                other,
                DEFAULT_REASONING_EFFORT
            );
            Some(DEFAULT_REASONING_EFFORT.to_string())
        },
    }
}

/// Extract the assistant message from a chat-completions response body.
///
/// Handles reasoning-model responses: `content` may be `null` (when the
/// completion budget ran out during reasoning) or an array of typed parts,
/// and `finish_reason: "length"` signals truncation.
fn extract_content(body: &str, max_tokens: u32) -> Result<String> {
    // OpenRouter pads slow responses with whitespace keep-alives; trim them so
    // error snippets show the actual JSON.
    let body = body.trim();
    let json: serde_json::Value = serde_json::from_str(body)
        .map_err(|e| Error::Config(format!("Failed to parse OpenRouter response: {}", e)))?;

    if let Some(err) = json.get("error") {
        let message = err
            .get("message")
            .and_then(|m| m.as_str())
            .unwrap_or("unknown error");
        return Err(Error::Config(format!("OpenRouter API error: {}", message)));
    }

    let unexpected = || {
        Error::Config(format!(
            "Unexpected OpenRouter response format: {}",
            truncate_str(body, 500)
        ))
    };

    let choice = json.pointer("/choices/0").ok_or_else(unexpected)?;
    let message = choice.get("message").ok_or_else(unexpected)?;
    let finish_reason = choice
        .get("finish_reason")
        .and_then(|f| f.as_str())
        .unwrap_or("");
    let truncated = finish_reason == "length";

    let content = match message.get("content") {
        Some(serde_json::Value::String(s)) => s.clone(),
        // Some providers return content as an array of typed parts. Keep only
        // text parts (or untyped ones) so reasoning/thinking parts that also
        // carry a `text` field never leak into the review.
        Some(serde_json::Value::Array(parts)) => parts
            .iter()
            .filter(|p| match p.get("type") {
                None => true,
                Some(serde_json::Value::String(t)) => t == "text",
                Some(_) => false,
            })
            .filter_map(|p| p.get("text").and_then(|t| t.as_str()))
            .collect(),
        // `null` content is expected when a reasoning model runs out of budget.
        Some(serde_json::Value::Null) | None => String::new(),
        Some(_) => return Err(unexpected()),
    };

    // Actual usage, reported alongside the configured budget in case the
    // provider clamped `max_tokens` below what we requested.
    let usage_u64 = |ptr: &str| json.pointer(ptr).and_then(|r| r.as_u64());
    let usage = |ptr: &str| usage_u64(ptr).map_or_else(|| "unknown".to_string(), |r| r.to_string());

    if content.trim().is_empty() {
        if truncated {
            return Err(Error::Config(format!(
                "OpenRouter model hit max_tokens (requested {}) before writing any review \
                 text (completion tokens: {}, reasoning tokens: {}); raise \
                 OPENROUTER_MAX_TOKENS or lower OPENROUTER_REASONING_EFFORT",
                max_tokens,
                usage("/usage/completion_tokens"),
                usage("/usage/completion_tokens_details/reasoning_tokens")
            )));
        }
        if let Some(refusal) = message
            .get("refusal")
            .and_then(|r| r.as_str())
            .filter(|r| !r.trim().is_empty())
        {
            return Err(Error::Config(format!(
                "OpenRouter model refused: {}",
                truncate_str(refusal, 500)
            )));
        }
        return Err(Error::Config(format!(
            "OpenRouter returned empty content (finish_reason: {:?}): {}",
            finish_reason,
            truncate_str(body, 500)
        )));
    }

    if truncated {
        // Prefer what the provider actually allowed over what we requested.
        let limit = usage_u64("/usage/completion_tokens").unwrap_or(u64::from(max_tokens));
        tracing::warn!(
            "OpenRouter review was cut off at its output limit ({} tokens, requested {}); \
             returning partial output",
            limit,
            max_tokens
        );
        // Note goes first so readers of the posted comment see the review is
        // incomplete before reading sections that may be cut short.
        return Ok(format!(
            "> **Review truncated:** the model hit its output limit ({} tokens), so later \
             sections may be missing.\n\n{}",
            limit,
            close_open_fence(content.trim_end())
        ));
    }

    Ok(content)
}

/// Close a fenced code block left open by truncation, so it does not swallow
/// the footer the reviewer appends after the agent output.
fn close_open_fence(text: &str) -> String {
    /// Leading run of ` or ~ (length >= 3) on a line, i.e. a fence marker,
    /// plus whether anything (an info string) follows the run.
    fn fence(line: &str) -> Option<(char, usize, bool)> {
        let t = line.trim_start();
        let c = t.chars().next().filter(|c| *c == '`' || *c == '~')?;
        let n = t.chars().take_while(|x| *x == c).count();
        let has_info = !t[n * c.len_utf8()..].trim().is_empty();
        (n >= 3).then_some((c, n, has_info))
    }

    // CommonMark: a fence closes on the same character with a run at least
    // as long as the opener and nothing after it (a closer has no info string).
    let mut open: Option<(char, usize)> = None;
    for line in text.lines() {
        match (open, fence(line)) {
            (None, Some((c, n, _))) => open = Some((c, n)),
            (Some((c, n)), Some((c2, n2, false))) if c == c2 && n2 >= n => open = None,
            _ => {},
        }
    }
    match open {
        Some((c, n)) => format!("{text}\n{}", c.to_string().repeat(n)),
        None => text.to_string(),
    }
}

impl Default for OpenRouterAgent {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl ReviewAgent for OpenRouterAgent {
    fn name(&self) -> &str {
        "openrouter"
    }

    fn model(&self) -> &str {
        &self.model
    }

    async fn is_available(&self) -> bool {
        self.api_key.is_some()
    }

    async fn review(&self, prompt: &str) -> Result<String> {
        self.call_api(prompt).await
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_new_without_api_key() {
        let agent = OpenRouterAgent::new();
        assert_eq!(agent.model, DEFAULT_MODEL);
    }

    #[test]
    fn test_with_model() {
        let agent = OpenRouterAgent::with_model("test/model".to_string());
        assert_eq!(agent.model, "test/model");
    }

    #[test]
    fn test_extract_content() {
        let ok = r#"{"choices":[{"message":{"content":"Looks good"}}]}"#;
        assert_eq!(extract_content(ok, 100).unwrap(), "Looks good");

        let empty = r#"{"choices":[{"message":{"content":"  "}}]}"#;
        assert!(extract_content(empty, 100).is_err());

        let err = r#"{"error":{"message":"bad key"}}"#;
        assert!(
            extract_content(err, 100)
                .unwrap_err()
                .to_string()
                .contains("bad key")
        );

        assert!(extract_content("<html>", 100).is_err());
        assert!(extract_content(r#"{"choices":[]}"#, 100).is_err());
        assert!(extract_content(r#"{"choices":[{"message":{"content":5}}]}"#, 100).is_err());
    }

    #[test]
    fn test_extract_content_reasoning_budget_exhausted() {
        // Shape observed from particle-ai/particle-1 (Oct 2026): leading
        // whitespace keep-alives, null content, reasoning text, finish=length.
        let body = concat!(
            "\n\n   \n\n",
            r#"{"id":"gen-1","object":"chat.completion","choices":[{"index":0,"#,
            r#""finish_reason":"length","native_finish_reason":"length","#,
            r#""message":{"role":"assistant","content":null,"refusal":null,"#,
            r#""reasoning":"Let me analyze the diff carefully for bugs."}}],"#,
            r#""usage":{"completion_tokens":4000,"#,
            r#""completion_tokens_details":{"reasoning_tokens":3990}}}"#
        );
        let msg = extract_content(body, 4096).unwrap_err().to_string();
        assert!(msg.contains("requested 4096"), "{msg}");
        assert!(msg.contains("completion tokens: 4000"), "{msg}");
        assert!(msg.contains("reasoning tokens: 3990"), "{msg}");
        assert!(msg.contains("OPENROUTER_MAX_TOKENS"), "{msg}");
    }

    #[test]
    fn test_extract_content_truncated_partial() {
        let body =
            r#"{"choices":[{"finish_reason":"length","message":{"content":"Partial review"}}]}"#;
        let out = extract_content(body, 50).unwrap();
        // Truncation note leads so it is visible at the top of the comment.
        assert!(out.starts_with("> **Review truncated:**"), "{out}");
        assert!(out.contains("(50 tokens)"), "{out}");
        assert!(out.ends_with("Partial review"), "{out}");

        // A clamped budget is reported from usage, not from the request.
        let clamped = r#"{"choices":[{"finish_reason":"length","message":{"content":"x"}}],"usage":{"completion_tokens":8192}}"#;
        let out = extract_content(clamped, 32_768).unwrap();
        assert!(out.contains("(8192 tokens)"), "{out}");

        // Output cut inside a code block gets the fence closed so the
        // reviewer's footer is not swallowed.
        let fenced = r#"{"choices":[{"finish_reason":"length","message":{"content":"Issues:\n```rust\nlet x = 1;"}}]}"#;
        let out = extract_content(fenced, 50).unwrap();
        assert!(out.ends_with("let x = 1;\n```"), "{out}");
    }

    #[test]
    fn test_close_open_fence() {
        assert_eq!(close_open_fence("a\n```\nb\n```"), "a\n```\nb\n```");
        assert_eq!(close_open_fence("a\n```py\nb"), "a\n```py\nb\n```");
        // `~~~` blocks close with `~~~`; a ``` inside one does not close it.
        assert_eq!(close_open_fence("~~~\n```\nb"), "~~~\n```\nb\n~~~");
        // A longer opener needs an equally long closer.
        assert_eq!(close_open_fence("````\n```\nb"), "````\n```\nb\n````");
        assert_eq!(close_open_fence("no fences"), "no fences");
        // A fence with an info string cannot close a block, so a nested
        // example opener leaves the outer block open.
        assert_eq!(
            close_open_fence("````md\n```rust\nlet x = 1;"),
            "````md\n```rust\nlet x = 1;\n````"
        );
        assert_eq!(
            close_open_fence("```\na\n```rust\nb"),
            "```\na\n```rust\nb\n```"
        );
        // Trailing whitespace on a closer is fine.
        assert_eq!(close_open_fence("```\na\n```  "), "```\na\n```  ");
    }

    #[test]
    fn test_extract_content_parts_and_refusal() {
        let parts = r#"{"choices":[{"finish_reason":"stop","message":{"content":[{"type":"text","text":"a"},{"type":"text","text":"b"}]}}]}"#;
        assert_eq!(extract_content(parts, 100).unwrap(), "ab");

        // Non-text parts (e.g. reasoning) are dropped even if they carry
        // `text`; untyped parts with `text` are kept.
        let mixed = r#"{"choices":[{"finish_reason":"stop","message":{"content":[{"type":"reasoning","text":"secret thoughts"},{"type":"text","text":"a"},{"text":"b"}]}}]}"#;
        assert_eq!(extract_content(mixed, 100).unwrap(), "ab");

        // A present but non-string `type` is not treated as text.
        let odd_type = r#"{"choices":[{"finish_reason":"stop","message":{"content":[{"type":5,"text":"x"},{"type":"text","text":"a"}]}}]}"#;
        assert_eq!(extract_content(odd_type, 100).unwrap(), "a");

        let refusal =
            r#"{"choices":[{"finish_reason":"stop","message":{"content":null,"refusal":"no"}}]}"#;
        assert!(
            extract_content(refusal, 100)
                .unwrap_err()
                .to_string()
                .contains("refused")
        );
    }

    #[test]
    fn test_env_parsing() {
        assert_eq!(max_tokens_from(None), DEFAULT_MAX_TOKENS);
        assert_eq!(max_tokens_from(Some(" 8000 ")), 8000);
        assert_eq!(max_tokens_from(Some("0")), DEFAULT_MAX_TOKENS);
        assert_eq!(max_tokens_from(Some("lots")), DEFAULT_MAX_TOKENS);

        assert_eq!(reasoning_effort_from(None).as_deref(), Some("medium"));
        assert_eq!(reasoning_effort_from(Some("HIGH")).as_deref(), Some("high"));
        assert_eq!(reasoning_effort_from(Some("none")), None);
        assert_eq!(
            reasoning_effort_from(Some("bogus")).as_deref(),
            Some("medium")
        );
    }

    #[test]
    fn test_request_body_reasoning() {
        let mut agent = OpenRouterAgent::with_model("m".to_string());
        agent.max_tokens = 1234;
        agent.reasoning_effort = Some("low".to_string());
        let body = agent.request_body("hi");
        assert_eq!(body["max_tokens"], 1234);
        assert_eq!(body["reasoning"]["effort"], "low");
        assert_eq!(body["reasoning"]["exclude"], true);

        agent.reasoning_effort = None;
        assert!(agent.request_body("hi").get("reasoning").is_none());
    }
}
