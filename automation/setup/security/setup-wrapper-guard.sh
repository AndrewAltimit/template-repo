#!/bin/bash
# Wrapper Guard Setup Script
#
# Hardens the git-guard and gh-validator wrappers by:
# 1. Creating a system group "wrapper-guard"
# 2. Relocating real git/gh binaries to a restricted directory
# 3. Installing wrapper binaries in their place at /usr/bin/
# 4. Using dpkg-divert to survive package manager updates
#
# After setup:
# - AI agents cannot bypass the wrappers (real binaries are permission-restricted)
# - Wrappers are setgid wrapper-guard, so they can execute the real binaries without
#   granting the calling user direct access
# - Emergency bypass requires sudo (no users are added to the group by default)
# - Package manager updates will place new binaries in the restricted directory, not /usr/bin/
#
# Requires: sudo, dpkg-divert (Debian/Ubuntu)
# Usage: sudo bash setup-wrapper-guard.sh [--wrapper-dir PATH]

set -euo pipefail

# Configuration
GUARD_DIR="/usr/lib/wrapper-guard"
GUARD_GROUP="wrapper-guard"
INTEGRITY_FILE="$GUARD_DIR/integrity.json"

# Default wrapper binary locations
WRAPPER_DIR="${HOME}/.local/bin"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --wrapper-dir)
            WRAPPER_DIR="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: sudo bash $0 [--wrapper-dir PATH]"
            echo ""
            echo "Options:"
            echo "  --wrapper-dir PATH   Directory containing wrapper binaries (default: ~/.local/bin)"
            echo ""
            echo "This script must be run with sudo."
            exit 0
            ;;
        *)
            error "Unknown argument: $1"
            ;;
    esac
done

echo "============================================================"
echo "Wrapper Guard Setup"
echo "============================================================"
echo ""

# --- Validation ---

# Must be run as root (or with sudo)
if [[ $EUID -ne 0 ]]; then
    error "This script must be run with sudo or as root"
fi

# Detect the real user (not root from sudo) -- used for integrity metadata
REAL_USER="${SUDO_USER:-$USER}"

# Check dpkg-divert availability
if ! command -v dpkg-divert &>/dev/null; then
    error "dpkg-divert not found. This script requires Debian/Ubuntu."
fi

# Check wrapper binaries exist
for binary in git gh; do
    if [[ ! -f "$WRAPPER_DIR/$binary" ]]; then
        error "Wrapper binary not found: $WRAPPER_DIR/$binary\n  Build and install wrappers first: tools/rust/install-all.sh"
    fi
    if [[ ! -x "$WRAPPER_DIR/$binary" ]]; then
        error "Wrapper binary not executable: $WRAPPER_DIR/$binary"
    fi
done

# Check real binaries exist at /usr/bin/ (not already diverted)
for binary in git gh; do
    if [[ -L "/usr/bin/$binary" ]]; then
        warn "/usr/bin/$binary is a symlink. Checking if already set up..."
        if [[ -f "$GUARD_DIR/${binary}.real" ]]; then
            info "Already set up: $binary (skipping divert, updating wrapper)"
        fi
    fi
done

# --- Step 1: Create system group ---
info "Creating system group: $GUARD_GROUP"
if getent group "$GUARD_GROUP" &>/dev/null; then
    info "Group $GUARD_GROUP already exists"
else
    groupadd --system "$GUARD_GROUP"
    info "Created group: $GUARD_GROUP"
fi

# --- Step 2: Create protected directory ---
info "Creating protected directory: $GUARD_DIR"
mkdir -p "$GUARD_DIR"
chown root:"$GUARD_GROUP" "$GUARD_DIR"
chmod 0750 "$GUARD_DIR"

# --- Step 3: Relocate real binaries with dpkg-divert ---
for binary in git gh; do
    REAL_PATH="/usr/bin/$binary"
    DIVERTED_PATH="$GUARD_DIR/${binary}.real"

    if [[ -f "$DIVERTED_PATH" ]]; then
        info "Real $binary already relocated to $DIVERTED_PATH"
    elif [[ -f "$REAL_PATH" ]] && [[ ! -L "$REAL_PATH" ]]; then
        info "Relocating /usr/bin/$binary -> $DIVERTED_PATH"

        # dpkg-divert tells the package manager about the relocation.
        # --rename moves the file. --local means this is a local diversion.
        # Future apt upgrades will install the new binary to DIVERTED_PATH, not REAL_PATH.
        dpkg-divert --local --rename --divert "$DIVERTED_PATH" "$REAL_PATH"

        info "Diverted $binary successfully"
    else
        warn "/usr/bin/$binary not found or is a symlink. Manual setup may be needed."
    fi

    # Set restrictive permissions on the real binary
    if [[ -f "$DIVERTED_PATH" ]]; then
        chown root:"$GUARD_GROUP" "$DIVERTED_PATH"
        chmod 0750 "$DIVERTED_PATH"
        info "Set permissions on $DIVERTED_PATH: root:$GUARD_GROUP 0750"
    fi
done

# --- Step 4: Install wrapper binaries as /usr/bin/{git,gh} ---
# Wrappers are setgid wrapper-guard so they inherit group permission
# to execute the real binaries in the restricted directory.
for binary in git gh; do
    info "Installing wrapper: /usr/bin/$binary"
    cp "$WRAPPER_DIR/$binary" "/usr/bin/$binary"
    chown root:"$GUARD_GROUP" "/usr/bin/$binary"
    chmod 2755 "/usr/bin/$binary"
done

# --- Step 5: Record integrity hashes ---
# Note: No users are added to the wrapper-guard group by default.
# The setgid bit on the wrappers allows them to execute the real binaries.
# Emergency bypass requires sudo. To grant a user direct access:
#   sudo usermod -aG wrapper-guard <username>
info "Recording wrapper integrity hashes..."
{
    echo "{"
    echo "  \"setup_date\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
    echo "  \"setup_user\": \"$REAL_USER\","
    echo "  \"wrappers\": {"

    first=true
    for binary in git gh; do
        if [[ "$first" == "true" ]]; then
            first=false
        else
            echo ","
        fi
        # Get the source hash from the wrapper
        HASH=$("/usr/bin/$binary" --wrapper-integrity 2>/dev/null | grep "source_hash=" | cut -d= -f2 || echo "unknown")
        BINARY_SHA=$(sha256sum "/usr/bin/$binary" | cut -d' ' -f1)
        printf "    \"%s\": {\n      \"source_hash\": \"%s\",\n      \"binary_sha256\": \"%s\"\n    }" "$binary" "$HASH" "$BINARY_SHA"
    done

    echo ""
    echo "  },"

    echo "  \"real_binaries\": {"
    first=true
    for binary in git gh; do
        if [[ "$first" == "true" ]]; then
            first=false
        else
            echo ","
        fi
        REAL_SHA=$(sha256sum "$GUARD_DIR/${binary}.real" 2>/dev/null | cut -d' ' -f1 || echo "not_found")
        printf "    \"%s\": {\n      \"path\": \"%s\",\n      \"sha256\": \"%s\"\n    }" "$binary" "$GUARD_DIR/${binary}.real" "$REAL_SHA"
    done
    echo ""
    echo "  }"

    echo "}"
} > "$INTEGRITY_FILE"

chown root:"$GUARD_GROUP" "$INTEGRITY_FILE"
chmod 0640 "$INTEGRITY_FILE"
info "Integrity hashes recorded to $INTEGRITY_FILE"

# --- Summary ---
echo ""
echo "============================================================"
echo "Setup Complete"
echo "============================================================"
echo ""
info "Real binaries:       $GUARD_DIR/{git.real,gh.real}"
info "Wrapper binaries:    /usr/bin/{git,gh}"
info "Guard group:         $GUARD_GROUP"
info "Integrity file:      $INTEGRITY_FILE"
echo ""
echo "Emergency bypass (requires sudo):"
echo "  sudo $GUARD_DIR/git.real <command>"
echo "  sudo $GUARD_DIR/gh.real <command>"
echo ""
echo "To grant a user direct bypass access (not recommended):"
echo "  sudo usermod -aG $GUARD_GROUP <username>"
echo ""
echo "Verify installation:"
echo "  sudo bash automation/setup/security/verify-wrapper-guard.sh"
echo ""
echo "============================================================"
