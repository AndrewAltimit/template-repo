#!/bin/bash
# wipe_drive.sh -- Cryptographic wipe of the data partition.
# Only runs when trigger file exists (enforced by systemd ConditionPathExists).

set -euo pipefail

TRIGGER_FILE="/run/tamper/wipe-authorized"
LOG="/var/log/tamper-wipe.log"
DATA_PARTITION="/dev/mmcblk0p3"   # LUKS2 data partition

log() {
    echo "$(date -Iseconds) [WIPE] $*" | tee -a "$LOG"
}

# Double-check trigger file (defense in depth beyond systemd condition).
if [ ! -f "$TRIGGER_FILE" ]; then
    log "ERROR: Trigger file missing -- refusing to wipe. This should not happen."
    exit 1
fi

log "=== DRIVE WIPE INITIATED ==="
log "Trigger: $(cat "$TRIGGER_FILE")"

# Phase 0: Flush master key from kernel memory BEFORE touching disk.
# luksSuspend wipes the volume key from the dm-crypt target, making the
# in-memory key unrecoverable even if an attacker prevents the subsequent
# disk overwrite or power-off.
if [ -e /dev/mapper/data_crypt ]; then
    log "Phase 0: Suspending LUKS mapping to flush master key from RAM..."
    cryptsetup luksSuspend data_crypt 2>/dev/null || true
    log "Master key wiped from kernel memory"

    log "Closing LUKS mapping..."
    umount /dev/mapper/data_crypt 2>/dev/null || true
    cryptsetup close data_crypt 2>/dev/null || true
fi

# Also suspend root if it exists (belt and suspenders).
if [ -e /dev/mapper/root_crypt ]; then
    log "Suspending root LUKS mapping..."
    cryptsetup luksSuspend root_crypt 2>/dev/null || true
fi

# Phase 1: Destroy LUKS2 header + all key slots (instant, irreversible).
# LUKS2 header is up to 16MB. Overwriting this makes all data permanently
# unrecoverable regardless of what's on the rest of the disk.
log "Phase 1: Destroying LUKS2 header and key material..."
if cryptsetup isLuks "$DATA_PARTITION" 2>/dev/null; then
    dd if=/dev/urandom of="$DATA_PARTITION" bs=1M count=16 conv=notrunc 2>/dev/null
    log "LUKS2 header destroyed -- data is now unrecoverable"
else
    log "WARNING: Target is not LUKS -- performing raw overwrite of first 256MB"
    dd if=/dev/urandom of="$DATA_PARTITION" bs=4M count=64 conv=notrunc 2>/dev/null
fi

# Phase 2: Additional overwrite for defense in depth.
log "Phase 2: Overwriting additional key material regions..."
dd if=/dev/urandom of="$DATA_PARTITION" bs=4M count=64 seek=4 conv=notrunc 2>/dev/null
log "Additional 256MB overwritten"

# Phase 3: Sync and clean up.
sync
rm -f "$TRIGGER_FILE"
log "=== WIPE COMPLETE ==="

# Phase 4: Power off.
log "Shutting down..."
systemctl poweroff --force --force
