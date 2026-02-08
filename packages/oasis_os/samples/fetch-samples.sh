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

# --- Sample music (royalty-free, CC0) ---
# Generate a short WAV tone as a reliable fallback (no network needed for WAV).
# We also try to download a real MP3 from a stable source.
MUSIC_FILE="ambient_dawn.mp3"
if [ ! -f "$MUSIC_FILE" ]; then
    echo "Downloading sample song: $MUSIC_FILE"
    # Try archive.org public domain audio (stable URLs).
    curl -fSL --max-time 15 -o "$MUSIC_FILE" \
        "https://archive.org/download/testmp3testfile/mpthreetest.mp3" 2>/dev/null \
    || {
        echo "WARN: Download failed. Generating a synthetic WAV file instead."
        MUSIC_FILE="ambient_dawn.wav"
        # Generate a 2-second 440Hz sine wave WAV using Python.
        python3 -c "
import struct, math
sr, dur, freq = 44100, 2, 440
samples = [int(16000*math.sin(2*math.pi*freq*t/sr)) for t in range(sr*dur)]
data = struct.pack('<' + 'h'*len(samples), *samples)
with open('$MUSIC_FILE', 'wb') as f:
    f.write(b'RIFF')
    f.write(struct.pack('<I', 36 + len(data)))
    f.write(b'WAVEfmt ')
    f.write(struct.pack('<IHHIIHH', 16, 1, 1, sr, sr*2, 2, 16))
    f.write(b'data')
    f.write(struct.pack('<I', len(data)))
    f.write(data)
" 2>/dev/null || echo "WARN: Could not generate WAV. Place an audio file here as ambient_dawn.mp3"
    }
else
    echo "Already have: $MUSIC_FILE"
fi

# --- Sample photo (royalty-free from picsum) ---
PHOTO_FILE="sample_landscape.png"
if [ ! -f "$PHOTO_FILE" ]; then
    echo "Downloading sample photo: $PHOTO_FILE"
    curl -fSL --max-time 15 -o "$PHOTO_FILE" \
        "https://picsum.photos/480/272.jpg" \
        || echo "WARN: Failed to download photo sample. You can manually place a PNG/JPG here as $PHOTO_FILE"
else
    echo "Already have: $PHOTO_FILE"
fi

echo ""
echo "Done! Sample files are in: $SCRIPT_DIR"
echo "These files are git-ignored and will not be committed."
ls -lh "$SCRIPT_DIR"/*.mp3 "$SCRIPT_DIR"/*.png "$SCRIPT_DIR"/*.jpg 2>/dev/null || true
