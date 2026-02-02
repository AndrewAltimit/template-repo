# Multi-stage Rust build for mcp-content-creation
# Stage 1: Build the Rust binary
# Use bookworm-based rust image to match runtime glibc version
FROM rust:1.93-slim-bookworm AS builder

# Install build dependencies for OpenSSL
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy MCP core framework first (dependency)
COPY tools/mcp/mcp_core_rust /build/tools/mcp/mcp_core_rust

# Copy content creation server
COPY tools/mcp/mcp_content_creation /build/tools/mcp/mcp_content_creation

# Build the binary
WORKDIR /build/tools/mcp/mcp_content_creation
RUN cargo build --release

# Stage 2: Runtime image with LaTeX and Manim dependencies
# Use python:3.11-slim for glibc compatibility with rust:1.93 builder
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # LaTeX packages - using smaller base package instead of texlive-full
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-latex-extra \
    texlive-science \
    texlive-pictures \
    # LaTeX build automation (for multi-pass compilation)
    latexmk \
    # PDF utilities (pdfinfo, pdftoppm)
    poppler-utils \
    pdf2svg \
    # Video/animation dependencies
    ffmpeg \
    # Cairo for Manim (runtime libs)
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    # Build tools for pycairo (manim dependency)
    build-essential \
    pkg-config \
    libcairo2-dev \
    libpango1.0-dev \
    # Networking
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Manim (Community edition)
RUN pip install --no-cache-dir manim

# Remove build dependencies to reduce image size
RUN apt-get update && apt-get remove -y \
    build-essential \
    pkg-config \
    libcairo2-dev \
    libpango1.0-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Create app user with configurable UID/GID
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} mcp || true && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} mcp || true

# Create directories
RUN mkdir -p /app /output && \
    chown -R mcp:mcp /app /output

WORKDIR /app

# Copy the binary from builder
COPY --from=builder /build/tools/mcp/mcp_content_creation/target/release/mcp-content-creation /usr/local/bin/

# Set permissions
RUN chmod +x /usr/local/bin/mcp-content-creation

# Switch to non-root user
USER mcp

# Environment
ENV RUST_LOG=info
ENV MCP_OUTPUT_DIR=/output
ENV MCP_PROJECT_ROOT=/app
ENV MANIM_MEDIA_DIR=/output/manim

# Expose port
EXPOSE 8011

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8011/health || exit 1

# Default command
CMD ["mcp-content-creation", "--mode", "standalone", "--port", "8011"]
