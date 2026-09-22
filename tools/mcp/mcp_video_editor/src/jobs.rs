//! Job tracking for long-running video operations.
//!
//! Every heavy tool call (analysis, rendering, clip extraction, captioning)
//! runs as a job. In the default *foreground* mode the tool call awaits the
//! job and returns its result; in *background* mode it returns the job id
//! immediately and the caller polls `video_editor/get_job_status`.
//!
//! Jobs run on their own tokio task, so a background job can be cancelled
//! (`video_editor/cancel_job`): aborting the task drops the in-flight
//! subprocess future, and `kill_on_drop` terminates ffmpeg/whisper. A panic
//! inside a job is caught at the task boundary and recorded as a failure.
//!
//! Concurrency of heavy work is bounded by a semaphore sized from
//! `MAX_PARALLEL_JOBS`; finished jobs are pruned beyond `MAX_RETAINED_JOBS`.

use std::collections::HashMap;
use std::future::Future;
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use tokio::sync::{RwLock, Semaphore};
use tokio::task::AbortHandle;

/// Job status.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum JobStatus {
    Pending,
    Running,
    Completed,
    Failed,
    Cancelled,
}

impl JobStatus {
    /// Whether the job has reached a terminal state.
    pub fn is_finished(self) -> bool {
        matches!(self, Self::Completed | Self::Failed | Self::Cancelled)
    }

    /// Parse a status name.
    pub fn parse(s: &str) -> Option<Self> {
        match s.trim().to_ascii_lowercase().as_str() {
            "pending" => Some(Self::Pending),
            "running" => Some(Self::Running),
            "completed" => Some(Self::Completed),
            "failed" => Some(Self::Failed),
            "cancelled" | "canceled" => Some(Self::Cancelled),
            _ => None,
        }
    }
}

/// A job tracking a long-running operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Job {
    pub id: String,
    pub operation: String,
    pub status: JobStatus,
    pub progress: u32,
    pub stage: String,
    pub created_at: DateTime<Utc>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub updated_at: Option<DateTime<Utc>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub result: Option<serde_json::Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

impl Job {
    fn new(operation: &str, counter: u64) -> Self {
        Self {
            id: format!("job_{counter}_{operation}"),
            operation: operation.to_string(),
            status: JobStatus::Pending,
            progress: 0,
            stage: "queued".to_string(),
            created_at: Utc::now(),
            updated_at: None,
            result: None,
            error: None,
        }
    }

    fn touch(&mut self) {
        self.updated_at = Some(Utc::now());
    }
}

struct Entry {
    job: Job,
    abort: Option<AbortHandle>,
}

/// Registry of all jobs plus the heavy-work semaphore.
pub struct JobManager {
    jobs: RwLock<HashMap<String, Entry>>,
    counter: AtomicU64,
    permits: Arc<Semaphore>,
    max_retained: usize,
}

/// Handle passed into a running job for progress reporting.
#[derive(Clone)]
pub struct JobContext {
    manager: Arc<JobManager>,
    id: String,
}

impl JobContext {
    /// Report progress (0-100) and the current stage.
    pub async fn progress(&self, progress: u32, stage: &str) {
        self.manager.update(&self.id, progress.min(99), stage).await;
    }
}

impl JobManager {
    /// Create a manager allowing `max_parallel` concurrent heavy jobs.
    pub fn new(max_parallel: usize, max_retained: usize) -> Self {
        Self {
            jobs: RwLock::new(HashMap::new()),
            counter: AtomicU64::new(0),
            permits: Arc::new(Semaphore::new(max_parallel.max(1))),
            max_retained: max_retained.max(1),
        }
    }

    /// Create and spawn a job running `work`.
    ///
    /// Returns the job id and a receiver that resolves when the job ends
    /// (useful for foreground execution). The job waits for a concurrency
    /// permit before starting.
    pub async fn spawn<F, Fut>(
        self: &Arc<Self>,
        operation: &str,
        work: F,
    ) -> (String, tokio::sync::oneshot::Receiver<()>)
    where
        F: FnOnce(JobContext) -> Fut + Send + 'static,
        Fut: Future<Output = anyhow::Result<serde_json::Value>> + Send + 'static,
    {
        let counter = self.counter.fetch_add(1, Ordering::SeqCst);
        let job = Job::new(operation, counter);
        let id = job.id.clone();
        self.jobs
            .write()
            .await
            .insert(id.clone(), Entry { job, abort: None });
        self.prune().await;

        let ctx = JobContext {
            manager: Arc::clone(self),
            id: id.clone(),
        };
        let permits = Arc::clone(&self.permits);
        let inner = tokio::spawn(async move {
            let _permit = permits.acquire_owned().await;
            ctx.manager
                .update_status(&ctx.id, JobStatus::Running, 1, "starting")
                .await;
            work(ctx).await
        });

        // Register the abort handle before the supervisor can observe the end.
        if let Some(entry) = self.jobs.write().await.get_mut(&id) {
            entry.abort = Some(inner.abort_handle());
        }

        let (done_tx, done_rx) = tokio::sync::oneshot::channel();
        let manager = Arc::clone(self);
        let sup_id = id.clone();
        tokio::spawn(async move {
            match inner.await {
                Ok(Ok(result)) => manager.finish(&sup_id, Ok(result)).await,
                Ok(Err(e)) => manager.finish(&sup_id, Err(format!("{e:#}"))).await,
                Err(join) if join.is_cancelled() => {},
                Err(join) => {
                    manager
                        .finish(&sup_id, Err(format!("job panicked: {join}")))
                        .await;
                },
            }
            let _ = done_tx.send(());
        });
        (id, done_rx)
    }

    /// Get a snapshot of a job.
    pub async fn get_job(&self, job_id: &str) -> Option<Job> {
        self.jobs.read().await.get(job_id).map(|e| e.job.clone())
    }

    /// List jobs (newest first), optionally filtered by status.
    pub async fn list(&self, status: Option<JobStatus>) -> Vec<Job> {
        let mut jobs: Vec<Job> = self
            .jobs
            .read()
            .await
            .values()
            .filter(|e| status.is_none_or(|s| e.job.status == s))
            .map(|e| {
                let mut j = e.job.clone();
                j.result = None; // keep listings compact
                j
            })
            .collect();
        jobs.sort_by(|a, b| {
            b.created_at
                .cmp(&a.created_at)
                .then_with(|| b.id.cmp(&a.id))
        });
        jobs
    }

    /// Cancel a pending/running job. Returns the job's state afterwards, or
    /// `None` if the id is unknown.
    pub async fn cancel(&self, job_id: &str) -> Option<Job> {
        let mut jobs = self.jobs.write().await;
        let entry = jobs.get_mut(job_id)?;
        if !entry.job.status.is_finished() {
            if let Some(abort) = entry.abort.take() {
                abort.abort();
            }
            entry.job.status = JobStatus::Cancelled;
            entry.job.stage = "cancelled".into();
            entry.job.error = Some("cancelled by request".into());
            entry.job.touch();
        }
        Some(entry.job.clone())
    }

    async fn update(&self, job_id: &str, progress: u32, stage: &str) {
        let mut jobs = self.jobs.write().await;
        if let Some(entry) = jobs.get_mut(job_id)
            && !entry.job.status.is_finished()
        {
            entry.job.progress = progress;
            entry.job.stage = stage.to_string();
            entry.job.touch();
            tracing::info!("Job {}: {}% - {}", job_id, progress, stage);
        }
    }

    async fn update_status(&self, job_id: &str, status: JobStatus, progress: u32, stage: &str) {
        let mut jobs = self.jobs.write().await;
        if let Some(entry) = jobs.get_mut(job_id)
            && !entry.job.status.is_finished()
        {
            entry.job.status = status;
            entry.job.progress = progress;
            entry.job.stage = stage.to_string();
            entry.job.touch();
        }
    }

    async fn finish(&self, job_id: &str, outcome: Result<serde_json::Value, String>) {
        let mut jobs = self.jobs.write().await;
        if let Some(entry) = jobs.get_mut(job_id) {
            entry.abort = None;
            if entry.job.status.is_finished() {
                return; // already cancelled
            }
            match outcome {
                Ok(result) => {
                    entry.job.status = JobStatus::Completed;
                    entry.job.progress = 100;
                    entry.job.stage = "done".into();
                    entry.job.result = Some(result);
                },
                Err(error) => {
                    tracing::warn!("Job {} failed: {}", job_id, error);
                    entry.job.status = JobStatus::Failed;
                    entry.job.stage = "failed".into();
                    entry.job.error = Some(error);
                },
            }
            entry.job.touch();
        }
    }

    /// Drop the oldest finished jobs beyond the retention limit.
    async fn prune(&self) {
        let mut jobs = self.jobs.write().await;
        if jobs.len() <= self.max_retained {
            return;
        }
        let mut finished: Vec<(DateTime<Utc>, String)> = jobs
            .values()
            .filter(|e| e.job.status.is_finished())
            .map(|e| (e.job.created_at, e.job.id.clone()))
            .collect();
        finished.sort();
        let excess = jobs.len() - self.max_retained;
        for (_, id) in finished.into_iter().take(excess) {
            jobs.remove(&id);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::time::Duration;

    fn manager() -> Arc<JobManager> {
        Arc::new(JobManager::new(2, 3))
    }

    #[tokio::test]
    async fn job_completes_with_result() {
        let m = manager();
        let (id, done) = m
            .spawn("test", |ctx| async move {
                ctx.progress(50, "halfway").await;
                Ok(json!({"ok": true}))
            })
            .await;
        done.await.unwrap();
        let job = m.get_job(&id).await.unwrap();
        assert_eq!(job.status, JobStatus::Completed);
        assert_eq!(job.progress, 100);
        assert_eq!(job.result, Some(json!({"ok": true})));
        assert!(id.starts_with("job_0_test"));
    }

    #[tokio::test]
    async fn job_failure_is_recorded() {
        let m = manager();
        let (id, done) = m.spawn("fail", |_| async { anyhow::bail!("boom") }).await;
        done.await.unwrap();
        let job = m.get_job(&id).await.unwrap();
        assert_eq!(job.status, JobStatus::Failed);
        assert_eq!(job.error.as_deref(), Some("boom"));
    }

    #[tokio::test]
    async fn job_panic_is_recorded_as_failure() {
        let m = manager();
        let (id, done) = m
            .spawn("panic", |_| async {
                if true {
                    panic!("kaboom");
                }
                Ok(json!(null))
            })
            .await;
        done.await.unwrap();
        let job = m.get_job(&id).await.unwrap();
        assert_eq!(job.status, JobStatus::Failed);
        assert!(job.error.unwrap().contains("panicked"));
    }

    #[tokio::test]
    async fn cancel_running_job() {
        let m = manager();
        let (id, done) = m
            .spawn("slow", |_| async {
                tokio::time::sleep(Duration::from_secs(30)).await;
                Ok(json!(null))
            })
            .await;
        tokio::time::sleep(Duration::from_millis(20)).await;
        let job = m.cancel(&id).await.unwrap();
        assert_eq!(job.status, JobStatus::Cancelled);
        tokio::time::timeout(Duration::from_secs(5), done)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(m.get_job(&id).await.unwrap().status, JobStatus::Cancelled);
        assert!(m.cancel("nope").await.is_none());
    }

    #[tokio::test]
    async fn concurrency_is_bounded() {
        let m = Arc::new(JobManager::new(1, 10));
        let (first, _d1) = m
            .spawn("a", |_| async {
                tokio::time::sleep(Duration::from_millis(300)).await;
                Ok(json!(1))
            })
            .await;
        let (second, d2) = m.spawn("b", |_| async { Ok(json!(2)) }).await;
        tokio::time::sleep(Duration::from_millis(50)).await;
        assert_eq!(m.get_job(&first).await.unwrap().status, JobStatus::Running);
        assert_eq!(m.get_job(&second).await.unwrap().status, JobStatus::Pending);
        d2.await.unwrap();
        assert_eq!(
            m.get_job(&second).await.unwrap().status,
            JobStatus::Completed
        );
    }

    #[tokio::test]
    async fn finished_jobs_are_pruned() {
        let m = manager();
        for _ in 0..6 {
            let (_, done) = m.spawn("x", |_| async { Ok(json!(null)) }).await;
            done.await.unwrap();
        }
        assert!(m.list(None).await.len() <= 4);
        let completed = m.list(Some(JobStatus::Completed)).await;
        assert!(
            completed.iter().all(|j| j.result.is_none()),
            "listings omit results"
        );
    }

    #[test]
    fn status_parsing() {
        assert_eq!(JobStatus::parse("Running"), Some(JobStatus::Running));
        assert_eq!(JobStatus::parse("canceled"), Some(JobStatus::Cancelled));
        assert_eq!(JobStatus::parse("x"), None);
    }
}
