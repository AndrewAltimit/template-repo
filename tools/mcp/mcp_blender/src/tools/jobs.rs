//! Async job inspection and control.

use async_trait::async_trait;
use serde::Deserialize;
use serde_json::{Value, json};
use std::time::Duration;
use uuid::Uuid;

use crate::jobs::CancelError;
use crate::server::{BlenderTool, Ctx, ToolError, ToolOutput, enum_prop};
use crate::types::{Job, JobStatus};

/// Longest `wait_seconds` accepted by `get_job_status`.
const MAX_WAIT_SECS: u64 = 300;

fn parse_job_id(raw: &str) -> Result<Uuid, ToolError> {
    Uuid::parse_str(raw.trim()).map_err(|_| {
        ToolError::invalid(format!(
            "Invalid job_id '{raw}' (expected a UUID returned by a render/bake tool)"
        ))
    })
}

fn find_job(ctx: &Ctx, id: Uuid) -> Result<Job, ToolError> {
    ctx.jobs.get(id).ok_or_else(|| {
        ToolError::invalid(format!(
            "Job {id} not found (unknown id, or it finished more than the retention period ago)"
        ))
    })
}

fn status_json(job: &Job) -> Value {
    json!({
        "job_id": job.id.to_string(),
        "job_type": job.job_type,
        "project": job.project,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "error": job.error,
        "output_path": job.output_path,
        "created_at": job.created_at.to_rfc3339(),
        "started_at": job.started_at.map(|t| t.to_rfc3339()),
        "updated_at": job.updated_at.map(|t| t.to_rfc3339()),
        "finished_at": job.finished_at.map(|t| t.to_rfc3339()),
    })
}

/// `get_job_status` arguments.
#[derive(Debug, Deserialize)]
pub struct JobStatusArgs {
    job_id: String,
    #[serde(default)]
    wait_seconds: u64,
}

/// Report a job's state, optionally long-polling until it finishes.
pub struct GetJobStatus;

#[async_trait]
impl BlenderTool for GetJobStatus {
    type Args = JobStatusArgs;
    const NAME: &'static str = "get_job_status";
    const DESCRIPTION: &'static str = "Get the status and progress of an async job (render_image, render_animation, \
batch_render, bake_simulation). Status is one of QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED. \
Set wait_seconds (max 300) to block until the job finishes or the wait elapses, instead of polling.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "job_id": { "type": "string", "description": "Job ID returned by the tool that started the job" },
                "wait_seconds": { "type": "integer", "minimum": 0, "maximum": MAX_WAIT_SECS, "default": 0, "description": "Wait up to this many seconds for the job to finish" }
            },
            "required": ["job_id"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let id = parse_job_id(&args.job_id)?;
        let mut job = find_job(ctx, id)?;
        let wait = Duration::from_secs(args.wait_seconds.min(MAX_WAIT_SECS));
        let deadline = tokio::time::Instant::now() + wait;
        while !job.status.is_terminal() && tokio::time::Instant::now() < deadline {
            tokio::time::sleep(Duration::from_millis(250)).await;
            job = find_job(ctx, id)?;
        }
        Ok(status_json(&job))
    }
}

/// `get_job_result` / `cancel_job` arguments.
#[derive(Debug, Deserialize)]
pub struct JobIdArgs {
    job_id: String,
}

/// Return the result of a finished job.
pub struct GetJobResult;

#[async_trait]
impl BlenderTool for GetJobResult {
    type Args = JobIdArgs;
    const NAME: &'static str = "get_job_result";
    const DESCRIPTION: &'static str = "Get the result of a finished job: output_path (image, video, frame directory or \
batch directory) plus the script's result (e.g. output_files for batch_render). For failed jobs returns the error; \
for jobs still running returns the current status.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": { "job_id": { "type": "string", "description": "Job ID to retrieve" } },
            "required": ["job_id"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let id = parse_job_id(&args.job_id)?;
        let job = find_job(ctx, id)?;
        match job.status {
            JobStatus::Completed => Ok(json!({
                "success": true,
                "job_id": id.to_string(),
                "status": job.status,
                "output_path": job.output_path,
                "result": job.result,
            })),
            JobStatus::Failed => Err(ToolError::failed(format!(
                "Job {id} failed: {}",
                job.error.as_deref().unwrap_or("unknown error")
            ))),
            JobStatus::Cancelled => Err(ToolError::failed(format!("Job {id} was cancelled"))),
            JobStatus::Queued | JobStatus::Running => Ok(json!({
                "success": false,
                "job_id": id.to_string(),
                "status": job.status,
                "progress": job.progress,
                "message": format!("Job {id} is not finished yet ({}); use get_job_status with wait_seconds", job.status),
            })),
        }
    }
}

/// Cancel a queued or running job, killing its Blender process.
pub struct CancelJob;

#[async_trait]
impl BlenderTool for CancelJob {
    type Args = JobIdArgs;
    const NAME: &'static str = "cancel_job";
    const DESCRIPTION: &'static str = "Cancel a queued or running job. A running Blender process is killed; partial \
output files may remain.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": { "job_id": { "type": "string", "description": "Job ID to cancel" } },
            "required": ["job_id"]
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let id = parse_job_id(&args.job_id)?;
        match ctx.jobs.cancel(id) {
            Ok(job) => Ok(json!({
                "success": true,
                "job_id": id.to_string(),
                "status": job.status,
                "message": format!("Job {id} cancelled"),
            })),
            Err(e @ CancelError::NotFound(_)) => Err(ToolError::invalid(e.to_string())),
            Err(e @ CancelError::AlreadyFinished(..)) => {
                Err(ToolError::failed(format!("Could not cancel: {e}")))
            },
        }
    }
}

/// `list_jobs` arguments.
#[derive(Debug, Deserialize)]
pub struct ListJobsArgs {
    #[serde(default)]
    status: Option<JobStatus>,
    #[serde(default = "default_limit")]
    limit: usize,
}

fn default_limit() -> usize {
    50
}

/// List known jobs, newest first.
pub struct ListJobs;

#[async_trait]
impl BlenderTool for ListJobs {
    type Args = ListJobsArgs;
    const NAME: &'static str = "list_jobs";
    const DESCRIPTION: &'static str = "List async jobs (newest first), optionally filtered by status. Finished jobs are \
kept for BLENDER_JOB_RETENTION_HOURS (default 24) and are lost when the server restarts.";

    fn schema() -> Value {
        json!({
            "type": "object",
            "properties": {
                "status": enum_prop(JobStatus::ALL, None, "Only jobs in this state"),
                "limit": { "type": "integer", "minimum": 1, "maximum": 1000, "default": 50 }
            }
        })
    }

    async fn run(ctx: &Ctx, args: Self::Args) -> ToolOutput {
        let limit = args.limit.clamp(1, 1000);
        let jobs: Vec<Value> = ctx
            .jobs
            .list()
            .iter()
            .filter(|j| args.status.is_none_or(|s| j.status == s))
            .take(limit)
            .map(status_json)
            .collect();
        Ok(json!({ "success": true, "count": jobs.len(), "jobs": jobs }))
    }
}
