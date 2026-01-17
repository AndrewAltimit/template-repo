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

/// Integration tests for IPC communication
/// These tests use actual OS sockets/pipes with proper protocol framing
#[cfg(test)]
mod integration_tests {
    use super::*;
    use itk_protocol::{encode, decode, MessageType};
    use rand::Rng;
    use std::thread;
    use std::time::Duration;

    /// Generate a unique channel name for testing
    fn test_channel_name() -> String {
        let id: u32 = rand::thread_rng().gen();
        format!("itk_test_{}", id)
    }

    #[test]
    #[cfg(unix)]
    fn test_unix_socket_ping_pong() {
        let channel_name = test_channel_name();
        let channel_name_client = channel_name.clone();

        // Start server in background thread
        let server_handle = thread::spawn(move || {
            let server = listen(&channel_name).expect("Failed to create server");
            let conn = server.accept().expect("Failed to accept connection");

            // Receive message (should be a Ping)
            let msg = conn.recv().expect("Failed to receive");
            let (msg_type, _): (MessageType, ()) = decode(&msg).expect("Failed to decode");
            assert_eq!(msg_type, MessageType::Ping);

            // Send Pong response
            let pong = encode(MessageType::Pong, &()).expect("Failed to encode");
            conn.send(&pong).expect("Failed to send");
        });

        // Give server time to start
        thread::sleep(Duration::from_millis(50));

        // Connect client
        let client = connect(&channel_name_client).expect("Failed to connect");

        // Send ping with proper protocol framing
        let ping = encode(MessageType::Ping, &()).expect("Failed to encode");
        client.send(&ping).expect("Failed to send");

        // Receive pong
        let response = client.recv().expect("Failed to receive");
        let (msg_type, _): (MessageType, ()) = decode(&response).expect("Failed to decode");
        assert_eq!(msg_type, MessageType::Pong);

        server_handle.join().expect("Server thread panicked");
    }

    #[test]
    #[cfg(unix)]
    fn test_unix_socket_screen_rect() {
        use itk_protocol::ScreenRect;

        let channel_name = test_channel_name();
        let channel_name_client = channel_name.clone();

        let server_handle = thread::spawn(move || {
            let server = listen(&channel_name).expect("Failed to create server");
            let conn = server.accept().expect("Failed to accept");

            let msg = conn.recv().expect("Failed to receive");
            let (msg_type, rect): (MessageType, ScreenRect) = decode(&msg).expect("Failed to decode");

            assert_eq!(msg_type, MessageType::ScreenRect);
            assert_eq!(rect.x, 100.0);
            assert_eq!(rect.y, 200.0);
            assert_eq!(rect.width, 640.0);
            assert_eq!(rect.height, 480.0);

            // Acknowledge
            let pong = encode(MessageType::Pong, &()).expect("Failed to encode");
            conn.send(&pong).expect("Failed to send");
        });

        thread::sleep(Duration::from_millis(50));

        let client = connect(&channel_name_client).expect("Failed to connect");

        let rect = ScreenRect {
            x: 100.0,
            y: 200.0,
            width: 640.0,
            height: 480.0,
            rotation: 0.0,
            visible: true,
        };
        let msg = encode(MessageType::ScreenRect, &rect).expect("Failed to encode");
        client.send(&msg).expect("Failed to send");

        let response = client.recv().expect("Failed to receive");
        let (msg_type, _): (MessageType, ()) = decode(&response).expect("Failed to decode");
        assert_eq!(msg_type, MessageType::Pong);

        server_handle.join().expect("Server thread panicked");
    }

    #[test]
    #[cfg(unix)]
    fn test_unix_socket_multiple_pings() {
        let channel_name = test_channel_name();
        let channel_name_client = channel_name.clone();

        let server_handle = thread::spawn(move || {
            let server = listen(&channel_name).expect("Failed to create server");
            let conn = server.accept().expect("Failed to accept");

            for _ in 0..5 {
                let msg = conn.recv().expect("Failed to receive");
                let (msg_type, _): (MessageType, ()) = decode(&msg).expect("Failed to decode");
                assert_eq!(msg_type, MessageType::Ping);
            }

            let pong = encode(MessageType::Pong, &()).expect("Failed to encode");
            conn.send(&pong).expect("Failed to send");
        });

        thread::sleep(Duration::from_millis(50));

        let client = connect(&channel_name_client).expect("Failed to connect");

        for _ in 0..5 {
            let ping = encode(MessageType::Ping, &()).expect("Failed to encode");
            client.send(&ping).expect("Failed to send");
        }

        let response = client.recv().expect("Failed to receive");
        let (msg_type, _): (MessageType, ()) = decode(&response).expect("Failed to decode");
        assert_eq!(msg_type, MessageType::Pong);

        server_handle.join().expect("Server thread panicked");
    }
}
