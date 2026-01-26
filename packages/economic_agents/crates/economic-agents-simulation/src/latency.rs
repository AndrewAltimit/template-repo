//! Network latency simulation.

use rand::Rng;
use std::time::Duration;
use tokio::time::sleep;

/// Simulates network latency for API calls.
pub struct LatencySimulator {
    /// Base latency in milliseconds.
    base_ms: u64,
    /// Maximum additional jitter in milliseconds.
    jitter_ms: u64,
    /// Probability of timeout (0.0-1.0).
    timeout_probability: f64,
    /// Whether simulation is enabled.
    enabled: bool,
}

impl LatencySimulator {
    /// Create a new latency simulator.
    pub fn new(base_ms: u64, jitter_ms: u64) -> Self {
        Self {
            base_ms,
            jitter_ms,
            timeout_probability: 0.02, // 2% timeout rate
            enabled: true,
        }
    }

    /// Disable the simulator.
    pub fn disable(&mut self) {
        self.enabled = false;
    }

    /// Enable the simulator.
    pub fn enable(&mut self) {
        self.enabled = true;
    }

    /// Set timeout probability.
    pub fn with_timeout_probability(mut self, prob: f64) -> Self {
        self.timeout_probability = prob.clamp(0.0, 1.0);
        self
    }

    /// Simulate latency for a simple operation.
    pub async fn simple(&self) -> Result<(), &'static str> {
        if !self.enabled {
            return Ok(());
        }

        let mut rng = rand::thread_rng();

        // Check for timeout
        if rng.r#gen::<f64>() < self.timeout_probability {
            return Err("Operation timed out");
        }

        let delay = self.base_ms + rng.r#gen_range(0..=self.jitter_ms);
        sleep(Duration::from_millis(delay)).await;
        Ok(())
    }

    /// Simulate latency for a complex operation (longer).
    pub async fn complex(&self) -> Result<(), &'static str> {
        if !self.enabled {
            return Ok(());
        }

        let mut rng = rand::thread_rng();

        // Higher timeout probability for complex ops
        if rng.r#gen::<f64>() < self.timeout_probability * 2.0 {
            return Err("Operation timed out");
        }

        let delay = (self.base_ms * 5) + rng.r#gen_range(0..=(self.jitter_ms * 10));
        sleep(Duration::from_millis(delay)).await;
        Ok(())
    }
}

impl Default for LatencySimulator {
    fn default() -> Self {
        Self::new(50, 100) // 50-150ms base latency
    }
}
