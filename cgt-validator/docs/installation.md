# Installation Guide

## Primary Method: Docker (Recommended)

This project follows a **container-first philosophy**. Docker ensures a consistent environment across all systems and eliminates "it works on my machine" problems.

### Prerequisites

- Docker (version 20.10 or later)
- Docker Compose (version 2.0 or later)
- Git

### Quick Start with Docker

```bash
# Clone the repository
git clone <repository-url>
cd cgt-validator

# Build and start the container environment
docker-compose up -d

# Run the validator
docker-compose run --rm cgt-validator validate oregon --file data.xlsx

# Or use the Makefile shortcuts
make docker-build
make docker-validate FILE=data.xlsx STATE=oregon
```

### Docker Development Environment

For development work, use the development container:

```bash
# Start an interactive development shell
make docker-shell

# Or directly with docker-compose
docker-compose run --rm cgt-dev bash

# Inside the container, all tools are pre-installed:
# - Python 3.11 with all dependencies
# - Pre-commit hooks
# - Testing tools
# - Linting and formatting tools
```

### Docker Commands Reference

```bash
# Build containers
docker-compose build

# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f cgt-validator

# Run tests in container
docker-compose run --rm cgt-test

# Run linting in container
docker-compose run --rm cgt-lint

# Clean up Docker resources
docker system prune -a
```

## Alternative: Local Installation (Not Recommended)

⚠️ **Warning**: Local installation is discouraged as it may lead to environment inconsistencies. Use Docker unless you have specific requirements that prevent container usage.

If you absolutely must install locally:

### System Requirements

- Python 3.8 or higher (3.11 recommended for consistency with containers)
- pip (Python package manager)
- Virtual environment tool (venv or virtualenv)

### Local Setup Steps

1. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install the package**:
   ```bash
   pip install -e .
   ```

3. **Install development dependencies** (if contributing):
   ```bash
   pip install -r requirements-dev.txt
   pre-commit install
   ```

4. **Verify installation**:
   ```bash
   cgt-validate --help
   ```

### Why Docker is Preferred

1. **Consistency**: Same environment for all developers and CI/CD
2. **Isolation**: No conflicts with system Python or other projects
3. **Simplicity**: One command to get a fully configured environment
4. **Reproducibility**: Guaranteed to work the same way everywhere
5. **Clean**: No system pollution with dependencies

## Container Architecture

The project provides several specialized containers:

- **cgt-validator**: Main application container for running validations
- **cgt-dev**: Development environment with all tools installed
- **cgt-test**: Automated test runner with watch mode
- **cgt-lint**: Code quality checks and formatting

All containers share the same base image and mount your local code, so changes are reflected immediately without rebuilding.

## Troubleshooting

### Docker Installation Issues

If Docker is not installed:
- **Linux**: Follow [Docker's official installation guide](https://docs.docker.com/engine/install/)
- **Mac**: Install [Docker Desktop for Mac](https://docs.docker.com/desktop/mac/install/)
- **Windows**: Install [Docker Desktop for Windows](https://docs.docker.com/desktop/windows/install/)

### Permission Issues

If you encounter permission errors with Docker:

```bash
# Add your user to the docker group (Linux)
sudo usermod -aG docker $USER
# Log out and back in for changes to take effect
```

### Port Conflicts

If ports are already in use:
1. Check `docker-compose.yml` for port mappings
2. Either stop conflicting services or modify the ports in `docker-compose.override.yml`

## Next Steps

After installation, see:
- [User Guide](user_guide.md) for usage instructions
- [Development Guide](DEVELOPMENT.md) for contributing
- [Troubleshooting Guide](troubleshooting.md) for common issues
