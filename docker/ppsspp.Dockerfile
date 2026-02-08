# Multi-stage build for PPSSPP emulator (SDL + Headless)
# Builds from source with patch support for MCP integration.
#
# Build: docker compose build ppsspp
# Run:   docker compose run --rm ppsspp /roms/release/EBOOT.PBP

# ---------------------------------------------------------------------------
# Stage 1: Build PPSSPP from source
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
    cmake \
    git \
    pkg-config \
    libsdl2-dev \
    libglew-dev \
    libcurl4-openssl-dev \
    libfontconfig1-dev \
    libsdl2-ttf-dev \
    libzip-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone PPSSPP with submodules
RUN git clone --depth=1 --recurse-submodules --shallow-submodules \
    https://github.com/hrydgard/ppsspp.git /ppsspp

# Apply patches (if any exist in the patches directory)
COPY docker/ppsspp-patches/ /ppsspp/patches/
RUN cd /ppsspp && \
    if ls patches/*.patch 1>/dev/null 2>&1; then \
        for p in patches/*.patch; do \
            echo "Applying patch: $p" && git apply "$p"; \
        done; \
    else \
        echo "No patches to apply"; \
    fi

# Build both SDL frontend and headless binary
WORKDIR /ppsspp/build
RUN cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DHEADLESS=ON \
    -DUSE_SYSTEM_LIBZIP=ON \
    -DCMAKE_SKIP_RPATH=ON
RUN make -j"$(nproc)"

# ---------------------------------------------------------------------------
# Stage 2: Minimal runtime image
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# Runtime dependencies only (no dev headers)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsdl2-2.0-0 \
    libsdl2-ttf-2.0-0 \
    libglew2.2 \
    libgl1-mesa-glx \
    libopengl0 \
    libfontconfig1 \
    libcurl4 \
    libzip4 \
    zlib1g \
    x11-utils \
    libx11-6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy binaries
COPY --from=builder /ppsspp/build/PPSSPPSDL /usr/local/bin/PPSSPPSDL
COPY --from=builder /ppsspp/build/PPSSPPHeadless /usr/local/bin/PPSSPPHeadless

# Copy assets (shaders, gamecontrollerdb, lang files, etc.)
COPY --from=builder /ppsspp/assets /usr/local/share/ppsspp/assets

# User management (match host UID/GID)
ARG USER_ID=1000
ARG GROUP_ID=1000
RUN groupadd -g ${GROUP_ID} ppsspp || true && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} ppsspp || true

# Create PSP directory structure for the user
RUN mkdir -p /home/ppsspp/.config/ppsspp/PSP/GAME && \
    chown -R ${USER_ID}:${GROUP_ID} /home/ppsspp/.config

# Entrypoint selects headless vs GUI
COPY docker/ppsspp-entrypoint.sh /usr/local/bin/ppsspp-entrypoint.sh
RUN chmod +x /usr/local/bin/ppsspp-entrypoint.sh

USER ppsspp

# Point PPSSPP at the assets directory
ENV PPSSPP_ASSETS_DIR=/usr/local/share/ppsspp/assets

ENTRYPOINT ["/usr/local/bin/ppsspp-entrypoint.sh"]
