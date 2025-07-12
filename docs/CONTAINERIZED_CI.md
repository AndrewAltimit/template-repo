# Containerized CI/CD Documentation

This document explains the containerized CI/CD approach used in this project, which ensures consistent environments across all development and CI operations.

## Overview

All Python CI/CD operations run in Docker containers to:
- Ensure consistent environments across developers and CI runners
- Avoid dependency conflicts
- Prevent permission issues with file creation
- Enable easy updates and maintenance

## Architecture

### Python CI Container

The Python CI container (`docker/python-ci.Dockerfile`) includes all necessary tools:
- **Formatters**: Black, isort
- **Linters**: flake8, pylint, mypy
- **Testing**: pytest, pytest-cov, pytest-asyncio
- **Security**: bandit, safety
- **Utilities**: yamllint, pre-commit

### Docker Compose Services

```yaml
python-ci:
  build:
    context: .
    dockerfile: docker/python-ci.Dockerfile
  container_name: python-ci
  user: "${USER_ID:-1000}:${GROUP_ID:-1000}"
  environment:
    - PYTHONDONTWRITEBYTECODE=1
    - PYTHONPYCACHEPREFIX=/tmp/pycache
```

Key features:
- Runs as current user to avoid permission issues
- Python cache prevention enabled
- Mounts current directory as working directory

## Usage

### Using Helper Scripts (Recommended)

The `run-ci.sh` script provides a simple interface:

```bash
# Format checking
./scripts/run-ci.sh format

# Linting
./scripts/run-ci.sh lint-basic
./scripts/run-ci.sh lint-full

# Testing
./scripts/run-ci.sh test

# Security scanning
./scripts/run-ci.sh security

# Auto-formatting
./scripts/run-ci.sh autoformat
```

### Direct Docker Compose Commands

For more control, use Docker Compose directly:

```bash
# Run Black formatter
docker-compose run --rm python-ci black .

# Run specific pytest tests
docker-compose run --rm python-ci pytest tests/test_specific.py -v

# Run with custom environment
docker-compose run --rm -e CUSTOM_VAR=value python-ci command
```

## Python Cache Prevention

To prevent permission issues with Python cache files:

1. **Environment Variables**:
   - `PYTHONDONTWRITEBYTECODE=1` - Prevents .pyc file creation
   - `PYTHONPYCACHEPREFIX=/tmp/pycache` - Redirects cache to temp directory
   - `PYTEST_CACHE_DISABLE=1` - Disables pytest cache

2. **Configuration Files**:
   - `pytest.ini` includes `-p no:cacheprovider`

3. **Container User Permissions**:
   - Containers run as current user (USER_ID:GROUP_ID)
   - No files are created with root permissions

## Workflow Integration

GitHub Actions workflows use the containerized approach:

```yaml
- name: Run Python Linting
  run: |
    ./scripts/run-ci.sh lint-basic
```

This ensures:
- Consistent behavior between local and CI environments
- No need to install Python dependencies on runners
- Faster execution with cached Docker images

## Adding New Tools

To add a new Python tool:

1. Update `docker/python-ci.Dockerfile`:
   ```dockerfile
   RUN pip install --no-cache-dir new-tool
   ```

2. Add to `run-ci.sh` if needed:
   ```bash
   new-stage)
     echo "=== Running new tool ==="
     docker-compose run --rm python-ci new-tool .
     ;;
   ```

3. Rebuild the container:
   ```bash
   docker-compose build python-ci
   ```

## Troubleshooting

### Container Build Issues
```bash
# Force rebuild without cache
docker-compose build --no-cache python-ci

# Check build logs
docker-compose build python-ci 2>&1 | tee build.log
```

### Permission Issues
```bash
# Verify user IDs
echo "USER_ID=$(id -u) GROUP_ID=$(id -g)"

# Run with explicit user
USER_ID=$(id -u) GROUP_ID=$(id -g) docker-compose run --rm python-ci command
```

### Performance Optimization
```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker-compose build python-ci

# Prune old images
docker image prune -f
```

## Benefits

1. **Consistency**: Same environment everywhere
2. **Isolation**: No system pollution
3. **Maintainability**: Easy updates via Dockerfile
4. **Security**: Controlled dependencies
5. **Speed**: Cached layers and images

## Best Practices

1. Always use helper scripts for common operations
2. Keep containers lightweight - only install necessary tools
3. Use specific versions in Dockerfile for reproducibility
4. Regular updates of base images and dependencies
5. Monitor container sizes and clean up regularly