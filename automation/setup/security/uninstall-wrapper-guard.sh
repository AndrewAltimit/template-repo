#!/bin/bash
# Wrapper Guard Uninstall Script
#
# Reverses the setup-wrapper-guard.sh changes:
# 1. Removes dpkg-divert to restore original binaries to /usr/bin/
# 2. Removes /usr/lib/wrapper-guard/ directory
# 3. Optionally removes the wrapper-guard group
#
# Requires: sudo
# Usage: sudo bash uninstall-wrapper-guard.sh [--remove-group]

set -euo pipefail

GUARD_DIR="/usr/lib/wrapper-guard"
GUARD_GROUP="wrapper-guard"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

REMOVE_GROUP=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --remove-group)
            REMOVE_GROUP=true
            shift
            ;;
        --help|-h)
            echo "Usage: sudo bash $0 [--remove-group]"
            echo ""
            echo "Options:"
            echo "  --remove-group   Also remove the wrapper-guard system group"
            exit 0
            ;;
        *)
            error "Unknown argument: $1"
            ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    error "This script must be run with sudo or as root"
fi

echo "============================================================"
echo "Wrapper Guard Uninstall"
echo "============================================================"
echo ""

# --- Step 1: Restore diverted binaries ---
for binary in git gh; do
    DIVERTED_PATH="$GUARD_DIR/${binary}.real"
    REAL_PATH="/usr/bin/$binary"

    # Check if diversion exists
    if dpkg-divert --list "$REAL_PATH" 2>/dev/null | grep -q "diversion"; then
        info "Removing diversion for $REAL_PATH"
        # Remove the wrapper from /usr/bin/ first
        rm -f "$REAL_PATH"
        # Reverse the diversion (--rename moves the file back)
        dpkg-divert --remove --rename "$REAL_PATH"
        info "Restored original $binary to $REAL_PATH"
    else
        warn "No diversion found for $REAL_PATH"
        # If the real binary is still in the guard dir, move it back manually
        if [[ -f "$DIVERTED_PATH" ]]; then
            info "Moving $DIVERTED_PATH back to $REAL_PATH"
            rm -f "$REAL_PATH"
            mv "$DIVERTED_PATH" "$REAL_PATH"
            chown root:root "$REAL_PATH"
            chmod 0755 "$REAL_PATH"
        fi
    fi
done

# --- Step 2: Remove guard directory ---
if [[ -d "$GUARD_DIR" ]]; then
    info "Removing $GUARD_DIR"
    rm -rf "$GUARD_DIR"
fi

# --- Step 3: Optionally remove group ---
if [[ "$REMOVE_GROUP" == "true" ]]; then
    if getent group "$GUARD_GROUP" &>/dev/null; then
        info "Removing group: $GUARD_GROUP"
        groupdel "$GUARD_GROUP"
    else
        info "Group $GUARD_GROUP does not exist"
    fi
else
    info "Keeping group $GUARD_GROUP (use --remove-group to remove)"
fi

echo ""
echo "============================================================"
echo "Uninstall Complete"
echo "============================================================"
echo ""
info "Original binaries restored to /usr/bin/"
info "Wrapper binaries may still exist in ~/.local/bin/ (not removed)"
echo ""
