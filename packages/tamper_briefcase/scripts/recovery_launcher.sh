#!/bin/bash
# recovery_launcher.sh -- Boot from live USB, authenticate, verify, reimage.
# Run from a Raspberry Pi OS Lite live environment.
# Calls the tamper-recovery Rust binary for crypto operations.

set -euo pipefail

USB_DEVICE="/dev/sda"             # Recovery USB block device
USB_ENCRYPTED="${USB_DEVICE}2"    # Partition 2 (LUKS)
USB_CLEAR="${USB_DEVICE}1"        # Partition 1 (clear)
USB_MOUNT="/mnt/recovery"
CLEAR_MOUNT="/mnt/recovery_meta"
TARGET_DEVICE="/dev/mmcblk0"      # Pi's SD card
RECOVERY_BIN="/usr/local/bin/tamper-recovery"

echo "========================================================"
echo "   BRIEFCASE PI -- RECOVERY MODE"
echo "   Hybrid Quantum-Safe Recovery"
echo "========================================================"
echo ""

# -- Step 1: Mount clear partition to read public material --
mkdir -p "$CLEAR_MOUNT"
mount -o ro "$USB_CLEAR" "$CLEAR_MOUNT"

# -- Step 2: Prompt for USB LUKS passphrase --
echo "Enter recovery USB passphrase:"
read -rs USB_PASSPHRASE
echo ""

# -- Step 3: Open encrypted partition --
echo "Decrypting recovery media..."
if ! echo -n "$USB_PASSPHRASE" | cryptsetup open "$USB_ENCRYPTED" recovery_crypt --key-file=-; then
    echo "[FAIL] Decryption failed. Invalid passphrase."
    umount "$CLEAR_MOUNT"
    exit 1
fi
echo "[OK] Recovery media decrypted."

mkdir -p "$USB_MOUNT"
mount /dev/mapper/recovery_crypt "$USB_MOUNT"

# -- Step 4: Verify image signature --
echo "Verifying image signature (ML-DSA-87)..."
if ! "$RECOVERY_BIN" verify \
    --image "$USB_MOUNT/base_image.img.zst" \
    --signature "$USB_MOUNT/base_image.img.zst.sig" \
    --public-meta-file "$CLEAR_MOUNT/recovery_public.json"; then
    echo "[FAIL] Signature verification FAILED. Image may be tampered."
    umount "$USB_MOUNT"
    cryptsetup close recovery_crypt
    umount "$CLEAR_MOUNT"
    exit 1
fi
echo "[OK] Image signature verified."

# -- Step 5: Decrypt device secrets --
echo ""
echo "To restore device encryption, you need the recovery secret."
echo "This requires your offline private keys."
echo ""
echo "Enter path to recovery_private.json (e.g., /media/secure-token/recovery_private.json):"
read -r PRIVATE_KEY_PATH

HAVE_DEVICE_SECRETS=false

if [ ! -f "$PRIVATE_KEY_PATH" ]; then
    echo "[FAIL] Private key file not found: $PRIVATE_KEY_PATH"
    echo "  You can still reimage, but will need to set up encryption manually."
    read -rp "Continue without device secrets? [y/N]: " CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        umount "$USB_MOUNT"
        cryptsetup close recovery_crypt
        umount "$CLEAR_MOUNT"
        exit 0
    fi
else
    echo "Unwrapping device secrets..."
    if "$RECOVERY_BIN" unwrap \
        --private-key-file "$PRIVATE_KEY_PATH" \
        --public-meta-file "$CLEAR_MOUNT/recovery_public.json" \
        --wrapped-secret-file "$CLEAR_MOUNT/wrapped_secret.bin" \
        --encrypted-secrets-file "$USB_MOUNT/device_secrets.json.enc" \
        --output /tmp/.device_secrets.json; then
        HAVE_DEVICE_SECRETS=true
    else
        echo "[FAIL] Failed to unwrap device secrets."
    fi
fi

# -- Step 6: Confirm destructive operation --
echo ""
echo "WARNING: This will completely reimage $TARGET_DEVICE"
echo "   All existing data on the SD card will be destroyed."
echo ""
read -rp "Type 'REIMAGE' to confirm: " CONFIRM

if [ "$CONFIRM" != "REIMAGE" ]; then
    echo "Aborted."
    [ -f /tmp/.device_secrets.json ] && shred -u /tmp/.device_secrets.json
    umount "$USB_MOUNT"
    cryptsetup close recovery_crypt
    umount "$CLEAR_MOUNT"
    exit 0
fi

# -- Step 7: Flash base image --
echo "Reimaging $TARGET_DEVICE... (this will take several minutes)"
zstd -d -c "$USB_MOUNT/base_image.img.zst" | dd of="$TARGET_DEVICE" bs=4M status=progress
sync
echo "[OK] Base image written."

# -- Step 8: Set up encryption on target --
if [ "$HAVE_DEVICE_SECRETS" = true ]; then
    echo "Setting up LUKS encryption on target..."

    ROOT_PASS=$(python3 -c "import json; print(json.load(open('/tmp/.device_secrets.json'))['root_passphrase'])")
    DATA_PASS=$(python3 -c "import json; print(json.load(open('/tmp/.device_secrets.json'))['data_passphrase'])")

    # Format and open root partition.
    echo -n "$ROOT_PASS" | cryptsetup luksFormat --type luks2 \
        --cipher aes-xts-plain64 --key-size 512 --hash sha512 \
        "${TARGET_DEVICE}p2" --key-file=-

    echo -n "$ROOT_PASS" | cryptsetup open "${TARGET_DEVICE}p2" target_root --key-file=-

    echo "Restoring root filesystem..."
    mkfs.ext4 -L ROOT /dev/mapper/target_root
    mkdir -p /mnt/target_root
    mount /dev/mapper/target_root /mnt/target_root

    # Restore tamper config.
    echo "Restoring tamper configuration..."
    mkdir -p /mnt/target_root/etc/tamper
    cp "$USB_MOUNT/tamper_config/"* /mnt/target_root/etc/tamper/
    chmod 600 /mnt/target_root/etc/tamper/*

    # Format data partition.
    echo -n "$DATA_PASS" | cryptsetup luksFormat --type luks2 \
        --cipher aes-xts-plain64 --key-size 512 --hash sha512 \
        "${TARGET_DEVICE}p3" --key-file=-

    # Clean up target mounts.
    umount /mnt/target_root
    cryptsetup close target_root

    # Shred temporary secrets.
    shred -u /tmp/.device_secrets.json
    echo "[OK] Encryption configured. Temporary secrets destroyed."
else
    echo "Skipping encryption setup (no device secrets available)."
    echo "You will need to set up LUKS manually after first boot."
fi

# -- Step 9: Cleanup --
sync
umount "$USB_MOUNT"
cryptsetup close recovery_crypt
umount "$CLEAR_MOUNT"

echo ""
echo "========================================================"
echo "   [OK] RECOVERY COMPLETE"
echo "   Remove recovery USB, remove private key media,"
echo "   and reboot."
echo "========================================================"
