# Containerized CI/CD Documentation

This document explains the container-first philosophy that drives this project's architecture.

## Container-First Philosophy

This project embraces a **container-first approach** as a core design principle:

- **Everything that can be containerized, is containerized**
- **Zero local tool installation required** (except Docker itself)
- **Maximum portability** - runs identically on any Linux system
- **Self-hosted infrastructure** - no cloud dependencies or costs

## Why Container-First?

1. **Portability**: Works on any Linux system with Docker - no other setup needed
2. **Consistency**: Eliminates "works on my machine" problems forever
3. **Simplicity**: No complex dependency management or version conflicts
4. **Isolation**: Each tool runs in its own environment
5. **Cost-effective**: Designed for self-hosted runners with zero cloud costs

## Architecture

### Python CI Container

The Python CI container (`docker/python-ci.Dockerfile`) includes all necessary tools:

- **Base Image**: Python 3.11-slim for optimal performance
- **Formatters**: Black, isort
- **Linters**: flake8, pylint, mypy
- **Testing**: pytest, pytest-cov, pytest-asyncio, pytest-mock
- **Security**: bandit, safety
- **Utilities**: yamllint, pre-commit
- **Coverage**: XML and terminal coverage reports

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
./automation/ci-cd/run-ci.sh format

# Linting
./automation/ci-cd/run-ci.sh lint-basic
./automation/ci-cd/run-ci.sh lint-full

# Testing
./automation/ci-cd/run-ci.sh test

# Security scanning
./automation/ci-cd/run-ci.sh security

# Auto-formatting
./automation/ci-cd/run-ci.sh autoformat

# Full CI pipeline (all checks)
./automation/ci-cd/run-ci.sh full

# YAML/JSON validation
./automation/ci-cd/run-ci.sh yaml-lint
./automation/ci-cd/run-ci.sh json-lint
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

2. **Configuration Files**:
   - `pytest.ini` includes `-p no:cacheprovider` to disable pytest cache

3. **Container User Permissions**:
   - Containers run as current user (USER_ID:GROUP_ID)
   - No files are created with root permissions

## Workflow Integration

GitHub Actions workflows use the containerized approach:

```yaml
- name: Run Python Linting
  run: |
    ./automation/ci-cd/run-ci.sh lint-basic

- name: Run Tests with Coverage
  run: |
    ./automation/ci-cd/run-ci.sh test
```

This ensures:

- Consistent behavior between local and CI environments
- No need to install Python dependencies on runners
- Faster execution with cached Docker images
- Python 3.11 environment matches production

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

## What's Containerized vs What's Not

### Containerized ✅

- **All Python tools**: Black, isort, flake8, pylint, mypy, pytest
- **MCP server**: Runs in its own container with all dependencies
- **CI/CD operations**: All pipeline steps use containers
- **Development tools**: Any tool that doesn't need Docker access

### Not Containerized ❌

- **Gemini CLI**: Needs to potentially invoke Docker (would require Docker-in-Docker)
- **Docker Compose**: Obviously needs to run on the host
- **GitHub Actions runner**: Needs system-level access
- **Git operations**: Need access to host git configuration

## Benefits

1. **Zero Setup Time**: Clone and run - no installation guides needed
2. **Perfect Reproducibility**: Same environment for solo developer across all machines
3. **No Version Conflicts**: Each container has exactly what it needs
4. **Easy Updates**: Just rebuild the container
5. **Self-Hosted Friendly**: Optimized for personal infrastructure

## Best Practices

1. Always use helper scripts for common operations
2. Keep containers lightweight - only install necessary tools
3. Use specific versions in Dockerfile for reproducibility (e.g., Python 3.11)
4. Leverage Docker layer caching on self-hosted runners
5. Design for single-maintainer efficiency
6. Run containers with user permissions to avoid file ownership issues
7. Use multi-stage builds when appropriate for smaller final images

## Philosophy in Practice

This container-first approach means:

- **No README sections about installing dependencies**
- **No version compatibility matrices**
- **No "please install X, Y, Z first" instructions**
- **Just Docker, and everything works**

Perfect for individual developers who want professional infrastructure without the complexity.
