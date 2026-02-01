//! Job management for long-running video operations.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use tokio::sync::RwLock;

/// Job status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum JobStatus {
    Pending,
    Running,
    Completed,
    Failed,
}

/// A job tracking a long-running operation
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
    #[serde(skip_serializing_if = "Vec::is_empty", default)]
    pub temp_files: Vec<String>,
}

impl Job {
    /// Create a new job
    pub fn new(operation: &str, counter: u64) -> Self {
        Self {
            id: format!("job_{}_{}", counter, operation),
            operation: operation.to_string(),
            status: JobStatus::Pending,
            progress: 0,
            stage: "initializing".to_string(),
            created_at: Utc::now(),
            updated_at: None,
            result: None,
            error: None,
            temp_files: Vec::new(),
        }
    }

    /// Update the job status
    pub fn update(&mut self, status: JobStatus, progress: u32, stage: &str) {
        self.status = status;
        self.progress = progress;
        self.stage = stage.to_string();
        self.updated_at = Some(Utc::now());
    }

    /// Mark job as completed with result
    pub fn complete(&mut self, result: serde_json::Value) {
        self.status = JobStatus::Completed;
        self.progress = 100;
        self.stage = "done".to_string();
        self.result = Some(result);
        self.updated_at = Some(Utc::now());
    }

    /// Mark job as failed with error
    pub fn fail(&mut self, error: &str) {
        self.status = JobStatus::Failed;
        self.error = Some(error.to_string());
        self.updated_at = Some(Utc::now());
    }

    /// Add a temp file to track for cleanup
    #[allow(dead_code)]
    pub fn add_temp_file(&mut self, path: String) {
        self.temp_files.push(path);
    }
}

/// Job manager for tracking all jobs
pub struct JobManager {
    jobs: RwLock<HashMap<String, Job>>,
    counter: AtomicU64,
}

impl JobManager {
    /// Create a new job manager
    pub fn new() -> Self {
        Self {
            jobs: RwLock::new(HashMap::new()),
            counter: AtomicU64::new(0),
        }
    }

    /// Create a new job
    pub async fn create_job(&self, operation: &str) -> String {
        let counter = self.counter.fetch_add(1, Ordering::SeqCst);
        let job = Job::new(operation, counter);
        let job_id = job.id.clone();

        let mut jobs = self.jobs.write().await;
        jobs.insert(job_id.clone(), job);

        job_id
    }

    /// Get a job by ID
    pub async fn get_job(&self, job_id: &str) -> Option<Job> {
        let jobs = self.jobs.read().await;
        jobs.get(job_id).cloned()
    }

    /// Update a job
    pub async fn update_job(&self, job_id: &str, status: JobStatus, progress: u32, stage: &str) {
        let mut jobs = self.jobs.write().await;
        if let Some(job) = jobs.get_mut(job_id) {
            job.update(status, progress, stage);
            tracing::info!(
                "Job {}: {} - {}% - {}",
                job_id,
                format!("{:?}", status).to_lowercase(),
                progress,
                stage
            );
        }
    }

    /// Complete a job with result
    pub async fn complete_job(&self, job_id: &str, result: serde_json::Value) {
        let mut jobs = self.jobs.write().await;
        if let Some(job) = jobs.get_mut(job_id) {
            job.complete(result);
        }
    }

    /// Fail a job with error
    pub async fn fail_job(&self, job_id: &str, error: &str) {
        let mut jobs = self.jobs.write().await;
        if let Some(job) = jobs.get_mut(job_id) {
            job.fail(error);
        }
    }

    /// Add a temp file to a job
    #[allow(dead_code)]
    pub async fn add_temp_file(&self, job_id: &str, path: String) {
        let mut jobs = self.jobs.write().await;
        if let Some(job) = jobs.get_mut(job_id) {
            job.add_temp_file(path);
        }
    }

    /// Clean up a job's temp files
    #[allow(dead_code)]
    pub async fn cleanup_job(&self, job_id: &str) {
        let jobs = self.jobs.read().await;
        if let Some(job) = jobs.get(job_id) {
            for temp_file in &job.temp_files {
                if let Err(e) = std::fs::remove_file(temp_file) {
                    tracing::warn!("Failed to clean up temp file {}: {}", temp_file, e);
                }
            }
        }
    }

    /// Get the current job counter value
    pub fn counter(&self) -> u64 {
        self.counter.load(Ordering::SeqCst)
    }
}

impl Default for JobManager {
    fn default() -> Self {
        Self::new()
    }
}
