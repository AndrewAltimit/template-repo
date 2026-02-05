# Tamper Briefcase

> A tamper-responsive Raspberry Pi briefcase system with dual-sensor detection, cryptographic drive wipe, and quantum-safe encrypted recovery.

## Overview

Secure physical transport for a field-deployable agent terminal. A Raspberry Pi 5 is mounted inside a hardened briefcase (Pelican 1490) with dual-sensor tamper detection (Hall effect primary + light secondary), a 120-second password challenge on unauthorized open, LUKS2 full-disk encryption with cryptographic wipe on failure, and a hybrid classical+post-quantum encrypted recovery USB for reimaging.

**Design documentation**: [`docs/hardware/secure-terminal-briefcase.md`](../../docs/hardware/secure-terminal-briefcase.md)

## Architecture

```
tamper-sensor (unprivileged) --> FIFO --> tamper-gate (root) --> tamper-challenge
                                                |
                                         [on failure]
                                                |
                                                v
                                         tamper-wipe.service
```

Three systemd services enforce split-privilege operation:

| Service | Privilege | Role |
|---------|-----------|------|
| `tamper-sensor` | User `tamper` | Reads Hall + light sensors, emits events + heartbeats |
| `tamper-gate` | Root (restricted) | Arming FSM, heartbeat watchdog, challenge dispatch, wipe authorization |
| `tamper-wipe` | Root (one-shot) | luksSuspend + irreversible LUKS header destruction |

The gate uses poll-based I/O with a heartbeat watchdog: if the sensor daemon stops sending heartbeats while the system is armed, the gate treats it as a tamper (sensor may have been physically disconnected or disabled).

## Workspace Structure

```
packages/tamper_briefcase/
+-- Cargo.toml                  # Workspace root
+-- crates/
|   +-- tamper-common/          # Shared types (events, config, state machine)
|   +-- tamper-sensor/          # Sensor daemon (rppal GPIO + I2C)
|   +-- tamper-gate/            # Gate orchestrator (arming FSM)
|   +-- tamper-challenge/       # Password challenge (scrypt verification)
|   +-- tamper-recovery/        # PQC key generation, wrapping, signing
+-- scripts/
|   +-- wipe_drive.sh           # Cryptographic drive wipe (bash)
|   +-- recovery_launcher.sh    # Live USB recovery orchestration (bash)
+-- systemd/
|   +-- tamper-sensor.service
|   +-- tamper-gate.service
|   +-- tamper-wipe.service
+-- deploy/
    +-- setup.sh                # Initial Pi setup script
```

## Build

Targets `aarch64-unknown-linux-gnu` (Raspberry Pi 5). Cross-compile from x86_64:

```bash
# Install cross-compilation toolchain
rustup target add aarch64-unknown-linux-gnu

# Build
cd packages/tamper_briefcase
cargo build --release --target aarch64-unknown-linux-gnu
```

For development/CI on x86_64 (check + lint only, no hardware access):

```bash
cargo check --workspace
cargo clippy --workspace
cargo fmt --check
```

## Deploy

On the Raspberry Pi:

```bash
./deploy/setup.sh
```

See [`docs/hardware/secure-terminal-briefcase.md`](../../docs/hardware/secure-terminal-briefcase.md) for complete deployment instructions including sensor wiring, LUKS setup, and recovery USB preparation.

## Crate Dependencies

| Crate | Key Dependencies |
|-------|-----------------|
| `tamper-common` | serde, toml, chrono |
| `tamper-sensor` | rppal (GPIO, I2C), tamper-common |
| `tamper-gate` | nix (FIFO, poll, signals), tamper-common |
| `tamper-challenge` | rpassword, scrypt, subtle, secrecy |
| `tamper-recovery` | x25519-dalek, pqcrypto-mlkem, pqcrypto-mldsa, aes-gcm, hkdf, secrecy, zeroize |

## Security Features

- **Split-privilege services**: Sensor runs unprivileged; only the gate has root access. The wipe service is a separate one-shot unit with a trigger file guard.
- **Heartbeat watchdog**: The sensor emits periodic heartbeats. If the gate detects sensor silence while armed, it triggers a password challenge (defends against sensor disconnection attacks).
- **luksSuspend before wipe**: The wipe script flushes the LUKS master key from kernel RAM via `cryptsetup luksSuspend` before destroying the LUKS header on disk, ensuring the key is unrecoverable even if the attacker interrupts the disk overwrite.
- **Automatic secret zeroization**: Password material and cryptographic keys use `secrecy::SecretString` and `zeroize::Zeroizing` for automatic cleanup on drop.
- **Constant-time password comparison**: Password verification uses `subtle::ConstantTimeEq` to prevent timing attacks.
- **Hybrid post-quantum recovery**: Recovery secrets are wrapped with X25519 + ML-KEM-1024 (classical + post-quantum) and signed with ML-DSA-87, protecting against harvest-now-decrypt-later attacks.

## Planned Enhancements

- **Bluetooth headset integration**: Paired audio device connected through the briefcase; voice-command disconnect triggers disarm/re-arm cycle. Reconnection requires opening the briefcase and disarming the wipe protocol before re-pairing.
- **Network alerting**: Signal/webhook on tamper before countdown starts.
- **Dead man's switch**: Server expects heartbeat; triggers remote wipe on silence.
- **Accelerometer** (MPU6050): Motion/tilt as additional tamper signal.
