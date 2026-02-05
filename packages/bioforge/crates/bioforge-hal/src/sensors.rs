//! Environmental sensor reading (temperature, humidity).

use async_trait::async_trait;
use bioforge_types::error::BioForgeError;

/// Environmental sensor reading.
#[derive(Debug, Clone)]
pub struct EnvironmentReading {
    pub ambient_temp_c: f64,
    pub ambient_humidity_pct: f64,
}

/// Trait for environmental sensors.
#[async_trait]
pub trait SensorReader: Send + Sync {
    /// Read ambient temperature and humidity.
    async fn read_environment(&self) -> Result<EnvironmentReading, BioForgeError>;
}

/// Mock sensor reader for development.
pub struct MockSensorReader;

#[async_trait]
impl SensorReader for MockSensorReader {
    async fn read_environment(&self) -> Result<EnvironmentReading, BioForgeError> {
        Ok(EnvironmentReading {
            ambient_temp_c: 22.5,
            ambient_humidity_pct: 45.0,
        })
    }
}
