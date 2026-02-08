//! System health monitoring.
//!
//! Collects CPU temperature, memory usage, disk usage, and network status
//! from `/proc` and `/sys` on Linux. Returns safe defaults on other platforms.

use std::fmt;

/// A snapshot of system health metrics.
#[derive(Debug, Clone, Default)]
pub struct SystemHealth {
    /// CPU temperature in degrees Celsius (None if unavailable).
    pub cpu_temp_c: Option<f32>,
    /// Used memory in KiB (None if unavailable).
    pub memory_used_kb: Option<u64>,
    /// Total memory in KiB (None if unavailable).
    pub memory_total_kb: Option<u64>,
    /// Used disk in KiB (None if unavailable).
    pub disk_used_kb: Option<u64>,
    /// Total disk in KiB (None if unavailable).
    pub disk_total_kb: Option<u64>,
    /// Whether the network interface is up.
    pub network_up: bool,
}

impl SystemHealth {
    /// Collect system health from Linux `/proc` and `/sys` filesystems.
    ///
    /// This reads real system files, not the VFS. It is only meaningful on
    /// Linux (Pi or desktop). On other platforms, returns defaults.
    #[cfg(target_os = "linux")]
    pub fn collect() -> Self {
        let mut health = Self::default();

        // CPU temperature from thermal zone.
        if let Ok(temp_str) = std::fs::read_to_string("/sys/class/thermal/thermal_zone0/temp") {
            if let Ok(millideg) = temp_str.trim().parse::<u64>() {
                health.cpu_temp_c = Some(millideg as f32 / 1000.0);
            }
        }

        // Memory from /proc/meminfo.
        if let Ok(meminfo) = std::fs::read_to_string("/proc/meminfo") {
            let mut total = None;
            let mut available = None;
            for line in meminfo.lines() {
                if let Some(val) = line.strip_prefix("MemTotal:") {
                    total = parse_kb_value(val);
                } else if let Some(val) = line.strip_prefix("MemAvailable:") {
                    available = parse_kb_value(val);
                }
            }
            health.memory_total_kb = total;
            if let (Some(t), Some(a)) = (total, available) {
                health.memory_used_kb = Some(t.saturating_sub(a));
            }
        }

        // Network: check if any non-lo interface is up.
        if let Ok(net_dev) = std::fs::read_to_string("/proc/net/dev") {
            for line in net_dev.lines().skip(2) {
                if let Some(iface) = line.split(':').next() {
                    let iface = iface.trim();
                    if iface != "lo" {
                        // Check operstate.
                        let state_path = format!("/sys/class/net/{iface}/operstate");
                        if let Ok(state) = std::fs::read_to_string(&state_path) {
                            if state.trim() == "up" {
                                health.network_up = true;
                                break;
                            }
                        }
                    }
                }
            }
        }

        health
    }

    /// Non-Linux stub: returns defaults.
    #[cfg(not(target_os = "linux"))]
    pub fn collect() -> Self {
        Self::default()
    }

    /// Format as multi-line text for terminal display.
    pub fn format(&self) -> String {
        let mut lines = Vec::new();
        lines.push("System Health".to_string());
        lines.push("-----------".to_string());

        match self.cpu_temp_c {
            Some(t) => lines.push(format!("CPU Temp:  {t:.1} C")),
            None => lines.push("CPU Temp:  N/A".to_string()),
        }

        match (self.memory_used_kb, self.memory_total_kb) {
            (Some(used), Some(total)) => {
                let pct = if total > 0 {
                    (used as f64 / total as f64) * 100.0
                } else {
                    0.0
                };
                lines.push(format!(
                    "Memory:    {} / {} MiB ({pct:.0}%)",
                    used / 1024,
                    total / 1024
                ));
            },
            _ => lines.push("Memory:    N/A".to_string()),
        }

        match (self.disk_used_kb, self.disk_total_kb) {
            (Some(used), Some(total)) => {
                let pct = if total > 0 {
                    (used as f64 / total as f64) * 100.0
                } else {
                    0.0
                };
                lines.push(format!(
                    "Disk:      {} / {} MiB ({pct:.0}%)",
                    used / 1024,
                    total / 1024
                ));
            },
            _ => lines.push("Disk:      N/A".to_string()),
        }

        lines.push(format!(
            "Network:   {}",
            if self.network_up { "UP" } else { "DOWN" }
        ));

        lines.join("\n")
    }
}

impl fmt::Display for SystemHealth {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.format())
    }
}

/// Parse a value like "  16384000 kB" into `Some(16384000)`.
#[cfg(target_os = "linux")]
fn parse_kb_value(s: &str) -> Option<u64> {
    let s = s.trim().trim_end_matches("kB").trim();
    s.parse().ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_health() {
        let h = SystemHealth::default();
        assert!(h.cpu_temp_c.is_none());
        assert!(h.memory_used_kb.is_none());
        assert!(!h.network_up);
    }

    #[test]
    fn format_all_none() {
        let h = SystemHealth::default();
        let text = h.format();
        assert!(text.contains("System Health"));
        assert!(text.contains("CPU Temp:  N/A"));
        assert!(text.contains("Memory:    N/A"));
        assert!(text.contains("Network:   DOWN"));
    }

    #[test]
    fn format_with_data() {
        let h = SystemHealth {
            cpu_temp_c: Some(42.5),
            memory_used_kb: Some(2048 * 1024),
            memory_total_kb: Some(4096 * 1024),
            disk_used_kb: Some(10240 * 1024),
            disk_total_kb: Some(30720 * 1024),
            network_up: true,
        };
        let text = h.format();
        assert!(text.contains("42.5 C"));
        assert!(text.contains("2048 / 4096 MiB"));
        assert!(text.contains("50%"));
        assert!(text.contains("Network:   UP"));
    }

    #[test]
    fn format_zero_total() {
        let h = SystemHealth {
            memory_used_kb: Some(0),
            memory_total_kb: Some(0),
            ..SystemHealth::default()
        };
        let text = h.format();
        // Should not panic on division by zero.
        assert!(text.contains("0%"));
    }

    #[test]
    fn collect_returns_something() {
        // Just verify it doesn't panic.
        let _h = SystemHealth::collect();
    }

    #[test]
    fn display_impl() {
        let h = SystemHealth::default();
        let text = format!("{h}");
        assert!(text.contains("System Health"));
    }
}
