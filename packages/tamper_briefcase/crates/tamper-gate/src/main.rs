//! Tamper gate orchestrator -- manages the arming FSM, password challenge, and
//! wipe authorization.
//!
//! Runs as root with restricted write paths. Reads sensor events from the FIFO
//! produced by `tamper-sensor`. On a confirmed tamper while armed, launches the
//! `tamper-challenge` binary as a subprocess. On challenge failure, creates a
//! trigger file and starts `tamper-wipe.service`.
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
use std::time::Instant;

use anyhow::{Context, Result};
use chrono::Utc;
use nix::poll::{PollFd, PollFlags, PollTimeout, poll};

use tamper_common::{Config, EventType, SystemState, TamperEvent};

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
fn run_challenge(config: &Config) -> bool {
    log::info!(
        "Launching password challenge (timeout={}s)",
        config.challenge_timeout_secs
    );

    let result = Command::new(&config.challenge_binary)
        .stdin(std::process::Stdio::inherit())
        .stdout(std::process::Stdio::inherit())
        .stderr(std::process::Stdio::inherit())
        .status();

    match result {
        Ok(status) => {
            if status.success() {
                log::info!("Challenge PASSED");
                true
            } else {
                log::error!("Challenge FAILED (exit code: {:?})", status.code());
                false
            }
        },
        Err(e) => {
            log::error!("Challenge subprocess error: {}", e);
            false
        },
    }
}

// ---------------------------------------------------------------------------
// Wipe authorization
// ---------------------------------------------------------------------------

/// Create the trigger file that `tamper-wipe.service` watches, then start the
/// wipe unit. This is the ONLY path to wipe -- the wipe unit has
/// `ConditionPathExists=/run/tamper/wipe-authorized`.
fn authorize_wipe(config: &Config) {
    log::error!("=== WIPE AUTHORIZED ===");

    let payload = serde_json::json!({
        "authorized_at": Utc::now().to_rfc3339(),
        "reason": "challenge_failed",
    });

    if let Err(e) = fs::write(&config.wipe_trigger_file, payload.to_string()) {
        log::error!(
            "Failed to write wipe trigger file {}: {}",
            config.wipe_trigger_file.display(),
            e
        );
    }

    // Start the wipe service unit.
    let _ = Command::new("systemctl")
        .args(["start", "tamper-wipe.service"])
        .status();
}

// ---------------------------------------------------------------------------
// Main loop
// ---------------------------------------------------------------------------

fn main() -> Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let config = Config::load(Path::new(Config::DEFAULT_PATH));

    log::info!("Tamper gate orchestrator starting");

    ensure_fifo(&config.event_fifo)?;

    let mut state = SystemState::Disarmed;
    let mut arming_start: Option<Instant> = None;
    let mut anomaly_counter: u32 = 0;
    let mut last_heartbeat = Instant::now();

    let heartbeat_timeout_ms = (config.heartbeat_timeout_secs * 1000) as i32;

    log::info!("State: {}", state);
    log::info!("Heartbeat timeout: {}s", config.heartbeat_timeout_secs,);

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
        // Poll the FIFO with a timeout based on the heartbeat window.
        // In Disarmed/Arming states, sensor silence is not critical, so we
        // use a generous timeout. In Armed state, silence means the sensor
        // may have been disabled (tamper).
        let timeout = match state {
            SystemState::Armed => PollTimeout::try_from(heartbeat_timeout_ms),
            _ => PollTimeout::try_from(heartbeat_timeout_ms * 2),
        }
        .unwrap_or(PollTimeout::MAX);

        let mut poll_fds = [PollFd::new(reader.get_ref().as_fd(), PollFlags::POLLIN)];
        let poll_result = poll(&mut poll_fds, timeout).context("poll() failed on FIFO")?;

        if poll_result == 0 {
            // Timeout -- no data from sensor within the heartbeat window.
            let silence_secs = last_heartbeat.elapsed().as_secs();

            if state == SystemState::Armed {
                log::error!(
                    "WATCHDOG: No heartbeat for {}s while ARMED -- sensor may be compromised",
                    silence_secs,
                );
                log::warn!("Triggering challenge due to sensor silence");

                if run_challenge(&config) {
                    log::info!("Challenge PASSED -- disarming");
                    state = SystemState::Disarmed;
                    last_heartbeat = Instant::now();
                } else {
                    log::error!("Challenge FAILED -- authorizing wipe");
                    authorize_wipe(&config);
                    std::process::exit(1);
                }
            } else {
                log::warn!(
                    "No heartbeat for {}s (state={}) -- sensor may be offline",
                    silence_secs,
                    state,
                );
            }
            continue;
        }

        // Data available -- read lines.
        line_buf.clear();
        let bytes_read = reader.read_line(&mut line_buf).context("FIFO read error")?;

        if bytes_read == 0 {
            log::warn!("FIFO closed -- sensor daemon disconnected");
            // Sensor disconnect while armed is a tamper indication.
            if state == SystemState::Armed {
                log::error!("Sensor disconnected while ARMED -- triggering challenge");
                if run_challenge(&config) {
                    log::info!("Challenge PASSED -- disarming");
                } else {
                    log::error!("Challenge FAILED -- authorizing wipe");
                    authorize_wipe(&config);
                    std::process::exit(1);
                }
            }
            break;
        }

        let line = line_buf.trim();
        if line.is_empty() {
            continue;
        }

        let event: TamperEvent = match serde_json::from_str(line) {
            Ok(e) => e,
            Err(e) => {
                log::warn!("Malformed event: {} -- {}", line, e);
                continue;
            },
        };

        // Reset heartbeat timer on any event from the sensor.
        last_heartbeat = Instant::now();

        if event.event_type == EventType::Heartbeat {
            log::debug!("Heartbeat received (lux={:.1})", event.lux);
            continue;
        }

        log::info!(
            "Event: {} (lux={:.1}, confidence={}, state={})",
            event.event_type,
            event.lux,
            event.confidence,
            state,
        );

        match state {
            // -- DISARMED ------------------------------------------------
            SystemState::Disarmed => {
                if event.event_type == EventType::LidClosed {
                    state = SystemState::Arming;
                    arming_start = Some(Instant::now());
                    log::info!("Lid closed -- arming in {}s", config.arming_delay_secs);
                }
                // Ignore opens while disarmed.
            },

            // -- ARMING --------------------------------------------------
            SystemState::Arming => {
                if event.event_type == EventType::LidOpened {
                    state = SystemState::Disarmed;
                    arming_start = None;
                    log::info!("Lid reopened during arming -- back to DISARMED");
                } else if let Some(start) = arming_start {
                    if start.elapsed().as_secs() >= config.arming_delay_secs {
                        state = SystemState::Armed;
                        anomaly_counter = 0;
                        log::info!("=== SYSTEM ARMED ===");
                    }
                }
            },

            // -- ARMED ---------------------------------------------------
            SystemState::Armed => {
                if event.event_type == EventType::LidOpened {
                    // Primary trigger.
                    log::warn!(
                        "TAMPER: Lid opened while armed (confidence={})",
                        event.confidence,
                    );

                    if run_challenge(&config) {
                        log::info!("Challenge PASSED -- disarming");
                        state = SystemState::Disarmed;
                    } else {
                        log::error!("Challenge FAILED -- authorizing wipe");
                        authorize_wipe(&config);
                        std::process::exit(1);
                    }
                } else if event.event_type == EventType::LightAnomaly {
                    anomaly_counter += 1;
                    log::warn!(
                        "Light anomaly #{}/{} while armed",
                        anomaly_counter,
                        config.anomaly_escalation_count,
                    );
                    if anomaly_counter >= config.anomaly_escalation_count {
                        log::warn!("Anomaly threshold reached -- triggering challenge");

                        if run_challenge(&config) {
                            state = SystemState::Disarmed;
                            anomaly_counter = 0;
                        } else {
                            authorize_wipe(&config);
                            std::process::exit(1);
                        }
                    }
                }
            },

            // -- CHALLENGING ---------------------------------------------
            SystemState::Challenging => {
                // Challenge is synchronous -- this state is transient.
                log::info!("In CHALLENGING state, ignoring concurrent events");
            },

            // -- WIPING --------------------------------------------------
            SystemState::Wiping => {
                log::info!("In WIPING state, ignoring events");
            },
        }
    }

    Ok(())
}
