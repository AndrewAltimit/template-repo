//! OASIS_OS desktop entry point.
//!
//! Creates an SDL2 window, initializes the SDI scene graph with demo objects,
//! and runs the main loop: clear -> draw -> swap -> poll input -> repeat.

use anyhow::Result;

use oasis_backend_sdl::SdlBackend;
use oasis_core::backend::{Color, InputBackend, SdiBackend};
use oasis_core::config::OasisConfig;
use oasis_core::input::InputEvent;
use oasis_core::sdi::SdiRegistry;

fn main() -> Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let config = OasisConfig::default();
    log::info!(
        "Starting OASIS_OS ({}x{})",
        config.screen_width,
        config.screen_height,
    );

    let mut backend = SdlBackend::new(
        &config.window_title,
        config.screen_width,
        config.screen_height,
    )?;
    backend.init(config.screen_width, config.screen_height)?;

    // Set up demo scene graph objects.
    let mut sdi = SdiRegistry::new();
    setup_demo_scene(&mut sdi);

    // Main loop.
    let bg_color = Color::rgb(20, 20, 30);
    'running: loop {
        // Poll input.
        let events = backend.poll_events();
        for event in &events {
            match event {
                InputEvent::Quit | InputEvent::ButtonPress(oasis_core::input::Button::Cancel) => {
                    break 'running;
                },
                _ => {},
            }
        }

        // Clear.
        backend.clear(bg_color)?;

        // Draw scene graph.
        sdi.draw(&mut backend)?;

        // Present.
        backend.swap_buffers()?;
    }

    backend.shutdown()?;
    log::info!("OASIS_OS shut down cleanly");
    Ok(())
}

/// Create some demo SDI objects to prove the pipeline works.
fn setup_demo_scene(sdi: &mut SdiRegistry) {
    // Status bar background.
    {
        let obj = sdi.create("status_bar");
        obj.x = 0;
        obj.y = 0;
        obj.w = 480;
        obj.h = 24;
        obj.color = Color::rgb(40, 40, 60);
    }

    // Main content area.
    {
        let obj = sdi.create("content_bg");
        obj.x = 10;
        obj.y = 34;
        obj.w = 460;
        obj.h = 228;
        obj.color = Color::rgb(30, 30, 45);
    }

    // Demo "icon" rectangles simulating a dashboard grid.
    let colors = [
        Color::rgb(70, 130, 180),  // Steel blue
        Color::rgb(60, 179, 113),  // Medium sea green
        Color::rgb(218, 165, 32),  // Goldenrod
        Color::rgb(178, 102, 178), // Plum
        Color::rgb(205, 92, 92),   // Indian red
        Color::rgb(100, 149, 237), // Cornflower blue
    ];

    for (i, color) in colors.iter().enumerate() {
        let col = i % 3;
        let row = i / 3;
        let name = format!("icon_{i}");
        let obj = sdi.create(&name);
        obj.x = 30 + (col as i32) * 155;
        obj.y = 50 + (row as i32) * 110;
        obj.w = 130;
        obj.h = 90;
        obj.color = *color;
    }

    // Cursor (drawn on top via highest z-order).
    {
        let obj = sdi.create("cursor");
        obj.x = 240;
        obj.y = 136;
        obj.w = 8;
        obj.h = 8;
        obj.color = Color::WHITE;
    }
}
