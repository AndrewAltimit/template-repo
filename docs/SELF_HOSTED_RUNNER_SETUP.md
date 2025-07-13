# Self-Hosted Runner Setup Guide

This guide documents the setup process for self-hosted GitHub Actions runners used in this container-first project.

## Philosophy

This project uses **self-hosted runners exclusively** to:

- Maintain zero infrastructure costs
- Have full control over the build environment
- Enable caching of Docker images for faster builds
- Support the container-first approach without cloud limitations

## System Requirements

### Operating System

- **Tested on**: Zorin OS 17 (Ubuntu-based)
- **Supported**: Ubuntu 20.04+, Debian 11+, or compatible Linux distributions

### Required Software

1. **Docker** (v20.10+)

   ```bash
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh

   # Add user to docker group
   sudo usermod -aG docker $USER
   # Log out and back in for group changes to take effect
   ```

2. **Docker Compose** (v2.0+)

   ```bash
   # Docker Compose v2 is included with Docker Desktop
   # For standalone installation:
   sudo apt-get update
   sudo apt-get install docker-compose-plugin
   ```

3. **Git** (v2.25+)

   ```bash
   sudo apt-get update
   sudo apt-get install git
   ```

4. **Node.js** (v22.16.0) via nvm

   ```bash
   # Install nvm
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
   source ~/.bashrc

   # Install Node.js
   nvm install 22.16.0
   nvm use 22.16.0
   ```

5. **Gemini CLI** (pre-authenticated)

   ```bash
   # Install Gemini CLI
   npm install -g @google/gemini-cli

   # Authenticate (happens automatically on first use)
   gemini
   ```

   Note: Gemini CLI cannot be containerized as it may need to invoke Docker commands.

6. **Python** (v3.11+)

   ```bash
   # Only needed for running helper scripts
   # All Python CI/CD operations run in containers with Python 3.11
   python3 --version
   ```

## GitHub Actions Runner Installation

1. **Download and Configure Runner**

   ```bash
   # Create a directory for the runner
   mkdir ~/actions-runner && cd ~/actions-runner

   # Download the latest runner package (v2.326.0 as of July 2025)
   # Check https://github.com/actions/runner/releases for the latest version
   curl -o actions-runner-linux-x64-2.326.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.326.0/actions-runner-linux-x64-2.326.0.tar.gz

   # Extract the installer
   tar xzf ./actions-runner-linux-x64-2.326.0.tar.gz
   ```

2. **Configure the Runner**

   ```bash
   # Run the configuration script
   # Note: Get your token from GitHub: Settings > Actions > Runners > New self-hosted runner
   ./config.sh --url https://github.com/YOUR_ORG/YOUR_REPO --token YOUR_TOKEN
   ```

3. **Install as a Service**

   ```bash
   # Install the runner as a service
   sudo ./svc.sh install
   sudo ./svc.sh start

   # Check service status
   sudo ./svc.sh status
   ```

## Environment Configuration

### User Permissions

The CI/CD pipeline runs Docker containers with the current user's UID/GID to avoid permission issues:

```bash
# These are automatically set by the scripts
export USER_ID=$(id -u)
export GROUP_ID=$(id -g)
```

Note: We use `USER_ID` and `GROUP_ID` instead of `UID` and `GID` because `UID` is a readonly variable in some shells.

### Docker Configuration

Ensure Docker can be run without sudo:

```bash
# Test Docker access
docker run hello-world
```

### Disk Space Requirements

- **Minimum**: 20GB free space
- **Recommended**: 50GB+ free space
- Docker images and build cache can consume significant space

### Network Requirements

- Access to Docker Hub for pulling base images
- Access to PyPI for Python packages
- Access to GitHub for cloning repositories

## Maintenance

### Regular Cleanup

To prevent disk space issues, regularly clean Docker resources:

```bash
# Remove unused containers, networks, images (keep last 7 days)
docker system prune -a --filter "until=168h"

# Remove unused volumes
docker volume prune

# Check disk usage
docker system df

# Clean runner work directory (if safe)
rm -rf ~/actions-runner/_work/*/*/_temp
```

### Runner Updates

Keep the GitHub Actions runner updated:

```bash
cd ~/actions-runner
sudo ./svc.sh stop

# Remove the runner (get removal token from GitHub: Settings > Actions > Runners > ... > Remove)
./config.sh remove --token YOUR_REMOVAL_TOKEN

# Download new version (check latest at github.com/actions/runner/releases)
curl -o actions-runner-linux-x64-X.X.X.tar.gz -L https://github.com/actions/runner/releases/download/vX.X.X/actions-runner-linux-x64-X.X.X.tar.gz
tar xzf ./actions-runner-linux-x64-X.X.X.tar.gz

# Reconfigure and start (get new token from GitHub: Settings > Actions > Runners > New self-hosted runner)
./config.sh --url https://github.com/YOUR_ORG/YOUR_REPO --token YOUR_TOKEN
sudo ./svc.sh install
sudo ./svc.sh start
```

## Troubleshooting

### Permission Issues

If you encounter permission errors:

1. Ensure your user is in the `docker` group
2. Verify the UID/GID environment variables are set correctly
3. Check that the workspace directory has proper permissions
4. Use the fix script: `./scripts/fix-runner-permissions.sh`

**Python Cache Prevention:**
The CI/CD system prevents Python cache issues by:

- Setting `PYTHONDONTWRITEBYTECODE=1` in all containers
- Setting `PYTHONPYCACHEPREFIX=/tmp/pycache` to redirect cache
- Disabling pytest cache via `pytest.ini` configuration (`-p no:cacheprovider`)
- Running containers with proper user permissions
- Using Python 3.11 slim base image for consistency

### Docker Build Failures

1. Check available disk space: `df -h`
2. Clean Docker cache: `docker builder prune`
3. Verify network connectivity to Docker Hub

### Runner Connection Issues

1. Check runner service logs: `sudo journalctl -u actions.runner.YOUR_REPO.YOUR_RUNNER_NAME -f`
2. Verify GitHub token hasn't expired
3. Ensure firewall allows outbound HTTPS connections

### Container-Specific Issues

1. **"Cannot connect to Docker daemon"**:
   ```bash
   # Ensure user is in docker group
   sudo usermod -aG docker $USER
   # Log out and back in
   ```

2. **Permission denied on files created by containers**:
   ```bash
   # Use the fix script
   ./scripts/fix-runner-permissions.sh
   ```

3. **Out of space errors**:
   ```bash
   # Check Docker space usage
   docker system df
   # Clean up old images
   docker system prune -a --filter "until=168h"
   ```

## Security Considerations

1. **Never run runners with root privileges**
2. **Use dedicated runner machines** when possible
3. **Regularly update all software** components
4. **Monitor runner logs** for suspicious activity
5. **Restrict repository access** to trusted contributors only

## Additional Resources

- [GitHub Actions Self-Hosted Runners Documentation](https://docs.github.com/en/actions/hosting-your-own-runners)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Linux Security Hardening Guide](https://www.debian.org/doc/manuals/securing-debian-manual/)
