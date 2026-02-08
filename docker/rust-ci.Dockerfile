# syntax=docker/dockerfile:1.4
# Rust CI/CD Image for injection_toolkit and other Rust projects
# Performance optimizations:
# - BuildKit cache mounts for apt and cargo
# - Rust 1.90+ (required for edition 2024 and let chains)
# - Incremental compilation cache

FROM rust:1.93-slim

# Install system dependencies with BuildKit cache
# libx11-dev etc. are needed for the overlay crate
# libasound2-dev is needed for cpal (audio output via ALSA)
# libav* / libsw* / clang are needed for ffmpeg-next (video decoding)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    libx11-dev \
    libxext-dev \
    libxrandr-dev \
    libxi-dev \
    libxcursor-dev \
    libxinerama-dev \
    libasound2-dev \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libavfilter-dev \
    libavdevice-dev \
    libswresample-dev \
    libswscale-dev \
    clang \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install rustfmt, clippy, and llvm-tools for coverage
RUN rustup component add rustfmt clippy llvm-tools-preview

# Install cargo tools for CI
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    cargo install cargo-deny --locked 2>/dev/null || true && \
    cargo install cargo-llvm-cov --locked 2>/dev/null || true

# Create working directory
WORKDIR /workspace

# Create a non-root user that will be overridden by docker-compose
# CARGO_HOME is set to /tmp/cargo at runtime for universal write access
RUN useradd -m -u 1000 ciuser \
    && mkdir -p /tmp/cargo && chmod 1777 /tmp/cargo

# Default CARGO_HOME for write access (matches docker-compose runtime override)
ENV CARGO_HOME=/tmp/cargo
ENV RUSTUP_HOME=/usr/local/rustup

# Configure cargo for CI (faster linking, better output)
ENV CARGO_INCREMENTAL=1 \
    CARGO_NET_RETRY=10 \
    RUST_BACKTRACE=short

# Default command
CMD ["bash"]
