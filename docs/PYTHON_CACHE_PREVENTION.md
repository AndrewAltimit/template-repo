# Python Cache Prevention Guide

This document explains how we prevent `__pycache__` permission issues in GitHub Actions self-hosted runners.

## Problem

When Python code runs in Docker containers with different user permissions, `__pycache__` files can be created with permissions that prevent the GitHub Actions checkout action from cleaning the workspace, resulting in errors like:

```
Error: EACCES: permission denied, unlink '.../__pycache__/__init__.cpython-310.pyc'
```

## Prevention Strategy

We use a multi-layered approach to **prevent** these files from being created with problematic permissions:

### 1. Environment Variables

All Python containers and executions use these environment variables:

- `PYTHONDONTWRITEBYTECODE=1` - Prevents Python from writing .pyc files
- `PYTHONPYCACHEPREFIX=/tmp/pycache` - Redirects any cache to a temporary location
- `PYTEST_CACHE_DISABLE=1` - Disables pytest's cache mechanism

### 2. Docker Configuration

#### Dockerfiles
All Python Dockerfiles include:
```dockerfile
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPYCACHEPREFIX=/tmp/pycache
ENV PYTEST_CACHE_DISABLE=1
```

#### docker-compose.yml
All Python services include these environment variables:
```yaml
environment:
  - PYTHONDONTWRITEBYTECODE=1
  - PYTHONPYCACHEPREFIX=/tmp/pycache
```

#### .dockerignore
Prevents cache files from being included in Docker builds:
```
__pycache__/
*.py[cod]
*.pyc
.pytest_cache/
.mypy_cache/
```

### 3. Test Configuration

#### pytest.ini
```ini
[pytest]
addopts = -p no:cacheprovider --cache-clear
```

#### CI Scripts
The `run-ci.sh` script explicitly sets environment variables for all Python executions:
```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX=/tmp/pycache
```

### 4. User Permissions

All CI containers run with the host user's UID/GID:
```yaml
user: "${USER_ID:-1000}:${GROUP_ID:-1000}"
```

This ensures any files created have the correct ownership.

## Implementation Checklist

When adding new Python containers or workflows:

1. **Dockerfile**: Add the three environment variables
2. **docker-compose.yml**: Include environment variables for the service
3. **CI Scripts**: Export environment variables before Python execution
4. **Test Commands**: Use `-p no:cacheprovider` flag with pytest

## Verification

To verify the prevention is working:

1. Run your CI pipeline
2. Check that no `__pycache__` directories are created in the workspace
3. Confirm subsequent runs don't encounter permission errors

## Emergency Cleanup

If you encounter existing cache files with permission issues:

```bash
# Manual cleanup
./scripts/cleanup-workspace.sh

# Or use Docker with root permissions
docker run --rm -v "$(pwd):/workspace" --user root alpine:latest \
  sh -c "find /workspace -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true"
```

## Key Points

- **Prevention is better than cleanup** - We stop the files from being created rather than cleaning them up
- **Multiple layers of protection** - Environment variables, pytest config, and Docker settings all work together
- **Consistent user permissions** - All containers run with the same UID/GID as the host
- **No performance impact** - Disabling bytecode generation has negligible impact on CI performance