//! `std::net` implementation of `NetworkBackend` and `NetworkStream`.

use std::io::{self, Read, Write};
use std::net::{TcpListener, TcpStream};

use crate::backend::{NetworkBackend, NetworkStream};
use crate::error::{OasisError, Result};

/// Network backend using `std::net` for desktop and Raspberry Pi.
pub struct StdNetworkBackend {
    listener: Option<TcpListener>,
}

impl StdNetworkBackend {
    pub fn new() -> Self {
        Self { listener: None }
    }
}

impl Default for StdNetworkBackend {
    fn default() -> Self {
        Self::new()
    }
}

impl NetworkBackend for StdNetworkBackend {
    fn listen(&mut self, port: u16) -> Result<()> {
        let addr = format!("0.0.0.0:{port}");
        let listener =
            TcpListener::bind(&addr).map_err(|e| OasisError::Backend(format!("bind: {e}")))?;
        listener
            .set_nonblocking(true)
            .map_err(|e| OasisError::Backend(format!("set_nonblocking: {e}")))?;
        log::info!("Remote terminal listening on {addr}");
        self.listener = Some(listener);
        Ok(())
    }

    fn accept(&mut self) -> Result<Option<Box<dyn NetworkStream>>> {
        let Some(ref listener) = self.listener else {
            return Err(OasisError::Backend("not listening".to_string()));
        };
        match listener.accept() {
            Ok((stream, addr)) => {
                log::info!("Remote connection from {addr}");
                stream
                    .set_nonblocking(true)
                    .map_err(|e| OasisError::Backend(format!("set_nonblocking: {e}")))?;
                Ok(Some(Box::new(StdNetworkStream::new(stream))))
            },
            Err(ref e) if e.kind() == io::ErrorKind::WouldBlock => Ok(None),
            Err(e) => Err(OasisError::Backend(format!("accept: {e}"))),
        }
    }

    fn connect(&mut self, address: &str, port: u16) -> Result<Box<dyn NetworkStream>> {
        let addr = format!("{address}:{port}");
        let stream =
            TcpStream::connect(&addr).map_err(|e| OasisError::Backend(format!("connect: {e}")))?;
        stream
            .set_nonblocking(true)
            .map_err(|e| OasisError::Backend(format!("set_nonblocking: {e}")))?;
        log::info!("Connected to {addr}");
        Ok(Box::new(StdNetworkStream::new(stream)))
    }
}

/// A TCP stream wrapping `std::net::TcpStream`.
pub struct StdNetworkStream {
    stream: TcpStream,
}

impl StdNetworkStream {
    pub fn new(stream: TcpStream) -> Self {
        Self { stream }
    }
}

impl NetworkStream for StdNetworkStream {
    fn read(&mut self, buf: &mut [u8]) -> Result<usize> {
        match self.stream.read(buf) {
            Ok(n) => Ok(n),
            Err(ref e) if e.kind() == io::ErrorKind::WouldBlock => Ok(0),
            Err(e) => Err(OasisError::Backend(format!("read: {e}"))),
        }
    }

    fn write(&mut self, data: &[u8]) -> Result<usize> {
        self.stream
            .write(data)
            .map_err(|e| OasisError::Backend(format!("write: {e}")))
    }

    fn close(&mut self) -> Result<()> {
        self.stream
            .shutdown(std::net::Shutdown::Both)
            .map_err(|e| OasisError::Backend(format!("close: {e}")))
    }
}

// Implement Send for StdNetworkStream (TcpStream is Send).
// NetworkStream requires Send, which TcpStream satisfies.
