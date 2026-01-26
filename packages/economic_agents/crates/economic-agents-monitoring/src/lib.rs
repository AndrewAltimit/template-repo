//! Event bus, metrics collection, and observability.
//!
//! This crate provides:
//! - Event bus for loose coupling
//! - Decision logging
//! - Metrics collection
//! - Resource tracking
//! - Alignment monitoring

pub mod alignment;
pub mod decision_logger;
pub mod events;
pub mod metrics;
pub mod resource_tracker;

pub use alignment::AlignmentMonitor;
pub use decision_logger::{DecisionLogger, LoggedDecision};
pub use events::{Event, EventBus, EventType};
pub use metrics::{HistogramStats, MetricsCollector, MetricsSnapshot};
pub use resource_tracker::ResourceTracker;
