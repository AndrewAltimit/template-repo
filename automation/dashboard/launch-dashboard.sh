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
DASHBOARD_DIR="$(dirname "$0")/../../packages/sleeper_detection/dashboard"
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
    if [ -f "tests/fixtures.py" ]; then
        python tests/fixtures.py
        if [ -f "tests/test_evaluation_results.db" ]; then
            cp tests/test_evaluation_results.db evaluation_results.db
            echo -e "${GREEN}Mock data generated successfully!${NC}"
        else
            echo -e "${RED}Failed to generate mock data${NC}"
            exit 1
        fi
    else
        echo -e "${RED}fixtures.py not found!${NC}"
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
echo
read -r -p "Select option [1-4]: " option

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
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

echo

# Launch method selection
echo "How would you like to run the dashboard?"
echo "1) Docker Compose (recommended)"
echo "2) Docker run"
echo "3) Local Python (requires dependencies installed)"
echo
read -r -p "Select launch method [1-3]: " launch_method

case $launch_method in
    1)
        echo -e "${GREEN}Launching dashboard with Docker Compose...${NC}"
        echo
        # Build the dashboard image
        docker-compose build dashboard
        # Run the dashboard
        docker-compose up dashboard
        ;;
    2)
        echo -e "${GREEN}Launching dashboard with Docker...${NC}"
        echo
        # Build the image
        docker build -t sleeper-dashboard:local .
        # Run the container
        docker run --rm \
            -p 8501:8501 \
            -v "$(pwd)/evaluation_results.db:/home/dashboard/app/evaluation_results.db" \
            -v "$(pwd)/auth:/home/dashboard/app/auth" \
            -e DATABASE_PATH=/home/dashboard/app/evaluation_results.db \
            sleeper-dashboard:local
        ;;
    3)
        echo -e "${GREEN}Launching dashboard locally...${NC}"
        echo
        # Check if dependencies are installed
        if ! python -c "import streamlit" 2>/dev/null; then
            echo -e "${YELLOW}Installing dependencies...${NC}"
            pip install -r requirements.txt
        fi
        # Set environment variable for database
        DATABASE_PATH="$(pwd)/evaluation_results.db"
        export DATABASE_PATH
        # Launch Streamlit
        streamlit run app.py --server.port 8501
        ;;
    *)
        echo -e "${RED}Invalid launch method${NC}"
        exit 1
        ;;
esac
