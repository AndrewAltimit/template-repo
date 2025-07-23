# Docker Compose Health Check Action

A reusable composite action for starting Docker Compose services and waiting for them to be healthy.

## Inputs

- **services**: Space-separated list of services to start (optional)
- **profiles**: Comma-separated list of Docker Compose profiles to activate (optional)
- **health-endpoint**: Health check endpoint URL (default: `http://localhost:8005/health`)
- **timeout**: Timeout in seconds (default: `60`)
- **build**: Whether to build images (default: `true`)

## Usage Examples

### Start specific services

```yaml
- uses: ./.github/actions/docker-compose-health-check
  with:
    services: 'mcp-code-quality mcp-content-creation mcp-gaea2'
    health-endpoint: 'http://localhost:8010/health'
    timeout: '60'
    build: 'true'
```

### Use Docker Compose profiles

```yaml
- uses: ./.github/actions/docker-compose-health-check
  with:
    profiles: 'services'
    health-endpoint: 'http://localhost:8010/health'
    timeout: '60'
```

### Start multiple profiles

```yaml
- uses: ./.github/actions/docker-compose-health-check
  with:
    profiles: 'services,database'
    health-endpoint: 'http://localhost:8010/health'
    timeout: '90'
```

## Important Notes

1. **Profile-based services**: If your `docker-compose.yml` uses profiles and you don't specify either `services` or `profiles`, no services will be started and the action will fail with a helpful error message.

2. **Service names vs profiles**: You can either specify individual service names OR use profiles, not both. Service names take precedence if both are provided.

3. **Health check endpoint**: The action will continuously check the specified endpoint until it responds successfully or the timeout is reached. Make sure at least one of your services exposes this endpoint.

4. **Automatic cleanup**: On failure, the action automatically runs `docker-compose down` to clean up services.

## Migration Guide

To migrate from inline docker-compose commands to this action:

**Before:**
```yaml
- name: Start services
  run: |
    docker-compose up --build -d
    # Wait for health check
    timeout=60
    elapsed=0
    while [ $elapsed -lt $timeout ]; do
      if curl -s http://localhost:8005/health > /dev/null; then
        break
      fi
      sleep 2
      elapsed=$((elapsed + 2))
    done
```

**After:**
```yaml
- uses: ./.github/actions/docker-compose-health-check
  with:
    services: 'mcp-server'
    health-endpoint: 'http://localhost:8005/health'
    timeout: '60'
```

This action automatically handles:
- Configuration validation
- Service startup with optional building
- Health checks with timeout
- Better error messages when no services are selected
- Automatic cleanup on failure
