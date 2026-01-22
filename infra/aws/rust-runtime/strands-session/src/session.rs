//! Session types and state management.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use strands_core::{Message, Usage};
use uuid::Uuid;

/// Session configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionConfig {
    /// Maximum number of messages to keep in memory
    pub max_messages: usize,
    /// Whether to persist to AgentCore Memory
    pub persist: bool,
    /// Session timeout in seconds
    pub timeout_secs: u64,
    /// Namespace for memory storage
    pub namespace: Option<String>,
}

impl Default for SessionConfig {
    fn default() -> Self {
        Self {
            max_messages: 100,
            persist: true,
            timeout_secs: 3600, // 1 hour
            namespace: None,
        }
    }
}

/// Session state tracking.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SessionState {
    /// Session is active and accepting requests
    Active,
    /// Session is currently processing a request
    Processing,
    /// Session has been suspended (can be resumed)
    Suspended,
    /// Session has been terminated
    Terminated,
}

/// A session containing conversation history and metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Session {
    /// Unique session identifier
    pub id: String,
    /// Session creation time
    pub created_at: DateTime<Utc>,
    /// Last activity time
    pub last_activity: DateTime<Utc>,
    /// Current session state
    pub state: SessionState,
    /// Conversation messages
    pub messages: Vec<Message>,
    /// Total token usage for this session
    pub total_usage: Usage,
    /// Session configuration
    pub config: SessionConfig,
    /// Custom metadata
    pub metadata: serde_json::Value,
}

impl Session {
    /// Create a new session with default configuration.
    pub fn new() -> Self {
        Self::with_config(SessionConfig::default())
    }

    /// Create a new session with the given configuration.
    pub fn with_config(config: SessionConfig) -> Self {
        let now = Utc::now();
        Self {
            id: Uuid::new_v4().to_string(),
            created_at: now,
            last_activity: now,
            state: SessionState::Active,
            messages: Vec::new(),
            total_usage: Usage::default(),
            config,
            metadata: serde_json::Value::Null,
        }
    }

    /// Create a session with a specific ID (for loading from storage).
    pub fn with_id(id: impl Into<String>, config: SessionConfig) -> Self {
        let now = Utc::now();
        Self {
            id: id.into(),
            created_at: now,
            last_activity: now,
            state: SessionState::Active,
            messages: Vec::new(),
            total_usage: Usage::default(),
            config,
            metadata: serde_json::Value::Null,
        }
    }

    /// Add a message to the session.
    pub fn add_message(&mut self, message: Message) {
        self.messages.push(message);
        self.last_activity = Utc::now();

        // Trim if over max messages
        if self.messages.len() > self.config.max_messages {
            let trim_count = self.messages.len() - self.config.max_messages;
            self.messages.drain(0..trim_count);
        }
    }

    /// Add usage to the session total.
    pub fn add_usage(&mut self, usage: &Usage) {
        self.total_usage.input_tokens += usage.input_tokens;
        self.total_usage.output_tokens += usage.output_tokens;
        self.total_usage.total_tokens += usage.total_tokens;
    }

    /// Get the message count.
    pub fn message_count(&self) -> usize {
        self.messages.len()
    }

    /// Check if the session has expired.
    pub fn is_expired(&self) -> bool {
        let elapsed = Utc::now()
            .signed_duration_since(self.last_activity)
            .num_seconds();
        elapsed as u64 > self.config.timeout_secs
    }

    /// Mark the session as processing.
    pub fn set_processing(&mut self) {
        self.state = SessionState::Processing;
        self.last_activity = Utc::now();
    }

    /// Mark the session as active.
    pub fn set_active(&mut self) {
        self.state = SessionState::Active;
        self.last_activity = Utc::now();
    }

    /// Suspend the session.
    pub fn suspend(&mut self) {
        self.state = SessionState::Suspended;
    }

    /// Terminate the session.
    pub fn terminate(&mut self) {
        self.state = SessionState::Terminated;
    }

    /// Clear all messages from the session.
    pub fn clear_messages(&mut self) {
        self.messages.clear();
        self.last_activity = Utc::now();
    }
}

impl Default for Session {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use strands_core::{ContentBlock, Role};

    #[test]
    fn test_session_creation() {
        let session = Session::new();
        assert!(!session.id.is_empty());
        assert_eq!(session.state, SessionState::Active);
        assert_eq!(session.messages.len(), 0);
    }

    #[test]
    fn test_add_message() {
        let mut session = Session::new();
        session.add_message(Message {
            role: Role::User,
            content: vec![ContentBlock::Text("Hello".to_string())],
        });
        assert_eq!(session.message_count(), 1);
    }

    #[test]
    fn test_message_trimming() {
        let config = SessionConfig {
            max_messages: 2,
            ..Default::default()
        };
        let mut session = Session::with_config(config);

        for i in 0..5 {
            session.add_message(Message {
                role: Role::User,
                content: vec![ContentBlock::Text(format!("Message {}", i))],
            });
        }

        assert_eq!(session.message_count(), 2);
    }

    #[test]
    fn test_state_transitions() {
        let mut session = Session::new();
        assert_eq!(session.state, SessionState::Active);

        session.set_processing();
        assert_eq!(session.state, SessionState::Processing);

        session.set_active();
        assert_eq!(session.state, SessionState::Active);

        session.suspend();
        assert_eq!(session.state, SessionState::Suspended);

        session.terminate();
        assert_eq!(session.state, SessionState::Terminated);
    }
}
