#!/bin/bash
# Export Sleeper Detection Database from Container
# Extracts evaluation_results.db from the sleeper-results volume
# Supports both Docker and Podman

set -e

echo "========================================="
echo "Sleeper Detection Database Export"
echo "From Container"
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
OUTPUT_DIR="./db_exports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="${OUTPUT_DIR}/evaluation_results_${TIMESTAMP}.sql"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --container)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --output-file)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Exports the evaluation results database from a running Docker container."
            echo ""
            echo "Options:"
            echo "  --container NAME     Container name (default: sleeper-dashboard)"
            echo "  --output-dir DIR     Output directory (default: ./db_exports)"
            echo "  --output-file FILE   Output file path (overrides --output-dir)"
            echo "  -h, --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0"
            echo "  $0 --container my-dashboard"
            echo "  $0 --output-dir /backups"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

echo "[1/5] Checking container runtime..."

echo "Using $CONTAINER_CMD"
echo ""

echo "[2/5] Checking container..."

# Check if container is running
if ! $CONTAINER_CMD ps --filter "name=${CONTAINER_NAME}" --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container '${CONTAINER_NAME}' is not running. Starting it now..."
    echo ""

    # Find and run start script
    START_SCRIPT=""
    if [ -f "../../dashboard/start.sh" ]; then
        START_SCRIPT="../../dashboard/start.sh"
    elif [ -f "../../../dashboard/start.sh" ]; then
        START_SCRIPT="../../../dashboard/start.sh"
    else
        # Search up the directory tree to find the dashboard start script
        # This allows the script to work from any location in the repository
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
    fi

    if [ -z "$START_SCRIPT" ]; then
        echo "ERROR: Could not find dashboard start.sh script"
        echo ""
        echo "Please start the dashboard manually:"
        echo "  cd packages/sleeper_detection/dashboard"
        echo "  ./start.sh"
        exit 1
    fi

    echo "Found start script: $START_SCRIPT"
    echo "Starting dashboard container..."
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

echo "[3/5] Checking database in container..."

# Check if database exists in container
if ! $CONTAINER_CMD exec "${CONTAINER_NAME}" test -f "${DB_PATH}" 2>/dev/null; then
    echo "ERROR: Database not found in container at ${DB_PATH}"
    echo ""
    echo "The database may not have been created yet."
    echo "Run an evaluation job first to create the database."
    exit 1
fi

# Get database size
DB_SIZE=$($CONTAINER_CMD exec "${CONTAINER_NAME}" stat -c %s "${DB_PATH}" 2>/dev/null)
DB_SIZE_KB=$((DB_SIZE / 1024))
echo "Database found in container: ${DB_PATH}"
echo "Database size: ${DB_SIZE_KB} KB"
echo ""

echo "[4/5] Exporting database..."

# Create output directory
mkdir -p "$(dirname "$OUTPUT_FILE")"

# Export database to SQL dump using container exec
echo "Dumping database to SQL..."
if ! $CONTAINER_CMD exec "${CONTAINER_NAME}" sqlite3 "${DB_PATH}" .dump > "${OUTPUT_FILE}"; then
    echo "ERROR: Failed to export database"
    exit 1
fi

echo "Export completed."
echo ""

echo "[5/5] Verifying export..."

if [ ! -f "$OUTPUT_FILE" ]; then
    echo "ERROR: Export file not created"
    exit 1
fi

EXPORT_SIZE_BYTES=$(stat -c%s "$OUTPUT_FILE")
EXPORT_SIZE_KB=$((EXPORT_SIZE_BYTES / 1024))

echo ""
echo "========================================="
echo "Export Complete!"
echo "========================================="
echo ""
echo "Export file: $OUTPUT_FILE"
echo "Export size: ${EXPORT_SIZE_KB} KB"
echo ""
echo "To import on another machine:"
echo "  1. Copy the file to the other machine"
echo "  2. Run: ./import_db_to_container.sh --sql-file $OUTPUT_FILE"
echo ""
echo "Or to view locally:"
echo "  sqlite3 $OUTPUT_FILE"
echo ""
