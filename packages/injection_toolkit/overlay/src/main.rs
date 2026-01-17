//! # ITK Overlay Application
//!
//! Example overlay application using the ITK overlay library.

use anyhow::Result;
use itk_overlay::{platform, render::Renderer, OverlayConfig, OverlayState};
use std::sync::Arc;
use tracing::{error, info};
use winit::{
    application::ApplicationHandler,
    event::WindowEvent,
    event_loop::{ActiveEventLoop, ControlFlow, EventLoop},
    window::{Window, WindowAttributes, WindowLevel},
};

struct App {
    config: OverlayConfig,
    state: OverlayState,
    window: Option<Arc<Window>>,
    renderer: Option<Renderer>,
}

impl App {
    fn new(config: OverlayConfig) -> Self {
        Self {
            config,
            state: OverlayState::default(),
            window: None,
            renderer: None,
        }
    }
}

impl ApplicationHandler for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.window.is_some() {
            return;
        }

        // Create window
        let window_attrs = WindowAttributes::default()
            .with_title(&self.config.title)
            .with_inner_size(winit::dpi::LogicalSize::new(
                self.config.width,
                self.config.height,
            ))
            .with_transparent(true)
            .with_decorations(false)
            .with_window_level(WindowLevel::AlwaysOnTop);

        let window = match event_loop.create_window(window_attrs) {
            Ok(w) => Arc::new(w),
            Err(e) => {
                error!(?e, "Failed to create window");
                event_loop.exit();
                return;
            }
        };

        // Set platform-specific attributes
        if let Err(e) = platform::set_transparent(&window) {
            error!(?e, "Failed to set transparent");
        }
        if let Err(e) = platform::set_always_on_top(&window, true) {
            error!(?e, "Failed to set always-on-top");
        }
        if self.state.click_through {
            if let Err(e) = platform::set_click_through(&window, true) {
                error!(?e, "Failed to set click-through");
            }
        }

        // Create renderer
        let renderer = pollster::block_on(Renderer::new(Arc::clone(&window)));
        match renderer {
            Ok(r) => {
                info!("Renderer initialized");
                self.renderer = Some(r);
            }
            Err(e) => {
                error!(?e, "Failed to create renderer");
                event_loop.exit();
                return;
            }
        }

        self.window = Some(window);
        info!("Overlay window created");
    }

    fn window_event(
        &mut self,
        event_loop: &ActiveEventLoop,
        _window_id: winit::window::WindowId,
        event: WindowEvent,
    ) {
        match event {
            WindowEvent::CloseRequested => {
                event_loop.exit();
            }

            WindowEvent::Resized(physical_size) => {
                if let Some(renderer) = &mut self.renderer {
                    renderer.resize(physical_size);
                }
            }

            WindowEvent::KeyboardInput { event, .. } => {
                // F9 toggles click-through mode
                if event.state.is_pressed() {
                    if let winit::keyboard::PhysicalKey::Code(winit::keyboard::KeyCode::F9) =
                        event.physical_key
                    {
                        self.state.click_through = !self.state.click_through;
                        if let Some(window) = &self.window {
                            if let Err(e) =
                                platform::set_click_through(window, self.state.click_through)
                            {
                                error!(?e, "Failed to toggle click-through");
                            }
                        }
                        info!(click_through = %self.state.click_through, "Toggled click-through mode");
                    }
                }
            }

            WindowEvent::RedrawRequested => {
                if let Some(renderer) = &mut self.renderer {
                    if let Err(e) = renderer.render(self.state.screen_rect.as_ref()) {
                        error!(?e, "Render failed");
                    }
                }
            }

            _ => {}
        }
    }

    fn about_to_wait(&mut self, _event_loop: &ActiveEventLoop) {
        if let Some(window) = &self.window {
            window.request_redraw();
        }
    }
}

fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("itk_overlay=info".parse().unwrap()),
        )
        .init();

    info!("Starting ITK Overlay");

    // Create config
    let config = OverlayConfig::default();

    // Create event loop and app
    let event_loop = EventLoop::new()?;
    event_loop.set_control_flow(ControlFlow::Poll);

    let mut app = App::new(config);
    event_loop.run_app(&mut app)?;

    Ok(())
}
