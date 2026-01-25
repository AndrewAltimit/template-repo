//! Factory for creating mock backends.

use crate::{MockCompute, MockMarketplace, MockWallet};

/// Configuration for mock backends.
#[derive(Debug, Clone)]
pub struct MockBackendConfig {
    /// Initial wallet balance.
    pub initial_balance: f64,
    /// Initial compute hours.
    pub initial_compute_hours: f64,
    /// Cost per compute hour.
    pub compute_cost_per_hour: f64,
    /// Number of initial tasks to generate.
    pub initial_tasks: usize,
}

impl Default for MockBackendConfig {
    fn default() -> Self {
        Self {
            initial_balance: 50.0,
            initial_compute_hours: 24.0,
            compute_cost_per_hour: 0.10,
            initial_tasks: 10,
        }
    }
}

/// Container for mock backend components.
pub struct MockBackends {
    pub wallet: MockWallet,
    pub marketplace: MockMarketplace,
    pub compute: MockCompute,
}

/// Factory for creating mock backend instances.
pub struct MockBackendFactory;

impl MockBackendFactory {
    /// Create mock backends with default configuration.
    pub async fn create() -> MockBackends {
        Self::create_with_config(MockBackendConfig::default()).await
    }

    /// Create mock backends with custom configuration.
    pub async fn create_with_config(config: MockBackendConfig) -> MockBackends {
        let wallet = MockWallet::new(config.initial_balance);
        let marketplace = MockMarketplace::new();
        let compute = MockCompute::new(config.initial_compute_hours, config.compute_cost_per_hour);

        // Generate initial tasks
        marketplace.generate_tasks(config.initial_tasks).await;

        MockBackends {
            wallet,
            marketplace,
            compute,
        }
    }
}
