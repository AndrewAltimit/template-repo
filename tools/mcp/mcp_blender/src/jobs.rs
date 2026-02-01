//! Job management for async Blender operations.

use crate::types::{Job, JobStatus};
use chrono::Utc;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, info, warn};
use uuid::Uuid;

/// Job manager for tracking async operations
pub struct JobManager {
    jobs: Arc<RwLock<HashMap<Uuid, Job>>>,
}

impl JobManager {
    /// Create a new job manager
    pub fn new() -> Self {
        Self {
            jobs: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Create a new job
    pub async fn create_job(&self, job_type: &str) -> Uuid {
        let job = Job::new(job_type);
        let id = job.id;

        let mut jobs = self.jobs.write().await;
        jobs.insert(id, job);

        info!("Created job {} of type {}", id, job_type);
        id
    }

    /// Create a job with a specific ID
    pub async fn create_job_with_id(&self, id: Uuid, job_type: &str) -> Uuid {
        let job = Job::new(job_type).with_id(id);

        let mut jobs = self.jobs.write().await;
        jobs.insert(id, job);

        info!("Created job {} of type {}", id, job_type);
        id
    }

    /// Get a job by ID
    pub async fn get_job(&self, id: Uuid) -> Option<Job> {
        let jobs = self.jobs.read().await;
        jobs.get(&id).cloned()
    }

    /// Update job status
    pub async fn update_status(&self, id: Uuid, status: JobStatus, message: Option<&str>) {
        let mut jobs = self.jobs.write().await;
        if let Some(job) = jobs.get_mut(&id) {
            job.status = status;
            job.updated_at = Some(Utc::now());
            if let Some(msg) = message {
                job.message = msg.to_string();
            }
            debug!("Updated job {} status to {}", id, status);
        } else {
            warn!("Job {} not found when updating status", id);
        }
    }

    /// Update job progress
    pub async fn update_progress(&self, id: Uuid, progress: u8) {
        let mut jobs = self.jobs.write().await;
        if let Some(job) = jobs.get_mut(&id) {
            job.progress = progress.min(100);
            job.updated_at = Some(Utc::now());
            debug!("Updated job {} progress to {}%", id, progress);
        }
    }

    /// Mark job as completed with result
    pub async fn complete_job(&self, id: Uuid, result: serde_json::Value, output_path: Option<&str>) {
        let mut jobs = self.jobs.write().await;
        if let Some(job) = jobs.get_mut(&id) {
            job.status = JobStatus::Completed;
            job.progress = 100;
            job.updated_at = Some(Utc::now());
            job.result = Some(result);
            if let Some(path) = output_path {
                job.output_path = Some(path.to_string());
            }
            info!("Job {} completed", id);
        }
    }

    /// Mark job as failed with error
    pub async fn fail_job(&self, id: Uuid, error: &str) {
        let mut jobs = self.jobs.write().await;
        if let Some(job) = jobs.get_mut(&id) {
            job.status = JobStatus::Failed;
            job.updated_at = Some(Utc::now());
            job.error = Some(error.to_string());
            warn!("Job {} failed: {}", id, error);
        }
    }

    /// Cancel a job
    pub async fn cancel_job(&self, id: Uuid) -> bool {
        let mut jobs = self.jobs.write().await;
        if let Some(job) = jobs.get_mut(&id) {
            if job.status == JobStatus::Queued || job.status == JobStatus::Running {
                job.status = JobStatus::Cancelled;
                job.updated_at = Some(Utc::now());
                info!("Job {} cancelled", id);
                return true;
            }
        }
        false
    }

    /// List all jobs
    pub async fn list_jobs(&self) -> Vec<Job> {
        let jobs = self.jobs.read().await;
        jobs.values().cloned().collect()
    }

    /// Clean up old completed jobs (older than the specified hours)
    pub async fn cleanup_old_jobs(&self, hours: i64) {
        let cutoff = Utc::now() - chrono::Duration::hours(hours);
        let mut jobs = self.jobs.write().await;

        let old_jobs: Vec<Uuid> = jobs
            .iter()
            .filter(|(_, job)| {
                matches!(
                    job.status,
                    JobStatus::Completed | JobStatus::Failed | JobStatus::Cancelled
                ) && job.updated_at.map_or(job.created_at, |t| t) < cutoff
            })
            .map(|(id, _)| *id)
            .collect();

        for id in old_jobs {
            jobs.remove(&id);
            debug!("Cleaned up old job {}", id);
        }
    }
}

impl Default for JobManager {
    fn default() -> Self {
        Self::new()
    }
}

impl Clone for JobManager {
    fn clone(&self) -> Self {
        Self {
            jobs: self.jobs.clone(),
        }
    }
}
