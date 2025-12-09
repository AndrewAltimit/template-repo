#!/bin/bash
# Script to run the dashboard locally with custom password

# Check if password is provided
if [ -z "$1" ]; then
    echo "Usage: ./run_local.sh <password>"
    echo "Example: ./run_local.sh kbvuej4326hgUO8f"
    exit 1
fi

DASHBOARD_PASSWORD="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Remove existing database to ensure password is set
echo "Removing existing database (if any)..."
rm -f "$SCRIPT_DIR/evaluation_results.db" 2>/dev/null

# Option 1: Using Docker directly (recommended)
echo "Starting dashboard with Docker..."
echo "Password will be: $DASHBOARD_PASSWORD"
echo ""

if ! docker run -d \
    --name local-dashboard \
    --rm \
    -p 8501:8501 \
    -e STREAMLIT_SERVER_HEADLESS=true \
    -e STREAMLIT_SERVER_PORT=8501 \
    -e STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    -e DASHBOARD_ADMIN_PASSWORD="$DASHBOARD_PASSWORD" \
    -v "$SCRIPT_DIR:/home/dashboard/app" \
    sleeper-dashboard:latest; then
    echo "Failed to start with existing image, building new one..."

    # Build the image
    cd "$SCRIPT_DIR" || exit
    docker build -t sleeper-dashboard:latest .

    # Try running again
    docker run -d \
        --name local-dashboard \
        --rm \
        -p 8501:8501 \
        -e STREAMLIT_SERVER_HEADLESS=true \
        -e STREAMLIT_SERVER_PORT=8501 \
        -e STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
        -e DASHBOARD_ADMIN_PASSWORD="$DASHBOARD_PASSWORD" \
        -v "$SCRIPT_DIR:/home/dashboard/app" \
        sleeper-dashboard:latest
fi

echo ""
echo "Dashboard starting..."
echo "Access at: http://localhost:8501"
echo "Username: admin"
echo "Password: $DASHBOARD_PASSWORD"
echo ""
echo "To stop: docker stop local-dashboard"
echo ""
echo "Checking status..."
sleep 3
docker ps | grep local-dashboard
