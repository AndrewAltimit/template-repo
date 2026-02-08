//! Tests for the networking module.

use std::io::{Read, Write};
use std::net::TcpStream;

use crate::backend::NetworkBackend;

use super::*;

// ---------------------------------------------------------------------------
// StdNetworkBackend tests
// ---------------------------------------------------------------------------

/// Helper: find a free TCP port by binding to port 0 and releasing it.
fn free_port() -> u16 {
    let tmp = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let port = tmp.local_addr().unwrap().port();
    drop(tmp);
    port
}

#[test]
fn listen_and_accept() {
    let mut backend = StdNetworkBackend::new();
    let port = free_port();

    backend.listen(port).unwrap();

    // No connection yet.
    let result = backend.accept().unwrap();
    assert!(result.is_none());

    // Connect a client.
    let mut client = TcpStream::connect(format!("127.0.0.1:{port}")).unwrap();
    client.write_all(b"hello").unwrap();
    std::thread::sleep(std::time::Duration::from_millis(50));

    // Accept should now return a stream.
    let mut server_stream = backend.accept().unwrap().expect("expected connection");

    let mut buf = [0u8; 64];
    let n = server_stream.read(&mut buf).unwrap();
    assert_eq!(&buf[..n], b"hello");

    // Server can write back.
    server_stream.write(b"world").unwrap();
    std::thread::sleep(std::time::Duration::from_millis(50));

    let mut response = [0u8; 64];
    let n = client.read(&mut response).unwrap();
    assert_eq!(&response[..n], b"world");

    server_stream.close().unwrap();
}

#[test]
fn connect_outbound() {
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();

    let handle = std::thread::spawn(move || {
        let (mut conn, _) = listener.accept().unwrap();
        conn.write_all(b"greeting").unwrap();
    });

    let mut backend = StdNetworkBackend::new();
    let mut stream = backend.connect("127.0.0.1", port).unwrap();

    std::thread::sleep(std::time::Duration::from_millis(100));

    let mut buf = [0u8; 64];
    let n = stream.read(&mut buf).unwrap();
    assert_eq!(&buf[..n], b"greeting");

    stream.close().unwrap();
    handle.join().unwrap();
}

#[test]
fn accept_without_listen_errors() {
    let mut backend = StdNetworkBackend::new();
    assert!(backend.accept().is_err());
}

#[test]
fn default_constructor() {
    let _backend = StdNetworkBackend::default();
}

// ---------------------------------------------------------------------------
// RemoteListener tests
// ---------------------------------------------------------------------------

#[test]
fn listener_not_listening_by_default() {
    let listener = RemoteListener::new(ListenerConfig::default());
    assert!(!listener.is_listening());
    assert_eq!(listener.connection_count(), 0);
}

#[test]
fn listener_start_and_stop() {
    let port = free_port();
    let config = ListenerConfig {
        port,
        psk: String::new(),
        max_connections: 2,
    };
    let mut listener = RemoteListener::new(config);
    let mut backend = StdNetworkBackend::new();
    listener.start(&mut backend).unwrap();
    assert!(listener.is_listening());
    listener.stop();
    assert!(!listener.is_listening());
}

#[test]
fn listener_accept_no_auth() {
    let port = free_port();
    let config = ListenerConfig {
        port,
        psk: String::new(),
        max_connections: 2,
    };
    let mut listener = RemoteListener::new(config);
    let mut backend = StdNetworkBackend::new();
    listener.start(&mut backend).unwrap();

    // Connect a client.
    let mut client = TcpStream::connect(format!("127.0.0.1:{port}")).unwrap();
    std::thread::sleep(std::time::Duration::from_millis(50));

    // Poll to accept.
    let commands = listener.poll(&mut backend);
    assert!(commands.is_empty()); // No commands yet.
    assert_eq!(listener.connection_count(), 1);

    // Read the welcome message.
    let mut buf = [0u8; 256];
    let n = client.read(&mut buf).unwrap();
    let welcome = String::from_utf8_lossy(&buf[..n]);
    assert!(welcome.contains("OASIS_OS"));

    // Send a command.
    client.write_all(b"status\n").unwrap();
    std::thread::sleep(std::time::Duration::from_millis(50));

    let commands = listener.poll(&mut backend);
    assert_eq!(commands.len(), 1);
    assert_eq!(commands[0].0, "status");

    // Send response.
    listener.send_response(0, "OASIS_OS v0.1.0").unwrap();
    std::thread::sleep(std::time::Duration::from_millis(50));

    let n = client.read(&mut buf).unwrap();
    let response = String::from_utf8_lossy(&buf[..n]);
    assert!(response.contains("OASIS_OS v0.1.0"));

    listener.stop();
}

#[test]
fn listener_psk_auth() {
    let port = free_port();
    let config = ListenerConfig {
        port,
        psk: "secret123".to_string(),
        max_connections: 2,
    };
    let mut listener = RemoteListener::new(config);
    let mut backend = StdNetworkBackend::new();
    listener.start(&mut backend).unwrap();

    let mut client = TcpStream::connect(format!("127.0.0.1:{port}")).unwrap();
    std::thread::sleep(std::time::Duration::from_millis(50));

    // Accept connection.
    listener.poll(&mut backend);

    // Read auth prompt.
    let mut buf = [0u8; 256];
    let n = client.read(&mut buf).unwrap();
    let msg = String::from_utf8_lossy(&buf[..n]);
    assert!(msg.contains("AUTH_REQUIRED"));

    // Send correct PSK.
    client.write_all(b"secret123\n").unwrap();
    std::thread::sleep(std::time::Duration::from_millis(50));

    listener.poll(&mut backend);

    let n = client.read(&mut buf).unwrap();
    let msg = String::from_utf8_lossy(&buf[..n]);
    assert!(msg.contains("AUTH_OK"));

    // Now send a command.
    client.write_all(b"help\n").unwrap();
    std::thread::sleep(std::time::Duration::from_millis(50));

    let commands = listener.poll(&mut backend);
    assert_eq!(commands.len(), 1);
    assert_eq!(commands[0].0, "help");

    listener.stop();
}

#[test]
fn listener_psk_auth_failure() {
    let port = free_port();
    let config = ListenerConfig {
        port,
        psk: "correct_key".to_string(),
        max_connections: 2,
    };
    let mut listener = RemoteListener::new(config);
    let mut backend = StdNetworkBackend::new();
    listener.start(&mut backend).unwrap();

    let mut client = TcpStream::connect(format!("127.0.0.1:{port}")).unwrap();
    std::thread::sleep(std::time::Duration::from_millis(50));

    listener.poll(&mut backend);

    // Read auth prompt.
    let mut buf = [0u8; 256];
    let _n = client.read(&mut buf).unwrap();

    // Send wrong PSK.
    client.write_all(b"wrong_key\n").unwrap();
    std::thread::sleep(std::time::Duration::from_millis(50));

    listener.poll(&mut backend);
    // Connection should be removed.
    assert_eq!(listener.connection_count(), 0);

    listener.stop();
}

#[test]
fn listener_quit_command() {
    let port = free_port();
    let config = ListenerConfig {
        port,
        psk: String::new(),
        max_connections: 2,
    };
    let mut listener = RemoteListener::new(config);
    let mut backend = StdNetworkBackend::new();
    listener.start(&mut backend).unwrap();

    let mut client = TcpStream::connect(format!("127.0.0.1:{port}")).unwrap();
    std::thread::sleep(std::time::Duration::from_millis(50));

    listener.poll(&mut backend);

    // Read welcome.
    let mut buf = [0u8; 256];
    let _n = client.read(&mut buf).unwrap();

    // Send quit.
    client.write_all(b"quit\n").unwrap();
    std::thread::sleep(std::time::Duration::from_millis(50));

    let commands = listener.poll(&mut backend);
    assert!(commands.is_empty()); // quit is handled internally.
    assert_eq!(listener.connection_count(), 0);

    listener.stop();
}

// ---------------------------------------------------------------------------
// RemoteClient tests
// ---------------------------------------------------------------------------

#[test]
fn client_default_state() {
    let client = RemoteClient::new();
    assert_eq!(client.state(), ClientState::Disconnected);
    assert!(!client.is_connected());
}

#[test]
fn client_connect_no_auth() {
    // Set up a simple echo server.
    let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();

    let handle = std::thread::spawn(move || {
        let (mut conn, _) = listener.accept().unwrap();
        conn.write_all(b"Hello from server\n").unwrap();
        let mut buf = [0u8; 256];
        let n = conn.read(&mut buf).unwrap();
        // Echo back.
        conn.write_all(&buf[..n]).unwrap();
    });

    let mut backend = StdNetworkBackend::new();
    let mut client = RemoteClient::new();
    client
        .connect(&mut backend, "127.0.0.1", port, None)
        .unwrap();
    assert_eq!(client.state(), ClientState::Connected);

    std::thread::sleep(std::time::Duration::from_millis(100));

    let lines = client.poll();
    assert!(!lines.is_empty());
    assert!(lines[0].contains("Hello from server"));

    client.send("test command").unwrap();
    std::thread::sleep(std::time::Duration::from_millis(100));

    let lines = client.poll();
    assert!(!lines.is_empty());

    client.disconnect();
    assert_eq!(client.state(), ClientState::Disconnected);

    handle.join().unwrap();
}

#[test]
fn client_send_without_connect_errors() {
    let mut client = RemoteClient::new();
    assert!(client.send("test").is_err());
}

// ---------------------------------------------------------------------------
// Host configuration tests
// ---------------------------------------------------------------------------

#[test]
fn parse_hosts_toml() {
    let toml = r##"
[[host]]
name = "briefcase"
address = "192.168.0.50"
port = 9000
protocol = "oasis-terminal"
psk = "secret"

[[host]]
name = "dev-server"
address = "192.168.0.100"
port = 22
protocol = "raw-tcp"
"##;
    let hosts = hosts::parse_hosts(toml).unwrap();
    assert_eq!(hosts.len(), 2);
    assert_eq!(hosts[0].name, "briefcase");
    assert_eq!(hosts[0].port, 9000);
    assert_eq!(hosts[0].psk, Some("secret".to_string()));
    assert_eq!(hosts[1].name, "dev-server");
    assert_eq!(hosts[1].port, 22);
    assert!(hosts[1].psk.is_none());
}

#[test]
fn parse_hosts_defaults() {
    let toml = r#"
[[host]]
name = "minimal"
address = "10.0.0.1"
"#;
    let hosts = hosts::parse_hosts(toml).unwrap();
    assert_eq!(hosts.len(), 1);
    assert_eq!(hosts[0].port, 9000);
    assert_eq!(hosts[0].protocol, "oasis-terminal");
}

#[test]
fn parse_empty_hosts() {
    let hosts = hosts::parse_hosts("").unwrap();
    assert!(hosts.is_empty());
}
