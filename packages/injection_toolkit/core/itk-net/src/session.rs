//! Session management
//!
//! A session represents a group of peers watching the same content together.
//! One peer is the leader who controls playback; others follow.

use crate::discovery::{DiscoveredPeer, Discovery};
use crate::peer::{NetMessage, PeerEvent, PeerManager, VideoCommand};
use crate::sync_manager::SyncManager;
use crate::{NetError, Result, DEFAULT_PORT};
use std::net::SocketAddr;
use std::time::{Duration, Instant};
use tracing::{info, warn};

/// Session configuration
#[derive(Debug, Clone)]
pub struct SessionConfig {
    /// Our display name
    pub name: String,
    /// Port to use for game connections
    pub port: u16,
    /// Whether to enable LAN discovery
    pub enable_discovery: bool,
}

impl Default for SessionConfig {
    fn default() -> Self {
        Self {
            name: format!("Player-{}", std::process::id() % 10000),
            port: DEFAULT_PORT,
            enable_discovery: true,
        }
    }
}

/// Our role in the session
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SessionRole {
    /// We control playback
    Leader,
    /// We follow the leader
    Follower,
}

/// Events from the session
#[derive(Debug, Clone)]
pub enum SessionEvent {
    /// Session started
    Started {
        session_id: String,
        role: SessionRole,
    },
    /// Peer joined the session
    PeerJoined { name: String, addr: SocketAddr },
    /// Peer left the session
    PeerLeft { name: String },
    /// We became the leader (leader left)
    BecameLeader,
    /// Sync state updated
    SyncUpdated { position_ms: u64, is_playing: bool },
    /// Should seek to position (large drift)
    SeekRequired { position_ms: u64 },
    /// Video command received
    Command(VideoCommand),
}

/// Multiplayer session
pub struct Session {
    /// Session configuration
    _config: SessionConfig,
    /// Session ID (content URL hash)
    session_id: String,
    /// Our role
    role: SessionRole,
    /// Peer manager
    peers: PeerManager,
    /// Discovery service
    discovery: Option<Discovery>,
    /// Sync manager
    sync: SyncManager,
    /// Leader's address (if we're a follower)
    leader_addr: Option<SocketAddr>,
    /// Pending events
    events: Vec<SessionEvent>,
    /// Last time we checked for leader timeout
    last_leader_check: Instant,
}

impl Session {
    /// Create a new session as leader
    pub fn create(config: SessionConfig, content_id: String) -> Result<Self> {
        let peers = PeerManager::new(config.port)?;

        let discovery = if config.enable_discovery {
            Some(Discovery::new(
                content_id.clone(),
                config.port,
                true, // We're the leader
                config.name.clone(),
            )?)
        } else {
            None
        };

        let sync = SyncManager::new(content_id.clone(), true);

        info!(session_id = %content_id, "Created session as leader");

        let mut session = Self {
            _config: config,
            session_id: content_id.clone(),
            role: SessionRole::Leader,
            peers,
            discovery,
            sync,
            leader_addr: None,
            events: Vec::new(),
            last_leader_check: Instant::now(),
        };

        session.events.push(SessionEvent::Started {
            session_id: content_id,
            role: SessionRole::Leader,
        });

        Ok(session)
    }

    /// Join an existing session
    pub fn join(
        config: SessionConfig,
        leader_addr: SocketAddr,
        content_id: String,
    ) -> Result<Self> {
        let mut peers = PeerManager::new(config.port)?;

        // Connect to the leader
        peers.connect(leader_addr)?;

        let discovery = if config.enable_discovery {
            Some(Discovery::new(
                content_id.clone(),
                config.port,
                false, // We're a follower
                config.name.clone(),
            )?)
        } else {
            None
        };

        let sync = SyncManager::new(content_id.clone(), false);

        info!(session_id = %content_id, leader = %leader_addr, "Joining session");

        let mut session = Self {
            _config: config,
            session_id: content_id.clone(),
            role: SessionRole::Follower,
            peers,
            discovery,
            sync,
            leader_addr: Some(leader_addr),
            events: Vec::new(),
            last_leader_check: Instant::now(),
        };

        session.events.push(SessionEvent::Started {
            session_id: content_id,
            role: SessionRole::Follower,
        });

        Ok(session)
    }

    /// Join a discovered session
    pub fn join_discovered(config: SessionConfig, peer: &DiscoveredPeer) -> Result<Self> {
        Self::join(config, peer.addr, peer.session_id.clone())
    }

    /// Get our role
    pub fn role(&self) -> SessionRole {
        self.role
    }

    /// Get session ID
    pub fn session_id(&self) -> &str {
        &self.session_id
    }

    /// Get current playback position
    pub fn position_ms(&self) -> u64 {
        self.sync.current_position_ms()
    }

    /// Get recommended playback rate
    pub fn playback_rate(&self) -> f64 {
        self.sync.playback_rate()
    }

    /// Check if playing
    pub fn is_playing(&self) -> bool {
        self.sync.is_playing()
    }

    /// Get current drift (followers only)
    pub fn drift_ms(&self) -> Option<i64> {
        self.sync.drift_ms()
    }

    /// Get peer count
    pub fn peer_count(&self) -> usize {
        self.peers.peer_count()
    }

    // === Leader commands ===

    /// Load content (leader only)
    pub fn load(&mut self, url: &str) -> Result<()> {
        if self.role != SessionRole::Leader {
            return Err(NetError::NotLeader);
        }
        self.sync.send_command(
            VideoCommand::Load {
                url: url.to_string(),
            },
            &mut self.peers,
        )
    }

    /// Play (leader only)
    pub fn play(&mut self) -> Result<()> {
        if self.role != SessionRole::Leader {
            return Err(NetError::NotLeader);
        }
        self.sync.send_command(VideoCommand::Play, &mut self.peers)
    }

    /// Pause (leader only)
    pub fn pause(&mut self) -> Result<()> {
        if self.role != SessionRole::Leader {
            return Err(NetError::NotLeader);
        }
        self.sync.send_command(VideoCommand::Pause, &mut self.peers)
    }

    /// Seek (leader only)
    pub fn seek(&mut self, position_ms: u64) -> Result<()> {
        if self.role != SessionRole::Leader {
            return Err(NetError::NotLeader);
        }
        self.sync
            .send_command(VideoCommand::Seek { position_ms }, &mut self.peers)
    }

    /// Poll for events
    pub fn poll(&mut self) -> Vec<SessionEvent> {
        // Poll discovery
        if let Some(ref mut discovery) = self.discovery {
            for peer in discovery.poll() {
                // Auto-connect to peers in same session
                if peer.session_id == self.session_id {
                    if let Err(e) = self.peers.connect(peer.addr) {
                        warn!(peer = %peer.addr, error = ?e, "Failed to connect to discovered peer");
                    }
                }
            }
        }

        // Poll network
        for event in self.peers.poll() {
            self.handle_peer_event(event);
        }

        // Update sync manager
        if let Err(e) = self.sync.update(&mut self.peers) {
            warn!(error = ?e, "Sync update failed");
        }

        // Check for seek requirement (large drift)
        if let Some(target_pos) = self.sync.should_seek() {
            self.sync.seek(target_pos);
            self.events.push(SessionEvent::SeekRequired {
                position_ms: target_pos,
            });
        }

        // Check for leader timeout (followers only)
        if self.role == SessionRole::Follower {
            self.check_leader_timeout();
        }

        std::mem::take(&mut self.events)
    }

    fn handle_peer_event(&mut self, event: PeerEvent) {
        match event {
            PeerEvent::PeerConnected(peer_id) => {
                if let Some(peer) = self.peers.get_peer(&peer_id) {
                    info!(peer = %peer_id, "Peer connected to session");
                    self.events.push(SessionEvent::PeerJoined {
                        name: peer.name.unwrap_or_else(|| peer_id.clone()),
                        addr: peer.addr,
                    });
                }
            }

            PeerEvent::PeerDisconnected(peer_id) | PeerEvent::Timeout(peer_id) => {
                info!(peer = %peer_id, "Peer left session");

                // Check if it was the leader
                if self.role == SessionRole::Follower {
                    if let Some(leader) = self.leader_addr {
                        if peer_id == leader.to_string() {
                            self.promote_to_leader();
                        }
                    }
                }

                self.events.push(SessionEvent::PeerLeft { name: peer_id });
            }

            PeerEvent::Message { from, data } => {
                self.handle_message(&from, &data);
            }
        }
    }

    fn handle_message(&mut self, from: &str, data: &[u8]) {
        let msg: NetMessage = match bincode::deserialize(data) {
            Ok(m) => m,
            Err(_) => return,
        };

        let peer_addr = match self.peers.get_peer(from) {
            Some(p) => p.addr,
            None => return,
        };

        match msg {
            NetMessage::SyncState(state) => {
                self.sync.receive_sync_state(state);
                self.events.push(SessionEvent::SyncUpdated {
                    position_ms: self.sync.current_position_ms(),
                    is_playing: self.sync.is_playing(),
                });
            }

            NetMessage::ClockPing(ping) => {
                self.sync
                    .receive_clock_ping(from, ping, &mut self.peers, peer_addr);
            }

            NetMessage::ClockPong(pong) => {
                self.sync.receive_clock_pong(from, pong);
            }

            NetMessage::VideoCommand(cmd) => {
                self.sync.receive_command(cmd.clone());
                self.events.push(SessionEvent::Command(cmd));
            }

            _ => {}
        }
    }

    fn check_leader_timeout(&mut self) {
        if self.last_leader_check.elapsed() < Duration::from_secs(5) {
            return;
        }
        self.last_leader_check = Instant::now();

        // If we haven't received sync state in a while, assume leader is gone
        // This is a simplified check - real implementation would track last sync time
        if let Some(leader) = self.leader_addr {
            if self.peers.get_peer(&leader.to_string()).is_none() {
                info!("Leader disconnected, promoting self");
                self.promote_to_leader();
            }
        }
    }

    fn promote_to_leader(&mut self) {
        self.role = SessionRole::Leader;
        self.leader_addr = None;
        self.sync.set_leader(true);

        if let Some(ref mut discovery) = self.discovery {
            discovery.update_announce(true, None);
        }

        info!("Promoted to leader");
        self.events.push(SessionEvent::BecameLeader);
    }
}
