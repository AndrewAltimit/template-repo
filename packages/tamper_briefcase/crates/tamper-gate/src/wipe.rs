//! Wipe authorization with a fail-closed fallback chain.
//!
//! The designed path is: write the trigger file, then `systemctl start
//! tamper-wipe.service` (whose `ConditionPathExists=` requires that file).
//! Every step is checked. If a step fails the gate escalates instead of
//! carrying on as if the wipe had started:
//!
//! 1. Write the trigger file (retried). Without it neither the unit nor the
//!    script will run, so a persistent failure skips straight to step 4.
//! 2. `systemctl start tamper-wipe.service` (retried with backoff). Spawn
//!    errors and non-zero exit statuses both count as failure.
//! 3. Run the wipe script directly. It re-checks the trigger file itself, and
//!    the gate's sandbox (`ProtectSystem=strict`) still leaves `/dev` writable.
//! 4. Force an immediate power-off. This does not destroy the LUKS header, but
//!    it drops the volume keys from RAM so the data partition is locked at
//!    rest; the device never stays up unlocked after a failed challenge.
//!
//! All I/O goes through [`WipeBackend`] so the chain is unit testable.

use std::io;

/// Attempts for each retried step (trigger write, unit start).
pub const MAX_ATTEMPTS: u32 = 3;

/// Side effects needed to authorize a wipe.
pub trait WipeBackend {
    /// Create the trigger file with the given JSON payload.
    fn write_trigger(&mut self, payload: &str) -> io::Result<()>;
    /// `systemctl start tamper-wipe.service`; `Err` on spawn failure or a
    /// non-success exit status.
    fn start_wipe_unit(&mut self) -> Result<(), String>;
    /// Run the wipe script directly (fallback).
    fn run_wipe_script(&mut self) -> Result<(), String>;
    /// Last resort: power off immediately. Normally does not return.
    fn force_poweroff(&mut self) -> Result<(), String>;
    /// Pause before retry number `attempt` (1-based).
    fn backoff(&mut self, attempt: u32);
}

/// How far down the fallback chain the gate had to go.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WipeOutcome {
    /// The wipe unit was started successfully.
    UnitStarted,
    /// The unit could not be started; the script was run directly.
    ScriptRanDirectly,
    /// Neither wipe path worked; a forced power-off was issued.
    PoweredOff,
    /// Every fallback failed. The caller must keep retrying and must never
    /// resume normal monitoring.
    AllFallbacksFailed,
}

impl WipeOutcome {
    /// Whether an actual wipe (not merely a power-off) was started.
    pub fn wipe_started(&self) -> bool {
        matches!(self, Self::UnitStarted | Self::ScriptRanDirectly)
    }
}

/// Authorize the wipe, escalating through the fallback chain on failure.
pub fn authorize_wipe(
    backend: &mut impl WipeBackend,
    reason: &str,
    authorized_at: &str,
) -> WipeOutcome {
    log::error!("=== WIPE AUTHORIZED (reason: {}) ===", reason);

    let payload = serde_json::json!({
        "authorized_at": authorized_at,
        "reason": "challenge_failed",
        "trigger": reason,
    })
    .to_string();

    let mut trigger_written = false;
    for attempt in 1..=MAX_ATTEMPTS {
        match backend.write_trigger(&payload) {
            Ok(()) => {
                trigger_written = true;
                break;
            },
            Err(e) => {
                log::error!(
                    "WIPE: failed to write trigger file (attempt {}/{}): {}",
                    attempt,
                    MAX_ATTEMPTS,
                    e
                );
                if attempt < MAX_ATTEMPTS {
                    backend.backoff(attempt);
                }
            },
        }
    }

    if trigger_written {
        for attempt in 1..=MAX_ATTEMPTS {
            match backend.start_wipe_unit() {
                Ok(()) => {
                    log::error!("WIPE: tamper-wipe.service started");
                    return WipeOutcome::UnitStarted;
                },
                Err(e) => {
                    log::error!(
                        "WIPE: failed to start tamper-wipe.service (attempt {}/{}): {}",
                        attempt,
                        MAX_ATTEMPTS,
                        e
                    );
                    if attempt < MAX_ATTEMPTS {
                        backend.backoff(attempt);
                    }
                },
            }
        }

        log::error!("WIPE: systemd path exhausted; invoking wipe script directly");
        match backend.run_wipe_script() {
            Ok(()) => return WipeOutcome::ScriptRanDirectly,
            Err(e) => log::error!("WIPE: direct wipe script invocation failed: {}", e),
        }
    } else {
        log::error!(
            "WIPE: trigger file could not be written; the wipe unit and script \
             would both refuse to run"
        );
    }

    log::error!("WIPE: all wipe paths failed; forcing power-off to lock the volume");
    match backend.force_poweroff() {
        Ok(()) => WipeOutcome::PoweredOff,
        Err(e) => {
            log::error!("WIPE: forced power-off failed: {}", e);
            WipeOutcome::AllFallbacksFailed
        },
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;

    /// Scripted backend: each step fails a configurable number of times.
    #[derive(Default)]
    pub(crate) struct MockBackend {
        pub trigger_failures: u32,
        pub unit_failures: u32,
        pub script_fails: bool,
        pub poweroff_fails: bool,
        pub calls: Vec<&'static str>,
        pub payload: Option<String>,
    }

    impl WipeBackend for MockBackend {
        fn write_trigger(&mut self, payload: &str) -> io::Result<()> {
            self.calls.push("trigger");
            if self.trigger_failures > 0 {
                self.trigger_failures -= 1;
                return Err(io::Error::other("read-only fs"));
            }
            self.payload = Some(payload.to_string());
            Ok(())
        }
        fn start_wipe_unit(&mut self) -> Result<(), String> {
            self.calls.push("unit");
            if self.unit_failures > 0 {
                self.unit_failures -= 1;
                return Err("exit status: 1".into());
            }
            Ok(())
        }
        fn run_wipe_script(&mut self) -> Result<(), String> {
            self.calls.push("script");
            if self.script_fails {
                Err("exit status: 1".into())
            } else {
                Ok(())
            }
        }
        fn force_poweroff(&mut self) -> Result<(), String> {
            self.calls.push("poweroff");
            if self.poweroff_fails {
                Err("EPERM".into())
            } else {
                Ok(())
            }
        }
        fn backoff(&mut self, _attempt: u32) {
            self.calls.push("backoff");
        }
    }

    #[test]
    fn happy_path_writes_trigger_then_starts_unit() {
        let mut b = MockBackend::default();
        let out = authorize_wipe(&mut b, "lid_opened", "2026-01-01T00:00:00Z");
        assert_eq!(out, WipeOutcome::UnitStarted);
        assert!(out.wipe_started());
        assert_eq!(b.calls, ["trigger", "unit"]);
        let payload: serde_json::Value = serde_json::from_str(&b.payload.unwrap()).unwrap();
        assert_eq!(payload["trigger"], "lid_opened");
        assert_eq!(payload["reason"], "challenge_failed");
    }

    #[test]
    fn transient_unit_failure_is_retried() {
        let mut b = MockBackend {
            unit_failures: 1,
            ..Default::default()
        };
        assert_eq!(authorize_wipe(&mut b, "x", "t"), WipeOutcome::UnitStarted);
        assert_eq!(b.calls, ["trigger", "unit", "backoff", "unit"]);
    }

    #[test]
    fn unit_failure_falls_back_to_direct_script() {
        let mut b = MockBackend {
            unit_failures: MAX_ATTEMPTS,
            ..Default::default()
        };
        assert_eq!(
            authorize_wipe(&mut b, "x", "t"),
            WipeOutcome::ScriptRanDirectly
        );
        assert_eq!(b.calls.iter().filter(|c| **c == "unit").count(), 3);
        assert_eq!(b.calls.last(), Some(&"script"));
    }

    #[test]
    fn script_failure_forces_poweroff() {
        let mut b = MockBackend {
            unit_failures: MAX_ATTEMPTS,
            script_fails: true,
            ..Default::default()
        };
        let out = authorize_wipe(&mut b, "x", "t");
        assert_eq!(out, WipeOutcome::PoweredOff);
        assert!(!out.wipe_started());
        assert_eq!(b.calls.last(), Some(&"poweroff"));
    }

    #[test]
    fn trigger_failure_skips_wipe_paths_and_powers_off() {
        let mut b = MockBackend {
            trigger_failures: MAX_ATTEMPTS,
            ..Default::default()
        };
        assert_eq!(authorize_wipe(&mut b, "x", "t"), WipeOutcome::PoweredOff);
        assert!(!b.calls.contains(&"unit"));
        assert!(!b.calls.contains(&"script"));
        assert_eq!(b.calls.iter().filter(|c| **c == "trigger").count(), 3);
    }

    #[test]
    fn transient_trigger_failure_is_retried() {
        let mut b = MockBackend {
            trigger_failures: 2,
            ..Default::default()
        };
        assert_eq!(authorize_wipe(&mut b, "x", "t"), WipeOutcome::UnitStarted);
    }

    #[test]
    fn everything_failing_is_reported() {
        let mut b = MockBackend {
            unit_failures: MAX_ATTEMPTS,
            script_fails: true,
            poweroff_fails: true,
            ..Default::default()
        };
        assert_eq!(
            authorize_wipe(&mut b, "x", "t"),
            WipeOutcome::AllFallbacksFailed
        );
    }
}
