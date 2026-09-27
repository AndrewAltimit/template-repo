//! Colony counting and plate analysis pipeline.
//!
//! Processes plate images captured by the Pi Camera to count colonies,
//! measure size distributions, and compare experimental vs control plates.
//!
//! **No real image analysis is implemented yet.** [`ColonyCounter::count`]
//! runs a mock pipeline: it ignores the pixels and reports a count that is
//! either injected per image path with [`ColonyCounter::with_mock_count`] or
//! [`PLACEHOLDER_COLONY_COUNT`]. Every result carries `simulated: true`.

use std::collections::HashMap;

use bioforge_types::error::BioForgeError;

/// Count reported by the mock pipeline for images with no injected count.
pub const PLACEHOLDER_COLONY_COUNT: u32 = 42;

/// Mean colony diameter reported by the mock pipeline, in pixels.
const MOCK_MEAN_DIAMETER_PX: f64 = 15.3;

/// Default minimum blob area (pixels).
const DEFAULT_MIN_AREA_PX: u32 = 50;
/// Default maximum blob area (pixels).
const DEFAULT_MAX_AREA_PX: u32 = 5000;

/// Result of colony counting on a single plate image.
#[derive(Debug, Clone)]
pub struct ColonyAnalysis {
    pub colony_count: u32,
    pub mean_diameter_px: f64,
    pub size_distribution: Vec<f64>,
    pub coordinates: Vec<(u32, u32)>,
    /// `true` when the result came from the mock pipeline rather than from
    /// the image. Currently always `true`.
    pub simulated: bool,
}

/// Plate comparison result.
#[derive(Debug, Clone)]
pub struct PlateComparison {
    pub control_count: u32,
    pub experimental_count: u32,
    pub transformation_efficiency: f64,
}

/// Colony counting pipeline.
#[derive(Debug)]
pub struct ColonyCounter {
    /// Minimum blob area in pixels to count as a colony.
    min_area_px: u32,
    /// Maximum blob area in pixels (filter out artifacts).
    max_area_px: u32,
    /// Mock counts injected per image path.
    mock_counts: HashMap<String, u32>,
}

impl ColonyCounter {
    /// Create a new colony counter with area thresholds.
    ///
    /// Returns an error if `min_area_px` is zero or `min_area_px >= max_area_px`.
    pub fn new(min_area_px: u32, max_area_px: u32) -> Result<Self, BioForgeError> {
        if min_area_px == 0 {
            return Err(BioForgeError::ConfigError(
                "min_area_px must be > 0".to_string(),
            ));
        }
        if min_area_px >= max_area_px {
            return Err(BioForgeError::ConfigError(format!(
                "min_area_px ({min_area_px}) must be less than max_area_px ({max_area_px})"
            )));
        }
        Ok(Self {
            min_area_px,
            max_area_px,
            mock_counts: HashMap::new(),
        })
    }

    /// Inject the count the mock pipeline reports for `image_path`.
    pub fn with_mock_count(mut self, image_path: &str, count: u32) -> Self {
        self.mock_counts.insert(image_path.to_string(), count);
        self
    }

    /// Count colonies in an image file.
    ///
    /// MOCK: the image is not read. The count is the injected value for this
    /// path, or [`PLACEHOLDER_COLONY_COUNT`]. Coordinates are a synthetic grid
    /// with one entry per reported colony. The real implementation will use
    /// image thresholding, connected component analysis, and size filtering.
    pub fn count(&self, image_path: &str) -> Result<ColonyAnalysis, BioForgeError> {
        let colony_count = self
            .mock_counts
            .get(image_path)
            .copied()
            .unwrap_or(PLACEHOLDER_COLONY_COUNT);
        tracing::info!(
            min_area = self.min_area_px,
            max_area = self.max_area_px,
            colony_count,
            "mock: colony counting (image not analyzed)"
        );
        let coordinates = (0..colony_count)
            .map(|i| (50 + (i % 20) * 40, 50 + (i / 20) * 40))
            .collect();
        Ok(ColonyAnalysis {
            colony_count,
            mean_diameter_px: MOCK_MEAN_DIAMETER_PX,
            size_distribution: vec![MOCK_MEAN_DIAMETER_PX; colony_count as usize],
            coordinates,
            simulated: true,
        })
    }

    /// Compare control and experimental plates.
    ///
    /// Transformation efficiency is `experimental / control`, or `0.0` when
    /// the control plate has no colonies.
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
        // Constructed directly: the defaults satisfy the invariants that
        // `new` enforces (0 < min < max); a test checks this.
        Self {
            min_area_px: DEFAULT_MIN_AREA_PX,
            max_area_px: DEFAULT_MAX_AREA_PX,
            mock_counts: HashMap::new(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_counter_creates_successfully() {
        let counter = ColonyCounter::default();
        assert_eq!(counter.min_area_px, 50);
        assert_eq!(counter.max_area_px, 5000);
    }

    #[test]
    fn default_satisfies_new_invariants() {
        assert!(ColonyCounter::new(DEFAULT_MIN_AREA_PX, DEFAULT_MAX_AREA_PX).is_ok());
    }

    #[test]
    fn valid_area_range() {
        let counter = ColonyCounter::new(10, 100).unwrap();
        assert_eq!(counter.min_area_px, 10);
    }

    #[test]
    fn rejects_inverted_range() {
        let err = ColonyCounter::new(100, 10).unwrap_err();
        assert!(err.to_string().contains("min_area_px"));
    }

    #[test]
    fn rejects_equal_range() {
        let err = ColonyCounter::new(50, 50).unwrap_err();
        assert!(err.to_string().contains("min_area_px"));
    }

    #[test]
    fn rejects_zero_min() {
        let err = ColonyCounter::new(0, 100).unwrap_err();
        assert!(err.to_string().contains("min_area_px must be > 0"));
    }

    #[test]
    fn mock_count_uses_placeholder_and_is_labelled_simulated() {
        let counter = ColonyCounter::default();
        let result = counter.count("fake_path.png").unwrap();
        assert_eq!(result.colony_count, PLACEHOLDER_COLONY_COUNT);
        assert!(result.simulated);
    }

    #[test]
    fn mock_count_reports_injected_value_consistently() {
        let counter = ColonyCounter::default().with_mock_count("plate.png", 7);
        let result = counter.count("plate.png").unwrap();
        assert_eq!(result.colony_count, 7);
        assert_eq!(result.coordinates.len(), 7);
        assert_eq!(result.size_distribution.len(), 7);
        assert!(result.simulated);
    }

    /// MOCK: exercises the efficiency arithmetic with injected counts. It
    /// says nothing about the accuracy of real colony counting.
    #[test]
    fn mock_transformation_efficiency_is_experimental_over_control() {
        let counter = ColonyCounter::default()
            .with_mock_count("ctrl.png", 200)
            .with_mock_count("exp.png", 50);
        let result = counter.compare("ctrl.png", "exp.png").unwrap();
        assert_eq!(result.control_count, 200);
        assert_eq!(result.experimental_count, 50);
        assert!((result.transformation_efficiency - 0.25).abs() < f64::EPSILON);

        // Order matters: swapping plates inverts the ratio.
        let swapped = counter.compare("exp.png", "ctrl.png").unwrap();
        assert!((swapped.transformation_efficiency - 4.0).abs() < f64::EPSILON);
    }

    /// MOCK: an empty control plate yields 0.0 rather than dividing by zero.
    #[test]
    fn mock_transformation_efficiency_with_empty_control_is_zero() {
        let counter = ColonyCounter::default()
            .with_mock_count("ctrl.png", 0)
            .with_mock_count("exp.png", 12);
        let result = counter.compare("ctrl.png", "exp.png").unwrap();
        assert_eq!(result.control_count, 0);
        assert_eq!(result.transformation_efficiency, 0.0);
    }
}
