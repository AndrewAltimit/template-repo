//! Platform service traits and desktop implementation.

use crate::error::Result;

// ---------------------------------------------------------------------------
// Power service
// ---------------------------------------------------------------------------

/// Battery / power state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BatteryState {
    /// Running on battery.
    Discharging,
    /// Plugged in and charging.
    Charging,
    /// Fully charged, on external power.
    Full,
    /// No battery present (desktop / wall power).
    NoBattery,
}

/// CPU clock speed.
#[derive(Debug, Clone, Copy)]
pub struct CpuClock {
    /// Current frequency in MHz.
    pub current_mhz: u32,
    /// Maximum frequency in MHz (0 if unknown).
    pub max_mhz: u32,
}

/// Snapshot of power-related information.
#[derive(Debug, Clone)]
pub struct PowerInfo {
    /// Battery charge percentage (0-100), or `None` if no battery.
    pub battery_percent: Option<u8>,
    /// Estimated minutes remaining, or `None` if unknown/charging.
    pub battery_minutes: Option<u32>,
    /// Current battery state.
    pub state: BatteryState,
    /// CPU clock info.
    pub cpu: CpuClock,
}

/// Abstraction over platform power management.
pub trait PowerService {
    /// Query current power information.
    fn power_info(&self) -> Result<PowerInfo>;
}

// ---------------------------------------------------------------------------
// Time service
// ---------------------------------------------------------------------------

/// A simple wall-clock timestamp.
#[derive(Debug, Clone, Copy)]
pub struct SystemTime {
    pub year: u16,
    pub month: u8,
    pub day: u8,
    pub hour: u8,
    pub minute: u8,
    pub second: u8,
}

impl std::fmt::Display for SystemTime {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{:04}-{:02}-{:02} {:02}:{:02}:{:02}",
            self.year, self.month, self.day, self.hour, self.minute, self.second,
        )
    }
}

/// Abstraction over platform time services.
pub trait TimeService {
    /// Current wall-clock time.
    fn now(&self) -> Result<SystemTime>;

    /// Seconds since the platform booted (or the process started).
    fn uptime_secs(&self) -> Result<u64>;
}

// ---------------------------------------------------------------------------
// USB service
// ---------------------------------------------------------------------------

/// USB connection state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum UsbState {
    /// USB storage is deactivated.
    Deactivated,
    /// USB storage is active (device exposed as mass storage).
    Activated,
    /// USB cable connected but storage not activated.
    Connected,
    /// No USB cable detected.
    Disconnected,
    /// Platform does not support USB management.
    Unsupported,
}

impl std::fmt::Display for UsbState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Deactivated => write!(f, "deactivated"),
            Self::Activated => write!(f, "activated"),
            Self::Connected => write!(f, "connected"),
            Self::Disconnected => write!(f, "disconnected"),
            Self::Unsupported => write!(f, "unsupported"),
        }
    }
}

/// Abstraction over USB mass-storage management.
pub trait UsbService {
    /// Current USB state.
    fn usb_state(&self) -> Result<UsbState>;

    /// Activate USB mass-storage mode (PSP exposes Memory Stick to host).
    fn activate(&mut self) -> Result<()>;

    /// Deactivate USB mass-storage mode.
    fn deactivate(&mut self) -> Result<()>;
}

// ---------------------------------------------------------------------------
// On-screen keyboard service
// ---------------------------------------------------------------------------

/// Result of an OSK session.
#[derive(Debug, Clone)]
pub enum OskResult {
    /// User confirmed input.
    Confirmed(String),
    /// User cancelled.
    Cancelled,
    /// Still editing (poll again next frame).
    Editing,
}

/// Abstraction over the platform's native on-screen keyboard.
/// On PSP this wraps `sceUtilityOskInitStart`. On desktop, the core
/// `osk` module provides a software keyboard rendered via SDI.
pub trait OskService {
    /// Begin an OSK session with an optional initial string.
    fn open(&mut self, title: &str, initial: &str) -> Result<()>;

    /// Poll the current state. Returns the result or `Editing` if still open.
    fn poll(&mut self) -> Result<OskResult>;

    /// Force-close the OSK.
    fn close(&mut self) -> Result<()>;
}

// ---------------------------------------------------------------------------
// Unified platform trait
// ---------------------------------------------------------------------------

/// Aggregate trait providing access to all platform services.
pub trait Platform: PowerService + TimeService + UsbService + OskService {}

// ---------------------------------------------------------------------------
// Desktop implementation
// ---------------------------------------------------------------------------

/// Default platform implementation for desktop/Pi using `std` facilities.
pub struct DesktopPlatform {
    start_time: std::time::Instant,
    osk_buffer: Option<String>,
    osk_title: Option<String>,
}

impl DesktopPlatform {
    pub fn new() -> Self {
        Self {
            start_time: std::time::Instant::now(),
            osk_buffer: None,
            osk_title: None,
        }
    }
}

impl Default for DesktopPlatform {
    fn default() -> Self {
        Self::new()
    }
}

impl PowerService for DesktopPlatform {
    fn power_info(&self) -> Result<PowerInfo> {
        // Desktop: no battery, unknown clock.
        Ok(PowerInfo {
            battery_percent: None,
            battery_minutes: None,
            state: BatteryState::NoBattery,
            cpu: CpuClock {
                current_mhz: 0,
                max_mhz: 0,
            },
        })
    }
}

impl TimeService for DesktopPlatform {
    fn now(&self) -> Result<SystemTime> {
        use std::time::SystemTime as StdTime;
        let dur = StdTime::now()
            .duration_since(StdTime::UNIX_EPOCH)
            .unwrap_or_default();
        let secs = dur.as_secs();

        // Simple UTC breakdown (no TZ handling -- good enough for an embedded OS).
        let days = secs / 86400;
        let time_of_day = secs % 86400;
        let hour = (time_of_day / 3600) as u8;
        let minute = ((time_of_day % 3600) / 60) as u8;
        let second = (time_of_day % 60) as u8;

        // Days since 1970-01-01 to Y-M-D.
        let (year, month, day) = days_to_ymd(days);

        Ok(SystemTime {
            year,
            month,
            day,
            hour,
            minute,
            second,
        })
    }

    fn uptime_secs(&self) -> Result<u64> {
        Ok(self.start_time.elapsed().as_secs())
    }
}

impl UsbService for DesktopPlatform {
    fn usb_state(&self) -> Result<UsbState> {
        Ok(UsbState::Unsupported)
    }

    fn activate(&mut self) -> Result<()> {
        Ok(()) // No-op on desktop.
    }

    fn deactivate(&mut self) -> Result<()> {
        Ok(()) // No-op on desktop.
    }
}

impl OskService for DesktopPlatform {
    fn open(&mut self, title: &str, initial: &str) -> Result<()> {
        self.osk_title = Some(title.to_string());
        self.osk_buffer = Some(initial.to_string());
        Ok(())
    }

    fn poll(&mut self) -> Result<OskResult> {
        // Desktop has a physical keyboard, so the OSK immediately returns
        // the initial text. Real input comes from TextInput events.
        match self.osk_buffer.take() {
            Some(buf) => Ok(OskResult::Confirmed(buf)),
            None => Ok(OskResult::Cancelled),
        }
    }

    fn close(&mut self) -> Result<()> {
        self.osk_buffer = None;
        self.osk_title = None;
        Ok(())
    }
}

impl Platform for DesktopPlatform {}

// ---------------------------------------------------------------------------
// Date helper
// ---------------------------------------------------------------------------

/// Convert days since Unix epoch to (year, month, day).
pub(crate) fn days_to_ymd(mut days: u64) -> (u16, u8, u8) {
    let mut year = 1970u16;
    loop {
        let year_days = if is_leap(year) { 366 } else { 365 };
        if days < year_days {
            break;
        }
        days -= year_days;
        year += 1;
    }
    let leap = is_leap(year);
    let month_days: [u64; 12] = [
        31,
        if leap { 29 } else { 28 },
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31,
    ];
    let mut month = 0u8;
    for (i, &md) in month_days.iter().enumerate() {
        if days < md {
            month = (i + 1) as u8;
            break;
        }
        days -= md;
    }
    if month == 0 {
        month = 12;
    }
    (year, month, (days + 1) as u8)
}

pub(crate) fn is_leap(y: u16) -> bool {
    (y.is_multiple_of(4) && !y.is_multiple_of(100)) || y.is_multiple_of(400)
}
