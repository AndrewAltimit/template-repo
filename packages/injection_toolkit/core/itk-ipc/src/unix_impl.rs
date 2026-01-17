//! Unix domain socket implementation

use super::{read_message, IpcChannel, IpcError, IpcServer, Result};
use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::os::unix::net::{UnixListener, UnixStream};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;

fn make_socket_path(name: &str) -> String {
    if name.starts_with('/') {
        name.to_string()
    } else {
        format!("/tmp/itk_{}.sock", name)
    }
}

/// Unix domain socket client
pub struct UnixSocketClient {
    stream: Mutex<UnixStream>,
    connected: AtomicBool,
    #[allow(dead_code)]
    path: String,
}

impl UnixSocketClient {
    /// Connect to a Unix socket server
    pub fn connect(name: &str) -> Result<Self> {
        let path = make_socket_path(name);

        let stream =
            UnixStream::connect(&path).map_err(|e| IpcError::ConnectionFailed(e.to_string()))?;

        Ok(Self {
            stream: Mutex::new(stream),
            connected: AtomicBool::new(true),
            path,
        })
    }
}

impl IpcChannel for UnixSocketClient {
    fn send(&self, data: &[u8]) -> Result<()> {
        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        let mut stream = self.stream.lock().unwrap();
        stream.write_all(data)?;
        stream.flush()?;

        Ok(())
    }

    fn recv(&self) -> Result<Vec<u8>> {
        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        let mut stream = self.stream.lock().unwrap();
        read_message(&mut *stream)
    }

    fn try_recv(&self) -> Result<Option<Vec<u8>>> {
        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        let mut stream = self.stream.lock().unwrap();

        // Set non-blocking temporarily
        stream.set_nonblocking(true)?;
        let result = read_message(&mut *stream);
        stream.set_nonblocking(false)?;

        match result {
            Ok(data) => Ok(Some(data)),
            Err(IpcError::Io(ref e)) if e.kind() == std::io::ErrorKind::WouldBlock => Ok(None),
            Err(e) => Err(e),
        }
    }

    fn is_connected(&self) -> bool {
        self.connected.load(Ordering::SeqCst)
    }

    fn close(&self) {
        if self.connected.swap(false, Ordering::SeqCst) {
            if let Ok(stream) = self.stream.lock() {
                let _ = stream.shutdown(std::net::Shutdown::Both);
            }
        }
    }
}

impl Drop for UnixSocketClient {
    fn drop(&mut self) {
        self.close();
    }
}

/// Unix domain socket server
pub struct UnixSocketServer {
    listener: UnixListener,
    path: String,
    listening: AtomicBool,
}

impl UnixSocketServer {
    /// Create a new Unix socket server
    ///
    /// The socket is created with restricted permissions (0o600) to prevent
    /// other users on the system from connecting.
    pub fn new(name: &str) -> Result<Self> {
        let path = make_socket_path(name);

        // Remove existing socket file if present
        let _ = fs::remove_file(&path);

        let listener = UnixListener::bind(&path).map_err(|e| IpcError::Platform(e.to_string()))?;

        // Set restrictive permissions (owner read/write only)
        // This prevents other users from injecting commands into the daemon
        if let Err(e) = fs::set_permissions(&path, fs::Permissions::from_mode(0o600)) {
            tracing::warn!(?e, "Failed to set socket permissions");
        }

        Ok(Self {
            listener,
            path,
            listening: AtomicBool::new(true),
        })
    }
}

impl IpcServer for UnixSocketServer {
    type Channel = UnixSocketConnection;

    fn accept(&self) -> Result<Self::Channel> {
        if !self.listening.load(Ordering::SeqCst) {
            return Err(IpcError::ChannelClosed);
        }

        let (stream, _addr) = self
            .listener
            .accept()
            .map_err(|e| IpcError::ConnectionFailed(e.to_string()))?;

        Ok(UnixSocketConnection {
            stream: Mutex::new(stream),
            connected: AtomicBool::new(true),
        })
    }

    fn close(&self) {
        self.listening.store(false, Ordering::SeqCst);
        // The listener will be cleaned up on drop
    }
}

impl Drop for UnixSocketServer {
    fn drop(&mut self) {
        self.close();
        // Clean up socket file
        let _ = std::fs::remove_file(&self.path);
    }
}

/// A connected Unix socket (server-side)
pub struct UnixSocketConnection {
    stream: Mutex<UnixStream>,
    connected: AtomicBool,
}

impl IpcChannel for UnixSocketConnection {
    fn send(&self, data: &[u8]) -> Result<()> {
        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        let mut stream = self.stream.lock().unwrap();
        stream.write_all(data)?;
        stream.flush()?;

        Ok(())
    }

    fn recv(&self) -> Result<Vec<u8>> {
        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        let mut stream = self.stream.lock().unwrap();
        read_message(&mut *stream)
    }

    fn try_recv(&self) -> Result<Option<Vec<u8>>> {
        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        let mut stream = self.stream.lock().unwrap();

        stream.set_nonblocking(true)?;
        let result = read_message(&mut *stream);
        stream.set_nonblocking(false)?;

        match result {
            Ok(data) => Ok(Some(data)),
            Err(IpcError::Io(ref e)) if e.kind() == std::io::ErrorKind::WouldBlock => Ok(None),
            Err(e) => Err(e),
        }
    }

    fn is_connected(&self) -> bool {
        self.connected.load(Ordering::SeqCst)
    }

    fn close(&self) {
        if self.connected.swap(false, Ordering::SeqCst) {
            if let Ok(stream) = self.stream.lock() {
                let _ = stream.shutdown(std::net::Shutdown::Both);
            }
        }
    }
}

impl Drop for UnixSocketConnection {
    fn drop(&mut self) {
        self.close();
    }
}
