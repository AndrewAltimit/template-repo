//! Saved host configuration for remote terminal connections.

use serde::Deserialize;

/// A saved remote host entry.
#[derive(Debug, Clone, Deserialize)]
pub struct HostEntry {
    /// Human-readable name (e.g., "briefcase", "dev-server").
    pub name: String,
    /// IP address or hostname.
    pub address: String,
    /// TCP port.
    #[serde(default = "default_port")]
    pub port: u16,
    /// Connection protocol hint.
    #[serde(default = "default_protocol")]
    pub protocol: String,
    /// Optional PSK for authentication.
    #[serde(default)]
    pub psk: Option<String>,
}

fn default_port() -> u16 {
    9000
}

fn default_protocol() -> String {
    "oasis-terminal".to_string()
}

/// Parse a hosts TOML file into a list of host entries.
pub fn parse_hosts(toml_str: &str) -> crate::error::Result<Vec<HostEntry>> {
    #[derive(Deserialize)]
    struct HostsFile {
        #[serde(default)]
        host: Vec<HostEntry>,
    }

    let file: HostsFile = toml::from_str(toml_str)
        .map_err(|e| crate::error::OasisError::Config(format!("hosts.toml: {e}")))?;
    Ok(file.host)
}
