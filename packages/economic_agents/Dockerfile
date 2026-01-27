# Build stage
FROM rust:1.85-slim-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy workspace files
COPY Cargo.toml Cargo.lock ./

# Copy all crates
COPY crates/ ./crates/

# Build release binary
RUN cargo build --release --bin economic-agents

# Runtime stage
FROM debian:bookworm-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 agent
USER agent
WORKDIR /home/agent

# Copy binary from builder
COPY --from=builder /app/target/release/economic-agents /usr/local/bin/economic-agents

# Create directories for configs and data
RUN mkdir -p /home/agent/config /home/agent/data

# Default command runs the CLI help
ENTRYPOINT ["economic-agents"]
CMD ["--help"]
