//! Shared data types and parsers for ComfyUI API payloads.
//!
//! ComfyUI's HTTP API is loosely versioned, so history and queue payloads are
//! parsed from `serde_json::Value` defensively instead of with strict structs:
//! unknown or missing fields degrade gracefully rather than failing the call.

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// A file produced by (or referenced in) a ComfyUI prompt.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ImageOutput {
    /// File name as stored by ComfyUI.
    pub filename: String,
    /// Subfolder relative to the output/temp/input directory ("" for root).
    #[serde(default)]
    pub subfolder: String,
    /// Storage area: `output`, `temp` or `input`.
    #[serde(rename = "type", default = "default_output_type")]
    pub output_type: String,
}

fn default_output_type() -> String {
    "output".to_string()
}

/// Lifecycle state of a queued prompt.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum JobStatus {
    /// Waiting in ComfyUI's pending queue.
    Queued,
    /// Currently executing.
    Running,
    /// Finished successfully.
    Completed,
    /// Finished with an execution error.
    Failed,
    /// Interrupted / cancelled before finishing.
    Interrupted,
    /// Still unfinished when the caller's wait timeout elapsed.
    Timeout,
    /// Not present in ComfyUI's queue or history (restarted or history cleared).
    Unknown,
}

impl JobStatus {
    /// Whether the job has reached a final state.
    pub fn is_terminal(self) -> bool {
        matches!(
            self,
            JobStatus::Completed | JobStatus::Failed | JobStatus::Interrupted
        )
    }
}

/// Snapshot of a job's state as reported by ComfyUI.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct JobState {
    /// Current status.
    pub status: JobStatus,
    /// 1-based position in the pending queue (only when queued).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub queue_position: Option<usize>,
    /// Images produced so far (only populated once completed).
    pub images: Vec<ImageOutput>,
    /// Human-readable error description for failed/interrupted jobs.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

impl JobState {
    /// A state with no images or error.
    pub fn bare(status: JobStatus) -> Self {
        Self {
            status,
            queue_position: None,
            images: Vec::new(),
            error: None,
        }
    }
}

/// Parse one `/history/{prompt_id}` entry into a [`JobState`].
///
/// History entries exist only once ComfyUI has finished (or aborted) a prompt.
/// `status.status_str == "error"` marks failures; an `execution_interrupted`
/// message marks cancellations. Older ComfyUI builds omit `status` entirely,
/// in which case the presence of an entry means completion.
pub fn parse_history_entry(entry: &Value) -> JobState {
    let images = collect_images(entry.get("outputs"));
    let status = entry.get("status");
    let status_str = status
        .and_then(|s| s.get("status_str"))
        .and_then(Value::as_str)
        .unwrap_or("");
    let completed = status
        .and_then(|s| s.get("completed"))
        .and_then(Value::as_bool);
    let messages: &[Value] = status
        .and_then(|s| s.get("messages"))
        .and_then(Value::as_array)
        .map(Vec::as_slice)
        .unwrap_or(&[]);

    let find_msg = |kind: &str| {
        messages.iter().find_map(|m| {
            let pair = m.as_array()?;
            (pair.first()?.as_str()? == kind).then(|| pair.get(1).cloned().unwrap_or(Value::Null))
        })
    };

    if let Some(detail) = find_msg("execution_interrupted") {
        let node = detail
            .get("node_type")
            .and_then(Value::as_str)
            .map(|t| format!(" at node {t}"))
            .unwrap_or_default();
        return JobState {
            status: JobStatus::Interrupted,
            queue_position: None,
            images,
            error: Some(format!("execution was interrupted{node}")),
        };
    }

    if status_str == "error" {
        let error = find_msg("execution_error")
            .map(|d| describe_execution_error(&d))
            .unwrap_or_else(|| "ComfyUI reported an execution error".to_string());
        return JobState {
            status: JobStatus::Failed,
            queue_position: None,
            images,
            error: Some(error),
        };
    }

    let status = match completed {
        Some(false) => JobStatus::Running,
        _ => JobStatus::Completed,
    };
    JobState {
        status,
        queue_position: None,
        images,
        error: None,
    }
}

fn describe_execution_error(detail: &Value) -> String {
    let get = |k: &str| detail.get(k).and_then(Value::as_str).unwrap_or("");
    let node_type = get("node_type");
    let node_id = detail
        .get("node_id")
        .map(|v| match v {
            Value::String(s) => s.clone(),
            other => other.to_string(),
        })
        .unwrap_or_default();
    let exc_type = get("exception_type");
    let message = get("exception_message").trim();
    let mut out = String::from("execution error");
    if !node_type.is_empty() || !node_id.is_empty() {
        out.push_str(&format!(" in node {node_id} ({node_type})"));
    }
    if !exc_type.is_empty() {
        out.push_str(&format!(": {exc_type}"));
    }
    if !message.is_empty() {
        out.push_str(&format!(": {message}"));
    }
    out
}

/// Collect image-like outputs (`images`, and `gifs` from video nodes) from a
/// history `outputs` map, ordered by node id for deterministic results.
pub fn collect_images(outputs: Option<&Value>) -> Vec<ImageOutput> {
    let Some(map) = outputs.and_then(Value::as_object) else {
        return Vec::new();
    };
    let mut node_ids: Vec<&String> = map.keys().collect();
    node_ids.sort_by_key(|id| (id.parse::<u64>().unwrap_or(u64::MAX), id.to_string()));

    let mut images = Vec::new();
    for id in node_ids {
        for key in ["images", "gifs"] {
            if let Some(list) = map[id].get(key).and_then(Value::as_array) {
                images.extend(
                    list.iter()
                        .filter_map(|v| serde_json::from_value::<ImageOutput>(v.clone()).ok()),
                );
            }
        }
    }
    images
}

/// Parsed `/queue` response: prompt ids that are running and pending.
#[derive(Debug, Clone, Default, PartialEq, Serialize)]
pub struct QueueSnapshot {
    /// Prompt ids currently executing.
    pub running: Vec<String>,
    /// Prompt ids waiting, in execution order.
    pub pending: Vec<String>,
}

impl QueueSnapshot {
    /// Parse ComfyUI's `/queue` payload. Each entry is
    /// `[number, prompt_id, prompt, extra_data, outputs_to_execute]`; pending
    /// entries are sorted by `number` (ComfyUI executes lowest first).
    pub fn parse(value: &Value) -> Self {
        let extract = |key: &str| -> Vec<(f64, String)> {
            value
                .get(key)
                .and_then(Value::as_array)
                .map(|items| {
                    items
                        .iter()
                        .filter_map(|item| {
                            let arr = item.as_array()?;
                            let number = arr.first()?.as_f64().unwrap_or(0.0);
                            let id = arr.get(1)?.as_str()?.to_string();
                            Some((number, id))
                        })
                        .collect()
                })
                .unwrap_or_default()
        };
        let running = extract("queue_running")
            .into_iter()
            .map(|(_, id)| id)
            .collect();
        let mut pending = extract("queue_pending");
        pending.sort_by(|a, b| a.0.total_cmp(&b.0));
        Self {
            running,
            pending: pending.into_iter().map(|(_, id)| id).collect(),
        }
    }

    /// The state of `prompt_id` according to this snapshot, if present.
    pub fn state_of(&self, prompt_id: &str) -> Option<JobState> {
        if self.running.iter().any(|id| id == prompt_id) {
            return Some(JobState::bare(JobStatus::Running));
        }
        self.pending
            .iter()
            .position(|id| id == prompt_id)
            .map(|idx| JobState {
                queue_position: Some(idx + 1),
                ..JobState::bare(JobStatus::Queued)
            })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn history_success() {
        let entry = json!({
            "outputs": {
                "9": {"images": [{"filename": "b.png", "subfolder": "", "type": "output"}]},
                "10": {"images": [{"filename": "c.png"}]},
                "7": {"images": [{"filename": "a.png", "subfolder": "x", "type": "temp"}]}
            },
            "status": {"status_str": "success", "completed": true, "messages": []}
        });
        let state = parse_history_entry(&entry);
        assert_eq!(state.status, JobStatus::Completed);
        let names: Vec<_> = state.images.iter().map(|i| i.filename.as_str()).collect();
        assert_eq!(names, ["a.png", "b.png", "c.png"]);
        assert_eq!(state.images[0].output_type, "temp");
        assert_eq!(state.images[2].output_type, "output");
        assert!(state.error.is_none());
    }

    #[test]
    fn history_without_status_counts_as_completed() {
        let state = parse_history_entry(&json!({"outputs": {}}));
        assert_eq!(state.status, JobStatus::Completed);
        assert!(state.images.is_empty());
    }

    #[test]
    fn history_error() {
        let entry = json!({
            "outputs": {},
            "status": {
                "status_str": "error",
                "completed": false,
                "messages": [
                    ["execution_start", {"prompt_id": "p"}],
                    ["execution_error", {
                        "node_id": "4", "node_type": "KSampler",
                        "exception_type": "RuntimeError",
                        "exception_message": "CUDA out of memory\n"
                    }]
                ]
            }
        });
        let state = parse_history_entry(&entry);
        assert_eq!(state.status, JobStatus::Failed);
        let err = state.error.unwrap();
        assert!(err.contains("node 4 (KSampler)"), "{err}");
        assert!(err.contains("RuntimeError: CUDA out of memory"), "{err}");
    }

    #[test]
    fn history_interrupted() {
        let entry = json!({
            "outputs": {},
            "status": {"status_str": "error", "completed": false, "messages": [
                ["execution_interrupted", {"node_type": "KSampler"}]
            ]}
        });
        let state = parse_history_entry(&entry);
        assert_eq!(state.status, JobStatus::Interrupted);
        assert!(state.error.unwrap().contains("KSampler"));
    }

    #[test]
    fn queue_parsing_and_positions() {
        let q = QueueSnapshot::parse(&json!({
            "queue_running": [[5, "run", {}, {}, []]],
            "queue_pending": [[8, "late", {}, {}, []], [6, "early", {}, {}, []], ["junk"]]
        }));
        assert_eq!(q.running, ["run"]);
        assert_eq!(q.pending, ["early", "late"]);
        assert_eq!(q.state_of("run").unwrap().status, JobStatus::Running);
        assert_eq!(q.state_of("late").unwrap().queue_position, Some(2));
        assert!(q.state_of("missing").is_none());
        assert_eq!(QueueSnapshot::parse(&json!({})), QueueSnapshot::default());
    }

    #[test]
    fn terminal_states() {
        assert!(JobStatus::Completed.is_terminal());
        assert!(JobStatus::Failed.is_terminal());
        assert!(!JobStatus::Queued.is_terminal());
        assert!(!JobStatus::Timeout.is_terminal());
    }
}
