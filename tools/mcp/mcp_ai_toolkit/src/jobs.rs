//! Training job lifecycle management.
//!
//! Each started job gets a dedicated monitor task that owns the child process
//! and awaits its exit, so job status is updated (and the process reaped) even
//! if nobody polls. Stop requests are delivered to the monitor task over a
//! channel; on Unix the job runs in its own process group and is stopped with
//! SIGTERM to the whole group (covering dataloader workers), escalating to
//! SIGKILL after a grace period.
//!
//! The job registry is persisted as JSON so history and log locations survive
//! a server restart. Jobs that were still running when the server stopped are
//! reloaded with status [`JobStatus::Unknown`], since their outcome can no
//! longer be observed.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::Arc;
use std::time::Duration;
use tokio::process::{Child, Command};
use tokio::sync::{Mutex, RwLock, mpsc, oneshot};
use tracing::{info, warn};

/// Maximum number of finished jobs kept in the registry.
const MAX_FINISHED_JOBS: usize = 200;

/// Training job status.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
pub enum JobStatus {
    Pending,
    Running,
    Completed,
    Failed,
    Stopped,
    /// The server restarted while the job was running; outcome unknown.
    Unknown,
}

impl JobStatus {
    /// Whether the job may still be consuming the GPU.
    pub fn is_active(self) -> bool {
        matches!(self, JobStatus::Pending | JobStatus::Running)
    }
}

impl std::fmt::Display for JobStatus {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            JobStatus::Pending => "pending",
            JobStatus::Running => "running",
            JobStatus::Completed => "completed",
            JobStatus::Failed => "failed",
            JobStatus::Stopped => "stopped",
            JobStatus::Unknown => "unknown",
        };
        f.write_str(s)
    }
}

/// Persisted information about a training job.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrainingJob {
    pub job_id: String,
    pub status: JobStatus,
    pub config_name: String,
    pub log_file: Option<String>,
    pub pid: Option<u32>,
    pub exit_code: Option<i32>,
    pub started_at: Option<String>,
    #[serde(default)]
    pub finished_at: Option<String>,
    /// Folder AI Toolkit writes weights and samples to (`<training_folder>/<run>`).
    pub output_folder: Option<String>,
    /// `train.steps` from the config, used to pick the right progress bar.
    #[serde(default)]
    pub total_steps: Option<u32>,
}

/// Everything needed to launch a training process.
#[derive(Debug, Clone)]
pub struct LaunchSpec {
    pub program: String,
    pub args: Vec<String>,
    pub cwd: PathBuf,
    /// Directory for the job log; the file is named `training_<job_id>.log`.
    pub log_dir: PathBuf,
    pub config_name: String,
    pub output_folder: Option<PathBuf>,
    pub total_steps: Option<u32>,
    /// Extra environment variables for the child.
    pub env: Vec<(String, String)>,
}

/// Result of a stop request.
#[derive(Debug, Clone, Serialize)]
pub struct StopOutcome {
    pub job_id: String,
    pub status: JobStatus,
    pub exit_code: Option<i32>,
    /// True if the process had to be SIGKILLed after the grace period.
    pub forced: bool,
}

struct StopRequest {
    grace: Duration,
    reply: oneshot::Sender<(Option<i32>, bool)>,
}

/// Registry of training jobs and their live processes.
pub struct JobManager {
    jobs: RwLock<HashMap<String, TrainingJob>>,
    controls: Mutex<HashMap<String, mpsc::Sender<StopRequest>>>,
    state_file: Option<PathBuf>,
    /// Serializes state-file writes.
    persist_lock: Mutex<()>,
}

impl JobManager {
    /// Create a manager, loading persisted jobs from `state_file` if present.
    pub fn new(state_file: Option<PathBuf>) -> Self {
        let mut jobs = HashMap::new();
        if let Some(path) = &state_file {
            match std::fs::read_to_string(path) {
                Ok(text) => match serde_json::from_str::<Vec<TrainingJob>>(&text) {
                    Ok(list) => {
                        for mut job in list {
                            if job.status.is_active() {
                                job.status = JobStatus::Unknown;
                            }
                            jobs.insert(job.job_id.clone(), job);
                        }
                        info!(
                            "Loaded {} training job(s) from {}",
                            jobs.len(),
                            path.display()
                        );
                    },
                    Err(e) => warn!("Ignoring corrupt job state {}: {}", path.display(), e),
                },
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => {},
                Err(e) => warn!("Could not read job state {}: {}", path.display(), e),
            }
        }
        Self {
            jobs: RwLock::new(jobs),
            controls: Mutex::new(HashMap::new()),
            state_file,
            persist_lock: Mutex::new(()),
        }
    }

    /// Snapshot of one job.
    pub async fn get(&self, job_id: &str) -> Option<TrainingJob> {
        self.jobs.read().await.get(job_id).cloned()
    }

    /// Snapshot of all jobs, newest first.
    pub async fn list(&self) -> Vec<TrainingJob> {
        let mut v: Vec<_> = self.jobs.read().await.values().cloned().collect();
        v.sort_by(|a, b| b.started_at.cmp(&a.started_at));
        v
    }

    /// Jobs that are pending or running.
    pub async fn active(&self) -> Vec<TrainingJob> {
        self.jobs
            .read()
            .await
            .values()
            .filter(|j| j.status.is_active())
            .cloned()
            .collect()
    }

    /// Spawn a training process and start monitoring it.
    pub async fn start(self: &Arc<Self>, spec: LaunchSpec) -> Result<TrainingJob, String> {
        let job_id = uuid::Uuid::new_v4().to_string();
        tokio::fs::create_dir_all(&spec.log_dir)
            .await
            .map_err(|e| format!("Failed to create log directory: {e}"))?;
        let log_file = spec.log_dir.join(format!("training_{job_id}.log"));
        let log = std::fs::File::create(&log_file)
            .map_err(|e| format!("Failed to create log file: {e}"))?;
        let log_err = log
            .try_clone()
            .map_err(|e| format!("Failed to open log file: {e}"))?;

        let mut cmd = Command::new(&spec.program);
        cmd.args(&spec.args)
            .current_dir(&spec.cwd)
            .stdin(Stdio::null())
            .stdout(Stdio::from(log))
            // tqdm progress and Python tracebacks go to stderr.
            .stderr(Stdio::from(log_err))
            .env("PYTHONUNBUFFERED", "1");
        for (k, v) in &spec.env {
            cmd.env(k, v);
        }
        #[cfg(unix)]
        cmd.process_group(0);

        let child = cmd.spawn().map_err(|e| {
            format!(
                "Failed to start '{}' in {}: {e}",
                spec.program,
                spec.cwd.display()
            )
        })?;

        let job = TrainingJob {
            job_id: job_id.clone(),
            status: JobStatus::Running,
            config_name: spec.config_name.clone(),
            log_file: Some(log_file.display().to_string()),
            pid: child.id(),
            exit_code: None,
            started_at: Some(chrono::Utc::now().to_rfc3339()),
            finished_at: None,
            output_folder: spec.output_folder.as_ref().map(|p| p.display().to_string()),
            total_steps: spec.total_steps,
        };

        let (tx, rx) = mpsc::channel(4);
        self.jobs.write().await.insert(job_id.clone(), job.clone());
        self.controls.lock().await.insert(job_id.clone(), tx);
        self.persist().await;

        let manager = Arc::clone(self);
        tokio::spawn(async move { manager.monitor(job_id, child, rx).await });

        info!("Started training job {} ({})", job.job_id, job.config_name);
        Ok(job)
    }

    async fn monitor(
        self: Arc<Self>,
        job_id: String,
        mut child: Child,
        mut rx: mpsc::Receiver<StopRequest>,
    ) {
        let (status, code, reply, forced) = tokio::select! {
            res = child.wait() => {
                match res {
                    Ok(s) if s.success() => (JobStatus::Completed, s.code(), None, false),
                    Ok(s) => (JobStatus::Failed, s.code(), None, false),
                    Err(e) => {
                        warn!("Failed waiting on job {}: {}", job_id, e);
                        (JobStatus::Failed, None, None, false)
                    },
                }
            }
            Some(req) = rx.recv() => {
                let (code, forced) = terminate(&mut child, req.grace).await;
                (JobStatus::Stopped, code, Some(req.reply), forced)
            }
        };

        self.controls.lock().await.remove(&job_id);
        {
            let mut jobs = self.jobs.write().await;
            if let Some(job) = jobs.get_mut(&job_id) {
                job.status = status;
                job.exit_code = code;
                job.finished_at = Some(chrono::Utc::now().to_rfc3339());
            }
            prune(&mut jobs);
        }
        self.persist().await;
        info!(
            "Training job {} finished: {} (exit {:?})",
            job_id, status, code
        );
        if let Some(reply) = reply {
            let _ = reply.send((code, forced));
        }
    }

    /// Stop a running job, waiting up to `grace` before force-killing it.
    pub async fn stop(&self, job_id: &str, grace: Duration) -> Result<StopOutcome, String> {
        let tx = self.controls.lock().await.get(job_id).cloned();
        let Some(tx) = tx else {
            return match self.get(job_id).await {
                Some(job) => Err(format!(
                    "Job {job_id} is not running (status: {})",
                    job.status
                )),
                None => Err(format!("Job {job_id} not found")),
            };
        };
        let (reply_tx, reply_rx) = oneshot::channel();
        tx.send(StopRequest {
            grace,
            reply: reply_tx,
        })
        .await
        .map_err(|_| format!("Job {job_id} finished before it could be stopped"))?;

        // A dropped reply means the process exited on its own while the request
        // was queued; the job record already holds the real outcome.
        let (reply_code, forced) = tokio::time::timeout(grace + Duration::from_secs(15), reply_rx)
            .await
            .map_err(|_| format!("Timed out waiting for job {job_id} to stop"))?
            .unwrap_or((None, false));

        let job = self.get(job_id).await;
        let status = job.as_ref().map(|j| j.status).unwrap_or(JobStatus::Stopped);
        let exit_code = reply_code.or_else(|| job.and_then(|j| j.exit_code));
        Ok(StopOutcome {
            job_id: job_id.to_string(),
            status,
            exit_code,
            forced,
        })
    }

    /// Write the registry to the state file (best effort, atomic rename).
    async fn persist(&self) {
        let Some(path) = &self.state_file else { return };
        let _guard = self.persist_lock.lock().await;
        let snapshot: Vec<TrainingJob> = self.jobs.read().await.values().cloned().collect();
        let Ok(text) = serde_json::to_string_pretty(&snapshot) else {
            return;
        };
        let tmp = path.with_extension("json.tmp");
        let result = async {
            tokio::fs::write(&tmp, text).await?;
            tokio::fs::rename(&tmp, path).await
        }
        .await;
        if let Err(e) = result {
            warn!("Could not persist job state to {}: {}", path.display(), e);
        }
    }
}

/// Drop the oldest finished jobs beyond [`MAX_FINISHED_JOBS`].
fn prune(jobs: &mut HashMap<String, TrainingJob>) {
    let mut finished: Vec<(String, Option<String>)> = jobs
        .values()
        .filter(|j| !j.status.is_active())
        .map(|j| (j.job_id.clone(), j.started_at.clone()))
        .collect();
    if finished.len() <= MAX_FINISHED_JOBS {
        return;
    }
    finished.sort_by(|a, b| a.1.cmp(&b.1));
    let excess = finished.len() - MAX_FINISHED_JOBS;
    for (id, _) in finished.into_iter().take(excess) {
        jobs.remove(&id);
    }
}

/// Terminate a child: SIGTERM its process group, then SIGKILL after `grace`.
/// Returns the exit code (if any) and whether a forced kill was needed.
async fn terminate(child: &mut Child, grace: Duration) -> (Option<i32>, bool) {
    #[cfg(unix)]
    if let Some(pid) = child.id()
        && !grace.is_zero()
        && let Ok(pgid) = i32::try_from(pid)
    {
        // SAFETY: kill(2) with a negative pid signals the process group we
        // created at spawn (process_group(0) makes pgid == pid). It has no
        // memory-safety preconditions.
        unsafe {
            libc::kill(-pgid, libc::SIGTERM);
        }
        if let Ok(Ok(status)) = tokio::time::timeout(grace, child.wait()).await {
            return (status.code(), false);
        }
        // SAFETY: as above; escalate to SIGKILL for the whole group.
        unsafe {
            libc::kill(-pgid, libc::SIGKILL);
        }
    }
    #[cfg(not(unix))]
    let _ = grace;

    let _ = child.start_kill();
    let code = child.wait().await.ok().and_then(|s| s.code());
    (code, true)
}

/// Default location of the persisted job registry.
pub fn default_state_file(outputs: &Path) -> PathBuf {
    outputs.join(".mcp_training_jobs.json")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn shell(script: &str) -> (String, Vec<String>) {
        if cfg!(windows) {
            ("cmd".into(), vec!["/C".into(), script.into()])
        } else {
            ("sh".into(), vec!["-c".into(), script.into()])
        }
    }

    fn spec(dir: &Path, script: &str) -> LaunchSpec {
        let (program, args) = shell(script);
        LaunchSpec {
            program,
            args,
            cwd: dir.to_path_buf(),
            log_dir: dir.join("logs"),
            config_name: "cfg".into(),
            output_folder: None,
            total_steps: Some(10),
            env: vec![],
        }
    }

    async fn wait_until_finished(m: &JobManager, id: &str) -> TrainingJob {
        for _ in 0..200 {
            let j = m.get(id).await.unwrap();
            if !j.status.is_active() {
                return j;
            }
            tokio::time::sleep(Duration::from_millis(25)).await;
        }
        panic!("job did not finish");
    }

    #[tokio::test]
    async fn job_completes_and_logs_are_captured() {
        let tmp = tempfile::tempdir().unwrap();
        let state = tmp.path().join("state.json");
        let m = Arc::new(JobManager::new(Some(state.clone())));
        let job = m
            .start(spec(tmp.path(), "echo hello && echo oops 1>&2"))
            .await
            .unwrap();
        assert_eq!(job.status, JobStatus::Running);

        let done = wait_until_finished(&m, &job.job_id).await;
        assert_eq!(done.status, JobStatus::Completed);
        assert_eq!(done.exit_code, Some(0));
        assert!(done.finished_at.is_some());

        let log = std::fs::read_to_string(done.log_file.as_ref().unwrap()).unwrap();
        assert!(log.contains("hello") && log.contains("oops"), "{log}");

        // Persisted and reloadable
        let reloaded = JobManager::new(Some(state));
        assert_eq!(
            reloaded.get(&job.job_id).await.unwrap().status,
            JobStatus::Completed
        );
        // Stopping a finished job is a clean error
        let err = m
            .stop(&job.job_id, Duration::from_secs(1))
            .await
            .unwrap_err();
        assert!(err.contains("not running"), "{err}");
        assert!(
            m.stop("nope", Duration::ZERO)
                .await
                .unwrap_err()
                .contains("not found")
        );
    }

    #[tokio::test]
    async fn failed_job_reports_exit_code() {
        let tmp = tempfile::tempdir().unwrap();
        let m = Arc::new(JobManager::new(None));
        let job = m.start(spec(tmp.path(), "exit 3")).await.unwrap();
        let done = wait_until_finished(&m, &job.job_id).await;
        assert_eq!(done.status, JobStatus::Failed);
        assert_eq!(done.exit_code, Some(3));
    }

    #[tokio::test]
    async fn stop_running_job() {
        let tmp = tempfile::tempdir().unwrap();
        let m = Arc::new(JobManager::new(None));
        let script = if cfg!(windows) {
            "ping -n 30 127.0.0.1 >NUL"
        } else {
            "sleep 30"
        };
        let job = m.start(spec(tmp.path(), script)).await.unwrap();
        assert_eq!(m.active().await.len(), 1);
        let out = m.stop(&job.job_id, Duration::from_secs(5)).await.unwrap();
        assert_eq!(out.status, JobStatus::Stopped);
        assert!(m.active().await.is_empty());
        assert_eq!(m.get(&job.job_id).await.unwrap().status, JobStatus::Stopped);
    }

    #[tokio::test]
    async fn spawn_failure_is_reported() {
        let tmp = tempfile::tempdir().unwrap();
        let m = Arc::new(JobManager::new(None));
        let mut s = spec(tmp.path(), "");
        s.program = "definitely-not-a-real-binary-xyz".into();
        let err = m.start(s).await.unwrap_err();
        assert!(err.contains("Failed to start"), "{err}");
        assert!(m.list().await.is_empty());
    }

    #[tokio::test]
    async fn reload_marks_running_jobs_unknown_and_ignores_corrupt_state() {
        let tmp = tempfile::tempdir().unwrap();
        let state = tmp.path().join("state.json");
        let job = TrainingJob {
            job_id: "j1".into(),
            status: JobStatus::Running,
            config_name: "c".into(),
            log_file: None,
            pid: Some(1),
            exit_code: None,
            started_at: None,
            finished_at: None,
            output_folder: None,
            total_steps: None,
        };
        std::fs::write(&state, serde_json::to_string(&vec![job]).unwrap()).unwrap();
        let m = JobManager::new(Some(state.clone()));
        assert_eq!(m.get("j1").await.unwrap().status, JobStatus::Unknown);

        std::fs::write(&state, "not json").unwrap();
        assert!(JobManager::new(Some(state)).list().await.is_empty());
    }

    #[test]
    fn prune_keeps_active_and_newest() {
        let mut jobs = HashMap::new();
        for i in 0..(MAX_FINISHED_JOBS + 5) {
            let id = format!("{i:04}");
            jobs.insert(
                id.clone(),
                TrainingJob {
                    job_id: id.clone(),
                    status: JobStatus::Completed,
                    config_name: "c".into(),
                    log_file: None,
                    pid: None,
                    exit_code: Some(0),
                    started_at: Some(id),
                    finished_at: None,
                    output_folder: None,
                    total_steps: None,
                },
            );
        }
        prune(&mut jobs);
        assert_eq!(jobs.len(), MAX_FINISHED_JOBS);
        assert!(!jobs.contains_key("0000"));
        assert!(jobs.contains_key(&format!("{:04}", MAX_FINISHED_JOBS + 4)));
    }
}
