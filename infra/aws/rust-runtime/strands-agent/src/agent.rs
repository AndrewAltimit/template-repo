//! Main Agent implementation.
//!
//! The Agent orchestrates conversations between users, models, and tools,
//! implementing the core agent loop: receive input → call model → execute tools → repeat.

use std::collections::HashMap;
use std::sync::Arc;

use futures::Stream;
use tokio::sync::Mutex;
use tracing::{debug, error, info, instrument, warn};
use uuid::Uuid;

use strands_core::{
    AgentEvent, BoxedTool, ContentBlock, Message, Messages, Result, StopReason, StrandsError,
    SystemPrompt, ToolConfig, ToolContext, ToolExecutionResult, ToolSpec, Usage,
};

use crate::conversation::ConversationManager;
use crate::loop_control::{LoopTerminationSignal, TerminationReceiver};
use crate::model::{BoxedModel, InferenceConfig, Model, ModelRequest};

/// Configuration for the agent.
#[derive(Debug, Clone)]
pub struct AgentConfig {
    /// System prompt for the agent
    pub system_prompt: SystemPrompt,

    /// Maximum iterations (model calls) per invocation
    pub max_iterations: u32,

    /// Inference configuration
    pub inference_config: InferenceConfig,

    /// Whether to enable streaming
    pub streaming: bool,

    /// Maximum retries on context overflow
    pub max_overflow_retries: u32,
}

impl Default for AgentConfig {
    fn default() -> Self {
        Self {
            system_prompt: SystemPrompt::empty(),
            max_iterations: 20,
            inference_config: InferenceConfig::default(),
            streaming: true,
            max_overflow_retries: 3,
        }
    }
}

impl AgentConfig {
    /// Create a new agent config.
    pub fn new() -> Self {
        Self::default()
    }

    /// Set the system prompt.
    pub fn with_system_prompt(mut self, prompt: impl Into<String>) -> Self {
        self.system_prompt = SystemPrompt::new(prompt);
        self
    }

    /// Set max iterations.
    pub fn with_max_iterations(mut self, max: u32) -> Self {
        self.max_iterations = max;
        self
    }

    /// Set inference config.
    pub fn with_inference_config(mut self, config: InferenceConfig) -> Self {
        self.inference_config = config;
        self
    }

    /// Enable or disable streaming.
    pub fn with_streaming(mut self, streaming: bool) -> Self {
        self.streaming = streaming;
        self
    }
}

/// Result of an agent invocation.
#[derive(Debug, Clone)]
pub struct AgentResult {
    /// The final message from the agent
    pub message: Message,

    /// Why the agent stopped
    pub stop_reason: StopReason,

    /// Total token usage across all iterations
    pub usage: Usage,

    /// Number of iterations (model calls)
    pub iterations: u32,
}

impl AgentResult {
    /// Get the text content of the response.
    pub fn text(&self) -> String {
        self.message.text()
    }
}

/// Builder for creating agents.
pub struct AgentBuilder {
    model: Option<BoxedModel>,
    config: AgentConfig,
    tools: HashMap<String, BoxedTool>,
}

impl AgentBuilder {
    /// Create a new agent builder.
    pub fn new() -> Self {
        Self {
            model: None,
            config: AgentConfig::default(),
            tools: HashMap::new(),
        }
    }

    /// Set the model provider.
    pub fn model(mut self, model: impl Model + 'static) -> Self {
        self.model = Some(Box::new(model));
        self
    }

    /// Set the agent configuration.
    pub fn config(mut self, config: AgentConfig) -> Self {
        self.config = config;
        self
    }

    /// Set the system prompt.
    pub fn system_prompt(mut self, prompt: impl Into<String>) -> Self {
        self.config.system_prompt = SystemPrompt::new(prompt);
        self
    }

    /// Register a tool.
    pub fn tool(mut self, tool: impl strands_core::Tool + 'static) -> Self {
        let spec = tool.spec();
        self.tools.insert(spec.name.clone(), Arc::new(tool));
        self
    }

    /// Set max iterations.
    pub fn max_iterations(mut self, max: u32) -> Self {
        self.config.max_iterations = max;
        self
    }

    /// Build the agent.
    pub fn build(self) -> Result<Agent> {
        let model = self
            .model
            .ok_or_else(|| StrandsError::config("Model is required"))?;

        Ok(Agent {
            model,
            config: self.config,
            tools: self.tools,
            conversation: Mutex::new(ConversationManager::new()),
        })
    }
}

impl Default for AgentBuilder {
    fn default() -> Self {
        Self::new()
    }
}

/// The main agent that orchestrates conversations.
pub struct Agent {
    /// The model provider
    model: BoxedModel,

    /// Agent configuration
    config: AgentConfig,

    /// Registered tools
    tools: HashMap<String, BoxedTool>,

    /// Conversation history (protected by mutex for thread safety)
    conversation: Mutex<ConversationManager>,
}

impl Agent {
    /// Create a new agent builder.
    pub fn builder() -> AgentBuilder {
        AgentBuilder::new()
    }

    /// Get the model ID.
    pub fn model_id(&self) -> &str {
        self.model.model_id()
    }

    /// Get the tool specifications.
    pub fn tool_specs(&self) -> Vec<ToolSpec> {
        self.tools.values().map(|t| t.spec()).collect()
    }

    /// Invoke the agent with a prompt using internal conversation state.
    ///
    /// **Warning:** This method uses a shared `Mutex<ConversationManager>` internally.
    /// For multi-user/concurrent scenarios, use `invoke_with_messages()` instead to
    /// avoid conversation history mixing between sessions.
    #[instrument(skip(self, prompt), fields(model = %self.model.model_id()))]
    pub async fn invoke(&self, prompt: impl Into<String>) -> Result<AgentResult> {
        let prompt = prompt.into();
        info!(prompt_len = prompt.len(), "Agent invocation started");

        // Add user message
        {
            let mut conv = self.conversation.lock().await;
            conv.add_user_message(&prompt);
        }

        // Run the agent loop
        let result = self.run_loop().await?;

        info!(
            iterations = result.iterations,
            stop_reason = ?result.stop_reason,
            "Agent invocation completed"
        );

        Ok(result)
    }

    /// Invoke the agent with a prompt and explicit conversation state.
    ///
    /// Unlike `invoke()`, this method operates on a local copy of the conversation,
    /// making it safe for concurrent use with different sessions. Returns the updated
    /// messages alongside the result.
    #[instrument(skip(self, prompt, messages), fields(model = %self.model.model_id()))]
    pub async fn invoke_with_messages(
        &self,
        prompt: impl Into<String>,
        mut messages: Messages,
    ) -> Result<(AgentResult, Messages)> {
        let prompt = prompt.into();
        info!(
            prompt_len = prompt.len(),
            "Agent invocation (session-isolated) started"
        );

        // Add user message to local state
        messages.push(Message::user(&prompt));

        // Run the agent loop with local conversation state
        let (result, final_messages) = self.run_loop_isolated(messages).await?;

        info!(
            iterations = result.iterations,
            stop_reason = ?result.stop_reason,
            "Agent invocation (session-isolated) completed"
        );

        Ok((result, final_messages))
    }

    /// Invoke the agent and return a stream of events.
    ///
    /// **Not yet implemented.** Returns a stream that immediately emits an error event.
    /// The model-level streaming (`BedrockModel::stream()`) works correctly, but the
    /// agent-level orchestration loop (tool execution across streaming iterations) is
    /// not yet wired up. Use `invoke()` or `invoke_with_messages()` instead.
    ///
    /// The conversation state is NOT modified by this method, so calling it won't
    /// corrupt subsequent invocations.
    #[instrument(skip(self, prompt), fields(model = %self.model.model_id()))]
    pub async fn invoke_stream(
        &self,
        prompt: impl Into<String>,
    ) -> Result<impl Stream<Item = AgentEvent>> {
        let _prompt = prompt.into();
        let invocation_id = Uuid::new_v4().to_string();

        info!(
            invocation_id = %invocation_id,
            "Agent stream invocation started (streaming not yet implemented)"
        );

        // Do NOT modify conversation state here - streaming is unimplemented
        // and adding a user message without a corresponding assistant response
        // would leave the conversation in an inconsistent state.

        // Create the event stream (emits an error event)
        let events = self.run_loop_stream(invocation_id).await?;
        Ok(events)
    }

    /// Clear the conversation history.
    pub async fn clear_history(&self) {
        let mut conv = self.conversation.lock().await;
        conv.clear();
    }

    /// Restore conversation from a list of messages.
    ///
    /// This replaces the current conversation state, enabling per-session
    /// isolation when the agent is shared across concurrent requests.
    pub async fn restore_messages(&self, messages: strands_core::Messages) {
        let mut conv = self.conversation.lock().await;
        conv.restore(messages);
    }

    /// Get the current conversation.
    pub async fn messages(&self) -> strands_core::Messages {
        let conv = self.conversation.lock().await;
        conv.snapshot()
    }

    // Private implementation methods

    async fn run_loop(&self) -> Result<AgentResult> {
        let mut total_usage = Usage::default();
        let mut iterations = 0u32;
        let mut overflow_retries = 0u32;

        loop {
            iterations += 1;

            if iterations > self.config.max_iterations {
                return Err(StrandsError::MaxIterationsExceeded {
                    max: self.config.max_iterations,
                });
            }

            debug!(iteration = iterations, "Starting agent loop iteration");

            // Build the model request
            let request = self.build_request().await;

            // Call the model
            let response = match self.model.invoke(request).await {
                Ok(resp) => {
                    overflow_retries = 0; // Reset on success
                    resp
                }
                Err(StrandsError::ContextWindowOverflow { .. }) => {
                    if overflow_retries >= self.config.max_overflow_retries {
                        return Err(StrandsError::context_overflow(
                            "Max overflow retries exceeded",
                        ));
                    }
                    overflow_retries += 1;
                    warn!(
                        retry = overflow_retries,
                        "Context overflow, reducing context"
                    );

                    let mut conv = self.conversation.lock().await;
                    if !conv.reduce_context() {
                        return Err(StrandsError::context_overflow(
                            "Cannot reduce context further",
                        ));
                    }
                    continue;
                }
                Err(e) => return Err(e),
            };

            total_usage.add(&response.usage);

            // Add assistant message to conversation
            {
                let mut conv = self.conversation.lock().await;
                conv.add_message(response.message.clone());
            }

            // Check if we should continue (tool use) or stop
            if response.stop_reason.is_terminal() {
                return Ok(AgentResult {
                    message: response.message,
                    stop_reason: response.stop_reason,
                    usage: total_usage,
                    iterations,
                });
            }

            // Execute tools
            let tool_results = self.execute_tools(&response.message).await?;

            // Add tool results to conversation
            {
                let mut conv = self.conversation.lock().await;
                conv.add_message(Message::user_with_content(tool_results));
            }
        }
    }

    /// Run the agent loop with an isolated (local) conversation state.
    /// This avoids touching the shared `self.conversation` mutex entirely,
    /// preventing race conditions when used concurrently with different sessions.
    async fn run_loop_isolated(&self, mut messages: Messages) -> Result<(AgentResult, Messages)> {
        let mut total_usage = Usage::default();
        let mut iterations = 0u32;
        let mut overflow_retries = 0u32;

        loop {
            iterations += 1;

            if iterations > self.config.max_iterations {
                return Err(StrandsError::MaxIterationsExceeded {
                    max: self.config.max_iterations,
                });
            }

            debug!(
                iteration = iterations,
                "Starting agent loop iteration (isolated)"
            );

            // Build the model request from local messages
            let tool_config = if self.tools.is_empty() {
                ToolConfig::empty()
            } else {
                ToolConfig::from_specs(self.tool_specs())
            };

            let request = ModelRequest::new(messages.clone())
                .with_system(self.config.system_prompt.clone())
                .with_tools(tool_config)
                .with_inference_config(self.config.inference_config.clone());

            // Call the model
            let response = match self.model.invoke(request).await {
                Ok(resp) => {
                    overflow_retries = 0;
                    resp
                }
                Err(StrandsError::ContextWindowOverflow { .. }) => {
                    if overflow_retries >= self.config.max_overflow_retries {
                        return Err(StrandsError::context_overflow(
                            "Max overflow retries exceeded",
                        ));
                    }
                    overflow_retries += 1;
                    warn!(
                        retry = overflow_retries,
                        "Context overflow, reducing context"
                    );

                    // Use a temporary ConversationManager for reduction logic
                    let mut conv = ConversationManager::from(messages);
                    if !conv.reduce_context() {
                        return Err(StrandsError::context_overflow(
                            "Cannot reduce context further",
                        ));
                    }
                    messages = conv.snapshot();
                    continue;
                }
                Err(e) => return Err(e),
            };

            total_usage.add(&response.usage);

            // Add assistant message to local state
            messages.push(response.message.clone());

            // Check if we should continue (tool use) or stop
            if response.stop_reason.is_terminal() {
                return Ok((
                    AgentResult {
                        message: response.message,
                        stop_reason: response.stop_reason,
                        usage: total_usage,
                        iterations,
                    },
                    messages,
                ));
            }

            // Execute tools
            let tool_results = self.execute_tools(&response.message).await?;

            // Add tool results to local state
            messages.push(Message::user_with_content(tool_results));
        }
    }

    /// Run the agent loop with early termination support.
    ///
    /// Similar to `run_loop_isolated`, but allows tools to signal early termination
    /// via a channel. When a termination signal is received, the loop stops immediately
    /// and returns the committed result.
    ///
    /// # Arguments
    ///
    /// * `messages` - Initial conversation messages
    /// * `termination_rx` - Receiver for termination signals from tools
    ///
    /// # Returns
    ///
    /// A tuple of (AgentResult, Messages, Option<Value>) where the Value is the
    /// committed result if early termination occurred.
    #[instrument(skip(self, messages, termination_rx), fields(model = %self.model.model_id()))]
    pub async fn run_loop_with_early_termination(
        &self,
        mut messages: Messages,
        mut termination_rx: TerminationReceiver,
    ) -> Result<(AgentResult, Messages, Option<serde_json::Value>)> {
        let mut total_usage = Usage::default();
        let mut iterations = 0u32;
        let mut overflow_retries = 0u32;

        loop {
            iterations += 1;

            if iterations > self.config.max_iterations {
                return Err(StrandsError::MaxIterationsExceeded {
                    max: self.config.max_iterations,
                });
            }

            debug!(
                iteration = iterations,
                "Starting agent loop iteration (with early termination)"
            );

            // Build the model request from local messages
            let tool_config = if self.tools.is_empty() {
                ToolConfig::empty()
            } else {
                ToolConfig::from_specs(self.tool_specs())
            };

            let request = ModelRequest::new(messages.clone())
                .with_system(self.config.system_prompt.clone())
                .with_tools(tool_config)
                .with_inference_config(self.config.inference_config.clone());

            // Call the model
            let response = match self.model.invoke(request).await {
                Ok(resp) => {
                    overflow_retries = 0;
                    resp
                }
                Err(StrandsError::ContextWindowOverflow { .. }) => {
                    if overflow_retries >= self.config.max_overflow_retries {
                        return Err(StrandsError::context_overflow(
                            "Max overflow retries exceeded",
                        ));
                    }
                    overflow_retries += 1;
                    warn!(
                        retry = overflow_retries,
                        "Context overflow, reducing context"
                    );

                    let mut conv = ConversationManager::from(messages);
                    if !conv.reduce_context() {
                        return Err(StrandsError::context_overflow(
                            "Cannot reduce context further",
                        ));
                    }
                    messages = conv.snapshot();
                    continue;
                }
                Err(e) => return Err(e),
            };

            total_usage.add(&response.usage);
            messages.push(response.message.clone());

            // Check if we should continue (tool use) or stop
            if response.stop_reason.is_terminal() {
                return Ok((
                    AgentResult {
                        message: response.message,
                        stop_reason: response.stop_reason,
                        usage: total_usage,
                        iterations,
                    },
                    messages,
                    None,
                ));
            }

            // Execute tools
            let tool_results = self.execute_tools(&response.message).await?;
            messages.push(Message::user_with_content(tool_results));

            // Check for early termination signal after tool execution
            match termination_rx.try_recv() {
                Ok(LoopTerminationSignal::ToolCompleted { tool_name, result }) => {
                    info!(
                        tool = %tool_name,
                        iterations,
                        "Agent loop terminated by tool completion"
                    );
                    return Ok((
                        AgentResult {
                            message: Message::assistant(format!(
                                "Response committed by {} tool.",
                                tool_name
                            )),
                            stop_reason: StopReason::EndTurn,
                            usage: total_usage,
                            iterations,
                        },
                        messages,
                        Some(result),
                    ));
                }
                Err(tokio::sync::mpsc::error::TryRecvError::Empty) => {
                    // No termination signal, continue loop
                }
                Err(tokio::sync::mpsc::error::TryRecvError::Disconnected) => {
                    warn!("Termination channel disconnected unexpectedly");
                    // Continue anyway - channel being dropped is not fatal
                }
            }
        }
    }

    async fn run_loop_stream(
        &self,
        invocation_id: String,
    ) -> Result<impl Stream<Item = AgentEvent>> {
        // TODO: Full streaming implementation. For now, emit an error event.
        let (tx, rx) = tokio::sync::mpsc::channel(100);

        tokio::spawn(async move {
            let _ = tx.send(AgentEvent::start(&invocation_id)).await;
            let _ = tx
                .send(AgentEvent::error(
                    "Full streaming not yet implemented - use invoke()",
                    false,
                ))
                .await;
        });

        Ok(tokio_stream::wrappers::ReceiverStream::new(rx))
    }

    async fn build_request(&self) -> ModelRequest {
        let conv = self.conversation.lock().await;
        let messages = conv.snapshot();

        let tool_config = if self.tools.is_empty() {
            ToolConfig::empty()
        } else {
            ToolConfig::from_specs(self.tool_specs())
        };

        ModelRequest::new(messages)
            .with_system(self.config.system_prompt.clone())
            .with_tools(tool_config)
            .with_inference_config(self.config.inference_config.clone())
    }

    async fn execute_tools(&self, message: &Message) -> Result<Vec<ContentBlock>> {
        let mut results = Vec::new();

        for tool_use in message.tool_uses() {
            debug!(
                tool = %tool_use.name,
                tool_use_id = %tool_use.tool_use_id,
                "Executing tool"
            );

            let result = match self.tools.get(&tool_use.name) {
                Some(tool) => {
                    let context = ToolContext::default();
                    match tool.execute(tool_use.input.clone(), &context).await {
                        Ok(result) => result,
                        Err(e) => {
                            error!(
                                tool = %tool_use.name,
                                error = %e,
                                "Tool execution failed"
                            );
                            ToolExecutionResult::error(e.to_string())
                        }
                    }
                }
                None => {
                    warn!(tool = %tool_use.name, "Tool not found");
                    ToolExecutionResult::error(format!("Tool '{}' not found", tool_use.name))
                }
            };

            results.push(ContentBlock::tool_result(
                &tool_use.tool_use_id,
                result.content,
                result.status,
            ));
        }

        Ok(results)
    }
}

#[cfg(test)]
mod tests {
    // Tests would go here with mocked models and tools
}
