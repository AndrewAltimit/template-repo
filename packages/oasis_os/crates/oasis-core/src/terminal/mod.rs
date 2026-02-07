//! Command interpreter and terminal subsystem.
//!
//! The terminal is a registry-based dispatch system. Commands implement the
//! `Command` trait and are registered by name. The interpreter parses input
//! lines, resolves the command name, and dispatches `execute()`.

mod commands;
mod interpreter;

pub use commands::register_builtins;
pub use interpreter::{Command, CommandOutput, CommandRegistry, Environment};
