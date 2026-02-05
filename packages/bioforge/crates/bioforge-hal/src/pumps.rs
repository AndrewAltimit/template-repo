//! Syringe and peristaltic pump drivers.

use async_trait::async_trait;
use bioforge_types::error::BioForgeError;

/// Trait for liquid dispensing hardware.
#[async_trait]
pub trait PumpDriver: Send + Sync {
    /// Dispense a precise volume in microliters.
    async fn dispense(&self, volume_ul: f64, flow_rate: Option<f64>) -> Result<f64, BioForgeError>;

    /// Aspirate a volume in microliters.
    async fn aspirate(&self, volume_ul: f64, flow_rate: Option<f64>) -> Result<f64, BioForgeError>;

    /// Prime the tubing line with a given volume.
    async fn prime(&self, volume_ul: f64) -> Result<(), BioForgeError>;
}

/// Mock pump driver for development and testing.
pub struct MockPumpDriver;

#[async_trait]
impl PumpDriver for MockPumpDriver {
    async fn dispense(
        &self,
        volume_ul: f64,
        _flow_rate: Option<f64>,
    ) -> Result<f64, BioForgeError> {
        tracing::info!(volume_ul, "mock: dispense");
        Ok(volume_ul)
    }

    async fn aspirate(
        &self,
        volume_ul: f64,
        _flow_rate: Option<f64>,
    ) -> Result<f64, BioForgeError> {
        tracing::info!(volume_ul, "mock: aspirate");
        Ok(volume_ul)
    }

    async fn prime(&self, volume_ul: f64) -> Result<(), BioForgeError> {
        tracing::info!(volume_ul, "mock: prime line");
        Ok(())
    }
}
