//! Loading and sanity-checking the BioForge configuration files.
//!
//! The server refuses to start on a config that would make the safety
//! enforcer meaningless (inverted ranges, zero rate limits, a safe travel
//! height outside the enclosure, ...). `SafetyEnforcer` itself trusts its
//! limits, so this is the only place such mistakes are caught.

use std::path::Path;

use anyhow::{Context, bail};
use bioforge_safety::enforcer::WorkspaceBounds;
use bioforge_types::config::{HardwareConfig, SafetyLimits};

/// Maximum accepted size of a config file. The real files are ~1 KiB; this
/// only guards against pointing `--config-dir` at something unexpected.
const MAX_CONFIG_BYTES: u64 = 1024 * 1024;

/// Fully loaded and validated configuration.
#[derive(Debug, Clone)]
pub struct LoadedConfig {
    /// Safety limits from `safety_limits.toml`.
    pub limits: SafetyLimits,
    /// Enclosure bounds derived from `hardware.toml`'s `[motion]` table.
    pub bounds: WorkspaceBounds,
}

fn read_capped(path: &Path) -> anyhow::Result<String> {
    let meta =
        std::fs::metadata(path).with_context(|| format!("failed to read {}", path.display()))?;
    if meta.len() > MAX_CONFIG_BYTES {
        bail!(
            "{} is {} bytes; refusing to parse config files larger than {MAX_CONFIG_BYTES} bytes",
            path.display(),
            meta.len()
        );
    }
    std::fs::read_to_string(path).with_context(|| format!("failed to read {}", path.display()))
}

/// Load `safety_limits.toml` and `hardware.toml` from `config_dir` and
/// validate them.
pub fn load_config(config_dir: &Path) -> anyhow::Result<LoadedConfig> {
    let safety_path = config_dir.join("safety_limits.toml");
    let hw_path = config_dir.join("hardware.toml");

    let limits: SafetyLimits = toml::from_str(&read_capped(&safety_path)?)
        .with_context(|| format!("failed to parse {}", safety_path.display()))?;
    let hw: HardwareConfig = toml::from_str(&read_capped(&hw_path)?)
        .with_context(|| format!("failed to parse {}", hw_path.display()))?;

    let bounds = WorkspaceBounds {
        x_max_mm: hw.motion.x_max_mm,
        y_max_mm: hw.motion.y_max_mm,
        z_max_mm: hw.motion.z_max_mm,
    };

    validate_config(&limits, &bounds).with_context(|| {
        format!(
            "invalid configuration in {} / {}",
            safety_path.display(),
            hw_path.display()
        )
    })?;

    Ok(LoadedConfig { limits, bounds })
}

/// Reject configurations that are internally inconsistent.
///
/// Every problem found is reported at once so an operator can fix the file
/// in one pass.
pub fn validate_config(limits: &SafetyLimits, bounds: &WorkspaceBounds) -> anyhow::Result<()> {
    let mut problems: Vec<String> = Vec::new();
    let mut check = |ok: bool, msg: String| {
        if !ok {
            problems.push(msg);
        }
    };

    let all_finite = [
        limits.thermal.absolute_max_c,
        limits.thermal.tool_max_c,
        limits.thermal.tool_min_c,
        limits.thermal.max_overshoot_c,
        limits.volume.max_dispense_ul,
        limits.volume.min_dispense_ul,
        limits.volume.max_total_ml,
        limits.volume.max_flow_rate_ul_s,
        limits.motion.max_speed_mm_s,
        limits.motion.max_accel_mm_s2,
        limits.operations.max_incubation_hours,
        limits.operations.safe_travel_height_mm,
        bounds.x_max_mm,
        bounds.y_max_mm,
        bounds.z_max_mm,
    ]
    .iter()
    .all(|v| v.is_finite());
    check(
        all_finite,
        "all numeric limits must be finite numbers".into(),
    );

    let t = &limits.thermal;
    check(
        t.tool_min_c < t.tool_max_c,
        format!(
            "thermal.tool_min_c ({}) must be < thermal.tool_max_c ({})",
            t.tool_min_c, t.tool_max_c
        ),
    );
    check(
        t.tool_max_c <= t.absolute_max_c,
        format!(
            "thermal.tool_max_c ({}) must be <= thermal.absolute_max_c ({})",
            t.tool_max_c, t.absolute_max_c
        ),
    );
    check(
        t.max_overshoot_c > 0.0,
        format!(
            "thermal.max_overshoot_c ({}) must be > 0",
            t.max_overshoot_c
        ),
    );

    let v = &limits.volume;
    check(
        v.min_dispense_ul > 0.0 && v.min_dispense_ul < v.max_dispense_ul,
        format!(
            "volume.min_dispense_ul ({}) must be > 0 and < volume.max_dispense_ul ({})",
            v.min_dispense_ul, v.max_dispense_ul
        ),
    );
    check(
        v.max_total_ml > 0.0,
        format!("volume.max_total_ml ({}) must be > 0", v.max_total_ml),
    );
    check(
        v.max_flow_rate_ul_s > 0.0,
        format!(
            "volume.max_flow_rate_ul_s ({}) must be > 0",
            v.max_flow_rate_ul_s
        ),
    );

    check(
        limits.rate.max_calls_per_minute > 0,
        "rate.max_calls_per_minute must be > 0 (0 would reject every actuator call)".into(),
    );

    let o = &limits.operations;
    check(
        o.max_incubation_hours > 0.0,
        format!(
            "operations.max_incubation_hours ({}) must be > 0",
            o.max_incubation_hours
        ),
    );
    check(
        o.max_heat_shock_hold_s > 0,
        "operations.max_heat_shock_hold_s must be > 0".into(),
    );
    check(
        o.max_mix_cycles > 0,
        "operations.max_mix_cycles must be > 0".into(),
    );

    check(
        bounds.x_max_mm > 0.0 && bounds.y_max_mm > 0.0 && bounds.z_max_mm > 0.0,
        format!(
            "motion bounds must be positive, got x={} y={} z={}",
            bounds.x_max_mm, bounds.y_max_mm, bounds.z_max_mm
        ),
    );
    check(
        o.safe_travel_height_mm >= 0.0 && o.safe_travel_height_mm <= bounds.z_max_mm,
        format!(
            "operations.safe_travel_height_mm ({}) must lie within [0, z_max_mm={}]",
            o.safe_travel_height_mm, bounds.z_max_mm
        ),
    );

    if problems.is_empty() {
        Ok(())
    } else {
        bail!("{}", problems.join("; "))
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use bioforge_types::config::*;
    use std::path::PathBuf;

    /// Limits used across the crate's tests: generous rate limits so tests
    /// are not throttled, otherwise the shipped defaults.
    pub(crate) fn test_limits() -> SafetyLimits {
        SafetyLimits {
            thermal: ThermalLimits {
                absolute_max_c: 60.0,
                tool_max_c: 50.0,
                tool_min_c: -5.0,
                max_overshoot_c: 1.5,
            },
            volume: VolumeLimits {
                max_dispense_ul: 1000.0,
                min_dispense_ul: 1.0,
                max_total_ml: 50.0,
                max_flow_rate_ul_s: 500.0,
            },
            motion: MotionLimits {
                max_speed_mm_s: 50.0,
                max_accel_mm_s2: 100.0,
            },
            rate: RateLimits {
                max_calls_per_minute: 10_000,
                min_actuator_interval_ms: 0,
            },
            operations: OperationLimits {
                max_incubation_hours: 72.0,
                max_heat_shock_hold_s: 300,
                max_mix_cycles: 20,
                safe_travel_height_mm: 15.0,
            },
        }
    }

    pub(crate) fn test_bounds() -> WorkspaceBounds {
        WorkspaceBounds {
            x_max_mm: 200.0,
            y_max_mm: 150.0,
            z_max_mm: 50.0,
        }
    }

    fn package_config_dir() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../../packages/bioforge/config")
    }

    #[test]
    fn shipped_package_config_loads() {
        let cfg = load_config(&package_config_dir()).expect("shipped config must be valid");
        assert_eq!(cfg.bounds.x_max_mm, 200.0);
        assert_eq!(cfg.limits.operations.max_mix_cycles, 20);
    }

    #[test]
    fn missing_dir_reports_path() {
        let err = load_config(Path::new("definitely/not/here")).unwrap_err();
        assert!(format!("{err:#}").contains("safety_limits.toml"));
    }

    #[test]
    fn test_limits_are_valid() {
        validate_config(&test_limits(), &test_bounds()).unwrap();
    }

    #[test]
    fn rejects_inverted_thermal_range_and_zero_rate() {
        let mut l = test_limits();
        l.thermal.tool_min_c = 60.0;
        l.rate.max_calls_per_minute = 0;
        let err = validate_config(&l, &test_bounds()).unwrap_err().to_string();
        assert!(err.contains("tool_min_c"), "{err}");
        assert!(err.contains("max_calls_per_minute"), "{err}");
    }

    #[test]
    fn rejects_tool_max_above_absolute_max() {
        let mut l = test_limits();
        l.thermal.tool_max_c = 70.0;
        assert!(validate_config(&l, &test_bounds()).is_err());
    }

    #[test]
    fn rejects_safe_height_outside_enclosure() {
        let mut l = test_limits();
        l.operations.safe_travel_height_mm = 80.0;
        let err = validate_config(&l, &test_bounds()).unwrap_err().to_string();
        assert!(err.contains("safe_travel_height_mm"), "{err}");
    }

    #[test]
    fn rejects_nan_limits() {
        let mut l = test_limits();
        l.volume.max_total_ml = f64::NAN;
        assert!(validate_config(&l, &test_bounds()).is_err());
    }

    #[test]
    fn loads_from_temp_dir_and_rejects_bad_toml() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("safety_limits.toml"), "not = [valid").unwrap();
        std::fs::write(dir.path().join("hardware.toml"), "").unwrap();
        let err = format!("{:#}", load_config(dir.path()).unwrap_err());
        assert!(err.contains("failed to parse"), "{err}");
    }
}
