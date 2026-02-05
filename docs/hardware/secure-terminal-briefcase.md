# Secure Terminal Briefcase

A Raspberry Pi secured inside a briefcase with dual-sensor tamper detection (Hall effect primary + light secondary), a 120-second password challenge on unauthorized open, cryptographic drive wipe on failure, and a quantum-safe encrypted recovery USB for reimaging.

**Implementation**: [`packages/tamper_briefcase/`](../../packages/tamper_briefcase/)

## Purpose

Secure physical transport for a field-deployable agent terminal. The briefcase provides the physical security layer for operating AI agents in untrusted environments -- extending the digital security model (LUKS, split-privilege services) into the physical domain (tamper detection, sensor hardening, cryptographic wipe).

## System Architecture

```
+------------------------------------------------------------------+
|  BRIEFCASE (Pelican 1490 or similar hard case)                   |
|                                                                  |
|  +------------+                                                  |
|  | Neodymium  | <- lid-mounted magnet (epoxied near latch)      |
|  | Magnet     |                                                  |
|  +------------+                                                  |
|  - - - - - - - - - -  lid / base hinge line  - - - - - - - - -  |
|                                                                  |
|  +------------+  +----------+   GPIO    +--------------------+   |
|  | Hall-effect|  | BH1750   |<-------->|  Raspberry Pi 5    |   |
|  | sensor     |  | Light    |   I2C +  |                    |   |
|  | (SS49E /   |  | Sensor   |   GPIO   |  +==============+  |   |
|  |  A3144)    |  +----------+          |  | LUKS2 Root   |  |   |
|  +------------+                        |  | LUKS2 Data   |  |   |
|       ^ aligned with lid magnet        |  +==============+  |   |
|                                        |                    |   |
|  +------------------+   USB-C          |  Recovery USB ->   |   |
|  |  USB-C Power     |<------->internal |  (port, serial-    |   |
|  |  Bank (cradle)   |   lead   USB-C   |   locked)          |   |
|  |  >=10,000 mAh    |                  +--------------------+   |
|  |  (slides out     |                                           |
|  |   for charging)  |                                           |
|  +------------------+                                           |
+------------------------------------------------------------------+
```

---

## Dual-Sensor Tamper Detection

### Why Two Sensors

A light sensor alone is unreliable as a primary trigger. It suffers from seam leakage in bright environments, dark-current drift and temperature variation, and the "briefcase moved under a lamp" problem. Debouncing helps with noise but cannot distinguish "lid opened" from "ambient conditions changed."

The fix: a **Hall effect sensor as the authoritative lid-state indicator** and a **light sensor as secondary confirmation and anti-tamper evidence**.

### Sensor Roles

| Sensor | Role | Failure Mode | Consequence |
|--------|------|--------------|-------------|
| Hall effect (A3144) | **Primary**: authoritative lid open/close detection | Magnet removed/shielded = permanent "open" reading | Triggers challenge (fail-safe) |
| BH1750 light sensor | **Secondary**: confirms physical exposure, detects bypass attempts | Sensor covered or blinded | Hall still triggers independently |

### Decision Matrix

```
Hall says CLOSED + Light LOW  -> Normal (armed, sleeping)
Hall says CLOSED + Light HIGH -> Suspicious (log anomaly, possible bypass attempt)
Hall says OPEN   + Light HIGH -> Confirmed tamper (trigger challenge)
Hall says OPEN   + Light LOW  -> Tamper in dark environment (still trigger -- Hall is authoritative)
```

Key principle: **Hall alone is sufficient to trigger.** Light alone never triggers -- it adds confidence and detects sensor-bypass scenarios.

### Arming Delay

Closing the briefcase does not instantly arm the system. The lid must remain continuously closed (Hall reading "closed") for a configurable delay (default 15 seconds) before transitioning from DISARMED to ARMED. This prevents false triggers while adjusting the latch or contents.

### Wiring

```
Hall Effect Sensor (A3144 -- digital latch, recommended for simplicity)
---------------------------------------------------------------------
VCC  ----------> Pin 1  (3.3V)
GND  ----------> Pin 9  (GND)
OUT  ----------> Pin 7  (GPIO 4)
     +-- 10k pull-up to 3.3V

Magnet present -> OUT = LOW  (lid closed)
Magnet absent  -> OUT = HIGH (lid open)

BH1750 Light Sensor (I2C)
-------------------------
VCC  ----------> Pin 1  (3.3V)
GND  ----------> Pin 6  (GND)
SDA  ----------> Pin 3  (GPIO 2 / SDA1)
SCL  ----------> Pin 5  (GPIO 3 / SCL1)
ADDR ----------> GND    (sets I2C address to 0x23)

Neodymium Magnet (12mm disc, N52 grade)
---------------------------------------
Epoxied to inside of lid, aligned directly above Hall sensor
when lid is closed. 5-10mm gap is fine for A3144.
```

### Physical Placement

Mount the Hall sensor on the base of the briefcase near the latch mechanism. Epoxy a small neodymium disc magnet to the corresponding spot on the lid interior. When closed, the magnet sits directly above the Hall sensor (within ~10mm). The BH1750 mounts nearby, oriented upward toward the lid seam -- the first entry point for light.

---

## Hardware Bill of Materials

### Core Components

| Component | Recommended Model | Purpose | Est. Cost |
|-----------|-------------------|---------|-----------|
| Raspberry Pi | Pi 5 (4GB+) | Main compute | $60-80 |
| MicroSD Card | Samsung PRO Endurance 128GB | OS + data (high-endurance) | $20 |
| Hall Effect Sensor | A3144 (digital latch) | Primary lid-state detection | $1-2 |
| Neodymium Magnet | 12mm N52 disc | Hall sensor trigger, lid-mounted | $2-3 |
| Light Sensor | BH1750 (I2C) | Secondary tamper confirmation | $3-5 |
| USB-C Power Bank | Anker 325 or similar (10,000mAh+) | Removable, rechargeable power | $25-35 |
| USB-C cable (short) | 15cm USB-C to USB-C, right-angle | Internal Pi-to-bank connection | $5 |
| Briefcase | Pelican 1490 Laptop Case | Hardened, light-sealed enclosure | $100-150 |
| Recovery USB | IronKey or Samsung T7 Shield | Quantum-safe recovery media | $50-80 |
| Pull-up Resistor | 10k (for A3144) | Hall sensor signal conditioning | $0.10 |
| Mounting | Brass standoffs, M2.5 screws, velcro, foam | Secure all components inside case | $10-15 |

### Battery / Power Design

A standard USB-C power bank in a foam cradle. No proprietary UPS HATs.

The bank sits in a snug foam cutout inside the briefcase, connected to the Pi via a short (15cm) USB-C cable with strain relief. To charge, unplug the cable and slide the bank out. To restore power, slide it back in and reconnect.

Benefits over HAT-based UPS solutions: no proprietary APIs, no pogo pin alignment issues, easy to swap/upgrade the bank, and you can charge it anywhere with any USB-C charger. A 10,000mAh bank will run a Pi 5 for roughly 4-6 hours depending on workload.

**Optional enhancement**: A small always-on MCU (e.g., ATtiny85 or RP2040) powered by the bank with negligible draw (~1mA) can monitor the Hall sensor even when the Pi is off, and trigger a wake signal or audible alarm. This covers the "power bank disconnected while case is closed" attack vector.

---

## Software Architecture

### Split-Privilege Service Model

The system splits into three systemd services enforcing least privilege:

```
+-------------------------------------------------------------+
|  SERVICE ARCHITECTURE                                       |
|                                                             |
|  +----------------------+                                   |
|  | tamper-sensor.service|  <- runs as unprivileged "tamper" |
|  | (reads Hall + Light) |  <- no device writes, no crypto  |
|  | Emits: LidOpened     |  <- writes JSON to root-owned    |
|  |        LidClosed     |     FIFO                         |
|  |        LightAnomaly  |                                   |
|  +----------+-----------+                                   |
|             | FIFO                                          |
|  +----------v-----------+                                   |
|  | tamper-gate.service  |  <- runs as root (minimal)       |
|  | (orchestrator)       |  <- receives sensor events       |
|  | Manages: arming FSM  |  <- launches challenge subprocess|
|  |          challenge   |  <- decides on wipe              |
|  |          lock/unlock |                                   |
|  +----------+-----------+                                   |
|             | only on confirmed failure                     |
|  +----------v-----------+                                   |
|  | tamper-wipe.service  |  <- ConditionPathExists guard    |
|  | (one-shot)           |  <- requires explicit trigger    |
|  | Irreversible action  |     file to start                |
|  +-----------------------+                                   |
+-------------------------------------------------------------+
```

This gives you:
- **Least privilege**: The sensor daemon has zero write access to block devices or crypto subsystems.
- **Explicit gating**: The wipe can only execute when a trigger file exists, created only by the gate service after a confirmed challenge failure.
- **Audit trail**: Each service logs independently. The wipe service's activation is a distinct systemd event.
- **Reduced blast radius**: A bug in the sensor code cannot accidentally trigger a wipe.

### Implementation

All application code is in Rust. See [`packages/tamper_briefcase/`](../../packages/tamper_briefcase/) for the full implementation:

| Crate | Binary | Role |
|-------|--------|------|
| `tamper-common` | (library) | Shared types: `TamperEvent`, `SystemState`, `Config` |
| `tamper-sensor` | `tamper-sensor` | GPIO + I2C sensor reading, FIFO event emission |
| `tamper-gate` | `tamper-gate` | Arming FSM, challenge dispatch, wipe authorization |
| `tamper-challenge` | `tamper-challenge` | Interactive password prompt with scrypt verification |
| `tamper-recovery` | `tamper-recovery` | PQC key generation, wrapping, signing, verification |

Bash scripts handle raw system operations:

| Script | Role |
|--------|------|
| `scripts/wipe_drive.sh` | LUKS header destruction via dd/cryptsetup |
| `scripts/recovery_launcher.sh` | Live USB recovery orchestration |

---

## Disk Encryption (LUKS2)

### Partition Layout

```
/dev/mmcblk0
+-- p1  (256MB)   boot    -- FAT32, unencrypted (kernel + initramfs)
+-- p2  (8GB)     rootfs  -- ext4, LUKS2 encrypted
+-- p3  (rest)    data    -- ext4, LUKS2 encrypted <- PRIMARY WIPE TARGET
```

### Secrets

| Secret | Protects | Stored Where | Backed Up How |
|--------|----------|--------------|---------------|
| Root passphrase | LUKS on /dev/mmcblk0p2 (OS) | Entered at boot (or keyfile in initramfs) | Paper backup in secure location |
| Data passphrase | LUKS on /dev/mmcblk0p3 (user data) | Entered after boot / keyfile | Paper backup + recovery USB (wrapped) |
| Tamper password | Challenge on lid-open | `/etc/tamper/password.hash` (scrypt) | You remember it |

During recovery, you need the root passphrase to unlock the freshly flashed OS and the data passphrase to recreate the data volume. The recovery USB stores the data passphrase in a quantum-safe wrapped form.

### Initial LUKS Setup

```bash
# Encrypted root (entered at boot via initramfs prompt)
sudo cryptsetup luksFormat --type luks2 \
    --cipher aes-xts-plain64 \
    --key-size 512 \
    --hash sha512 \
    --iter-time 5000 \
    /dev/mmcblk0p2

# Encrypted data partition
sudo cryptsetup luksFormat --type luks2 \
    --cipher aes-xts-plain64 \
    --key-size 512 \
    --hash sha512 \
    --iter-time 5000 \
    /dev/mmcblk0p3

# Open and format data
sudo cryptsetup open /dev/mmcblk0p3 data_crypt
sudo mkfs.ext4 -L SECURE_DATA /dev/mapper/data_crypt
```

---

## Recovery USB -- Quantum-Safe Key Wrapping

### What PQC Buys You Here

AES-256-XTS is already quantum-resistant for symmetric data-at-rest encryption. The LUKS container does not need PQC. Where PQC matters is in **how you protect and distribute the recovery key material** -- specifically, public-key operations like key encapsulation and digital signatures.

The threat model: an adversary who captures your recovery USB today and stores the encrypted data, hoping to break the public-key wrapping layer with a future quantum computer. By using a hybrid classical+PQ scheme for key wrapping, you ensure the recovery secret remains protected even against harvest-now-decrypt-later attacks.

### USB Structure

```
Recovery USB (32GB+)
+-- Partition 1 (512MB) -- FAT32, unencrypted
|   +-- recovery_public.json        <- PQ public keys + wrapped blob metadata
|   +-- wrapped_secret.bin           <- Hybrid-encrypted recovery secret
|
+-- Partition 2 (rest) -- LUKS2 encrypted
    |   (passphrase derived from unwrapped recovery secret)
    +-- base_image.img.zst          <- Compressed Pi OS image
    +-- base_image.img.zst.sig      <- ML-DSA-87 detached signature
    +-- tamper_config/              <- /etc/tamper/* files
    |   +-- password.hash
    |   +-- salt
    +-- device_secrets.json.enc     <- Wrapped root + data passphrases
    +-- manifest.json               <- Image version, SHA-256 checksums
```

### Key Wrapping Flow

```
SETUP (on air-gapped workstation):
===================================

1. Generate a 64-byte random RECOVERY SECRET
   +-- This is the master secret. Everything derives from it.

2. Derive the LUKS passphrase for USB Partition 2 via KDF:
   +-- luks_passphrase = HKDF-SHA512(recovery_secret, salt, "usb-luks")

3. Derive a wrapping key for the device secrets bundle:
   +-- wrap_key = HKDF-SHA512(recovery_secret, salt, "device-secrets-wrap")

4. Encrypt device_secrets.json with wrap_key (AES-256-GCM)
   +-- Contains: root_passphrase, data_passphrase

5. Wrap the RECOVERY SECRET using hybrid key encapsulation:
   +-- Classical: X25519 ECDH -> shared_secret_classical
   +-- Post-Quantum: ML-KEM-1024 -> shared_secret_pq
   +-- Combined: SHA-512(shared_secret_classical || shared_secret_pq) -> wrapping_key
       +-- AES-256-GCM-encrypt(recovery_secret, wrapping_key) -> wrapped_blob

6. Sign the disk image with ML-DSA-87

7. Store on USB:
   +-- Partition 1 (clear): public keys, wrapped_blob, salt, signature
   +-- Partition 2 (LUKS): image, device_secrets.json.enc, config

8. Store OFFLINE (paper / air-gapped):
   +-- Classical private key (X25519)
   +-- PQ private key (ML-KEM-1024)
   +-- Signing private key (ML-DSA-87)
   +-- Recovery secret (emergency backup)


RECOVERY (on target Pi, booted from live USB):
===============================================

1. User enters recovery password at prompt
   +-- This password decrypts the offline-stored private keys

2. Unwrap: Use private keys to decapsulate -> recover wrapping_key
   +-- Decrypt wrapped_blob -> RECOVERY SECRET

3. Derive luks_passphrase from recovery secret
   +-- Open USB Partition 2

4. Verify image signature (ML-DSA-87)

5. Flash image to SD card

6. Derive wrap_key, decrypt device_secrets.json.enc
   +-- Retrieve root_passphrase + data_passphrase

7. Configure the freshly flashed system:
   +-- Set up LUKS on root with root_passphrase
   +-- Set up LUKS on data with data_passphrase
   +-- Restore tamper config from tamper_config/
```

### Implementation

Key generation and unwrapping are implemented in the `tamper-recovery` Rust crate:

```bash
# Generate recovery material (air-gapped workstation)
tamper-recovery generate --output-dir ./recovery_keys

# Sign a disk image
tamper-recovery sign --image base_image.img.zst \
    --private-key-file ./recovery_keys/private/recovery_private.json \
    --output base_image.img.zst.sig

# Verify image signature (recovery environment)
tamper-recovery verify --image base_image.img.zst \
    --signature base_image.img.zst.sig \
    --public-meta-file recovery_public.json

# Unwrap device secrets (recovery environment)
tamper-recovery unwrap \
    --private-key-file /media/token/recovery_private.json \
    --public-meta-file /mnt/recovery_meta/recovery_public.json \
    --wrapped-secret-file /mnt/recovery_meta/wrapped_secret.bin \
    --encrypted-secrets-file /mnt/recovery/device_secrets.json.enc
```

---

## Physical Installation Guide

### Briefcase Layout

```
+------------------------------------------------------+
| LID INTERIOR                                         |
|                                                      |
|  +----------+                                        |
|  | Neodymium| <- 12mm disc, epoxied, aligned above   |
|  | Magnet   |   Hall sensor when lid is closed       |
|  +----------+                                        |
|                                                      |
|---- hinge -------------------------------------------|
| BASE                                                 |
|                                                      |
|  +-----+  +---------+                               |
|  |Hall |  | BH1750  | <- both near latch edge        |
|  |A3144|  | (facing |                                |
|  |     |  |  up)    |                                |
|  +--+--+  +----+----+                                |
|     |          |    jumper wires                      |
|  +--+----------+----------+  +-------------------+   |
|  |                        |  |                   |   |
|  |    Raspberry Pi 5      |  |  USB-C Power Bank |   |
|  |    (brass standoffs    |  |  (foam cradle,    |   |
|  |     on acrylic plate)  |  |   slides out)     |   |
|  |                        |  |                   |   |
|  +------------------------+  +-------------------+   |
|                                                      |
|  +------------------------------------------------+  |
|  |  Foam padding / weatherstripping around edges  |  |
|  +------------------------------------------------+  |
+------------------------------------------------------+
```

### Mounting Notes

1. **Hall sensor + magnet alignment**: Most critical mechanical detail. The A3144 needs the magnet within ~10mm when closed. Test alignment before permanently mounting -- use blu-tack first, mark positions, then epoxy.

2. **Light sealing**: Line the briefcase seam with adhesive foam weatherstripping. Aim for < 1 lux when sealed for huge margin before false triggers matter (since light is secondary).

3. **Power bank cradle**: Cut a foam block to snugly hold the bank. Use a short right-angle USB-C cable with strain relief (zip-tied to the mounting plate) so repeated insertion does not stress the Pi's port.

4. **Ventilation**: A Pi 5 under load can thermal-throttle in a sealed case. If running anything heavier than idle monitoring, drill small ventilation holes in the mounting plate or add a slim 5V fan. For a mostly-sleeping tamper monitor, passive cooling is fine.

---

## Setup & Deployment

### Quick Setup

Run the consolidated setup script on the Pi:

```bash
cd packages/tamper_briefcase
cargo build --release
./deploy/setup.sh
```

### Manual Setup Checklist

```bash
# 1. Flash Raspberry Pi OS Lite (64-bit) to SD card
sudo rpi-imager

# 2. Create tamper user
sudo useradd --system --no-create-home --shell /usr/sbin/nologin tamper
sudo usermod -aG i2c,gpio tamper

# 3. Enable I2C
sudo raspi-config  # Interface Options -> I2C -> Enable

# 4. Install dependencies
sudo apt update && sudo apt install -y cryptsetup zstd i2c-tools

# 5. Verify sensors
i2cdetect -y 1        # Should show 0x23 (BH1750)

# 6. Set tamper password
sudo tamper-challenge setup

# 7. Install binaries
sudo cp target/release/tamper-sensor /usr/local/bin/
sudo cp target/release/tamper-gate /usr/local/bin/
sudo cp target/release/tamper-challenge /usr/local/bin/
sudo cp target/release/tamper-recovery /usr/local/bin/
sudo cp scripts/wipe_drive.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/wipe_drive.sh

# 8. Install and enable services
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tamper-sensor tamper-gate
sudo systemctl start tamper-sensor tamper-gate

# 9. Create LUKS partitions (see Disk Encryption section)

# 10. Build recovery USB on air-gapped workstation (see Recovery section)
```

### Testing Procedure

```
Test 1 -- Sensor reads:
  Close case, verify Hall reads LOW, lux < 1.
  Open case, verify Hall reads HIGH, lux jumps.

Test 2 -- Arming delay:
  Close case, watch journal. Confirm ARMING state for 15s, then ARMED.
  Reopen during arming -- confirm return to DISARMED.

Test 3 -- Challenge (non-destructive):
  Temporarily replace wipe_drive.sh with a no-op script.
  Arm the system, open the case, verify challenge prompt appears.
  Enter correct password -- verify DISARMED.
  Enter wrong password 3x -- verify wipe trigger file is created.

Test 4 -- Wipe (sacrificial SD card):
  Use a throwaway SD card with a LUKS partition.
  Run the full wipe flow. Verify LUKS header is destroyed
  (cryptsetup isLuks should fail afterward).

Test 5 -- Recovery:
  Use the recovery USB to reimage the wiped card.
  Verify LUKS is reconfigured and tamper services start on boot.

Test 6 -- Anomaly detection:
  With system armed, shine a flashlight through seams while
  holding magnet in place (simulating Hall bypass). Verify
  LIGHT_ANOMALY events logged and escalation after threshold.
```

---

## Security Considerations

| Threat | Mitigation |
|--------|------------|
| Cold boot attack | Enable encrypted swap; consider kernel memory encryption |
| SD card physical removal | LUKS2 FDE -- data at rest is encrypted |
| Light sensor bypass (tape/cover) | Hall is primary and independent; sustained light anomaly escalates |
| Hall sensor bypass (external magnet) | Light sensor detects exposure; anomaly counter triggers challenge |
| Both sensors bypassed simultaneously | Requires precise physical access; consider potting sensors in epoxy |
| Power cut to prevent wipe | Battery bank provides independent power |
| Power bank removed while closed | Optional: always-on MCU monitors Hall independently |
| USB device injection | Lock USB ports by serial number; only allow recovery stick |
| Recovery stick theft | Hybrid PQ+classical encryption; private keys stored separately offline |
| Shoulder surfing | Consider OLED display instead of HDMI for password entry |
| Wipe triggered accidentally | Split-service architecture with explicit trigger file guard |

---

## Planned Enhancements

### Bluetooth Headset Integration (Next)

Paired audio device connected through the briefcase. Voice-command disconnect triggers a disarm/re-arm cycle. Reconnection requires:

1. Opening the briefcase (triggers tamper challenge)
2. Authenticating via password challenge
3. Disarming the wipe protocol
4. Re-pairing the Bluetooth audio device

This ensures the headset cannot be silently reassociated without passing through the full tamper response chain.

### Other Planned Features

- **Network alerting**: Send Signal/Telegram/webhook on tamper before countdown starts
- **Dead man's switch**: Server expects heartbeat every N hours; triggers remote wipe on silence
- **Decoy partition**: Wrong password shows fake desktop; real data stays in hidden LUKS volume
- **TPM 2.0 HAT**: Bind LUKS keys to hardware state (detects SD card moved to different Pi)
- **Accelerometer** (MPU6050): Detect motion/tilt as additional tamper signal
- **GPS geofencing**: Alert or trigger if briefcase leaves defined geographic area
- **Faraday cage lining**: Copper mesh inside case to block RF (WiFi/Bluetooth attacks)
- **Always-on MCU co-processor**: ATtiny85/RP2040 on battery, monitors Hall even when Pi is off, triggers piezo alarm
