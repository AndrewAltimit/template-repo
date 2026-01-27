#!/bin/bash

# Run dashboard tests with various options
# Usage: ./run_tests.sh [option]
# Options:
#   unit      - Run unit tests only
#   e2e       - Run E2E Selenium tests only
#   visual    - Run visual regression tests
#   all       - Run all tests (default)
#   docker    - Run tests in Docker containers
#   ci        - Run in CI mode (headless, with coverage)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE=${1:-all}
DASHBOARD_URL=${DASHBOARD_URL:-http://localhost:8501}

echo -e "${GREEN}Sleeper Detection Dashboard Test Runner${NC}"
echo -e "${GREEN}========================================${NC}"

# Function to check if dashboard is running
check_dashboard() {
    echo -e "${YELLOW}Checking if dashboard is accessible at $DASHBOARD_URL...${NC}"
    if curl -s -o /dev/null -w "%{http_code}" "$DASHBOARD_URL" | grep -q "200\|302"; then
        echo -e "${GREEN}✓ Dashboard is running${NC}"
        return 0
    else
        echo -e "${RED}✗ Dashboard is not accessible${NC}"
        return 1
    fi
}

# Function to start dashboard locally
start_dashboard() {
    echo -e "${YELLOW}Starting dashboard locally...${NC}"
    cd ..
    streamlit run app.py &
    DASHBOARD_PID=$!
    sleep 5
    cd tests
}

# Function to stop dashboard
stop_dashboard() {
    if [ -n "$DASHBOARD_PID" ]; then
        echo -e "${YELLOW}Stopping dashboard...${NC}"
        kill "$DASHBOARD_PID" 2>/dev/null || true
    fi
}

# Function to generate test data
generate_test_data() {
    echo -e "${YELLOW}Generating test data fixtures...${NC}"
    python fixtures.py
}

# Function to run unit tests
run_unit_tests() {
    echo -e "${YELLOW}Running unit tests...${NC}"
    python -m pytest test_streamlit_components.py -v --cov=../ --cov-report=html --cov-report=term
}

# Function to run E2E tests
run_e2e_tests() {
    echo -e "${YELLOW}Running E2E Selenium tests...${NC}"

    # Check if dashboard is running
    if ! check_dashboard; then
        start_dashboard
        trap stop_dashboard EXIT
    fi

    python -m pytest test_selenium_e2e.py -v --html=report.html --self-contained-html
}

# Function to run visual regression tests
run_visual_tests() {
    echo -e "${YELLOW}Running visual regression tests with AI analysis...${NC}"

    # Run E2E tests first to generate screenshots
    run_e2e_tests

    # Run AI visual analyzer
    python ai_visual_analyzer.py
}

# Function to detect architecture and set Selenium image
detect_selenium_image() {
    local arch
    arch=$(uname -m)
    if [ "$arch" = "arm64" ] || [ "$arch" = "aarch64" ]; then
        # ARM64 architecture - use seleniarm
        export SELENIUM_IMAGE="seleniarm/standalone-chromium:latest"
        echo -e "${YELLOW}Detected ARM64 architecture, using seleniarm/standalone-chromium${NC}"
    else
        # x86_64 architecture - use official selenium
        export SELENIUM_IMAGE="selenium/standalone-chrome:latest"
        echo -e "${YELLOW}Detected x86_64 architecture, using selenium/standalone-chrome${NC}"
    fi
}

# Function to run tests in Docker
run_docker_tests() {
    echo -e "${YELLOW}Running tests in Docker containers...${NC}"

    # Auto-detect architecture and set Selenium image
    detect_selenium_image

    # Build and run test containers
    docker compose -f docker-compose.test.yml build
    docker compose -f docker-compose.test.yml up --abort-on-container-exit

    # Copy test results
    docker cp test-runner:/app/screenshots ./
    docker cp test-runner:/app/report.html ./

    # Clean up
    docker compose -f docker-compose.test.yml down
}

# Function to run CI tests
run_ci_tests() {
    echo -e "${YELLOW}Running tests in CI mode...${NC}"

    # Set headless mode for Chrome
    export HEADLESS=true

    # Generate test data
    generate_test_data

    # Run all tests with coverage
    python -m pytest . -v \
        --cov=../ \
        --cov-report=xml \
        --cov-report=html \
        --cov-report=term \
        --html=report.html \
        --self-contained-html \
        --timeout=300
}

# Function to clean up test artifacts
cleanup() {
    echo -e "${YELLOW}Cleaning up test artifacts...${NC}"
    rm -rf screenshots/*.png
    rm -rf ai_feedback/*.json
    rm -rf ai_analysis_results/*.json
    rm -rf __pycache__
    rm -rf .pytest_cache
    rm -rf htmlcov
    rm -f report.html
    rm -f .coverage
    rm -f coverage.xml
}

# Main execution
case "$TEST_TYPE" in
    unit)
        generate_test_data
        run_unit_tests
        ;;
    e2e)
        generate_test_data
        run_e2e_tests
        ;;
    visual)
        generate_test_data
        run_visual_tests
        ;;
    docker)
        run_docker_tests
        ;;
    ci)
        run_ci_tests
        ;;
    all)
        generate_test_data
        run_unit_tests
        run_e2e_tests
        run_visual_tests
        ;;
    clean)
        cleanup
        ;;
    *)
        echo -e "${RED}Invalid option: $TEST_TYPE${NC}"
        echo "Usage: $0 [unit|e2e|visual|all|docker|ci|clean]"
        exit 1
        ;;
esac

echo -e "${GREEN}Testing completed!${NC}"

# Show test results summary
if [ -f "report.html" ]; then
    echo -e "${GREEN}Test report generated: report.html${NC}"
fi

if [ -f "coverage.xml" ]; then
    COVERAGE=$(python -c "import xml.etree.ElementTree as ET; tree = ET.parse('coverage.xml'); root = tree.getroot(); print(root.attrib.get('line-rate', 0))")
    COVERAGE_PCT=$(echo "scale=2; $COVERAGE * 100" | bc)
    echo -e "${GREEN}Code coverage: ${COVERAGE_PCT}%${NC}"
fi

if [ -d "screenshots" ]; then
    SCREENSHOT_COUNT=$(find screenshots -name "*.png" -type f 2>/dev/null | wc -l)
    if [ "$SCREENSHOT_COUNT" -gt 0 ]; then
        echo -e "${GREEN}Screenshots captured: $SCREENSHOT_COUNT${NC}"
    fi
fi
