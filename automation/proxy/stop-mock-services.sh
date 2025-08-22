#!/bin/bash
# Stop any running mock services on the host

echo "Stopping mock services running on host..."

# First try graceful termination by process name
echo "Attempting graceful shutdown..."

# Send SIGTERM to processes (graceful shutdown)
if pkill -f mock_company_api.py; then
    echo "Sent shutdown signal to mock_company_api.py"
fi

if pkill -f company_translation_wrapper.py; then
    echo "Sent shutdown signal to company_translation_wrapper.py"
fi

# Give processes time to cleanup
sleep 2

# Check if processes are still running and force kill if necessary
if pgrep -f mock_company_api.py > /dev/null 2>&1; then
    echo "Force stopping mock_company_api.py..."
    pkill -9 -f mock_company_api.py 2>/dev/null || true
fi

if pgrep -f company_translation_wrapper.py > /dev/null 2>&1; then
    echo "Force stopping company_translation_wrapper.py..."
    pkill -9 -f company_translation_wrapper.py 2>/dev/null || true
fi

# Also check ports and clean up any remaining processes
if lsof -i :"${MOCK_API_PORT:-8050}" 2>/dev/null | grep -q LISTEN; then
    echo "Cleaning up remaining processes on port ${MOCK_API_PORT:-8050}..."
    lsof -t -i:"${MOCK_API_PORT:-8050}" | xargs -r kill 2>/dev/null || true
    sleep 1
    # Force kill if still running
    lsof -t -i:"${MOCK_API_PORT:-8050}" | xargs -r kill -9 2>/dev/null || true
fi

if lsof -i :"${WRAPPER_PORT:-8052}" 2>/dev/null | grep -q LISTEN; then
    echo "Cleaning up remaining processes on port ${WRAPPER_PORT:-8052}..."
    lsof -t -i:"${WRAPPER_PORT:-8052}" | xargs -r kill 2>/dev/null || true
    sleep 1
    # Force kill if still running
    lsof -t -i:"${WRAPPER_PORT:-8052}" | xargs -r kill -9 2>/dev/null || true
fi

echo "All mock services stopped"
