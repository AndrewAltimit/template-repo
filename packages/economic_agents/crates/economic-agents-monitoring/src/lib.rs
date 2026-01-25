//! Event bus, metrics collection, and observability.
//!
//! This crate provides:
//! - Event bus for loose coupling
//! - Decision logging
//! - Metrics collection
//! - Resource tracking
//! - Alignment monitoring

pub mod events;
pub mod decision_logger;
pub mod metrics;
pub mod resource_tracker;
pub mod alignment;

pub use events::{Event, EventBus, EventType};
pub use decision_logger::DecisionLogger;
pub use metrics::MetricsCollector;
pub use resource_tracker::ResourceTracker;
pub use alignment::AlignmentMonitor;
