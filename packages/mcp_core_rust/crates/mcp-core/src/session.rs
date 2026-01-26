//! Session management for MCP servers.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

/// Information about a client session
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionInfo {
    /// Unique session identifier
    pub id: String,
    /// Client information (name, version)
    pub client_info: Option<ClientInfo>,
    /// Negotiated protocol version
    pub protocol_version: String,
    /// Session creation timestamp
    pub created_at: chrono::DateTime<chrono::Utc>,
    /// Whether the session has been initialized
    pub initialized: bool,
}

/// Client information provided during initialization
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClientInfo {
    /// Client name
    pub name: String,
    /// Client version
    pub version: Option<String>,
}

impl SessionInfo {
    /// Create a new session
    pub fn new(protocol_version: impl Into<String>) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            client_info: None,
            protocol_version: protocol_version.into(),
            created_at: chrono::Utc::now(),
            initialized: false,
        }
    }

    /// Create a session with a specific ID
    pub fn with_id(id: impl Into<String>, protocol_version: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            client_info: None,
            protocol_version: protocol_version.into(),
            created_at: chrono::Utc::now(),
            initialized: false,
        }
    }

    /// Set client information
    pub fn with_client_info(mut self, client_info: ClientInfo) -> Self {
        self.client_info = Some(client_info);
        self
    }

    /// Mark the session as initialized
    pub fn mark_initialized(&mut self) {
        self.initialized = true;
    }
}

/// Thread-safe session manager
#[derive(Clone)]
pub struct SessionManager {
    sessions: Arc<RwLock<HashMap<String, SessionInfo>>>,
}

impl Default for SessionManager {
    fn default() -> Self {
        Self::new()
    }
}

impl SessionManager {
    /// Create a new session manager
    pub fn new() -> Self {
        Self {
            sessions: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Create a new session and return its ID
    pub async fn create_session(&self, protocol_version: impl Into<String>) -> String {
        let session = SessionInfo::new(protocol_version);
        let id = session.id.clone();
        self.sessions.write().await.insert(id.clone(), session);
        id
    }

    /// Get or create a session by ID
    pub async fn get_or_create(
        &self,
        session_id: Option<&str>,
        protocol_version: impl Into<String>,
    ) -> String {
        if let Some(id) = session_id {
            if self.sessions.read().await.contains_key(id) {
                return id.to_string();
            }
            // Session ID provided but doesn't exist - create with that ID
            let session = SessionInfo::with_id(id, protocol_version);
            self.sessions
                .write()
                .await
                .insert(id.to_string(), session);
            id.to_string()
        } else {
            // No session ID - create new
            self.create_session(protocol_version).await
        }
    }

    /// Get a session by ID
    pub async fn get(&self, session_id: &str) -> Option<SessionInfo> {
        self.sessions.read().await.get(session_id).cloned()
    }

    /// Update a session
    pub async fn update<F>(&self, session_id: &str, f: F) -> bool
    where
        F: FnOnce(&mut SessionInfo),
    {
        if let Some(session) = self.sessions.write().await.get_mut(session_id) {
            f(session);
            true
        } else {
            false
        }
    }

    /// Remove a session
    pub async fn remove(&self, session_id: &str) -> Option<SessionInfo> {
        self.sessions.write().await.remove(session_id)
    }

    /// Check if a session exists
    pub async fn exists(&self, session_id: &str) -> bool {
        self.sessions.read().await.contains_key(session_id)
    }

    /// Get the number of active sessions
    pub async fn count(&self) -> usize {
        self.sessions.read().await.len()
    }

    /// Clear all sessions
    pub async fn clear(&self) {
        self.sessions.write().await.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_session_creation() {
        let manager = SessionManager::new();
        let id = manager.create_session("2024-11-05").await;

        assert!(!id.is_empty());
        assert!(manager.exists(&id).await);

        let session = manager.get(&id).await.unwrap();
        assert_eq!(session.protocol_version, "2024-11-05");
        assert!(!session.initialized);
    }

    #[tokio::test]
    async fn test_session_update() {
        let manager = SessionManager::new();
        let id = manager.create_session("2024-11-05").await;

        let updated = manager
            .update(&id, |s| {
                s.mark_initialized();
                s.client_info = Some(ClientInfo {
                    name: "test-client".to_string(),
                    version: Some("1.0.0".to_string()),
                });
            })
            .await;

        assert!(updated);

        let session = manager.get(&id).await.unwrap();
        assert!(session.initialized);
        assert_eq!(session.client_info.unwrap().name, "test-client");
    }

    #[tokio::test]
    async fn test_get_or_create() {
        let manager = SessionManager::new();

        // Create new session when none exists
        let id1 = manager.get_or_create(None, "2024-11-05").await;
        assert!(manager.exists(&id1).await);

        // Get existing session
        let id2 = manager.get_or_create(Some(&id1), "2024-11-05").await;
        assert_eq!(id1, id2);

        // Create with specific ID that doesn't exist
        let id3 = manager.get_or_create(Some("custom-id"), "2024-11-05").await;
        assert_eq!(id3, "custom-id");
        assert!(manager.exists("custom-id").await);
    }
}
