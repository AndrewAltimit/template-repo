//! Protocol state machine and validation for BioForge experiment workflows.
//!
//! Manages the finite state machine that governs experiment execution,
//! enforcing step ordering, prerequisite validation, and human-in-the-loop
//! gate requirements.

use bioforge_types::error::BioForgeError;
use bioforge_types::protocol::{Protocol, ProtocolState, ProtocolStep};
use std::collections::HashSet;

/// The protocol state machine managing experiment execution.
pub struct StateMachine {
    state: ProtocolState,
    protocol: Option<Protocol>,
    current_step: usize,
    run_id: String,
}

impl StateMachine {
    pub fn new(run_id: impl Into<String>) -> Self {
        Self {
            state: ProtocolState::Idle,
            protocol: None,
            current_step: 0,
            run_id: run_id.into(),
        }
    }

    /// Current state.
    pub fn state(&self) -> ProtocolState {
        self.state
    }

    /// Current run ID.
    pub fn run_id(&self) -> &str {
        &self.run_id
    }

    /// Load a protocol, transitioning from Idle to ProtocolLoaded.
    pub fn load_protocol(&mut self, protocol: Protocol) -> Result<(), BioForgeError> {
        if self.state != ProtocolState::Idle && self.state != ProtocolState::ExperimentComplete {
            return Err(BioForgeError::InvalidTransition {
                from: self.state.to_string(),
                to: "ProtocolLoaded".to_string(),
            });
        }
        validate_protocol(&protocol)?;
        self.protocol = Some(protocol);
        self.current_step = 0;
        self.state = ProtocolState::ProtocolLoaded;
        Ok(())
    }

    /// Attempt a state transition, validating it against the allowed transitions.
    pub fn transition(&mut self, target: ProtocolState) -> Result<(), BioForgeError> {
        if self.is_valid_transition(self.state, target) {
            tracing::info!(
                from = ?self.state,
                to = ?target,
                run_id = %self.run_id,
                "state transition"
            );
            self.state = target;
            Ok(())
        } else {
            Err(BioForgeError::InvalidTransition {
                from: self.state.to_string(),
                to: target.to_string(),
            })
        }
    }

    /// Get the current step if a protocol is loaded.
    pub fn current_step(&self) -> Option<&ProtocolStep> {
        self.protocol
            .as_ref()
            .and_then(|p| p.steps.get(self.current_step))
    }

    /// Check whether the current step requires human gate confirmation.
    pub fn requires_human_gate(&self) -> bool {
        self.current_step().is_some_and(|s| s.human_gate)
    }

    /// Advance to the next step in the protocol.
    pub fn advance_step(&mut self) -> Option<&ProtocolStep> {
        self.current_step += 1;
        self.current_step()
    }

    /// Reset the state machine to Idle.
    pub fn reset(&mut self) {
        self.state = ProtocolState::Idle;
        self.protocol = None;
        self.current_step = 0;
    }

    fn is_valid_transition(&self, from: ProtocolState, to: ProtocolState) -> bool {
        use ProtocolState::*;
        matches!(
            (from, to),
            (Idle, ProtocolLoaded)
                | (ProtocolLoaded, MediaPrep)
                | (MediaPrep, MediaReady)
                | (MediaReady, ReagentsLoaded)
                | (ReagentsLoaded, Transforming)
                | (Transforming, TransformationComplete)
                | (TransformationComplete, Plating)
                | (Plating, PlatesReady)
                | (PlatesReady, Incubating)
                | (Incubating, IncubationComplete)
                | (IncubationComplete, Analyzing)
                | (Analyzing, ExperimentComplete)
                | (ExperimentComplete, ProtocolLoaded)
                | (ExperimentComplete, Idle)
        )
    }
}

/// Validate a protocol definition for structural correctness.
pub fn validate_protocol(protocol: &Protocol) -> Result<(), BioForgeError> {
    if protocol.steps.is_empty() {
        return Err(BioForgeError::ProtocolError(
            "protocol has no steps".to_string(),
        ));
    }

    // Verify step IDs are unique
    let mut seen_ids = HashSet::new();
    for step in &protocol.steps {
        if !seen_ids.insert(step.id) {
            return Err(BioForgeError::ProtocolError(format!(
                "duplicate step id: {}",
                step.id
            )));
        }
    }

    // Verify step IDs are in ascending order
    for window in protocol.steps.windows(2) {
        if window[0].id >= window[1].id {
            return Err(BioForgeError::ProtocolError(format!(
                "step ids must be ascending: {} >= {}",
                window[0].id, window[1].id
            )));
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use bioforge_types::protocol::*;

    fn make_step(id: u32, human_gate: bool) -> ProtocolStep {
        ProtocolStep {
            id,
            name: format!("step_{id}"),
            action: StepAction::Wait {
                seconds: 1,
                reason: "test".to_string(),
            },
            human_gate,
            notes: None,
        }
    }

    fn make_protocol(steps: Vec<ProtocolStep>) -> Protocol {
        Protocol {
            name: "test".to_string(),
            version: "1.0".to_string(),
            description: "test protocol".to_string(),
            steps,
        }
    }

    // -- Protocol validation --

    #[test]
    fn validate_empty_protocol() {
        let p = make_protocol(vec![]);
        assert!(validate_protocol(&p).is_err());
    }

    #[test]
    fn validate_single_step() {
        let p = make_protocol(vec![make_step(1, false)]);
        assert!(validate_protocol(&p).is_ok());
    }

    #[test]
    fn validate_duplicate_ids() {
        let p = make_protocol(vec![make_step(1, false), make_step(1, false)]);
        assert!(validate_protocol(&p).is_err());
    }

    #[test]
    fn validate_non_ascending_ids() {
        let p = make_protocol(vec![make_step(2, false), make_step(1, false)]);
        assert!(validate_protocol(&p).is_err());
    }

    #[test]
    fn validate_ascending_ids() {
        let p = make_protocol(vec![
            make_step(1, false),
            make_step(2, false),
            make_step(3, false),
        ]);
        assert!(validate_protocol(&p).is_ok());
    }

    // -- State machine transitions --

    #[test]
    fn full_happy_path() {
        use ProtocolState::*;
        let mut sm = StateMachine::new("run_001");

        let protocol = make_protocol(vec![make_step(1, false), make_step(2, true)]);
        sm.load_protocol(protocol).unwrap();
        assert_eq!(sm.state(), ProtocolLoaded);

        let transitions = [
            MediaPrep,
            MediaReady,
            ReagentsLoaded,
            Transforming,
            TransformationComplete,
            Plating,
            PlatesReady,
            Incubating,
            IncubationComplete,
            Analyzing,
            ExperimentComplete,
        ];

        for target in transitions {
            sm.transition(target).unwrap();
            assert_eq!(sm.state(), target);
        }
    }

    #[test]
    fn cannot_skip_states() {
        let mut sm = StateMachine::new("run_001");
        let protocol = make_protocol(vec![make_step(1, false)]);
        sm.load_protocol(protocol).unwrap();

        // Try to skip from ProtocolLoaded directly to Transforming
        assert!(sm.transition(ProtocolState::Transforming).is_err());
        assert_eq!(sm.state(), ProtocolState::ProtocolLoaded);
    }

    #[test]
    fn cannot_load_protocol_from_wrong_state() {
        let mut sm = StateMachine::new("run_001");
        let protocol = make_protocol(vec![make_step(1, false)]);
        sm.load_protocol(protocol).unwrap();
        sm.transition(ProtocolState::MediaPrep).unwrap();

        // Cannot load protocol from MediaPrep
        let p2 = make_protocol(vec![make_step(1, false)]);
        assert!(sm.load_protocol(p2).is_err());
    }

    #[test]
    fn can_reload_protocol_after_completion() {
        use ProtocolState::*;
        let mut sm = StateMachine::new("run_001");
        let protocol = make_protocol(vec![make_step(1, false)]);
        sm.load_protocol(protocol).unwrap();

        for target in [
            MediaPrep,
            MediaReady,
            ReagentsLoaded,
            Transforming,
            TransformationComplete,
            Plating,
            PlatesReady,
            Incubating,
            IncubationComplete,
            Analyzing,
            ExperimentComplete,
        ] {
            sm.transition(target).unwrap();
        }

        // Can reload from ExperimentComplete
        let p2 = make_protocol(vec![make_step(1, false)]);
        assert!(sm.load_protocol(p2).is_ok());
    }

    #[test]
    fn reset_returns_to_idle() {
        let mut sm = StateMachine::new("run_001");
        let protocol = make_protocol(vec![make_step(1, false)]);
        sm.load_protocol(protocol).unwrap();
        sm.transition(ProtocolState::MediaPrep).unwrap();

        sm.reset();
        assert_eq!(sm.state(), ProtocolState::Idle);
    }

    #[test]
    fn human_gate_detection() {
        let mut sm = StateMachine::new("run_001");
        let protocol = make_protocol(vec![make_step(1, true), make_step(2, false)]);
        sm.load_protocol(protocol).unwrap();

        assert!(sm.requires_human_gate());
        sm.advance_step();
        assert!(!sm.requires_human_gate());
    }
}
