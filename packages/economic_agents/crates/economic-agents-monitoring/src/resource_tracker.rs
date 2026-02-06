//! Resource consumption tracking.

use chrono::{DateTime, Utc};
use std::collections::VecDeque;
use std::sync::Arc;
use tokio::sync::RwLock;

/// A resource consumption record.
#[derive(Debug, Clone)]
pub struct ResourceRecord {
    pub resource_type: ResourceType,
    pub amount: f64,
    pub operation: String,
    pub timestamp: DateTime<Utc>,
}

/// Types of resources tracked.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ResourceType {
    ComputeHours,
    Currency,
    ApiCalls,
    LlmTokens,
}

/// Tracks resource consumption over time.
pub struct ResourceTracker {
    records: Arc<RwLock<VecDeque<ResourceRecord>>>,
    max_records: usize,
}

impl ResourceTracker {
    /// Create a new resource tracker.
    pub fn new() -> Self {
        Self {
            records: Arc::new(RwLock::new(VecDeque::new())),
            max_records: 10000,
        }
    }

    /// Record resource consumption.
    pub async fn record(
        &self,
        resource_type: ResourceType,
        amount: f64,
        operation: impl Into<String>,
    ) {
        let record = ResourceRecord {
            resource_type,
            amount,
            operation: operation.into(),
            timestamp: Utc::now(),
        };

        let mut records = self.records.write().await;
        records.push_back(record);
        if records.len() > self.max_records {
            records.pop_front();
        }
    }

    /// Get total consumption for a resource type.
    pub async fn total(&self, resource_type: ResourceType) -> f64 {
        let records = self.records.read().await;
        records
            .iter()
            .filter(|r| r.resource_type == resource_type)
            .map(|r| r.amount)
            .sum()
    }

    /// Get consumption since a timestamp.
    pub async fn since(&self, resource_type: ResourceType, since: DateTime<Utc>) -> f64 {
        let records = self.records.read().await;
        records
            .iter()
            .filter(|r| r.resource_type == resource_type && r.timestamp >= since)
            .map(|r| r.amount)
            .sum()
    }

    /// Get recent records.
    pub async fn recent(&self, count: usize) -> Vec<ResourceRecord> {
        let records = self.records.read().await;
        records.iter().rev().take(count).rev().cloned().collect()
    }
}

impl Default for ResourceTracker {
    fn default() -> Self {
        Self::new()
    }
}
