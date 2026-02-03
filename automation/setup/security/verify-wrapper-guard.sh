#!/bin/bash
# Wrapper Guard Verification Script
#
# Checks the integrity of the wrapper-guard installation:
# 1. Wrapper binaries at /usr/bin/ report correct integrity hashes
# 2. Real binaries at /usr/lib/wrapper-guard/ have correct permissions
# 3. The wrapper-guard group exists
# 4. dpkg diversions are in place
#
# Usage: sudo bash verify-wrapper-guard.sh
# Exit code: 0 = all checks pass, 1 = one or more checks failed

set -euo pipefail

GUARD_DIR="/usr/lib/wrapper-guard"
GUARD_GROUP="wrapper-guard"
INTEGRITY_FILE="$GUARD_DIR/integrity.json"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0
WARN_COUNT=0

pass() { echo -e "  ${GREEN}PASS${NC} $1"; PASS=$((PASS + 1)); }
fail() { echo -e "  ${RED}FAIL${NC} $1"; FAIL=$((FAIL + 1)); }
warn_check() { echo -e "  ${YELLOW}WARN${NC} $1"; WARN_COUNT=$((WARN_COUNT + 1)); }

echo "============================================================"
echo "Wrapper Guard Verification"
echo "============================================================"
echo ""

# --- Check 1: Guard group exists ---
echo "Checking group..."
if getent group "$GUARD_GROUP" &>/dev/null; then
    pass "Group '$GUARD_GROUP' exists"
else
    fail "Group '$GUARD_GROUP' does not exist"
fi

# --- Check 2: Guard directory exists with correct permissions ---
echo "Checking guard directory..."
if [[ -d "$GUARD_DIR" ]]; then
    pass "Directory $GUARD_DIR exists"

    # Check ownership
    OWNER=$(stat -c '%U:%G' "$GUARD_DIR" 2>/dev/null || echo "unknown")
    if [[ "$OWNER" == "root:$GUARD_GROUP" ]]; then
        pass "Directory ownership: $OWNER"
    else
        fail "Directory ownership: $OWNER (expected root:$GUARD_GROUP)"
    fi

    # Check permissions
    PERMS=$(stat -c '%a' "$GUARD_DIR" 2>/dev/null || echo "unknown")
    if [[ "$PERMS" == "750" ]]; then
        pass "Directory permissions: $PERMS"
    else
        fail "Directory permissions: $PERMS (expected 750)"
    fi
else
    fail "Directory $GUARD_DIR does not exist"
fi

# --- Check 3: Real binaries exist with correct permissions ---
echo "Checking real binaries..."
for binary in git gh; do
    REAL_PATH="$GUARD_DIR/${binary}.real"
    if [[ -f "$REAL_PATH" ]]; then
        pass "Real $binary exists at $REAL_PATH"

        # Check ownership
        OWNER=$(stat -c '%U:%G' "$REAL_PATH" 2>/dev/null || echo "unknown")
        if [[ "$OWNER" == "root:$GUARD_GROUP" ]]; then
            pass "Real $binary ownership: $OWNER"
        else
            fail "Real $binary ownership: $OWNER (expected root:$GUARD_GROUP)"
        fi

        # Check permissions
        PERMS=$(stat -c '%a' "$REAL_PATH" 2>/dev/null || echo "unknown")
        if [[ "$PERMS" == "750" ]]; then
            pass "Real $binary permissions: $PERMS"
        else
            fail "Real $binary permissions: $PERMS (expected 750)"
        fi
    else
        fail "Real $binary not found at $REAL_PATH"
    fi
done

# --- Check 4: Wrapper binaries at /usr/bin/ ---
echo "Checking wrapper binaries..."
for binary in git gh; do
    WRAPPER_PATH="/usr/bin/$binary"
    if [[ -f "$WRAPPER_PATH" ]] && [[ -x "$WRAPPER_PATH" ]]; then
        pass "Wrapper $binary exists at $WRAPPER_PATH"

        # Check it responds to --wrapper-integrity
        INTEGRITY_OUTPUT=$("$WRAPPER_PATH" --wrapper-integrity 2>/dev/null || echo "")
        if echo "$INTEGRITY_OUTPUT" | grep -q "source_hash="; then
            HASH=$(echo "$INTEGRITY_OUTPUT" | grep "source_hash=" | cut -d= -f2)
            pass "Wrapper $binary reports source_hash=$HASH"

            # Compare with recorded hash if integrity file exists
            if [[ -f "$INTEGRITY_FILE" ]]; then
                # Simple grep-based extraction (avoid jq dependency)
                RECORDED=$(grep -A2 "\"$binary\"" "$INTEGRITY_FILE" | grep "source_hash" | sed 's/.*: "\(.*\)".*/\1/' | head -1)
                if [[ "$HASH" == "$RECORDED" ]]; then
                    pass "Wrapper $binary hash matches recorded hash"
                else
                    fail "Wrapper $binary hash MISMATCH: current=$HASH recorded=$RECORDED"
                fi
            else
                warn_check "No integrity file found (cannot compare hashes)"
            fi
        else
            fail "Wrapper $binary does not respond to --wrapper-integrity"
        fi
    else
        fail "Wrapper $binary not found or not executable at $WRAPPER_PATH"
    fi
done

# --- Check 5: dpkg diversions ---
echo "Checking dpkg diversions..."
for binary in git gh; do
    if dpkg-divert --list "/usr/bin/$binary" 2>/dev/null | grep -q "diversion"; then
        DIVERT_TARGET=$(dpkg-divert --list "/usr/bin/$binary" 2>/dev/null | grep -o "to [^ ]*" | head -1 | sed 's/to //')
        pass "dpkg-divert active for /usr/bin/$binary -> $DIVERT_TARGET"
    else
        fail "No dpkg-divert for /usr/bin/$binary (package updates may overwrite wrapper)"
    fi
done

# --- Check 6: Wrapper binary SHA-256 matches recorded ---
echo "Checking binary checksums..."
if [[ -f "$INTEGRITY_FILE" ]]; then
    for binary in git gh; do
        CURRENT_SHA=$(sha256sum "/usr/bin/$binary" 2>/dev/null | cut -d' ' -f1 || echo "none")
        RECORDED_SHA=$(grep -A3 "\"$binary\"" "$INTEGRITY_FILE" | grep "binary_sha256" | sed 's/.*: "\(.*\)".*/\1/' | head -1)
        if [[ -n "$RECORDED_SHA" ]] && [[ "$CURRENT_SHA" == "$RECORDED_SHA" ]]; then
            pass "Binary SHA-256 matches for $binary"
        elif [[ -z "$RECORDED_SHA" ]]; then
            warn_check "No recorded binary SHA-256 for $binary"
        else
            fail "Binary SHA-256 MISMATCH for $binary: current=$CURRENT_SHA recorded=$RECORDED_SHA"
        fi
    done
else
    warn_check "Integrity file not found at $INTEGRITY_FILE"
fi

# --- Summary ---
echo ""
echo "============================================================"
echo "Verification Summary"
echo "============================================================"
echo ""
echo -e "  ${GREEN}Passed:${NC}   $PASS"
if [[ $FAIL -gt 0 ]]; then
    echo -e "  ${RED}Failed:${NC}   $FAIL"
fi
if [[ $WARN_COUNT -gt 0 ]]; then
    echo -e "  ${YELLOW}Warnings:${NC} $WARN_COUNT"
fi
echo ""

if [[ $FAIL -gt 0 ]]; then
    echo -e "${RED}VERIFICATION FAILED${NC} - $FAIL check(s) failed"
    echo ""
    echo "To fix, re-run setup:"
    echo "  sudo bash automation/setup/security/setup-wrapper-guard.sh"
    exit 1
else
    echo -e "${GREEN}VERIFICATION PASSED${NC}"
    exit 0
fi
