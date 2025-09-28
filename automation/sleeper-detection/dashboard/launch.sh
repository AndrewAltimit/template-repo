#!/bin/bash

# Dashboard Launcher Script
# Launches the Sleeper Detection Dashboard with optional data seeding

set -e

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Change to dashboard directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_DIR="$(cd "$SCRIPT_DIR/../../../packages/sleeper_detection/dashboard" && pwd)"
cd "$DASHBOARD_DIR"

echo -e "${GREEN}=== Sleeper Detection Dashboard Launcher ===${NC}"
echo

# Function to create empty database
create_empty_db() {
    echo -e "${YELLOW}Creating empty database...${NC}"
    python -c "
import sqlite3
conn = sqlite3.connect('evaluation_results.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS evaluation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    test_type TEXT NOT NULL,
    accuracy REAL,
    precision REAL,
    recall REAL,
    f1_score REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    config TEXT,
    notes TEXT
)
''')
conn.commit()
conn.close()
print('Empty database created successfully!')
"
}

# Function to generate mock data
generate_mock_data() {
    echo -e "${YELLOW}Generating mock test data...${NC}"

    # Use the new centralized mock data system
    if [ -f "initialize_mock_db.py" ]; then
        python initialize_mock_db.py
        if [ -f "evaluation_results_mock.db" ]; then
            # Copy mock database to the expected location
            cp evaluation_results_mock.db evaluation_results.db
            echo -e "${GREEN}Mock data generated successfully!${NC}"
            echo -e "${GREEN}Using centralized mock data with 6 models including test-sleeper-v1${NC}"
        else
            echo -e "${RED}Failed to generate mock database${NC}"
            exit 1
        fi
    elif [ -f "tests/fixtures.py" ]; then
        # Fallback to old method if new system not available
        python tests/fixtures.py
        if [ -f "tests/test_evaluation_results.db" ]; then
            cp tests/test_evaluation_results.db evaluation_results.db
            echo -e "${GREEN}Mock data generated successfully (legacy method)!${NC}"
        else
            echo -e "${RED}Failed to generate mock data${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Mock data generator not found!${NC}"
        exit 1
    fi
}

# Function to load specific database file
load_database() {
    local db_file="$1"
    if [ -f "$db_file" ]; then
        cp "$db_file" evaluation_results.db
        echo -e "${GREEN}Database loaded from: $db_file${NC}"
    else
        echo -e "${RED}Database file not found: $db_file${NC}"
        exit 1
    fi
}

# Check if running in Docker or locally
if [ -f /.dockerenv ]; then
    echo "Running in Docker environment"
fi

# Database initialization menu
echo "How would you like to initialize the database?"
echo "1) Seed with mock test data (recommended for demo)"
echo "2) Initialize empty database"
echo "3) Load from specific file"
echo "4) Use existing database (if available)"
echo "5) Reset authentication (recreate admin user)"
echo
read -r -p "Select option [1-5]: " option

case $option in
    1)
        generate_mock_data
        ;;
    2)
        create_empty_db
        ;;
    3)
        read -r -p "Enter path to database file: " db_path
        load_database "$db_path"
        ;;
    4)
        if [ -f "evaluation_results.db" ]; then
            echo -e "${GREEN}Using existing database${NC}"
        else
            echo -e "${YELLOW}No existing database found, creating empty one...${NC}"
            create_empty_db
        fi
        ;;
    5)
        echo -e "${YELLOW}Resetting authentication...${NC}"
        # Remove existing auth database to force recreation
        if [ -f "auth/users.db" ]; then
            rm "auth/users.db"
            echo -e "${GREEN}Removed existing auth database${NC}"
        fi
        # Use existing evaluation database if available
        if [ -f "evaluation_results.db" ]; then
            echo -e "${GREEN}Using existing evaluation database${NC}"
        else
            create_empty_db
        fi
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

echo

# Launch method selection
echo "How would you like to run the dashboard?"
echo "1) Docker (recommended)"
echo "2) Local Python (requires dependencies installed)"
echo
read -r -p "Select launch method [1-2]: " launch_method

case $launch_method in
    1)
        echo -e "${GREEN}Launching dashboard with Docker...${NC}"
        echo -e "${YELLOW}Note: Building image from dashboard directory${NC}"

        # Build the Docker image
        echo "Building dashboard image..."
        docker build -t sleeper-dashboard:latest "$DASHBOARD_DIR"

        # Stop any existing container
        docker stop sleeper-dashboard 2>/dev/null || true
        docker rm sleeper-dashboard 2>/dev/null || true

        # Load environment variables from .env if it exists
        ENV_FILE="$SCRIPT_DIR/../../../.env"
        if [ -f "$ENV_FILE" ]; then
            set -a  # Export all variables
            # shellcheck source=/dev/null
            source "$ENV_FILE"
            set +a  # Stop exporting
            echo "Loaded environment from .env (DASHBOARD_ADMIN_PASSWORD is set: $([ -n "$DASHBOARD_ADMIN_PASSWORD" ] && echo "Yes" || echo "No"))"
        else
            echo -e "${YELLOW}Warning: .env file not found at $ENV_FILE${NC}"
        fi

        # Run the dashboard container
        echo "Starting dashboard container..."
        echo "Using DASHBOARD_ADMIN_PASSWORD from .env: ${DASHBOARD_ADMIN_PASSWORD:0:4}..."

        # Don't mount the whole directory to avoid overwriting auth database
        # Only mount what we need
        docker run -d \
            --name sleeper-dashboard \
            -p 8501:8501 \
            -v "$DASHBOARD_DIR/evaluation_results.db:/home/dashboard/app/evaluation_results.db:ro" \
            -v "$DASHBOARD_DIR/components:/home/dashboard/app/components:ro" \
            -v "$DASHBOARD_DIR/utils:/home/dashboard/app/utils:ro" \
            -v "$DASHBOARD_DIR/config:/home/dashboard/app/config:ro" \
            -e DATABASE_PATH=/home/dashboard/app/evaluation_results.db \
            -e DASHBOARD_ADMIN_PASSWORD="${DASHBOARD_ADMIN_PASSWORD}" \
            -e PYTHONUNBUFFERED=1 \
            sleeper-dashboard:latest

        echo
        echo -e "${GREEN}Dashboard started successfully!${NC}"
        echo -e "${CYAN}Access at: http://localhost:8501${NC}"
        echo -e "${CYAN}View logs: docker logs -f sleeper-dashboard${NC}"
        echo -e "${CYAN}Stop: docker stop sleeper-dashboard${NC}"
        ;;
    2)
        echo -e "${GREEN}Launching dashboard locally...${NC}"
        echo
        # Check if dependencies are installed
        if ! python -c "import streamlit" 2>/dev/null; then
            echo -e "${YELLOW}Installing dependencies...${NC}"
            pip install -r requirements.txt
        fi

        # Load environment variables from .env if it exists
        ENV_FILE="$SCRIPT_DIR/../../../.env"
        if [ -f "$ENV_FILE" ]; then
            set -a  # Export all variables
            # shellcheck source=/dev/null
            source "$ENV_FILE"
            set +a  # Stop exporting
            echo "Loaded environment from .env (DASHBOARD_ADMIN_PASSWORD is set: $([ -n "$DASHBOARD_ADMIN_PASSWORD" ] && echo "Yes" || echo "No"))"
        else
            echo -e "${YELLOW}Warning: .env file not found at $ENV_FILE${NC}"
        fi

        # Set environment variables
        DATABASE_PATH="$(pwd)/evaluation_results.db"
        export DATABASE_PATH
        export DASHBOARD_ADMIN_PASSWORD="${DASHBOARD_ADMIN_PASSWORD:-}"

        # Launch Streamlit
        streamlit run app.py --server.port 8501
        ;;
    *)
        echo -e "${RED}Invalid launch method${NC}"
        exit 1
        ;;
esac
