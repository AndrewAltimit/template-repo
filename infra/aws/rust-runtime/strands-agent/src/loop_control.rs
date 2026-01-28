//! Agent loop control signals.
//!
//! Provides mechanisms for external control of the agent loop,
//! including early termination signals from tools.

use serde_json::Value;

/// Signal that can terminate the agent loop early.
#[derive(Debug, Clone)]
pub enum LoopTerminationSignal {
    /// Tool signaled successful completion
    ToolCompleted {
        /// Name of the tool that triggered termination
        tool_name: String,
        /// The result value from the tool
        result: Value,
    },
}

/// Type alias for the termination signal receiver.
pub type TerminationReceiver = tokio::sync::mpsc::Receiver<LoopTerminationSignal>;

/// Type alias for the termination signal sender.
pub type TerminationSender = tokio::sync::mpsc::Sender<LoopTerminationSignal>;

/// Create a new termination channel pair.
pub fn termination_channel() -> (TerminationSender, TerminationReceiver) {
    tokio::sync::mpsc::channel(1)
}
