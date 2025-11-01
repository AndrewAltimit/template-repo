#!/bin/bash
# Import Sleeper Detection Database to Docker Container
# Imports SQL dump into the sleeper-results Docker volume

set -e

echo "========================================="
echo "Sleeper Detection Database Import"
echo "To Docker Container"
echo "========================================="
echo ""

# Default values
CONTAINER_NAME="sleeper-dashboard"
DB_PATH="/results/evaluation_results.db"
SQL_FILE=""
BACKUP_EXISTING=true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --container)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        --sql-file)
            SQL_FILE="$2"
            shift 2
            ;;
        --no-backup)
            BACKUP_EXISTING=false
            shift
            ;;
        -h|--help)
            echo "Usage: $0 --sql-file FILE [OPTIONS]"
            echo ""
            echo "Imports an SQL dump file into the evaluation results database in a Docker container."
            echo ""
            echo "Required:"
            echo "  --sql-file FILE      SQL dump file to import"
            echo ""
            echo "Options:"
            echo "  --container NAME     Container name (default: sleeper-dashboard)"
            echo "  --no-backup          Skip backing up existing database"
            echo "  -h, --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --sql-file db_exports/evaluation_results_20250101_120000.sql"
            echo "  $0 --sql-file export.sql --container my-dashboard"
            echo "  $0 --sql-file export.sql --no-backup"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$SQL_FILE" ]; then
    echo "ERROR: --sql-file is required"
    echo "Use -h or --help for usage information"
    exit 1
fi

echo "[1/4] Checking SQL file..."

if [ ! -f "$SQL_FILE" ]; then
    echo "ERROR: SQL file not found: $SQL_FILE"
    exit 1
fi

SQL_SIZE=$(du -h "$SQL_FILE" | cut -f1)
echo "SQL file found: $SQL_FILE"
echo "SQL file size: $SQL_SIZE"
echo ""

echo "[2/4] Checking container..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker not found. Please install Docker."
    exit 1
fi

# Check if container is running
if ! docker ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container '${CONTAINER_NAME}' is not running. Starting it now..."
    echo ""

    # Find and run start script
    START_SCRIPT=""
    SEARCH_DIR="$(pwd)"
    while [ "$SEARCH_DIR" != "/" ]; do
        if [ -f "$SEARCH_DIR/packages/sleeper_detection/dashboard/start.sh" ]; then
            START_SCRIPT="$SEARCH_DIR/packages/sleeper_detection/dashboard/start.sh"
            break
        fi
        if [ -f "$SEARCH_DIR/dashboard/start.sh" ]; then
            START_SCRIPT="$SEARCH_DIR/dashboard/start.sh"
            break
        fi
        SEARCH_DIR="$(dirname "$SEARCH_DIR")"
    done

    if [ -z "$START_SCRIPT" ]; then
        echo "ERROR: Could not find dashboard start.sh script"
        exit 1
    fi

    bash "$START_SCRIPT" > /dev/null 2>&1 &

    # Wait for container to start with polling
    echo "Waiting for container to start..."
    for i in {1..30}; do
        if docker ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
            echo "Container started successfully."
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "ERROR: Container failed to start within 60 seconds."
            echo ""
            echo "Recent container logs:"
            docker logs --tail 30 "${CONTAINER_NAME}" 2>&1 || echo "Could not retrieve logs"
            exit 1
        fi
        sleep 2
    done
fi

echo "Container '${CONTAINER_NAME}' is running."
echo ""

echo "[3/4] Backup and import..."

if [ "$BACKUP_EXISTING" = true ]; then
    # Check if database exists and backup
    if docker exec "${CONTAINER_NAME}" test -f "${DB_PATH}" 2>/dev/null; then
        BACKUP_PATH="${DB_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
        echo "Creating backup in container: ${BACKUP_PATH}"
        docker exec "${CONTAINER_NAME}" cp "${DB_PATH}" "${BACKUP_PATH}"
    fi
fi

echo "Importing database..."
# Import SQL file into container
if ! docker exec -i "${CONTAINER_NAME}" sqlite3 "${DB_PATH}" < "$SQL_FILE"; then
    echo "ERROR: Failed to import database"
    exit 1
fi

echo "Import completed."
echo ""

echo "[4/4] Verifying import..."

# Verify database exists
if ! docker exec "${CONTAINER_NAME}" test -f "${DB_PATH}"; then
    echo "ERROR: Database not found after import"
    exit 1
fi

echo ""
echo "========================================="
echo "Import Complete!"
echo "========================================="
echo ""
echo "Database location (in container): ${DB_PATH}"
echo "Container name: ${CONTAINER_NAME}"
echo ""
echo "The dashboard can now use the imported data."
echo "Access at: http://localhost:8501"
echo ""
