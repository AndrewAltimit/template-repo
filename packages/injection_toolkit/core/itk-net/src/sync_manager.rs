//! Sync manager - integrates itk-sync with network messaging
//!
//! Handles clock synchronization and playback sync across peers.

use crate::peer::{NetMessage, PeerManager, VideoCommand};
use crate::{CLOCK_PING_INTERVAL_MS, Result, SYNC_INTERVAL_MS};
use itk_protocol::SyncState;
use itk_sync::{ClockSync, DriftCorrector, PlaybackSync};
use std::collections::HashMap;
use std::net::SocketAddr;
use std::time::Instant;
use tracing::{debug, info};

/// Manages synchronization state for a session
pub struct SyncManager {
    /// Our local playback state
    local_sync: PlaybackSync,
    /// Whether we are the leader
    is_leader: bool,
    /// Drift corrector (for followers)
    drift_corrector: DriftCorrector,
    /// Per-peer clock sync (for leader to track followers)
    peer_clocks: HashMap<String, ClockSync>,
    /// Last sync broadcast time
    last_sync_broadcast: Instant,
    /// Last clock ping time
    last_clock_ping: Instant,
    /// Pending clock pings (peer_id -> send_time_ms)
    pending_pings: HashMap<String, u64>,
}

impl SyncManager {
    /// Create a new sync manager
    pub fn new(content_id: String, is_leader: bool) -> Self {
        Self {
            local_sync: PlaybackSync::new(content_id),
            is_leader,
            drift_corrector: DriftCorrector::new(),
            peer_clocks: HashMap::new(),
            last_sync_broadcast: Instant::now(),
            last_clock_ping: Instant::now(),
            pending_pings: HashMap::new(),
        }
    }

    /// Set whether we are the leader
    pub fn set_leader(&mut self, is_leader: bool) {
        self.is_leader = is_leader;
        info!(is_leader, "Leader status changed");
    }

    /// Get current local position (with drift correction if follower)
    pub fn current_position_ms(&self) -> u64 {
        self.local_sync.current_position_ms()
    }

    /// Get the recommended playback rate (for drift correction)
    pub fn playback_rate(&self) -> f64 {
        if self.is_leader {
            1.0
        } else {
            self.drift_corrector
                .calculate_rate(self.local_sync.current_position_ms())
        }
    }

    /// Check if we should seek to correct large drift
    pub fn should_seek(&self) -> Option<u64> {
        if self.is_leader {
            None
        } else {
            self.drift_corrector
                .should_seek(self.local_sync.current_position_ms())
        }
    }

    /// Get current drift in milliseconds (followers only)
    pub fn drift_ms(&self) -> Option<i64> {
        if self.is_leader {
            None
        } else {
            self.drift_corrector
                .current_drift_ms(self.local_sync.current_position_ms())
        }
    }

    /// Load new content
    pub fn load(&mut self, content_id: String) {
        self.local_sync = PlaybackSync::new(content_id);
    }

    /// Start playback
    pub fn play(&mut self) {
        self.local_sync.set_playing(true);
    }

    /// Pause playback
    pub fn pause(&mut self) {
        self.local_sync.set_playing(false);
    }

    /// Seek to position
    pub fn seek(&mut self, position_ms: u64) {
        self.local_sync.seek(position_ms);
    }

    /// Check if currently playing
    pub fn is_playing(&self) -> bool {
        self.local_sync.is_playing
    }

    /// Get the content ID
    pub fn content_id(&self) -> &str {
        &self.local_sync.content_id
    }

    /// Process received sync state (from leader)
    pub fn receive_sync_state(&mut self, state: SyncState) {
        if self.is_leader {
            // Leaders ignore sync states from others
            return;
        }

        debug!(
            position = state.position_at_ref_ms,
            playing = state.is_playing,
            "Received sync state"
        );

        // Update drift corrector target
        let playback_sync = PlaybackSync {
            content_id: state.content_id.clone(),
            position_at_ref_ms: state.position_at_ref_ms,
            ref_wallclock_ms: state.ref_wallclock_ms,
            is_playing: state.is_playing,
            playback_rate: state.playback_rate,
        };
        self.drift_corrector.update_target(playback_sync.clone());

        // Update local sync if content changed
        if self.local_sync.content_id != state.content_id {
            self.local_sync.content_id = state.content_id;
        }

        // Match play/pause state
        if self.local_sync.is_playing != state.is_playing {
            self.local_sync.set_playing(state.is_playing);
        }
    }

    /// Process received clock ping
    pub fn receive_clock_ping(
        &mut self,
        _from: &str,
        ping: itk_protocol::ClockPing,
        peer_manager: &mut PeerManager,
        peer_addr: SocketAddr,
    ) {
        let pong = itk_protocol::ClockPong {
            sender_time_ms: ping.sender_time_ms,
            receiver_time_ms: itk_sync::now_ms(),
        };
        let msg = NetMessage::ClockPong(pong);
        let _ = peer_manager.send_unreliable(peer_addr, &msg);
    }

    /// Process received clock pong
    pub fn receive_clock_pong(&mut self, from: &str, pong: itk_protocol::ClockPong) {
        let recv_time = itk_sync::now_ms();

        if self.is_leader {
            // Leader tracks clock offset to each peer
            let clock = self.peer_clocks.entry(from.to_string()).or_default();
            clock.process_pong(pong.sender_time_ms, pong.receiver_time_ms, recv_time);
        } else {
            // Follower uses drift corrector's clock sync
            self.drift_corrector.clock_sync_mut().process_pong(
                pong.sender_time_ms,
                pong.receiver_time_ms,
                recv_time,
            );
        }

        self.pending_pings.remove(from);
    }

    /// Periodic update - call this regularly
    pub fn update(&mut self, peer_manager: &mut PeerManager) -> Result<()> {
        let now = Instant::now();

        // Leader broadcasts sync state
        if self.is_leader
            && now.duration_since(self.last_sync_broadcast).as_millis() as u64 >= SYNC_INTERVAL_MS
        {
            self.broadcast_sync_state(peer_manager)?;
            self.last_sync_broadcast = now;
        }

        // Send clock pings periodically
        if now.duration_since(self.last_clock_ping).as_millis() as u64 >= CLOCK_PING_INTERVAL_MS {
            self.send_clock_pings(peer_manager)?;
            self.last_clock_ping = now;
        }

        Ok(())
    }

    fn broadcast_sync_state(&mut self, peer_manager: &mut PeerManager) -> Result<()> {
        let state = SyncState {
            content_id: self.local_sync.content_id.clone(),
            position_at_ref_ms: self.local_sync.position_at_ref_ms,
            ref_wallclock_ms: self.local_sync.ref_wallclock_ms,
            is_playing: self.local_sync.is_playing,
            playback_rate: self.local_sync.playback_rate,
        };

        let msg = NetMessage::SyncState(state);
        peer_manager.broadcast(&msg)
    }

    fn send_clock_pings(&mut self, peer_manager: &mut PeerManager) -> Result<()> {
        let now_ms = itk_sync::now_ms();
        let peers: Vec<_> = peer_manager
            .peers()
            .into_iter()
            .map(|p| (p.id(), p.addr))
            .collect();

        for (peer_id, addr) in peers {
            let ping = itk_protocol::ClockPing {
                sender_time_ms: now_ms,
            };
            self.pending_pings.insert(peer_id, now_ms);
            let msg = NetMessage::ClockPing(ping);
            let _ = peer_manager.send_unreliable(addr, &msg);
        }

        Ok(())
    }

    /// Send a video command to all peers (leader only)
    pub fn send_command(
        &mut self,
        cmd: VideoCommand,
        peer_manager: &mut PeerManager,
    ) -> Result<()> {
        if !self.is_leader {
            return Ok(());
        }

        // Apply locally first
        match &cmd {
            VideoCommand::Load { url } => {
                self.load(url.clone());
            },
            VideoCommand::Play => {
                self.play();
            },
            VideoCommand::Pause => {
                self.pause();
            },
            VideoCommand::Seek { position_ms } => {
                self.seek(*position_ms);
            },
        }

        // Broadcast to peers
        let msg = NetMessage::VideoCommand(cmd);
        peer_manager.broadcast_reliable(&msg)
    }

    /// Process a received video command (followers)
    pub fn receive_command(&mut self, cmd: VideoCommand) {
        if self.is_leader {
            return; // Leaders don't take commands
        }

        match cmd {
            VideoCommand::Load { url } => {
                info!(url = %url, "Received load command");
                self.load(url);
            },
            VideoCommand::Play => {
                info!("Received play command");
                self.play();
            },
            VideoCommand::Pause => {
                info!("Received pause command");
                self.pause();
            },
            VideoCommand::Seek { position_ms } => {
                info!(position_ms, "Received seek command");
                self.seek(position_ms);
            },
        }
    }
}
