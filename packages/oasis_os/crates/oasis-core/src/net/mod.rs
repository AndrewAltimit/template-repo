//! Networking: std::net backend, remote terminal listener, outbound client.

mod client;
mod hosts;
mod listener;
mod std_backend;

pub use client::{ClientState, RemoteClient};
pub use hosts::{HostEntry, parse_hosts};
pub use listener::{ListenerConfig, RemoteListener};
pub use std_backend::{StdNetworkBackend, StdNetworkStream};

#[cfg(test)]
mod tests;
