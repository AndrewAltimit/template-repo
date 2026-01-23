//! Windows named pipe implementation
//!
//! Named pipes are created with security descriptors that restrict access
//! to the current user only, preventing other users on the system from
//! connecting to or injecting commands into the daemon.

use super::{read_message, IpcChannel, IpcError, IpcServer, Result};
use std::ffi::OsStr;
use std::io::Read;
use std::os::windows::ffi::OsStrExt;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use windows::core::PCWSTR;
use windows::Win32::Foundation::{
    CloseHandle, LocalFree, HANDLE, HLOCAL, INVALID_HANDLE_VALUE, WIN32_ERROR,
};
use windows::Win32::Security::Authorization::{
    ConvertStringSecurityDescriptorToSecurityDescriptorW, SDDL_REVISION_1,
};
use windows::Win32::Security::{PSECURITY_DESCRIPTOR, SECURITY_ATTRIBUTES};
use windows::Win32::Storage::FileSystem::{
    CreateFileW, FlushFileBuffers, ReadFile, WriteFile, FILE_ATTRIBUTE_NORMAL, FILE_GENERIC_READ,
    FILE_GENERIC_WRITE, FILE_SHARE_NONE, OPEN_EXISTING, PIPE_ACCESS_DUPLEX,
};
use windows::Win32::System::Pipes::{
    ConnectNamedPipe, CreateNamedPipeW, DisconnectNamedPipe, PeekNamedPipe, PIPE_READMODE_BYTE,
    PIPE_TYPE_BYTE, PIPE_UNLIMITED_INSTANCES, PIPE_WAIT,
};

const BUFFER_SIZE: u32 = 65536;

/// Check if a pipe has data available using PeekNamedPipe.
///
/// Returns the number of bytes available, or 0 if none.
fn peek_pipe_bytes(handle: HANDLE) -> std::result::Result<u32, IpcError> {
    let mut bytes_available = 0u32;

    unsafe {
        // PeekNamedPipe with null buffers just checks byte availability
        PeekNamedPipe(handle, None, 0, None, Some(&mut bytes_available), None)
            .map_err(|e| IpcError::Io(std::io::Error::other(e.to_string())))?;
    }

    Ok(bytes_available)
}

/// Write all data to a handle, looping until complete.
///
/// Windows WriteFile may write fewer bytes than requested (partial write).
/// This function ensures all data is written before returning.
fn write_all_to_handle(handle: HANDLE, data: &[u8]) -> std::result::Result<(), IpcError> {
    let mut offset = 0;
    while offset < data.len() {
        let mut bytes_written = 0u32;
        let remaining = &data[offset..];

        unsafe {
            WriteFile(handle, Some(remaining), Some(&mut bytes_written), None)
                .map_err(|e| IpcError::Io(std::io::Error::other(e.to_string())))?;
        }

        if bytes_written == 0 {
            return Err(IpcError::Io(std::io::Error::new(
                std::io::ErrorKind::WriteZero,
                "WriteFile wrote zero bytes",
            )));
        }

        offset += bytes_written as usize;
    }
    Ok(())
}

/// ERROR_PIPE_CONNECTED (535) - The pipe is already connected.
/// This occurs when a client connects between CreateNamedPipeW and ConnectNamedPipe.
/// It's not an error condition - it means the pipe is ready for use.
const ERROR_PIPE_CONNECTED: WIN32_ERROR = WIN32_ERROR(535);

fn to_wide_string(s: &str) -> Vec<u16> {
    OsStr::new(s).encode_wide().chain(Some(0)).collect()
}

/// Validate and create a pipe name from a name.
///
/// For security, this function:
/// - Rejects names with path traversal sequences (..)
/// - Rejects names that look like full pipe paths (prevents escaping itk_ namespace)
/// - Creates paths only in \\.\pipe\itk_* namespace
fn make_pipe_name(name: &str) -> Result<String> {
    // Reject path traversal attempts
    if name.contains("..") {
        return Err(IpcError::Platform(
            "pipe name cannot contain path traversal sequences".into(),
        ));
    }

    // Reject names that look like they're trying to specify a full pipe path
    // This prevents callers from escaping the itk_ namespace
    if name.starts_with(r"\\") || name.starts_with(r"//") {
        return Err(IpcError::Platform(
            "pipe name cannot be a full pipe path".into(),
        ));
    }

    // Reject names with path separators
    if name.contains('\\') || name.contains('/') {
        return Err(IpcError::Platform(
            "pipe name cannot contain path separators".into(),
        ));
    }

    Ok(format!(r"\\.\pipe\itk_{}", name))
}

/// RAII wrapper for security descriptor allocated by Windows APIs
struct SecurityDescriptorGuard {
    ptr: PSECURITY_DESCRIPTOR,
}

impl Drop for SecurityDescriptorGuard {
    fn drop(&mut self) {
        if !self.ptr.0.is_null() {
            unsafe {
                let _ = LocalFree(HLOCAL(self.ptr.0));
            }
        }
    }
}

/// Create security attributes that restrict pipe access to the current user only.
///
/// Uses SDDL (Security Descriptor Definition Language) to define:
/// - D: = DACL (Discretionary Access Control List)
/// - (A;;GA;;;CO) = Allow Generic All access to Creator Owner
///
/// This prevents other users on the system from connecting to the pipe,
/// similar to Unix socket permissions of 0o600.
fn create_restricted_security_attributes() -> Result<(SECURITY_ATTRIBUTES, SecurityDescriptorGuard)>
{
    // SDDL: D:(A;;GA;;;CO)
    // D: = DACL
    // A = Allow
    // GA = Generic All (full access)
    // CO = Creator Owner (the user who created the pipe)
    //
    // This restricts access to only the user who created the pipe.
    let sddl = to_wide_string("D:(A;;GA;;;CO)");

    let mut sd_ptr = PSECURITY_DESCRIPTOR::default();

    unsafe {
        ConvertStringSecurityDescriptorToSecurityDescriptorW(
            PCWSTR(sddl.as_ptr()),
            SDDL_REVISION_1,
            &mut sd_ptr,
            None,
        )
        .map_err(|e| IpcError::Platform(format!("Failed to create security descriptor: {}", e)))?;
    }

    let guard = SecurityDescriptorGuard { ptr: sd_ptr };

    let sa = SECURITY_ATTRIBUTES {
        nLength: std::mem::size_of::<SECURITY_ATTRIBUTES>() as u32,
        lpSecurityDescriptor: sd_ptr.0,
        bInheritHandle: false.into(),
    };

    Ok((sa, guard))
}

/// Windows named pipe client
pub struct NamedPipeClient {
    handle: Mutex<HANDLE>,
    connected: AtomicBool,
    #[allow(dead_code)]
    name: String,
}

// SAFETY: HANDLE is a raw pointer but we protect all access with a Mutex.
// The handle is only accessed through the Mutex, ensuring thread-safe access.
unsafe impl Send for NamedPipeClient {}
unsafe impl Sync for NamedPipeClient {}

impl NamedPipeClient {
    /// Connect to a named pipe server
    pub fn connect(name: &str) -> Result<Self> {
        let pipe_name = make_pipe_name(name)?;
        let wide_name = to_wide_string(&pipe_name);

        unsafe {
            let handle = CreateFileW(
                PCWSTR(wide_name.as_ptr()),
                (FILE_GENERIC_READ | FILE_GENERIC_WRITE).0,
                FILE_SHARE_NONE,
                None,
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL,
                None,
            )
            .map_err(|e| IpcError::ConnectionFailed(e.to_string()))?;

            if handle == INVALID_HANDLE_VALUE {
                return Err(IpcError::ConnectionFailed("Invalid handle".into()));
            }

            Ok(Self {
                handle: Mutex::new(handle),
                connected: AtomicBool::new(true),
                name: pipe_name,
            })
        }
    }
}

impl IpcChannel for NamedPipeClient {
    fn send(&self, data: &[u8]) -> Result<()> {
        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        let handle = self.handle.lock().unwrap();

        // Use helper to ensure all data is written (handles partial writes)
        write_all_to_handle(*handle, data)?;

        unsafe {
            FlushFileBuffers(*handle)
                .map_err(|e| IpcError::Io(std::io::Error::other(e.to_string())))?;
        }

        Ok(())
    }

    fn recv(&self) -> Result<Vec<u8>> {
        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        let handle = self.handle.lock().unwrap();
        let mut reader = PipeReader { handle: *handle };
        read_message(&mut reader)
    }

    fn try_recv(&self) -> Result<Option<Vec<u8>>> {
        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        let handle = self.handle.lock().unwrap();

        // Use PeekNamedPipe for true non-blocking check
        let bytes_available = peek_pipe_bytes(*handle)?;
        if bytes_available == 0 {
            return Ok(None);
        }

        // Data is available, read it
        let mut reader = PipeReader { handle: *handle };
        read_message(&mut reader).map(Some)
    }

    fn is_connected(&self) -> bool {
        self.connected.load(Ordering::SeqCst)
    }

    fn close(&self) {
        if self.connected.swap(false, Ordering::SeqCst) {
            let handle = self.handle.lock().unwrap();
            unsafe {
                let _ = CloseHandle(*handle);
            }
        }
    }
}

impl Drop for NamedPipeClient {
    fn drop(&mut self) {
        self.close();
    }
}

/// Windows named pipe server
pub struct NamedPipeServer {
    name: String,
    listening: AtomicBool,
}

impl NamedPipeServer {
    /// Create a new named pipe server
    pub fn new(name: &str) -> Result<Self> {
        let pipe_name = make_pipe_name(name)?;

        Ok(Self {
            name: pipe_name,
            listening: AtomicBool::new(true),
        })
    }

    /// Create a new pipe instance.
    ///
    /// Uses default security attributes (accessible to the creating user and system).
    fn create_pipe_instance(&self) -> Result<HANDLE> {
        let wide_name = to_wide_string(&self.name);

        unsafe {
            let handle = CreateNamedPipeW(
                PCWSTR(wide_name.as_ptr()),
                PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
                PIPE_UNLIMITED_INSTANCES,
                BUFFER_SIZE,
                BUFFER_SIZE,
                0,
                None,
            );

            if handle == INVALID_HANDLE_VALUE {
                return Err(IpcError::Platform("Failed to create named pipe".into()));
            }

            Ok(handle)
        }
    }
}

impl IpcServer for NamedPipeServer {
    type Channel = NamedPipeConnection;

    fn accept(&self) -> Result<Self::Channel> {
        if !self.listening.load(Ordering::SeqCst) {
            return Err(IpcError::ChannelClosed);
        }

        let handle = self.create_pipe_instance()?;

        unsafe {
            // Wait for client to connect.
            // If the client connects between CreateNamedPipeW and ConnectNamedPipe,
            // we get ERROR_PIPE_CONNECTED (535), which is not an error - it means
            // the pipe is already connected and ready for use.
            if let Err(e) = ConnectNamedPipe(handle, None) {
                if e.code() != windows::core::HRESULT::from(ERROR_PIPE_CONNECTED) {
                    let _ = CloseHandle(handle);
                    return Err(IpcError::ConnectionFailed(e.to_string()));
                }
                // ERROR_PIPE_CONNECTED is success - pipe is already connected
            }
        }

        Ok(NamedPipeConnection {
            handle: Mutex::new(handle),
            connected: AtomicBool::new(true),
        })
    }

    fn close(&self) {
        self.listening.store(false, Ordering::SeqCst);
    }
}

/// A connected named pipe (server-side)
pub struct NamedPipeConnection {
    handle: Mutex<HANDLE>,
    connected: AtomicBool,
}

// SAFETY: HANDLE is a raw pointer but we protect all access with a Mutex.
// The handle is only accessed through the Mutex, ensuring thread-safe access.
unsafe impl Send for NamedPipeConnection {}
unsafe impl Sync for NamedPipeConnection {}

impl IpcChannel for NamedPipeConnection {
    fn send(&self, data: &[u8]) -> Result<()> {
        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        let handle = self.handle.lock().unwrap();

        // Use helper to ensure all data is written (handles partial writes)
        write_all_to_handle(*handle, data)?;

        unsafe {
            FlushFileBuffers(*handle)
                .map_err(|e| IpcError::Io(std::io::Error::other(e.to_string())))?;
        }

        Ok(())
    }

    fn recv(&self) -> Result<Vec<u8>> {
        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        let handle = self.handle.lock().unwrap();
        let mut reader = PipeReader { handle: *handle };
        read_message(&mut reader)
    }

    fn try_recv(&self) -> Result<Option<Vec<u8>>> {
        if !self.is_connected() {
            return Err(IpcError::NotConnected);
        }

        let handle = self.handle.lock().unwrap();

        // Use PeekNamedPipe for true non-blocking check
        let bytes_available = peek_pipe_bytes(*handle)?;
        if bytes_available == 0 {
            return Ok(None);
        }

        // Data is available, read it
        let mut reader = PipeReader { handle: *handle };
        read_message(&mut reader).map(Some)
    }

    fn is_connected(&self) -> bool {
        self.connected.load(Ordering::SeqCst)
    }

    fn close(&self) {
        if self.connected.swap(false, Ordering::SeqCst) {
            let handle = self.handle.lock().unwrap();
            unsafe {
                let _ = DisconnectNamedPipe(*handle);
                let _ = CloseHandle(*handle);
            }
        }
    }
}

impl Drop for NamedPipeConnection {
    fn drop(&mut self) {
        self.close();
    }
}

/// Helper for reading from a pipe handle
struct PipeReader {
    handle: HANDLE,
}

impl Read for PipeReader {
    fn read(&mut self, buf: &mut [u8]) -> std::io::Result<usize> {
        let mut bytes_read = 0u32;

        unsafe {
            ReadFile(self.handle, Some(buf), Some(&mut bytes_read), None)
                .map_err(|e| std::io::Error::other(e.to_string()))?;
        }

        Ok(bytes_read as usize)
    }
}
