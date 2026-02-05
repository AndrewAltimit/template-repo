//! Protocol state machine and validation for BioForge experiment workflows.
//!
//! Manages the finite state machine that governs experiment execution,
//! enforcing step ordering, prerequisite validation, and human-in-the-loop
//! gate requirements.

use bioforge_types::error::BioForgeError;
use bioforge_types::protocol::{Protocol, ProtocolState, ProtocolStep};

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
                from: format!("{:?}", self.state),
                to: "ProtocolLoaded".to_string(),
            });
        }
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
                from: format!("{:?}", self.state),
                to: format!("{target:?}"),
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

/// Validate a protocol definition against hardware capabilities and safety limits.
pub fn validate_protocol(protocol: &Protocol) -> Result<(), BioForgeError> {
    if protocol.steps.is_empty() {
        return Err(BioForgeError::ProtocolError(
            "protocol has no steps".to_string(),
        ));
    }
    // Further validation (volume limits, temp ranges, etc.) would be done
    // by the SafetyEnforcer during execution.
    Ok(())
}
