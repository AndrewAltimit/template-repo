//! Shared state for JSON response tools.

use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::Arc;
use tokio::sync::mpsc;

/// The committed response from an agent.
#[derive(Debug, Clone)]
pub struct CommittedResponse {
    /// The validated JSON response
    pub json_response: serde_json::Value,
    /// Number of validation attempts before success
    pub validation_attempts: u32,
}

/// Shared state between validate_json and commit_response tools.
#[derive(Clone)]
pub struct JsonResponseState {
    /// Current validation attempt count
    pub attempts: Arc<AtomicU32>,
    /// Maximum allowed attempts
    pub max_attempts: u32,
    /// Whether a response has been committed
    pub committed: Arc<AtomicBool>,
    /// Channel to signal committed response
    pub commit_tx: mpsc::Sender<CommittedResponse>,
    /// The JSON schema to validate against
    pub schema: Arc<serde_json::Value>,
}

impl JsonResponseState {
    /// Create a new JSON response state.
    pub fn new(
        schema: serde_json::Value,
        max_attempts: u32,
        commit_tx: mpsc::Sender<CommittedResponse>,
    ) -> Self {
        Self {
            attempts: Arc::new(AtomicU32::new(0)),
            max_attempts,
            committed: Arc::new(AtomicBool::new(false)),
            commit_tx,
            schema: Arc::new(schema),
        }
    }

    /// Increment and return the current attempt number.
    pub fn increment_attempts(&self) -> u32 {
        self.attempts.fetch_add(1, Ordering::SeqCst) + 1
    }

    /// Get the current attempt count.
    pub fn current_attempts(&self) -> u32 {
        self.attempts.load(Ordering::SeqCst)
    }

    /// Check if max attempts exceeded.
    pub fn exceeded_max_attempts(&self) -> bool {
        self.current_attempts() >= self.max_attempts
    }

    /// Try to mark as committed. Returns true if this call committed, false if already committed.
    pub fn try_commit(&self) -> bool {
        !self.committed.swap(true, Ordering::SeqCst)
    }

    /// Check if already committed.
    pub fn is_committed(&self) -> bool {
        self.committed.load(Ordering::SeqCst)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_attempt_tracking() {
        let (tx, _rx) = mpsc::channel(1);
        let state = JsonResponseState::new(serde_json::json!({}), 8, tx);

        assert_eq!(state.current_attempts(), 0);
        assert_eq!(state.increment_attempts(), 1);
        assert_eq!(state.increment_attempts(), 2);
        assert_eq!(state.current_attempts(), 2);
    }

    #[tokio::test]
    async fn test_commit_once() {
        let (tx, _rx) = mpsc::channel(1);
        let state = JsonResponseState::new(serde_json::json!({}), 8, tx);

        assert!(!state.is_committed());
        assert!(state.try_commit()); // First commit succeeds
        assert!(state.is_committed());
        assert!(!state.try_commit()); // Second commit fails
    }

    #[tokio::test]
    async fn test_max_attempts() {
        let (tx, _rx) = mpsc::channel(1);
        let state = JsonResponseState::new(serde_json::json!({}), 3, tx);

        assert!(!state.exceeded_max_attempts());
        state.increment_attempts(); // 1
        state.increment_attempts(); // 2
        assert!(!state.exceeded_max_attempts());
        state.increment_attempts(); // 3
        assert!(state.exceeded_max_attempts());
    }
}
