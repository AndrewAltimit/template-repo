# Multi-stage Dockerfile for Strands Rust Runtime
# Optimized for AWS Graviton (ARM64) with static linking

# =============================================================================
# Stage 1: Build the Rust binary
# =============================================================================
FROM --platform=$BUILDPLATFORM rust:1.88-alpine AS builder

# Install build dependencies for cross-compilation and static linking
RUN apk add --no-cache \
    musl-dev \
    openssl-dev \
    openssl-libs-static \
    pkgconfig \
    cmake \
    make \
    perl \
    git

# Set up cross-compilation if needed
ARG TARGETARCH
RUN case "$TARGETARCH" in \
    "arm64") \
        RUST_TARGET="aarch64-unknown-linux-musl" ;; \
    "amd64") \
        RUST_TARGET="x86_64-unknown-linux-musl" ;; \
    *) \
        echo "Unsupported architecture: $TARGETARCH" && exit 1 ;; \
    esac && \
    rustup target add $RUST_TARGET && \
    echo "RUST_TARGET=$RUST_TARGET" > /rust_target.env

# Create app directory
WORKDIR /build

# Copy workspace files for dependency caching
COPY rust-runtime/Cargo.toml rust-runtime/Cargo.lock* ./
COPY rust-runtime/strands-core/Cargo.toml ./strands-core/
COPY rust-runtime/strands-agent/Cargo.toml ./strands-agent/
COPY rust-runtime/strands-models/Cargo.toml ./strands-models/
COPY rust-runtime/strands-tools/Cargo.toml ./strands-tools/
COPY rust-runtime/strands-session/Cargo.toml ./strands-session/
COPY rust-runtime/strands-runtime/Cargo.toml ./strands-runtime/

# Create dummy source files for dependency compilation
RUN mkdir -p strands-core/src strands-agent/src strands-models/src \
    strands-tools/src strands-session/src strands-runtime/src && \
    echo "pub fn dummy() {}" > strands-core/src/lib.rs && \
    echo "pub fn dummy() {}" > strands-agent/src/lib.rs && \
    echo "pub fn dummy() {}" > strands-models/src/lib.rs && \
    echo "pub fn dummy() {}" > strands-tools/src/lib.rs && \
    echo "pub fn dummy() {}" > strands-session/src/lib.rs && \
    echo "fn main() {}" > strands-runtime/src/main.rs

# Build dependencies only (cached layer)
RUN . /rust_target.env && \
    OPENSSL_STATIC=1 \
    OPENSSL_LIB_DIR=/usr/lib \
    OPENSSL_INCLUDE_DIR=/usr/include \
    cargo build --release --target $RUST_TARGET --workspace || true

# Remove dummy sources
RUN rm -rf strands-*/src

# Copy actual source code
COPY rust-runtime/strands-core/src ./strands-core/src
COPY rust-runtime/strands-agent/src ./strands-agent/src
COPY rust-runtime/strands-models/src ./strands-models/src
COPY rust-runtime/strands-tools/src ./strands-tools/src
COPY rust-runtime/strands-session/src ./strands-session/src
COPY rust-runtime/strands-runtime/src ./strands-runtime/src

# Build the final release binary
RUN . /rust_target.env && \
    touch strands-*/src/*.rs && \
    OPENSSL_STATIC=1 \
    OPENSSL_LIB_DIR=/usr/lib \
    OPENSSL_INCLUDE_DIR=/usr/include \
    cargo build --release --target $RUST_TARGET --package strands-runtime && \
    # Copy binary to a known location
    cp target/$RUST_TARGET/release/strands-runtime /strands-runtime && \
    # Strip the binary for smaller size
    strip /strands-runtime || true

# =============================================================================
# Stage 2: Create minimal runtime image
# =============================================================================
FROM --platform=$TARGETPLATFORM alpine:3.20 AS runtime

# Install CA certificates for HTTPS
RUN apk add --no-cache ca-certificates tzdata && \
    rm -rf /var/cache/apk/*

# Create non-root user for security
RUN addgroup -g 1000 agentgroup && \
    adduser -u 1000 -G agentgroup -s /bin/sh -D agentuser

# Set working directory
WORKDIR /app

# Copy the binary from builder
COPY --from=builder /strands-runtime /app/strands-runtime

# Set ownership
RUN chown -R agentuser:agentgroup /app

# Switch to non-root user
USER agentuser

# Environment variables (configurable at runtime)
ENV PORT=8080 \
    MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0 \
    AWS_REGION=us-east-1 \
    LOG_LEVEL=info \
    RUST_LOG=info,strands_runtime=debug \
    OTEL_SERVICE_NAME=strands-rust-runtime

# Expose the HTTP port
EXPOSE 8080

# Health check - matches AgentCore protocol
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/ping || exit 1

# Run the binary
ENTRYPOINT ["/app/strands-runtime"]
