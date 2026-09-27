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

CI runs these containerized via `automation-cli ci run tamper-full` (fmt, clippy, tests, build for the host-buildable crates). The gate's arming FSM (`tamper-gate/src/fsm.rs`), its wipe fallback chain (`wipe.rs`), and the sensor's decision logic (`tamper-sensor/src/logic.rs`) are pure and unit tested without hardware; `cargo test -p tamper-sensor` runs the latter on any host.

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
- **Heartbeat watchdog**: The sensor emits periodic heartbeats. If the gate sees no valid sensor event within the heartbeat timeout while armed, it triggers a password challenge (defends against sensor disconnection attacks). Malformed FIFO lines do not reset the watchdog.
- **Light sensor failure is fail-closed**: A failed BH1750 read is reported as `lux: null`, never as a numeric sentinel. After 8 consecutive failed reads the sensor daemon stops sending heartbeats, so the gate's watchdog treats the sensor as compromised (challenge while armed). Hall edge events keep flowing meanwhile.
- **Checked wipe authorization with fallbacks**: On a failed challenge the gate writes the trigger file and starts `tamper-wipe.service`, checking every step. On failure it retries, then runs `wipe_drive.sh` directly (path configurable as `wipe_script`), then forces a power-off so the volume keys leave RAM. It never returns to monitoring after a failed challenge.
- **luksSuspend before wipe**: The wipe script flushes the LUKS master key from kernel RAM via `cryptsetup luksSuspend` before destroying the LUKS header on disk, ensuring the key is unrecoverable even if the attacker interrupts the disk overwrite.
- **Secret zeroization**: Passwords use `secrecy::SecretString`. Recovery secrets, derived keys, KEM shared secrets, decrypted device secrets and parsed private-key bundles are held in `zeroize::Zeroizing` (or types that zeroize on drop). The `pqcrypto` key and shared-secret types do not support zeroization; their bytes are copied into zeroizing buffers as soon as possible.
- **Constant-time password comparison**: Password verification uses `subtle::ConstantTimeEq` to prevent timing attacks.
- **Hybrid post-quantum recovery**: Recovery secrets are wrapped with X25519 + ML-KEM-1024 (classical + post-quantum) and signed with ML-DSA-87, protecting against harvest-now-decrypt-later attacks.

## Recovery Formats

- **Wrap format v2** (written by `tamper-recovery generate`): X-Wing-style combiner. The AES-256-GCM wrapping key is derived with HKDF-SHA512 over a domain label, the ML-KEM shared secret, the X25519 shared secret, the X25519 ephemeral public key, and the X25519 recipient public key, so the key is bound to the exact encapsulation. The wrap also authenticates a version label.
- **Wrap format v1** (earlier builds): still unwrapped, selected only by an explicit `"version": 1` in `recovery_public.json`, with a warning. Unknown or missing versions are rejected, and editing a v2 bundle to claim v1 fails authentication. Regenerate v1 recovery media when convenient.
- **Image signatures**: `sign` streams the image through SHA-512 and signs a domain-separated digest (`BCSIGv2` header). Legacy bare signatures over the raw image still verify, but that path must read the whole image into memory.
- **Private keys are stored unencrypted.** `recovery_private.json` and `recovery_secret.hex` are plain files (created `0600`). Keep them only on protected offline media, such as an encrypted, air-gapped token; anyone who reads them can unwrap the recovery secret and sign images. Both files are parsed into typed, validated structures (unknown fields, wrong key lengths, and malformed nonces are rejected).

## Planned Enhancements

- **Bluetooth headset integration**: Paired audio device connected through the briefcase; voice-command disconnect triggers disarm/re-arm cycle. Reconnection requires opening the briefcase and disarming the wipe protocol before re-pairing.
- **Network alerting**: Signal/webhook on tamper before countdown starts.
- **Dead man's switch**: Server expects heartbeat; triggers remote wipe on silence.
- **Accelerometer** (MPU6050): Motion/tilt as additional tamper signal.
