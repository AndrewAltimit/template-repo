//! Compute resource interface.

use async_trait::async_trait;

use crate::{ComputeStatus, Currency, Hours, Result};

/// Interface for compute resource management.
///
/// Implementations may connect to real cloud providers (AWS, GCP),
/// mock compute tracking, or API-based compute services.
#[async_trait]
pub trait Compute: Send + Sync {
    /// Get current compute status.
    async fn get_status(&self) -> Result<ComputeStatus>;

    /// Add funds/hours to compute account.
    ///
    /// # Arguments
    /// * `amount` - Currency amount to add
    ///
    /// # Returns
    /// New compute status after funding.
    async fn add_funds(&self, amount: Currency) -> Result<ComputeStatus>;

    /// Consume compute time.
    ///
    /// # Arguments
    /// * `hours` - Hours to consume
    ///
    /// # Returns
    /// New compute status after consumption.
    async fn consume_time(&self, hours: Hours) -> Result<ComputeStatus>;

    /// Get the cost per hour.
    async fn get_cost_per_hour(&self) -> Result<Currency>;

    /// Get remaining hours.
    async fn get_hours_remaining(&self) -> Result<Hours>;

    /// Check if compute is available (hours > 0).
    async fn is_available(&self) -> Result<bool> {
        Ok(self.get_hours_remaining().await? > 0.0)
    }
}
