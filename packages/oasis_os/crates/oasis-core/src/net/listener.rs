//! Remote terminal listener.
//!
//! Accepts inbound TCP connections, authenticates via pre-shared key,
//! and feeds received command lines into the command interpreter.
//! Designed for non-blocking polling from the main loop.

use crate::backend::{NetworkBackend, NetworkStream};
use crate::error::{OasisError, Result};

/// Maximum number of simultaneous remote connections.
const DEFAULT_MAX_CONNECTIONS: usize = 4;

/// Maximum bytes in a single input line.
const MAX_LINE_LEN: usize = 1024;

/// Authentication state for a connection.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum AuthState {
    /// Waiting for client to send the PSK.
    AwaitingAuth,
    /// Authenticated and ready for commands.
    Authenticated,
}

/// A single remote client connection.
struct RemoteConnection {
    stream: Box<dyn NetworkStream>,
    auth: AuthState,
    /// Accumulates partial line data between polls.
    read_buf: Vec<u8>,
}

impl RemoteConnection {
    fn new(stream: Box<dyn NetworkStream>) -> Self {
        Self {
            stream,
            auth: AuthState::AwaitingAuth,
            read_buf: Vec::with_capacity(256),
        }
    }
}

/// Configuration for the remote terminal listener.
#[derive(Debug, Clone)]
pub struct ListenerConfig {
    /// Port to listen on.
    pub port: u16,
    /// Pre-shared key for authentication (empty = no auth required).
    pub psk: String,
    /// Maximum simultaneous connections.
    pub max_connections: usize,
}

impl Default for ListenerConfig {
    fn default() -> Self {
        Self {
            port: 9000,
            psk: String::new(),
            max_connections: DEFAULT_MAX_CONNECTIONS,
        }
    }
}

/// Remote terminal listener that manages inbound connections.
///
/// Call `poll()` each frame from the main loop. It returns command lines
/// received from authenticated clients along with responses to send back.
pub struct RemoteListener {
    config: ListenerConfig,
    connections: Vec<RemoteConnection>,
    listening: bool,
}

impl RemoteListener {
    /// Create a new listener with the given configuration.
    pub fn new(config: ListenerConfig) -> Self {
        Self {
            config,
            connections: Vec::new(),
            listening: false,
        }
    }

    /// Start listening on the configured port.
    pub fn start(&mut self, backend: &mut dyn NetworkBackend) -> Result<()> {
        backend.listen(self.config.port)?;
        self.listening = true;
        Ok(())
    }

    /// Whether the listener is active.
    pub fn is_listening(&self) -> bool {
        self.listening
    }

    /// Number of active connections.
    pub fn connection_count(&self) -> usize {
        self.connections.len()
    }

    /// Poll for new connections and incoming data.
    ///
    /// Returns a list of (command_line, connection_index) pairs from
    /// authenticated clients. After executing commands, call
    /// `send_response()` to return output to the client.
    pub fn poll(&mut self, backend: &mut dyn NetworkBackend) -> Vec<(String, usize)> {
        if !self.listening {
            return Vec::new();
        }

        // Accept new connections.
        if self.connections.len() < self.config.max_connections {
            match backend.accept() {
                Ok(Some(stream)) => {
                    let mut conn = RemoteConnection::new(stream);
                    if self.config.psk.is_empty() {
                        // No auth required.
                        conn.auth = AuthState::Authenticated;
                        let _ = conn.stream.write(b"OASIS_OS remote terminal\n> ");
                    } else {
                        let _ = conn.stream.write(b"AUTH_REQUIRED\n");
                    }
                    self.connections.push(conn);
                },
                Ok(None) => {},
                Err(e) => log::warn!("accept error: {e}"),
            }
        }

        // Read from all connections.
        let mut commands = Vec::new();
        let mut to_remove = Vec::new();

        for (idx, conn) in self.connections.iter_mut().enumerate() {
            let mut buf = [0u8; 512];
            match conn.stream.read(&mut buf) {
                Ok(0) => {
                    // Connection closed or no data (non-blocking).
                },
                Ok(n) => {
                    conn.read_buf.extend_from_slice(&buf[..n]);

                    // Check for disconnect (0-length read means EOF on blocking,
                    // but for non-blocking it returns WouldBlock -> mapped to 0).
                    // We detect actual EOF when the stream errors on write.

                    // Process complete lines.
                    while let Some(newline_pos) = conn.read_buf.iter().position(|&b| b == b'\n') {
                        let line_bytes: Vec<u8> = conn.read_buf.drain(..=newline_pos).collect();
                        let line = String::from_utf8_lossy(&line_bytes).trim().to_string();

                        if line.is_empty() {
                            continue;
                        }

                        match conn.auth {
                            AuthState::AwaitingAuth => {
                                if line == self.config.psk {
                                    conn.auth = AuthState::Authenticated;
                                    let _ = conn.stream.write(b"AUTH_OK\n> ");
                                } else {
                                    let _ = conn.stream.write(b"AUTH_FAIL\n");
                                    to_remove.push(idx);
                                }
                            },
                            AuthState::Authenticated => {
                                if line == "quit" || line == "exit" {
                                    let _ = conn.stream.write(b"Goodbye.\n");
                                    to_remove.push(idx);
                                } else {
                                    commands.push((line, idx));
                                }
                            },
                        }
                    }

                    // Guard against overlong lines.
                    if conn.read_buf.len() > MAX_LINE_LEN {
                        conn.read_buf.clear();
                        let _ = conn.stream.write(b"error: line too long\n> ");
                    }
                },
                Err(e) => {
                    log::debug!("connection {idx} read error: {e}");
                    to_remove.push(idx);
                },
            }
        }

        // Remove closed/failed connections (in reverse to preserve indices).
        to_remove.sort_unstable();
        to_remove.dedup();
        for idx in to_remove.into_iter().rev() {
            let mut conn = self.connections.remove(idx);
            let _ = conn.stream.close();
        }

        commands
    }

    /// Send command output back to a specific client.
    pub fn send_response(&mut self, conn_idx: usize, text: &str) -> Result<()> {
        let conn = self
            .connections
            .get_mut(conn_idx)
            .ok_or_else(|| OasisError::Backend("invalid connection index".to_string()))?;
        conn.stream
            .write(text.as_bytes())
            .map_err(|e| OasisError::Backend(format!("send: {e}")))?;
        conn.stream
            .write(b"\n> ")
            .map_err(|e| OasisError::Backend(format!("send prompt: {e}")))?;
        Ok(())
    }

    /// Shut down all connections and stop listening.
    pub fn stop(&mut self) {
        for conn in &mut self.connections {
            let _ = conn.stream.write(b"\nServer shutting down.\n");
            let _ = conn.stream.close();
        }
        self.connections.clear();
        self.listening = false;
    }
}
