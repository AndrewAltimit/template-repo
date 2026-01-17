//! # ITK IPC
//!
//! Cross-platform IPC channels for the Injection Toolkit.
//!
//! This crate provides:
//! - Platform-agnostic IPC channel abstraction
//! - Async support via tokio
//! - Message framing with the ITK protocol
//!
//! ## Platform Support
//!
//! - **Windows**: Named pipes via `\\.\pipe\itk_*`
//! - **Linux**: Unix domain sockets via `/tmp/itk_*.sock`

use itk_protocol::{Header, HEADER_SIZE};
use std::io;
use thiserror::Error;

/// IPC errors
#[derive(Error, Debug)]
pub enum IpcError {
    #[error("connection failed: {0}")]
    ConnectionFailed(String),

    #[error("channel closed")]
    ChannelClosed,

    #[error("timeout waiting for connection")]
    Timeout,

    #[error("invalid channel name: {0}")]
    InvalidName(String),

    #[error("protocol error: {0}")]
    Protocol(#[from] itk_protocol::ProtocolError),

    #[error("IO error: {0}")]
    Io(#[from] io::Error),

    #[error("already listening")]
    AlreadyListening,

    #[error("not connected")]
    NotConnected,

    #[error("platform error: {0}")]
    Platform(String),
}

/// Result type for IPC operations
pub type Result<T> = std::result::Result<T, IpcError>;

/// IPC channel trait for platform-agnostic messaging
pub trait IpcChannel: Send + Sync {
    /// Send raw bytes over the channel
    fn send(&self, data: &[u8]) -> Result<()>;

    /// Receive raw bytes from the channel
    ///
    /// Blocks until data is available or the channel is closed.
    fn recv(&self) -> Result<Vec<u8>>;

    /// Try to receive without blocking
    ///
    /// Returns None if no data is available.
    fn try_recv(&self) -> Result<Option<Vec<u8>>>;

    /// Check if the channel is connected
    fn is_connected(&self) -> bool;

    /// Close the channel
    fn close(&self);
}

// Note: Async IPC support can be added in the future via a feature flag

/// IPC server that accepts connections
pub trait IpcServer: Send + Sync {
    /// The channel type returned when accepting connections
    type Channel: IpcChannel;

    /// Accept a new connection
    ///
    /// Blocks until a client connects.
    fn accept(&self) -> Result<Self::Channel>;

    /// Stop listening and close the server
    fn close(&self);
}

/// Create a platform-appropriate channel name
pub fn make_channel_name(base_name: &str) -> String {
    cfg_if::cfg_if! {
        if #[cfg(windows)] {
            format!(r"\\.\pipe\itk_{}", base_name)
        } else {
            format!("/tmp/itk_{}.sock", base_name)
        }
    }
}

// Platform-specific implementations
cfg_if::cfg_if! {
    if #[cfg(windows)] {
        mod windows_impl;
        pub use windows_impl::{NamedPipeClient, NamedPipeServer};

        /// Create a client channel connected to the given name
        pub fn connect(name: &str) -> Result<impl IpcChannel> {
            windows_impl::NamedPipeClient::connect(name)
        }

        /// Create a server listening on the given name
        pub fn listen(name: &str) -> Result<impl IpcServer> {
            windows_impl::NamedPipeServer::new(name)
        }
    } else if #[cfg(unix)] {
        mod unix_impl;
        pub use unix_impl::{UnixSocketClient, UnixSocketServer, UnixSocketConnection};

        /// Create a client channel connected to the given name
        pub fn connect(name: &str) -> Result<UnixSocketClient> {
            unix_impl::UnixSocketClient::connect(name)
        }

        /// Create a server listening on the given name
        pub fn listen(name: &str) -> Result<UnixSocketServer> {
            unix_impl::UnixSocketServer::new(name)
        }
    }
}

/// Helper for reading length-prefixed messages
pub fn read_message(reader: &mut impl io::Read) -> Result<Vec<u8>> {
    // Read header first
    let mut header_buf = [0u8; HEADER_SIZE];
    reader.read_exact(&mut header_buf)?;

    let header = Header::from_bytes(&header_buf)?;

    // Read payload
    let mut payload = vec![0u8; header.payload_len as usize];
    reader.read_exact(&mut payload)?;

    // Return full message (header + payload)
    let mut message = Vec::with_capacity(HEADER_SIZE + payload.len());
    message.extend_from_slice(&header_buf);
    message.extend_from_slice(&payload);

    Ok(message)
}

/// Helper for writing length-prefixed messages
pub fn write_message(writer: &mut impl io::Write, data: &[u8]) -> Result<()> {
    writer.write_all(data)?;
    writer.flush()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_channel_name_format() {
        let name = make_channel_name("test");

        #[cfg(windows)]
        assert!(name.starts_with(r"\\.\pipe\itk_"));

        #[cfg(unix)]
        assert!(name.starts_with("/tmp/itk_") && name.ends_with(".sock"));
    }
}
