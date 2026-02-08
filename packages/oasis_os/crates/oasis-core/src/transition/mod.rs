//! Screen transition effects for mode and skin switching.
//!
//! Provides fade, slide, and custom transitions that render as overlays
//! on top of the SDI scene graph. Transitions are frame-based with
//! configurable duration.

use crate::backend::{Color, SdiBackend};
use crate::error::Result;

/// Available transition effects.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TransitionEffect {
    /// No transition -- instant switch.
    None,
    /// Fade from opaque to transparent (reveal).
    FadeIn,
    /// Fade from transparent to opaque (conceal).
    FadeOut,
    /// Slide content in from the right.
    SlideRight,
    /// Slide content in from the left.
    SlideLeft,
    /// PSIX-style horizontal page slide: incoming from left, outgoing to right.
    PageSlideLeft,
    /// PSIX-style horizontal page slide: incoming from right, outgoing to left.
    PageSlideRight,
}

/// Runtime state for an active transition.
#[derive(Debug)]
pub struct TransitionState {
    /// The effect being applied.
    pub effect: TransitionEffect,
    /// Current frame within the transition.
    pub frame: u32,
    /// Total frames for the transition.
    pub duration: u32,
    /// Screen dimensions.
    pub screen_w: u32,
    pub screen_h: u32,
}

impl TransitionState {
    /// Start a new transition.
    pub fn new(effect: TransitionEffect, duration_frames: u32, w: u32, h: u32) -> Self {
        Self {
            effect,
            frame: 0,
            duration: duration_frames,
            screen_w: w,
            screen_h: h,
        }
    }

    /// Progress as a float from 0.0 (start) to 1.0 (complete).
    pub fn progress(&self) -> f32 {
        if self.duration == 0 {
            return 1.0;
        }
        (self.frame as f32 / self.duration as f32).min(1.0)
    }

    /// Whether the transition has finished.
    pub fn is_done(&self) -> bool {
        self.frame >= self.duration
    }

    /// Advance the transition by one frame.
    pub fn tick(&mut self) {
        if self.frame < self.duration {
            self.frame += 1;
        }
    }

    /// For page slide transitions, return the X offset for the incoming page.
    /// Returns 0 when the transition is done or not a slide type.
    pub fn incoming_x_offset(&self) -> i32 {
        if self.is_done() {
            return 0;
        }
        let t = self.progress();
        let w = self.screen_w as f32;
        match self.effect {
            TransitionEffect::PageSlideLeft => {
                // Incoming from left: starts at -480, ends at 0.
                (-(1.0 - t) * w) as i32
            },
            TransitionEffect::PageSlideRight => {
                // Incoming from right: starts at +480, ends at 0.
                ((1.0 - t) * w) as i32
            },
            _ => 0,
        }
    }

    /// For page slide transitions, return the X offset for the outgoing page.
    /// Returns 0 when not a slide type.
    pub fn outgoing_x_offset(&self) -> i32 {
        if self.is_done() {
            return 0;
        }
        let t = self.progress();
        let w = self.screen_w as f32;
        match self.effect {
            TransitionEffect::PageSlideLeft => {
                // Outgoing slides to the right.
                (t * w) as i32
            },
            TransitionEffect::PageSlideRight => {
                // Outgoing slides to the left.
                -(t * w) as i32
            },
            _ => 0,
        }
    }

    /// Draw the transition overlay. Call this after `sdi.draw()` and
    /// before `backend.swap_buffers()`.
    pub fn draw_overlay(&self, backend: &mut dyn SdiBackend) -> Result<()> {
        if self.effect == TransitionEffect::None || self.is_done() {
            return Ok(());
        }

        let t = self.progress();

        match self.effect {
            TransitionEffect::FadeIn => {
                // Black overlay fading from opaque to transparent.
                let alpha = ((1.0 - t) * 255.0) as u8;
                backend.fill_rect(
                    0,
                    0,
                    self.screen_w,
                    self.screen_h,
                    Color::rgba(0, 0, 0, alpha),
                )?;
            },
            TransitionEffect::FadeOut => {
                // Black overlay fading from transparent to opaque.
                let alpha = (t * 255.0) as u8;
                backend.fill_rect(
                    0,
                    0,
                    self.screen_w,
                    self.screen_h,
                    Color::rgba(0, 0, 0, alpha),
                )?;
            },
            TransitionEffect::SlideRight => {
                // Black curtain sliding off to the right.
                let curtain_x = (t * self.screen_w as f32) as i32;
                if curtain_x < self.screen_w as i32 {
                    backend.fill_rect(
                        curtain_x,
                        0,
                        self.screen_w - curtain_x as u32,
                        self.screen_h,
                        Color::rgba(0, 0, 0, 255),
                    )?;
                }
            },
            TransitionEffect::SlideLeft => {
                // Black curtain sliding off to the left.
                let curtain_w = ((1.0 - t) * self.screen_w as f32) as u32;
                if curtain_w > 0 {
                    backend.fill_rect(0, 0, curtain_w, self.screen_h, Color::rgba(0, 0, 0, 255))?;
                }
            },
            TransitionEffect::None
            | TransitionEffect::PageSlideLeft
            | TransitionEffect::PageSlideRight => {},
        }

        Ok(())
    }
}

/// Convenience: start a fade-in transition at the standard duration.
pub fn fade_in(w: u32, h: u32) -> TransitionState {
    TransitionState::new(TransitionEffect::FadeIn, 15, w, h)
}

/// Convenience: start a fade-out transition at the standard duration.
pub fn fade_out(w: u32, h: u32) -> TransitionState {
    TransitionState::new(TransitionEffect::FadeOut, 15, w, h)
}

/// Convenience: PSIX-style page slide from the left.
pub fn page_slide_left(w: u32, h: u32) -> TransitionState {
    TransitionState::new(TransitionEffect::PageSlideLeft, 20, w, h)
}

/// Convenience: PSIX-style page slide from the right.
pub fn page_slide_right(w: u32, h: u32) -> TransitionState {
    TransitionState::new(TransitionEffect::PageSlideRight, 20, w, h)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn progress_starts_at_zero() {
        let ts = TransitionState::new(TransitionEffect::FadeIn, 30, 480, 272);
        assert!((ts.progress() - 0.0).abs() < f32::EPSILON);
        assert!(!ts.is_done());
    }

    #[test]
    fn progress_advances() {
        let mut ts = TransitionState::new(TransitionEffect::FadeIn, 10, 480, 272);
        ts.tick();
        assert!((ts.progress() - 0.1).abs() < 0.01);
        for _ in 0..9 {
            ts.tick();
        }
        assert!((ts.progress() - 1.0).abs() < f32::EPSILON);
        assert!(ts.is_done());
    }

    #[test]
    fn tick_clamps_at_duration() {
        let mut ts = TransitionState::new(TransitionEffect::FadeOut, 5, 480, 272);
        for _ in 0..100 {
            ts.tick();
        }
        assert_eq!(ts.frame, 5);
        assert!(ts.is_done());
    }

    #[test]
    fn zero_duration_is_instant() {
        let ts = TransitionState::new(TransitionEffect::FadeIn, 0, 480, 272);
        assert!((ts.progress() - 1.0).abs() < f32::EPSILON);
        assert!(ts.is_done());
    }

    #[test]
    fn none_effect_always_done_conceptually() {
        let ts = TransitionState::new(TransitionEffect::None, 30, 480, 272);
        // draw_overlay is a no-op for None, but is_done follows frame count.
        assert!(!ts.is_done());
    }

    #[test]
    fn convenience_constructors() {
        let fi = fade_in(480, 272);
        assert_eq!(fi.effect, TransitionEffect::FadeIn);
        assert_eq!(fi.duration, 15);

        let fo = fade_out(480, 272);
        assert_eq!(fo.effect, TransitionEffect::FadeOut);
        assert_eq!(fo.duration, 15);
    }

    #[test]
    fn slide_right_progress() {
        let mut ts = TransitionState::new(TransitionEffect::SlideRight, 10, 480, 272);
        ts.tick();
        ts.tick();
        // At frame 2/10 = 0.2, curtain should start at 0.2 * 480 = 96px.
        let t = ts.progress();
        let curtain_x = (t * 480.0) as i32;
        assert_eq!(curtain_x, 96);
    }

    #[test]
    fn slide_left_progress() {
        let mut ts = TransitionState::new(TransitionEffect::SlideLeft, 10, 480, 272);
        for _ in 0..5 {
            ts.tick();
        }
        // At frame 5/10 = 0.5, curtain width = (1 - 0.5) * 480 = 240px.
        let t = ts.progress();
        let curtain_w = ((1.0 - t) * 480.0) as u32;
        assert_eq!(curtain_w, 240);
    }

    #[test]
    fn page_slide_left_offsets() {
        let mut ts = TransitionState::new(TransitionEffect::PageSlideLeft, 10, 480, 272);
        // At start: incoming at -480, outgoing at 0.
        assert_eq!(ts.incoming_x_offset(), -480);
        assert_eq!(ts.outgoing_x_offset(), 0);

        for _ in 0..5 {
            ts.tick();
        }
        // At midpoint: incoming at -240, outgoing at +240.
        assert_eq!(ts.incoming_x_offset(), -240);
        assert_eq!(ts.outgoing_x_offset(), 240);

        for _ in 0..5 {
            ts.tick();
        }
        // Done: both 0.
        assert_eq!(ts.incoming_x_offset(), 0);
        assert_eq!(ts.outgoing_x_offset(), 0);
    }

    #[test]
    fn page_slide_right_offsets() {
        let mut ts = TransitionState::new(TransitionEffect::PageSlideRight, 10, 480, 272);
        assert_eq!(ts.incoming_x_offset(), 480);
        assert_eq!(ts.outgoing_x_offset(), 0);

        for _ in 0..10 {
            ts.tick();
        }
        assert_eq!(ts.incoming_x_offset(), 0);
        assert_eq!(ts.outgoing_x_offset(), 0);
    }

    #[test]
    fn page_slide_convenience() {
        let ts = page_slide_left(480, 272);
        assert_eq!(ts.effect, TransitionEffect::PageSlideLeft);
        assert_eq!(ts.duration, 20);

        let ts = page_slide_right(480, 272);
        assert_eq!(ts.effect, TransitionEffect::PageSlideRight);
    }
}
