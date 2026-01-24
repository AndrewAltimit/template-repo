//! Conversation management and context window handling.
//!
//! Manages the conversation history and provides strategies for
//! handling context window overflow.

use strands_core::{ContentBlock, Message, Messages, Role};
use tracing::{debug, warn};

/// Manages conversation history and context window.
#[derive(Debug, Clone)]
pub struct ConversationManager {
    /// The conversation messages
    messages: Messages,

    /// Maximum number of messages to keep (None = unlimited)
    max_messages: Option<usize>,

    /// Strategy for reducing context when overflow occurs
    reduction_strategy: ContextReductionStrategy,
}

/// Strategy for reducing context when the window overflows.
#[derive(Debug, Clone, Copy, Default)]
pub enum ContextReductionStrategy {
    /// Remove oldest messages first (keep most recent)
    #[default]
    RemoveOldest,

    /// Summarize older messages (requires model call)
    Summarize,

    /// Truncate long messages
    TruncateContent,
}

impl ConversationManager {
    /// Create a new conversation manager.
    pub fn new() -> Self {
        Self {
            messages: Vec::new(),
            max_messages: None,
            reduction_strategy: ContextReductionStrategy::default(),
        }
    }

    /// Create with a maximum message limit.
    pub fn with_max_messages(max_messages: usize) -> Self {
        Self {
            messages: Vec::new(),
            max_messages: Some(max_messages),
            reduction_strategy: ContextReductionStrategy::default(),
        }
    }

    /// Set the context reduction strategy.
    pub fn with_reduction_strategy(mut self, strategy: ContextReductionStrategy) -> Self {
        self.reduction_strategy = strategy;
        self
    }

    /// Get the current messages.
    pub fn messages(&self) -> &Messages {
        &self.messages
    }

    /// Get mutable access to messages.
    pub fn messages_mut(&mut self) -> &mut Messages {
        &mut self.messages
    }

    /// Add a message to the conversation.
    pub fn add_message(&mut self, message: Message) {
        self.messages.push(message);
        self.enforce_limits();
    }

    /// Add a user message.
    pub fn add_user_message(&mut self, content: impl Into<String>) {
        self.add_message(Message::user(content));
    }

    /// Add an assistant message.
    pub fn add_assistant_message(&mut self, content: impl Into<String>) {
        self.add_message(Message::assistant(content));
    }

    /// Add a message with multiple content blocks.
    pub fn add_message_with_content(&mut self, role: Role, content: Vec<ContentBlock>) {
        let message = match role {
            Role::User => Message::user_with_content(content),
            Role::Assistant => Message::assistant_with_content(content),
        };
        self.add_message(message);
    }

    /// Clear all messages.
    pub fn clear(&mut self) {
        self.messages.clear();
    }

    /// Get the number of messages.
    pub fn len(&self) -> usize {
        self.messages.len()
    }

    /// Check if empty.
    pub fn is_empty(&self) -> bool {
        self.messages.is_empty()
    }

    /// Get the last message.
    pub fn last_message(&self) -> Option<&Message> {
        self.messages.last()
    }

    /// Get the last assistant message.
    pub fn last_assistant_message(&self) -> Option<&Message> {
        self.messages.iter().rev().find(|m| m.is_assistant())
    }

    /// Reduce context for overflow recovery.
    ///
    /// This is called when a context window overflow occurs to reduce
    /// the conversation size and retry.
    pub fn reduce_context(&mut self) -> bool {
        if self.messages.len() <= 2 {
            // Can't reduce further - need at least the last exchange
            warn!("Cannot reduce context further - minimum messages reached");
            return false;
        }

        match self.reduction_strategy {
            ContextReductionStrategy::RemoveOldest => {
                // Remove the oldest message pair (user + assistant)
                let remove_count = self.calculate_removal_count();
                debug!(
                    "Reducing context by removing {} oldest messages",
                    remove_count
                );

                // Ensure we maintain user/assistant alternation
                self.messages.drain(0..remove_count);
                true
            }
            ContextReductionStrategy::TruncateContent => {
                // Truncate long text content in older messages
                let truncated = self.truncate_old_messages();
                if truncated {
                    debug!("Truncated content in older messages");
                }
                truncated
            }
            ContextReductionStrategy::Summarize => {
                // Would require a model call - not implemented inline
                // Fall back to removing oldest
                warn!("Summarize strategy not implemented, falling back to remove oldest");
                self.messages.drain(0..2);
                true
            }
        }
    }

    /// Restore messages from a saved state.
    pub fn restore(&mut self, messages: Messages) {
        self.messages = messages;
        self.enforce_limits();
    }

    /// Clone messages for saving.
    pub fn snapshot(&self) -> Messages {
        self.messages.clone()
    }

    // Private helper methods

    fn enforce_limits(&mut self) {
        if let Some(max) = self.max_messages {
            while self.messages.len() > max {
                self.messages.remove(0);
            }
        }
    }

    fn calculate_removal_count(&self) -> usize {
        // Remove ~25% of messages, but at least 2
        let target = (self.messages.len() / 4).max(2);

        // Ensure we remove complete pairs
        if target % 2 != 0 {
            target + 1
        } else {
            target
        }
    }

    fn truncate_old_messages(&mut self) -> bool {
        const MAX_TEXT_LENGTH: usize = 1000;
        const TRUNCATE_SUFFIX: &str = "... [truncated]";

        let mut truncated = false;
        let len = self.messages.len();

        // Only truncate messages before the last 4
        if len <= 4 {
            return false;
        }

        for message in self.messages.iter_mut().take(len - 4) {
            for content in message.content.iter_mut() {
                if let ContentBlock::Text(text) = content {
                    if text.len() > MAX_TEXT_LENGTH {
                        text.truncate(MAX_TEXT_LENGTH - TRUNCATE_SUFFIX.len());
                        text.push_str(TRUNCATE_SUFFIX);
                        truncated = true;
                    }
                }
            }
        }

        truncated
    }
}

impl Default for ConversationManager {
    fn default() -> Self {
        Self::new()
    }
}

impl From<Messages> for ConversationManager {
    fn from(messages: Messages) -> Self {
        Self {
            messages,
            max_messages: None,
            reduction_strategy: ContextReductionStrategy::default(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add_messages() {
        let mut manager = ConversationManager::new();

        manager.add_user_message("Hello");
        manager.add_assistant_message("Hi there!");

        assert_eq!(manager.len(), 2);
        assert!(manager.messages()[0].is_user());
        assert!(manager.messages()[1].is_assistant());
    }

    #[test]
    fn test_max_messages_limit() {
        let mut manager = ConversationManager::with_max_messages(4);

        for i in 0..10 {
            if i % 2 == 0 {
                manager.add_user_message(format!("User {}", i));
            } else {
                manager.add_assistant_message(format!("Assistant {}", i));
            }
        }

        assert_eq!(manager.len(), 4);
    }

    #[test]
    fn test_reduce_context() {
        let mut manager = ConversationManager::new();

        for i in 0..10 {
            if i % 2 == 0 {
                manager.add_user_message(format!("User {}", i));
            } else {
                manager.add_assistant_message(format!("Assistant {}", i));
            }
        }

        let original_len = manager.len();
        assert!(manager.reduce_context());
        assert!(manager.len() < original_len);
    }
}
