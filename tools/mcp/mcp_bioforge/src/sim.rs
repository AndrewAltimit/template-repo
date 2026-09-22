//! Simulated hardware used when no real drivers are wired in.
//!
//! `bioforge-hal` ships mock drivers for pumps, motion, camera and sensors
//! that are good enough for simulation. Its `MockThermalController`, however,
//! ignores setpoints and always reports 4 C / 37 C, which would make
//! `get_system_status` contradict the temperatures the agent just set.
//! [`SimThermalController`] tracks commanded setpoints instead.

use std::sync::Mutex;

use async_trait::async_trait;
use bioforge_hal::pumps::MockPumpDriver;
use bioforge_hal::sensors::MockSensorReader;
use bioforge_hal::thermal::{HeatShockReport, ThermalController, ThermalReading};
use bioforge_hal::{camera::MockCamera, motion::MockMotionController};
use bioforge_types::error::BioForgeError;
use bioforge_types::protocol::ThermalZone;
use std::sync::Arc;

use crate::lab::Hardware;

/// Temperature a zone reads when it has never been commanded (ambient).
pub const SIM_AMBIENT_C: f64 = 22.5;

/// Thermal controller simulation that remembers each zone's setpoint and
/// reports it back as an already-stable reading.
#[derive(Debug)]
pub struct SimThermalController {
    /// `[cold, warm]` setpoints; `None` means the zone was never commanded.
    setpoints: Mutex<[Option<f64>; 2]>,
}

impl Default for SimThermalController {
    fn default() -> Self {
        Self {
            setpoints: Mutex::new([None, None]),
        }
    }
}

fn idx(zone: ThermalZone) -> usize {
    match zone {
        ThermalZone::Cold => 0,
        ThermalZone::Warm => 1,
    }
}

impl SimThermalController {
    fn with_setpoints<R>(
        &self,
        f: impl FnOnce(&mut [Option<f64>; 2]) -> R,
    ) -> Result<R, BioForgeError> {
        // The critical sections below cannot panic, but never propagate a
        // poisoned lock as a panic either.
        let mut guard = self
            .setpoints
            .lock()
            .map_err(|e| BioForgeError::HardwareFault(format!("thermal sim lock poisoned: {e}")))?;
        Ok(f(&mut guard))
    }
}

#[async_trait]
impl ThermalController for SimThermalController {
    async fn set_temperature(&self, zone: ThermalZone, target_c: f64) -> Result<(), BioForgeError> {
        tracing::info!(?zone, target_c, "sim: set temperature");
        self.with_setpoints(|s| s[idx(zone)] = Some(target_c))
    }

    async fn read_temperature(&self, zone: ThermalZone) -> Result<ThermalReading, BioForgeError> {
        let sp = self.with_setpoints(|s| s[idx(zone)])?;
        let current = sp.unwrap_or(SIM_AMBIENT_C);
        Ok(ThermalReading {
            zone,
            current_c: current,
            target_c: current,
            stable: true,
        })
    }

    async fn heat_shock(
        &self,
        ramp_to_c: f64,
        hold_s: u64,
        return_to_c: f64,
    ) -> Result<HeatShockReport, BioForgeError> {
        tracing::info!(ramp_to_c, hold_s, return_to_c, "sim: heat shock");
        // Heat shock runs in the warm zone and leaves it at `return_to_c`.
        self.with_setpoints(|s| s[idx(ThermalZone::Warm)] = Some(return_to_c))?;
        Ok(HeatShockReport {
            actual_hold_s: hold_s as f64,
            peak_temp_c: ramp_to_c + 0.3,
            min_temp_during_hold_c: ramp_to_c - 0.3,
        })
    }
}

/// Build the fully simulated hardware stack.
pub fn simulated_hardware() -> Hardware {
    Hardware {
        pumps: Arc::new(MockPumpDriver),
        thermal: Arc::new(SimThermalController::default()),
        motion: Arc::new(MockMotionController::new()),
        camera: Arc::new(MockCamera),
        sensors: Arc::new(MockSensorReader),
        simulated: true,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn tracks_setpoints_per_zone() {
        let t = SimThermalController::default();
        assert_eq!(
            t.read_temperature(ThermalZone::Cold)
                .await
                .unwrap()
                .current_c,
            SIM_AMBIENT_C
        );
        t.set_temperature(ThermalZone::Cold, 4.0).await.unwrap();
        t.set_temperature(ThermalZone::Warm, 37.0).await.unwrap();
        assert_eq!(
            t.read_temperature(ThermalZone::Cold)
                .await
                .unwrap()
                .current_c,
            4.0
        );
        assert_eq!(
            t.read_temperature(ThermalZone::Warm)
                .await
                .unwrap()
                .current_c,
            37.0
        );
    }

    #[tokio::test]
    async fn heat_shock_leaves_warm_zone_at_return_temp() {
        let t = SimThermalController::default();
        let r = t.heat_shock(42.0, 45, 4.0).await.unwrap();
        assert_eq!(r.actual_hold_s, 45.0);
        assert_eq!(
            t.read_temperature(ThermalZone::Warm)
                .await
                .unwrap()
                .current_c,
            4.0
        );
    }
}
