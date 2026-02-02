//! LAN peer discovery via UDP broadcast
//!
//! Broadcasts presence on the local network to find other peers.

use crate::{NetError, Result, DISCOVERY_PORT};
use serde::{Deserialize, Serialize};
use socket2::{Domain, Protocol, Socket, Type};
use std::net::{SocketAddr, UdpSocket};
use std::time::{Duration, Instant, SystemTime};
use tracing::{debug, info, warn};

/// Discovery announcement message
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiscoveryAnnounce {
    /// Magic identifier for our protocol
    pub magic: [u8; 4],
    /// Protocol version
    pub version: u32,
    /// Unique peer identifier (distinguishes instances in same session)
    pub peer_id: u64,
    /// Session ID (content hash or random)
    pub session_id: String,
    /// Peer's game port (for laminar connection)
    pub game_port: u16,
    /// Whether this peer is the session leader
    pub is_leader: bool,
    /// Peer's display name
    pub name: String,
}

impl DiscoveryAnnounce {
    pub const MAGIC: [u8; 4] = *b"ITKD"; // ITK Discovery

    pub fn new(session_id: String, game_port: u16, is_leader: bool, name: String) -> Self {
        // Generate a unique peer ID from process ID and high-resolution time
        let time_nanos = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos() as u64;
        let peer_id = time_nanos ^ (std::process::id() as u64) << 32;

        Self {
            magic: Self::MAGIC,
            version: 1,
            peer_id,
            session_id,
            game_port,
            is_leader,
            name,
        }
    }

    pub fn is_valid(&self) -> bool {
        self.magic == Self::MAGIC && self.version == 1
    }
}

/// Discovered peer information
#[derive(Debug, Clone)]
pub struct DiscoveredPeer {
    /// Peer's address for game connection
    pub addr: SocketAddr,
    /// Session ID
    pub session_id: String,
    /// Whether this peer is the leader
    pub is_leader: bool,
    /// Peer's display name
    pub name: String,
    /// When we discovered this peer
    pub discovered_at: Instant,
}

/// LAN discovery service
pub struct Discovery {
    /// UDP socket for broadcast
    socket: UdpSocket,
    /// Our announcement
    announce: DiscoveryAnnounce,
    /// Discovered peers
    discovered: Vec<DiscoveredPeer>,
    /// Last broadcast time
    last_broadcast: Instant,
    /// Broadcast interval
    broadcast_interval: Duration,
}

impl Discovery {
    /// Create a new discovery service
    pub fn new(session_id: String, game_port: u16, is_leader: bool, name: String) -> Result<Self> {
        // Use socket2 to set SO_REUSEADDR/SO_REUSEPORT before binding, allowing
        // multiple instances to listen on the same discovery port simultaneously.
        let sock2 = Socket::new(Domain::IPV4, Type::DGRAM, Some(Protocol::UDP))
            .map_err(|e| NetError::BindFailed(format!("Failed to create socket: {}", e)))?;

        sock2
            .set_reuse_address(true)
            .map_err(|e| NetError::BindFailed(format!("Failed to set SO_REUSEADDR: {}", e)))?;

        // SO_REUSEPORT allows multiple processes to bind to the same port (Linux/macOS)
        #[cfg(not(windows))]
        sock2
            .set_reuse_port(true)
            .map_err(|e| NetError::BindFailed(format!("Failed to set SO_REUSEPORT: {}", e)))?;

        let addr: std::net::SocketAddrV4 = format!("0.0.0.0:{}", DISCOVERY_PORT).parse().unwrap();
        sock2.bind(&socket2::SockAddr::from(addr)).map_err(|e| {
            NetError::BindFailed(format!(
                "Failed to bind discovery port {}: {}",
                DISCOVERY_PORT, e
            ))
        })?;

        let socket: UdpSocket = sock2.into();

        // Enable broadcast
        socket
            .set_broadcast(true)
            .map_err(|e| NetError::BindFailed(format!("Failed to enable broadcast: {}", e)))?;

        // Non-blocking mode
        socket
            .set_nonblocking(true)
            .map_err(|e| NetError::BindFailed(format!("Failed to set non-blocking: {}", e)))?;

        let announce = DiscoveryAnnounce::new(session_id, game_port, is_leader, name);

        info!(port = DISCOVERY_PORT, "Discovery service started");

        Ok(Self {
            socket,
            announce,
            discovered: Vec::new(),
            last_broadcast: Instant::now() - Duration::from_secs(10), // Trigger immediate broadcast
            broadcast_interval: Duration::from_secs(2),
        })
    }

    /// Update our announcement (e.g., when becoming leader)
    pub fn update_announce(&mut self, is_leader: bool, session_id: Option<String>) {
        self.announce.is_leader = is_leader;
        if let Some(sid) = session_id {
            self.announce.session_id = sid;
        }
    }

    /// Poll for discovery events
    pub fn poll(&mut self) -> Vec<DiscoveredPeer> {
        // Broadcast if interval elapsed
        if self.last_broadcast.elapsed() >= self.broadcast_interval {
            self.broadcast();
            self.last_broadcast = Instant::now();
        }

        // Receive announcements
        let mut buf = [0u8; 1024];
        let mut new_peers = Vec::new();

        loop {
            match self.socket.recv_from(&mut buf) {
                Ok((len, src_addr)) => {
                    if let Some(peer) = self.handle_packet(&buf[..len], src_addr) {
                        new_peers.push(peer);
                    }
                },
                Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                    break;
                },
                Err(e) => {
                    warn!(error = ?e, "Discovery recv error");
                    break;
                },
            }
        }

        // Prune old discoveries (older than 10 seconds)
        let now = Instant::now();
        self.discovered
            .retain(|p| now.duration_since(p.discovered_at) < Duration::from_secs(10));

        new_peers
    }

    fn broadcast(&self) {
        let data = match bincode::serialize(&self.announce) {
            Ok(d) => d,
            Err(e) => {
                warn!(error = ?e, "Failed to serialize announce");
                return;
            },
        };

        // Broadcast to LAN
        let broadcast_addr: SocketAddr = format!("255.255.255.255:{}", DISCOVERY_PORT)
            .parse()
            .unwrap();

        if let Err(e) = self.socket.send_to(&data, broadcast_addr) {
            debug!(error = ?e, "Broadcast send failed (may be normal on some networks)");
        }
    }

    fn handle_packet(&mut self, data: &[u8], src_addr: SocketAddr) -> Option<DiscoveredPeer> {
        let announce: DiscoveryAnnounce = match bincode::deserialize(data) {
            Ok(a) => a,
            Err(_) => return None,
        };

        if !announce.is_valid() {
            return None;
        }

        // Ignore our own broadcasts (compare unique peer ID, not session+port)
        if announce.peer_id == self.announce.peer_id {
            return None;
        }

        // Build peer address with their game port
        let game_addr = SocketAddr::new(src_addr.ip(), announce.game_port);

        let peer = DiscoveredPeer {
            addr: game_addr,
            session_id: announce.session_id.clone(),
            is_leader: announce.is_leader,
            name: announce.name.clone(),
            discovered_at: Instant::now(),
        };

        // Check if already discovered
        let existing = self
            .discovered
            .iter_mut()
            .find(|p| p.addr == game_addr && p.session_id == announce.session_id);

        if let Some(existing) = existing {
            existing.discovered_at = Instant::now();
            existing.is_leader = announce.is_leader;
            None // Not a new discovery
        } else {
            info!(
                peer = %game_addr,
                session = %announce.session_id,
                leader = announce.is_leader,
                "Discovered peer"
            );
            self.discovered.push(peer.clone());
            Some(peer)
        }
    }

    /// Get all currently known peers
    pub fn peers(&self) -> &[DiscoveredPeer] {
        &self.discovered
    }

    /// Find peers in a specific session
    pub fn peers_in_session(&self, session_id: &str) -> Vec<&DiscoveredPeer> {
        self.discovered
            .iter()
            .filter(|p| p.session_id == session_id)
            .collect()
    }

    /// Find the leader for a session
    pub fn find_leader(&self, session_id: &str) -> Option<&DiscoveredPeer> {
        self.discovered
            .iter()
            .find(|p| p.session_id == session_id && p.is_leader)
    }
}
