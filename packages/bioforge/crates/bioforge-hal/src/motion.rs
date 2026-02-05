//! XY gantry stepper control.

use async_trait::async_trait;
use bioforge_types::error::BioForgeError;

/// Current gantry position.
#[derive(Debug, Clone, Copy)]
pub struct Position {
    pub x_mm: f64,
    pub y_mm: f64,
    pub z_mm: f64,
}

/// Trait for motion control hardware.
#[async_trait]
pub trait MotionController: Send + Sync {
    /// Move to an absolute position within enclosure bounds.
    async fn move_to(
        &self,
        x_mm: f64,
        y_mm: f64,
        z_mm: Option<f64>,
    ) -> Result<Position, BioForgeError>;

    /// Home all axes.
    async fn home(&self) -> Result<Position, BioForgeError>;

    /// Get current position.
    async fn position(&self) -> Result<Position, BioForgeError>;
}

/// Mock motion controller for development.
pub struct MockMotionController {
    pos: std::sync::Mutex<Position>,
}

impl MockMotionController {
    pub fn new() -> Self {
        Self {
            pos: std::sync::Mutex::new(Position {
                x_mm: 0.0,
                y_mm: 0.0,
                z_mm: 0.0,
            }),
        }
    }

    fn lock_pos(&self) -> Result<std::sync::MutexGuard<'_, Position>, BioForgeError> {
        self.pos.lock().map_err(|e| {
            BioForgeError::HardwareFault(format!("motion controller mutex poisoned: {e}"))
        })
    }
}

impl Default for MockMotionController {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl MotionController for MockMotionController {
    async fn move_to(
        &self,
        x_mm: f64,
        y_mm: f64,
        z_mm: Option<f64>,
    ) -> Result<Position, BioForgeError> {
        let new_pos = Position {
            x_mm,
            y_mm,
            z_mm: z_mm.unwrap_or(0.0),
        };
        tracing::info!(?new_pos, "mock: move to");
        *self.lock_pos()? = new_pos;
        Ok(new_pos)
    }

    async fn home(&self) -> Result<Position, BioForgeError> {
        let home = Position {
            x_mm: 0.0,
            y_mm: 0.0,
            z_mm: 0.0,
        };
        *self.lock_pos()? = home;
        Ok(home)
    }

    async fn position(&self) -> Result<Position, BioForgeError> {
        Ok(*self.lock_pos()?)
    }
}
