//! Network error types

use thiserror::Error;

/// Network errors
#[derive(Error, Debug)]
pub enum NetError {
    #[error("failed to bind socket: {0}")]
    BindFailed(String),

    #[error("connection failed: {0}")]
    ConnectionFailed(String),

    #[error("send failed: {0}")]
    SendFailed(String),

    #[error("serialization error: {0}")]
    Serialization(#[from] bincode::Error),

    #[error("peer not found: {0}")]
    PeerNotFound(String),

    #[error("session not found")]
    SessionNotFound,

    #[error("not the leader")]
    NotLeader,

    #[error("already in session")]
    AlreadyInSession,

    #[error("io error: {0}")]
    Io(#[from] std::io::Error),

    #[error("laminar error: {0}")]
    Laminar(String),
}

/// Result type for network operations
pub type Result<T> = std::result::Result<T, NetError>;
