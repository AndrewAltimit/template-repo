#!/bin/bash
# Export Sleeper Detection Database
# Creates a portable SQL dump of evaluation results for transfer to other machines

set -e

echo "========================================="
echo "Sleeper Detection Database Export"
echo "========================================="
echo ""

# Default values
DB_PATH="/results/evaluation_results.db"
OUTPUT_DIR="./db_exports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="${OUTPUT_DIR}/evaluation_results_${TIMESTAMP}.sql"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --db-path)
            DB_PATH="$2"
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
            echo "Options:"
            echo "  --db-path PATH       Path to database file (default: /results/evaluation_results.db)"
            echo "  --output-dir DIR     Output directory (default: ./db_exports)"
            echo "  --output-file FILE   Output file path (overrides --output-dir)"
            echo "  -h, --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0"
            echo "  $0 --db-path /custom/path/results.db"
            echo "  $0 --output-dir /backup/location"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

echo "[1/4] Checking database..."

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "ERROR: Database not found at: $DB_PATH"
    echo ""
    echo "Common locations:"
    echo "  - /results/evaluation_results.db (container volume)"
    echo "  - packages/sleeper_detection/dashboard/evaluation_results.db"
    echo "  - Custom path specified in environment"
    exit 1
fi

echo "Database found: $DB_PATH"
DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
echo "Database size: $DB_SIZE"
echo ""

echo "[2/4] Analyzing database contents..."

# Count records in each table
TABLES=$(sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")

if [ -z "$TABLES" ]; then
    echo "WARNING: Database has no tables"
else
    echo "Tables found:"
    for table in $TABLES; do
        COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM $table;")
        echo "  - $table: $COUNT records"
    done
fi
echo ""

echo "[3/4] Creating export directory..."
mkdir -p "$(dirname "$OUTPUT_FILE")"
echo "Export will be saved to: $OUTPUT_FILE"
echo ""

echo "[4/4] Exporting database..."

# Export to SQL dump
if sqlite3 "$DB_PATH" .dump > "$OUTPUT_FILE"; then
    EXPORT_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo ""
    echo "========================================="
    echo "Export Complete!"
    echo "========================================="
    echo ""
    echo "Export file: $OUTPUT_FILE"
    echo "Export size: $EXPORT_SIZE"
    echo ""
    echo "To import on another machine:"
    echo "  ./scripts/data/import_db.sh --sql-file $OUTPUT_FILE"
    echo ""
    echo "Or manually:"
    echo "  sqlite3 /results/evaluation_results.db < $OUTPUT_FILE"
    echo ""
else
    echo ""
    echo "ERROR: Export failed"
    exit 1
fi
