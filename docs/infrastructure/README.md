# Infrastructure Documentation

Complete documentation for DevOps, CI/CD, and self-hosted infrastructure.

## 📚 Documentation Files

### [Self-Hosted Runner Setup](./self-hosted-runner.md)
Configuration and maintenance of GitHub Actions self-hosted runners.
- Runner installation and registration
- Systemd service configuration
- Security best practices
- Troubleshooting guide

### [GitHub Environments Setup](./github-environments.md)
Managing GitHub environments, secrets, and variables.
- Environment creation and configuration
- Secret management best practices
- Variable scoping and usage
- Protection rules

### [Containerization](./containerization.md)
Container-first philosophy and Docker implementation.
- Docker and Docker Compose setup
- Container architecture
- CI/CD containerization
- Development workflows

### [Git Hooks](./git-hooks.md)
Git hooks configuration and management.
- Pre-commit hooks
- Post-commit automation
- Security hooks
- Custom hook development

## 🚀 Quick Setup

1. **Set up runners first** - [Self-Hosted Runner Setup](./self-hosted-runner.md)
2. **Configure GitHub** - [GitHub Environments](./github-environments.md)
3. **Install Docker** - [Containerization Guide](./containerization.md)
4. **Enable hooks** - [Git Hooks Configuration](./git-hooks.md)

## 🔧 Common Tasks

### Start a self-hosted runner
```bash
./automation/setup/runner/fix-runner-permissions.sh
sudo systemctl start github-runner
```

### Test containerized CI
```bash
./automation/ci-cd/run-ci.sh full
```

### Check Docker setup
```bash
docker-compose ps
docker-compose logs -f
```

## 📖 Related Documentation

- [Main Documentation](../README.md)
- [AI Agents](../ai-agents/)
- [MCP Architecture](../mcp/)
