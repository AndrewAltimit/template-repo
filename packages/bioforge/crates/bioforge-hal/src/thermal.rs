//! PID-controlled thermal management for Peltier modules.

use async_trait::async_trait;
use bioforge_types::error::BioForgeError;
use bioforge_types::protocol::ThermalZone;

/// Thermal zone reading.
#[derive(Debug, Clone)]
pub struct ThermalReading {
    pub zone: ThermalZone,
    pub current_c: f64,
    pub target_c: f64,
    pub stable: bool,
}

/// Trait for thermal control hardware.
#[async_trait]
pub trait ThermalController: Send + Sync {
    /// Set a zone to a target temperature.
    async fn set_temperature(&self, zone: ThermalZone, target_c: f64) -> Result<(), BioForgeError>;

    /// Read current temperature from a zone.
    async fn read_temperature(&self, zone: ThermalZone) -> Result<ThermalReading, BioForgeError>;

    /// Execute a heat shock sequence (atomic operation).
    async fn heat_shock(
        &self,
        ramp_to_c: f64,
        hold_s: u64,
        return_to_c: f64,
    ) -> Result<HeatShockReport, BioForgeError>;
}

/// Report from a completed heat shock sequence.
#[derive(Debug, Clone)]
pub struct HeatShockReport {
    pub actual_hold_s: f64,
    pub peak_temp_c: f64,
    pub min_temp_during_hold_c: f64,
}

/// Mock thermal controller for development.
pub struct MockThermalController;

#[async_trait]
impl ThermalController for MockThermalController {
    async fn set_temperature(&self, zone: ThermalZone, target_c: f64) -> Result<(), BioForgeError> {
        tracing::info!(?zone, target_c, "mock: set temperature");
        Ok(())
    }

    async fn read_temperature(&self, zone: ThermalZone) -> Result<ThermalReading, BioForgeError> {
        let target = match zone {
            ThermalZone::Cold => 4.0,
            ThermalZone::Warm => 37.0,
        };
        Ok(ThermalReading {
            zone,
            current_c: target,
            target_c: target,
            stable: true,
        })
    }

    async fn heat_shock(
        &self,
        ramp_to_c: f64,
        hold_s: u64,
        return_to_c: f64,
    ) -> Result<HeatShockReport, BioForgeError> {
        tracing::info!(ramp_to_c, hold_s, return_to_c, "mock: heat shock");
        Ok(HeatShockReport {
            actual_hold_s: hold_s as f64,
            peak_temp_c: ramp_to_c + 0.3,
            min_temp_during_hold_c: ramp_to_c - 0.3,
        })
    }
}
