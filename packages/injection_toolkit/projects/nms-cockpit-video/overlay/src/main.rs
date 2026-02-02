//! NMS Cockpit Video Overlay
//!
//! Overlay application for the No Man's Sky Cockpit Video Player.
//! Displays video on cockpit screen with egui controls.

use anyhow::{Context, Result};
use clap::Parser;
use itk_ipc::IpcChannel;
use itk_protocol::{encode, MessageType, ScreenRect, VideoLoad, VideoPause, VideoPlay, VideoSeek};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tracing::{debug, error, info, warn};
use winit::{
    event::{Event, WindowEvent},
    event_loop::{ControlFlow, EventLoop},
    window::{WindowBuilder, WindowLevel},
};

mod platform;
mod render;
mod ui;
mod video;

use render::NmsRenderer;
use ui::VideoControls;
use video::VideoFrameReader;

/// NMS Cockpit Video Overlay
#[derive(Parser, Debug)]
#[command(name = "nms-video-overlay")]
#[command(about = "Video overlay for No Man's Sky Cockpit Video Player")]
struct Args {
    /// Daemon IPC channel name
    #[arg(long, default_value = "nms_cockpit_client")]
    daemon_channel: String,

    /// Window width
    #[arg(long, default_value = "1920")]
    width: u32,

    /// Window height
    #[arg(long, default_value = "1080")]
    height: u32,

    /// Video rectangle position and size: x,y,w,h (screen pixels)
    /// Default: centered 1280x720
    #[arg(long, value_parser = parse_video_rect)]
    video_rect: Option<ScreenRect>,

    /// Log level
    #[arg(long, default_value = "info")]
    log_level: String,
}

/// Parse a video rect string "x,y,w,h" into a ScreenRect.
fn parse_video_rect(s: &str) -> Result<ScreenRect, String> {
    let parts: Vec<&str> = s.split(',').collect();
    if parts.len() != 4 {
        return Err("Expected format: x,y,w,h (e.g., 320,180,1280,720)".to_string());
    }
    let x: f32 = parts[0]
        .trim()
        .parse()
        .map_err(|e| format!("Invalid x: {e}"))?;
    let y: f32 = parts[1]
        .trim()
        .parse()
        .map_err(|e| format!("Invalid y: {e}"))?;
    let w: f32 = parts[2]
        .trim()
        .parse()
        .map_err(|e| format!("Invalid width: {e}"))?;
    let h: f32 = parts[3]
        .trim()
        .parse()
        .map_err(|e| format!("Invalid height: {e}"))?;
    Ok(ScreenRect {
        x,
        y,
        width: w,
        height: h,
        rotation: 0.0,
        visible: true,
    })
}

/// Default video rectangle: centered, 720p on a 1920x1080 screen.
const DEFAULT_VIDEO_RECT: ScreenRect = ScreenRect {
    x: 320.0,
    y: 180.0,
    width: 1280.0,
    height: 720.0,
    rotation: 0.0,
    visible: true,
};

/// Overlay state
struct OverlayState {
    /// Current screen rect for rendering
    screen_rect: Option<ScreenRect>,
    /// Whether in click-through mode
    click_through: bool,
}

impl Default for OverlayState {
    fn default() -> Self {
        Self {
            screen_rect: None,
            click_through: true,
        }
    }
}

/// Manages the IPC connection to the daemon with auto-reconnect.
struct DaemonConnection {
    channel_name: String,
    channel: Option<Box<dyn IpcChannel>>,
    last_connect_attempt: Instant,
    reconnect_interval: Duration,
}

impl DaemonConnection {
    fn new(channel_name: &str) -> Self {
        Self {
            channel_name: channel_name.to_string(),
            channel: None,
            last_connect_attempt: Instant::now() - Duration::from_secs(10), // Allow immediate first attempt
            reconnect_interval: Duration::from_secs(2),
        }
    }

    /// Try to connect if not already connected (rate-limited).
    fn ensure_connected(&mut self) {
        if self.channel.as_ref().is_some_and(|c| c.is_connected()) {
            return;
        }

        // Rate-limit reconnection attempts
        if self.last_connect_attempt.elapsed() < self.reconnect_interval {
            return;
        }
        self.last_connect_attempt = Instant::now();

        match itk_ipc::connect(&self.channel_name) {
            Ok(ch) => {
                info!(channel = %self.channel_name, "Connected to daemon");
                self.channel = Some(Box::new(ch));
            },
            Err(e) => {
                debug!(?e, "Daemon not available, will retry");
                self.channel = None;
            },
        }
    }

    /// Send a protocol message to the daemon.
    fn send_message<T: serde::Serialize>(&mut self, msg_type: MessageType, payload: &T) -> bool {
        self.ensure_connected();
        let Some(ref channel) = self.channel else {
            return false;
        };

        match encode(msg_type, payload) {
            Ok(data) => match channel.send(&data) {
                Ok(()) => true,
                Err(e) => {
                    warn!(?e, "Failed to send to daemon, disconnecting");
                    self.channel = None;
                    false
                },
            },
            Err(e) => {
                error!(?e, "Failed to encode message");
                false
            },
        }
    }

    fn is_connected(&self) -> bool {
        self.channel.as_ref().is_some_and(|c| c.is_connected())
    }
}

fn main() -> Result<()> {
    let args = Args::parse();

    // Initialize logging
    let filter = format!(
        "nms_video_overlay={},itk={}",
        args.log_level, args.log_level
    );
    let env_filter = tracing_subscriber::EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(&filter));
    tracing_subscriber::fmt().with_env_filter(env_filter).init();

    info!("NMS Cockpit Video Overlay starting");

    let video_rect = args.video_rect.unwrap_or(DEFAULT_VIDEO_RECT);

    // Create event loop
    let event_loop = EventLoop::new().context("Failed to create event loop")?;
    event_loop.set_control_flow(ControlFlow::Poll);

    // Create window sized and positioned to match the video rect
    let window = WindowBuilder::new()
        .with_title("NMS Cockpit Video")
        .with_inner_size(winit::dpi::PhysicalSize::new(
            video_rect.width as u32,
            video_rect.height as u32,
        ))
        .with_position(winit::dpi::PhysicalPosition::new(
            video_rect.x as i32,
            video_rect.y as i32,
        ))
        .with_decorations(false)
        .with_window_level(WindowLevel::AlwaysOnTop)
        .build(&event_loop)
        .context("Failed to create window")?;

    let window = Arc::new(window);

    // Set platform-specific attributes
    if let Err(e) = platform::set_transparent(&window) {
        error!(?e, "Failed to set transparent");
    }
    if let Err(e) = platform::set_always_on_top(&window, true) {
        error!(?e, "Failed to set always-on-top");
    }
    if let Err(e) = platform::set_click_through(&window, true) {
        error!(?e, "Failed to set click-through");
    }

    // Create renderer with egui
    let mut renderer = pollster::block_on(NmsRenderer::new(Arc::clone(&window)))
        .context("Failed to create renderer")?;
    info!("Renderer initialized");

    // Application state
    let mut state = OverlayState::default();
    let mut frame_reader = VideoFrameReader::new();
    let mut controls = VideoControls::new();
    let mut daemon = DaemonConnection::new(&args.daemon_channel);
    let mut logged_frame_connection = false;
    let mut f9_was_down = false;

    info!("NMS Cockpit Video Overlay started. Press F9 to toggle controls.");

    // Run event loop
    event_loop
        .run(move |event, elwt| {
            match event {
                Event::WindowEvent { event, .. } => {
                    // Pass events to egui first when interactive
                    if !state.click_through {
                        let _ = renderer.handle_event(&event);
                    }

                    match event {
                        WindowEvent::CloseRequested => {
                            elwt.exit();
                        },

                        WindowEvent::Resized(physical_size) => {
                            renderer.resize(physical_size);
                        },

                        WindowEvent::KeyboardInput { event, .. } => {
                            if event.state.is_pressed() {
                                match event.physical_key {
                                    // F9 toggles click-through/interactive mode
                                    winit::keyboard::PhysicalKey::Code(
                                        winit::keyboard::KeyCode::F9,
                                    ) => {
                                        state.click_through = !state.click_through;
                                        if let Err(e) = platform::set_click_through(
                                            &window,
                                            state.click_through,
                                        ) {
                                            error!(?e, "Failed to toggle click-through");
                                        }
                                        info!(
                                            mode = if state.click_through {
                                                "click-through"
                                            } else {
                                                "interactive"
                                            },
                                            "Mode toggled"
                                        );
                                    },
                                    // Space toggles play/pause in interactive mode
                                    winit::keyboard::PhysicalKey::Code(
                                        winit::keyboard::KeyCode::Space,
                                    ) => {
                                        if !state.click_through {
                                            controls.toggle_play_pause();
                                        }
                                    },
                                    // Left arrow seeks back 10s
                                    winit::keyboard::PhysicalKey::Code(
                                        winit::keyboard::KeyCode::ArrowLeft,
                                    ) => {
                                        if !state.click_through {
                                            controls.seek_relative(-10_000);
                                        }
                                    },
                                    // Right arrow seeks forward 10s
                                    winit::keyboard::PhysicalKey::Code(
                                        winit::keyboard::KeyCode::ArrowRight,
                                    ) => {
                                        if !state.click_through {
                                            controls.seek_relative(10_000);
                                        }
                                    },
                                    _ => {},
                                }
                            }
                        },

                        WindowEvent::RedrawRequested => {
                            // Get screen rect: prefer NMS mod rect, fall back to CLI/default
                            let screen_rect = state.screen_rect.as_ref().or_else(|| {
                                if frame_reader.is_connected() && frame_reader.last_pts_ms() > 0 {
                                    Some(&video_rect)
                                } else {
                                    None
                                }
                            });

                            // Render video and UI
                            let show_ui = !state.click_through;
                            if let Err(e) = renderer.render(screen_rect, show_ui, &mut controls) {
                                error!(?e, "Render failed");
                            }
                        },

                        _ => {},
                    }
                },

                Event::AboutToWait => {
                    // Poll global F9 hotkey (works even in click-through mode)
                    if platform::is_key_just_pressed(platform::VK_F9, &mut f9_was_down) {
                        state.click_through = !state.click_through;
                        if let Err(e) = platform::set_click_through(&window, state.click_through) {
                            error!(?e, "Failed to toggle click-through");
                        }
                        info!(
                            mode = if state.click_through {
                                "click-through"
                            } else {
                                "interactive"
                            },
                            "Mode toggled"
                        );
                    }

                    // Update connection status
                    controls.set_daemon_connected(daemon.is_connected());

                    // Log frame buffer connection status
                    if !logged_frame_connection && frame_reader.is_connected() {
                        info!("Connected to video frame buffer");
                        logged_frame_connection = true;
                    }

                    // Read new video frames
                    if let Some(frame_data) = frame_reader.try_read_frame() {
                        renderer.update_texture(frame_data);
                        // Update controls with current position
                        controls.set_position(frame_reader.last_pts_ms());
                        debug!(pts_ms = frame_reader.last_pts_ms(), "Updated frame");
                    }

                    // Update duration from shared memory (set once on load)
                    let dur = frame_reader.duration_ms();
                    if dur > 0 {
                        controls.set_duration(dur);
                    }

                    // Process any UI actions
                    process_ui_actions(&mut controls, &mut daemon);

                    // Request redraw
                    window.request_redraw();
                },

                _ => {},
            }
        })
        .context("Event loop failed")?;

    Ok(())
}

/// Process UI actions and send commands to the daemon via IPC.
fn process_ui_actions(controls: &mut VideoControls, daemon: &mut DaemonConnection) {
    // Periodically try to connect
    daemon.ensure_connected();

    // Load video
    if let Some(url) = controls.take_load_request() {
        info!(url = %url, "Loading video");
        let cmd = VideoLoad {
            source: url,
            start_position_ms: 0,
            autoplay: true,
        };
        if !daemon.send_message(MessageType::VideoLoad, &cmd) {
            warn!("Failed to send load command (daemon not connected)");
        }
    }

    // Play
    if controls.take_play_request() {
        debug!("Play");
        let cmd = VideoPlay {
            from_position_ms: None,
        };
        daemon.send_message(MessageType::VideoPlay, &cmd);
    }

    // Pause
    if controls.take_pause_request() {
        debug!("Pause");
        let cmd = VideoPause {};
        daemon.send_message(MessageType::VideoPause, &cmd);
    }

    // Seek
    if let Some(position_ms) = controls.take_seek_request() {
        debug!(position_ms, "Seek");
        let cmd = VideoSeek { position_ms };
        daemon.send_message(MessageType::VideoSeek, &cmd);
    }
}
