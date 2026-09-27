//! Pure sensor decision logic, kept free of `rppal` I/O so it compiles and is
//! unit tested on any host (the hardware loop in `sensor.rs` is aarch64-only).

use tamper_common::{Confidence, EventType};

/// Consecutive failed BH1750 reads tolerated before the light sensor is
/// treated as disabled. At the default 250 ms poll interval this is 2 s, long
/// enough to ride out a transient I2C glitch.
pub const MAX_CONSECUTIVE_LIGHT_FAILURES: u32 = 8;

/// Classify one poll into the event to emit, if any.
///
/// `lux` is `None` when the light sensor read failed. An unknown light level
/// never produces a `LightAnomaly` (there is no reading to compare) and caps a
/// lid-open event at `Medium` confidence (Hall alone). Loss of the light
/// sensor is escalated separately through [`LightHealth`], not by pretending
/// the reading was dark.
pub fn classify(
    prev_closed: bool,
    lid_closed: bool,
    lux: Option<f64>,
    threshold_lux: f64,
) -> Option<(EventType, Confidence)> {
    let bright = lux.is_some_and(|l| l > threshold_lux);
    if prev_closed && !lid_closed {
        let confidence = if bright {
            Confidence::High
        } else {
            Confidence::Medium
        };
        Some((EventType::LidOpened, confidence))
    } else if !prev_closed && lid_closed {
        Some((EventType::LidClosed, Confidence::High))
    } else if lid_closed && bright {
        Some((EventType::LightAnomaly, Confidence::Anomaly))
    } else {
        None
    }
}

/// Tracks light-sensor health across polls.
///
/// A heartbeat tells the gate "both sensors are live". Once the light sensor
/// has failed [`MAX_CONSECUTIVE_LIGHT_FAILURES`] times in a row, the daemon
/// stops sending heartbeats so the gate's watchdog fires: while armed that is
/// treated as tamper (challenge, then wipe on failure). This is the
/// fail-closed response to an attacker disconnecting the BH1750 to defeat
/// Hall-spoof detection. Hall edge events are still emitted meanwhile.
#[derive(Debug, Default)]
pub struct LightHealth {
    consecutive_failures: u32,
}

impl LightHealth {
    /// Record the outcome of one read. Returns `true` exactly when this read
    /// pushed the sensor into the failed state (for one-shot logging).
    pub fn record(&mut self, read_ok: bool) -> bool {
        if read_ok {
            self.consecutive_failures = 0;
            false
        } else {
            self.consecutive_failures = self.consecutive_failures.saturating_add(1);
            self.consecutive_failures == MAX_CONSECUTIVE_LIGHT_FAILURES
        }
    }

    /// Whether the daemon may certify liveness with a heartbeat.
    pub fn heartbeat_allowed(&self) -> bool {
        self.consecutive_failures < MAX_CONSECUTIVE_LIGHT_FAILURES
    }

    pub fn consecutive_failures(&self) -> u32 {
        self.consecutive_failures
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const T: f64 = 5.0;

    #[test]
    fn open_edge_confidence_depends_on_light() {
        assert_eq!(
            classify(true, false, Some(50.0), T),
            Some((EventType::LidOpened, Confidence::High))
        );
        assert_eq!(
            classify(true, false, Some(1.0), T),
            Some((EventType::LidOpened, Confidence::Medium))
        );
        // Unknown light: Hall alone is still authoritative.
        assert_eq!(
            classify(true, false, None, T),
            Some((EventType::LidOpened, Confidence::Medium))
        );
    }

    #[test]
    fn close_edge_and_anomaly() {
        assert_eq!(
            classify(false, true, None, T),
            Some((EventType::LidClosed, Confidence::High))
        );
        assert_eq!(
            classify(true, true, Some(50.0), T),
            Some((EventType::LightAnomaly, Confidence::Anomaly))
        );
        assert_eq!(classify(true, true, Some(1.0), T), None);
        // A failed read must not be reported as "dark and fine" via an
        // anomaly check on a sentinel; it simply yields no anomaly here and
        // is escalated through LightHealth instead.
        assert_eq!(classify(true, true, None, T), None);
        assert_eq!(classify(false, false, Some(50.0), T), None);
    }

    #[test]
    fn heartbeats_withheld_after_repeated_light_failures() {
        let mut h = LightHealth::default();
        for i in 1..MAX_CONSECUTIVE_LIGHT_FAILURES {
            assert!(!h.record(false), "failure {i} must not trip yet");
            assert!(h.heartbeat_allowed());
        }
        assert!(h.record(false), "threshold crossing is reported once");
        assert!(!h.heartbeat_allowed());
        assert!(!h.record(false), "only the crossing read reports");
        assert!(!h.heartbeat_allowed());

        // Recovery restores heartbeats.
        assert!(!h.record(true));
        assert!(h.heartbeat_allowed());
        assert_eq!(h.consecutive_failures(), 0);
    }

    #[test]
    fn transient_failure_is_tolerated() {
        let mut h = LightHealth::default();
        h.record(false);
        h.record(true);
        h.record(false);
        assert!(h.heartbeat_allowed());
        assert_eq!(h.consecutive_failures(), 1);
    }
}
