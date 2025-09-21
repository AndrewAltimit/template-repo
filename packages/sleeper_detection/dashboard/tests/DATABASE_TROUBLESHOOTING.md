# Database Accessibility Troubleshooting Guide

This document outlines the solutions implemented to resolve the "no such table: evaluation_results" issue in the Streamlit dashboard Docker tests.

## Problem Summary

The dashboard container could not access the SQLite database table "evaluation_results" despite successful database generation, due to:

1. **Environment Variable Not Used**: DataLoader wasn't checking `DATABASE_PATH` environment variable
2. **Working Directory Mismatch**: Database mounted at `/app/` but dashboard working dir was `/home/dashboard/app/`
3. **File Permissions**: Database file not readable by dashboard container user
4. **Path Configuration**: DataLoader search paths didn't include the Docker mount location

## Solutions Implemented

### 1. Enhanced DataLoader Environment Variable Support

**File**: `utils/data_loader.py`

- Added `os.environ.get("DATABASE_PATH")` check in `__init__`
- Added `/app/test_evaluation_results.db` to fallback search paths
- Added logging for database path resolution

### 2. Fixed Docker Volume Mounting

**File**: `tests/docker-compose.test.yml`

- Updated volume mount from `/app/` to `/home/dashboard/app/` (aligns with Dockerfile WORKDIR)
- Updated `DATABASE_PATH` environment variable to match mount location
- Added read-only (`:ro`) flags for security

### 3. Improved File Permissions

**File**: `tests/fixtures.py`

- Added `stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH` permissions
- Ensures database is readable by different container users

### 4. Enhanced GitHub Workflow Validation

**File**: `.github/workflows/dashboard-tests.yml`

Added comprehensive verification steps:
- Database existence check after generation
- SQLite query verification before container start
- Database accessibility test from dashboard container
- Proper permission setting (`chmod 644`)

### 5. Database Health Check Script

**File**: `tests/check_database.py`

Standalone script for verifying database accessibility:
- Checks file existence
- Validates table schema
- Tests data accessibility
- Can be used in health checks or debugging

## Usage Examples

### Testing Database Access

```bash
# Generate test database
docker-compose -f docker-compose.test.yml run --rm --no-deps test-runner python /app/tests/fixtures.py

# Verify database with health check
DATABASE_PATH=test_evaluation_results.db python check_database.py

# Test from dashboard container
docker-compose -f docker-compose.test.yml exec dashboard python /home/dashboard/app/tests/check_database.py
```

### Environment Variables

```bash
# For dashboard container
DATABASE_PATH=/home/dashboard/app/test_evaluation_results.db

# For test-runner container
DATABASE_PATH=/app/tests/test_evaluation_results.db
```

## File Structure

```
tests/
├── test_evaluation_results.db          # Generated database
├── check_database.py                   # Health check script
├── fixtures.py                         # Database generation (updated)
├── docker-compose.test.yml             # Container configuration (updated)
└── DATABASE_TROUBLESHOOTING.md         # This guide
```

## Verification Steps

1. **Database Generation**: Verify `test_evaluation_results.db` exists after fixtures.py
2. **Container Mount**: Check volume mounts align with working directories
3. **Environment Variables**: Ensure `DATABASE_PATH` is set correctly
4. **Permissions**: Verify database file is readable (644 permissions)
5. **Health Check**: Use `check_database.py` to validate accessibility

## Common Issues and Solutions

### Issue: "Database file does not exist"
- Check volume mount paths in docker-compose.test.yml
- Verify fixtures.py successfully created the database
- Ensure proper working directory context

### Issue: "Permission denied"
- Run `chmod 644 test_evaluation_results.db`
- Check container user IDs match file ownership
- Verify database creation sets proper permissions

### Issue: "No such table: evaluation_results"
- Use `check_database.py` to verify table existence
- Check if fixtures.py completed successfully
- Verify SQLite database isn't corrupted

### Issue: Environment variable not recognized
- Ensure `DATABASE_PATH` is set in docker-compose environment section
- Check DataLoader import path and environment variable parsing
- Test locally with `DATABASE_PATH=path python script.py`

## Testing the Solutions

```bash
# Full test sequence
cd packages/sleeper_detection/dashboard/tests

# 1. Generate database
docker-compose -f docker-compose.test.yml run --rm --no-deps test-runner python /app/tests/fixtures.py

# 2. Verify generation
python check_database.py

# 3. Start services
docker-compose -f docker-compose.test.yml up -d dashboard

# 4. Test from container
docker-compose -f docker-compose.test.yml exec dashboard python /home/dashboard/app/tests/check_database.py

# 5. Cleanup
docker-compose -f docker-compose.test.yml down
```

These solutions ensure robust database accessibility across all Docker container environments and provide comprehensive debugging tools for future issues.
