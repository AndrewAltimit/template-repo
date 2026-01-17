# syntax=docker/dockerfile:1.4
# Rust CI/CD Image with Nightly Toolchain for advanced testing
# Includes: Miri (UB detection), Loom (concurrency testing), cross-compile targets
#
# Performance optimizations:
# - BuildKit cache mounts for apt
# - Pre-installed toolchains and targets

FROM rust:1.83-slim

# Install system dependencies with BuildKit cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    git \
    gcc-mingw-w64-x86-64 \
    && rm -rf /var/lib/apt/lists/*

# Install stable toolchain components
RUN rustup component add rustfmt clippy

# Install nightly toolchain with Miri
RUN rustup toolchain install nightly --component miri \
    && rustup run nightly cargo miri setup

# Install cross-compilation targets
RUN rustup target add x86_64-unknown-linux-gnu \
    && rustup target add x86_64-pc-windows-gnu \
    && rustup +nightly target add x86_64-unknown-linux-gnu \
    && rustup +nightly target add x86_64-pc-windows-gnu

# Create working directory
WORKDIR /workspace

# Create a non-root user that will be overridden by docker-compose
RUN useradd -m -u 1000 ciuser

# Default environment (CARGO_HOME set at runtime for write access)
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_TERM_COLOR=always

# Default command
CMD ["bash"]
