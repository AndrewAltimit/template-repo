mod failure;
mod precommit;
mod respond;
mod trust;

use anyhow::Result;
use clap::Subcommand;

#[derive(Subcommand)]
pub enum ReviewAction {
    /// Respond to AI code review feedback using Claude
    Respond(respond::RespondArgs),
    /// Handle CI pipeline failures with automated fixes
    Failure(failure::FailureArgs),
    /// Run precommit checks (autoformat, lint, test) before committing agent changes
    Precommit(precommit::PrecommitArgs),
}

pub fn run(action: ReviewAction) -> Result<()> {
    match action {
        ReviewAction::Respond(args) => respond::run(args),
        ReviewAction::Failure(args) => failure::run(args),
        ReviewAction::Precommit(args) => precommit::run(args),
    }
}
