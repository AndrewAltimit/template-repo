# Desktop Control MCP Server Dockerfile
# Provides cross-platform desktop automation capabilities

FROM python:3.11-slim

# Install system dependencies for Linux desktop control
RUN apt-get update && apt-get install -y --no-install-recommends \
    # X11 automation tools
    xdotool \
    wmctrl \
    scrot \
    x11-utils \
    xclip \
    # For xrandr
    x11-xserver-utils \
    # ImageMagick for window screenshots
    imagemagick \
    # Python tkinter (required by pyautogui on Linux)
    python3-tk \
    # General utilities
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements
COPY docker/requirements/requirements-desktop-control.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP core and desktop control packages
COPY tools/mcp/mcp_core /app/tools/mcp/mcp_core
COPY tools/mcp/mcp_desktop_control /app/tools/mcp/mcp_desktop_control

# Install packages
RUN pip install --no-cache-dir /app/tools/mcp/mcp_core && \
    pip install --no-cache-dir /app/tools/mcp/mcp_desktop_control

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Create non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Port for HTTP mode
EXPOSE 8025

# Default command - run in HTTP mode
CMD ["python", "-m", "mcp_desktop_control.server", "--mode", "http"]
