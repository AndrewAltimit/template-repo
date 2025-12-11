#!/bin/bash
# Import Sleeper Detection Database to Container
# Imports SQL dump into the sleeper-results volume
# Supports both Docker and Podman

set -e
set -o pipefail

echo "========================================="
echo "Sleeper Detection Database Import"
echo "To Container"
echo "========================================="
echo ""

# Detect container runtime (podman or docker)
CONTAINER_CMD=""
if command -v podman &> /dev/null; then
    CONTAINER_CMD="podman"
elif command -v docker &> /dev/null; then
    CONTAINER_CMD="docker"
else
    echo "ERROR: Neither podman nor docker found. Please install one of them."
    exit 1
fi

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

# Get file size (cross-platform: Linux uses -c%s, macOS uses -f%z)
if [[ "$OSTYPE" == "darwin"* ]]; then
    SQL_SIZE_BYTES=$(stat -f%z "$SQL_FILE")
else
    SQL_SIZE_BYTES=$(stat -c%s "$SQL_FILE")
fi
SQL_SIZE_KB=$((SQL_SIZE_BYTES / 1024))
echo "SQL file found: $SQL_FILE"
echo "SQL file size: ${SQL_SIZE_KB} KB"
echo ""

echo "[2/4] Checking container..."

echo "Using $CONTAINER_CMD"

# Check if container is running
if ! $CONTAINER_CMD ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container '${CONTAINER_NAME}' is not running. Starting it now..."
    echo ""

    # Find and run start script
    # Search up the directory tree to find the dashboard start script
    # This allows the script to work from any location in the repository
    START_SCRIPT=""
    SEARCH_DIR="$(pwd)"
    while [ "$SEARCH_DIR" != "/" ]; do
        if [ -f "$SEARCH_DIR/packages/sleeper_agents/dashboard/start.sh" ]; then
            START_SCRIPT="$SEARCH_DIR/packages/sleeper_agents/dashboard/start.sh"
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

    bash "$START_SCRIPT" --no-logs > /dev/null 2>&1 &

    # Wait for container to start with polling
    echo "Waiting for container to start..."
    for i in {1..30}; do
        if $CONTAINER_CMD ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
            echo "Container started successfully."
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "ERROR: Container failed to start within 60 seconds."
            echo ""
            echo "Recent container logs:"
            $CONTAINER_CMD logs --tail 30 "${CONTAINER_NAME}" 2>&1 || echo "Could not retrieve logs"
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
    if $CONTAINER_CMD exec "${CONTAINER_NAME}" test -f "${DB_PATH}" 2>/dev/null; then
        BACKUP_PATH="${DB_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
        echo "Creating backup in container: ${BACKUP_PATH}"
        $CONTAINER_CMD exec "${CONTAINER_NAME}" cp "${DB_PATH}" "${BACKUP_PATH}"
    fi
fi

echo "Importing database..."
# Import SQL file into container
if ! $CONTAINER_CMD exec -i "${CONTAINER_NAME}" sqlite3 "${DB_PATH}" < "$SQL_FILE"; then
    echo "ERROR: Failed to import database"
    exit 1
fi

echo "Import completed."
echo ""

echo "[4/4] Verifying import..."

# Verify database exists
if ! $CONTAINER_CMD exec "${CONTAINER_NAME}" test -f "${DB_PATH}"; then
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
