//! `automation-cli wait` -- block until a TCP port (or HTTP endpoint) answers.
//! Drop-in replacement for `wait-for-it.sh`; exits 1 on timeout.

use std::net::{TcpStream, ToSocketAddrs};
use std::time::{Duration, Instant};

use anyhow::{Result, bail};
use clap::Args;

use crate::shared::{http, output};

#[derive(Args)]
pub struct WaitArgs {
    /// Target as HOST:PORT (wait-for-it style); alternative to --host/--port
    #[arg(value_name = "HOST:PORT", conflicts_with = "port")]
    pub target: Option<String>,

    /// Host to check
    #[arg(short = 'H', long, default_value = "localhost")]
    pub host: String,

    /// Port to check (required unless HOST:PORT is given)
    #[arg(short, long, required_unless_present = "target")]
    pub port: Option<u16>,

    /// Timeout in seconds (0 = check once)
    #[arg(short, long, default_value = "15")]
    pub timeout: u64,

    /// HTTP health endpoint path (implies HTTP check instead of TCP)
    #[arg(short = 'e', long)]
    pub health_endpoint: Option<String>,

    /// Suppress output
    #[arg(short, long)]
    pub quiet: bool,
}

/// Split `host:port` (IPv6 hosts may be bracketed: `[::1]:8080`).
fn parse_target(target: &str) -> Result<(String, u16)> {
    let Some((host, port)) = target.rsplit_once(':') else {
        bail!("invalid target `{target}`: expected HOST:PORT");
    };
    let host = host.trim_start_matches('[').trim_end_matches(']');
    if host.is_empty() {
        bail!("invalid target `{target}`: empty host");
    }
    let port: u16 = port
        .parse()
        .map_err(|_| anyhow::anyhow!("invalid port in `{target}`"))?;
    Ok((host.to_string(), port))
}

/// Normalize a health endpoint to start with `/`.
fn normalize_endpoint(ep: &str) -> String {
    if ep.starts_with('/') {
        ep.to_string()
    } else {
        format!("/{ep}")
    }
}

pub fn run(args: WaitArgs) -> Result<()> {
    let (host, port) = match (&args.target, args.port) {
        (Some(t), _) => parse_target(t)?,
        (None, Some(p)) => (args.host.clone(), p),
        (None, None) => bail!("a port is required (--port or HOST:PORT)"),
    };
    let endpoint = args.health_endpoint.as_deref().map(normalize_endpoint);
    let label = format!("{host}:{port}{}", endpoint.as_deref().unwrap_or(""));

    if !args.quiet {
        output::step(&format!("wait: waiting {}s for {label}", args.timeout));
    }

    let client = match &endpoint {
        Some(_) => Some(http::client(Duration::from_secs(3))?),
        None => None,
    };
    let url = endpoint
        .as_ref()
        .map(|ep| format!("http://{}:{port}{ep}", url_host(&host)));

    let start = Instant::now();
    let ok = http::poll_until(
        Duration::from_secs(args.timeout),
        Duration::from_secs(1),
        || match (&client, &url) {
            (Some(c), Some(u)) => http::get_ok(c, u),
            _ => check_tcp(&host, port),
        },
        || {},
    );

    if ok {
        if !args.quiet {
            output::success(&format!(
                "{label} is available after {}s",
                start.elapsed().as_secs()
            ));
        }
        return Ok(());
    }
    let msg = format!("timeout after {}s waiting for {label}", args.timeout);
    if !args.quiet {
        output::fail(&msg);
    }
    bail!("{msg}");
}

/// Bracket bare IPv6 literals for use in a URL.
fn url_host(host: &str) -> String {
    if host.contains(':') {
        format!("[{host}]")
    } else {
        host.to_string()
    }
}

fn check_tcp(host: &str, port: u16) -> bool {
    let Ok(addrs) = (host, port).to_socket_addrs() else {
        return false;
    };
    addrs
        .into_iter()
        .any(|a| TcpStream::connect_timeout(&a, Duration::from_secs(2)).is_ok())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tcp_check_fails_on_closed_port() {
        // Port 1 is almost certainly not listening
        assert!(!check_tcp("127.0.0.1", 1));
    }

    #[test]
    fn tcp_check_succeeds_on_listening_port() {
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        assert!(check_tcp("127.0.0.1", port));
    }

    #[test]
    fn http_check_fails_on_bad_host() {
        let c = http::client(Duration::from_millis(500)).unwrap();
        assert!(!http::get_ok(&c, "http://192.0.2.1:1/health"));
    }

    #[test]
    fn parse_target_variants() {
        assert_eq!(parse_target("db:5432").unwrap(), ("db".to_string(), 5432));
        assert_eq!(
            parse_target("[::1]:8080").unwrap(),
            ("::1".to_string(), 8080)
        );
        assert!(parse_target("nohost").is_err());
        assert!(parse_target(":80").is_err());
        assert!(parse_target("host:notaport").is_err());
        assert!(parse_target("host:70000").is_err());
    }

    #[test]
    fn endpoint_and_host_normalization() {
        assert_eq!(normalize_endpoint("health"), "/health");
        assert_eq!(normalize_endpoint("/health"), "/health");
        assert_eq!(url_host("::1"), "[::1]");
        assert_eq!(url_host("localhost"), "localhost");
    }
}
