//! Unix domain socket implementation

use super::{IpcChannel, IpcError, IpcServer, Result, read_message};
use std::fs;
use std::io::Write;
use std::os::unix::net::{UnixListener, UnixStream};
use std::sync::Mutex;
use std::sync::atomic::{AtomicBool, Ordering};

/// Validate and create a socket path from a name.
///
/// For security, this function:
/// - Rejects names with path traversal sequences (..)
/// - Rejects absolute paths (prevents arbitrary file operations)
/// - Creates paths only in /tmp/itk_*.sock
fn make_socket_path(name: &str) -> Result<String> {
    // Reject path traversal attempts
    if name.contains("..") {
        return Err(IpcError::Platform(
            "socket name cannot contain path traversal sequences".into(),
        ));
    }

    // Reject absolute paths - prevents arbitrary file deletion/creation
    if name.starts_with('/') {
        return Err(IpcError::Platform(
            "socket name cannot be an absolute path".into(),
        ));
    }

    // Reject names with slashes to prevent subdirectory traversal
    if name.contains('/') || name.contains('\\') {
        return Err(IpcError::Platform(
            "socket name cannot contain path separators".into(),
        ));
    }

    Ok(format!("/tmp/itk_{}.sock", name))
}

/// Safely remove a socket file, verifying it's actually a socket first.
///
/// Uses symlink_metadata to avoid following symlinks, preventing any
/// interaction with symlink targets.
fn remove_socket_file(path: &str) {
    // Use symlink_metadata to not follow symlinks - strictly safer
    if let Ok(metadata) = fs::symlink_metadata(path) {
        use std::os::unix::fs::FileTypeExt;
        if metadata.file_type().is_socket() {
            let _ = fs::remove_file(path);
        }
        // If it's not a socket, don't remove it - could be a regular file
    }
    // If metadata fails (file doesn't exist), that's fine
}

/// Non-blocking receive helper that keeps the lock held while consuming data.
///
/// This prevents race conditions where another thread could consume data between
/// peeking and actually reading.
fn try_recv_with_fd(fd: std::os::unix::io::RawFd) -> Result<Option<Vec<u8>>> {
    use itk_protocol::HEADER_SIZE;

    // Use MSG_PEEK to check if enough data is available without consuming bytes.
    let mut peek_buf = [0u8; HEADER_SIZE];
    let peeked = unsafe {
        libc::recv(
            fd,
            peek_buf.as_mut_ptr() as *mut libc::c_void,
            HEADER_SIZE,
            libc::MSG_PEEK | libc::MSG_DONTWAIT,
        )
    };

    if peeked < 0 {
        let err = std::io::Error::last_os_error();
        if err.kind() == std::io::ErrorKind::WouldBlock
            || err.kind() == std::io::ErrorKind::Interrupted
        {
            return Ok(None);
        }
        return Err(IpcError::Io(err));
    }

    // recv returning 0 means EOF (connection closed)
    if peeked == 0 {
        return Err(IpcError::ChannelClosed);
    }

    if (peeked as usize) < HEADER_SIZE {
        // Partial header available - not enough data yet
        return Ok(None);
    }

    // Parse header to determine total message size
    let header = itk_protocol::Header::from_bytes(&peek_buf).map_err(IpcError::Protocol)?;
    let total_size = HEADER_SIZE + header.payload_len as usize;

    // Peek again to check if full message is available
    let mut message = vec![0u8; total_size];
    let peeked_full = unsafe {
        libc::recv(
            fd,
            message.as_mut_ptr() as *mut libc::c_void,
            total_size,
            libc::MSG_PEEK | libc::MSG_DONTWAIT,
        )
    };

    if peeked_full < 0 {
        let err = std::io::Error::last_os_error();
        if err.kind() == std::io::ErrorKind::WouldBlock
            || err.kind() == std::io::ErrorKind::Interrupted
        {
            return Ok(None);
        }
        return Err(IpcError::Io(err));
    }

    if (peeked_full as usize) < total_size {
        return Ok(None);
    }

    // Full message is available - consume it (we still hold the lock in the caller)
    let received = unsafe {
        libc::recv(
            fd,
            message.as_mut_ptr() as *mut libc::c_void,
            total_size,
            0, // Blocking read, but we know data is available
        )
    };

    if received < 0 {
        let err = std::io::Error::last_os_error();
        // EINTR on final recv is unusual but handle it by reporting no data available
        if err.kind() == std::io::ErrorKind::Interrupted {
            return Ok(None);
        }
        return Err(IpcError::Io(err));
    }

    if (received as usize) != total_size {
        return Err(IpcError::Protocol(
            itk_protocol::ProtocolError::IncompletePayload {
                need: total_size - itk_protocol::HEADER_SIZE,
                have: (received as usize).saturating_sub(itk_protocol::HEADER_SIZE),
            },
        ));
    }

    Ok(Some(message))
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
        let path = make_socket_path(name)?;

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
        use std::os::unix::io::AsRawFd;

        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        // Keep lock held during entire operation to prevent race conditions
        let stream = self.stream.lock().unwrap();
        let fd = stream.as_raw_fd();
        try_recv_with_fd(fd)
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
        let path = make_socket_path(name)?;

        // Safely remove existing socket file if present (verifies it's actually a socket)
        remove_socket_file(&path);

        // Set restrictive umask before creating socket to prevent race condition.
        // Without this, the socket would briefly exist with default permissions
        // (potentially allowing other users to connect) before set_permissions runs.
        let old_umask = unsafe { libc::umask(0o077) };

        let bind_result = UnixListener::bind(&path);

        // Restore original umask immediately after bind
        unsafe {
            libc::umask(old_umask);
        }

        let listener = bind_result.map_err(|e| IpcError::Platform(e.to_string()))?;

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
        // Clean up socket file (verify it's actually a socket before deletion)
        remove_socket_file(&self.path);
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
        use std::os::unix::io::AsRawFd;

        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        // Keep lock held during entire operation to prevent race conditions
        let stream = self.stream.lock().unwrap();
        let fd = stream.as_raw_fd();
        try_recv_with_fd(fd)
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
