//! In-memory registry for asynchronous Blender jobs.
//!
//! State transitions are monotonic: `QUEUED -> RUNNING -> {COMPLETED | FAILED}`
//! and `QUEUED | RUNNING -> CANCELLED`. Once a job is terminal nothing can
//! change it, so a worker finishing after a cancellation cannot resurrect the
//! job as "completed". Each job owns a cancellation signal that its worker
//! watches; [`JobManager::cancel`] flips it, which kills the Blender process.
//!
//! The lock is a `std::sync::Mutex` held only for short, non-`await`ing
//! critical sections; poisoning is tolerated (the data stays consistent
//! because every mutation is a single assignment).

use crate::types::{Job, JobStatus};
use chrono::Utc;
use serde_json::Value;
use std::collections::HashMap;
use std::sync::{Arc, Mutex, MutexGuard};
use std::time::Duration;
use tokio::sync::watch;
use tracing::{debug, info, warn};
use uuid::Uuid;

/// Hard cap on remembered jobs; the oldest finished ones are dropped first.
const MAX_TRACKED_JOBS: usize = 1000;

/// Receiver side of a job's cancellation signal.
pub type CancelSignal = watch::Receiver<bool>;

struct Entry {
    job: Job,
    cancel: watch::Sender<bool>,
}

/// Why a cancellation request was refused.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum CancelError {
    /// Unknown (or already pruned) job id.
    #[error("job {0} not found")]
    NotFound(Uuid),
    /// The job already reached a terminal state.
    #[error("job {0} already finished with status {1}")]
    AlreadyFinished(Uuid, JobStatus),
}

/// Thread-safe, cloneable job registry.
#[derive(Clone)]
pub struct JobManager {
    inner: Arc<Mutex<HashMap<Uuid, Entry>>>,
    retention: Duration,
}

impl JobManager {
    /// Registry that forgets finished jobs after `retention`.
    pub fn new(retention: Duration) -> Self {
        Self {
            inner: Arc::new(Mutex::new(HashMap::new())),
            retention,
        }
    }

    fn lock(&self) -> MutexGuard<'_, HashMap<Uuid, Entry>> {
        self.inner
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    /// Register a new queued job; returns its id and cancellation signal.
    pub fn create(&self, job_type: &str, project: Option<String>) -> (Uuid, CancelSignal) {
        let mut job = Job::new(job_type);
        job.project = project;
        let id = job.id;
        let (tx, rx) = watch::channel(false);
        let mut jobs = self.lock();
        Self::prune_locked(&mut jobs, self.retention);
        jobs.insert(id, Entry { job, cancel: tx });
        info!("Created job {} ({})", id, job_type);
        (id, rx)
    }

    /// Snapshot of one job.
    pub fn get(&self, id: Uuid) -> Option<Job> {
        self.lock().get(&id).map(|e| e.job.clone())
    }

    /// Snapshot of all jobs, newest first (expired jobs are pruned first).
    pub fn list(&self) -> Vec<Job> {
        let mut guard = self.lock();
        Self::prune_locked(&mut guard, self.retention);
        let mut jobs: Vec<Job> = guard.values().map(|e| e.job.clone()).collect();
        drop(guard);
        jobs.sort_by_key(|job| std::cmp::Reverse(job.created_at));
        jobs
    }

    /// `(queued, running, total)` counts.
    pub fn counts(&self) -> (usize, usize, usize) {
        let jobs = self.lock();
        let queued = jobs
            .values()
            .filter(|e| e.job.status == JobStatus::Queued)
            .count();
        let running = jobs
            .values()
            .filter(|e| e.job.status == JobStatus::Running)
            .count();
        (queued, running, jobs.len())
    }

    /// `QUEUED -> RUNNING`. Returns false if the job is gone or not queued
    /// (e.g. cancelled while waiting for a slot).
    pub fn mark_running(&self, id: Uuid) -> bool {
        let mut jobs = self.lock();
        match jobs.get_mut(&id) {
            Some(entry) if entry.job.status == JobStatus::Queued => {
                let now = Utc::now();
                entry.job.status = JobStatus::Running;
                entry.job.message = "Blender started".to_string();
                entry.job.started_at = Some(now);
                entry.job.updated_at = Some(now);
                true
            },
            _ => false,
        }
    }

    /// Record progress for a running job (ignored in any other state).
    pub fn update_progress(&self, id: Uuid, progress: u8, message: Option<&str>) {
        let mut jobs = self.lock();
        if let Some(entry) = jobs.get_mut(&id)
            && entry.job.status == JobStatus::Running
        {
            // Progress never goes backwards and 100 is reserved for completion.
            entry.job.progress = entry.job.progress.max(progress.min(99));
            if let Some(msg) = message.filter(|m| !m.is_empty()) {
                entry.job.message = msg.to_string();
            }
            entry.job.updated_at = Some(Utc::now());
            debug!("Job {} progress {}%", id, entry.job.progress);
        }
    }

    /// Finish a job successfully. Returns false if it was already terminal.
    pub fn complete(&self, id: Uuid, result: Value, output_path: Option<String>) -> bool {
        self.finish(id, |job| {
            job.status = JobStatus::Completed;
            job.progress = 100;
            job.message = "Completed".to_string();
            job.result = Some(result);
            if output_path.is_some() {
                job.output_path = output_path;
            }
        })
    }

    /// Finish a job with an error. Returns false if it was already terminal.
    pub fn fail(&self, id: Uuid, error: &str) -> bool {
        let error = error.to_string();
        self.finish(id, |job| {
            job.status = JobStatus::Failed;
            job.message = "Failed".to_string();
            job.error = Some(error);
        })
    }

    fn finish(&self, id: Uuid, apply: impl FnOnce(&mut Job)) -> bool {
        let mut jobs = self.lock();
        match jobs.get_mut(&id) {
            Some(entry) if !entry.job.status.is_terminal() => {
                apply(&mut entry.job);
                let now = Utc::now();
                entry.job.updated_at = Some(now);
                entry.job.finished_at = Some(now);
                info!("Job {} finished: {}", id, entry.job.status);
                true
            },
            Some(entry) => {
                debug!(
                    "Ignoring late result for job {} (already {})",
                    id, entry.job.status
                );
                false
            },
            None => {
                warn!("Result for unknown job {}", id);
                false
            },
        }
    }

    /// Cancel a queued or running job and signal its worker to kill Blender.
    pub fn cancel(&self, id: Uuid) -> Result<Job, CancelError> {
        let mut jobs = self.lock();
        let entry = jobs.get_mut(&id).ok_or(CancelError::NotFound(id))?;
        if entry.job.status.is_terminal() {
            return Err(CancelError::AlreadyFinished(id, entry.job.status));
        }
        let now = Utc::now();
        entry.job.status = JobStatus::Cancelled;
        entry.job.message = "Cancelled by request".to_string();
        entry.job.updated_at = Some(now);
        entry.job.finished_at = Some(now);
        // Receivers may already be gone if the worker just exited; that's fine.
        let _ = entry.cancel.send(true);
        info!("Job {} cancelled", id);
        Ok(entry.job.clone())
    }

    /// Drop finished jobs older than the retention window (and, if still over
    /// [`MAX_TRACKED_JOBS`], the oldest finished jobs).
    #[cfg(test)]
    pub fn prune(&self) {
        let mut jobs = self.lock();
        Self::prune_locked(&mut jobs, self.retention);
    }

    fn prune_locked(jobs: &mut HashMap<Uuid, Entry>, retention: Duration) {
        let cutoff =
            Utc::now() - chrono::Duration::from_std(retention).unwrap_or(chrono::Duration::MAX);
        jobs.retain(|_, e| {
            !(e.job.status.is_terminal() && e.job.finished_at.unwrap_or(e.job.created_at) < cutoff)
        });
        if jobs.len() >= MAX_TRACKED_JOBS {
            let mut finished: Vec<(Uuid, chrono::DateTime<Utc>)> = jobs
                .iter()
                .filter(|(_, e)| e.job.status.is_terminal())
                .map(|(id, e)| (*id, e.job.finished_at.unwrap_or(e.job.created_at)))
                .collect();
            finished.sort_by_key(|(_, t)| *t);
            let excess = jobs.len() + 1 - MAX_TRACKED_JOBS;
            for (id, _) in finished.into_iter().take(excess) {
                jobs.remove(&id);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn manager() -> JobManager {
        JobManager::new(Duration::from_secs(3600))
    }

    #[test]
    fn create_and_get() {
        let m = manager();
        let (id, cancel) = m.create("render_image", Some("scene.blend".into()));
        let job = m.get(id).unwrap();
        assert_eq!(job.status, JobStatus::Queued);
        assert_eq!(job.job_type, "render_image");
        assert_eq!(job.project.as_deref(), Some("scene.blend"));
        assert!(!*cancel.borrow());
        assert!(m.get(Uuid::new_v4()).is_none());
    }

    #[test]
    fn full_lifecycle() {
        let m = manager();
        let (id, _) = m.create("render_image", None);
        assert!(m.mark_running(id));
        assert!(!m.mark_running(id), "cannot start twice");
        m.update_progress(id, 40, Some("frame 4/10"));
        let job = m.get(id).unwrap();
        assert_eq!((job.status, job.progress), (JobStatus::Running, 40));
        assert_eq!(job.message, "frame 4/10");
        assert!(job.started_at.is_some());

        assert!(m.complete(id, json!({"ok": true}), Some("/out/a.png".into())));
        let job = m.get(id).unwrap();
        assert_eq!(job.status, JobStatus::Completed);
        assert_eq!(job.progress, 100);
        assert_eq!(job.output_path.as_deref(), Some("/out/a.png"));
        assert!(job.finished_at.is_some());
    }

    #[test]
    fn progress_is_monotonic_and_capped_until_completion() {
        let m = manager();
        let (id, _) = m.create("bake", None);
        m.update_progress(id, 10, None);
        assert_eq!(m.get(id).unwrap().progress, 0, "ignored while queued");
        m.mark_running(id);
        m.update_progress(id, 60, None);
        m.update_progress(id, 30, None);
        assert_eq!(m.get(id).unwrap().progress, 60);
        m.update_progress(id, 250, None);
        assert_eq!(m.get(id).unwrap().progress, 99);
    }

    #[test]
    fn terminal_states_are_final() {
        let m = manager();
        let (id, _) = m.create("render", None);
        m.mark_running(id);
        assert!(m.fail(id, "boom"));
        assert!(!m.complete(id, json!({}), None));
        assert!(!m.fail(id, "again"));
        let job = m.get(id).unwrap();
        assert_eq!(job.status, JobStatus::Failed);
        assert_eq!(job.error.as_deref(), Some("boom"));
    }

    #[test]
    fn cancel_signals_worker_and_blocks_late_results() {
        let m = manager();
        let (id, cancel) = m.create("render", None);
        m.mark_running(id);
        let job = m.cancel(id).unwrap();
        assert_eq!(job.status, JobStatus::Cancelled);
        assert!(*cancel.borrow(), "worker must observe the cancellation");
        // The worker finishing afterwards must not overwrite the cancellation.
        assert!(!m.complete(id, json!({}), None));
        assert_eq!(m.get(id).unwrap().status, JobStatus::Cancelled);
    }

    #[test]
    fn cancel_while_queued_prevents_start() {
        let m = manager();
        let (id, _) = m.create("render", None);
        m.cancel(id).unwrap();
        assert!(!m.mark_running(id));
    }

    #[test]
    fn cancel_errors() {
        let m = manager();
        let missing = Uuid::new_v4();
        assert_eq!(
            m.cancel(missing).unwrap_err(),
            CancelError::NotFound(missing)
        );
        let (id, _) = m.create("render", None);
        m.mark_running(id);
        m.complete(id, json!({}), None);
        assert_eq!(
            m.cancel(id).unwrap_err(),
            CancelError::AlreadyFinished(id, JobStatus::Completed)
        );
    }

    #[test]
    fn list_is_newest_first_and_counts() {
        let m = manager();
        let (a, _) = m.create("a", None);
        std::thread::sleep(Duration::from_millis(5));
        let (b, _) = m.create("b", None);
        m.mark_running(b);
        let ids: Vec<Uuid> = m.list().iter().map(|j| j.id).collect();
        assert_eq!(ids, vec![b, a]);
        assert_eq!(m.counts(), (1, 1, 2));
    }

    #[test]
    fn prune_drops_expired_finished_jobs_only() {
        let m = JobManager::new(Duration::ZERO);
        let (done, _) = m.create("done", None);
        m.mark_running(done);
        m.complete(done, json!({}), None);
        let (active, _) = m.create("active", None);
        std::thread::sleep(Duration::from_millis(5));
        m.prune();
        assert!(m.get(done).is_none());
        assert!(m.get(active).is_some());
    }

    #[test]
    fn clones_share_state() {
        let m = manager();
        let clone = m.clone();
        let (id, _) = m.create("render", None);
        assert!(clone.mark_running(id));
        assert_eq!(m.get(id).unwrap().status, JobStatus::Running);
    }
}
