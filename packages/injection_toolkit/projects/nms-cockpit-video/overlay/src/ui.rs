//! Video Controls UI
//!
//! egui-based video player controls for the NMS overlay.

use egui::{Align2, Color32, FontId, RichText, Rounding, Stroke, Vec2};

/// Video player controls state
pub struct VideoControls {
    /// URL input text
    url_input: String,
    /// Whether video is playing
    is_playing: bool,
    /// Current position in milliseconds
    position_ms: u64,
    /// Total duration in milliseconds
    duration_ms: u64,
    /// Pending load request
    pending_load: Option<String>,
    /// Pending play request
    pending_play: bool,
    /// Pending pause request
    pending_pause: bool,
    /// Pending seek request (position in ms)
    pending_seek: Option<u64>,
    /// Whether the seek bar is being dragged
    seeking: bool,
    /// Seek position while dragging
    seek_position: f32,
    /// Whether connected to daemon
    daemon_connected: bool,
}

impl VideoControls {
    pub fn new() -> Self {
        Self {
            url_input: String::new(),
            is_playing: false,
            position_ms: 0,
            duration_ms: 0,
            pending_load: None,
            pending_play: false,
            pending_pause: false,
            pending_seek: None,
            seeking: false,
            seek_position: 0.0,
            daemon_connected: false,
        }
    }

    /// Set the current playback position
    pub fn set_position(&mut self, position_ms: u64) {
        if !self.seeking {
            self.position_ms = position_ms;
        }
    }

    /// Set the total duration
    pub fn set_duration(&mut self, duration_ms: u64) {
        self.duration_ms = duration_ms;
    }

    /// Set playing state
    pub fn set_playing(&mut self, playing: bool) {
        self.is_playing = playing;
    }

    /// Set daemon connection status
    pub fn set_daemon_connected(&mut self, connected: bool) {
        self.daemon_connected = connected;
    }

    /// Toggle play/pause
    pub fn toggle_play_pause(&mut self) {
        if self.is_playing {
            self.pending_pause = true;
        } else {
            self.pending_play = true;
        }
    }

    /// Seek relative to current position
    pub fn seek_relative(&mut self, delta_ms: i64) {
        let new_pos = (self.position_ms as i64 + delta_ms).max(0) as u64;
        let clamped = new_pos.min(self.duration_ms);
        self.pending_seek = Some(clamped);
    }

    /// Take pending load request
    pub fn take_load_request(&mut self) -> Option<String> {
        self.pending_load.take()
    }

    /// Take pending play request
    pub fn take_play_request(&mut self) -> bool {
        std::mem::take(&mut self.pending_play)
    }

    /// Take pending pause request
    pub fn take_pause_request(&mut self) -> bool {
        std::mem::take(&mut self.pending_pause)
    }

    /// Take pending seek request
    pub fn take_seek_request(&mut self) -> Option<u64> {
        self.pending_seek.take()
    }

    /// Render the controls UI
    pub fn ui(&mut self, ctx: &egui::Context) {
        // Semi-transparent panel at the bottom
        egui::Area::new(egui::Id::new("video_controls"))
            .anchor(Align2::CENTER_BOTTOM, Vec2::new(0.0, -20.0))
            .show(ctx, |ui| {
                egui::Frame::none()
                    .fill(Color32::from_rgba_unmultiplied(20, 20, 30, 220))
                    .rounding(Rounding::same(8.0))
                    .stroke(Stroke::new(1.0, Color32::from_rgb(60, 60, 80)))
                    .inner_margin(16.0)
                    .show(ui, |ui| {
                        ui.set_min_width(600.0);
                        self.render_controls(ui);
                    });
            });
    }

    fn render_controls(&mut self, ui: &mut egui::Ui) {
        ui.vertical(|ui| {
            // URL input row
            ui.horizontal(|ui| {
                // Connection status dot
                let color = if self.daemon_connected {
                    Color32::from_rgb(80, 200, 80)
                } else {
                    Color32::from_rgb(200, 80, 80)
                };
                let (rect, response) =
                    ui.allocate_exact_size(Vec2::new(10.0, 10.0), egui::Sense::hover());
                ui.painter().circle_filled(rect.center(), 4.0, color);
                response.on_hover_text(if self.daemon_connected {
                    "Connected to daemon"
                } else {
                    "Daemon not connected"
                });
                ui.add_space(4.0);

                ui.label(RichText::new("URL:").color(Color32::WHITE));
                let response = ui.add(
                    egui::TextEdit::singleline(&mut self.url_input)
                        .desired_width(400.0)
                        .hint_text("Enter video URL or file path...")
                        .text_color(Color32::WHITE),
                );

                if ui
                    .button(RichText::new("Load").color(Color32::WHITE))
                    .clicked()
                    || (response.lost_focus()
                        && ui.input(|i| i.key_pressed(egui::Key::Enter)))
                {
                    if !self.url_input.is_empty() {
                        self.pending_load = Some(self.url_input.clone());
                    }
                }
            });

            ui.add_space(8.0);

            // Playback controls row
            ui.horizontal(|ui| {
                // Play/Pause button
                let play_pause_text = if self.is_playing { "||" } else { ">" };
                if ui
                    .button(
                        RichText::new(play_pause_text)
                            .font(FontId::proportional(20.0))
                            .color(Color32::WHITE),
                    )
                    .clicked()
                {
                    self.toggle_play_pause();
                }

                ui.add_space(8.0);

                // Time display
                let current_time = format_time(self.position_ms);
                let total_time = format_time(self.duration_ms);
                ui.label(
                    RichText::new(format!("{} / {}", current_time, total_time))
                        .color(Color32::LIGHT_GRAY)
                        .font(FontId::monospace(14.0)),
                );

                ui.add_space(8.0);

                // Seek bar
                let _progress = if self.duration_ms > 0 {
                    if self.seeking {
                        self.seek_position
                    } else {
                        self.position_ms as f32 / self.duration_ms as f32
                    }
                } else {
                    0.0
                };

                let slider_response = ui.add(
                    egui::Slider::new(&mut self.seek_position, 0.0..=1.0)
                        .show_value(false)
                        .trailing_fill(true),
                );

                // Update seek position from actual position when not dragging
                if !self.seeking && self.duration_ms > 0 {
                    self.seek_position = self.position_ms as f32 / self.duration_ms as f32;
                }

                // Handle dragging
                if slider_response.drag_started() {
                    self.seeking = true;
                }
                if slider_response.drag_stopped() {
                    self.seeking = false;
                    let seek_ms = (self.seek_position * self.duration_ms as f32) as u64;
                    self.pending_seek = Some(seek_ms);
                }

                ui.add_space(8.0);

                // Keyboard shortcuts hint
                ui.label(
                    RichText::new("[Space] Play/Pause  [</>] Seek  [F9] Hide")
                        .color(Color32::GRAY)
                        .small(),
                );
            });
        });
    }
}

impl Default for VideoControls {
    fn default() -> Self {
        Self::new()
    }
}

/// Format milliseconds as MM:SS or HH:MM:SS
fn format_time(ms: u64) -> String {
    let total_secs = ms / 1000;
    let hours = total_secs / 3600;
    let mins = (total_secs % 3600) / 60;
    let secs = total_secs % 60;

    if hours > 0 {
        format!("{:02}:{:02}:{:02}", hours, mins, secs)
    } else {
        format!("{:02}:{:02}", mins, secs)
    }
}
