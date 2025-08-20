#!/bin/sh
set -e

# Fix ownership of critical directories to match runtime user
# This handles cases where the host UID/GID differs from the build-time user
if [ -d "/output" ]; then
    chown -R "${USER_ID:-1000}:${GROUP_ID:-1000}" /output 2>/dev/null || \
        echo "Warning: Could not change ownership of /output directory (running as $(id -u):$(id -g))"
fi

if [ -d "/cache" ]; then
    chown -R "${USER_ID:-1000}:${GROUP_ID:-1000}" /cache 2>/dev/null || \
        echo "Warning: Could not change ownership of /cache directory (running as $(id -u):$(id -g))"
fi

if [ -d "/tmp/video_editor" ]; then
    chown -R "${USER_ID:-1000}:${GROUP_ID:-1000}" /tmp/video_editor 2>/dev/null || \
        echo "Warning: Could not change ownership of /tmp/video_editor directory (running as $(id -u):$(id -g))"
fi

# Execute the default command
exec "$@"