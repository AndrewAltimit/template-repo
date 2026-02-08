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
    pub async fn complete_job(
        &self,
        id: Uuid,
        result: serde_json::Value,
        output_path: Option<&str>,
    ) {
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
        if let Some(job) = jobs.get_mut(&id)
            && (job.status == JobStatus::Queued || job.status == JobStatus::Running)
        {
            job.status = JobStatus::Cancelled;
            job.updated_at = Some(Utc::now());
            info!("Job {} cancelled", id);
            return true;
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

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_job_manager_creation() {
        let manager = JobManager::new();
        let jobs = manager.list_jobs().await;
        assert!(jobs.is_empty());
    }

    #[tokio::test]
    async fn test_create_job() {
        let manager = JobManager::new();
        let job_id = manager.create_job("render").await;

        let job = manager.get_job(job_id).await;
        assert!(job.is_some());
        let job = job.unwrap();
        assert_eq!(job.job_type, "render");
        assert_eq!(job.status, JobStatus::Queued);
        assert_eq!(job.progress, 0);
    }

    #[tokio::test]
    async fn test_create_job_with_id() {
        let manager = JobManager::new();
        let custom_id = Uuid::new_v4();
        let returned_id = manager.create_job_with_id(custom_id, "bake").await;

        assert_eq!(returned_id, custom_id);
        let job = manager.get_job(custom_id).await.unwrap();
        assert_eq!(job.id, custom_id);
        assert_eq!(job.job_type, "bake");
    }

    #[tokio::test]
    async fn test_get_nonexistent_job() {
        let manager = JobManager::new();
        let random_id = Uuid::new_v4();
        let job = manager.get_job(random_id).await;
        assert!(job.is_none());
    }

    #[tokio::test]
    async fn test_update_status() {
        let manager = JobManager::new();
        let job_id = manager.create_job("render").await;

        manager
            .update_status(job_id, JobStatus::Running, Some("Processing frame 1"))
            .await;

        let job = manager.get_job(job_id).await.unwrap();
        assert_eq!(job.status, JobStatus::Running);
        assert_eq!(job.message, "Processing frame 1");
        assert!(job.updated_at.is_some());
    }

    #[tokio::test]
    async fn test_update_progress() {
        let manager = JobManager::new();
        let job_id = manager.create_job("render").await;

        manager.update_progress(job_id, 50).await;
        let job = manager.get_job(job_id).await.unwrap();
        assert_eq!(job.progress, 50);

        // Test progress clamping to 100
        manager.update_progress(job_id, 150).await;
        let job = manager.get_job(job_id).await.unwrap();
        assert_eq!(job.progress, 100);
    }

    #[tokio::test]
    async fn test_complete_job() {
        let manager = JobManager::new();
        let job_id = manager.create_job("render").await;

        let result = serde_json::json!({"frames_rendered": 100, "output_file": "render.mp4"});
        manager
            .complete_job(job_id, result.clone(), Some("/output/render.mp4"))
            .await;

        let job = manager.get_job(job_id).await.unwrap();
        assert_eq!(job.status, JobStatus::Completed);
        assert_eq!(job.progress, 100);
        assert_eq!(job.result, Some(result));
        assert_eq!(job.output_path, Some("/output/render.mp4".to_string()));
    }

    #[tokio::test]
    async fn test_fail_job() {
        let manager = JobManager::new();
        let job_id = manager.create_job("render").await;

        manager.fail_job(job_id, "Out of memory").await;

        let job = manager.get_job(job_id).await.unwrap();
        assert_eq!(job.status, JobStatus::Failed);
        assert_eq!(job.error, Some("Out of memory".to_string()));
    }

    #[tokio::test]
    async fn test_cancel_queued_job() {
        let manager = JobManager::new();
        let job_id = manager.create_job("render").await;

        let cancelled = manager.cancel_job(job_id).await;
        assert!(cancelled);

        let job = manager.get_job(job_id).await.unwrap();
        assert_eq!(job.status, JobStatus::Cancelled);
    }

    #[tokio::test]
    async fn test_cancel_running_job() {
        let manager = JobManager::new();
        let job_id = manager.create_job("render").await;

        manager
            .update_status(job_id, JobStatus::Running, None)
            .await;
        let cancelled = manager.cancel_job(job_id).await;
        assert!(cancelled);

        let job = manager.get_job(job_id).await.unwrap();
        assert_eq!(job.status, JobStatus::Cancelled);
    }

    #[tokio::test]
    async fn test_cannot_cancel_completed_job() {
        let manager = JobManager::new();
        let job_id = manager.create_job("render").await;

        manager
            .complete_job(job_id, serde_json::json!({}), None)
            .await;

        let cancelled = manager.cancel_job(job_id).await;
        assert!(!cancelled);

        let job = manager.get_job(job_id).await.unwrap();
        assert_eq!(job.status, JobStatus::Completed);
    }

    #[tokio::test]
    async fn test_cannot_cancel_failed_job() {
        let manager = JobManager::new();
        let job_id = manager.create_job("render").await;

        manager.fail_job(job_id, "Error").await;

        let cancelled = manager.cancel_job(job_id).await;
        assert!(!cancelled);

        let job = manager.get_job(job_id).await.unwrap();
        assert_eq!(job.status, JobStatus::Failed);
    }

    #[tokio::test]
    async fn test_list_jobs() {
        let manager = JobManager::new();

        let id1 = manager.create_job("render").await;
        let id2 = manager.create_job("bake").await;
        let id3 = manager.create_job("export").await;

        let jobs = manager.list_jobs().await;
        assert_eq!(jobs.len(), 3);

        let ids: Vec<Uuid> = jobs.iter().map(|j| j.id).collect();
        assert!(ids.contains(&id1));
        assert!(ids.contains(&id2));
        assert!(ids.contains(&id3));
    }

    #[tokio::test]
    async fn test_job_manager_clone() {
        let manager = JobManager::new();
        let job_id = manager.create_job("render").await;

        let cloned_manager = manager.clone();

        // Both managers should see the same job
        let job_from_original = manager.get_job(job_id).await;
        let job_from_clone = cloned_manager.get_job(job_id).await;

        assert!(job_from_original.is_some());
        assert!(job_from_clone.is_some());
        assert_eq!(job_from_original.unwrap().id, job_from_clone.unwrap().id);

        // Updates from clone should be visible to original
        cloned_manager
            .update_status(job_id, JobStatus::Running, None)
            .await;
        let job = manager.get_job(job_id).await.unwrap();
        assert_eq!(job.status, JobStatus::Running);
    }

    #[tokio::test]
    async fn test_job_manager_default() {
        let manager = JobManager::default();
        let jobs = manager.list_jobs().await;
        assert!(jobs.is_empty());
    }

    #[tokio::test]
    async fn test_update_nonexistent_job_status() {
        let manager = JobManager::new();
        let random_id = Uuid::new_v4();

        // Should not panic, just log warning
        manager
            .update_status(random_id, JobStatus::Running, None)
            .await;

        // Job still doesn't exist
        assert!(manager.get_job(random_id).await.is_none());
    }
}
