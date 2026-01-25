//! Time simulation for economic agents.
//!
//! This module provides simulation clock and time-based event tracking
//! for connecting agent cycles to calendar time.

mod clock;
mod events;

pub use clock::{SimulationClock, TimeStats, TimeUnit};
pub use events::{TimeBasedEvent, TimeTracker, UpcomingEvent};
