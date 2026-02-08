#!/usr/bin/env bash
# fetch-samples.sh -- Download sample media for OASIS_OS testing.
#
# Downloads a royalty-free song and photo into this directory so the
# Music Player and Photo Viewer apps have real content to display.
#
# Usage:
#   cd packages/oasis_os/samples
#   ./fetch-samples.sh
#
# The downloaded files are git-ignored and never committed.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Fetching sample media for OASIS_OS..."

# --- Sample music (royalty-free from pixabay) ---
MUSIC_FILE="ambient_dawn.mp3"
if [ ! -f "$MUSIC_FILE" ]; then
    echo "Downloading sample song: $MUSIC_FILE"
    curl -fSL -o "$MUSIC_FILE" \
        "https://cdn.pixabay.com/audio/2024/11/28/audio_3a4e843638.mp3" \
        || echo "WARN: Failed to download music sample. You can manually place an MP3 here as $MUSIC_FILE"
else
    echo "Already have: $MUSIC_FILE"
fi

# --- Sample photo (royalty-free from picsum) ---
PHOTO_FILE="sample_landscape.png"
if [ ! -f "$PHOTO_FILE" ]; then
    echo "Downloading sample photo: $PHOTO_FILE"
    curl -fSL -o "$PHOTO_FILE" \
        "https://picsum.photos/480/272.jpg" \
        || echo "WARN: Failed to download photo sample. You can manually place a PNG/JPG here as $PHOTO_FILE"
else
    echo "Already have: $PHOTO_FILE"
fi

echo ""
echo "Done! Sample files are in: $SCRIPT_DIR"
echo "These files are git-ignored and will not be committed."
ls -lh "$SCRIPT_DIR"/*.mp3 "$SCRIPT_DIR"/*.png "$SCRIPT_DIR"/*.jpg 2>/dev/null || true
