use std::net::TcpStream;
use std::time::{Duration, Instant};

use anyhow::{Result, bail};
use clap::Args;

use crate::shared::output;

#[derive(Args)]
pub struct WaitArgs {
    /// Host to check
    #[arg(short = 'H', long, default_value = "localhost")]
    pub host: String,

    /// Port to check
    #[arg(short, long)]
    pub port: u16,

    /// Timeout in seconds
    #[arg(short, long, default_value = "15")]
    pub timeout: u64,

    /// HTTP health endpoint path (implies HTTP check instead of TCP)
    #[arg(short = 'e', long)]
    pub health_endpoint: Option<String>,

    /// Suppress output
    #[arg(short, long)]
    pub quiet: bool,
}

pub fn run(args: WaitArgs) -> Result<()> {
    let timeout = Duration::from_secs(args.timeout);
    let start = Instant::now();

    if !args.quiet {
        output::step(&format!(
            "wait: waiting {}s for {}:{}",
            args.timeout, args.host, args.port
        ));
    }

    loop {
        let ok = match &args.health_endpoint {
            Some(endpoint) => check_http(&args.host, args.port, endpoint),
            None => check_tcp(&args.host, args.port),
        };

        if ok {
            let elapsed = start.elapsed().as_secs();
            if !args.quiet {
                match &args.health_endpoint {
                    Some(ep) => output::success(&format!(
                        "{}:{}{ep} is available after {elapsed}s",
                        args.host, args.port
                    )),
                    None => output::success(&format!(
                        "{}:{} is available after {elapsed}s",
                        args.host, args.port
                    )),
                }
            }
            return Ok(());
        }

        if start.elapsed() >= timeout {
            let msg = format!(
                "timeout after {}s waiting for {}:{}",
                args.timeout, args.host, args.port
            );
            if !args.quiet {
                output::fail(&msg);
            }
            bail!("{msg}");
        }

        std::thread::sleep(Duration::from_secs(1));
    }
}

fn check_tcp(host: &str, port: u16) -> bool {
    use std::net::ToSocketAddrs;
    let addr = format!("{host}:{port}");
    let Ok(mut addrs) = addr.to_socket_addrs() else {
        return false;
    };
    addrs.any(|a| TcpStream::connect_timeout(&a, Duration::from_secs(2)).is_ok())
}

fn check_http(host: &str, port: u16, endpoint: &str) -> bool {
    let url = format!("http://{host}:{port}{endpoint}");
    // Use a blocking reqwest client with a short timeout
    reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(3))
        .build()
        .ok()
        .and_then(|c| c.get(&url).send().ok())
        .is_some_and(|r| r.status().is_success())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tcp_check_fails_on_closed_port() {
        // Port 1 is almost certainly not listening
        assert!(!check_tcp("127.0.0.1", 1));
    }

    #[test]
    fn test_http_check_fails_on_bad_host() {
        assert!(!check_http("192.0.2.1", 1, "/health"));
    }
}
