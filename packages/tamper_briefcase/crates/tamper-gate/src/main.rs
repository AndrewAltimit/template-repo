//! Tamper gate orchestrator: manages the arming FSM, password challenge, and
//! wipe authorization.
//!
//! Runs as root with restricted write paths. Reads sensor events from the FIFO
//! produced by `tamper-sensor`. On a confirmed tamper while armed, launches the
//! `tamper-challenge` binary as a subprocess. On challenge failure, creates a
//! trigger file and starts `tamper-wipe.service`, escalating through checked
//! fallbacks if that fails (see `wipe.rs`).
//!
//! The arming FSM is a pure state machine in `fsm.rs`; this file only wires it
//! to the FIFO, the challenge subprocess, and the wipe backend.
//!
//! # Service architecture
//!
//! The split-privilege model ensures:
//! - The sensor daemon (most complex, always-running) has zero write access to
//!   block devices or crypto subsystems.
//! - The wipe can only execute when an explicit trigger file exists.
//! - A bug in sensor code cannot accidentally trigger a wipe.

use std::fs;
use std::io::{BufRead, BufReader};
use std::os::unix::io::AsFd;
use std::path::Path;
use std::process::Command;
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use chrono::Utc;
use nix::poll::{PollFd, PollFlags, PollTimeout, poll};

use tamper_common::{Config, EventType, SystemState, TamperEvent};

mod fsm;
mod wipe;

use fsm::{ChallengeReason, GateFsm, Input, Resolution, Step};
use wipe::{WipeBackend, WipeOutcome};

// ---------------------------------------------------------------------------
// FIFO setup
// ---------------------------------------------------------------------------

/// Create the event FIFO if it does not exist and set permissions so the
/// unprivileged `tamper` user can write to it.
fn ensure_fifo(path: &Path) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).context("Failed to create FIFO directory")?;
    }

    if !path.exists() {
        nix::unistd::mkfifo(path, nix::sys::stat::Mode::from_bits_truncate(0o620))
            .context("Failed to create FIFO")?;
    }

    // Attempt to chown root:tamper. Non-fatal if the group doesn't exist.
    if let Ok(Some(group)) = nix::unistd::Group::from_name("tamper") {
        let _ = nix::unistd::chown(path, Some(nix::unistd::Uid::from_raw(0)), Some(group.gid));
    }

    Ok(())
}

// ---------------------------------------------------------------------------
// Challenge
// ---------------------------------------------------------------------------

/// Launch the password challenge binary. Returns `true` on success (exit 0).
/// Enforces the configured timeout: kills the child if it exceeds the limit.
fn run_challenge(config: &Config) -> bool {
    log::info!(
        "Launching password challenge (timeout={}s)",
        config.challenge_timeout_secs
    );

    let mut child = match Command::new(&config.challenge_binary)
        .stdin(std::process::Stdio::inherit())
        .stdout(std::process::Stdio::inherit())
        .stderr(std::process::Stdio::inherit())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => {
            log::error!("Challenge subprocess error: {}", e);
            return false;
        },
    };

    let timeout = std::time::Duration::from_secs(config.challenge_timeout_secs);
    let deadline = Instant::now() + timeout;

    // Poll the child with short sleeps to enforce the timeout.
    loop {
        match child.try_wait() {
            Ok(Some(status)) => {
                if status.success() {
                    log::info!("Challenge PASSED");
                    return true;
                } else {
                    log::error!("Challenge FAILED (exit code: {:?})", status.code());
                    return false;
                }
            },
            Ok(None) => {
                if Instant::now() >= deadline {
                    log::error!(
                        "Challenge TIMEOUT after {}s; killing child",
                        config.challenge_timeout_secs
                    );
                    let _ = child.kill();
                    let _ = child.wait();
                    return false;
                }
                std::thread::sleep(std::time::Duration::from_millis(100));
            },
            Err(e) => {
                log::error!("Error waiting for challenge process: {}", e);
                let _ = child.kill();
                let _ = child.wait();
                return false;
            },
        }
    }
}

// ---------------------------------------------------------------------------
// Wipe authorization (real backend)
// ---------------------------------------------------------------------------

/// Production [`WipeBackend`]: trigger file, systemd, direct script, power-off.
struct SystemWipeBackend<'a> {
    config: &'a Config,
}

/// Run a command to completion, mapping spawn errors and non-zero exits to
/// `Err` so no failure can be silently discarded.
fn run_checked(cmd: &mut Command) -> Result<(), String> {
    match cmd.status() {
        Ok(status) if status.success() => Ok(()),
        Ok(status) => Err(format!("{:?} exited with {}", cmd, status)),
        Err(e) => Err(format!("failed to spawn {:?}: {}", cmd, e)),
    }
}

impl WipeBackend for SystemWipeBackend<'_> {
    fn write_trigger(&mut self, payload: &str) -> std::io::Result<()> {
        fs::write(&self.config.wipe_trigger_file, payload)
    }

    fn start_wipe_unit(&mut self) -> Result<(), String> {
        run_checked(Command::new("systemctl").args(["start", "tamper-wipe.service"]))
    }

    fn run_wipe_script(&mut self) -> Result<(), String> {
        run_checked(&mut Command::new(&self.config.wipe_script))
    }

    fn force_poweroff(&mut self) -> Result<(), String> {
        nix::unistd::sync();
        let systemctl_err =
            match run_checked(Command::new("systemctl").args(["poweroff", "--force", "--force"])) {
                Ok(()) => return Ok(()),
                Err(e) => e,
            };
        log::error!("WIPE: {}; falling back to reboot(2)", systemctl_err);
        // reboot(2) only returns on failure.
        match nix::sys::reboot::reboot(nix::sys::reboot::RebootMode::RB_POWER_OFF) {
            Ok(never) => match never {},
            Err(e) => Err(format!("{systemctl_err}; reboot(RB_POWER_OFF) failed: {e}")),
        }
    }

    fn backoff(&mut self, attempt: u32) {
        std::thread::sleep(Duration::from_millis(500 * u64::from(attempt)));
    }
}

// ---------------------------------------------------------------------------
// Orchestration (FSM + side effects)
// ---------------------------------------------------------------------------

/// Side effects the orchestrator needs, injectable for tests.
trait GateIo {
    fn run_challenge(&mut self) -> bool;
    fn authorize_wipe(&mut self, reason: ChallengeReason) -> WipeOutcome;
}

struct SystemIo<'a> {
    config: &'a Config,
}

impl GateIo for SystemIo<'_> {
    fn run_challenge(&mut self) -> bool {
        run_challenge(self.config)
    }

    fn authorize_wipe(&mut self, reason: ChallengeReason) -> WipeOutcome {
        let mut backend = SystemWipeBackend {
            config: self.config,
        };
        wipe::authorize_wipe(&mut backend, reason.as_str(), &Utc::now().to_rfc3339())
    }
}

/// Result of dispatching one input.
#[derive(Debug, PartialEq, Eq)]
enum Control {
    /// Keep monitoring.
    Continue,
    /// A challenge failed and the wipe was authorized. Monitoring must not
    /// resume; the caller enters [`hold_wiping`].
    Wiping(ChallengeReason, WipeOutcome),
}

/// Feed one input to the FSM and perform any challenge/wipe it demands.
fn dispatch(fsm: &mut GateFsm, input: Input, now: Instant, io: &mut impl GateIo) -> Control {
    let prev = fsm.state();
    let step = fsm.handle(input, now);
    if fsm.state() != prev {
        log::info!("State: {} -> {}", prev, fsm.state());
    }
    if input == Input::Event(EventType::LightAnomaly) && fsm.state() == SystemState::Armed {
        log::warn!("Light anomaly #{} while armed", fsm.anomaly_counter());
    }

    let Step::Challenge(reason) = step else {
        return Control::Continue;
    };

    log::warn!("TAMPER ({}): launching password challenge", reason.as_str());
    let passed = io.run_challenge();
    match fsm.resolve_challenge(reason, passed) {
        Resolution::Disarmed => {
            log::info!("Challenge PASSED; disarming");
            Control::Continue
        },
        Resolution::AuthorizeWipe(reason) => {
            log::error!("Challenge FAILED; authorizing wipe");
            let outcome = io.authorize_wipe(reason);
            Control::Wiping(reason, outcome)
        },
    }
}

/// Never return to monitoring after a failed challenge. Exiting would let
/// systemd restart the gate in `Disarmed`, which is fail-open. Instead keep
/// re-driving the wipe chain until the machine goes down.
fn hold_wiping(io: &mut impl GateIo, reason: ChallengeReason, first: WipeOutcome) -> ! {
    let mut outcome = first;
    loop {
        let wait = if outcome.wipe_started() {
            // The wipe script powers off when done; give it time.
            Duration::from_secs(60)
        } else {
            Duration::from_secs(5)
        };
        log::error!(
            "WIPING: last outcome {:?}; re-driving wipe in {}s if still running",
            outcome,
            wait.as_secs()
        );
        std::thread::sleep(wait);
        outcome = io.authorize_wipe(reason);
    }
}

// ---------------------------------------------------------------------------
// Main loop
// ---------------------------------------------------------------------------

fn main() -> Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let config = Config::load(Path::new(Config::DEFAULT_PATH));

    log::info!("Tamper gate orchestrator starting");

    ensure_fifo(&config.event_fifo)?;

    let mut io = SystemIo { config: &config };
    let mut fsm = GateFsm::new(
        Duration::from_secs(config.arming_delay_secs),
        config.anomaly_escalation_count,
    );
    let heartbeat_timeout = Duration::from_secs(config.heartbeat_timeout_secs);
    let mut last_heartbeat = Instant::now();

    log::info!("State: {}", fsm.state());
    log::info!("Heartbeat timeout: {}s", config.heartbeat_timeout_secs);

    // Open FIFO for reading (blocks until sensor daemon opens write end).
    log::info!(
        "Waiting for sensor daemon on {}...",
        config.event_fifo.display()
    );
    let fifo = fs::File::open(&config.event_fifo).context("Failed to open event FIFO")?;
    let mut reader = BufReader::new(fifo);
    log::info!("Sensor daemon connected.");

    let mut line_buf = String::new();

    loop {
        // The watchdog deadline is measured from the last *valid* sensor
        // event, not from the last poll, so a stream of malformed lines cannot
        // keep postponing it.
        let remaining = heartbeat_timeout.saturating_sub(last_heartbeat.elapsed());

        // Lines already buffered by BufReader are invisible to poll(2), so
        // only poll once the buffer is drained.
        let has_data = if reader.buffer().is_empty() {
            let ms = i32::try_from(remaining.as_millis()).unwrap_or(i32::MAX);
            let timeout = PollTimeout::try_from(ms).unwrap_or(PollTimeout::MAX);
            let mut poll_fds = [PollFd::new(reader.get_ref().as_fd(), PollFlags::POLLIN)];
            poll(&mut poll_fds, timeout).context("poll() failed on FIFO")? > 0
        } else {
            true
        };

        let input = if !has_data {
            let silence_secs = last_heartbeat.elapsed().as_secs();
            if fsm.state() == SystemState::Armed {
                log::error!(
                    "WATCHDOG: No valid sensor event for {}s while ARMED; sensor may be compromised",
                    silence_secs,
                );
            } else {
                log::warn!(
                    "No heartbeat for {}s (state={}); sensor may be offline",
                    silence_secs,
                    fsm.state(),
                );
            }
            // Restart the window so the watchdog fires once per period (and a
            // passed challenge gets a fresh window).
            last_heartbeat = Instant::now();
            Input::WatchdogTimeout
        } else {
            line_buf.clear();
            let bytes_read = reader.read_line(&mut line_buf).context("FIFO read error")?;

            if bytes_read == 0 {
                log::warn!("FIFO closed: sensor daemon disconnected");
                if let Control::Wiping(reason, outcome) =
                    dispatch(&mut fsm, Input::SensorDisconnected, Instant::now(), &mut io)
                {
                    hold_wiping(&mut io, reason, outcome);
                }
                // Do NOT exit the loop. Exiting would return Ok(()) (exit code
                // 0), and systemd's `Restart=on-failure` would NOT restart the
                // gate, leaving the briefcase permanently unmonitored. Instead,
                // re-open the FIFO and keep watching. The open blocks until the
                // sensor daemon (Restart=always) reconnects its write end.
                log::info!("Re-opening event FIFO, waiting for sensor daemon to reconnect...");
                let fifo =
                    fs::File::open(&config.event_fifo).context("Failed to re-open event FIFO")?;
                reader = BufReader::new(fifo);
                last_heartbeat = Instant::now();
                log::info!("Sensor daemon reconnected.");
                continue;
            }

            let line = line_buf.trim();
            if line.is_empty() {
                continue;
            }

            let event: TamperEvent = match serde_json::from_str(line) {
                Ok(e) => e,
                Err(e) => {
                    log::warn!("Malformed event: {} ({})", line, e);
                    continue;
                },
            };

            // Reset the watchdog on any valid event from the sensor.
            last_heartbeat = Instant::now();

            if event.event_type == EventType::Heartbeat {
                log::debug!("Heartbeat received (lux={:?})", event.lux);
            } else {
                log::info!(
                    "Event: {} (lux={:?}, confidence={}, state={})",
                    event.event_type,
                    event.lux,
                    event.confidence,
                    fsm.state(),
                );
            }
            Input::Event(event.event_type)
        };

        if let Control::Wiping(reason, outcome) = dispatch(&mut fsm, input, Instant::now(), &mut io)
        {
            hold_wiping(&mut io, reason, outcome);
        }
    }
    // The loop only exits by propagating an I/O error with `?`; the wipe path
    // diverges in `hold_wiping`, so there is no trailing `Ok(())`.
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    /// Records challenge/wipe calls; the challenge result is scripted.
    struct MockIo {
        challenge_passes: bool,
        wipe_outcome: WipeOutcome,
        challenges: u32,
        wipes: Vec<ChallengeReason>,
    }

    impl MockIo {
        fn new(challenge_passes: bool) -> Self {
            Self {
                challenge_passes,
                wipe_outcome: WipeOutcome::UnitStarted,
                challenges: 0,
                wipes: Vec::new(),
            }
        }
    }

    impl GateIo for MockIo {
        fn run_challenge(&mut self) -> bool {
            self.challenges += 1;
            self.challenge_passes
        }
        fn authorize_wipe(&mut self, reason: ChallengeReason) -> WipeOutcome {
            self.wipes.push(reason);
            self.wipe_outcome.clone()
        }
    }

    fn arm(fsm: &mut GateFsm, io: &mut MockIo) -> Instant {
        let t0 = Instant::now();
        let t1 = t0 + Duration::from_secs(15);
        dispatch(fsm, Input::Event(EventType::LidClosed), t0, io);
        dispatch(fsm, Input::Event(EventType::Heartbeat), t1, io);
        assert_eq!(fsm.state(), SystemState::Armed);
        t1
    }

    #[test]
    fn lid_open_while_armed_runs_challenge_and_disarms_on_pass() {
        let mut fsm = GateFsm::new(Duration::from_secs(15), 10);
        let mut io = MockIo::new(true);
        let t = arm(&mut fsm, &mut io);
        let c = dispatch(&mut fsm, Input::Event(EventType::LidOpened), t, &mut io);
        assert_eq!(c, Control::Continue);
        assert_eq!(io.challenges, 1);
        assert!(io.wipes.is_empty());
        assert_eq!(fsm.state(), SystemState::Disarmed);
    }

    #[test]
    fn heartbeat_timeout_with_failed_challenge_authorizes_wipe() {
        let mut fsm = GateFsm::new(Duration::from_secs(15), 10);
        let mut io = MockIo::new(false);
        let t = arm(&mut fsm, &mut io);
        let c = dispatch(&mut fsm, Input::WatchdogTimeout, t, &mut io);
        assert_eq!(
            c,
            Control::Wiping(ChallengeReason::HeartbeatTimeout, WipeOutcome::UnitStarted)
        );
        assert_eq!(io.wipes, [ChallengeReason::HeartbeatTimeout]);
        assert_eq!(fsm.state(), SystemState::Wiping);
    }

    #[test]
    fn wipe_failure_is_surfaced_not_swallowed() {
        let mut fsm = GateFsm::new(Duration::from_secs(15), 10);
        let mut io = MockIo::new(false);
        io.wipe_outcome = WipeOutcome::AllFallbacksFailed;
        let t = arm(&mut fsm, &mut io);
        let c = dispatch(&mut fsm, Input::Event(EventType::LidOpened), t, &mut io);
        // The caller receives the failure and must hold in Wiping; it never
        // gets Control::Continue back, so monitoring cannot resume.
        assert_eq!(
            c,
            Control::Wiping(ChallengeReason::LidOpened, WipeOutcome::AllFallbacksFailed)
        );
        assert_eq!(fsm.state(), SystemState::Wiping);
    }

    #[test]
    fn disarmed_watchdog_does_not_challenge() {
        let mut fsm = GateFsm::new(Duration::from_secs(15), 10);
        let mut io = MockIo::new(false);
        let c = dispatch(&mut fsm, Input::WatchdogTimeout, Instant::now(), &mut io);
        assert_eq!(c, Control::Continue);
        assert_eq!(io.challenges, 0);
    }

    #[test]
    fn run_checked_reports_spawn_and_exit_failures() {
        assert!(run_checked(&mut Command::new("true")).is_ok());
        let err = run_checked(&mut Command::new("false")).unwrap_err();
        assert!(err.contains("exited with"), "{err}");
        let err = run_checked(&mut Command::new("/nonexistent/tamper-wipe-binary")).unwrap_err();
        assert!(err.contains("failed to spawn"), "{err}");
    }
}
