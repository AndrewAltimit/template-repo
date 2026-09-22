//! Subcommand implementations.
//!
//! `main.rs` owns argument parsing; each function here implements one
//! subcommand and preserves the documented stdout formats (logs go to
//! stderr so JSON output stays machine-readable).

use std::path::Path;
use std::sync::Arc;
use std::sync::atomic::AtomicBool;

use clap::Subcommand;
use serde_json::json;
use tracing::{error, info, warn};

use crate::agents::{AgentRegistry, filter_agent_list};
use crate::analyzers::{
    AgentAnalyzer, AnalysisFinding, FindingCategory, FindingPriority, default_analysis_prompt,
};
use crate::creators::{CreationResult, IssueCreator};
use crate::error::Error;
use crate::iteration::{self, AgentType};
use crate::monitor::{IssueMonitor, Monitor, PrMonitor, RefinementConfig, RefinementMonitor};
use crate::review;
use crate::security::SecurityManager;
use crate::security::commit::{fetch_pr_head, is_valid_sha, sha_matches};
use crate::security::trigger::parse_trigger;

/// `github-agents security <command>`
#[derive(Subcommand, Debug)]
pub enum SecurityCommand {
    /// Check whether a user is on the agent allow-list (exit 8 if not)
    CheckUser {
        /// GitHub username
        #[arg(long)]
        username: String,
    },
    /// Check whether an action (e.g. issue_approved) is allowed (exit 8 if not)
    CheckAction {
        /// Action name, e.g. issue_approved, pr_review
        #[arg(long)]
        action: String,
    },
    /// Verify a PR's head commit matches the approved SHA (exit 8 if not)
    ValidatePrCommit {
        /// PR number
        #[arg(long)]
        pr: u64,
        /// Approved commit SHA (7-40 hex characters)
        #[arg(long)]
        expected_sha: String,
        /// Repository (owner/repo); defaults to GITHUB_REPOSITORY
        #[arg(long)]
        repo: Option<String>,
    },
    /// Parse a trigger keyword from comment text
    ParseTrigger {
        /// Comment text to parse
        #[arg(long)]
        comment: String,
    },
}

/// `issue-monitor`
pub async fn issue_monitor(
    running: Arc<AtomicBool>,
    continuous: bool,
    interval: u64,
) -> Result<(), Error> {
    let monitor = IssueMonitor::new(running)?;
    run_monitor(&monitor, "issue", continuous, interval).await
}

/// `pr-monitor`
pub async fn pr_monitor(
    running: Arc<AtomicBool>,
    continuous: bool,
    interval: u64,
) -> Result<(), Error> {
    let monitor = PrMonitor::new(running)?;
    run_monitor(&monitor, "PR", continuous, interval).await
}

async fn run_monitor(
    monitor: &dyn Monitor,
    label: &str,
    continuous: bool,
    interval: u64,
) -> Result<(), Error> {
    if continuous {
        info!(
            "Running {} monitor continuously (interval: {}s)",
            label, interval
        );
        monitor.run_continuous(interval).await
    } else {
        info!("Running {} monitor once", label);
        monitor.process_items().await
    }
}

/// `refinement-monitor`
pub async fn refinement(
    running: Arc<AtomicBool>,
    agents: &str,
    config: RefinementConfig,
    format: &str,
) -> Result<(), Error> {
    let agent_list = filter_agent_list(agents);
    if agent_list.is_empty() {
        return Err(Error::Config(format!(
            "No usable agents in '{}' (disabled agents are skipped)",
            agents
        )));
    }
    info!(
        "Running backlog refinement with agents: {:?}, max_issues: {}, dry_run: {}",
        agent_list, config.max_issues_per_run, config.dry_run
    );

    let monitor = RefinementMonitor::new(running, config)?;
    let results = monitor.run(&agent_list).await?;

    if format == "json" {
        println!("{}", serde_json::to_string_pretty(&results)?);
    } else {
        println!(
            "Refinement complete: {} issues reviewed, {} insights added",
            results.len(),
            results.iter().map(|r| r.insights_added).sum::<usize>()
        );
    }
    Ok(())
}

/// Options for `pr-review`.
pub struct PrReviewOptions {
    pub pr_number: u64,
    pub agent: Option<String>,
    pub profile: Option<String>,
    pub full: bool,
    pub dry_run: bool,
    pub json: bool,
    /// `Some(agent)` when `--editor` was passed
    pub editor_agent: Option<String>,
}

/// `pr-review`
pub async fn pr_review(opts: PrReviewOptions) -> Result<(), Error> {
    info!("Running PR review for #{}", opts.pr_number);

    let mut config = review::PRReviewConfig::load()?;
    if let Some(editor_agent) = opts.editor_agent {
        config.editor_enabled = true;
        config.editor_agent = editor_agent;
    }

    let profile = match &opts.profile {
        Some(name) => {
            let p = review::config::ReviewProfile::load(name)?;
            info!("Using review profile '{}': {}", name, p.display_name);
            Some(p)
        },
        None => None,
    };

    // The profile's agent takes precedence over --agent
    let agent = profile.as_ref().map(|p| p.agent.clone()).or(opts.agent);

    let reviewer =
        review::PRReviewer::new_with_profile(config, agent.as_deref(), opts.dry_run, profile)
            .await?;
    let review_text = reviewer.review_pr(opts.pr_number, opts.full).await?;

    if opts.json {
        let result = json!({
            "pr_number": opts.pr_number,
            "review": review_text,
            "dry_run": opts.dry_run,
        });
        println!("{}", serde_json::to_string_pretty(&result)?);
    } else if !opts.dry_run {
        println!("Review posted to PR #{}", opts.pr_number);
    }
    // In dry-run text mode the reviewer already printed the preview
    Ok(())
}

/// Load the security manager for commands that take `--config`.
///
/// A missing file yields defaults. With `lenient`, an unreadable/invalid
/// file also falls back to defaults (with a warning); otherwise it is an
/// error.
fn load_security(config: &Path, lenient: bool) -> Result<SecurityManager, Error> {
    if !config.exists() {
        return Ok(SecurityManager::new());
    }
    match SecurityManager::from_config_path(config) {
        Ok(m) => Ok(m),
        Err(e) if lenient => {
            warn!(
                "Invalid security config {} ({}); using built-in defaults",
                config.display(),
                e
            );
            Ok(SecurityManager::new())
        },
        Err(e) => Err(e),
    }
}

/// `iteration-check`
pub async fn iteration_check(
    pr: u64,
    agent_type: &str,
    max_iterations: u32,
    format: &str,
    config: &Path,
) -> Result<(), Error> {
    info!("Checking iteration count for PR #{}", pr);

    let agent_type = AgentType::parse(agent_type).ok_or_else(|| {
        Error::Config(format!(
            "Invalid agent type '{}'. Must be 'review-fix' or 'failure-fix'",
            agent_type
        ))
    })?;

    // Lenient: falling back to the default admin only narrows who may
    // extend limits, which is the safe direction.
    let admins = load_security(config, true)?.allowed_users();
    let result = iteration::check_iteration(pr, agent_type, max_iterations, &admins).await?;

    match format {
        "json" => println!("{}", serde_json::to_string_pretty(&result)?),
        "github-actions" => iteration::output_github_actions(&result)?,
        _ => {
            println!("Agent Type: {}", result.agent_type);
            println!("Iteration Count: {}", result.iteration_count);
            println!(
                "Effective Max: {} (base: {} + {}x extensions)",
                result.effective_max, result.max_iterations, result.continue_count
            );
            println!("Exceeded Max: {}", result.exceeded_max);
            println!("Should Skip: {}", result.should_skip);
        },
    }
    Ok(())
}

/// Options for `analyze`.
pub struct AnalyzeOptions {
    pub agents: String,
    pub include_paths: String,
    pub exclude_paths: String,
    pub categories: String,
    pub min_priority: String,
    pub max_issues: usize,
    pub dry_run: bool,
    pub json: bool,
}

fn split_list(s: &str) -> Vec<String> {
    s.split(',')
        .map(|p| p.trim().to_string())
        .filter(|p| !p.is_empty())
        .collect()
}

/// Resolve the repository: `GITHUB_REPOSITORY`, else `gh repo view`.
async fn resolve_repository() -> Result<String, Error> {
    if let Ok(repo) = std::env::var("GITHUB_REPOSITORY")
        && !repo.trim().is_empty()
    {
        return Ok(repo.trim().to_string());
    }
    let out = crate::utils::run_gh_command(
        &[
            "repo",
            "view",
            "--json",
            "nameWithOwner",
            "-q",
            ".nameWithOwner",
        ],
        false,
    )
    .await?
    .map(|s| s.trim().to_string())
    .filter(|s| s.contains('/'));
    out.ok_or_else(|| Error::EnvNotSet("GITHUB_REPOSITORY".to_string()))
}

/// `analyze`
pub async fn analyze(opts: AnalyzeOptions) -> Result<(), Error> {
    info!("Running codebase analysis");

    let categories: Vec<FindingCategory> = opts
        .categories
        .split(',')
        .filter_map(|s| {
            let c = FindingCategory::parse(s);
            if c.is_none() && !s.trim().is_empty() {
                warn!("Ignoring unknown category '{}'", s.trim());
            }
            c
        })
        .collect();
    if categories.is_empty() {
        return Err(Error::Config("No valid categories specified".to_string()));
    }
    let min_priority = FindingPriority::parse(&opts.min_priority)
        .ok_or_else(|| Error::Config(format!("Invalid priority: {}", opts.min_priority)))?;
    let agent_names = filter_agent_list(&opts.agents);
    if agent_names.is_empty() {
        return Err(Error::Config(format!(
            "No usable agents in '{}' (disabled agents are skipped)",
            opts.agents
        )));
    }

    let repo = resolve_repository().await?;
    let include = split_list(&opts.include_paths);
    let exclude = split_list(&opts.exclude_paths);
    info!("Repository: {}", repo);
    info!("Categories: {:?}", categories);
    info!("Include paths: {:?}", include);
    info!("Exclude paths: {:?}", exclude);

    let repo_path = std::env::current_dir()?;
    let registry = AgentRegistry::new();
    let prompt = default_analysis_prompt(&categories);
    let mut all_findings: Vec<AnalysisFinding> = Vec::new();

    for name in &agent_names {
        let agent = match registry.select_agent(Some(name)).await {
            Ok(a) => a,
            Err(e) => {
                warn!("Skipping agent {}: {}", name, e);
                continue;
            },
        };
        info!("Running analysis with agent: {}", name);
        let analyzer = AgentAnalyzer::new(name.clone(), agent, prompt.clone(), categories.clone())
            .with_include_paths(include.clone())
            .with_exclude_paths(exclude.clone());
        match analyzer.analyze(&repo_path).await {
            Ok(findings) => {
                info!("Agent {} found {} findings", name, findings.len());
                all_findings.extend(findings);
            },
            Err(e) => error!("Agent {} analysis failed: {}", name, e),
        }
    }
    info!("Total findings from all agents: {}", all_findings.len());

    let mut creator = IssueCreator::new(&repo)
        .with_min_priority(min_priority)
        .with_max_issues(opts.max_issues)
        .with_dry_run(opts.dry_run);
    let results = creator.create_issues(all_findings).await?;
    print_analysis_results(&results, opts.dry_run, opts.json)
}

fn print_analysis_results(
    results: &[CreationResult],
    dry_run: bool,
    as_json: bool,
) -> Result<(), Error> {
    let created = results.iter().filter(|r| r.created).count();
    let skipped = results.len() - created;

    if as_json {
        let output = json!({
            "findings": results.iter().map(|r| &r.finding).collect::<Vec<_>>(),
            "count": results.len(),
            "created": created,
            "skipped": skipped,
            "dry_run": dry_run,
            "results": results,
        });
        println!("{}", serde_json::to_string_pretty(&output)?);
        return Ok(());
    }

    println!(
        "Analysis complete: {} findings, {} issues created, {} skipped",
        results.len(),
        created,
        skipped
    );
    for r in results {
        if r.created {
            println!(
                "  [CREATED] #{}: {}",
                r.issue_number.unwrap_or(0),
                r.finding.title
            );
        } else if let Some(reason) = &r.skipped_reason {
            println!("  [SKIPPED] {}: {}", r.finding.title, reason);
        }
    }
    Ok(())
}

/// Print a security command result and convert a negative outcome into
/// `Error::SecurityCheck` (exit code 8).
fn report(as_json: bool, ok: bool, value: serde_json::Value, text: String) -> Result<(), Error> {
    if as_json {
        println!("{}", serde_json::to_string_pretty(&value)?);
    } else {
        println!("{}", text);
    }
    if ok {
        Ok(())
    } else {
        Err(Error::SecurityCheck(text))
    }
}

/// `security ...`
pub async fn security(cmd: SecurityCommand, config: &Path, as_json: bool) -> Result<(), Error> {
    match cmd {
        SecurityCommand::CheckUser { username } => {
            let allowed = load_security(config, false)?.is_user_allowed(&username);
            report(
                as_json,
                allowed,
                json!({ "username": username, "allowed": allowed }),
                format!(
                    "User '{}' is {}",
                    username,
                    if allowed { "allowed" } else { "NOT allowed" }
                ),
            )
        },
        SecurityCommand::CheckAction { action } => {
            let allowed = load_security(config, false)?.is_action_allowed(&action);
            report(
                as_json,
                allowed,
                json!({ "action": action, "allowed": allowed }),
                format!(
                    "Action '{}' is {}",
                    action,
                    if allowed { "allowed" } else { "NOT allowed" }
                ),
            )
        },
        SecurityCommand::ValidatePrCommit {
            pr,
            expected_sha,
            repo,
        } => validate_pr_commit(pr, &expected_sha, repo, as_json).await,
        SecurityCommand::ParseTrigger { comment } => {
            let parsed = parse_trigger(&comment);
            let value = json!({
                "found": parsed.is_some(),
                "action": parsed.as_ref().map(|t| t.action.clone()),
                "agent": parsed.as_ref().and_then(|t| t.agent.clone()),
            });
            let text = match &parsed {
                Some(t) => format!(
                    "Trigger: action={} agent={}",
                    t.action,
                    t.agent.as_deref().unwrap_or("(none)")
                ),
                None => "No trigger found".to_string(),
            };
            report(as_json, true, value, text)
        },
    }
}

async fn validate_pr_commit(
    pr: u64,
    expected_sha: &str,
    repo: Option<String>,
    as_json: bool,
) -> Result<(), Error> {
    if !is_valid_sha(expected_sha) {
        return Err(Error::Config(format!(
            "--expected-sha must be 7-64 hex characters, got {:?}",
            expected_sha
        )));
    }
    let repo = match repo {
        Some(r) => r,
        None => resolve_repository().await?,
    };
    let head = fetch_pr_head(&repo, pr).await?;
    let ok = sha_matches(expected_sha, &head.sha);
    report(
        as_json,
        ok,
        json!({
            "pr": pr,
            "expected_sha": expected_sha,
            "head_sha": head.sha,
            "valid": ok,
        }),
        if ok {
            format!("PR #{} head {} matches {}", pr, head.sha, expected_sha)
        } else {
            format!(
                "PR #{} head {} does not match approved commit {}",
                pr, head.sha, expected_sha
            )
        },
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_split_list() {
        assert_eq!(split_list(" a, b ,,c "), vec!["a", "b", "c"]);
        assert!(split_list("").is_empty());
    }

    #[test]
    fn test_report_exit_semantics() {
        assert!(report(false, true, json!({}), "ok".into()).is_ok());
        let err = report(false, false, json!({}), "denied".into()).unwrap_err();
        assert_eq!(err.exit_code(), 8);
    }

    #[test]
    fn test_load_security_missing_file_defaults() {
        let m = load_security(Path::new("definitely/not/here.yaml"), false).unwrap();
        assert!(m.is_action_allowed("issue_approved"));
    }

    #[test]
    fn test_load_security_invalid_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("bad.yaml");
        std::fs::write(&path, "security:\n  agent_admins: 5\n").unwrap();
        assert!(load_security(&path, false).is_err());
        assert!(load_security(&path, true).is_ok());
    }
}
