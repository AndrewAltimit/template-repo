//! Pure arming state machine for the gate orchestrator.
//!
//! No I/O happens here: the FSM consumes [`Input`]s with an explicit `now`
//! and returns a [`Step`] telling the caller whether a password challenge is
//! required. The caller runs the challenge and reports the result through
//! [`GateFsm::resolve_challenge`]. This keeps every transition unit testable
//! without the FIFO, the challenge binary, or systemd.

use std::time::{Duration, Instant};

use tamper_common::{EventType, SystemState};

/// Something the gate observed.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Input {
    /// A well-formed event from the sensor daemon (heartbeats included).
    Event(EventType),
    /// No valid sensor event within the heartbeat timeout window.
    WatchdogTimeout,
    /// The sensor daemon closed its end of the FIFO.
    SensorDisconnected,
}

/// Why a challenge was demanded. Recorded in the wipe trigger file.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ChallengeReason {
    LidOpened,
    LightAnomalies,
    HeartbeatTimeout,
    SensorDisconnected,
}

impl ChallengeReason {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::LidOpened => "lid_opened",
            Self::LightAnomalies => "light_anomalies",
            Self::HeartbeatTimeout => "heartbeat_timeout",
            Self::SensorDisconnected => "sensor_disconnected",
        }
    }
}

/// What the caller must do after feeding an input.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Step {
    /// Nothing beyond logging.
    Continue,
    /// Run the password challenge, then call [`GateFsm::resolve_challenge`].
    Challenge(ChallengeReason),
}

/// Outcome of a resolved challenge.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Resolution {
    /// Challenge passed; the system is disarmed.
    Disarmed,
    /// Challenge failed (wrong password, timeout, or crash); wipe must be
    /// authorized. The FSM is now terminally in `Wiping`.
    AuthorizeWipe(ChallengeReason),
}

/// Arming FSM state plus the counters that drive transitions.
#[derive(Debug)]
pub struct GateFsm {
    state: SystemState,
    arming_start: Option<Instant>,
    anomaly_counter: u32,
    arming_delay: Duration,
    anomaly_escalation_count: u32,
}

impl GateFsm {
    pub fn new(arming_delay: Duration, anomaly_escalation_count: u32) -> Self {
        Self {
            state: SystemState::Disarmed,
            arming_start: None,
            anomaly_counter: 0,
            arming_delay,
            anomaly_escalation_count,
        }
    }

    pub fn state(&self) -> SystemState {
        self.state
    }

    pub fn anomaly_counter(&self) -> u32 {
        self.anomaly_counter
    }

    /// Feed one input and get the required follow-up.
    pub fn handle(&mut self, input: Input, now: Instant) -> Step {
        match self.state {
            SystemState::Disarmed => {
                // Opens (and silence) are ignored while disarmed.
                if input == Input::Event(EventType::LidClosed) {
                    self.state = SystemState::Arming;
                    self.arming_start = Some(now);
                }
                Step::Continue
            },

            SystemState::Arming => {
                match input {
                    Input::Event(EventType::LidOpened) => {
                        self.state = SystemState::Disarmed;
                        self.arming_start = None;
                    },
                    // Any other sensor event, heartbeats included, proves the
                    // sensor is alive with the lid still shut, so it can
                    // complete the arming delay. (Heartbeats must count here:
                    // with the lid closed they are usually the only events.)
                    Input::Event(_) => {
                        if self
                            .arming_start
                            .is_some_and(|start| now.duration_since(start) >= self.arming_delay)
                        {
                            self.state = SystemState::Armed;
                            self.arming_start = None;
                            self.anomaly_counter = 0;
                        }
                    },
                    // Silence or disconnect: lid state cannot be confirmed, so
                    // do not complete arming on it.
                    Input::WatchdogTimeout | Input::SensorDisconnected => {},
                }
                Step::Continue
            },

            SystemState::Armed => match input {
                Input::Event(EventType::LidOpened) => {
                    self.begin_challenge(ChallengeReason::LidOpened)
                },
                Input::Event(EventType::LightAnomaly) => {
                    self.anomaly_counter = self.anomaly_counter.saturating_add(1);
                    if self.anomaly_counter >= self.anomaly_escalation_count {
                        self.begin_challenge(ChallengeReason::LightAnomalies)
                    } else {
                        Step::Continue
                    }
                },
                Input::Event(EventType::LidClosed | EventType::Heartbeat) => Step::Continue,
                Input::WatchdogTimeout => self.begin_challenge(ChallengeReason::HeartbeatTimeout),
                Input::SensorDisconnected => {
                    self.begin_challenge(ChallengeReason::SensorDisconnected)
                },
            },

            // The challenge runs synchronously in the caller, and Wiping is
            // terminal: ignore everything.
            SystemState::Challenging | SystemState::Wiping => Step::Continue,
        }
    }

    fn begin_challenge(&mut self, reason: ChallengeReason) -> Step {
        self.state = SystemState::Challenging;
        Step::Challenge(reason)
    }

    /// Report the result of a challenge requested by [`Step::Challenge`].
    pub fn resolve_challenge(&mut self, reason: ChallengeReason, passed: bool) -> Resolution {
        if passed {
            self.state = SystemState::Disarmed;
            self.arming_start = None;
            self.anomaly_counter = 0;
            Resolution::Disarmed
        } else {
            self.state = SystemState::Wiping;
            Resolution::AuthorizeWipe(reason)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const DELAY: Duration = Duration::from_secs(15);

    fn ev(e: EventType) -> Input {
        Input::Event(e)
    }

    /// Drive a fresh FSM to Armed and return it with the instant it armed.
    fn armed() -> (GateFsm, Instant) {
        let mut fsm = GateFsm::new(DELAY, 3);
        let t0 = Instant::now();
        assert_eq!(fsm.handle(ev(EventType::LidClosed), t0), Step::Continue);
        assert_eq!(fsm.state(), SystemState::Arming);
        let t1 = t0 + DELAY;
        assert_eq!(fsm.handle(ev(EventType::Heartbeat), t1), Step::Continue);
        assert_eq!(fsm.state(), SystemState::Armed);
        (fsm, t1)
    }

    #[test]
    fn heartbeat_completes_arming_only_after_delay() {
        let mut fsm = GateFsm::new(DELAY, 3);
        let t0 = Instant::now();
        fsm.handle(ev(EventType::LidClosed), t0);
        fsm.handle(ev(EventType::Heartbeat), t0 + DELAY / 2);
        assert_eq!(fsm.state(), SystemState::Arming);
        fsm.handle(ev(EventType::Heartbeat), t0 + DELAY);
        assert_eq!(fsm.state(), SystemState::Armed);
    }

    #[test]
    fn silence_does_not_complete_arming() {
        let mut fsm = GateFsm::new(DELAY, 3);
        let t0 = Instant::now();
        fsm.handle(ev(EventType::LidClosed), t0);
        fsm.handle(Input::WatchdogTimeout, t0 + DELAY * 2);
        assert_eq!(fsm.state(), SystemState::Arming);
    }

    #[test]
    fn lid_open_during_arming_disarms() {
        let mut fsm = GateFsm::new(DELAY, 3);
        let t0 = Instant::now();
        fsm.handle(ev(EventType::LidClosed), t0);
        fsm.handle(ev(EventType::LidOpened), t0 + Duration::from_secs(1));
        assert_eq!(fsm.state(), SystemState::Disarmed);
        // Arming restarts from scratch on the next close.
        fsm.handle(ev(EventType::Heartbeat), t0 + DELAY * 2);
        assert_eq!(fsm.state(), SystemState::Disarmed);
    }

    #[test]
    fn disarmed_ignores_opens_and_silence() {
        let mut fsm = GateFsm::new(DELAY, 3);
        let t = Instant::now();
        assert_eq!(fsm.handle(ev(EventType::LidOpened), t), Step::Continue);
        assert_eq!(fsm.handle(Input::WatchdogTimeout, t), Step::Continue);
        assert_eq!(fsm.handle(Input::SensorDisconnected, t), Step::Continue);
        assert_eq!(fsm.state(), SystemState::Disarmed);
    }

    #[test]
    fn lid_open_while_armed_raises_alarm() {
        let (mut fsm, t) = armed();
        assert_eq!(
            fsm.handle(ev(EventType::LidOpened), t),
            Step::Challenge(ChallengeReason::LidOpened)
        );
        assert_eq!(fsm.state(), SystemState::Challenging);
        // Concurrent events are ignored while challenging.
        assert_eq!(fsm.handle(ev(EventType::LidOpened), t), Step::Continue);
    }

    #[test]
    fn heartbeat_timeout_while_armed_is_tamper() {
        let (mut fsm, t) = armed();
        assert_eq!(
            fsm.handle(Input::WatchdogTimeout, t),
            Step::Challenge(ChallengeReason::HeartbeatTimeout)
        );
        assert_eq!(fsm.state(), SystemState::Challenging);
    }

    #[test]
    fn sensor_disconnect_while_armed_is_tamper() {
        let (mut fsm, t) = armed();
        assert_eq!(
            fsm.handle(Input::SensorDisconnected, t),
            Step::Challenge(ChallengeReason::SensorDisconnected)
        );
    }

    #[test]
    fn light_anomalies_escalate_at_threshold() {
        let (mut fsm, t) = armed();
        assert_eq!(fsm.handle(ev(EventType::LightAnomaly), t), Step::Continue);
        assert_eq!(fsm.handle(ev(EventType::LightAnomaly), t), Step::Continue);
        assert_eq!(fsm.anomaly_counter(), 2);
        assert_eq!(
            fsm.handle(ev(EventType::LightAnomaly), t),
            Step::Challenge(ChallengeReason::LightAnomalies)
        );
    }

    #[test]
    fn authorized_disarm_resets_state() {
        let (mut fsm, t) = armed();
        fsm.handle(ev(EventType::LightAnomaly), t);
        let Step::Challenge(reason) = fsm.handle(ev(EventType::LidOpened), t) else {
            panic!("expected challenge");
        };
        assert_eq!(fsm.resolve_challenge(reason, true), Resolution::Disarmed);
        assert_eq!(fsm.state(), SystemState::Disarmed);
        assert_eq!(fsm.anomaly_counter(), 0);
        // Must go through a fresh close + delay to re-arm.
        fsm.handle(ev(EventType::Heartbeat), t + DELAY * 4);
        assert_eq!(fsm.state(), SystemState::Disarmed);
    }

    #[test]
    fn failed_challenge_authorizes_wipe_and_is_terminal() {
        let (mut fsm, t) = armed();
        let Step::Challenge(reason) = fsm.handle(Input::WatchdogTimeout, t) else {
            panic!("expected challenge");
        };
        assert_eq!(
            fsm.resolve_challenge(reason, false),
            Resolution::AuthorizeWipe(ChallengeReason::HeartbeatTimeout)
        );
        assert_eq!(fsm.state(), SystemState::Wiping);
        // Nothing gets the FSM out of Wiping.
        for input in [
            ev(EventType::LidClosed),
            ev(EventType::Heartbeat),
            ev(EventType::LidOpened),
            Input::WatchdogTimeout,
        ] {
            assert_eq!(fsm.handle(input, t + DELAY), Step::Continue);
            assert_eq!(fsm.state(), SystemState::Wiping);
        }
    }
}
