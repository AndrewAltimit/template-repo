#!/bin/bash

# Start Dashboard with Mock Data
# This script initializes the mock database and starts the dashboard

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[SETUP] Initializing mock database..."
python initialize_mock_db.py

echo ""
echo "[LAUNCH] Starting dashboard with mock data..."
echo "   Dashboard will be available at: http://localhost:8501"
echo ""

# Set environment variable to use mock data
export USE_MOCK_DATA=true
export DATABASE_PATH="${SCRIPT_DIR}/evaluation_results_mock.db"

# Start streamlit
streamlit run app.py --server.port 8501
