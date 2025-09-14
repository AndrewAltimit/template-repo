#!/bin/bash
# Checksum verification helper script

set -euo pipefail

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

# Default checksums file location
CHECKSUMS_FILE="${CHECKSUMS_FILE:-/opt/databricks/config/checksums.txt}"

verify_checksum() {
    local file="$1"
    local expected_hash="$2"

    if [ -z "$expected_hash" ] || [ "$expected_hash" = "SKIP" ]; then
        echo -e "${RED}Warning: No checksum provided for $file - skipping verification${NC}" >&2
        return 0
    fi

    echo "Verifying checksum for $file..."

    # Calculate actual hash
    local actual_hash
    actual_hash=$(sha256sum "$file" | cut -d' ' -f1)

    if [ "$actual_hash" = "$expected_hash" ]; then
        echo -e "${GREEN}✓ Checksum verified for $file${NC}"
        return 0
    else
        echo -e "${RED}✗ Checksum verification failed for $file${NC}" >&2
        echo -e "${RED}  Expected: $expected_hash${NC}" >&2
        echo -e "${RED}  Actual:   $actual_hash${NC}" >&2
        return 1
    fi
}

get_checksum_from_file() {
    local filename="$1"
    local version="$2"
    local platform="$3"
    local arch="$4"

    if [ ! -f "$CHECKSUMS_FILE" ]; then
        echo "SKIP"
        return
    fi

    # Search for matching checksum
    grep -E "^[a-f0-9]{64}" "$CHECKSUMS_FILE" | while read -r hash file ver plat ar rest; do
        if [[ "$file" == *"$filename"* ]] || \
           { [[ -n "$version" ]] && [[ "$ver" == "$version" ]] && \
            [[ "$plat" == "$platform" ]] && [[ "$ar" == "$arch" ]]; }; then
            echo "$hash"
            return
        fi
    done

    echo "SKIP"
}

# Export functions for use in other scripts
export -f verify_checksum
export -f get_checksum_from_file
