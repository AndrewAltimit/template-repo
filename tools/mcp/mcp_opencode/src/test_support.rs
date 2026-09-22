//! Minimal in-process HTTP/1.1 mock server for offline tests.
//!
//! Serves a fixed queue of canned responses (one per connection, in order)
//! and records every request so tests can assert on headers and bodies.

use std::collections::VecDeque;
use std::sync::{Arc, Mutex};

use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpListener;

/// A canned response.
#[derive(Clone)]
pub struct MockResponse {
    status: u16,
    headers: Vec<(String, String)>,
    body: String,
    hang: bool,
}

impl MockResponse {
    /// `200 OK` with a JSON body.
    pub fn ok(body: impl Into<String>) -> Self {
        Self::status(200, body)
    }

    /// Arbitrary status with a JSON body.
    pub fn status(status: u16, body: impl Into<String>) -> Self {
        Self {
            status,
            headers: Vec::new(),
            body: body.into(),
            hang: false,
        }
    }

    /// Never respond (to exercise timeouts).
    pub fn hang() -> Self {
        Self {
            hang: true,
            ..Self::status(200, "")
        }
    }

    /// Add a response header.
    pub fn header(mut self, name: &str, value: &str) -> Self {
        self.headers.push((name.to_string(), value.to_string()));
        self
    }
}

/// A captured request.
#[derive(Clone, Debug)]
pub struct CapturedRequest {
    /// Request line plus headers.
    pub head: String,
    /// Request body.
    pub body: String,
}

/// Running mock server; stops when the test runtime shuts down.
pub struct MockServer {
    /// Base URL, e.g. `http://127.0.0.1:12345`.
    pub url: String,
    requests: Arc<Mutex<Vec<CapturedRequest>>>,
}

impl MockServer {
    /// Bind to an ephemeral port and start serving `responses`.
    pub async fn start(responses: Vec<MockResponse>) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0")
            .await
            .expect("bind mock server");
        let url = format!("http://{}", listener.local_addr().expect("local addr"));
        let requests = Arc::new(Mutex::new(Vec::new()));
        let queue = Arc::new(Mutex::new(VecDeque::from(responses)));

        let captured = Arc::clone(&requests);
        tokio::spawn(async move {
            loop {
                let Ok((mut socket, _)) = listener.accept().await else {
                    return;
                };
                let captured = Arc::clone(&captured);
                let queue = Arc::clone(&queue);
                tokio::spawn(async move {
                    let Some(request) = read_request(&mut socket).await else {
                        return;
                    };
                    captured.lock().expect("lock").push(request);
                    let response = queue.lock().expect("lock").pop_front().unwrap_or_else(|| {
                        MockResponse::status(500, r#"{"error":{"message":"mock exhausted"}}"#)
                    });
                    if response.hang {
                        tokio::time::sleep(std::time::Duration::from_secs(3600)).await;
                        return;
                    }
                    let mut raw = format!(
                        "HTTP/1.1 {} MOCK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n",
                        response.status,
                        response.body.len()
                    );
                    for (k, v) in &response.headers {
                        raw.push_str(&format!("{k}: {v}\r\n"));
                    }
                    raw.push_str("\r\n");
                    raw.push_str(&response.body);
                    let _ = socket.write_all(raw.as_bytes()).await;
                    let _ = socket.shutdown().await;
                });
            }
        });

        Self { url, requests }
    }

    /// All requests received so far.
    pub fn requests(&self) -> Vec<CapturedRequest> {
        self.requests.lock().expect("lock").clone()
    }
}

async fn read_request(socket: &mut tokio::net::TcpStream) -> Option<CapturedRequest> {
    let mut buf = Vec::new();
    let mut chunk = [0u8; 4096];
    let header_end = loop {
        let n = socket.read(&mut chunk).await.ok()?;
        if n == 0 {
            return None;
        }
        buf.extend_from_slice(&chunk[..n]);
        if let Some(pos) = buf.windows(4).position(|w| w == b"\r\n\r\n") {
            break pos + 4;
        }
    };
    let head = String::from_utf8_lossy(&buf[..header_end]).to_string();
    let content_length = head
        .lines()
        .find_map(|l| {
            let (k, v) = l.split_once(':')?;
            k.trim()
                .eq_ignore_ascii_case("content-length")
                .then(|| v.trim().parse::<usize>().ok())
                .flatten()
        })
        .unwrap_or(0);
    while buf.len() < header_end + content_length {
        let n = socket.read(&mut chunk).await.ok()?;
        if n == 0 {
            break;
        }
        buf.extend_from_slice(&chunk[..n]);
    }
    let body = String::from_utf8_lossy(&buf[header_end..]).to_string();
    Some(CapturedRequest { head, body })
}
