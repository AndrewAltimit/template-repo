//! Type definitions for AgentCore Memory MCP Server

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Memory event (short-term memory)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryEvent {
    pub id: String,
    pub actor_id: String,
    pub session_id: String,
    pub content: String,
    pub timestamp: DateTime<Utc>,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}

/// Memory record (long-term memory)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryRecord {
    pub id: String,
    pub content: String,
    pub namespace: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub relevance: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub created_at: Option<DateTime<Utc>>,
    #[serde(default)]
    pub metadata: HashMap<String, serde_json::Value>,
}

/// Result of batch operations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatchResult {
    pub created: usize,
    pub failed: usize,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub errors: Vec<String>,
}

impl BatchResult {
    pub fn success(count: usize) -> Self {
        Self {
            created: count,
            failed: 0,
            errors: Vec::new(),
        }
    }

    pub fn failure(count: usize, error: String) -> Self {
        Self {
            created: 0,
            failed: count,
            errors: vec![error],
        }
    }
}

/// ChromaDB configuration
#[derive(Debug, Clone)]
pub struct ChromaDBConfig {
    pub host: String,
    pub port: u16,
    pub collection_prefix: String,
}

impl Default for ChromaDBConfig {
    fn default() -> Self {
        Self {
            host: "localhost".to_string(),
            port: 8000,
            collection_prefix: "agent_memory".to_string(),
        }
    }
}

impl ChromaDBConfig {
    pub fn from_env() -> Self {
        let host = std::env::var("CHROMADB_HOST").unwrap_or_else(|_| "localhost".to_string());
        let port = std::env::var("CHROMADB_PORT")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(8000);
        let collection_prefix =
            std::env::var("CHROMADB_COLLECTION").unwrap_or_else(|_| "agent_memory".to_string());

        Self {
            host,
            port,
            collection_prefix,
        }
    }

    pub fn base_url(&self) -> String {
        format!("http://{}:{}", self.host, self.port)
    }
}

/// Predefined memory namespaces
#[allow(dead_code)]
pub mod namespaces {
    // Codebase Knowledge
    pub const ARCHITECTURE: &str = "codebase/architecture";
    pub const PATTERNS: &str = "codebase/patterns";
    pub const CONVENTIONS: &str = "codebase/conventions";
    pub const DEPENDENCIES: &str = "codebase/dependencies";

    // Review Context
    pub const PR_REVIEWS: &str = "reviews/pr";
    pub const ISSUE_CONTEXT: &str = "reviews/issues";

    // User & Project Preferences
    pub const USER_PREFS: &str = "preferences/user";
    pub const PROJECT_PREFS: &str = "preferences/project";

    // Personality
    pub const VOICE_PREFERENCES: &str = "personality/voice_preferences";
    pub const EXPRESSION_PATTERNS: &str = "personality/expression_patterns";
    pub const REACTION_HISTORY: &str = "personality/reaction_history";
    pub const AVATAR_SETTINGS: &str = "personality/avatar_settings";

    // Context
    pub const CONVERSATION_TONE: &str = "context/conversation_tone";
    pub const USER_COMMUNICATION: &str = "context/user_preferences";
    pub const INTERACTION_HISTORY: &str = "context/interaction_history";

    // Agent-Specific Learnings
    pub const CLAUDE_LEARNINGS: &str = "agents/claude";
    pub const GEMINI_LEARNINGS: &str = "agents/gemini";
    pub const OPENCODE_LEARNINGS: &str = "agents/opencode";
    pub const CRUSH_LEARNINGS: &str = "agents/crush";
    pub const CODEX_LEARNINGS: &str = "agents/codex";

    // Cross-Cutting Concerns
    pub const SECURITY_PATTERNS: &str = "security/patterns";
    pub const TESTING_PATTERNS: &str = "testing/patterns";
    pub const PERFORMANCE: &str = "performance/patterns";

    /// Get all predefined namespaces
    pub fn all_namespaces() -> Vec<&'static str> {
        vec![
            ARCHITECTURE,
            PATTERNS,
            CONVENTIONS,
            DEPENDENCIES,
            PR_REVIEWS,
            ISSUE_CONTEXT,
            USER_PREFS,
            PROJECT_PREFS,
            VOICE_PREFERENCES,
            EXPRESSION_PATTERNS,
            REACTION_HISTORY,
            AVATAR_SETTINGS,
            CONVERSATION_TONE,
            USER_COMMUNICATION,
            INTERACTION_HISTORY,
            CLAUDE_LEARNINGS,
            GEMINI_LEARNINGS,
            OPENCODE_LEARNINGS,
            CRUSH_LEARNINGS,
            CODEX_LEARNINGS,
            SECURITY_PATTERNS,
            TESTING_PATTERNS,
            PERFORMANCE,
        ]
    }

    /// Get category from namespace (e.g., "codebase/patterns" -> "codebase")
    pub fn get_category(namespace: &str) -> &str {
        namespace.split('/').next().unwrap_or(namespace)
    }
}

/// ChromaDB API request/response types
pub mod chromadb_api {
    use serde::{Deserialize, Serialize};
    use std::collections::HashMap;

    #[derive(Debug, Serialize)]
    pub struct CreateCollectionRequest {
        pub name: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub metadata: Option<HashMap<String, String>>,
        pub get_or_create: bool,
    }

    #[derive(Debug, Deserialize)]
    #[allow(dead_code)]
    pub struct CollectionResponse {
        pub id: String,
        pub name: String,
        #[serde(default)]
        pub metadata: Option<HashMap<String, serde_json::Value>>,
    }

    #[derive(Debug, Serialize)]
    pub struct AddDocumentsRequest {
        pub ids: Vec<String>,
        pub documents: Vec<String>,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub metadatas: Option<Vec<HashMap<String, serde_json::Value>>>,
    }

    #[derive(Debug, Serialize)]
    pub struct QueryRequest {
        pub query_texts: Vec<String>,
        pub n_results: u32,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub include: Option<Vec<String>>,
    }

    #[derive(Debug, Deserialize)]
    pub struct QueryResponse {
        pub ids: Vec<Vec<String>>,
        #[serde(default)]
        pub documents: Option<Vec<Vec<String>>>,
        #[serde(default)]
        pub metadatas: Option<Vec<Vec<HashMap<String, serde_json::Value>>>>,
        #[serde(default)]
        pub distances: Option<Vec<Vec<f64>>>,
    }

    #[derive(Debug, Serialize)]
    pub struct GetRequest {
        #[serde(skip_serializing_if = "Option::is_none")]
        pub ids: Option<Vec<String>>,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub limit: Option<u32>,
        #[serde(rename = "where", skip_serializing_if = "Option::is_none")]
        pub where_filter: Option<serde_json::Value>,
        #[serde(skip_serializing_if = "Option::is_none")]
        pub include: Option<Vec<String>>,
    }

    #[derive(Debug, Deserialize)]
    pub struct GetResponse {
        pub ids: Vec<String>,
        #[serde(default)]
        pub documents: Option<Vec<String>>,
        #[serde(default)]
        pub metadatas: Option<Vec<HashMap<String, serde_json::Value>>>,
    }
}
