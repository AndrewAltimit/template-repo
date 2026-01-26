//! Mock compute implementation.

use async_trait::async_trait;
use economic_agents_interfaces::{
    Compute, ComputeStatus, Currency, EconomicAgentError, Hours, Result,
};
use std::sync::Arc;
use tokio::sync::RwLock;

/// Mock compute resource manager for testing and simulation.
pub struct MockCompute {
    hours_remaining: Arc<RwLock<Hours>>,
    cost_per_hour: Currency,
    total_consumed: Arc<RwLock<Hours>>,
    total_spent: Arc<RwLock<Currency>>,
}

impl MockCompute {
    /// Create a new mock compute with the given initial hours.
    pub fn new(initial_hours: Hours, cost_per_hour: Currency) -> Self {
        Self {
            hours_remaining: Arc::new(RwLock::new(initial_hours)),
            cost_per_hour,
            total_consumed: Arc::new(RwLock::new(0.0)),
            total_spent: Arc::new(RwLock::new(0.0)),
        }
    }
}

#[async_trait]
impl Compute for MockCompute {
    async fn get_status(&self) -> Result<ComputeStatus> {
        Ok(ComputeStatus {
            hours_remaining: *self.hours_remaining.read().await,
            cost_per_hour: self.cost_per_hour,
            total_consumed: *self.total_consumed.read().await,
            total_spent: *self.total_spent.read().await,
            is_active: *self.hours_remaining.read().await > 0.0,
        })
    }

    async fn add_funds(&self, amount: Currency) -> Result<ComputeStatus> {
        let hours_to_add = amount / self.cost_per_hour;
        *self.hours_remaining.write().await += hours_to_add;
        *self.total_spent.write().await += amount;
        self.get_status().await
    }

    async fn consume_time(&self, hours: Hours) -> Result<ComputeStatus> {
        let mut remaining = self.hours_remaining.write().await;

        if *remaining < hours {
            return Err(EconomicAgentError::InsufficientCapital {
                required: hours,
                available: *remaining,
            });
        }

        *remaining -= hours;
        *self.total_consumed.write().await += hours;

        drop(remaining);
        self.get_status().await
    }

    async fn get_cost_per_hour(&self) -> Result<Currency> {
        Ok(self.cost_per_hour)
    }

    async fn get_hours_remaining(&self) -> Result<Hours> {
        Ok(*self.hours_remaining.read().await)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_initial_state() {
        let compute = MockCompute::new(24.0, 0.10);
        let status = compute.get_status().await.unwrap();
        assert_eq!(status.hours_remaining, 24.0);
        assert_eq!(status.cost_per_hour, 0.10);
        assert!(status.is_active);
    }

    #[tokio::test]
    async fn test_consume_time() {
        let compute = MockCompute::new(24.0, 0.10);
        compute.consume_time(10.0).await.unwrap();
        assert_eq!(compute.get_hours_remaining().await.unwrap(), 14.0);
    }

    #[tokio::test]
    async fn test_add_funds() {
        let compute = MockCompute::new(24.0, 0.10);
        compute.add_funds(5.0).await.unwrap(); // Adds 50 hours
        assert_eq!(compute.get_hours_remaining().await.unwrap(), 74.0);
    }

    #[tokio::test]
    async fn test_insufficient_hours() {
        let compute = MockCompute::new(5.0, 0.10);
        let result = compute.consume_time(10.0).await;
        assert!(matches!(
            result,
            Err(EconomicAgentError::InsufficientCapital { .. })
        ));
    }
}
