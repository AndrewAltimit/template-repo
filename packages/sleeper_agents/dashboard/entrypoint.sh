#!/bin/bash
# Dashboard entrypoint script
# Ensures directories exist and have proper permissions before starting Streamlit

set -e

# Create results directory if it doesn't exist (volume mount point)
# This handles the case where the volume is empty or newly created
if [ ! -d /results ]; then
    mkdir -p /results 2>/dev/null || true
fi

# Try to create the database file if it doesn't exist
# This will fail silently if we don't have permissions (read-only volume)
if [ ! -f /results/evaluation_results.db ]; then
    touch /results/evaluation_results.db 2>/dev/null || true
fi

# Ensure data directory exists for local databases
mkdir -p /home/dashboard/app/data 2>/dev/null || true

# If we can't write to /results, use local data directory as fallback
if [ ! -w /results ]; then
    echo "WARNING: /results volume is not writable, using local data directory"
    export DATABASE_PATH=/home/dashboard/app/data/evaluation_results.db
fi

# Execute the main command (streamlit)
exec "$@"
