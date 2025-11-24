#!/bin/sh
set -e

# Running as root initially, fix ownership of critical directories
# This ensures the container works with any host UID/GID
echo "Setting up permissions for user ${USER_ID:-1000}:${GROUP_ID:-1000}..."

# Update appuser's UID/GID if different from default
if [ "${USER_ID:-1000}" != "1000" ] || [ "${GROUP_ID:-1000}" != "1000" ]; then
    usermod -u "${USER_ID:-1000}" appuser 2>/dev/null || true
    groupmod -g "${GROUP_ID:-1000}" appuser 2>/dev/null || true
fi

# Fix ownership of output directory
if [ -d "/output" ]; then
    chown -R "${USER_ID:-1000}:${GROUP_ID:-1000}" /output
fi

# Fix ownership of the specific gaea2 output directory
if [ -d "/output/gaea2" ]; then
    chown -R "${USER_ID:-1000}:${GROUP_ID:-1000}" /output/gaea2
fi

echo "Permissions configured, starting application as appuser..."

# Execute the command as the non-root user using gosu
exec gosu appuser "$@"
