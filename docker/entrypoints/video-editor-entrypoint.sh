#!/bin/sh
set -e

# Fix ownership of critical directories to match runtime user
# This handles cases where the host UID/GID differs from the build-time user
if [ -d "/output" ]; then
    if ! chown -R "${USER_ID:-1000}:${GROUP_ID:-1000}" /output 2>&1; then
        echo "Warning: Could not change ownership of /output directory (running as $(id -u):$(id -g))"
        echo "  Continuing anyway - write operations may fail if permissions are incorrect"
    fi
fi

if [ -d "/cache" ]; then
    if ! chown -R "${USER_ID:-1000}:${GROUP_ID:-1000}" /cache 2>&1; then
        echo "Warning: Could not change ownership of /cache directory (running as $(id -u):$(id -g))"
        echo "  Cache operations may be affected"
    fi
fi

if [ -d "/tmp/video_editor" ]; then
    if ! chown -R "${USER_ID:-1000}:${GROUP_ID:-1000}" /tmp/video_editor 2>&1; then
        echo "Warning: Could not change ownership of /tmp/video_editor directory (running as $(id -u):$(id -g))"
        echo "  Temporary file operations may be affected"
    fi
fi

# Execute the default command
exec "$@"