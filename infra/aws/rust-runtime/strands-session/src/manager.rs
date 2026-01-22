//! Session manager for handling session lifecycle.

use std::collections::HashMap;
use std::sync::Arc;

use async_trait::async_trait;
use strands_core::Result;
use tokio::sync::RwLock;
use tracing::{debug, instrument, warn};

use crate::memory::AgentCoreMemory;
use crate::session::{Session, SessionConfig};

/// Session storage backend trait.
#[async_trait]
pub trait SessionStorage: Send + Sync {
    /// Load a session by ID.
    async fn load(&self, session_id: &str) -> Result<Option<Session>>;

    /// Save a session.
    async fn save(&self, session: &Session) -> Result<()>;

    /// Delete a session.
    async fn delete(&self, session_id: &str) -> Result<()>;

    /// List all session IDs.
    async fn list(&self) -> Result<Vec<String>>;
}

/// In-memory session storage for testing.
#[derive(Default)]
pub struct InMemoryStorage {
    sessions: RwLock<HashMap<String, Session>>,
}

#[async_trait]
impl SessionStorage for InMemoryStorage {
    async fn load(&self, session_id: &str) -> Result<Option<Session>> {
        let sessions = self.sessions.read().await;
        Ok(sessions.get(session_id).cloned())
    }

    async fn save(&self, session: &Session) -> Result<()> {
        let mut sessions = self.sessions.write().await;
        sessions.insert(session.id.clone(), session.clone());
        Ok(())
    }

    async fn delete(&self, session_id: &str) -> Result<()> {
        let mut sessions = self.sessions.write().await;
        sessions.remove(session_id);
        Ok(())
    }

    async fn list(&self) -> Result<Vec<String>> {
        let sessions = self.sessions.read().await;
        Ok(sessions.keys().cloned().collect())
    }
}

/// Session manager for creating, loading, and managing sessions.
pub struct SessionManager {
    /// Session storage backend
    storage: Arc<dyn SessionStorage>,
    /// Default session configuration
    default_config: SessionConfig,
    /// Active sessions cache
    active_sessions: RwLock<HashMap<String, Session>>,
    /// Optional AgentCore Memory integration
    memory: Option<AgentCoreMemory>,
}

impl SessionManager {
    /// Create a new session manager with in-memory storage.
    pub fn new() -> Self {
        Self {
            storage: Arc::new(InMemoryStorage::default()),
            default_config: SessionConfig::default(),
            active_sessions: RwLock::new(HashMap::new()),
            memory: None,
        }
    }

    /// Create a session manager with custom storage.
    pub fn with_storage(storage: Arc<dyn SessionStorage>) -> Self {
        Self {
            storage,
            default_config: SessionConfig::default(),
            active_sessions: RwLock::new(HashMap::new()),
            memory: None,
        }
    }

    /// Set the default session configuration.
    pub fn with_config(mut self, config: SessionConfig) -> Self {
        self.default_config = config;
        self
    }

    /// Set the AgentCore Memory integration.
    pub fn with_memory(mut self, memory: AgentCoreMemory) -> Self {
        self.memory = Some(memory);
        self
    }

    /// Create a new session.
    #[instrument(skip(self))]
    pub async fn create_session(&self) -> Result<Session> {
        self.create_session_with_config(self.default_config.clone())
            .await
    }

    /// Create a new session with custom configuration.
    #[instrument(skip(self, config))]
    pub async fn create_session_with_config(&self, config: SessionConfig) -> Result<Session> {
        let session = Session::with_config(config);
        debug!(session_id = %session.id, "Creating new session");

        // Cache the session
        {
            let mut cache = self.active_sessions.write().await;
            cache.insert(session.id.clone(), session.clone());
        }

        // Persist to storage
        self.storage.save(&session).await?;

        Ok(session)
    }

    /// Get or create a session by ID.
    #[instrument(skip(self))]
    pub async fn get_or_create(&self, session_id: &str) -> Result<Session> {
        // Check cache first
        {
            let cache = self.active_sessions.read().await;
            if let Some(session) = cache.get(session_id) {
                if !session.is_expired() {
                    return Ok(session.clone());
                }
            }
        }

        // Try to load from storage
        if let Some(session) = self.storage.load(session_id).await? {
            if !session.is_expired() {
                // Add to cache
                let mut cache = self.active_sessions.write().await;
                cache.insert(session_id.to_string(), session.clone());
                return Ok(session);
            } else {
                // Session expired, delete it
                warn!(session_id, "Session expired, creating new one");
                self.storage.delete(session_id).await?;
            }
        }

        // Create new session with the requested ID
        let session = Session::with_id(session_id, self.default_config.clone());
        debug!(session_id, "Creating new session with specified ID");

        // Cache and persist
        {
            let mut cache = self.active_sessions.write().await;
            cache.insert(session.id.clone(), session.clone());
        }
        self.storage.save(&session).await?;

        Ok(session)
    }

    /// Update a session.
    #[instrument(skip(self, session))]
    pub async fn update_session(&self, session: &Session) -> Result<()> {
        debug!(session_id = %session.id, "Updating session");

        // Update cache
        {
            let mut cache = self.active_sessions.write().await;
            cache.insert(session.id.clone(), session.clone());
        }

        // Persist to storage
        self.storage.save(session).await?;

        // Sync to AgentCore Memory if configured
        if let Some(memory) = &self.memory {
            if session.config.persist {
                memory.sync_session(session).await?;
            }
        }

        Ok(())
    }

    /// Delete a session.
    #[instrument(skip(self))]
    pub async fn delete_session(&self, session_id: &str) -> Result<()> {
        debug!(session_id, "Deleting session");

        // Remove from cache
        {
            let mut cache = self.active_sessions.write().await;
            cache.remove(session_id);
        }

        // Remove from storage
        self.storage.delete(session_id).await?;

        Ok(())
    }

    /// Clean up expired sessions.
    #[instrument(skip(self))]
    pub async fn cleanup_expired(&self) -> Result<usize> {
        let session_ids = self.storage.list().await?;
        let mut cleaned = 0;

        for session_id in session_ids {
            if let Some(session) = self.storage.load(&session_id).await? {
                if session.is_expired() {
                    debug!(session_id = %session.id, "Cleaning up expired session");
                    self.delete_session(&session_id).await?;
                    cleaned += 1;
                }
            }
        }

        debug!(cleaned, "Cleaned up expired sessions");
        Ok(cleaned)
    }

    /// Get the number of active sessions in cache.
    pub async fn active_count(&self) -> usize {
        let cache = self.active_sessions.read().await;
        cache.len()
    }

    /// List all session IDs.
    pub async fn list_sessions(&self) -> Result<Vec<String>> {
        self.storage.list().await
    }
}

impl Default for SessionManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use strands_core::{ContentBlock, Message, Role};

    #[tokio::test]
    async fn test_create_session() {
        let manager = SessionManager::new();
        let session = manager.create_session().await.unwrap();

        assert!(!session.id.is_empty());
        assert_eq!(session.state, SessionState::Active);
    }

    #[tokio::test]
    async fn test_get_or_create() {
        let manager = SessionManager::new();

        // First call creates
        let session1 = manager.get_or_create("test-session").await.unwrap();
        assert_eq!(session1.id, "test-session");

        // Second call returns same session
        let session2 = manager.get_or_create("test-session").await.unwrap();
        assert_eq!(session2.id, "test-session");
    }

    #[tokio::test]
    async fn test_update_session() {
        let manager = SessionManager::new();
        let mut session = manager.create_session().await.unwrap();

        session.add_message(Message {
            role: Role::User,
            content: vec![ContentBlock::Text("Hello".to_string())],
        });

        manager.update_session(&session).await.unwrap();

        // Reload and verify
        let loaded = manager.get_or_create(&session.id).await.unwrap();
        assert_eq!(loaded.message_count(), 1);
    }

    #[tokio::test]
    async fn test_delete_session() {
        let manager = SessionManager::new();
        let session = manager.create_session().await.unwrap();
        let session_id = session.id.clone();

        manager.delete_session(&session_id).await.unwrap();

        // New get_or_create should create a fresh session
        let new_session = manager.get_or_create(&session_id).await.unwrap();
        assert_eq!(new_session.message_count(), 0);
    }
}
