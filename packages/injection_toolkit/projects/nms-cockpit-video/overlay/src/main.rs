//! NMS Cockpit Video Overlay
//!
//! Overlay application for the No Man's Sky Cockpit Video Player.
//! Displays video on cockpit screen with egui controls.

use anyhow::{Context, Result};
use clap::Parser;
use itk_protocol::ScreenRect;
use std::sync::Arc;
use tracing::{debug, error, info};
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

    /// Log level
    #[arg(long, default_value = "info")]
    log_level: String,
}

/// Default video rectangle: centered, 720p
static DEFAULT_VIDEO_RECT: ScreenRect = ScreenRect {
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

fn main() -> Result<()> {
    let args = Args::parse();

    // Initialize logging
    let filter = format!("nms_video_overlay={},itk={}", args.log_level, args.log_level);
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive(filter.parse().unwrap()),
        )
        .init();

    info!("NMS Cockpit Video Overlay starting");

    // Create event loop
    let event_loop = EventLoop::new().context("Failed to create event loop")?;
    event_loop.set_control_flow(ControlFlow::Poll);

    // Create window
    let window = WindowBuilder::new()
        .with_title("NMS Cockpit Video")
        .with_inner_size(winit::dpi::LogicalSize::new(args.width, args.height))
        .with_transparent(true)
        .with_decorations(false)
        .with_window_level(WindowLevel::AlwaysOnTop)
        .build(&event_loop)
        .context("Failed to create window")?;

    let window = Arc::new(window);

    // Set platform-specific attributes
    if let Err(e) = platform::set_transparent(&*window) {
        error!(?e, "Failed to set transparent");
    }
    if let Err(e) = platform::set_always_on_top(&*window, true) {
        error!(?e, "Failed to set always-on-top");
    }
    if let Err(e) = platform::set_click_through(&*window, true) {
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
    let mut logged_frame_connection = false;

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
                        }

                        WindowEvent::Resized(physical_size) => {
                            renderer.resize(physical_size);
                        }

                        WindowEvent::KeyboardInput { event, .. } => {
                            if event.state.is_pressed() {
                                match event.physical_key {
                                    // F9 toggles click-through/interactive mode
                                    winit::keyboard::PhysicalKey::Code(
                                        winit::keyboard::KeyCode::F9,
                                    ) => {
                                        state.click_through = !state.click_through;
                                        if let Err(e) =
                                            platform::set_click_through(&*window, state.click_through)
                                        {
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
                                    // Space toggles play/pause in interactive mode
                                    winit::keyboard::PhysicalKey::Code(
                                        winit::keyboard::KeyCode::Space,
                                    ) => {
                                        if !state.click_through {
                                            controls.toggle_play_pause();
                                        }
                                    }
                                    // Left arrow seeks back 10s
                                    winit::keyboard::PhysicalKey::Code(
                                        winit::keyboard::KeyCode::ArrowLeft,
                                    ) => {
                                        if !state.click_through {
                                            controls.seek_relative(-10_000);
                                        }
                                    }
                                    // Right arrow seeks forward 10s
                                    winit::keyboard::PhysicalKey::Code(
                                        winit::keyboard::KeyCode::ArrowRight,
                                    ) => {
                                        if !state.click_through {
                                            controls.seek_relative(10_000);
                                        }
                                    }
                                    _ => {}
                                }
                            }
                        }

                        WindowEvent::RedrawRequested => {
                            // Get screen rect from state or use default if video is playing
                            let screen_rect = state.screen_rect.as_ref().or_else(|| {
                                if frame_reader.is_connected() && frame_reader.last_pts_ms() > 0 {
                                    Some(&DEFAULT_VIDEO_RECT)
                                } else {
                                    None
                                }
                            });

                            // Render video and UI
                            let show_ui = !state.click_through;
                            if let Err(e) = renderer.render(screen_rect, show_ui, &mut controls) {
                                error!(?e, "Render failed");
                            }
                        }

                        _ => {}
                    }
                }

                Event::AboutToWait => {
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

                    // Process any UI actions
                    process_ui_actions(&mut controls);

                    // Request redraw
                    window.request_redraw();
                }

                _ => {}
            }
        })
        .context("Event loop failed")?;

    Ok(())
}

/// Process UI actions (currently just logs - IPC will be added later)
fn process_ui_actions(controls: &mut VideoControls) {
    // Load video
    if let Some(url) = controls.take_load_request() {
        info!(url = %url, "Load video requested (IPC not yet implemented)");
    }

    // Play
    if controls.take_play_request() {
        debug!("Play requested");
    }

    // Pause
    if controls.take_pause_request() {
        debug!("Pause requested");
    }

    // Seek
    if let Some(position_ms) = controls.take_seek_request() {
        debug!(position_ms, "Seek requested");
    }
}
