mod failure;
mod respond;
mod trust;

use anyhow::Result;
use clap::Subcommand;

#[derive(Subcommand)]
pub enum ReviewAction {
    /// Respond to AI code review feedback (Gemini/Codex) using Claude
    Respond(respond::RespondArgs),
    /// Handle CI pipeline failures with automated fixes
    Failure(failure::FailureArgs),
}

pub fn run(action: ReviewAction) -> Result<()> {
    match action {
        ReviewAction::Respond(args) => respond::run(args),
        ReviewAction::Failure(args) => failure::run(args),
    }
}
