//! AWS Bedrock model provider.
//!
//! Implements the Model trait for AWS Bedrock's Converse API,
//! supporting streaming, tool use, and guardrails.

use std::collections::HashMap;

use async_trait::async_trait;
use aws_sdk_bedrockruntime::{
    types::{
        ContentBlock as BedrockContentBlock, ConversationRole,
        ConverseOutput as ConverseOutputType, ConverseStreamOutput as StreamEvent,
        InferenceConfiguration, Message as BedrockMessage, StopReason as BedrockStopReason,
        SystemContentBlock, Tool, ToolConfiguration, ToolInputSchema, ToolResultBlock,
        ToolResultContentBlock as BedrockToolResultContentBlock,
        ToolResultStatus as BedrockToolResultStatus, ToolSpecification, ToolUseBlock,
    },
    Client,
};
// Note: Not using StreamExt to avoid conflicts with Option::map
use tracing::{debug, error, instrument};

use strands_agent::model::{
    InferenceConfig, Model, ModelRequest, ModelResponse, ModelStream, ModelStreamChunk,
};
use strands_core::{
    ContentBlock, Message, Result, Role, StopReason, StrandsError, ToolResultContentBlock,
    ToolResultStatus, ToolUseContent, Usage,
};

/// AWS Bedrock model provider.
pub struct BedrockModel {
    /// Bedrock runtime client
    client: Client,

    /// Model ID (e.g., "anthropic.claude-sonnet-4-20250514")
    model_id: String,

    /// AWS region (stored for potential future use in logging/debugging)
    #[allow(dead_code)]
    region: String,
}

impl BedrockModel {
    /// Create a new Bedrock model from existing config.
    pub async fn new(model_id: impl Into<String>, region: impl Into<String>) -> Self {
        let region = region.into();
        let config = aws_config::defaults(aws_config::BehaviorVersion::latest())
            .region(aws_config::Region::new(region.clone()))
            .load()
            .await;

        Self {
            client: Client::new(&config),
            model_id: model_id.into(),
            region,
        }
    }

    /// Create with a custom AWS config.
    pub fn with_config(
        config: &aws_config::SdkConfig,
        model_id: impl Into<String>,
        region: impl Into<String>,
    ) -> Self {
        Self {
            client: Client::new(config),
            model_id: model_id.into(),
            region: region.into(),
        }
    }

    /// Create with an existing client.
    pub fn with_client(
        client: Client,
        model_id: impl Into<String>,
        region: impl Into<String>,
    ) -> Self {
        Self {
            client,
            model_id: model_id.into(),
            region: region.into(),
        }
    }

    // Conversion helpers

    fn convert_role(role: Role) -> ConversationRole {
        match role {
            Role::User => ConversationRole::User,
            Role::Assistant => ConversationRole::Assistant,
        }
    }

    fn convert_bedrock_role(role: &ConversationRole) -> Role {
        match role {
            ConversationRole::User => Role::User,
            ConversationRole::Assistant => Role::Assistant,
            _ => Role::Assistant, // Default fallback
        }
    }

    fn convert_stop_reason(reason: &BedrockStopReason) -> StopReason {
        match reason {
            BedrockStopReason::EndTurn => StopReason::EndTurn,
            BedrockStopReason::ToolUse => StopReason::ToolUse,
            BedrockStopReason::MaxTokens => StopReason::MaxTokens,
            BedrockStopReason::ContentFiltered => StopReason::ContentFiltered,
            BedrockStopReason::GuardrailIntervened => StopReason::GuardrailIntervened,
            BedrockStopReason::StopSequence => StopReason::StopSequence,
            _ => StopReason::EndTurn,
        }
    }

    fn convert_message_to_bedrock(message: &Message) -> Result<BedrockMessage> {
        let content_blocks: Vec<BedrockContentBlock> = message
            .content
            .iter()
            .filter_map(Self::convert_content_to_bedrock)
            .collect();

        BedrockMessage::builder()
            .role(Self::convert_role(message.role))
            .set_content(Some(content_blocks))
            .build()
            .map_err(|e| StrandsError::model(format!("Failed to build message: {}", e)))
    }

    fn convert_content_to_bedrock(content: &ContentBlock) -> Option<BedrockContentBlock> {
        match content {
            ContentBlock::Text(text) => Some(BedrockContentBlock::Text(text.clone())),

            ContentBlock::ToolUse(tool_use) => {
                let block = ToolUseBlock::builder()
                    .tool_use_id(&tool_use.tool_use_id)
                    .name(&tool_use.name)
                    .input(aws_smithy_types::Document::Object(
                        Self::json_to_document_map(&tool_use.input),
                    ))
                    .build()
                    .ok()?;
                Some(BedrockContentBlock::ToolUse(block))
            }

            ContentBlock::ToolResult(result) => {
                let content_blocks: Vec<BedrockToolResultContentBlock> = result
                    .content
                    .iter()
                    .filter_map(Self::convert_tool_result_content)
                    .collect();

                let status = match result.status {
                    ToolResultStatus::Success => BedrockToolResultStatus::Success,
                    ToolResultStatus::Error => BedrockToolResultStatus::Error,
                };

                let block = ToolResultBlock::builder()
                    .tool_use_id(&result.tool_use_id)
                    .set_content(Some(content_blocks))
                    .status(status)
                    .build()
                    .ok()?;
                Some(BedrockContentBlock::ToolResult(block))
            }

            // Skip other content types for now
            _ => None,
        }
    }

    fn convert_tool_result_content(
        content: &ToolResultContentBlock,
    ) -> Option<BedrockToolResultContentBlock> {
        match content {
            ToolResultContentBlock::Text(text) => {
                Some(BedrockToolResultContentBlock::Text(text.clone()))
            }
            ToolResultContentBlock::Json(value) => Some(BedrockToolResultContentBlock::Json(
                Self::json_to_document(value),
            )),
            _ => None,
        }
    }

    fn convert_bedrock_content(content: &BedrockContentBlock) -> Option<ContentBlock> {
        match content {
            BedrockContentBlock::Text(text) => Some(ContentBlock::Text(text.clone())),

            BedrockContentBlock::ToolUse(tool_use) => {
                let input = Self::document_to_json(tool_use.input());
                Some(ContentBlock::ToolUse(ToolUseContent {
                    tool_use_id: tool_use.tool_use_id().to_string(),
                    name: tool_use.name().to_string(),
                    input,
                }))
            }

            _ => None,
        }
    }

    fn convert_bedrock_message(message: &BedrockMessage) -> Message {
        let content: Vec<ContentBlock> = message
            .content()
            .iter()
            .filter_map(Self::convert_bedrock_content)
            .collect();

        Message {
            role: Self::convert_bedrock_role(message.role()),
            content,
        }
    }

    fn build_tool_config(request: &ModelRequest) -> Option<ToolConfiguration> {
        if request.tools.tools.is_empty() {
            return None;
        }

        let tools: Vec<Tool> = request
            .tools
            .tools
            .iter()
            .filter_map(|spec| {
                let input_schema = ToolInputSchema::Json(Self::json_to_document(
                    &serde_json::to_value(&spec.input_schema).ok()?,
                ));

                let tool_spec = ToolSpecification::builder()
                    .name(&spec.name)
                    .description(&spec.description)
                    .input_schema(input_schema)
                    .build()
                    .ok()?;

                Some(Tool::ToolSpec(tool_spec))
            })
            .collect();

        ToolConfiguration::builder()
                .set_tools(Some(tools))
                .build()
                .ok()
    }

    fn build_inference_config(config: &InferenceConfig) -> Option<InferenceConfiguration> {
        let mut builder = InferenceConfiguration::builder();

        if let Some(max_tokens) = config.max_tokens {
            builder = builder.max_tokens(max_tokens as i32);
        }

        if let Some(temp) = config.temperature {
            builder = builder.temperature(temp);
        }

        if let Some(top_p) = config.top_p {
            builder = builder.top_p(top_p);
        }

        if !config.stop_sequences.is_empty() {
            builder = builder.set_stop_sequences(Some(config.stop_sequences.clone()));
        }

        Some(builder.build())
    }

    fn json_to_document(value: &serde_json::Value) -> aws_smithy_types::Document {
        match value {
            serde_json::Value::Null => aws_smithy_types::Document::Null,
            serde_json::Value::Bool(b) => aws_smithy_types::Document::Bool(*b),
            serde_json::Value::Number(n) => {
                if let Some(u) = n.as_u64() {
                    aws_smithy_types::Document::Number(aws_smithy_types::Number::PosInt(u))
                } else if let Some(i) = n.as_i64() {
                    aws_smithy_types::Document::Number(aws_smithy_types::Number::NegInt(i))
                } else if let Some(f) = n.as_f64() {
                    aws_smithy_types::Document::Number(aws_smithy_types::Number::Float(f))
                } else {
                    aws_smithy_types::Document::Null
                }
            }
            serde_json::Value::String(s) => aws_smithy_types::Document::String(s.clone()),
            serde_json::Value::Array(arr) => {
                aws_smithy_types::Document::Array(arr.iter().map(Self::json_to_document).collect())
            }
            serde_json::Value::Object(_) => {
                aws_smithy_types::Document::Object(Self::json_to_document_map(value))
            }
        }
    }

    fn json_to_document_map(
        value: &serde_json::Value,
    ) -> HashMap<String, aws_smithy_types::Document> {
        match value {
            serde_json::Value::Object(obj) => obj
                .iter()
                .map(|(k, v)| (k.clone(), Self::json_to_document(v)))
                .collect(),
            _ => HashMap::new(),
        }
    }

    fn document_to_json(doc: &aws_smithy_types::Document) -> serde_json::Value {
        match doc {
            aws_smithy_types::Document::Null => serde_json::Value::Null,
            aws_smithy_types::Document::Bool(b) => serde_json::Value::Bool(*b),
            aws_smithy_types::Document::Number(n) => match n {
                aws_smithy_types::Number::PosInt(i) => serde_json::Value::Number((*i).into()),
                aws_smithy_types::Number::NegInt(i) => serde_json::Value::Number((*i).into()),
                aws_smithy_types::Number::Float(f) => serde_json::Number::from_f64(*f)
                    .map(serde_json::Value::Number)
                    .unwrap_or(serde_json::Value::Null),
            },
            aws_smithy_types::Document::String(s) => serde_json::Value::String(s.clone()),
            aws_smithy_types::Document::Array(arr) => {
                serde_json::Value::Array(arr.iter().map(Self::document_to_json).collect())
            }
            aws_smithy_types::Document::Object(obj) => serde_json::Value::Object(
                obj.iter()
                    .map(|(k, v)| (k.clone(), Self::document_to_json(v)))
                    .collect(),
            ),
        }
    }

    fn map_client_error(err: aws_sdk_bedrockruntime::Error) -> StrandsError {
        let message = err.to_string();

        // Check for throttling
        if message.contains("throttl") || message.contains("ThrottlingException") {
            return StrandsError::throttled(message);
        }

        // Check for context window overflow
        if message.contains("context")
            && (message.contains("length") || message.contains("exceed") || message.contains("too"))
        {
            return StrandsError::context_overflow(message);
        }

        StrandsError::model(message)
    }
}

#[async_trait]
impl Model for BedrockModel {
    fn model_id(&self) -> &str {
        &self.model_id
    }

    #[instrument(skip(self, request), fields(model_id = %self.model_id))]
    async fn invoke(&self, request: ModelRequest) -> Result<ModelResponse> {
        debug!(
            messages = request.messages.len(),
            tools = request.tools.tools.len(),
            "Invoking Bedrock model"
        );

        // Convert messages
        let messages: Vec<BedrockMessage> = request
            .messages
            .iter()
            .map(Self::convert_message_to_bedrock)
            .collect::<Result<Vec<_>>>()?;

        // Build system content
        let system: Vec<SystemContentBlock> = if request.system.is_empty() {
            vec![]
        } else {
            vec![SystemContentBlock::Text(request.system.text())]
        };

        // Build request
        let mut req = self
            .client
            .converse()
            .model_id(&self.model_id)
            .set_messages(Some(messages))
            .set_system(Some(system));

        // Add tool config if present
        if let Some(tool_config) = Self::build_tool_config(&request) {
            req = req.tool_config(tool_config);
        }

        // Add inference config if present
        if let Some(inference_config) = Self::build_inference_config(&request.inference_config) {
            req = req.inference_config(inference_config);
        }

        // Execute request
        let response = req.send().await.map_err(|e| {
            error!(error = %e, "Bedrock API error");
            Self::map_client_error(e.into())
        })?;

        // Extract response
        let output = response
            .output()
            .ok_or_else(|| StrandsError::model("No output in response"))?;

        let (message, stop_reason) = match output {
            ConverseOutputType::Message(msg) => {
                let stop_reason = Self::convert_stop_reason(response.stop_reason());
                (Self::convert_bedrock_message(msg), stop_reason)
            }
            _ => {
                return Err(StrandsError::model("Unexpected output type"));
            }
        };

        // Extract usage
        let usage = response
            .usage()
            .map(|u| Usage {
                input_tokens: u.input_tokens() as u32,
                output_tokens: u.output_tokens() as u32,
                total_tokens: (u.input_tokens() + u.output_tokens()) as u32,
                ..Default::default()
            })
            .unwrap_or_default();

        debug!(
            stop_reason = ?stop_reason,
            input_tokens = usage.input_tokens,
            output_tokens = usage.output_tokens,
            "Bedrock response received"
        );

        Ok(ModelResponse {
            message,
            stop_reason,
            usage,
        })
    }

    #[instrument(skip(self, request), fields(model_id = %self.model_id))]
    async fn stream(&self, request: ModelRequest) -> Result<ModelStream> {
        debug!(
            messages = request.messages.len(),
            tools = request.tools.tools.len(),
            "Streaming from Bedrock model"
        );

        // Convert messages
        let messages: Vec<BedrockMessage> = request
            .messages
            .iter()
            .map(Self::convert_message_to_bedrock)
            .collect::<Result<Vec<_>>>()?;

        // Build system content
        let system: Vec<SystemContentBlock> = if request.system.is_empty() {
            vec![]
        } else {
            vec![SystemContentBlock::Text(request.system.text())]
        };

        // Build request
        let mut req = self
            .client
            .converse_stream()
            .model_id(&self.model_id)
            .set_messages(Some(messages))
            .set_system(Some(system));

        // Add tool config if present
        if let Some(tool_config) = Self::build_tool_config(&request) {
            req = req.tool_config(tool_config);
        }

        // Add inference config if present
        if let Some(inference_config) = Self::build_inference_config(&request.inference_config) {
            req = req.inference_config(inference_config);
        }

        // Execute streaming request
        let response = req.send().await.map_err(|e| {
            error!(error = %e, "Bedrock streaming API error");
            Self::map_client_error(e.into())
        })?;

        // Convert the EventReceiver to a stream using async-stream
        let mut event_receiver = response.stream;
        let model_id = self.model_id.clone();

        let stream = async_stream::stream! {
            let mut accumulator = StreamAccumulator::new();
            loop {
                match event_receiver.recv().await {
                    Ok(Some(event)) => {
                        if let Some(chunk) = accumulator.process_event(event) {
                            yield chunk;
                        }
                    }
                    Ok(None) => {
                        // Stream ended normally
                        break;
                    }
                    Err(e) => {
                        error!(error = %e, model_id = %model_id, "Stream error");
                        yield Err(StrandsError::model(e.to_string()));
                        break;
                    }
                }
            }
        };

        Ok(Box::pin(stream))
    }
}

/// Stateful stream converter that accumulates content across events.
struct StreamAccumulator {
    /// Accumulated text content
    text_parts: Vec<String>,
    /// Active tool_use_id from the most recent ToolUseStart
    active_tool_use_id: String,
    /// Active tool name
    active_tool_name: String,
    /// Accumulated tool input JSON
    active_tool_input: String,
    /// Completed content blocks
    content_blocks: Vec<ContentBlock>,
}

impl StreamAccumulator {
    fn new() -> Self {
        Self {
            text_parts: Vec::new(),
            active_tool_use_id: String::new(),
            active_tool_name: String::new(),
            active_tool_input: String::new(),
            content_blocks: Vec::new(),
        }
    }

    fn process_event(&mut self, event: StreamEvent) -> Option<Result<ModelStreamChunk>> {
        match event {
            StreamEvent::ContentBlockDelta(delta) => {
                if let Some(d) = delta.delta() {
                    match d {
                        aws_sdk_bedrockruntime::types::ContentBlockDelta::Text(text) => {
                            self.text_parts.push(text.clone());
                            Some(Ok(ModelStreamChunk::TextDelta(text.clone())))
                        }
                        aws_sdk_bedrockruntime::types::ContentBlockDelta::ToolUse(tool_delta) => {
                            let input_str = tool_delta.input().to_string();
                            self.active_tool_input.push_str(&input_str);
                            Some(Ok(ModelStreamChunk::ToolInputDelta {
                                tool_use_id: self.active_tool_use_id.clone(),
                                input_delta: input_str,
                            }))
                        }
                        _ => None,
                    }
                } else {
                    None
                }
            }

            StreamEvent::ContentBlockStart(start) => {
                if let Some(block) = start.start() {
                    match block {
                        aws_sdk_bedrockruntime::types::ContentBlockStart::ToolUse(tool_start) => {
                            self.active_tool_use_id = tool_start.tool_use_id().to_string();
                            self.active_tool_name = tool_start.name().to_string();
                            self.active_tool_input.clear();
                            Some(Ok(ModelStreamChunk::ToolUseStart {
                                tool_use_id: self.active_tool_use_id.clone(),
                                name: self.active_tool_name.clone(),
                            }))
                        }
                        _ => None,
                    }
                } else {
                    None
                }
            }

            StreamEvent::ContentBlockStop(_) => {
                // Finalize the current content block
                if !self.active_tool_use_id.is_empty() {
                    let input: serde_json::Value =
                        serde_json::from_str(&self.active_tool_input).unwrap_or_default();
                    self.content_blocks
                        .push(ContentBlock::ToolUse(ToolUseContent {
                            tool_use_id: self.active_tool_use_id.clone(),
                            name: self.active_tool_name.clone(),
                            input,
                        }));
                    self.active_tool_use_id.clear();
                    self.active_tool_name.clear();
                    self.active_tool_input.clear();
                }
                None
            }

            StreamEvent::MessageStop(stop) => {
                let stop_reason = BedrockModel::convert_stop_reason(stop.stop_reason());

                // Build the accumulated message
                let mut content = Vec::new();
                if !self.text_parts.is_empty() {
                    content.push(ContentBlock::Text(self.text_parts.join("")));
                }
                content.append(&mut self.content_blocks);

                let message = Message {
                    role: Role::Assistant,
                    content,
                };

                Some(Ok(ModelStreamChunk::MessageComplete {
                    message,
                    stop_reason,
                }))
            }

            StreamEvent::Metadata(meta) => {
                meta.usage().map(|usage| Ok(ModelStreamChunk::Usage(Usage {
                        input_tokens: usage.input_tokens() as u32,
                        output_tokens: usage.output_tokens() as u32,
                        total_tokens: (usage.input_tokens() + usage.output_tokens()) as u32,
                        ..Default::default()
                    })))
            }

            _ => None,
        }
    }
}
