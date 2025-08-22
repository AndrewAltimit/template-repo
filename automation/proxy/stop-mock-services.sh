#!/bin/bash
# Stop any running mock services on the host

echo "Stopping mock services running on host..."

# Kill processes on port 8050 (mock API)
if lsof -i :8050 2>/dev/null | grep -q LISTEN; then
    echo "Stopping processes on port 8050..."
    lsof -t -i:8050 | xargs -r kill -9 2>/dev/null
    echo "✅ Stopped mock API on port 8050"
else
    echo "No processes found on port 8050"
fi

# Kill processes on port 8052 (translation wrapper)
if lsof -i :8052 2>/dev/null | grep -q LISTEN; then
    echo "Stopping processes on port 8052..."
    lsof -t -i:8052 | xargs -r kill -9 2>/dev/null
    echo "✅ Stopped wrapper on port 8052"
else
    echo "No processes found on port 8052"
fi

# Also kill by process name
pkill -f mock_company_api.py 2>/dev/null || true
pkill -f company_translation_wrapper.py 2>/dev/null || true

echo "All mock services stopped"
