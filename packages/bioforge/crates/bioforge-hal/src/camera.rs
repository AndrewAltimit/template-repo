//! Pi Camera image capture for plate imaging.

use async_trait::async_trait;
use bioforge_types::error::BioForgeError;
use bioforge_types::protocol::LightingMode;

/// Captured image metadata.
#[derive(Debug, Clone)]
pub struct CapturedImage {
    pub image_id: String,
    pub path: String,
    pub width: u32,
    pub height: u32,
    pub lighting_mode: LightingMode,
}

/// Trait for camera hardware.
#[async_trait]
pub trait Camera: Send + Sync {
    /// Capture a plate image with the specified lighting mode.
    async fn capture(
        &self,
        plate_id: &str,
        lighting_mode: LightingMode,
    ) -> Result<CapturedImage, BioForgeError>;
}

/// Mock camera for development.
pub struct MockCamera;

#[async_trait]
impl Camera for MockCamera {
    async fn capture(
        &self,
        plate_id: &str,
        lighting_mode: LightingMode,
    ) -> Result<CapturedImage, BioForgeError> {
        let image_id = format!("{plate_id}_{}", chrono::Utc::now().format("%Y%m%d_%H%M%S"));
        tracing::info!(
            plate_id,
            ?lighting_mode,
            image_id,
            "mock: capture plate image"
        );
        Ok(CapturedImage {
            image_id: image_id.clone(),
            path: format!("/tmp/bioforge/images/{image_id}.png"),
            width: 4608,
            height: 2592,
            lighting_mode,
        })
    }
}
