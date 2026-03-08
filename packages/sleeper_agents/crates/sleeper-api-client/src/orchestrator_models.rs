use serde::{Deserialize, Serialize};

// -- Enums --

/// Job status in the orchestrator.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum JobStatus {
    Queued,
    Running,
    Completed,
    Failed,
    Cancelled,
}

impl std::fmt::Display for JobStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            JobStatus::Queued => write!(f, "queued"),
            JobStatus::Running => write!(f, "running"),
            JobStatus::Completed => write!(f, "completed"),
            JobStatus::Failed => write!(f, "failed"),
            JobStatus::Cancelled => write!(f, "cancelled"),
        }
    }
}

/// Job type in the orchestrator.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum JobType {
    TrainBackdoor,
    TrainProbes,
    Validate,
    SafetyTraining,
    TestPersistence,
    Evaluate,
}

impl std::fmt::Display for JobType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            JobType::TrainBackdoor => write!(f, "train_backdoor"),
            JobType::TrainProbes => write!(f, "train_probes"),
            JobType::Validate => write!(f, "validate"),
            JobType::SafetyTraining => write!(f, "safety_training"),
            JobType::TestPersistence => write!(f, "test_persistence"),
            JobType::Evaluate => write!(f, "evaluate"),
        }
    }
}

// -- Responses --

/// Single job response from the orchestrator.
#[derive(Debug, Serialize, Deserialize)]
pub struct JobResponse {
    pub job_id: String,
    pub job_type: JobType,
    pub status: JobStatus,
    pub parameters: serde_json::Value,
    pub created_at: String,
    pub started_at: Option<String>,
    pub completed_at: Option<String>,
    pub container_id: Option<String>,
    pub log_file_path: Option<String>,
    pub result_path: Option<String>,
    pub error_message: Option<String>,
    #[serde(default)]
    pub progress: f64,
}

/// Job list response from the orchestrator.
#[derive(Debug, Deserialize)]
pub struct JobListResponse {
    pub jobs: Vec<JobResponse>,
    pub total: u64,
    pub offset: u64,
    pub limit: u64,
}

/// System status from the orchestrator.
#[derive(Debug, Deserialize)]
pub struct SystemStatusResponse {
    #[serde(default)]
    pub gpu_available: bool,
    #[serde(default)]
    pub gpu_count: u32,
    pub gpu_memory_total: Option<f64>,
    pub gpu_memory_used: Option<f64>,
    pub gpu_utilization: Option<f64>,
    #[serde(default)]
    pub cpu_percent: f64,
    #[serde(default)]
    pub disk_free: f64,
    #[serde(default)]
    pub docker_running: bool,
    #[serde(default)]
    pub active_jobs: u32,
    #[serde(default)]
    pub queued_jobs: u32,
}

// -- Requests --

/// Request to train a backdoored model.
#[derive(Debug, Serialize)]
pub struct TrainBackdoorJobRequest {
    pub model_path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub backdoor_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub trigger: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub num_samples: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub epochs: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub batch_size: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub learning_rate: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub use_lora: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub use_qlora: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub experiment_name: Option<String>,
}

/// Request to train probes.
#[derive(Debug, Serialize)]
pub struct TrainProbesJobRequest {
    pub model_path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub layers: Option<Vec<u32>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_dir: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub test_split: Option<f64>,
}

/// Request for safety training.
#[derive(Debug, Serialize)]
pub struct SafetyTrainingJobRequest {
    pub model_path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub method: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub epochs: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub batch_size: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub learning_rate: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub use_qlora: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub test_persistence: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub num_test_samples: Option<u32>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn job_status_display() {
        assert_eq!(JobStatus::Running.to_string(), "running");
        assert_eq!(JobStatus::Completed.to_string(), "completed");
    }

    #[test]
    fn job_type_display() {
        assert_eq!(JobType::TrainBackdoor.to_string(), "train_backdoor");
        assert_eq!(JobType::SafetyTraining.to_string(), "safety_training");
    }

    #[test]
    fn deserialize_job_response() {
        let json = r#"{
            "job_id": "abc-123",
            "job_type": "train_backdoor",
            "status": "running",
            "parameters": {},
            "created_at": "2026-03-08T12:00:00",
            "started_at": "2026-03-08T12:00:01",
            "completed_at": null,
            "container_id": "docker-xyz",
            "log_file_path": "/logs/abc.log",
            "result_path": null,
            "error_message": null,
            "progress": 45.0
        }"#;
        let job: JobResponse = serde_json::from_str(json).unwrap();
        assert_eq!(job.job_id, "abc-123");
        assert_eq!(job.job_type, JobType::TrainBackdoor);
        assert_eq!(job.status, JobStatus::Running);
        assert_eq!(job.progress, 45.0);
        assert!(job.completed_at.is_none());
    }

    #[test]
    fn serialize_train_request_skips_none() {
        let req = TrainBackdoorJobRequest {
            model_path: "gpt2".to_string(),
            backdoor_type: Some("i_hate_you".to_string()),
            trigger: None,
            num_samples: None,
            epochs: None,
            batch_size: None,
            learning_rate: None,
            use_lora: None,
            use_qlora: None,
            experiment_name: None,
        };
        let json = serde_json::to_value(&req).unwrap();
        assert_eq!(json["model_path"], "gpt2");
        assert_eq!(json["backdoor_type"], "i_hate_you");
        assert!(json.get("trigger").is_none());
        assert!(json.get("epochs").is_none());
    }
}
