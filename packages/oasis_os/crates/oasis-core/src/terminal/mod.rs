//! Command interpreter and terminal subsystem.
//!
//! The terminal is a registry-based dispatch system. Commands implement the
//! `Command` trait and are registered by name. The interpreter parses input
//! lines, resolves the command name, and dispatches `execute()`.

pub mod agent_commands;
pub mod audio_commands;
mod commands;
mod interpreter;
pub mod plugin_commands;

pub use agent_commands::register_agent_commands;
pub use audio_commands::register_audio_commands;
pub use commands::register_builtins;
pub use interpreter::{Command, CommandOutput, CommandRegistry, Environment};
pub use plugin_commands::register_plugin_commands;
