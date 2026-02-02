//! Peer connection management using laminar
//!
//! Provides reliable and unreliable messaging between peers.

use crate::{NetError, Result, DEFAULT_PORT};
use laminar::{Config, Packet, Socket, SocketEvent};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tracing::{debug, info, warn};

/// Peer identifier (socket address as string)
pub type PeerId = String;

/// Information about a connected peer
#[derive(Debug, Clone)]
pub struct Peer {
    /// Peer's network address
    pub addr: SocketAddr,
    /// Display name (if known)
    pub name: Option<String>,
    /// Last time we received a message from this peer
    pub last_seen: Instant,
    /// Whether this peer is the session leader
    pub is_leader: bool,
    /// Estimated latency in milliseconds
    pub latency_ms: Option<u32>,
}

impl Peer {
    pub fn new(addr: SocketAddr) -> Self {
        Self {
            addr,
            name: None,
            last_seen: Instant::now(),
            is_leader: false,
            latency_ms: None,
        }
    }

    pub fn id(&self) -> PeerId {
        self.addr.to_string()
    }
}

/// Events from the peer manager
#[derive(Debug, Clone)]
pub enum PeerEvent {
    /// A new peer connected
    PeerConnected(PeerId),
    /// A peer disconnected
    PeerDisconnected(PeerId),
    /// Received a message from a peer
    Message { from: PeerId, data: Vec<u8> },
    /// Connection timeout
    Timeout(PeerId),
}

/// Network message types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NetMessage {
    /// Heartbeat/keepalive
    Ping { timestamp_ms: u64 },
    /// Response to ping
    Pong {
        timestamp_ms: u64,
        peer_time_ms: u64,
    },
    /// Announce presence with name
    Announce { name: String },
    /// Sync state broadcast (unreliable, frequent)
    SyncState(itk_protocol::SyncState),
    /// Clock ping for time sync
    ClockPing(itk_protocol::ClockPing),
    /// Clock pong response
    ClockPong(itk_protocol::ClockPong),
    /// Video command (reliable)
    VideoCommand(VideoCommand),
}

/// Video control commands
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VideoCommand {
    Load { url: String },
    Play,
    Pause,
    Seek { position_ms: u64 },
}

/// Manages peer connections
pub struct PeerManager {
    /// Laminar socket
    socket: Socket,
    /// Connected peers
    peers: Arc<RwLock<HashMap<PeerId, Peer>>>,
    /// Our local address
    local_addr: SocketAddr,
    /// Pending events
    events: Arc<RwLock<Vec<PeerEvent>>>,
}

impl PeerManager {
    /// Create a new peer manager bound to the given port
    pub fn new(port: u16) -> Result<Self> {
        let addr: SocketAddr = format!("0.0.0.0:{}", port)
            .parse()
            .map_err(|e| NetError::BindFailed(format!("{}", e)))?;

        let config = Config {
            heartbeat_interval: Some(Duration::from_millis(500)),
            idle_connection_timeout: Duration::from_secs(10),
            ..Default::default()
        };

        let socket = Socket::bind_with_config(addr, config)
            .map_err(|e| NetError::BindFailed(e.to_string()))?;

        let local_addr = socket
            .local_addr()
            .map_err(|e| NetError::BindFailed(e.to_string()))?;

        info!(addr = %local_addr, "PeerManager bound");

        Ok(Self {
            socket,
            peers: Arc::new(RwLock::new(HashMap::new())),
            local_addr,
            events: Arc::new(RwLock::new(Vec::new())),
        })
    }

    /// Create with default port
    pub fn with_default_port() -> Result<Self> {
        Self::new(DEFAULT_PORT)
    }

    /// Get our local address
    pub fn local_addr(&self) -> SocketAddr {
        self.local_addr
    }

    /// Connect to a peer
    pub fn connect(&mut self, addr: SocketAddr) -> Result<()> {
        // Send announce message to initiate connection
        let msg = NetMessage::Announce {
            name: format!("peer-{}", self.local_addr.port()),
        };
        self.send_reliable(addr, &msg)?;
        info!(peer = %addr, "Connecting to peer");
        Ok(())
    }

    /// Send a message reliably (guaranteed delivery, ordered)
    pub fn send_reliable(&mut self, addr: SocketAddr, msg: &NetMessage) -> Result<()> {
        let data = bincode::serialize(msg)?;
        let packet = Packet::reliable_ordered(addr, data, Some(0));
        self.socket
            .send(packet)
            .map_err(|e| NetError::SendFailed(e.to_string()))?;
        Ok(())
    }

    /// Send a message unreliably (may be lost, unordered - good for sync state)
    pub fn send_unreliable(&mut self, addr: SocketAddr, msg: &NetMessage) -> Result<()> {
        let data = bincode::serialize(msg)?;
        let packet = Packet::unreliable(addr, data);
        self.socket
            .send(packet)
            .map_err(|e| NetError::SendFailed(e.to_string()))?;
        Ok(())
    }

    /// Broadcast a message to all connected peers (unreliable)
    pub fn broadcast(&mut self, msg: &NetMessage) -> Result<()> {
        let peers: Vec<SocketAddr> = self.peers.read().values().map(|p| p.addr).collect();
        for addr in peers {
            if let Err(e) = self.send_unreliable(addr, msg) {
                warn!(peer = %addr, error = ?e, "Failed to broadcast to peer");
            }
        }
        Ok(())
    }

    /// Broadcast a message reliably to all peers
    pub fn broadcast_reliable(&mut self, msg: &NetMessage) -> Result<()> {
        let peers: Vec<SocketAddr> = self.peers.read().values().map(|p| p.addr).collect();
        for addr in peers {
            if let Err(e) = self.send_reliable(addr, msg) {
                warn!(peer = %addr, error = ?e, "Failed to broadcast reliable to peer");
            }
        }
        Ok(())
    }

    /// Poll for network events (non-blocking)
    pub fn poll(&mut self) -> Vec<PeerEvent> {
        // Process socket events
        self.socket.manual_poll(Instant::now());

        while let Some(event) = self.socket.recv() {
            self.handle_socket_event(event);
        }

        // Return accumulated events
        std::mem::take(&mut *self.events.write())
    }

    fn handle_socket_event(&mut self, event: SocketEvent) {
        match event {
            SocketEvent::Packet(packet) => {
                let addr = packet.addr();
                let peer_id = addr.to_string();

                // Update last seen
                {
                    let mut peers = self.peers.write();
                    if let Some(peer) = peers.get_mut(&peer_id) {
                        peer.last_seen = Instant::now();
                    }
                }

                // Try to deserialize message
                match bincode::deserialize::<NetMessage>(packet.payload()) {
                    Ok(msg) => {
                        self.handle_message(addr, msg);
                    },
                    Err(e) => {
                        warn!(peer = %addr, error = ?e, "Failed to deserialize message");
                    },
                }
            },

            SocketEvent::Connect(addr) => {
                let peer_id = addr.to_string();
                info!(peer = %addr, "Peer connected");

                {
                    let mut peers = self.peers.write();
                    peers.insert(peer_id.clone(), Peer::new(addr));
                }

                self.events.write().push(PeerEvent::PeerConnected(peer_id));
            },

            SocketEvent::Disconnect(addr) => {
                let peer_id = addr.to_string();
                info!(peer = %addr, "Peer disconnected");

                {
                    let mut peers = self.peers.write();
                    peers.remove(&peer_id);
                }

                self.events
                    .write()
                    .push(PeerEvent::PeerDisconnected(peer_id));
            },

            SocketEvent::Timeout(addr) => {
                let peer_id = addr.to_string();
                warn!(peer = %addr, "Peer timeout");

                {
                    let mut peers = self.peers.write();
                    peers.remove(&peer_id);
                }

                self.events.write().push(PeerEvent::Timeout(peer_id));
            },
        }
    }

    fn handle_message(&mut self, addr: SocketAddr, msg: NetMessage) {
        let peer_id = addr.to_string();

        match msg {
            NetMessage::Announce { name } => {
                debug!(peer = %addr, name = %name, "Peer announced");
                let mut peers = self.peers.write();
                if let Some(peer) = peers.get_mut(&peer_id) {
                    peer.name = Some(name);
                } else {
                    let mut peer = Peer::new(addr);
                    peer.name = Some(name);
                    peers.insert(peer_id.clone(), peer);
                    drop(peers);
                    self.events.write().push(PeerEvent::PeerConnected(peer_id));
                }
            },

            NetMessage::Ping { timestamp_ms } => {
                // Respond with pong
                let pong = NetMessage::Pong {
                    timestamp_ms,
                    peer_time_ms: itk_sync::now_ms(),
                };
                let _ = self.send_unreliable(addr, &pong);
            },

            NetMessage::Pong {
                timestamp_ms,
                peer_time_ms: _,
            } => {
                // Calculate latency
                let now = itk_sync::now_ms();
                let rtt = now.saturating_sub(timestamp_ms) as u32;

                let mut peers = self.peers.write();
                if let Some(peer) = peers.get_mut(&peer_id) {
                    peer.latency_ms = Some(rtt / 2);
                }
            },

            // Forward other messages as events
            _ => {
                let data = bincode::serialize(&msg).unwrap_or_default();
                self.events.write().push(PeerEvent::Message {
                    from: peer_id,
                    data,
                });
            },
        }
    }

    /// Get list of connected peers
    pub fn peers(&self) -> Vec<Peer> {
        self.peers.read().values().cloned().collect()
    }

    /// Get a specific peer
    pub fn get_peer(&self, id: &str) -> Option<Peer> {
        self.peers.read().get(id).cloned()
    }

    /// Number of connected peers
    pub fn peer_count(&self) -> usize {
        self.peers.read().len()
    }
}
