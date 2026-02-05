//! Safety interlocks, audit logging, and rate limiting for BioForge.
//!
//! Enforces defense-in-depth safety constraints at the software layer:
//! - Volume, temperature, and position bounds checking
//! - Rate limiting for actuator commands
//! - Immutable append-only audit log (JSON Lines)
//! - Human-in-the-loop gate enforcement

pub mod audit;
pub mod enforcer;

pub use audit::AuditLog;
pub use enforcer::SafetyEnforcer;
