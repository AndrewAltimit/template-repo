#!/bin/bash
# Import Sleeper Detection Database
# Imports SQL dump from another machine into local evaluation results database

set -e

echo "========================================="
echo "Sleeper Detection Database Import"
echo "========================================="
echo ""

# Default values
# Auto-detect database location by searching up directory tree
DB_PATH=""
SEARCH_DIR="$(pwd)"

# Try to find packages/sleeper_detection/dashboard/evaluation_results.db
while [ "$SEARCH_DIR" != "/" ]; do
    if [ -d "$SEARCH_DIR/packages/sleeper_detection/dashboard" ]; then
        DB_PATH="$SEARCH_DIR/packages/sleeper_detection/dashboard/evaluation_results.db"
        break
    fi
    if [ -d "$SEARCH_DIR/dashboard" ]; then
        DB_PATH="$SEARCH_DIR/dashboard/evaluation_results.db"
        break
    fi
    SEARCH_DIR="$(dirname "$SEARCH_DIR")"
done

# Fallback to container path
if [ -z "$DB_PATH" ]; then
    DB_PATH="/results/evaluation_results.db"
fi

SQL_FILE=""
BACKUP_EXISTING=true
MERGE_MODE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --db-path)
            DB_PATH="$2"
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
        --merge)
            MERGE_MODE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 --sql-file FILE [OPTIONS]"
            echo ""
            echo "Required:"
            echo "  --sql-file FILE      SQL dump file to import"
            echo ""
            echo "Options:"
            echo "  --db-path PATH       Target database path (default: auto-detect)"
            echo "  --no-backup          Skip backing up existing database"
            echo "  --merge              Merge with existing data instead of replacing"
            echo "  -h, --help          Show this help message"
            echo ""
            echo "Database auto-detection:"
            echo "  - Searches up directory tree for packages/sleeper_detection/dashboard/evaluation_results.db"
            echo "  - Also checks for dashboard/evaluation_results.db (if in sleeper_detection dir)"
            echo "  - Falls back to /results/evaluation_results.db (container volume)"
            echo ""
            echo "Examples:"
            echo "  $0 --sql-file db_exports/evaluation_results_20250101_120000.sql"
            echo "  $0 --sql-file export.sql --db-path /custom/path/results.db"
            echo "  $0 --sql-file export.sql --merge --no-backup"
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

echo "[1/5] Checking SQL file..."

# Check if SQL file exists
if [ ! -f "$SQL_FILE" ]; then
    echo "ERROR: SQL file not found: $SQL_FILE"
    exit 1
fi

echo "SQL file found: $SQL_FILE"
SQL_SIZE=$(du -h "$SQL_FILE" | cut -f1)
echo "SQL file size: $SQL_SIZE"

# Quick validation of SQL file
if ! grep -q "CREATE TABLE" "$SQL_FILE"; then
    echo "WARNING: SQL file may not contain table definitions"
    read -r -p "Continue anyway? (y/N): " response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Import cancelled"
        exit 1
    fi
fi
echo ""

echo "[2/5] Checking target database..."

# Check if target database exists
DB_EXISTS=false
if [ -f "$DB_PATH" ]; then
    DB_EXISTS=true
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
    echo "Existing database found: $DB_PATH"
    echo "Existing database size: $DB_SIZE"

    # Count existing records
    echo "Existing data:"
    TABLES=$(sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;" 2>/dev/null || echo "")
    if [ -n "$TABLES" ]; then
        for table in $TABLES; do
            COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "0")
            echo "  - $table: $COUNT records"
        done
    fi
else
    echo "No existing database found (will create new)"
fi
echo ""

echo "[3/5] Backup and preparation..."

if [ "$DB_EXISTS" = true ] && [ "$BACKUP_EXISTING" = true ]; then
    BACKUP_FILE="${DB_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "Creating backup: $BACKUP_FILE"
    cp "$DB_PATH" "$BACKUP_FILE"
    echo "Backup created successfully"

    if [ "$MERGE_MODE" = false ]; then
        echo "Removing existing database (replace mode)"
        rm "$DB_PATH"
    fi
elif [ "$DB_EXISTS" = true ] && [ "$MERGE_MODE" = false ]; then
    echo "WARNING: Existing database will be replaced without backup"
    read -r -p "Continue? (y/N): " response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        echo "Import cancelled"
        exit 1
    fi
    rm "$DB_PATH"
fi

# Create parent directory if needed
mkdir -p "$(dirname "$DB_PATH")"
echo ""

echo "[4/5] Importing database..."

IMPORT_SUCCESS=false
if [ "$MERGE_MODE" = true ]; then
    echo "Merge mode: Importing into existing database"
    # In merge mode, we import into existing database
    # Duplicate primary keys will cause errors, so we need to handle that
    echo "WARNING: Duplicate primary keys may cause import errors"
    if sqlite3 "$DB_PATH" < "$SQL_FILE" 2>&1 | grep -v "UNIQUE constraint failed" || true; then
        IMPORT_SUCCESS=true
    fi
else
    echo "Replace mode: Creating fresh database"
    if sqlite3 "$DB_PATH" < "$SQL_FILE"; then
        IMPORT_SUCCESS=true
    fi
fi

if [ "$IMPORT_SUCCESS" = true ] || [ "$MERGE_MODE" = true ]; then
    echo "Import completed"
else
    echo "ERROR: Import failed"

    # Restore backup if exists
    if [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ]; then
        echo "Restoring backup..."
        mv "$BACKUP_FILE" "$DB_PATH"
        echo "Backup restored"
    fi
    exit 1
fi
echo ""

echo "[5/5] Verifying import..."

# Verify import
NEW_SIZE=$(du -h "$DB_PATH" | cut -f1)
echo "New database size: $NEW_SIZE"
echo ""
echo "Imported data:"
TABLES=$(sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
if [ -n "$TABLES" ]; then
    for table in $TABLES; do
        COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM $table;")
        echo "  - $table: $COUNT records"
    done
else
    echo "WARNING: No tables found in database"
fi
echo ""

echo "========================================="
echo "Import Complete!"
echo "========================================="
echo ""
echo "Database location: $DB_PATH"
if [ "$BACKUP_EXISTING" = true ] && [ -n "$BACKUP_FILE" ]; then
    echo "Backup location: $BACKUP_FILE"
fi
echo ""
echo "The database is now ready to use with the dashboard"
echo ""
