//! Colony counting and plate analysis pipeline.
//!
//! Processes plate images captured by the Pi Camera to count colonies,
//! measure size distributions, and compare experimental vs control plates.

use bioforge_types::error::BioForgeError;

/// Result of colony counting on a single plate image.
#[derive(Debug, Clone)]
pub struct ColonyAnalysis {
    pub colony_count: u32,
    pub mean_diameter_px: f64,
    pub size_distribution: Vec<f64>,
    pub coordinates: Vec<(u32, u32)>,
}

/// Plate comparison result.
#[derive(Debug, Clone)]
pub struct PlateComparison {
    pub control_count: u32,
    pub experimental_count: u32,
    pub transformation_efficiency: f64,
}

/// Colony counting pipeline.
pub struct ColonyCounter {
    /// Minimum blob area in pixels to count as a colony.
    min_area_px: u32,
    /// Maximum blob area in pixels (filter out artifacts).
    max_area_px: u32,
}

impl ColonyCounter {
    pub fn new(min_area_px: u32, max_area_px: u32) -> Self {
        Self {
            min_area_px,
            max_area_px,
        }
    }

    /// Count colonies in an image file.
    ///
    /// Currently returns a mock result. Real implementation will use
    /// image thresholding, connected component analysis, and size filtering.
    pub fn count(&self, _image_path: &str) -> Result<ColonyAnalysis, BioForgeError> {
        tracing::info!(
            min_area = self.min_area_px,
            max_area = self.max_area_px,
            "mock: colony counting"
        );
        // Mock result for Phase 1
        Ok(ColonyAnalysis {
            colony_count: 42,
            mean_diameter_px: 15.3,
            size_distribution: vec![8.0, 12.0, 15.0, 18.0, 22.0],
            coordinates: vec![(100, 200), (150, 300), (200, 150)],
        })
    }

    /// Compare control and experimental plates.
    pub fn compare(
        &self,
        control_path: &str,
        experimental_path: &str,
    ) -> Result<PlateComparison, BioForgeError> {
        let control = self.count(control_path)?;
        let experimental = self.count(experimental_path)?;
        let efficiency = if control.colony_count > 0 {
            experimental.colony_count as f64 / control.colony_count as f64
        } else {
            0.0
        };
        Ok(PlateComparison {
            control_count: control.colony_count,
            experimental_count: experimental.colony_count,
            transformation_efficiency: efficiency,
        })
    }
}

impl Default for ColonyCounter {
    fn default() -> Self {
        Self::new(50, 5000)
    }
}
