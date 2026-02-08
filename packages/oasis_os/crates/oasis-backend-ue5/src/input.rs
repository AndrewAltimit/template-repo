//! FFI input backend.
//!
//! Queues `InputEvent`s pushed from the FFI layer and delivers them
//! when polled by the core framework.

use oasis_core::backend::InputBackend;
use oasis_core::input::InputEvent;

/// Input backend driven by FFI event pushes.
///
/// The FFI layer converts C-ABI `OasisInputEvent` structs into Rust
/// `InputEvent` values and pushes them here. The core framework polls
/// via `InputBackend::poll_events()`.
pub struct FfiInputBackend {
    events: Vec<InputEvent>,
}

impl FfiInputBackend {
    pub fn new() -> Self {
        Self { events: Vec::new() }
    }

    /// Push an input event into the queue (called from FFI layer).
    pub fn push_event(&mut self, event: InputEvent) {
        self.events.push(event);
    }

    /// Number of queued events.
    pub fn pending_count(&self) -> usize {
        self.events.len()
    }
}

impl Default for FfiInputBackend {
    fn default() -> Self {
        Self::new()
    }
}

impl InputBackend for FfiInputBackend {
    fn poll_events(&mut self) -> Vec<InputEvent> {
        std::mem::take(&mut self.events)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use oasis_core::input::Button;

    #[test]
    fn empty_by_default() {
        let mut backend = FfiInputBackend::new();
        assert!(backend.poll_events().is_empty());
    }

    #[test]
    fn push_and_poll() {
        let mut backend = FfiInputBackend::new();
        backend.push_event(InputEvent::ButtonPress(Button::Confirm));
        backend.push_event(InputEvent::TextInput('A'));
        assert_eq!(backend.pending_count(), 2);

        let events = backend.poll_events();
        assert_eq!(events.len(), 2);
        assert_eq!(events[0], InputEvent::ButtonPress(Button::Confirm));
        assert_eq!(events[1], InputEvent::TextInput('A'));

        // Queue is drained after poll.
        assert!(backend.poll_events().is_empty());
    }

    #[test]
    fn default_constructor() {
        let _backend = FfiInputBackend::default();
    }
}
