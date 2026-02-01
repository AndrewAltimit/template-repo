//! VRChat Remote Backend Adapter.
//!
//! Controls VRChat avatars on a remote Windows machine using OSC protocol.

use async_trait::async_trait;
use rosc::{encoder, OscMessage, OscPacket, OscType};
use serde_json::Value;
use std::collections::HashMap;
use std::net::UdpSocket;
use std::sync::atomic::{AtomicBool, AtomicI32, AtomicU64, Ordering};
use std::sync::Arc;
use tokio::sync::RwLock;
use tokio::time::{sleep, Duration};
use tracing::{debug, info, warn};

use crate::constants::{
    emotion_to_vrcemote, gesture_to_vrcemote, get_vrcemote_name, DEFAULT_EMOTE_TIMEOUT,
    DEFAULT_MOVEMENT_DURATION, DEFAULT_OSC_IN_PORT, DEFAULT_OSC_OUT_PORT, DEFAULT_VRCHAT_HOST,
};
use crate::types::{
    AudioData, BackendCapabilities, CanonicalAnimationData, EmotionType, EnvironmentState,
    GestureType, VideoFrame,
};

use super::adapter::{BackendAdapter, BackendError, BackendResult};

/// VRChat Remote Backend for controlling avatars via OSC.
pub struct VRChatRemoteBackend {
    connected: AtomicBool,
    capabilities: BackendCapabilities,
    config: Arc<RwLock<HashMap<String, Value>>>,

    // OSC client
    osc_socket: Arc<RwLock<Option<UdpSocket>>>,
    remote_host: Arc<RwLock<String>>,
    osc_in_port: Arc<RwLock<u16>>,

    // OSC receiver state
    osc_receiver_cancel: Arc<RwLock<Option<tokio::sync::oneshot::Sender<()>>>>,
    avatar_params: Arc<RwLock<HashMap<String, Value>>>,
    world_name: Arc<RwLock<Option<String>>>,

    // Avatar state tracking
    current_emotion: Arc<RwLock<EmotionType>>,
    current_gesture: Arc<RwLock<GestureType>>,
    use_vrcemote: AtomicBool,
    current_vrcemote: AtomicI32,
    emote_is_active: AtomicBool,

    // Movement state
    movement_active: AtomicBool,
    vertical_movement: Arc<RwLock<f32>>,
    horizontal_movement: Arc<RwLock<f32>>,

    // Task handles for cancellation
    movement_cancel: Arc<RwLock<Option<tokio::sync::oneshot::Sender<()>>>>,
    emote_cancel: Arc<RwLock<Option<tokio::sync::oneshot::Sender<()>>>>,

    // Statistics
    osc_messages_sent: AtomicU64,
    osc_messages_received: AtomicU64,
    animation_frames: AtomicU64,
    errors: AtomicU64,
}

impl Default for VRChatRemoteBackend {
    fn default() -> Self {
        Self::new()
    }
}

impl VRChatRemoteBackend {
    /// Create a new VRChat remote backend.
    pub fn new() -> Self {
        let capabilities = BackendCapabilities {
            animation: true,
            audio: true,
            bidirectional: true,
            streaming: true,
            ..Default::default()
        };

        Self {
            connected: AtomicBool::new(false),
            capabilities,
            config: Arc::new(RwLock::new(HashMap::new())),
            osc_socket: Arc::new(RwLock::new(None)),
            remote_host: Arc::new(RwLock::new(DEFAULT_VRCHAT_HOST.to_string())),
            osc_in_port: Arc::new(RwLock::new(DEFAULT_OSC_IN_PORT)),
            osc_receiver_cancel: Arc::new(RwLock::new(None)),
            avatar_params: Arc::new(RwLock::new(HashMap::new())),
            world_name: Arc::new(RwLock::new(None)),
            current_emotion: Arc::new(RwLock::new(EmotionType::Neutral)),
            current_gesture: Arc::new(RwLock::new(GestureType::None)),
            use_vrcemote: AtomicBool::new(true),
            current_vrcemote: AtomicI32::new(0),
            emote_is_active: AtomicBool::new(false),
            movement_active: AtomicBool::new(false),
            vertical_movement: Arc::new(RwLock::new(0.0)),
            horizontal_movement: Arc::new(RwLock::new(0.0)),
            movement_cancel: Arc::new(RwLock::new(None)),
            emote_cancel: Arc::new(RwLock::new(None)),
            osc_messages_sent: AtomicU64::new(0),
            osc_messages_received: AtomicU64::new(0),
            animation_frames: AtomicU64::new(0),
            errors: AtomicU64::new(0),
        }
    }

    /// Start the OSC receiver task to listen for incoming messages from VRChat.
    async fn start_osc_receiver(&self, osc_out_port: u16) -> BackendResult<()> {
        // Cancel existing receiver if any
        if let Some(cancel) = self.osc_receiver_cancel.write().await.take() {
            let _ = cancel.send(());
        }

        // Create UDP socket for receiving
        let receiver_socket = UdpSocket::bind(format!("0.0.0.0:{}", osc_out_port)).map_err(|e| {
            BackendError::NetworkError(format!(
                "Failed to bind OSC receiver to port {}: {}",
                osc_out_port, e
            ))
        })?;

        receiver_socket.set_nonblocking(true).map_err(|e| {
            BackendError::NetworkError(format!("Failed to set non-blocking: {}", e))
        })?;

        let (tx, rx) = tokio::sync::oneshot::channel();
        *self.osc_receiver_cancel.write().await = Some(tx);

        let avatar_params = self.avatar_params.clone();
        let world_name = self.world_name.clone();
        let use_vrcemote = Arc::new(AtomicBool::new(self.use_vrcemote.load(Ordering::SeqCst)));
        let osc_messages_received = Arc::new(AtomicU64::new(0));

        // Spawn receiver task
        tokio::spawn(async move {
            let mut buf = [0u8; 1024];

            tokio::select! {
                _ = async {
                    loop {
                        // Non-blocking receive with small delay
                        match receiver_socket.recv_from(&mut buf) {
                            Ok((size, _addr)) => {
                                if let Ok((_, packet)) = rosc::decoder::decode_udp(&buf[..size]) {
                                    Self::handle_osc_packet(
                                        packet,
                                        &avatar_params,
                                        &world_name,
                                        &use_vrcemote,
                                        &osc_messages_received,
                                    ).await;
                                }
                            }
                            Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                                // No data available, sleep briefly
                                sleep(Duration::from_millis(10)).await;
                            }
                            Err(e) => {
                                warn!("OSC receiver error: {}", e);
                                sleep(Duration::from_millis(100)).await;
                            }
                        }
                    }
                } => {}
                _ = rx => {
                    info!("OSC receiver stopped");
                }
            }
        });

        info!("OSC receiver listening on port {}", osc_out_port);
        Ok(())
    }

    /// Handle incoming OSC packet.
    async fn handle_osc_packet(
        packet: OscPacket,
        avatar_params: &Arc<RwLock<HashMap<String, Value>>>,
        world_name: &Arc<RwLock<Option<String>>>,
        use_vrcemote: &AtomicBool,
        osc_messages_received: &AtomicU64,
    ) {
        match packet {
            OscPacket::Message(msg) => {
                Self::handle_osc_message(msg, avatar_params, world_name, use_vrcemote, osc_messages_received).await;
            }
            OscPacket::Bundle(bundle) => {
                for p in bundle.content {
                    Box::pin(Self::handle_osc_packet(p, avatar_params, world_name, use_vrcemote, osc_messages_received)).await;
                }
            }
        }
    }

    /// Handle a single OSC message.
    async fn handle_osc_message(
        msg: OscMessage,
        avatar_params: &Arc<RwLock<HashMap<String, Value>>>,
        world_name: &Arc<RwLock<Option<String>>>,
        use_vrcemote: &AtomicBool,
        osc_messages_received: &AtomicU64,
    ) {
        osc_messages_received.fetch_add(1, Ordering::SeqCst);

        // Handle avatar parameter updates
        if msg.addr.starts_with("/avatar/parameters/") {
            let param_name = msg.addr.replace("/avatar/parameters/", "");

            if let Some(arg) = msg.args.first() {
                let value = match arg {
                    OscType::Float(f) => Value::Number(serde_json::Number::from_f64(*f as f64).unwrap_or(0.into())),
                    OscType::Int(i) => Value::Number((*i).into()),
                    OscType::Bool(b) => Value::Bool(*b),
                    OscType::String(s) => Value::String(s.clone()),
                    _ => return,
                };

                avatar_params.write().await.insert(param_name.clone(), value);

                // Auto-detect VRCEmote system
                if param_name == "VRCEmote" && !use_vrcemote.load(Ordering::SeqCst) {
                    info!("VRCEmote detected! Switching to VRCEmote emotion system.");
                    use_vrcemote.store(true, Ordering::SeqCst);
                }

                debug!("Received avatar param: {} = {:?}", param_name, arg);
            }
        }
        // Handle world info
        else if msg.addr.starts_with("/world/") {
            if let Some(OscType::String(name)) = msg.args.first() {
                *world_name.write().await = Some(name.clone());
                debug!("Received world name: {}", name);
            }
        }
    }

    /// Send an OSC message.
    async fn send_osc(&self, address: &str, value: OscType) -> BackendResult<()> {
        let socket_guard = self.osc_socket.read().await;
        let socket = socket_guard.as_ref().ok_or(BackendError::NotConnected)?;

        let remote_host = self.remote_host.read().await;
        let port = *self.osc_in_port.read().await;
        let addr = format!("{}:{}", remote_host, port);

        let msg = OscMessage {
            addr: address.to_string(),
            args: vec![value.clone()],
        };

        let packet = OscPacket::Message(msg);
        let encoded = encoder::encode(&packet)
            .map_err(|e| BackendError::OscError(format!("Failed to encode OSC: {}", e)))?;

        socket
            .send_to(&encoded, &addr)
            .map_err(|e| BackendError::NetworkError(format!("Failed to send OSC: {}", e)))?;

        self.osc_messages_sent.fetch_add(1, Ordering::SeqCst);

        // Log VRCEmote changes
        if address.contains("VRCEmote") {
            info!("OSC: Sent {} = {:?}", address, value);
        } else {
            debug!("OSC: Sent {} = {:?}", address, value);
        }

        Ok(())
    }

    /// Send OSC float value.
    async fn send_osc_float(&self, address: &str, value: f32) -> BackendResult<()> {
        self.send_osc(address, OscType::Float(value)).await
    }

    /// Send OSC int value.
    async fn send_osc_int(&self, address: &str, value: i32) -> BackendResult<()> {
        self.send_osc(address, OscType::Int(value)).await
    }

    /// Set avatar emotion with toggle behavior.
    async fn set_emotion(&self, emotion: EmotionType, _intensity: f32) -> BackendResult<()> {
        if self.use_vrcemote.load(Ordering::SeqCst) {
            let emotion_map = emotion_to_vrcemote();
            if let Some(&emote_value) = emotion_map.get(&emotion) {
                let current = self.current_vrcemote.load(Ordering::SeqCst);
                let is_active = self.emote_is_active.load(Ordering::SeqCst);

                // If trying to activate the same emote, toggle it off
                if is_active && current == emote_value && emote_value != 0 {
                    self.send_osc_int("/avatar/parameters/VRCEmote", emote_value)
                        .await?;
                    self.emote_is_active.store(false, Ordering::SeqCst);
                    self.current_vrcemote.store(0, Ordering::SeqCst);
                    info!("Toggled off VRCEmote {} by resending", emote_value);
                } else {
                    // Clear different active emote first if needed
                    if is_active && current != emote_value && emote_value != 0 {
                        self.send_osc_int("/avatar/parameters/VRCEmote", current)
                            .await?;
                        sleep(Duration::from_millis(100)).await;
                        info!("Toggled off previous emote {}", current);
                    }

                    // Set the new emote
                    self.send_osc_int("/avatar/parameters/VRCEmote", emote_value)
                        .await?;
                    self.current_vrcemote.store(emote_value, Ordering::SeqCst);
                    self.emote_is_active
                        .store(emote_value != 0, Ordering::SeqCst);

                    // Start timeout timer for emote
                    if emote_value != 0 {
                        self.start_emote_timeout(emote_value).await;
                    }

                    info!("Set VRCEmote to {} for {:?}", emote_value, emotion);
                }
            }
        }

        *self.current_emotion.write().await = emotion;
        Ok(())
    }

    /// Set avatar gesture with toggle behavior.
    async fn set_gesture(&self, gesture: GestureType, _intensity: f32) -> BackendResult<()> {
        if self.use_vrcemote.load(Ordering::SeqCst) {
            let gesture_map = gesture_to_vrcemote();
            if let Some(&emote_value) = gesture_map.get(&gesture) {
                let current = self.current_vrcemote.load(Ordering::SeqCst);
                let is_active = self.emote_is_active.load(Ordering::SeqCst);

                // If trying to activate the same gesture, toggle it off
                if is_active && current == emote_value && emote_value != 0 {
                    self.send_osc_int("/avatar/parameters/VRCEmote", emote_value)
                        .await?;
                    self.emote_is_active.store(false, Ordering::SeqCst);
                    self.current_vrcemote.store(0, Ordering::SeqCst);
                    info!("Toggled off VRCEmote {} by resending", emote_value);
                } else {
                    // Clear different active emote first if needed
                    if is_active && current != emote_value && current != 0 {
                        self.send_osc_int("/avatar/parameters/VRCEmote", current)
                            .await?;
                        sleep(Duration::from_millis(200)).await;
                        info!("Toggled off previous gesture {}", current);
                    }

                    // Set the new gesture
                    self.send_osc_int("/avatar/parameters/VRCEmote", emote_value)
                        .await?;
                    self.current_vrcemote.store(emote_value, Ordering::SeqCst);
                    self.emote_is_active
                        .store(emote_value != 0, Ordering::SeqCst);

                    // Start timeout timer for emote
                    if emote_value != 0 {
                        self.start_emote_timeout(emote_value).await;
                    }

                    info!(
                        "Set VRCEmote to {} for gesture {:?}, active={}",
                        emote_value,
                        gesture,
                        emote_value != 0
                    );
                }
            }
        }

        *self.current_gesture.write().await = gesture;
        Ok(())
    }

    /// Handle movement parameters with auto-stop.
    async fn handle_movement_params(
        &self,
        params: &HashMap<String, serde_json::Value>,
    ) -> BackendResult<()> {
        // Clear active emote if one is set
        if self.emote_is_active.load(Ordering::SeqCst) {
            let current = self.current_vrcemote.load(Ordering::SeqCst);
            if current != 0 {
                info!("Clearing active emote {} for movement", current);

                // Try multiple approaches to ensure emote clears
                self.send_osc_int("/avatar/parameters/VRCEmote", 0).await?;
                sleep(Duration::from_millis(100)).await;
                self.send_osc_int("/avatar/parameters/VRCEmote", current)
                    .await?;
                sleep(Duration::from_millis(100)).await;
                self.send_osc_int("/avatar/parameters/VRCEmote", 0).await?;

                self.emote_is_active.store(false, Ordering::SeqCst);
                self.current_vrcemote.store(0, Ordering::SeqCst);
            }
        }

        // Cancel emote timer if running
        if let Some(cancel) = self.emote_cancel.write().await.take() {
            let _ = cancel.send(());
        }

        // Cancel any existing movement timer
        if let Some(cancel) = self.movement_cancel.write().await.take() {
            let _ = cancel.send(());
        }

        // Movement axes
        let mut forward_value = 0.0f32;
        let mut right_value = 0.0f32;

        if let Some(Value::Number(n)) = params.get("move_forward") {
            forward_value = n.as_f64().unwrap_or(0.0) as f32;
            forward_value = forward_value.clamp(-1.0, 1.0);
            *self.vertical_movement.write().await = forward_value;
            self.send_osc_float("/input/Vertical", forward_value)
                .await?;
            info!("Sent movement Vertical: {}", forward_value);
        }

        if let Some(Value::Number(n)) = params.get("move_right") {
            right_value = n.as_f64().unwrap_or(0.0) as f32;
            right_value = right_value.clamp(-1.0, 1.0);
            *self.horizontal_movement.write().await = right_value;
            self.send_osc_float("/input/Horizontal", right_value)
                .await?;
            info!("Sent movement Horizontal: {}", right_value);
        }

        // Auto-stop movement after duration
        if forward_value != 0.0 || right_value != 0.0 {
            self.movement_active.store(true, Ordering::SeqCst);

            let duration = params
                .get("duration")
                .and_then(|v| v.as_f64())
                .unwrap_or(DEFAULT_MOVEMENT_DURATION as f64) as f32;

            self.start_movement_timeout(duration).await;
            info!("Movement will auto-stop in {} seconds", duration);
        } else {
            self.movement_active.store(false, Ordering::SeqCst);
        }

        // Looking/turning
        if let Some(Value::Number(n)) = params.get("look_horizontal") {
            let value = (n.as_f64().unwrap_or(0.0) as f32).clamp(-1.0, 1.0);
            self.send_osc_float("/input/LookHorizontal", value).await?;
            info!("Sent look horizontal: {}", value);
        }

        if let Some(Value::Number(n)) = params.get("look_vertical") {
            let value = (n.as_f64().unwrap_or(0.0) as f32).clamp(-1.0, 1.0);
            self.send_osc_float("/input/LookVertical", value).await?;
            info!("Sent look vertical: {}", value);
        }

        // Run modifier
        if let Some(Value::Bool(run)) = params.get("run") {
            let run_value = if *run { 1 } else { 0 };
            self.send_osc_int("/input/Run", run_value).await?;
            info!("Sent run: {}", run_value);
        }

        // Jump action
        if let Some(Value::Bool(true)) = params.get("jump") {
            self.send_osc_int("/input/Jump", 1).await?;
            info!("Sent jump: 1");
            sleep(Duration::from_millis(100)).await;
            self.send_osc_int("/input/Jump", 0).await?;
        }

        // Crouch
        if let Some(Value::Bool(crouch)) = params.get("crouch") {
            let crouch_value = if *crouch { 1 } else { 0 };
            self.send_osc_int("/input/Crouch", crouch_value).await?;
            info!("Sent crouch: {}", crouch_value);
        }

        Ok(())
    }

    /// Start movement auto-stop timer.
    async fn start_movement_timeout(&self, duration: f32) {
        let (tx, rx) = tokio::sync::oneshot::channel();
        *self.movement_cancel.write().await = Some(tx);

        let movement_active = Arc::new(AtomicBool::new(true));
        let movement_active_clone = movement_active.clone();
        let vertical = self.vertical_movement.clone();
        let horizontal = self.horizontal_movement.clone();
        let socket = self.osc_socket.clone();
        let remote_host = self.remote_host.clone();
        let osc_in_port = self.osc_in_port.clone();

        tokio::spawn(async move {
            tokio::select! {
                _ = sleep(Duration::from_secs_f32(duration)) => {
                    if movement_active_clone.load(Ordering::SeqCst) {
                        // Stop movement
                        if let Some(ref sock) = *socket.read().await {
                            let host = remote_host.read().await;
                            let port = *osc_in_port.read().await;
                            let addr = format!("{}:{}", host, port);

                            // Send stop commands
                            for (osc_addr, _) in [("/input/Vertical", 0.0f32), ("/input/Horizontal", 0.0f32)] {
                                let msg = OscMessage {
                                    addr: osc_addr.to_string(),
                                    args: vec![OscType::Float(0.0)],
                                };
                                let packet = OscPacket::Message(msg);
                                if let Ok(encoded) = encoder::encode(&packet) {
                                    let _ = sock.send_to(&encoded, &addr);
                                }
                            }
                        }

                        *vertical.write().await = 0.0;
                        *horizontal.write().await = 0.0;
                        info!("Auto-stopped movement after timeout");
                    }
                }
                _ = rx => {
                    // Cancelled
                }
            }
        });

        self.movement_active.store(true, Ordering::SeqCst);
    }

    /// Start emote auto-clear timer.
    async fn start_emote_timeout(&self, emote_value: i32) {
        // Cancel existing timer
        if let Some(cancel) = self.emote_cancel.write().await.take() {
            let _ = cancel.send(());
        }

        let (tx, rx) = tokio::sync::oneshot::channel();
        *self.emote_cancel.write().await = Some(tx);

        let socket = self.osc_socket.clone();
        let remote_host = self.remote_host.clone();
        let osc_in_port = self.osc_in_port.clone();
        let emote_is_active = Arc::new(AtomicBool::new(true));
        let current_vrcemote = Arc::new(AtomicI32::new(emote_value));

        tokio::spawn(async move {
            tokio::select! {
                _ = sleep(Duration::from_secs(DEFAULT_EMOTE_TIMEOUT)) => {
                    info!("Emote {} timed out, force clearing", emote_value);

                    if let Some(ref sock) = *socket.read().await {
                        let host = remote_host.read().await;
                        let port = *osc_in_port.read().await;
                        let addr = format!("{}:{}", host, port);

                        // Toggle off by sending the same value
                        let msg = OscMessage {
                            addr: "/avatar/parameters/VRCEmote".to_string(),
                            args: vec![OscType::Int(emote_value)],
                        };
                        let packet = OscPacket::Message(msg);
                        if let Ok(encoded) = encoder::encode(&packet) {
                            let _ = sock.send_to(&encoded, &addr);
                        }
                    }

                    emote_is_active.store(false, Ordering::SeqCst);
                    current_vrcemote.store(0, Ordering::SeqCst);
                }
                _ = rx => {
                    // Cancelled
                }
            }
        });

        info!(
            "Started {}-second timeout for emote {}",
            DEFAULT_EMOTE_TIMEOUT, emote_value
        );
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
        info!("VRChat remote backend connecting with config: {:?}", config);

        // Parse configuration
        let remote_host = config
            .get("remote_host")
            .and_then(|v| v.as_str())
            .unwrap_or(DEFAULT_VRCHAT_HOST)
            .to_string();

        let osc_in_port = config
            .get("osc_in_port")
            .and_then(|v| v.as_u64())
            .unwrap_or(DEFAULT_OSC_IN_PORT as u64) as u16;

        let osc_out_port = config
            .get("osc_out_port")
            .and_then(|v| v.as_u64())
            .unwrap_or(DEFAULT_OSC_OUT_PORT as u64) as u16;

        if let Some(use_vrcemote) = config.get("use_vrcemote").and_then(|v| v.as_bool()) {
            self.use_vrcemote.store(use_vrcemote, Ordering::SeqCst);
            info!(
                "Using {} emotion system (configured)",
                if use_vrcemote {
                    "VRCEmote"
                } else {
                    "traditional"
                }
            );
        }

        // Create UDP socket for OSC
        let socket = UdpSocket::bind("0.0.0.0:0")
            .map_err(|e| BackendError::NetworkError(format!("Failed to bind socket: {}", e)))?;

        socket.set_nonblocking(true).map_err(|e| {
            BackendError::NetworkError(format!("Failed to set non-blocking: {}", e))
        })?;

        // Store configuration
        *self.osc_socket.write().await = Some(socket);
        *self.remote_host.write().await = remote_host.clone();
        *self.osc_in_port.write().await = osc_in_port;
        *self.config.write().await = config;

        // Test connection with a simple parameter update
        self.send_osc_float("/avatar/parameters/TestConnection", 1.0)
            .await?;

        // Start OSC receiver for incoming messages from VRChat
        match self.start_osc_receiver(osc_out_port).await {
            Ok(()) => info!("OSC receiver started on port {}", osc_out_port),
            Err(e) => {
                warn!("Could not start OSC receiver: {} - continuing in send-only mode", e);
            }
        }

        self.connected.store(true, Ordering::SeqCst);
        info!("Connected to VRChat at {}:{}", remote_host, osc_in_port);

        Ok(())
    }

    async fn disconnect(&mut self) -> BackendResult<()> {
        info!("VRChat remote backend disconnecting");

        // Cancel OSC receiver
        if let Some(cancel) = self.osc_receiver_cancel.write().await.take() {
            let _ = cancel.send(());
        }

        // Cancel timers
        if let Some(cancel) = self.movement_cancel.write().await.take() {
            let _ = cancel.send(());
        }
        if let Some(cancel) = self.emote_cancel.write().await.take() {
            let _ = cancel.send(());
        }

        *self.osc_socket.write().await = None;
        self.connected.store(false, Ordering::SeqCst);

        info!("Disconnected from VRChat");
        Ok(())
    }

    async fn send_animation_data(&mut self, data: CanonicalAnimationData) -> BackendResult<()> {
        if !self.is_connected() {
            return Err(BackendError::NotConnected);
        }

        // Update emotion if changed
        let current_emotion = *self.current_emotion.read().await;
        if let Some(emotion) = data.emotion {
            if emotion != current_emotion {
                self.set_emotion(emotion, data.emotion_intensity).await?;
            }
        }

        // Update gesture if changed
        let current_gesture = *self.current_gesture.read().await;
        if let Some(gesture) = data.gesture {
            if gesture != current_gesture {
                self.set_gesture(gesture, data.gesture_intensity).await?;
            }
        }

        // Update blend shapes
        for (shape, value) in &data.blend_shapes {
            let param_name = format!("/avatar/parameters/BlendShape_{}", shape);
            self.send_osc_float(&param_name, *value).await?;
        }

        // Handle movement parameters
        if !data.parameters.is_empty() {
            self.handle_movement_params(&data.parameters).await?;
        }

        // Update custom avatar parameters
        if let Some(Value::Object(avatar_params)) = data.parameters.get("avatar_params") {
            for (param, value) in avatar_params {
                let addr = format!("/avatar/parameters/{}", param);
                match value {
                    Value::Number(n) => {
                        if let Some(i) = n.as_i64() {
                            self.send_osc_int(&addr, i as i32).await?;
                        } else if let Some(f) = n.as_f64() {
                            self.send_osc_float(&addr, f as f32).await?;
                        }
                    }
                    Value::Bool(b) => {
                        self.send_osc_int(&addr, if *b { 1 } else { 0 }).await?;
                    }
                    _ => {}
                }
            }
        }

        self.animation_frames.fetch_add(1, Ordering::SeqCst);
        Ok(())
    }

    async fn send_audio_data(&mut self, audio: AudioData) -> BackendResult<()> {
        if !self.is_connected() {
            warn!("Cannot send audio - not connected to VRChat");
            return Err(BackendError::NotConnected);
        }

        info!(
            "send_audio_data called - {} bytes, format={}",
            audio.data.len(),
            audio.format
        );

        // Process expression tags from ElevenLabs audio
        if let Some(tags) = &audio.expression_tags {
            for tag in tags {
                if let Some((emotion, intensity)) = crate::constants::get_emotion_from_tag(tag) {
                    self.set_emotion(emotion, intensity).await?;
                }
            }
        }

        // VRChat automatically generates visemes from audio playback
        // Send audio playback trigger
        if let Some(text) = &audio.text {
            // Truncate to VRChat string limit
            let text = if text.len() > 127 { &text[..127] } else { text };
            self.send_osc(
                "/avatar/parameters/AudioText",
                OscType::String(text.to_string()),
            )
            .await?;
        }

        // Trigger audio playback state
        self.send_osc_float("/avatar/parameters/AudioPlaying", 1.0)
            .await?;

        // Schedule audio stop after duration
        if audio.duration > 0.0 {
            let socket = self.osc_socket.clone();
            let remote_host = self.remote_host.clone();
            let osc_in_port = self.osc_in_port.clone();
            let duration = audio.duration;

            tokio::spawn(async move {
                sleep(Duration::from_secs_f32(duration)).await;

                if let Some(ref sock) = *socket.read().await {
                    let host = remote_host.read().await;
                    let port = *osc_in_port.read().await;
                    let addr = format!("{}:{}", host, port);

                    // Stop audio
                    let msg = OscMessage {
                        addr: "/avatar/parameters/AudioPlaying".to_string(),
                        args: vec![OscType::Float(0.0)],
                    };
                    let packet = OscPacket::Message(msg);
                    if let Ok(encoded) = encoder::encode(&packet) {
                        let _ = sock.send_to(&encoded, &addr);
                    }

                    // Clear text
                    let msg = OscMessage {
                        addr: "/avatar/parameters/AudioText".to_string(),
                        args: vec![OscType::String(String::new())],
                    };
                    let packet = OscPacket::Message(msg);
                    if let Ok(encoded) = encoder::encode(&packet) {
                        let _ = sock.send_to(&encoded, &addr);
                    }
                }
            });
        }

        Ok(())
    }

    async fn receive_state(&self) -> BackendResult<Option<EnvironmentState>> {
        if !self.is_connected() {
            return Err(BackendError::NotConnected);
        }

        // Return state from OSC receiver tracked parameters
        let world = self.world_name.read().await.clone();

        let state = EnvironmentState {
            world_name: world.or_else(|| Some("Unknown".to_string())),
            ..Default::default()
        };

        Ok(Some(state))
    }

    async fn capture_video_frame(&self) -> BackendResult<Option<VideoFrame>> {
        if !self.is_connected() {
            return Err(BackendError::NotConnected);
        }

        // Video capture requires bridge server integration
        debug!("Video capture requires bridge server (use_bridge=True)");
        Ok(None)
    }

    async fn reset_all(&mut self) -> BackendResult<()> {
        if !self.is_connected() {
            return Err(BackendError::NotConnected);
        }

        info!("Resetting all states");

        // Clear any active emote
        let current = self.current_vrcemote.load(Ordering::SeqCst);
        if self.emote_is_active.load(Ordering::SeqCst) && current != 0 {
            self.send_osc_int("/avatar/parameters/VRCEmote", current)
                .await?;
            self.emote_is_active.store(false, Ordering::SeqCst);
            self.current_vrcemote.store(0, Ordering::SeqCst);
            info!("Reset: Cleared active emote");
        }

        // Stop all movement
        self.send_osc_float("/input/Vertical", 0.0).await?;
        self.send_osc_float("/input/Horizontal", 0.0).await?;
        self.send_osc_int("/input/Run", 0).await?;
        self.send_osc_int("/input/Jump", 0).await?;
        self.send_osc_int("/input/Crouch", 0).await?;

        // Reset state tracking
        *self.vertical_movement.write().await = 0.0;
        *self.horizontal_movement.write().await = 0.0;
        self.movement_active.store(false, Ordering::SeqCst);

        // Cancel timers
        if let Some(cancel) = self.movement_cancel.write().await.take() {
            let _ = cancel.send(());
        }

        info!("Reset: All states cleared");
        Ok(())
    }

    async fn execute_behavior(
        &mut self,
        behavior: &str,
        _parameters: HashMap<String, Value>,
    ) -> BackendResult<()> {
        if !self.is_connected() {
            return Err(BackendError::NotConnected);
        }

        info!("Executing behavior: {}", behavior);

        match behavior {
            "greet" => {
                self.set_gesture(GestureType::Wave, 1.0).await?;
                self.set_emotion(EmotionType::Happy, 1.0).await?;
            }
            "dance" => {
                self.set_gesture(GestureType::Dance, 1.0).await?;
            }
            "sit" => {
                self.send_osc_int("/avatar/parameters/Sitting", 1).await?;
            }
            "stand" => {
                self.send_osc_int("/avatar/parameters/Sitting", 0).await?;
            }
            "jump" => {
                self.send_osc_int("/input/Jump", 1).await?;
            }
            "crouch" => {
                self.send_osc_int("/avatar/parameters/Crouching", 1).await?;
            }
            _ => {
                warn!("Unknown behavior: {}", behavior);
            }
        }

        Ok(())
    }

    async fn get_statistics(&self) -> BackendResult<HashMap<String, Value>> {
        let current_emotion = self.current_emotion.read().await;
        let current_gesture = self.current_gesture.read().await;

        let mut stats = HashMap::new();
        stats.insert(
            "backend".to_string(),
            Value::String(self.backend_name().to_string()),
        );
        stats.insert("connected".to_string(), Value::Bool(self.is_connected()));
        stats.insert(
            "remote_host".to_string(),
            Value::String(self.remote_host.read().await.clone()),
        );
        stats.insert(
            "osc_messages_sent".to_string(),
            Value::Number(self.osc_messages_sent.load(Ordering::SeqCst).into()),
        );
        stats.insert(
            "osc_messages_received".to_string(),
            Value::Number(self.osc_messages_received.load(Ordering::SeqCst).into()),
        );
        stats.insert(
            "avatar_params_count".to_string(),
            Value::Number(self.avatar_params.read().await.len().into()),
        );
        stats.insert(
            "animation_frames".to_string(),
            Value::Number(self.animation_frames.load(Ordering::SeqCst).into()),
        );
        stats.insert(
            "errors".to_string(),
            Value::Number(self.errors.load(Ordering::SeqCst).into()),
        );
        stats.insert(
            "current_emotion".to_string(),
            serde_json::to_value(*current_emotion).unwrap_or(Value::Null),
        );
        stats.insert(
            "current_gesture".to_string(),
            serde_json::to_value(*current_gesture).unwrap_or(Value::Null),
        );
        stats.insert(
            "current_vrcemote".to_string(),
            Value::Number(self.current_vrcemote.load(Ordering::SeqCst).into()),
        );
        stats.insert(
            "emote_name".to_string(),
            Value::String(
                get_vrcemote_name(self.current_vrcemote.load(Ordering::SeqCst)).to_string(),
            ),
        );

        Ok(stats)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_vrchat_backend_creation() {
        let backend = VRChatRemoteBackend::new();
        assert!(!backend.is_connected());
        assert_eq!(backend.backend_name(), "vrchat_remote");
        assert!(backend.capabilities().animation);
        assert!(backend.capabilities().audio);
    }
}
