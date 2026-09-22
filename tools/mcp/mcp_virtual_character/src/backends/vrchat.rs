//! VRChat backend adapter (OSC over UDP).
//!
//! Sends avatar/input messages to VRChat's OSC input port (default 9000) and
//! listens for VRChat's OSC output (default 9001) to track avatar parameters
//! and detect whether VRChat is actually running.
//!
//! # Emote semantics
//!
//! Emotions and gestures are expressed through the integer `VRCEmote`
//! parameter. Many avatars treat the gesture wheel as *toggles*: resending the
//! active value turns it off, and `0` does not clear it. Standard avatars
//! instead clear on `0`. Clearing therefore sends the active value followed by
//! `0`, which works for both. Emote state lives behind a single async mutex so
//! concurrent tool calls, the sequence player and the emote auto-clear timer
//! cannot interleave toggles.
//!
//! # Lifecycle
//!
//! All background work (OSC receiver, movement auto-stop, emote auto-clear,
//! audio-state reset) runs in tasks owned by the backend. `disconnect`, a
//! reconnect, or dropping the backend aborts them and releases the UDP ports,
//! so switching backends or reconnecting never leaves a stale listener bound
//! to 9001.

use async_trait::async_trait;
use rosc::{encoder, OscMessage, OscPacket, OscType};
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex as StdMutex, MutexGuard};
use std::time::{Duration, Instant};
use tokio::net::UdpSocket;
use tokio::sync::Mutex;
use tokio::task::JoinHandle;
use tokio::time::sleep;
use tracing::{debug, info, warn};

use super::adapter::{AudioOutcome, BackendAdapter, BackendError, BackendResult, EmoteAction};
use super::movement::{
    parse_avatar_params, parse_movement, validate_param_name, AvatarParamValue, MovementCommand,
};
use crate::audio::{AudioFormat, AudioPlayer, DEFAULT_MAX_PLAYBACK};
use crate::audio_emotion_mappings::{
    extract_tags_from_text, get_dominant_emotion_from_tags, strip_tags,
};
use crate::constants::{
    get_vrcemote_name, vrcemote_for_emotion, vrcemote_for_gesture, VRCEmoteValue,
    DEFAULT_AUDIO_DEVICE, DEFAULT_EMOTE_TIMEOUT_SECS, DEFAULT_OSC_IN_PORT, DEFAULT_OSC_OUT_PORT,
    DEFAULT_VRCHAT_HOST,
};
use crate::types::{
    AudioData, BackendCapabilities, CanonicalAnimationData, EmotionType, EnvironmentState,
    GestureType,
};

/// OSC address of the emote parameter.
const VRCEMOTE_ADDR: &str = "/avatar/parameters/VRCEmote";
/// Avatar float parameter set to 1 while audio is playing.
const AUDIO_PLAYING_ADDR: &str = "/avatar/parameters/AudioPlaying";
/// VRChat chatbox input address: (text, send_immediately, notify).
const CHATBOX_ADDR: &str = "/chatbox/input";
/// VRChat chatbox message limit (characters).
const CHATBOX_MAX_CHARS: usize = 144;
/// Pause between toggling one emote off and another on.
const EMOTE_SWITCH_DELAY: Duration = Duration::from_millis(100);
/// Timeout for resolving `remote_host`.
const RESOLVE_TIMEOUT: Duration = Duration::from_secs(5);
/// Fallback for resetting `AudioPlaying` when duration is unknown and audio
/// is not played locally.
const AUDIO_STATE_FALLBACK: Duration = Duration::from_secs(10);
/// Cap on tracked avatar parameters (protects against OSC floods).
const MAX_TRACKED_PARAMS: usize = 1024;
/// VRChat is considered "responding" if OSC arrived within this window.
const RESPONDING_WINDOW: Duration = Duration::from_secs(30);

/// Where `play_audio` audio is rendered.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum AudioPlaybackMode {
    /// `local` when VRChat is on this machine (loopback host), else `none`.
    #[default]
    Auto,
    /// Play on this machine's audio output (route it to VRChat's microphone
    /// with a virtual cable such as VoiceMeeter).
    Local,
    /// Do not play audio; only send expression/`AudioPlaying` OSC state.
    None,
}

impl AudioPlaybackMode {
    fn parse(s: &str) -> Option<Self> {
        match s.trim().to_lowercase().as_str() {
            "auto" => Some(Self::Auto),
            "local" => Some(Self::Local),
            "none" | "off" => Some(Self::None),
            _ => None,
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::Auto => "auto",
            Self::Local => "local",
            Self::None => "none",
        }
    }
}

/// Validated VRChat backend configuration.
#[derive(Debug, Clone, PartialEq)]
pub struct VRChatConfig {
    /// Host running VRChat.
    pub remote_host: String,
    /// VRChat's OSC input port (we send here).
    pub osc_in_port: u16,
    /// VRChat's OSC output port (we listen here).
    pub osc_out_port: u16,
    /// Express emotions/gestures through `VRCEmote`.
    pub use_vrcemote: bool,
    /// Seconds before an active emote is toggled off automatically (0 disables).
    pub emote_timeout: f64,
    /// Listen for VRChat's OSC output.
    pub listen: bool,
    /// Audio playback mode.
    pub audio_playback: AudioPlaybackMode,
    /// Output device for local playback (VLC/paplay device name).
    pub audio_device: Option<String>,
    /// Show `play_audio` transcripts in the VRChat chatbox.
    pub chatbox_transcripts: bool,
}

impl Default for VRChatConfig {
    fn default() -> Self {
        Self {
            remote_host: DEFAULT_VRCHAT_HOST.to_string(),
            osc_in_port: DEFAULT_OSC_IN_PORT,
            osc_out_port: DEFAULT_OSC_OUT_PORT,
            use_vrcemote: true,
            emote_timeout: DEFAULT_EMOTE_TIMEOUT_SECS,
            listen: true,
            audio_playback: AudioPlaybackMode::Auto,
            audio_device: Some(DEFAULT_AUDIO_DEVICE.to_string()),
            chatbox_transcripts: false,
        }
    }
}

/// Raw `set_backend.config` object. Accepts the legacy Python aliases
/// `vrchat_recv_port` / `vrchat_send_port`.
#[derive(Debug, Default, Deserialize)]
struct RawConfig {
    remote_host: Option<String>,
    #[serde(alias = "vrchat_recv_port")]
    osc_in_port: Option<i64>,
    #[serde(alias = "vrchat_send_port")]
    osc_out_port: Option<i64>,
    use_vrcemote: Option<bool>,
    emote_timeout: Option<f64>,
    listen: Option<bool>,
    audio_playback: Option<String>,
    audio_device: Option<String>,
    chatbox_transcripts: Option<bool>,
}

fn port(value: i64, name: &str) -> BackendResult<u16> {
    u16::try_from(value)
        .ok()
        .filter(|p| *p != 0)
        .ok_or_else(|| {
            BackendError::InvalidParameter(format!("{name} must be 1-65535, got {value}"))
        })
}

impl VRChatConfig {
    /// Defaults overridden by environment variables:
    /// `VIRTUAL_CHARACTER_HOST`, `VIRTUAL_CHARACTER_OSC_IN`,
    /// `VIRTUAL_CHARACTER_OSC_OUT`, `VIRTUAL_CHARACTER_USE_VRCEMOTE`,
    /// `VIRTUAL_CHARACTER_EMOTE_TIMEOUT`, `VIRTUAL_CHARACTER_AUDIO_PLAYBACK`,
    /// `VIRTUAL_CHARACTER_AUDIO_DEVICE`. Invalid values are ignored with a
    /// warning.
    pub fn from_env() -> Self {
        Self::from_env_with(|k| std::env::var(k).ok())
    }

    /// [`from_env`](Self::from_env) with an injectable lookup (for tests).
    pub fn from_env_with(get: impl Fn(&str) -> Option<String>) -> Self {
        let mut c = Self::default();
        let get = |k: &str| {
            get(k)
                .map(|v| v.trim().to_string())
                .filter(|v| !v.is_empty())
        };
        if let Some(h) = get("VIRTUAL_CHARACTER_HOST") {
            c.remote_host = h;
        }
        let parse_port = |k: &str, cur: &mut u16| {
            if let Some(v) = get(k) {
                match v.parse::<u16>() {
                    Ok(p) if p != 0 => *cur = p,
                    _ => warn!("Ignoring invalid {}={}", k, v),
                }
            }
        };
        parse_port("VIRTUAL_CHARACTER_OSC_IN", &mut c.osc_in_port);
        parse_port("VIRTUAL_CHARACTER_OSC_OUT", &mut c.osc_out_port);
        if let Some(v) = get("VIRTUAL_CHARACTER_USE_VRCEMOTE") {
            match v.to_lowercase().as_str() {
                "1" | "true" | "yes" | "on" => c.use_vrcemote = true,
                "0" | "false" | "no" | "off" => c.use_vrcemote = false,
                _ => warn!("Ignoring invalid VIRTUAL_CHARACTER_USE_VRCEMOTE={}", v),
            }
        }
        if let Some(v) = get("VIRTUAL_CHARACTER_EMOTE_TIMEOUT") {
            match v.parse::<f64>() {
                Ok(t) if t.is_finite() && t >= 0.0 => c.emote_timeout = t,
                _ => warn!("Ignoring invalid VIRTUAL_CHARACTER_EMOTE_TIMEOUT={}", v),
            }
        }
        if let Some(v) = get("VIRTUAL_CHARACTER_AUDIO_PLAYBACK") {
            match AudioPlaybackMode::parse(&v) {
                Some(m) => c.audio_playback = m,
                None => warn!("Ignoring invalid VIRTUAL_CHARACTER_AUDIO_PLAYBACK={}", v),
            }
        }
        if let Some(v) = get("VIRTUAL_CHARACTER_AUDIO_DEVICE") {
            c.audio_device = Some(v);
        }
        c
    }

    /// Apply a `set_backend.config` object on top of `self`.
    pub fn merged_with(mut self, config: &HashMap<String, Value>) -> BackendResult<Self> {
        let raw: RawConfig = serde_json::from_value(Value::Object(
            config.iter().map(|(k, v)| (k.clone(), v.clone())).collect(),
        ))
        .map_err(|e| {
            BackendError::InvalidParameter(format!("invalid vrchat_remote config: {e}"))
        })?;

        if let Some(h) = raw.remote_host {
            let h = h.trim().to_string();
            if h.is_empty() || h.len() > 253 || h.contains(char::is_whitespace) {
                return Err(BackendError::InvalidParameter(format!(
                    "invalid remote_host '{h}'"
                )));
            }
            self.remote_host = h;
        }
        if let Some(p) = raw.osc_in_port {
            self.osc_in_port = port(p, "osc_in_port")?;
        }
        if let Some(p) = raw.osc_out_port {
            self.osc_out_port = port(p, "osc_out_port")?;
        }
        if let Some(v) = raw.use_vrcemote {
            self.use_vrcemote = v;
        }
        if let Some(t) = raw.emote_timeout {
            if !t.is_finite() || !(0.0..=3600.0).contains(&t) {
                return Err(BackendError::InvalidParameter(
                    "emote_timeout must be between 0 and 3600 seconds".to_string(),
                ));
            }
            self.emote_timeout = t;
        }
        if let Some(v) = raw.listen {
            self.listen = v;
        }
        if let Some(m) = raw.audio_playback {
            self.audio_playback = AudioPlaybackMode::parse(&m).ok_or_else(|| {
                BackendError::InvalidParameter(format!(
                    "audio_playback must be auto, local or none, got '{m}'"
                ))
            })?;
        }
        if let Some(d) = raw.audio_device {
            let d = d.trim().to_string();
            self.audio_device = if d.is_empty() { None } else { Some(d) };
        }
        if let Some(v) = raw.chatbox_transcripts {
            self.chatbox_transcripts = v;
        }
        Ok(self)
    }

    /// Resolve `Auto` against the target address.
    fn effective_audio_mode(&self, target: &SocketAddr) -> AudioPlaybackMode {
        match self.audio_playback {
            AudioPlaybackMode::Auto if target.ip().is_loopback() => AudioPlaybackMode::Local,
            AudioPlaybackMode::Auto => AudioPlaybackMode::None,
            m => m,
        }
    }
}

/// Emote tracking (guarded by an async mutex, see module docs).
#[derive(Debug, Default)]
struct EmoteState {
    current: i32,
    active: bool,
}

/// Lock a std mutex, recovering from poisoning (the protected data is plain
/// state that stays consistent even if a holder panicked).
fn lock<T>(m: &StdMutex<T>) -> MutexGuard<'_, T> {
    m.lock().unwrap_or_else(|e| e.into_inner())
}

/// Connection state shared with background tasks.
struct Shared {
    socket: UdpSocket,
    target: SocketAddr,
    config: VRChatConfig,
    audio_mode: AudioPlaybackMode,
    connected_at: Instant,

    emote: Mutex<EmoteState>,
    current_emotion: StdMutex<EmotionType>,
    current_gesture: StdMutex<GestureType>,
    avatar_params: StdMutex<HashMap<String, Value>>,
    avatar_id: StdMutex<Option<String>>,
    world_name: StdMutex<Option<String>>,
    receiver_status: StdMutex<String>,
    /// Milliseconds since `connected_at` of the last received OSC packet + 1
    /// (0 = never).
    last_received_ms: AtomicU64,

    osc_sent: AtomicU64,
    osc_received: AtomicU64,
    animation_frames: AtomicU64,
    audio_clips: AtomicU64,
    errors: AtomicU64,
}

impl Shared {
    async fn send(&self, address: &str, args: Vec<OscType>) -> BackendResult<()> {
        let packet = OscPacket::Message(OscMessage {
            addr: address.to_string(),
            args,
        });
        let encoded = encoder::encode(&packet)
            .map_err(|e| BackendError::OscError(format!("failed to encode {address}: {e}")))?;
        match self.socket.send_to(&encoded, self.target).await {
            Ok(_) => {
                self.osc_sent.fetch_add(1, Ordering::Relaxed);
                debug!("OSC -> {} {:?}", address, packet_args(&packet));
                Ok(())
            },
            Err(e) => {
                self.errors.fetch_add(1, Ordering::Relaxed);
                Err(BackendError::NetworkError(format!(
                    "failed to send {address} to {}: {e}",
                    self.target
                )))
            },
        }
    }

    async fn send_int(&self, address: &str, v: i32) -> BackendResult<()> {
        self.send(address, vec![OscType::Int(v)]).await
    }

    async fn send_float(&self, address: &str, v: f32) -> BackendResult<()> {
        self.send(address, vec![OscType::Float(v)]).await
    }

    /// Toggle off the active emote (resend it, then send 0).
    async fn clear_locked(&self, st: &mut EmoteState) -> BackendResult<bool> {
        if st.active && st.current != 0 {
            let cur = st.current;
            self.send_int(VRCEMOTE_ADDR, cur).await?;
            self.send_int(VRCEMOTE_ADDR, 0).await?;
            st.active = false;
            st.current = 0;
            info!("Cleared VRCEmote {} ({})", cur, get_vrcemote_name(cur));
            Ok(true)
        } else {
            st.current = 0;
            st.active = false;
            Ok(false)
        }
    }

    async fn clear_emote(&self) -> BackendResult<bool> {
        let mut st = self.emote.lock().await;
        self.clear_locked(&mut st).await
    }

    /// Clear only if `value` is still the active emote (used by the timer).
    async fn clear_emote_if(&self, value: i32) -> BackendResult<bool> {
        let mut st = self.emote.lock().await;
        if st.active && st.current == value {
            self.clear_locked(&mut st).await
        } else {
            Ok(false)
        }
    }

    /// Apply the toggle state machine for `value` (1-8, or 0 to clear).
    async fn set_emote(&self, value: i32) -> BackendResult<EmoteAction> {
        let mut st = self.emote.lock().await;
        if value == 0 {
            return Ok(if self.clear_locked(&mut st).await? {
                EmoteAction::Cleared
            } else {
                EmoteAction::Unchanged
            });
        }
        if st.active && st.current == value {
            self.clear_locked(&mut st).await?;
            return Ok(EmoteAction::ToggledOff);
        }
        if st.active && st.current != 0 {
            self.clear_locked(&mut st).await?;
            sleep(EMOTE_SWITCH_DELAY).await;
        }
        self.send_int(VRCEMOTE_ADDR, value).await?;
        st.current = value;
        st.active = true;
        info!("Set VRCEmote {} ({})", value, get_vrcemote_name(value));
        Ok(EmoteAction::Activated)
    }

    fn record_received(&self) {
        self.osc_received.fetch_add(1, Ordering::Relaxed);
        let ms = self.connected_at.elapsed().as_millis() as u64 + 1;
        self.last_received_ms.store(ms, Ordering::Relaxed);
    }

    fn last_received_ago(&self) -> Option<Duration> {
        match self.last_received_ms.load(Ordering::Relaxed) {
            0 => None,
            ms => Some(
                self.connected_at
                    .elapsed()
                    .saturating_sub(Duration::from_millis(ms - 1)),
            ),
        }
    }

    /// Apply one incoming OSC packet to tracked state.
    fn handle_packet(&self, packet: OscPacket, depth: usize) {
        match packet {
            OscPacket::Message(msg) => self.handle_message(msg),
            OscPacket::Bundle(bundle) if depth < 8 => {
                for p in bundle.content {
                    self.handle_packet(p, depth + 1);
                }
            },
            OscPacket::Bundle(_) => {},
        }
    }

    fn handle_message(&self, msg: OscMessage) {
        if let Some(name) = msg.addr.strip_prefix("/avatar/parameters/") {
            let value = match msg.args.first() {
                Some(OscType::Float(f)) => json!(f),
                Some(OscType::Int(i)) => json!(i),
                Some(OscType::Bool(b)) => json!(b),
                Some(OscType::String(s)) => json!(s),
                _ => return,
            };
            let mut params = lock(&self.avatar_params);
            if params.len() < MAX_TRACKED_PARAMS || params.contains_key(name) {
                params.insert(name.to_string(), value);
            }
        } else if msg.addr == "/avatar/change" {
            if let Some(OscType::String(id)) = msg.args.first() {
                info!("VRChat avatar changed: {}", id);
                *lock(&self.avatar_id) = Some(id.clone());
                // Parameters belong to the previous avatar.
                lock(&self.avatar_params).clear();
            }
        } else if msg.addr.starts_with("/world/") {
            if let Some(OscType::String(name)) = msg.args.first() {
                *lock(&self.world_name) = Some(name.clone());
            }
        }
    }
}

fn packet_args(p: &OscPacket) -> Vec<OscType> {
    match p {
        OscPacket::Message(m) => m.args.clone(),
        OscPacket::Bundle(_) => Vec::new(),
    }
}

/// Ensure a socket is not inherited by child processes.
///
/// Audio players are spawned as child processes. On Windows, sockets can end
/// up inheritable (e.g. when a Layered Service Provider is installed), in
/// which case a long-running player would keep the OSC listener port bound
/// after we close it, breaking reconnects until the player exits.
#[cfg(windows)]
fn make_non_inheritable(socket: &UdpSocket) {
    use std::os::windows::io::AsRawSocket;
    const HANDLE_FLAG_INHERIT: u32 = 0x0000_0001;
    #[link(name = "kernel32")]
    extern "system" {
        fn SetHandleInformation(handle: *mut std::ffi::c_void, mask: u32, flags: u32) -> i32;
    }
    // SAFETY: the raw socket is a valid handle owned by `socket` for the
    // duration of this call; SetHandleInformation only changes its
    // inheritance flag and does not take ownership.
    let ok = unsafe {
        SetHandleInformation(
            socket.as_raw_socket() as usize as *mut std::ffi::c_void,
            HANDLE_FLAG_INHERIT,
            0,
        )
    };
    if ok == 0 {
        debug!(
            "SetHandleInformation failed: {}",
            std::io::Error::last_os_error()
        );
    }
}

/// Sockets are created close-on-exec on Unix; nothing to do.
#[cfg(not(windows))]
fn make_non_inheritable(_socket: &UdpSocket) {}

/// Background tasks owned by a connection.
#[derive(Default)]
struct Tasks {
    receiver: Option<JoinHandle<()>>,
    movement: Option<JoinHandle<()>>,
    emote_timeout: Option<JoinHandle<()>>,
    audio_state: Option<JoinHandle<()>>,
}

impl Tasks {
    fn abort_all(&mut self) {
        for h in [
            self.receiver.take(),
            self.movement.take(),
            self.emote_timeout.take(),
            self.audio_state.take(),
        ]
        .into_iter()
        .flatten()
        {
            h.abort();
        }
    }
}

/// Replace a task slot, aborting the previous task.
fn replace_task(slot: &mut Option<JoinHandle<()>>, new: JoinHandle<()>) {
    if let Some(old) = slot.replace(new) {
        old.abort();
    }
}

/// VRChat backend controlling an avatar via OSC.
pub struct VRChatRemoteBackend {
    capabilities: BackendCapabilities,
    shared: Option<Arc<Shared>>,
    tasks: StdMutex<Tasks>,
    connected: AtomicBool,
    player: AudioPlayer,
}

impl Default for VRChatRemoteBackend {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for VRChatRemoteBackend {
    fn drop(&mut self) {
        lock(&self.tasks).abort_all();
    }
}

impl VRChatRemoteBackend {
    /// Create a new (disconnected) VRChat backend.
    pub fn new() -> Self {
        Self {
            capabilities: BackendCapabilities {
                animation: true,
                audio: true,
                bidirectional: true,
                ..Default::default()
            },
            shared: None,
            tasks: StdMutex::new(Tasks::default()),
            connected: AtomicBool::new(false),
            player: AudioPlayer::default(),
        }
    }

    fn shared(&self) -> BackendResult<Arc<Shared>> {
        match (&self.shared, self.is_connected()) {
            (Some(s), true) => Ok(s.clone()),
            _ => Err(BackendError::NotConnected),
        }
    }

    /// Resolve `host:port`, preferring IPv4.
    async fn resolve(host: &str, port: u16) -> BackendResult<SocketAddr> {
        let addrs: Vec<SocketAddr> =
            tokio::time::timeout(RESOLVE_TIMEOUT, tokio::net::lookup_host((host, port)))
                .await
                .map_err(|_| BackendError::Timeout(format!("resolving {host} timed out")))?
                .map_err(|e| BackendError::ConnectionFailed(format!("cannot resolve {host}: {e}")))?
                .collect();
        addrs
            .iter()
            .find(|a| a.is_ipv4())
            .or_else(|| addrs.first())
            .copied()
            .ok_or_else(|| BackendError::ConnectionFailed(format!("no address for {host}")))
    }

    fn spawn_receiver(shared: Arc<Shared>, socket: UdpSocket) -> JoinHandle<()> {
        tokio::spawn(async move {
            let mut buf = vec![0u8; 65_536];
            loop {
                match socket.recv_from(&mut buf).await {
                    Ok((size, _from)) => {
                        shared.record_received();
                        match rosc::decoder::decode_udp(&buf[..size]) {
                            Ok((_, packet)) => shared.handle_packet(packet, 0),
                            Err(e) => debug!("Ignoring malformed OSC packet: {}", e),
                        }
                    },
                    Err(e) => {
                        // Windows reports ICMP port-unreachable as a recv error
                        // (WSAECONNRESET); it is not fatal for a UDP listener.
                        debug!("OSC receive error: {}", e);
                        sleep(Duration::from_millis(50)).await;
                    },
                }
            }
        })
    }

    fn schedule_emote_timeout(&self, shared: &Arc<Shared>, value: i32) {
        let timeout = shared.config.emote_timeout;
        if timeout <= 0.0 {
            return;
        }
        let s = shared.clone();
        let handle = tokio::spawn(async move {
            sleep(Duration::from_secs_f64(timeout)).await;
            match s.clear_emote_if(value).await {
                Ok(true) => info!("Emote {} auto-cleared after {}s", value, timeout),
                Ok(false) => {},
                Err(e) => warn!("Emote auto-clear failed: {}", e),
            }
        });
        replace_task(&mut lock(&self.tasks).emote_timeout, handle);
    }

    fn cancel_emote_timeout(&self) {
        if let Some(h) = lock(&self.tasks).emote_timeout.take() {
            h.abort();
        }
    }

    /// Emote change with timer bookkeeping.
    async fn apply_emote(&self, shared: &Arc<Shared>, value: i32) -> BackendResult<EmoteAction> {
        let action = shared.set_emote(value).await?;
        match action {
            EmoteAction::Activated => self.schedule_emote_timeout(shared, value),
            _ => self.cancel_emote_timeout(),
        }
        Ok(action)
    }

    async fn apply_movement(&self, shared: &Arc<Shared>, m: &MovementCommand) -> BackendResult<()> {
        // Many emotes lock locomotion; clear before moving.
        if (m.has_motion() || m.jump) && shared.clear_emote().await? {
            self.cancel_emote_timeout();
            sleep(EMOTE_SWITCH_DELAY).await;
        }

        let axes = [
            ("/input/Vertical", m.forward),
            ("/input/Horizontal", m.right),
            ("/input/LookHorizontal", m.look_horizontal),
            ("/input/LookVertical", m.look_vertical),
        ];
        for (addr, v) in axes {
            if let Some(v) = v {
                shared.send_float(addr, v).await?;
            }
        }
        if let Some(run) = m.run {
            shared.send_int("/input/Run", run as i32).await?;
        }
        if let Some(crouch) = m.crouch {
            shared.send_int("/input/Crouch", crouch as i32).await?;
        }
        if m.jump {
            shared.send_int("/input/Jump", 1).await?;
            sleep(Duration::from_millis(100)).await;
            shared.send_int("/input/Jump", 0).await?;
        }

        let mut tasks = lock(&self.tasks);
        if m.has_motion() {
            let s = shared.clone();
            let duration = m.duration;
            let set_axes: Vec<&'static str> = axes
                .iter()
                .filter(|(_, v)| v.is_some())
                .map(|(a, _)| *a)
                .collect();
            let handle = tokio::spawn(async move {
                sleep(Duration::from_secs_f64(duration)).await;
                for addr in set_axes {
                    if let Err(e) = s.send_float(addr, 0.0).await {
                        warn!("Movement auto-stop failed: {}", e);
                    }
                }
                debug!("Movement auto-stopped after {}s", duration);
            });
            replace_task(&mut tasks.movement, handle);
        } else if axes.iter().any(|(_, v)| v.is_some()) {
            // Explicit zero axes: the caller stopped motion; drop the timer.
            if let Some(h) = tasks.movement.take() {
                h.abort();
            }
        }
        Ok(())
    }

    async fn send_chatbox(shared: &Shared, text: &str) -> BackendResult<()> {
        let clean = strip_tags(text);
        if clean.is_empty() {
            return Ok(());
        }
        let truncated: String = clean.chars().take(CHATBOX_MAX_CHARS).collect();
        shared
            .send(
                CHATBOX_ADDR,
                vec![
                    OscType::String(truncated),
                    OscType::Bool(true),
                    OscType::Bool(false),
                ],
            )
            .await
    }
}

#[async_trait]
impl BackendAdapter for VRChatRemoteBackend {
    fn backend_name(&self) -> &'static str {
        "vrchat_remote"
    }

    fn is_connected(&self) -> bool {
        self.connected.load(Ordering::SeqCst)
    }

    fn capabilities(&self) -> &BackendCapabilities {
        &self.capabilities
    }

    async fn connect(&mut self, config: HashMap<String, Value>) -> BackendResult<()> {
        // Release any previous connection first (frees the listener port).
        self.disconnect().await?;

        let cfg = VRChatConfig::from_env().merged_with(&config)?;
        info!(
            "Connecting to VRChat OSC at {}:{} (listen on {})",
            cfg.remote_host, cfg.osc_in_port, cfg.osc_out_port
        );
        let target = Self::resolve(&cfg.remote_host, cfg.osc_in_port).await?;
        let bind_addr = if target.is_ipv4() {
            "0.0.0.0:0"
        } else {
            "[::]:0"
        };
        let socket = UdpSocket::bind(bind_addr)
            .await
            .map_err(|e| BackendError::NetworkError(format!("failed to bind OSC socket: {e}")))?;
        make_non_inheritable(&socket);

        let receiver_socket = if cfg.listen {
            match UdpSocket::bind(("0.0.0.0", cfg.osc_out_port)).await {
                Ok(s) => {
                    make_non_inheritable(&s);
                    Some(s)
                },
                Err(e) => {
                    warn!(
                        "Could not listen on OSC port {}: {} - continuing send-only",
                        cfg.osc_out_port, e
                    );
                    None
                },
            }
        } else {
            None
        };
        let receiver_status = match (&receiver_socket, cfg.listen) {
            (Some(_), _) => format!("listening on 0.0.0.0:{}", cfg.osc_out_port),
            (None, true) => format!(
                "send-only: port {} unavailable (another OSC app or server instance is using it)",
                cfg.osc_out_port
            ),
            (None, false) => "disabled (listen=false)".to_string(),
        };

        let audio_mode = cfg.effective_audio_mode(&target);
        self.player = AudioPlayer::new(cfg.audio_device.clone());
        let shared = Arc::new(Shared {
            socket,
            target,
            audio_mode,
            connected_at: Instant::now(),
            emote: Mutex::new(EmoteState::default()),
            current_emotion: StdMutex::new(EmotionType::Neutral),
            current_gesture: StdMutex::new(GestureType::None),
            avatar_params: StdMutex::new(HashMap::new()),
            avatar_id: StdMutex::new(None),
            world_name: StdMutex::new(None),
            receiver_status: StdMutex::new(receiver_status),
            last_received_ms: AtomicU64::new(0),
            osc_sent: AtomicU64::new(0),
            osc_received: AtomicU64::new(0),
            animation_frames: AtomicU64::new(0),
            audio_clips: AtomicU64::new(0),
            errors: AtomicU64::new(0),
            config: cfg,
        });

        if let Some(rs) = receiver_socket {
            lock(&self.tasks).receiver = Some(Self::spawn_receiver(shared.clone(), rs));
        }
        self.shared = Some(shared);
        self.connected.store(true, Ordering::SeqCst);
        info!("VRChat backend ready (target {})", target);
        Ok(())
    }

    async fn disconnect(&mut self) -> BackendResult<()> {
        let was_connected = self.connected.swap(false, Ordering::SeqCst);
        let handles = {
            let mut tasks = lock(&self.tasks);
            [
                tasks.receiver.take(),
                tasks.movement.take(),
                tasks.emote_timeout.take(),
                tasks.audio_state.take(),
            ]
        };
        for h in handles.into_iter().flatten() {
            h.abort();
            // Await so the listener socket is closed before a reconnect binds.
            let _ = h.await;
        }
        self.shared = None;
        if was_connected {
            info!("Disconnected from VRChat");
        }
        Ok(())
    }

    async fn send_animation_data(&mut self, data: CanonicalAnimationData) -> BackendResult<()> {
        let shared = self.shared()?;

        // Validate everything before sending anything.
        let movement = parse_movement(&data.parameters)?;
        let mut avatar_params = parse_avatar_params(&data.parameters)?;
        for shape in data.blend_shapes.keys() {
            validate_param_name(shape)?;
        }
        // VRCEmote in avatar_params goes through the emote state machine.
        let raw_emote = avatar_params
            .iter()
            .position(|(n, _)| n == "VRCEmote")
            .map(|i| avatar_params.remove(i).1);

        let mut emote_sent = false;
        if let Some(v) = raw_emote {
            let value = match v {
                AvatarParamValue::Int(i) => i,
                AvatarParamValue::Float(f) => f.round() as i32,
                AvatarParamValue::Bool(b) => b as i32,
            };
            if !(VRCEmoteValue::MIN..=VRCEmoteValue::MAX).contains(&value) {
                return Err(BackendError::InvalidParameter(format!(
                    "VRCEmote must be 0-8, got {value}"
                )));
            }
            self.apply_emote(&shared, value).await?;
            emote_sent = true;
        }

        if let Some(gesture) = data.gesture {
            *lock(&shared.current_gesture) = gesture;
            if shared.config.use_vrcemote && !emote_sent {
                let v = vrcemote_for_gesture(gesture) as i32;
                if gesture == GestureType::None {
                    if shared.clear_emote().await? {
                        self.cancel_emote_timeout();
                    }
                } else if v != 0 {
                    self.apply_emote(&shared, v).await?;
                    emote_sent = true;
                } else {
                    debug!("Gesture {:?} has no VRCEmote mapping", gesture);
                }
            }
        }

        if let Some(emotion) = data.emotion {
            *lock(&shared.current_emotion) = emotion;
            // A gesture in the same frame takes priority over the emotion's emote.
            if shared.config.use_vrcemote && !emote_sent && data.gesture.is_none() {
                let v = vrcemote_for_emotion(emotion) as i32;
                if emotion == EmotionType::Neutral {
                    if shared.clear_emote().await? {
                        self.cancel_emote_timeout();
                    }
                } else if v != 0 {
                    self.apply_emote(&shared, v).await?;
                }
            }
        }

        for (shape, value) in &data.blend_shapes {
            if value.is_finite() {
                shared
                    .send_float(&format!("/avatar/parameters/BlendShape_{shape}"), *value)
                    .await?;
            }
        }

        if let Some(m) = movement {
            self.apply_movement(&shared, &m).await?;
        }

        for (name, value) in avatar_params {
            let arg = match value {
                AvatarParamValue::Int(i) => OscType::Int(i),
                AvatarParamValue::Float(f) => OscType::Float(f),
                AvatarParamValue::Bool(b) => OscType::Bool(b),
            };
            shared
                .send(&format!("/avatar/parameters/{name}"), vec![arg])
                .await?;
        }

        shared.animation_frames.fetch_add(1, Ordering::Relaxed);
        Ok(())
    }

    async fn send_audio_data(&mut self, audio: AudioData) -> BackendResult<AudioOutcome> {
        let shared = self.shared()?;
        shared.audio_clips.fetch_add(1, Ordering::Relaxed);
        let mut outcome = AudioOutcome::default();

        // Expression: dominant emotion from explicit tags, else from the text.
        let tags: Vec<String> = match (&audio.expression_tags, &audio.text) {
            (Some(t), _) if !t.is_empty() => t.clone(),
            (_, Some(text)) => extract_tags_from_text(text),
            _ => Vec::new(),
        };
        if let Some((emotion, _intensity)) = get_dominant_emotion_from_tags(&tags) {
            *lock(&shared.current_emotion) = emotion;
            outcome.emotion = Some(emotion.as_str().to_string());
            let v = vrcemote_for_emotion(emotion) as i32;
            if shared.config.use_vrcemote && v != 0 {
                // Do not toggle off an emote that is already showing this emotion.
                let already = {
                    let st = shared.emote.lock().await;
                    st.active && st.current == v
                };
                if !already {
                    self.apply_emote(&shared, v).await?;
                }
            }
        }

        // Playback.
        let mut done = None;
        match shared.audio_mode {
            AudioPlaybackMode::Local => {
                let format = AudioFormat::from_name(&audio.format).unwrap_or(AudioFormat::Unknown);
                let max = if audio.duration > 0.0 {
                    Duration::from_secs_f64(audio.duration as f64 * 1.5 + 5.0)
                } else {
                    DEFAULT_MAX_PLAYBACK
                };
                let result = self
                    .player
                    .play(
                        &audio.data,
                        format,
                        shared.config.audio_device.as_deref(),
                        max,
                    )
                    .await;
                match result {
                    Ok(playback) => {
                        outcome.played = true;
                        outcome.method = Some(playback.method);
                        done = Some(playback.done);
                    },
                    // Explicit local playback must fail loudly; `auto` degrades
                    // (e.g. inside a container with no audio player).
                    Err(e) if shared.config.audio_playback == AudioPlaybackMode::Local => {
                        return Err(BackendError::Audio(e));
                    },
                    Err(e) => {
                        warn!("Local audio playback unavailable: {}", e);
                        outcome
                            .notes
                            .push(format!("audio not played (audio_playback=auto): {e}"));
                    },
                }
            },
            _ => {
                outcome.notes.push(format!(
                    "audio not played: audio_playback={} (VRChat at {}). Run this server on the \
                     VRChat machine or set config.audio_playback=\"local\" and route the output \
                     to VRChat's microphone.",
                    shared.config.audio_playback.as_str(),
                    shared.target
                ));
            },
        }

        if shared.config.chatbox_transcripts {
            if let Some(text) = &audio.text {
                Self::send_chatbox(&shared, text).await?;
            }
        }

        shared.send_float(AUDIO_PLAYING_ADDR, 1.0).await?;
        let s = shared.clone();
        let duration = audio.duration;
        let handle = tokio::spawn(async move {
            match done {
                Some(rx) => {
                    let _ = rx.await;
                },
                None => {
                    let wait = if duration > 0.0 {
                        Duration::from_secs_f64(duration as f64)
                    } else {
                        AUDIO_STATE_FALLBACK
                    };
                    sleep(wait).await;
                },
            }
            if let Err(e) = s.send_float(AUDIO_PLAYING_ADDR, 0.0).await {
                warn!("Failed to reset AudioPlaying: {}", e);
            }
        });
        // A new clip supersedes the previous clip's reset timer.
        replace_task(&mut lock(&self.tasks).audio_state, handle);

        Ok(outcome)
    }

    async fn receive_state(&self) -> BackendResult<Option<EnvironmentState>> {
        let shared = self.shared()?;
        let world = lock(&shared.world_name).clone();
        Ok(Some(EnvironmentState {
            world_name: world,
            ..Default::default()
        }))
    }

    async fn reset_all(&mut self) -> BackendResult<()> {
        let shared = self.shared()?;
        info!("Resetting all VRChat states");
        {
            let mut tasks = lock(&self.tasks);
            for h in [
                tasks.movement.take(),
                tasks.emote_timeout.take(),
                tasks.audio_state.take(),
            ]
            .into_iter()
            .flatten()
            {
                h.abort();
            }
        }
        shared.clear_emote().await?;
        for addr in [
            "/input/Vertical",
            "/input/Horizontal",
            "/input/LookHorizontal",
            "/input/LookVertical",
        ] {
            shared.send_float(addr, 0.0).await?;
        }
        for addr in ["/input/Run", "/input/Jump", "/input/Crouch"] {
            shared.send_int(addr, 0).await?;
        }
        shared.send_float(AUDIO_PLAYING_ADDR, 0.0).await?;
        *lock(&shared.current_emotion) = EmotionType::Neutral;
        *lock(&shared.current_gesture) = GestureType::None;
        Ok(())
    }

    async fn execute_behavior(
        &mut self,
        behavior: &str,
        _parameters: HashMap<String, Value>,
    ) -> BackendResult<()> {
        let shared = self.shared()?;
        info!("Executing behavior: {}", behavior);
        match behavior {
            "greet" => {
                let anim = CanonicalAnimationData::new(0.0)
                    .with_gesture(GestureType::Wave, 1.0)
                    .with_emotion(EmotionType::Happy, 1.0);
                self.send_animation_data(anim).await?;
            },
            "dance" => {
                self.send_animation_data(
                    CanonicalAnimationData::new(0.0).with_gesture(GestureType::Dance, 1.0),
                )
                .await?;
            },
            "sit" => shared.send_int("/avatar/parameters/Sitting", 1).await?,
            "stand" => {
                shared.send_int("/avatar/parameters/Sitting", 0).await?;
                shared.send_int("/avatar/parameters/Crouching", 0).await?;
                shared.send_int("/input/Crouch", 0).await?;
            },
            "jump" => {
                shared.send_int("/input/Jump", 1).await?;
                sleep(Duration::from_millis(100)).await;
                shared.send_int("/input/Jump", 0).await?;
            },
            "crouch" => shared.send_int("/avatar/parameters/Crouching", 1).await?,
            other => {
                return Err(BackendError::InvalidParameter(format!(
                    "unknown behavior '{other}'"
                )))
            },
        }
        Ok(())
    }

    async fn send_vrcemote(&mut self, value: i32) -> BackendResult<EmoteAction> {
        let shared = self.shared()?;
        if !(VRCEmoteValue::MIN..=VRCEmoteValue::MAX).contains(&value) {
            return Err(BackendError::InvalidParameter(format!(
                "VRCEmote must be {}-{}, got {value}",
                VRCEmoteValue::MIN,
                VRCEmoteValue::MAX
            )));
        }
        self.apply_emote(&shared, value).await
    }

    async fn avatar_parameters(&self) -> BackendResult<HashMap<String, Value>> {
        let shared = self.shared()?;
        let params = lock(&shared.avatar_params).clone();
        Ok(params)
    }

    async fn get_statistics(&self) -> BackendResult<HashMap<String, Value>> {
        let mut stats = HashMap::new();
        stats.insert("backend".into(), json!(self.backend_name()));
        stats.insert("connected".into(), json!(self.is_connected()));
        let Some(shared) = &self.shared else {
            return Ok(stats);
        };
        let (current, active) = {
            let st = shared.emote.lock().await;
            (st.current, st.active)
        };
        let last = shared.last_received_ago();
        stats.insert("remote_host".into(), json!(shared.config.remote_host));
        stats.insert("target".into(), json!(shared.target.to_string()));
        stats.insert("osc_out_port".into(), json!(shared.config.osc_out_port));
        stats.insert(
            "receiver".into(),
            json!(lock(&shared.receiver_status).clone()),
        );
        stats.insert(
            "last_osc_received_secs_ago".into(),
            json!(last.map(|d| (d.as_secs_f64() * 10.0).round() / 10.0)),
        );
        stats.insert(
            "vrchat_responding".into(),
            json!(last.is_some_and(|d| d < RESPONDING_WINDOW)),
        );
        stats.insert(
            "osc_messages_sent".into(),
            json!(shared.osc_sent.load(Ordering::Relaxed)),
        );
        stats.insert(
            "osc_messages_received".into(),
            json!(shared.osc_received.load(Ordering::Relaxed)),
        );
        stats.insert(
            "animation_frames".into(),
            json!(shared.animation_frames.load(Ordering::Relaxed)),
        );
        stats.insert(
            "audio_clips".into(),
            json!(shared.audio_clips.load(Ordering::Relaxed)),
        );
        stats.insert(
            "errors".into(),
            json!(shared.errors.load(Ordering::Relaxed)),
        );
        stats.insert(
            "avatar_params_count".into(),
            json!(lock(&shared.avatar_params).len()),
        );
        stats.insert("avatar_id".into(), json!(lock(&shared.avatar_id).clone()));
        stats.insert(
            "current_emotion".into(),
            json!(lock(&shared.current_emotion).as_str()),
        );
        stats.insert(
            "current_gesture".into(),
            json!(lock(&shared.current_gesture).as_str()),
        );
        stats.insert("current_vrcemote".into(), json!(current));
        stats.insert("emote_active".into(), json!(active));
        stats.insert("emote_name".into(), json!(get_vrcemote_name(current)));
        stats.insert("use_vrcemote".into(), json!(shared.config.use_vrcemote));
        stats.insert("emote_timeout".into(), json!(shared.config.emote_timeout));
        stats.insert("audio_playback".into(), json!(shared.audio_mode.as_str()));
        stats.insert("audio_device".into(), json!(shared.config.audio_device));
        stats.insert(
            "chatbox_transcripts".into(),
            json!(shared.config.chatbox_transcripts),
        );
        Ok(stats)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A fake VRChat: a UDP socket that records received OSC messages.
    struct FakeVrchat {
        socket: UdpSocket,
    }

    impl FakeVrchat {
        async fn new() -> Self {
            Self {
                socket: UdpSocket::bind("127.0.0.1:0").await.unwrap(),
            }
        }

        fn port(&self) -> u16 {
            self.socket.local_addr().unwrap().port()
        }

        /// Receive messages until `quiet` elapses without traffic.
        async fn drain(&self, quiet: Duration) -> Vec<(String, Vec<OscType>)> {
            let mut out = Vec::new();
            let mut buf = vec![0u8; 65_536];
            while let Ok(Ok((n, _))) =
                tokio::time::timeout(quiet, self.socket.recv_from(&mut buf)).await
            {
                if let Ok((_, OscPacket::Message(m))) = rosc::decoder::decode_udp(&buf[..n]) {
                    out.push((m.addr, m.args));
                }
            }
            out
        }
    }

    fn free_port() -> u16 {
        std::net::UdpSocket::bind("127.0.0.1:0")
            .unwrap()
            .local_addr()
            .unwrap()
            .port()
    }

    async fn connected(fake: &FakeVrchat, extra: Value) -> VRChatRemoteBackend {
        let mut cfg = json!({
            "remote_host": "127.0.0.1",
            "osc_in_port": fake.port(),
            "osc_out_port": free_port(),
            "audio_playback": "none",
            "emote_timeout": 0,
        });
        if let (Some(base), Some(extra)) = (cfg.as_object_mut(), extra.as_object()) {
            base.extend(extra.clone());
        }
        let mut b = VRChatRemoteBackend::new();
        b.connect(serde_json::from_value(cfg).unwrap())
            .await
            .unwrap();
        b
    }

    fn emote_values(msgs: &[(String, Vec<OscType>)]) -> Vec<i32> {
        msgs.iter()
            .filter(|(a, _)| a == VRCEMOTE_ADDR)
            .filter_map(|(_, args)| match args.first() {
                Some(OscType::Int(i)) => Some(*i),
                _ => None,
            })
            .collect()
    }

    const QUIET: Duration = Duration::from_millis(150);

    #[tokio::test]
    async fn test_vrchat_backend_creation() {
        let backend = VRChatRemoteBackend::new();
        assert!(!backend.is_connected());
        assert_eq!(backend.backend_name(), "vrchat_remote");
        assert!(backend.capabilities().animation);
        assert!(backend.capabilities().audio);
    }

    #[tokio::test]
    async fn test_not_connected_errors() {
        let mut b = VRChatRemoteBackend::new();
        assert!(matches!(
            b.send_animation_data(CanonicalAnimationData::new(0.0))
                .await,
            Err(BackendError::NotConnected)
        ));
        assert!(matches!(
            b.reset_all().await,
            Err(BackendError::NotConnected)
        ));
        assert!(b.disconnect().await.is_ok());
    }

    #[test]
    fn test_config_merge_and_validation() {
        let base = VRChatConfig::default();
        let map = |v: Value| -> HashMap<String, Value> { serde_json::from_value(v).unwrap() };

        let c = base
            .clone()
            .merged_with(&map(
                json!({"remote_host": "10.0.0.5", "vrchat_recv_port": 9100, "use_vrcemote": false}),
            ))
            .unwrap();
        assert_eq!(c.remote_host, "10.0.0.5");
        assert_eq!(c.osc_in_port, 9100);
        assert!(!c.use_vrcemote);

        assert!(base
            .clone()
            .merged_with(&map(json!({"osc_in_port": 70000})))
            .is_err());
        assert!(base
            .clone()
            .merged_with(&map(json!({"osc_out_port": 0})))
            .is_err());
        assert!(base
            .clone()
            .merged_with(&map(json!({"osc_in_port": "9000"})))
            .is_err());
        assert!(base
            .clone()
            .merged_with(&map(json!({"audio_playback": "loud"})))
            .is_err());
        assert!(base
            .clone()
            .merged_with(&map(json!({"remote_host": "a b"})))
            .is_err());
        assert!(base
            .merged_with(&map(json!({"emote_timeout": -1})))
            .is_err());
    }

    #[test]
    fn test_config_from_env() {
        let env: HashMap<&str, &str> = [
            ("VIRTUAL_CHARACTER_HOST", "192.168.0.10"),
            ("VIRTUAL_CHARACTER_OSC_IN", "9010"),
            ("VIRTUAL_CHARACTER_OSC_OUT", "not-a-port"),
            ("VIRTUAL_CHARACTER_EMOTE_TIMEOUT", "3"),
            ("VIRTUAL_CHARACTER_AUDIO_PLAYBACK", "local"),
            ("VIRTUAL_CHARACTER_USE_VRCEMOTE", "false"),
        ]
        .into_iter()
        .collect();
        let c = VRChatConfig::from_env_with(|k| env.get(k).map(|v| v.to_string()));
        assert_eq!(c.remote_host, "192.168.0.10");
        assert_eq!(c.osc_in_port, 9010);
        assert_eq!(c.osc_out_port, DEFAULT_OSC_OUT_PORT); // invalid ignored
        assert_eq!(c.emote_timeout, 3.0);
        assert_eq!(c.audio_playback, AudioPlaybackMode::Local);
        assert!(!c.use_vrcemote);
    }

    #[test]
    fn test_effective_audio_mode() {
        let c = VRChatConfig::default();
        let local: SocketAddr = "127.0.0.1:9000".parse().unwrap();
        let remote: SocketAddr = "192.168.1.5:9000".parse().unwrap();
        assert_eq!(c.effective_audio_mode(&local), AudioPlaybackMode::Local);
        assert_eq!(c.effective_audio_mode(&remote), AudioPlaybackMode::None);
        let forced = VRChatConfig {
            audio_playback: AudioPlaybackMode::None,
            ..VRChatConfig::default()
        };
        assert_eq!(forced.effective_audio_mode(&local), AudioPlaybackMode::None);
    }

    #[tokio::test]
    async fn test_emote_toggle_state_machine() {
        let fake = FakeVrchat::new().await;
        let mut b = connected(&fake, json!({})).await;

        assert_eq!(b.send_vrcemote(4).await.unwrap(), EmoteAction::Activated);
        assert_eq!(emote_values(&fake.drain(QUIET).await), vec![4]);

        // Switching emotes toggles the old one off first.
        assert_eq!(b.send_vrcemote(5).await.unwrap(), EmoteAction::Activated);
        assert_eq!(emote_values(&fake.drain(QUIET).await), vec![4, 0, 5]);

        // Same emote again toggles it off.
        assert_eq!(b.send_vrcemote(5).await.unwrap(), EmoteAction::ToggledOff);
        assert_eq!(emote_values(&fake.drain(QUIET).await), vec![5, 0]);

        assert_eq!(b.send_vrcemote(0).await.unwrap(), EmoteAction::Unchanged);
        assert!(b.send_vrcemote(9).await.is_err());
        b.disconnect().await.unwrap();
    }

    #[tokio::test]
    async fn test_gesture_takes_priority_over_emotion() {
        let fake = FakeVrchat::new().await;
        let mut b = connected(&fake, json!({})).await;
        let anim = CanonicalAnimationData::new(0.0)
            .with_emotion(EmotionType::Happy, 1.0)
            .with_gesture(GestureType::Wave, 1.0);
        b.send_animation_data(anim).await.unwrap();
        // Only the wave (1) is sent; happy (cheer=4) would have cancelled it.
        assert_eq!(emote_values(&fake.drain(QUIET).await), vec![1]);

        // Neutral clears.
        b.send_animation_data(
            CanonicalAnimationData::new(0.0).with_emotion(EmotionType::Neutral, 1.0),
        )
        .await
        .unwrap();
        assert_eq!(emote_values(&fake.drain(QUIET).await), vec![1, 0]);
    }

    #[tokio::test]
    async fn test_emote_auto_clear_updates_real_state() {
        let fake = FakeVrchat::new().await;
        let mut b = connected(&fake, json!({"emote_timeout": 0.2})).await;
        b.send_vrcemote(3).await.unwrap();
        tokio::time::sleep(Duration::from_millis(400)).await;
        assert_eq!(emote_values(&fake.drain(QUIET).await), vec![3, 3, 0]);
        let stats = b.get_statistics().await.unwrap();
        assert_eq!(stats["emote_active"], json!(false));
        // Sending the same emote again activates it (state was really cleared).
        assert_eq!(b.send_vrcemote(3).await.unwrap(), EmoteAction::Activated);
    }

    #[tokio::test]
    async fn test_movement_clears_emote_and_auto_stops() {
        let fake = FakeVrchat::new().await;
        let mut b = connected(&fake, json!({})).await;
        b.send_vrcemote(6).await.unwrap();
        fake.drain(QUIET).await;

        let mut params = HashMap::new();
        params.insert("move_forward".to_string(), json!(0.5));
        params.insert("look_horizontal".to_string(), json!(0.2));
        params.insert("duration".to_string(), json!(0.2));
        b.send_animation_data(CanonicalAnimationData::new(0.0).with_parameters(params))
            .await
            .unwrap();
        tokio::time::sleep(Duration::from_millis(350)).await;
        let msgs = fake.drain(QUIET).await;
        assert_eq!(emote_values(&msgs), vec![6, 0]);
        let vertical: Vec<_> = msgs
            .iter()
            .filter(|(a, _)| a == "/input/Vertical")
            .map(|(_, args)| args[0].clone())
            .collect();
        assert_eq!(vertical, vec![OscType::Float(0.5), OscType::Float(0.0)]);
        assert!(msgs
            .iter()
            .any(|(a, args)| a == "/input/LookHorizontal" && args[0] == OscType::Float(0.0)));
    }

    #[tokio::test]
    async fn test_avatar_params_only_do_not_touch_emote() {
        let fake = FakeVrchat::new().await;
        let mut b = connected(&fake, json!({})).await;
        b.send_vrcemote(2).await.unwrap();
        fake.drain(QUIET).await;

        let mut params = HashMap::new();
        params.insert(
            "avatar_params".to_string(),
            json!({"Blush": 0.5, "Hat": true}),
        );
        b.send_animation_data(CanonicalAnimationData::new(0.0).with_parameters(params))
            .await
            .unwrap();
        let msgs = fake.drain(QUIET).await;
        assert!(
            emote_values(&msgs).is_empty(),
            "emote was cleared: {msgs:?}"
        );
        assert!(msgs
            .iter()
            .any(|(a, args)| a == "/avatar/parameters/Hat" && args[0] == OscType::Bool(true)));
    }

    #[tokio::test]
    async fn test_invalid_parameters_send_nothing() {
        let fake = FakeVrchat::new().await;
        let mut b = connected(&fake, json!({})).await;
        let mut params = HashMap::new();
        params.insert("move_forward".to_string(), json!("fast"));
        let err = b
            .send_animation_data(
                CanonicalAnimationData::new(0.0)
                    .with_gesture(GestureType::Wave, 1.0)
                    .with_parameters(params),
            )
            .await;
        assert!(matches!(err, Err(BackendError::InvalidParameter(_))));
        assert!(fake.drain(QUIET).await.is_empty());
    }

    #[tokio::test]
    async fn test_audio_without_playback_reports_honestly() {
        let fake = FakeVrchat::new().await;
        let mut b = connected(&fake, json!({"chatbox_transcripts": true})).await;
        let audio = AudioData {
            data: vec![0u8; 2000],
            format: "wav".into(),
            duration: 0.2,
            text: Some("Hello there! [laughs] Great to see you.".into()),
            ..Default::default()
        };
        let outcome = b.send_audio_data(audio).await.unwrap();
        assert!(!outcome.played);
        assert_eq!(outcome.emotion.as_deref(), Some("happy"));
        assert!(!outcome.notes.is_empty());
        tokio::time::sleep(Duration::from_millis(300)).await;
        let msgs = fake.drain(QUIET).await;
        assert_eq!(emote_values(&msgs), vec![4]);
        let chat = msgs.iter().find(|(a, _)| a == CHATBOX_ADDR).unwrap();
        assert_eq!(
            chat.1[0],
            OscType::String("Hello there! Great to see you.".into())
        );
        let playing: Vec<_> = msgs
            .iter()
            .filter(|(a, _)| a == AUDIO_PLAYING_ADDR)
            .map(|(_, args)| args[0].clone())
            .collect();
        assert_eq!(playing, vec![OscType::Float(1.0), OscType::Float(0.0)]);
    }

    #[tokio::test]
    async fn test_receiver_tracks_params_and_reconnect_rebinds_port() {
        let fake = FakeVrchat::new().await;
        let listen_port = free_port();
        let mut b = connected(&fake, json!({"osc_out_port": listen_port})).await;
        let stats = b.get_statistics().await.unwrap();
        assert!(stats["receiver"].as_str().unwrap().starts_with("listening"));
        assert_eq!(stats["vrchat_responding"], json!(false));

        // VRChat -> us: a parameter update.
        let msg = encoder::encode(&OscPacket::Message(OscMessage {
            addr: "/avatar/parameters/VRCEmote".into(),
            args: vec![OscType::Int(3)],
        }))
        .unwrap();
        fake.socket
            .send_to(&msg, ("127.0.0.1", listen_port))
            .await
            .unwrap();
        tokio::time::sleep(Duration::from_millis(100)).await;
        let params = b.avatar_parameters().await.unwrap();
        assert_eq!(params.get("VRCEmote"), Some(&json!(3)));
        let stats = b.get_statistics().await.unwrap();
        assert_eq!(stats["vrchat_responding"], json!(true));

        // Reconnect on the same listen port must succeed (old listener released).
        let cfg: HashMap<String, Value> = serde_json::from_value(json!({
            "remote_host": "127.0.0.1",
            "osc_in_port": fake.port(),
            "osc_out_port": listen_port,
            "audio_playback": "none",
        }))
        .unwrap();
        b.connect(cfg).await.unwrap();
        let stats = b.get_statistics().await.unwrap();
        assert!(
            stats["receiver"].as_str().unwrap().starts_with("listening"),
            "{stats:?}"
        );
        b.disconnect().await.unwrap();
        assert!(!b.is_connected());
    }

    #[tokio::test]
    async fn test_unknown_behavior_rejected() {
        let fake = FakeVrchat::new().await;
        let mut b = connected(&fake, json!({})).await;
        assert!(b
            .execute_behavior("moonwalk", HashMap::new())
            .await
            .is_err());
        b.execute_behavior("jump", HashMap::new()).await.unwrap();
        let msgs = fake.drain(QUIET).await;
        let jumps: Vec<_> = msgs
            .iter()
            .filter(|(a, _)| a == "/input/Jump")
            .map(|(_, args)| args[0].clone())
            .collect();
        assert_eq!(jumps, vec![OscType::Int(1), OscType::Int(0)]);
    }
}
