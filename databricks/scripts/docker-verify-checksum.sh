#!/bin/bash
# Helper script for Dockerfile checksum verification using centralized checksums.txt

set -euo pipefail

FILE="$1"
FILENAME="$2"
CHECKSUMS_FILE="${3:-/opt/databricks/config/checksums.txt}"

if [ ! -f "$CHECKSUMS_FILE" ]; then
    echo "Warning: Checksums file not found at $CHECKSUMS_FILE"
    exit 0
fi

# Extract checksum from the checksums file
EXPECTED_HASH=$(grep -E "^[a-f0-9]{64}.*${FILENAME}" "$CHECKSUMS_FILE" | head -1 | cut -d' ' -f1)

if [ -z "$EXPECTED_HASH" ]; then
    echo "Warning: No checksum found for $FILENAME"
    exit 0
fi

echo "Verifying checksum for $FILENAME..."
echo "${EXPECTED_HASH}  ${FILE}" | sha256sum -c - || exit 1
echo "✓ Checksum verified for $FILENAME"
