#!/usr/bin/env bash
# Build OASIS_OS EBOOT.PBP for PSP / PPSSPP.
#
# Prerequisites:
#   rustup toolchain install nightly
#   rustup component add rust-src --toolchain nightly
#   cargo install cargo-psp
#
# Usage:
#   ./build.sh          # debug build
#   ./build.sh release  # release build (optimized)

set -euo pipefail
cd "$(dirname "$0")"

if [ "${1:-}" = "release" ]; then
    cargo psp --release
    echo ""
    echo "EBOOT.PBP: target/mipsel-sony-psp/release/EBOOT.PBP"
else
    cargo psp
    echo ""
    echo "EBOOT.PBP: target/mipsel-sony-psp/debug/EBOOT.PBP"
fi

echo "Copy to: ms0:/PSP/GAME/OASISOS/EBOOT.PBP"
