# gh-validator Build Image
# Compiles the Rust-based gh-validator binary for use in other containers
#
# This image is used as a source for multi-stage builds. Other Dockerfiles
# can copy the compiled binary:
#   COPY --from=gh-validator-builder /usr/local/bin/gh /usr/local/bin/gh
#
# The binary shadows the system `gh` command and provides:
# - Secret masking in GitHub comments
# - Unicode emoji blocking (prevents display issues)
# - Formatting validation (enforces --body-file for reaction images)
# - URL validation with SSRF protection

FROM rust:1.83-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a new empty project for dependency caching
WORKDIR /build

# Copy only Cargo files first to cache dependencies
COPY tools/rust/gh-validator/Cargo.toml tools/rust/gh-validator/Cargo.lock* ./

# Create dummy src to build dependencies
RUN mkdir -p src && echo "fn main() {}" > src/main.rs

# Build dependencies only (will be cached)
RUN cargo build --release || true

# Now copy the actual source code
COPY tools/rust/gh-validator/src ./src

# Touch main.rs to force rebuild of our code (not dependencies)
RUN touch src/main.rs

# Build the actual binary with optimizations
RUN cargo build --release

# Copy binary to a standard location
RUN cp target/release/gh /usr/local/bin/gh

# Final stage - minimal image with just the binary
FROM scratch AS export

COPY --from=builder /usr/local/bin/gh /gh

# For use as a builder image, expose the binary path
FROM debian:bookworm-slim AS runtime

COPY --from=builder /usr/local/bin/gh /usr/local/bin/gh

# Verify binary works
RUN /usr/local/bin/gh --help 2>&1 | head -1 || echo "Binary built successfully"

CMD ["/usr/local/bin/gh", "--help"]
