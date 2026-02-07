//! Tests for platform services.

use super::*;

#[test]
fn desktop_power_info() {
    let platform = DesktopPlatform::new();
    let info = platform.power_info().unwrap();
    assert_eq!(info.state, BatteryState::NoBattery);
    assert!(info.battery_percent.is_none());
}

#[test]
fn desktop_time_now() {
    let platform = DesktopPlatform::new();
    let t = platform.now().unwrap();
    // Should be a reasonable year.
    assert!(t.year >= 2024);
    assert!((1..=12).contains(&t.month));
    assert!((1..=31).contains(&t.day));
}

#[test]
fn desktop_time_display() {
    let t = SystemTime {
        year: 2026,
        month: 2,
        day: 7,
        hour: 14,
        minute: 30,
        second: 0,
    };
    assert_eq!(t.to_string(), "2026-02-07 14:30:00");
}

#[test]
fn desktop_uptime() {
    let platform = DesktopPlatform::new();
    let up = platform.uptime_secs().unwrap();
    // Just started, should be 0 or very small.
    assert!(up < 5);
}

#[test]
fn desktop_usb_unsupported() {
    let platform = DesktopPlatform::new();
    assert_eq!(platform.usb_state().unwrap(), UsbState::Unsupported);
}

#[test]
fn usb_state_display() {
    assert_eq!(UsbState::Activated.to_string(), "activated");
    assert_eq!(UsbState::Unsupported.to_string(), "unsupported");
}

#[test]
fn desktop_osk_immediate_confirm() {
    let mut platform = DesktopPlatform::new();
    platform.open("Test", "hello").unwrap();
    match platform.poll().unwrap() {
        OskResult::Confirmed(s) => assert_eq!(s, "hello"),
        other => panic!("expected Confirmed, got {other:?}"),
    }
}

#[test]
fn desktop_osk_close() {
    let mut platform = DesktopPlatform::new();
    platform.open("Test", "data").unwrap();
    platform.close().unwrap();
    match platform.poll().unwrap() {
        OskResult::Cancelled => {},
        other => panic!("expected Cancelled after close, got {other:?}"),
    }
}

#[test]
fn days_to_ymd_epoch() {
    let (y, m, d) = services::days_to_ymd(0);
    assert_eq!((y, m, d), (1970, 1, 1));
}

#[test]
fn days_to_ymd_known_date() {
    // 2024-01-01 = 19723 days since epoch.
    let (y, m, d) = services::days_to_ymd(19723);
    assert_eq!((y, m, d), (2024, 1, 1));
}

#[test]
fn days_to_ymd_leap_day() {
    // 2024-02-29 = 19723 + 31 + 28 = 19782 days since epoch.
    // Wait, January has 31 days, so Jan 31 = 19723+30 = 19753.
    // Feb 1 = 19754, Feb 29 = 19754 + 28 = 19782.
    let (y, m, d) = services::days_to_ymd(19782);
    assert_eq!((y, m, d), (2024, 2, 29));
}

#[test]
fn is_leap_checks() {
    assert!(services::is_leap(2000));
    assert!(services::is_leap(2024));
    assert!(!services::is_leap(1900));
    assert!(!services::is_leap(2023));
}
