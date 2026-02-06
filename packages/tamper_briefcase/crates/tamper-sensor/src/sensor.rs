//! Sensor daemon implementation (aarch64 only).
//!
//! Reads Hall effect and light sensors, emits events via FIFO.

use std::fs::OpenOptions;
use std::io::Write;
use std::path::Path;
use std::thread;
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use chrono::Utc;
use rppal::gpio::{Gpio, InputPin, Level};
use rppal::i2c::I2c;

use tamper_common::{
    BH1750_CONTINUOUS_HIGH_RES, BH1750_POWER_ON, Confidence, Config, EventType, HallState,
    TamperEvent,
};

// ---------------------------------------------------------------------------
// Hardware abstractions
// ---------------------------------------------------------------------------

/// Digital Hall effect latch (A3144).
///
/// When the neodymium magnet is present (lid closed), the output is pulled LOW.
/// When absent (lid open), the internal pull-up drives it HIGH.
struct HallSensor {
    pin: InputPin,
}

impl HallSensor {
    fn new(gpio_pin: u8) -> Result<Self> {
        let gpio = Gpio::new().context("Failed to initialize GPIO")?;
        let pin = gpio
            .get(gpio_pin)
            .context("Failed to get GPIO pin")?
            .into_input_pullup();
        Ok(Self { pin })
    }

    /// Returns `true` if the magnet is detected (lid closed).
    fn is_closed(&self) -> bool {
        self.pin.read() == Level::Low
    }
}

/// BH1750 ambient light sensor over I2C.
struct LightSensor {
    i2c: I2c,
    addr: u16,
}

impl LightSensor {
    fn new(bus: u8, addr: u16) -> Result<Self> {
        let mut i2c = I2c::with_bus(bus).context("Failed to open I2C bus")?;
        i2c.set_slave_address(addr)
            .context("Failed to set I2C slave address")?;

        // Power on the sensor.
        i2c.write(&[BH1750_POWER_ON])
            .context("Failed to power on BH1750")?;

        // Start continuous high-resolution measurement mode.
        i2c.write(&[BH1750_CONTINUOUS_HIGH_RES])
            .context("Failed to start BH1750 measurement")?;

        // The first measurement takes ~120ms in high-res mode.
        thread::sleep(Duration::from_millis(180));

        Ok(Self { i2c, addr })
    }

    /// Read ambient light level in lux. Returns -1.0 on I2C failure.
    fn read_lux(&mut self) -> f64 {
        let mut buf = [0u8; 2];
        match self.i2c.read(&mut buf) {
            Ok(_) => {
                let raw = ((buf[0] as u16) << 8) | (buf[1] as u16);
                raw as f64 / 1.2
            },
            Err(e) => {
                log::warn!("I2C read failed (addr=0x{:02X}): {}", self.addr, e);
                -1.0
            },
        }
    }
}

// ---------------------------------------------------------------------------
// Event emission
// ---------------------------------------------------------------------------

/// Write a JSON event line to the FIFO for `tamper-gate` to consume.
fn emit_event(fifo: &mut std::fs::File, event: &TamperEvent) -> Result<()> {
    let line = serde_json::to_string(event).context("Failed to serialize event")?;
    fifo.write_all(line.as_bytes())
        .context("Failed to write to FIFO")?;
    fifo.write_all(b"\n")
        .context("Failed to write newline to FIFO")?;
    fifo.flush().context("Failed to flush FIFO")?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

pub fn run() -> Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();

    let config = Config::load(Path::new(Config::DEFAULT_PATH));

    log::info!("Tamper sensor daemon starting");
    log::info!("  Hall GPIO pin: {}", config.hall_gpio_pin);
    log::info!("  BH1750 I2C addr: 0x{:02X}", config.bh1750_i2c_addr);
    log::info!("  Light threshold: {} lux", config.light_threshold_lux);
    log::info!("  Poll interval: {} ms", config.poll_interval_ms);
    log::info!("  Heartbeat interval: {}s", config.heartbeat_interval_secs);
    log::info!("  Event FIFO: {}", config.event_fifo.display());

    let hall = HallSensor::new(config.hall_gpio_pin)?;
    let mut light = LightSensor::new(config.i2c_bus, config.bh1750_i2c_addr)?;

    // Open FIFO for writing. This blocks until tamper-gate opens the read end.
    log::info!(
        "Waiting for tamper-gate to connect on {}...",
        config.event_fifo.display()
    );
    let mut fifo = OpenOptions::new()
        .write(true)
        .open(&config.event_fifo)
        .context("Failed to open event FIFO for writing")?;
    log::info!("Connected to tamper-gate. Monitoring sensors.");

    let mut prev_closed = hall.is_closed();
    let poll_duration = Duration::from_millis(config.poll_interval_ms);
    let heartbeat_interval = Duration::from_secs(config.heartbeat_interval_secs);
    let mut last_heartbeat = Instant::now();

    loop {
        let lid_closed = hall.is_closed();
        let lux = light.read_lux();
        let hall_state = if lid_closed {
            HallState::Closed
        } else {
            HallState::Open
        };

        // State transition: CLOSED -> OPEN
        if prev_closed && !lid_closed {
            let confidence = if lux > config.light_threshold_lux {
                Confidence::High
            } else {
                Confidence::Medium
            };

            let event = TamperEvent {
                timestamp: Utc::now(),
                event_type: EventType::LidOpened,
                hall_state,
                lux: (lux * 100.0).round() / 100.0,
                confidence,
            };
            log::warn!("LID OPENED (lux={:.1}, confidence={})", lux, confidence);
            if let Err(e) = emit_event(&mut fifo, &event) {
                log::error!("Failed to emit event: {}", e);
            }
        }
        // State transition: OPEN -> CLOSED
        else if !prev_closed && lid_closed {
            let event = TamperEvent {
                timestamp: Utc::now(),
                event_type: EventType::LidClosed,
                hall_state,
                lux: (lux * 100.0).round() / 100.0,
                confidence: Confidence::High,
            };
            log::info!("LID CLOSED (lux={:.1})", lux);
            if let Err(e) = emit_event(&mut fifo, &event) {
                log::error!("Failed to emit event: {}", e);
            }
        }
        // Anomaly: Hall says closed but light is bright
        else if lid_closed && lux > config.light_threshold_lux {
            let event = TamperEvent {
                timestamp: Utc::now(),
                event_type: EventType::LightAnomaly,
                hall_state,
                lux: (lux * 100.0).round() / 100.0,
                confidence: Confidence::Anomaly,
            };
            log::warn!("ANOMALY: Hall=CLOSED but lux={:.1} (possible bypass)", lux);
            if let Err(e) = emit_event(&mut fifo, &event) {
                log::error!("Failed to emit event: {}", e);
            }
        }

        // Periodic heartbeat.
        if last_heartbeat.elapsed() >= heartbeat_interval {
            let event = TamperEvent {
                timestamp: Utc::now(),
                event_type: EventType::Heartbeat,
                hall_state,
                lux: (lux * 100.0).round() / 100.0,
                confidence: Confidence::High,
            };
            if let Err(e) = emit_event(&mut fifo, &event) {
                log::error!("Failed to emit heartbeat: {}", e);
            }
            last_heartbeat = Instant::now();
        }

        prev_closed = lid_closed;
        thread::sleep(poll_duration);
    }
}
