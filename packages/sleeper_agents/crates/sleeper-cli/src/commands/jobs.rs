use std::time::Duration;

use anyhow::Result;
use clap::Subcommand;
use sleeper_api_client::{JobResponse, JobStatus};
use sleeper_orchestrator::output;

use crate::common::orchestrator_client;

#[derive(Subcommand)]
pub enum JobsAction {
    /// List jobs (optionally filtered by status or type)
    List {
        /// Filter by status: queued, running, completed, failed, cancelled
        #[arg(long)]
        status: Option<String>,

        /// Filter by job type: train_backdoor, train_probes, etc.
        #[arg(long, name = "type")]
        job_type: Option<String>,

        /// Maximum number of jobs to show
        #[arg(long, default_value = "20")]
        limit: u32,

        /// Output as JSON
        #[arg(long)]
        json: bool,
    },

    /// Show detailed status of a specific job
    Status {
        /// Job ID (UUID)
        job_id: String,

        /// Output as JSON
        #[arg(long)]
        json: bool,
    },

    /// Show job logs
    Logs {
        /// Job ID (UUID)
        job_id: String,

        /// Number of lines to show
        #[arg(long, default_value = "100")]
        tail: u32,

        /// Follow logs in real-time (polls every 2s)
        #[arg(long, short)]
        follow: bool,
    },

    /// Cancel a running or queued job
    Cancel {
        /// Job ID (UUID)
        job_id: String,
    },

    /// Remove completed/failed job records
    Clean {
        /// Remove completed jobs
        #[arg(long)]
        completed: bool,

        /// Remove failed jobs
        #[arg(long)]
        failed: bool,
    },
}

pub async fn run(action: JobsAction) -> Result<()> {
    let client = orchestrator_client()?;

    match action {
        JobsAction::List {
            status,
            job_type,
            limit,
            json,
        } => {
            let resp = client
                .list_jobs(status.as_deref(), job_type.as_deref(), limit, 0)
                .await
                .map_err(|e| anyhow::anyhow!("Failed to list jobs: {e}"))?;

            if json {
                println!("{}", serde_json::to_string_pretty(&resp.jobs)?);
                return Ok(());
            }

            if resp.jobs.is_empty() {
                output::info("No jobs found");
                return Ok(());
            }

            output::header(&format!("Jobs ({}/{})", resp.jobs.len(), resp.total));

            // Table header
            eprintln!(
                "  {:<36}  {:<16}  {:<10}  {:<6}  CREATED",
                "ID", "TYPE", "STATUS", "PROG"
            );
            eprintln!("  {}", "-".repeat(90));

            for job in &resp.jobs {
                let status_colored = format_status(&job.status);
                let created = truncate_timestamp(&job.created_at);
                let progress = if job.progress > 0.0 {
                    format!("{:.0}%", job.progress)
                } else {
                    "-".to_string()
                };

                eprintln!(
                    "  {:<36}  {:<16}  {:<10}  {:<6}  {}",
                    job.job_id, job.job_type, status_colored, progress, created
                );
            }
            Ok(())
        },

        JobsAction::Status { job_id, json } => {
            let job = client
                .get_job(&job_id)
                .await
                .map_err(|e| anyhow::anyhow!("Failed to get job: {e}"))?;

            if json {
                // Re-serialize the job (it's already deserialized, so re-fetch as raw)
                let raw: serde_json::Value = serde_json::to_value(&job)?;
                println!("{}", serde_json::to_string_pretty(&raw)?);
                return Ok(());
            }

            print_job_detail(&job);
            Ok(())
        },

        JobsAction::Logs {
            job_id,
            tail,
            follow,
        } => {
            if follow {
                return follow_logs(&client, &job_id, tail).await;
            }

            let logs = client
                .get_logs(&job_id, tail)
                .await
                .map_err(|e| anyhow::anyhow!("Failed to get logs: {e}"))?;

            if logs.trim().is_empty() {
                output::info("No logs available yet");
            } else {
                print!("{logs}");
            }
            Ok(())
        },

        JobsAction::Cancel { job_id } => {
            client
                .cancel_job(&job_id)
                .await
                .map_err(|e| anyhow::anyhow!("Failed to cancel job: {e}"))?;

            output::success(&format!("Job {job_id} cancelled"));
            Ok(())
        },

        JobsAction::Clean { completed, failed } => {
            if !completed && !failed {
                output::warn("Specify --completed and/or --failed");
                return Ok(());
            }

            let resp = client
                .list_jobs(None, None, 1000, 0)
                .await
                .map_err(|e| anyhow::anyhow!("Failed to list jobs: {e}"))?;

            let mut cleaned = 0u32;
            for job in &resp.jobs {
                let should_clean = (completed && job.status == JobStatus::Completed)
                    || (failed && job.status == JobStatus::Failed);

                if should_clean && client.cancel_job(&job.job_id).await.is_ok() {
                    cleaned += 1;
                }
            }

            output::success(&format!("Cleaned {cleaned} jobs"));
            Ok(())
        },
    }
}

fn print_job_detail(job: &JobResponse) {
    output::header(&format!("Job: {}", job.job_id));
    output::detail(&format!("Type:      {}", job.job_type));
    output::detail(&format!("Status:    {}", format_status(&job.status)));
    output::detail(&format!("Progress:  {:.1}%", job.progress));
    output::detail(&format!("Created:   {}", job.created_at));

    if let Some(ref started) = job.started_at {
        output::detail(&format!("Started:   {started}"));
    }
    if let Some(ref completed) = job.completed_at {
        output::detail(&format!("Completed: {completed}"));
    }
    if let Some(ref container) = job.container_id {
        output::detail(&format!("Container: {container}"));
    }
    if let Some(ref result) = job.result_path {
        output::detail(&format!("Results:   {result}"));
    }
    if let Some(ref error) = job.error_message {
        output::fail(&format!("Error: {error}"));
    }

    // Show parameters
    if let Some(params) = job.parameters.as_object()
        && !params.is_empty()
    {
        output::subheader("Parameters");
        for (key, val) in params {
            let val_str = match val {
                serde_json::Value::String(s) => s.clone(),
                other => other.to_string(),
            };
            output::detail(&format!("{key}: {val_str}"));
        }
    }
}

fn format_status(status: &JobStatus) -> String {
    match status {
        JobStatus::Queued => "queued".to_string(),
        JobStatus::Running => "RUNNING".to_string(),
        JobStatus::Completed => "done".to_string(),
        JobStatus::Failed => "FAILED".to_string(),
        JobStatus::Cancelled => "cancelled".to_string(),
    }
}

fn truncate_timestamp(ts: &str) -> &str {
    // Show just date + time, not microseconds
    if ts.len() > 19 { &ts[..19] } else { ts }
}

/// Poll the logs endpoint repeatedly until the job finishes.
async fn follow_logs(
    client: &sleeper_api_client::OrchestratorClient,
    job_id: &str,
    initial_tail: u32,
) -> Result<()> {
    let mut lines_seen = 0u32;
    let poll_interval = Duration::from_secs(2);

    // First fetch
    match client.get_logs(job_id, initial_tail).await {
        Ok(logs) => {
            let text = logs.trim_end();
            if !text.is_empty() {
                println!("{text}");
                lines_seen = text.lines().count() as u32;
            }
        },
        Err(e) => {
            output::warn(&format!("Could not fetch logs: {e}"));
        },
    }

    loop {
        tokio::time::sleep(poll_interval).await;

        // Check job status
        let job = match client.get_job(job_id).await {
            Ok(j) => j,
            Err(_) => continue,
        };

        // Fetch new logs (ask for more than we've seen)
        let fetch_count = lines_seen + 200;
        if let Ok(logs) = client.get_logs(job_id, fetch_count).await {
            let all_lines: Vec<&str> = logs.trim_end().lines().collect();
            let total = all_lines.len() as u32;

            if total > lines_seen {
                // Print only the new lines
                let new_start = if total <= fetch_count {
                    lines_seen as usize
                } else {
                    0
                };
                for line in &all_lines[new_start..] {
                    println!("{line}");
                }
                lines_seen = total;
            }
        }

        // Stop following when job is done
        match job.status {
            JobStatus::Completed => {
                output::success("Job completed");
                break;
            },
            JobStatus::Failed => {
                output::fail("Job failed");
                if let Some(ref err) = job.error_message {
                    output::detail(&format!("Error: {err}"));
                }
                break;
            },
            JobStatus::Cancelled => {
                output::warn("Job cancelled");
                break;
            },
            _ => {},
        }
    }

    Ok(())
}
