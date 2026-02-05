# ESP32 Co-Processor Firmware

Placeholder for the real-time co-processor firmware running on an ESP32-S3 or RP2040.

## Purpose

The co-processor handles time-critical operations that cannot tolerate Linux scheduling jitter:

- Stepper motor pulse generation for syringe pumps and XY gantry (TMC2209 drivers)
- PID thermal control loop for Peltier modules (H-bridge PWM)
- Peristaltic pump PWM control
- DS18B20 1-Wire temperature probe reading
- Watchdog timer for hardware safety

## Planned Implementation

- **Framework**: Embassy (async embedded Rust, no_std)
- **Target**: ESP32-S3 or RP2040 (TBD based on peripheral requirements)
- **Communication**: UART/USB serial to Pi 5 with a simple command protocol
- **Toolchain**: Separate from the main workspace (requires nightly + target-specific build)

## Build (Future)

```bash
# Requires separate toolchain setup
rustup target add riscv32imc-unknown-none-elf  # for ESP32
# or
rustup target add thumbv6m-none-eabi           # for RP2040

cargo build --release
```

## Status

Not yet implemented. The Pi 5 handles all control directly during Phase 1-2.
The co-processor will be introduced in Phase 3 when liquid handling requires
precise real-time stepper control.
