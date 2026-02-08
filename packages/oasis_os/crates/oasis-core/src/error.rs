//! Error types for OASIS_OS.

use std::io;

/// Errors produced by the OASIS_OS framework.
#[derive(Debug, thiserror::Error)]
pub enum OasisError {
    #[error("SDI error: {0}")]
    Sdi(String),

    #[error("backend error: {0}")]
    Backend(String),

    #[error("config error: {0}")]
    Config(String),

    #[error("VFS error: {0}")]
    Vfs(String),

    #[error("command error: {0}")]
    Command(String),

    #[error("platform error: {0}")]
    Platform(String),

    #[error("window manager error: {0}")]
    Wm(String),

    #[error("plugin error: {0}")]
    Plugin(String),

    #[error("I/O error: {0}")]
    Io(#[from] io::Error),

    #[error("TOML parse error: {0}")]
    TomlParse(#[from] toml::de::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),
}

/// Convenience alias.
pub type Result<T> = std::result::Result<T, OasisError>;
