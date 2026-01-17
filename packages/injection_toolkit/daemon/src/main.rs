//! # ITK Daemon Template
//!
//! Central coordinator daemon for an Injection Toolkit project.
//!
//! This template provides:
//! - IPC server for injected modules
//! - State aggregation and caching
//! - Optional multiplayer synchronization
//! - Configurable logging
//!
//! ## Customization Points
//!
//! 1. `StateHandler` trait - implement for your application-specific state
//! 2. `process_injector_message` - handle messages from injected code
//! 3. `process_client_message` - handle messages from overlay/MCP clients
//!
//! ## Security
//!
//! IMPORTANT: Data from the injector should be treated as UNTRUSTED.
//! A compromised or malicious injector could send crafted messages.
//! All incoming data is validated before use.

use anyhow::{bail, Context, Result};
use itk_ipc::{IpcChannel, IpcServer};
use itk_protocol::{
    decode, encode, MessageType, ScreenRect, StateEvent, StateQuery, StateResponse, StateSnapshot,
};
use std::collections::HashMap;
use std::sync::{Arc, RwLock};
use std::thread;
use tracing::{error, info, warn};

// =============================================================================
// Security: Input Validation
// =============================================================================

/// Maximum allowed string length for event types and keys
const MAX_STRING_LEN: usize = 256;

/// Maximum allowed JSON data size
const MAX_DATA_SIZE: usize = 64 * 1024; // 64 KB

/// Maximum screen dimension (sanity check)
const MAX_SCREEN_DIM: f32 = 16384.0;

/// Validate a ScreenRect from untrusted source
fn validate_screen_rect(rect: &ScreenRect) -> Result<()> {
    // Check for NaN/Inf which could cause issues
    if !rect.x.is_finite()
        || !rect.y.is_finite()
        || !rect.width.is_finite()
        || !rect.height.is_finite()
        || !rect.rotation.is_finite()
    {
        bail!("ScreenRect contains non-finite values");
    }

    // Sanity check dimensions
    if rect.x.abs() > MAX_SCREEN_DIM
        || rect.y.abs() > MAX_SCREEN_DIM
        || rect.width > MAX_SCREEN_DIM
        || rect.height > MAX_SCREEN_DIM
    {
        bail!("ScreenRect dimensions out of bounds");
    }

    // Width/height should be non-negative
    if rect.width < 0.0 || rect.height < 0.0 {
        bail!("ScreenRect has negative dimensions");
    }

    // Check for coordinate overflow (could crash GPU/wgpu)
    let right = rect.x + rect.width;
    let bottom = rect.y + rect.height;
    if !right.is_finite()
        || !bottom.is_finite()
        || right.abs() > MAX_SCREEN_DIM
        || bottom.abs() > MAX_SCREEN_DIM
    {
        bail!(
            "ScreenRect coordinate overflow: right={}, bottom={}",
            right,
            bottom
        );
    }

    Ok(())
}

/// Validate a StateEvent from untrusted source
fn validate_state_event(event: &StateEvent) -> Result<()> {
    if event.event_type.len() > MAX_STRING_LEN {
        bail!(
            "StateEvent event_type too long: {} bytes",
            event.event_type.len()
        );
    }
    if event.data.len() > MAX_DATA_SIZE {
        bail!("StateEvent data too large: {} bytes", event.data.len());
    }
    if event.app_id.len() > MAX_STRING_LEN {
        bail!("StateEvent app_id too long: {} bytes", event.app_id.len());
    }
    Ok(())
}

/// Validate a StateSnapshot from untrusted source
fn validate_state_snapshot(snapshot: &StateSnapshot) -> Result<()> {
    if snapshot.app_id.len() > MAX_STRING_LEN {
        bail!(
            "StateSnapshot app_id too long: {} bytes",
            snapshot.app_id.len()
        );
    }
    if snapshot.data.len() > MAX_DATA_SIZE {
        bail!(
            "StateSnapshot data too large: {} bytes",
            snapshot.data.len()
        );
    }
    Ok(())
}

/// Application state container
///
/// Customize this for your specific application.
#[derive(Debug, Default)]
pub struct AppState {
    /// Screen rect from injector (for overlay positioning)
    pub screen_rect: Option<ScreenRect>,

    /// Custom state data (JSON format for flexibility)
    pub custom_data: HashMap<String, String>,

    /// Last update timestamp
    pub last_update_ms: u64,
}

/// Daemon configuration
#[derive(Debug, Clone)]
pub struct DaemonConfig {
    /// Application identifier (e.g., "nms", "vrchat")
    pub app_id: String,

    /// IPC channel name for injector communication
    pub injector_channel: String,

    /// IPC channel name for client (overlay/MCP) communication
    pub client_channel: String,

    /// Enable multiplayer sync
    pub enable_sync: bool,
}

impl Default for DaemonConfig {
    fn default() -> Self {
        Self {
            app_id: "itk_app".to_string(),
            injector_channel: "itk_injector".to_string(),
            client_channel: "itk_client".to_string(),
            enable_sync: false,
        }
    }
}

/// Main daemon struct
pub struct Daemon {
    config: DaemonConfig,
    state: Arc<RwLock<AppState>>,
}

impl Daemon {
    /// Create a new daemon instance
    pub fn new(config: DaemonConfig) -> Self {
        Self {
            config,
            state: Arc::new(RwLock::new(AppState::default())),
        }
    }

    /// Run the daemon
    pub fn run(&self) -> Result<()> {
        info!(
            app_id = %self.config.app_id,
            "Starting ITK daemon"
        );

        // Start injector listener thread
        let injector_state = Arc::clone(&self.state);
        let injector_channel = self.config.injector_channel.clone();
        let injector_handle = thread::spawn(move || {
            if let Err(e) = run_injector_listener(&injector_channel, injector_state) {
                error!(?e, "Injector listener failed");
            }
        });

        // Start client listener thread
        let client_state = Arc::clone(&self.state);
        let client_channel = self.config.client_channel.clone();
        let app_id = self.config.app_id.clone();
        let client_handle = thread::spawn(move || {
            if let Err(e) = run_client_listener(&client_channel, client_state, &app_id) {
                error!(?e, "Client listener failed");
            }
        });

        info!("Daemon running. Press Ctrl+C to stop.");

        // Wait for threads
        let _ = injector_handle.join();
        let _ = client_handle.join();

        Ok(())
    }
}

/// Run the injector IPC listener
fn run_injector_listener(channel_name: &str, state: Arc<RwLock<AppState>>) -> Result<()> {
    info!(channel = %channel_name, "Starting injector listener");

    let server = itk_ipc::listen(channel_name).context("Failed to create injector IPC server")?;

    loop {
        info!("Waiting for injector connection...");

        match server.accept() {
            Ok(channel) => {
                info!("Injector connected");
                handle_injector_connection(channel, Arc::clone(&state));
            }
            Err(e) => {
                warn!(?e, "Failed to accept injector connection");
                thread::sleep(std::time::Duration::from_secs(1));
            }
        }
    }
}

/// Handle a connected injector
fn handle_injector_connection(channel: impl IpcChannel, state: Arc<RwLock<AppState>>) {
    loop {
        match channel.recv() {
            Ok(data) => {
                if let Err(e) = process_injector_message(&data, &state) {
                    warn!(?e, "Failed to process injector message");
                }
            }
            Err(itk_ipc::IpcError::ChannelClosed) => {
                info!("Injector disconnected");
                break;
            }
            Err(e) => {
                warn!(?e, "Error receiving from injector");
                break;
            }
        }
    }
}

/// Process a message from the injector
///
/// SECURITY: All data from the injector is treated as UNTRUSTED and validated.
/// Customize this function for your application's specific message types.
fn process_injector_message(data: &[u8], state: &Arc<RwLock<AppState>>) -> Result<()> {
    let header = itk_protocol::decode_header(data)?;

    match header.msg_type {
        MessageType::ScreenRect => {
            let (_, rect): (_, ScreenRect) = decode(data)?;
            // SECURITY: Validate before use
            validate_screen_rect(&rect)?;
            let mut state = state.write().unwrap();
            state.screen_rect = Some(rect);
            state.last_update_ms = itk_sync::now_ms();
        }

        MessageType::StateEvent => {
            let (_, event): (_, StateEvent) = decode(data)?;
            // SECURITY: Validate before use
            validate_state_event(&event)?;
            let mut state = state.write().unwrap();
            state.custom_data.insert(event.event_type, event.data);
            state.last_update_ms = event.timestamp_ms;
        }

        MessageType::StateSnapshot => {
            let (_, snapshot): (_, StateSnapshot) = decode(data)?;
            // SECURITY: Validate before use
            validate_state_snapshot(&snapshot)?;
            let mut state = state.write().unwrap();
            state
                .custom_data
                .insert("snapshot".to_string(), snapshot.data);
            state.last_update_ms = snapshot.timestamp_ms;
        }

        other => {
            warn!(?other, "Unexpected message type from injector");
        }
    }

    Ok(())
}

/// Run the client (overlay/MCP) IPC listener
fn run_client_listener(
    channel_name: &str,
    state: Arc<RwLock<AppState>>,
    app_id: &str,
) -> Result<()> {
    info!(channel = %channel_name, "Starting client listener");

    let server = itk_ipc::listen(channel_name).context("Failed to create client IPC server")?;

    loop {
        info!("Waiting for client connection...");

        match server.accept() {
            Ok(channel) => {
                info!("Client connected");
                handle_client_connection(channel, Arc::clone(&state), app_id);
            }
            Err(e) => {
                warn!(?e, "Failed to accept client connection");
                thread::sleep(std::time::Duration::from_secs(1));
            }
        }
    }
}

/// Handle a connected client
fn handle_client_connection(channel: impl IpcChannel, state: Arc<RwLock<AppState>>, app_id: &str) {
    loop {
        match channel.recv() {
            Ok(data) => {
                if let Err(e) = process_client_message(&data, &state, &channel, app_id) {
                    warn!(?e, "Failed to process client message");
                }
            }
            Err(itk_ipc::IpcError::ChannelClosed) => {
                info!("Client disconnected");
                break;
            }
            Err(e) => {
                warn!(?e, "Error receiving from client");
                break;
            }
        }
    }
}

/// Process a message from a client (overlay or MCP)
///
/// Customize this function for your application's specific queries.
fn process_client_message(
    data: &[u8],
    state: &Arc<RwLock<AppState>>,
    channel: &impl IpcChannel,
    app_id: &str,
) -> Result<()> {
    let header = itk_protocol::decode_header(data)?;

    match header.msg_type {
        MessageType::Ping => {
            // Respond with pong
            let pong = encode(MessageType::Pong, &())?;
            channel.send(&pong)?;
        }

        MessageType::StateQuery => {
            let (_, query): (_, StateQuery) = decode(data)?;
            let response = handle_state_query(&query, state, app_id)?;
            let encoded = encode(MessageType::StateResponse, &response)?;
            channel.send(&encoded)?;
        }

        other => {
            warn!(?other, "Unexpected message type from client");
        }
    }

    Ok(())
}

/// Handle a state query from a client
fn handle_state_query(
    query: &StateQuery,
    state: &Arc<RwLock<AppState>>,
    app_id: &str,
) -> Result<StateResponse> {
    let state = state.read().unwrap();

    let response = match query.query_type.as_str() {
        "screen_rect" => {
            if let Some(ref rect) = state.screen_rect {
                StateResponse {
                    success: true,
                    data: Some(serde_json::to_string(rect)?),
                    error: None,
                }
            } else {
                StateResponse {
                    success: false,
                    data: None,
                    error: Some("No screen rect available".to_string()),
                }
            }
        }

        "snapshot" => {
            let snapshot = StateSnapshot {
                app_id: app_id.to_string(),
                timestamp_ms: state.last_update_ms,
                data: serde_json::to_string(&state.custom_data)?,
            };
            StateResponse {
                success: true,
                data: Some(serde_json::to_string(&snapshot)?),
                error: None,
            }
        }

        "custom" => {
            // Query for specific custom data key
            if let Some(value) = state.custom_data.get(&query.params) {
                StateResponse {
                    success: true,
                    data: Some(value.clone()),
                    error: None,
                }
            } else {
                StateResponse {
                    success: false,
                    data: None,
                    error: Some(format!("Key not found: {}", query.params)),
                }
            }
        }

        _ => StateResponse {
            success: false,
            data: None,
            error: Some(format!("Unknown query type: {}", query.query_type)),
        },
    };

    Ok(response)
}

fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("itk_daemon=info".parse().unwrap()),
        )
        .init();

    // Load config (in a real app, this would come from CLI args or a config file)
    let config = DaemonConfig::default();

    // Create and run daemon
    let daemon = Daemon::new(config);
    daemon.run()?;

    Ok(())
}
