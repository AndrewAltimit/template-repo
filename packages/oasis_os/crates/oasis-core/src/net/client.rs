//! Remote terminal outbound client.
//!
//! Connects to a remote OASIS_OS instance (or any TCP text service),
//! sends commands, and receives output. Designed for non-blocking polling.

use crate::backend::{NetworkBackend, NetworkStream};
use crate::error::{OasisError, Result};

/// State of the remote client connection.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ClientState {
    /// Not connected.
    Disconnected,
    /// Connected but awaiting authentication response.
    Authenticating,
    /// Connected and authenticated (or no auth needed).
    Connected,
}

/// Outbound remote terminal client.
pub struct RemoteClient {
    stream: Option<Box<dyn NetworkStream>>,
    state: ClientState,
    /// Accumulates received data between polls.
    read_buf: Vec<u8>,
    /// Lines received from the remote side.
    received_lines: Vec<String>,
}

impl RemoteClient {
    pub fn new() -> Self {
        Self {
            stream: None,
            state: ClientState::Disconnected,
            read_buf: Vec::with_capacity(256),
            received_lines: Vec::new(),
        }
    }

    /// Current connection state.
    pub fn state(&self) -> ClientState {
        self.state
    }

    /// Connect to a remote host.
    pub fn connect(
        &mut self,
        backend: &mut dyn NetworkBackend,
        address: &str,
        port: u16,
        psk: Option<&str>,
    ) -> Result<()> {
        let stream = backend.connect(address, port)?;
        self.stream = Some(stream);

        if let Some(key) = psk {
            // Send PSK immediately.
            if let Some(ref mut s) = self.stream {
                s.write(format!("{key}\n").as_bytes())
                    .map_err(|e| OasisError::Backend(format!("auth send: {e}")))?;
            }
            self.state = ClientState::Authenticating;
        } else {
            self.state = ClientState::Connected;
        }

        Ok(())
    }

    /// Send a command line to the remote host.
    pub fn send(&mut self, line: &str) -> Result<()> {
        let stream = self
            .stream
            .as_mut()
            .ok_or_else(|| OasisError::Backend("not connected".to_string()))?;
        stream
            .write(format!("{line}\n").as_bytes())
            .map_err(|e| OasisError::Backend(format!("send: {e}")))?;
        Ok(())
    }

    /// Poll for received data from the remote host.
    /// Returns new lines received since last poll.
    pub fn poll(&mut self) -> Vec<String> {
        let Some(ref mut stream) = self.stream else {
            return Vec::new();
        };

        let mut buf = [0u8; 512];
        match stream.read(&mut buf) {
            Ok(0) => {},
            Ok(n) => {
                self.read_buf.extend_from_slice(&buf[..n]);

                // Extract complete lines.
                while let Some(pos) = self.read_buf.iter().position(|&b| b == b'\n') {
                    let line_bytes: Vec<u8> = self.read_buf.drain(..=pos).collect();
                    let line = String::from_utf8_lossy(&line_bytes).trim().to_string();

                    // Handle auth responses.
                    if self.state == ClientState::Authenticating {
                        if line == "AUTH_OK" {
                            self.state = ClientState::Connected;
                            continue;
                        } else if line == "AUTH_FAIL" {
                            self.disconnect();
                            self.received_lines
                                .push("Authentication failed.".to_string());
                            break;
                        }
                    }

                    if !line.is_empty() {
                        self.received_lines.push(line);
                    }
                }
            },
            Err(_) => {
                // Connection likely dropped.
                self.disconnect();
                self.received_lines.push("Connection lost.".to_string());
            },
        }

        std::mem::take(&mut self.received_lines)
    }

    /// Disconnect from the remote host.
    pub fn disconnect(&mut self) {
        if let Some(ref mut stream) = self.stream {
            let _ = stream.write(b"quit\n");
            let _ = stream.close();
        }
        self.stream = None;
        self.state = ClientState::Disconnected;
    }

    /// Whether we are currently connected.
    pub fn is_connected(&self) -> bool {
        self.state != ClientState::Disconnected
    }
}

impl Default for RemoteClient {
    fn default() -> Self {
        Self::new()
    }
}
