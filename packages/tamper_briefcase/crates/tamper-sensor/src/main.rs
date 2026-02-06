//! Tamper sensor daemon -- reads Hall effect and light sensors, emits events.
//!
//! Runs as an unprivileged user (`tamper`). No device writes, no crypto
//! operations. Communicates with `tamper-gate` via a root-owned FIFO.
//!
//! # Sensor roles
//!
//! - **Hall effect (A3144)**: Authoritative lid-state indicator. LOW = magnet
//!   present = lid closed. Alone sufficient to trigger.
//! - **BH1750 light sensor**: Secondary confirmation. Detects bypass attempts
//!   (Hall spoofed while lid is actually open).
//!
//! # Platform requirement
//!
//! This binary requires Raspberry Pi hardware (aarch64). On other architectures,
//! it compiles but exits immediately with an error message.

#[cfg(target_arch = "aarch64")]
mod sensor;

fn main() {
    #[cfg(not(target_arch = "aarch64"))]
    {
        eprintln!(
            "tamper-sensor requires Raspberry Pi hardware (aarch64), current arch: {}",
            std::env::consts::ARCH,
        );
        eprintln!("For cross-compilation: cargo build --target aarch64-unknown-linux-gnu");
        std::process::exit(1);
    }

    #[cfg(target_arch = "aarch64")]
    {
        if let Err(e) = sensor::run() {
            eprintln!("Fatal: {e:#}");
            std::process::exit(1);
        }
    }
}
