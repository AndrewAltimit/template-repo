//! NMS Cockpit Video Player - Daemon
//!
//! Central coordinator for the No Man's Sky cockpit video player.
//! Handles video decoding, screen rect from the mod, and multiplayer sync.

use anyhow::{Context, Result};
use clap::Parser;
use itk_ipc::{IpcChannel, IpcServer};
use itk_protocol::{
    decode, encode, MessageType, ScreenRect, StateQuery, StateResponse,
    VideoLoad, VideoPause, VideoPlay, VideoSeek,
};
use std::sync::{Arc, RwLock};
use std::thread;
use std::time::Duration;
use tracing::{debug, error, info, warn};

mod video;
use video::VideoPlayer;

/// NMS Cockpit Video Player Daemon
#[derive(Parser, Debug)]
#[command(name = "nms-video-daemon")]
#[command(about = "Video playback daemon for No Man's Sky Cockpit Video Player")]
struct Args {
    /// IPC channel name for the NMS mod
    #[arg(long, default_value = "nms_cockpit_injector")]
    mod_channel: String,

    /// IPC channel name for clients (overlay, MCP)
    #[arg(long, default_value = "nms_cockpit_client")]
    client_channel: String,

    /// Enable multiplayer sync
    #[arg(long)]
    multiplayer: bool,

    /// Multiplayer sync port
    #[arg(long, default_value = "7331")]
    sync_port: u16,

    /// Log level (trace, debug, info, warn, error)
    #[arg(long, default_value = "info")]
    log_level: String,
}

/// Application state
#[derive(Default)]
struct AppState {
    /// Screen rect from NMS mod
    screen_rect: Option<ScreenRect>,
    /// Last update timestamp
    last_update_ms: u64,
    /// Video player
    video_player: Option<VideoPlayer>,
}

fn main() -> Result<()> {
    let args = Args::parse();

    // Initialize logging
    let filter = format!("nms_video_daemon={},itk={}", args.log_level, args.log_level);
    let env_filter = tracing_subscriber::EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(&filter));
    tracing_subscriber::fmt()
        .with_env_filter(env_filter)
        .init();

    info!("NMS Cockpit Video Player Daemon starting");
    info!(mod_channel = %args.mod_channel, client_channel = %args.client_channel);

    if args.multiplayer {
        info!(port = args.sync_port, "Multiplayer sync enabled");
    }

    let state = Arc::new(RwLock::new(AppState::default()));

    // Initialize video player
    {
        let mut state = state.write().unwrap();
        state.video_player = Some(VideoPlayer::new());
        info!("Video player initialized");
    }

    // Start mod listener thread (receives ScreenRect from NMS)
    let mod_state = Arc::clone(&state);
    let mod_channel = args.mod_channel.clone();
    let mod_handle = thread::spawn(move || {
        if let Err(e) = run_mod_listener(&mod_channel, mod_state) {
            error!(?e, "Mod listener failed");
        }
    });

    // Start client listener thread (receives commands from overlay)
    let client_state = Arc::clone(&state);
    let client_channel = args.client_channel.clone();
    let client_handle = thread::spawn(move || {
        if let Err(e) = run_client_listener(&client_channel, client_state) {
            error!(?e, "Client listener failed");
        }
    });

    info!("Daemon running. Press Ctrl+C to stop.");

    // Wait for threads
    let _ = mod_handle.join();
    let _ = client_handle.join();

    Ok(())
}

/// Run the mod IPC listener (receives ScreenRect from NMS mod)
fn run_mod_listener(channel_name: &str, state: Arc<RwLock<AppState>>) -> Result<()> {
    info!(channel = %channel_name, "Starting mod listener");

    let server = itk_ipc::listen(channel_name).context("Failed to create mod IPC server")?;

    loop {
        info!("Waiting for NMS mod connection...");

        match server.accept() {
            Ok(channel) => {
                info!("NMS mod connected");
                handle_mod_connection(channel, Arc::clone(&state));
            }
            Err(e) => {
                warn!(?e, "Failed to accept mod connection");
                thread::sleep(Duration::from_secs(1));
            }
        }
    }
}

/// Handle a connected NMS mod
fn handle_mod_connection(channel: impl IpcChannel, state: Arc<RwLock<AppState>>) {
    loop {
        match channel.recv() {
            Ok(data) => {
                if let Err(e) = process_mod_message(&data, &state) {
                    warn!(?e, "Failed to process mod message");
                }
            }
            Err(itk_ipc::IpcError::ChannelClosed) => {
                info!("NMS mod disconnected");
                break;
            }
            Err(e) => {
                warn!(?e, "Error receiving from mod");
                break;
            }
        }
    }
}

/// Process a message from the NMS mod
fn process_mod_message(data: &[u8], state: &Arc<RwLock<AppState>>) -> Result<()> {
    let header = itk_protocol::decode_header(data)?;

    match header.msg_type {
        MessageType::ScreenRect => {
            let (_, rect): (_, ScreenRect) = decode(data)?;

            // Validate the rect
            if !rect.x.is_finite() || !rect.y.is_finite()
                || !rect.width.is_finite() || !rect.height.is_finite()
            {
                warn!("Invalid ScreenRect from mod (non-finite values)");
                return Ok(());
            }

            debug!(x = rect.x, y = rect.y, w = rect.width, h = rect.height, "Updated screen rect");

            let mut state = state.write().unwrap();
            state.screen_rect = Some(rect);
            state.last_update_ms = itk_sync::now_ms();
        }
        other => {
            warn!(?other, "Unexpected message type from mod");
        }
    }

    Ok(())
}

/// Run the client IPC listener (receives commands from overlay)
fn run_client_listener(channel_name: &str, state: Arc<RwLock<AppState>>) -> Result<()> {
    info!(channel = %channel_name, "Starting client listener");

    let server = itk_ipc::listen(channel_name).context("Failed to create client IPC server")?;

    loop {
        info!("Waiting for client connection...");

        match server.accept() {
            Ok(channel) => {
                info!("Client connected");
                handle_client_connection(channel, Arc::clone(&state));
            }
            Err(e) => {
                warn!(?e, "Failed to accept client connection");
                thread::sleep(Duration::from_secs(1));
            }
        }
    }
}

/// Handle a connected client (overlay)
fn handle_client_connection(channel: impl IpcChannel, state: Arc<RwLock<AppState>>) {
    loop {
        match channel.recv() {
            Ok(data) => {
                if let Err(e) = process_client_message(&data, &state, &channel) {
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

/// Process a message from a client
fn process_client_message(
    data: &[u8],
    state: &Arc<RwLock<AppState>>,
    channel: &impl IpcChannel,
) -> Result<()> {
    let header = itk_protocol::decode_header(data)?;

    match header.msg_type {
        MessageType::Ping => {
            let pong = encode(MessageType::Pong, &())?;
            channel.send(&pong)?;
        }

        MessageType::StateQuery => {
            let (_, query): (_, StateQuery) = decode(data)?;
            let response = handle_state_query(&query, state)?;
            let encoded = encode(MessageType::StateResponse, &response)?;
            channel.send(&encoded)?;
        }

        MessageType::VideoLoad => {
            let (_, cmd): (_, VideoLoad) = decode(data)?;
            info!(source = %cmd.source, "Loading video");
            let state = state.read().unwrap();
            if let Some(ref player) = state.video_player {
                player.load(&cmd.source, cmd.start_position_ms, cmd.autoplay);
            }
        }

        MessageType::VideoPlay => {
            let (_, _cmd): (_, VideoPlay) = decode(data)?;
            debug!("Play");
            let state = state.read().unwrap();
            if let Some(ref player) = state.video_player {
                player.play();
            }
        }

        MessageType::VideoPause => {
            let (_, _cmd): (_, VideoPause) = decode(data)?;
            debug!("Pause");
            let state = state.read().unwrap();
            if let Some(ref player) = state.video_player {
                player.pause();
            }
        }

        MessageType::VideoSeek => {
            let (_, cmd): (_, VideoSeek) = decode(data)?;
            debug!(position_ms = cmd.position_ms, "Seek");
            let state = state.read().unwrap();
            if let Some(ref player) = state.video_player {
                player.seek(cmd.position_ms);
            }
        }

        other => {
            warn!(?other, "Unexpected message type from client");
        }
    }

    Ok(())
}

/// Handle a state query
fn handle_state_query(query: &StateQuery, state: &Arc<RwLock<AppState>>) -> Result<StateResponse> {
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
                    error: Some("No screen rect available (NMS mod not connected)".to_string()),
                }
            }
        }

        "video_state" => {
            if let Some(ref player) = state.video_player {
                if let Some(video_state) = player.get_video_state() {
                    StateResponse {
                        success: true,
                        data: Some(serde_json::to_string(&video_state)?),
                        error: None,
                    }
                } else {
                    StateResponse {
                        success: false,
                        data: None,
                        error: Some("No video loaded".to_string()),
                    }
                }
            } else {
                StateResponse {
                    success: false,
                    data: None,
                    error: Some("Video player not initialized".to_string()),
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
