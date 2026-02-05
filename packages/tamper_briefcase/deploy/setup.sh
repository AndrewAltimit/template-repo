#!/bin/bash
# setup.sh -- Consolidated setup script for the tamper briefcase system.
# Run on the Raspberry Pi after flashing the OS.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "========================================================"
echo "   Tamper Briefcase -- Initial Setup"
echo "========================================================"
echo ""

# -- 1. Create tamper user --
echo "[1/8] Creating tamper system user..."
if id "tamper" &>/dev/null; then
    echo "  User 'tamper' already exists."
else
    sudo useradd --system --no-create-home --shell /usr/sbin/nologin tamper
    echo "  Created system user 'tamper'."
fi
sudo usermod -aG i2c,gpio tamper 2>/dev/null || true

# -- 2. Enable I2C --
echo "[2/8] Enabling I2C..."
if [ -e /dev/i2c-1 ]; then
    echo "  I2C already enabled."
else
    echo "  Please enable I2C via raspi-config:"
    echo "    sudo raspi-config -> Interface Options -> I2C -> Enable"
    echo "  Then rerun this script."
    exit 1
fi

# -- 3. Install system dependencies --
echo "[3/8] Installing system dependencies..."
sudo apt update -qq
sudo apt install -y -qq cryptsetup zstd i2c-tools

# -- 4. Verify sensors --
echo "[4/8] Verifying sensor connectivity..."
echo "  Scanning I2C bus 1..."
i2cdetect -y 1 2>/dev/null | head -5
echo "  (BH1750 should appear at address 0x23)"
echo ""

# -- 5. Install binaries --
echo "[5/8] Installing binaries..."
BINS=(tamper-sensor tamper-gate tamper-challenge tamper-recovery)
for bin in "${BINS[@]}"; do
    if [ -f "$SCRIPT_DIR/target/release/$bin" ]; then
        sudo cp "$SCRIPT_DIR/target/release/$bin" /usr/local/bin/
        echo "  Installed $bin"
    else
        echo "  WARNING: $bin not found in target/release/. Build first:"
        echo "    cd $SCRIPT_DIR && cargo build --release"
    fi
done

sudo cp "$SCRIPT_DIR/scripts/wipe_drive.sh" /usr/local/bin/
sudo chmod +x /usr/local/bin/wipe_drive.sh
echo "  Installed wipe_drive.sh"

# -- 6. Set tamper password --
echo "[6/8] Setting tamper password..."
sudo mkdir -p /etc/tamper
if [ -f /etc/tamper/password.hash ]; then
    echo "  Password already configured. To reset, run:"
    echo "    sudo tamper-challenge setup"
else
    sudo tamper-challenge setup
fi

# -- 7. Install systemd units --
echo "[7/8] Installing systemd services..."
sudo cp "$SCRIPT_DIR/systemd/tamper-sensor.service" /etc/systemd/system/
sudo cp "$SCRIPT_DIR/systemd/tamper-gate.service" /etc/systemd/system/
sudo cp "$SCRIPT_DIR/systemd/tamper-wipe.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tamper-sensor tamper-gate
echo "  Services installed and enabled."

# -- 8. Start services --
echo "[8/8] Starting services..."
sudo systemctl start tamper-sensor tamper-gate
echo "  Services started."

echo ""
echo "========================================================"
echo "   Setup complete."
echo ""
echo "   Next steps:"
echo "   1. Verify sensors: journalctl -u tamper-sensor -f"
echo "   2. Test arming: close the briefcase, wait 15s"
echo "   3. Set up LUKS partitions (see documentation)"
echo "   4. Build recovery USB on air-gapped workstation"
echo "========================================================"
