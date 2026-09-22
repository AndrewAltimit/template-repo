//! Host statistics: CPU, memory, disk and NVIDIA GPU usage.

use serde::Serialize;
use std::path::Path;
use std::time::Duration;
use sysinfo::{Disks, System};
use tokio::process::Command;

/// Timeout for the `nvidia-smi` query.
const NVIDIA_SMI_TIMEOUT: Duration = Duration::from_secs(5);

/// Statistics for one GPU as reported by `nvidia-smi`.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct GpuDevice {
    pub index: u32,
    pub name: String,
    pub memory_used_mb: Option<f64>,
    pub memory_total_mb: Option<f64>,
    pub utilization_percent: Option<f64>,
    pub temperature_c: Option<f64>,
}

/// GPU query outcome.
#[derive(Debug, Clone, Serialize)]
pub struct GpuReport {
    pub available: bool,
    /// Kept for backward compatibility with the previous response shape.
    pub cuda_available: bool,
    pub devices: Vec<GpuDevice>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

/// CPU / memory / disk snapshot.
#[derive(Debug, Clone, Serialize)]
pub struct HostStats {
    pub cpu_percent: f32,
    pub memory_percent: f32,
    pub memory_used_gb: f64,
    pub memory_total_gb: f64,
    pub disk_usage_percent: f32,
    pub disk_free_gb: f64,
    pub disk_total_gb: f64,
    /// Mount point of the disk holding the AI Toolkit directory.
    pub disk_mount: Option<String>,
}

const GB: f64 = 1024.0 * 1024.0 * 1024.0;

fn round2(x: f64) -> f64 {
    (x * 100.0).round() / 100.0
}

/// Collect host statistics (blocking: samples CPU twice, ~200ms).
pub fn host_stats(data_path: &Path) -> HostStats {
    let mut sys = System::new();
    sys.refresh_cpu_usage();
    std::thread::sleep(sysinfo::MINIMUM_CPU_UPDATE_INTERVAL.max(Duration::from_millis(100)));
    sys.refresh_cpu_usage();
    sys.refresh_memory();

    let total_mem = sys.total_memory();
    let used_mem = sys.used_memory();

    // Pick the disk whose mount point is the longest prefix of the data path.
    let target = data_path
        .canonicalize()
        .unwrap_or_else(|_| data_path.to_path_buf());
    let disks = Disks::new_with_refreshed_list();
    let disk = disks
        .iter()
        .filter(|d| target.starts_with(d.mount_point()))
        .max_by_key(|d| d.mount_point().as_os_str().len())
        .or_else(|| disks.iter().find(|d| d.mount_point() == Path::new("/")));

    let (usage, free, total, mount) = match disk {
        Some(d) if d.total_space() > 0 => {
            let total = d.total_space();
            let avail = d.available_space().min(total);
            (
                ((total - avail) as f64 / total as f64 * 100.0) as f32,
                avail as f64 / GB,
                total as f64 / GB,
                Some(d.mount_point().display().to_string()),
            )
        },
        _ => (0.0, 0.0, 0.0, None),
    };

    HostStats {
        cpu_percent: sys.global_cpu_usage(),
        memory_percent: (used_mem as f64 / total_mem.max(1) as f64 * 100.0) as f32,
        memory_used_gb: round2(used_mem as f64 / GB),
        memory_total_gb: round2(total_mem as f64 / GB),
        disk_usage_percent: usage,
        disk_free_gb: round2(free),
        disk_total_gb: round2(total),
        disk_mount: mount,
    }
}

/// Parse `nvidia-smi --query-gpu=index,name,memory.used,memory.total,
/// utilization.gpu,temperature.gpu --format=csv,noheader,nounits` output.
pub fn parse_nvidia_smi(csv: &str) -> Vec<GpuDevice> {
    csv.lines()
        .filter_map(|line| {
            let cols: Vec<&str> = line.split(',').map(str::trim).collect();
            if cols.len() < 6 {
                return None;
            }
            let num = |s: &str| s.parse::<f64>().ok();
            Some(GpuDevice {
                index: cols[0].parse().ok()?,
                name: cols[1].to_string(),
                memory_used_mb: num(cols[2]),
                memory_total_mb: num(cols[3]),
                utilization_percent: num(cols[4]),
                temperature_c: num(cols[5]),
            })
        })
        .collect()
}

/// Query GPUs via `nvidia-smi` with a timeout.
pub async fn gpu_report() -> GpuReport {
    let cuda_env = std::env::var("CUDA_VISIBLE_DEVICES")
        .map(|v| !v.trim().is_empty() && v.trim() != "-1")
        .unwrap_or(false);
    let mut cmd = Command::new("nvidia-smi");
    cmd.args([
        "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits",
    ])
    .kill_on_drop(true);

    let failure = |error: String| GpuReport {
        available: false,
        cuda_available: cuda_env,
        devices: vec![],
        error: Some(error),
    };

    match tokio::time::timeout(NVIDIA_SMI_TIMEOUT, cmd.output()).await {
        Err(_) => failure("nvidia-smi timed out".into()),
        Ok(Err(e)) => failure(format!("nvidia-smi unavailable: {e}")),
        Ok(Ok(out)) if !out.status.success() => failure(format!(
            "nvidia-smi failed: {}",
            String::from_utf8_lossy(&out.stderr).trim()
        )),
        Ok(Ok(out)) => {
            let devices = parse_nvidia_smi(&String::from_utf8_lossy(&out.stdout));
            GpuReport {
                available: !devices.is_empty(),
                cuda_available: !devices.is_empty() || cuda_env,
                devices,
                error: None,
            }
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_nvidia_smi_csv() {
        let csv = "0, NVIDIA GeForce RTX 4090, 1234, 24564, 87, 65\n\
                   1, NVIDIA A100-SXM4-80GB, [N/A], 81920, 0, 30\n\
                   garbage line\n";
        let d = parse_nvidia_smi(csv);
        assert_eq!(d.len(), 2);
        assert_eq!(d[0].name, "NVIDIA GeForce RTX 4090");
        assert_eq!(d[0].memory_used_mb, Some(1234.0));
        assert_eq!(d[0].utilization_percent, Some(87.0));
        assert_eq!(d[1].index, 1);
        assert_eq!(d[1].memory_used_mb, None);
        assert!(parse_nvidia_smi("").is_empty());
    }

    #[test]
    fn host_stats_is_sane() {
        let s = host_stats(Path::new("."));
        assert!(s.memory_total_gb > 0.0);
        assert!((0.0..=100.0).contains(&s.memory_percent));
        assert!((0.0..=100.0).contains(&s.disk_usage_percent));
    }
}
