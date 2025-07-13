# Docker Compose Health Check Action

A reusable composite action for starting Docker Compose services and waiting for them to be healthy.

## Usage Example

```yaml
- uses: ./.github/actions/docker-compose-health-check
  with:
    services: 'mcp-server'
    health-endpoint: 'http://localhost:8005/health'
    timeout: '60'
    build: 'true'
```

## Future Migration

To use this action in workflows, replace the duplicated docker-compose logic with:

```yaml
- uses: ./.github/actions/docker-compose-health-check
  with:
    services: ''  # all services
    health-endpoint: 'http://localhost:8005/health'

# After testing, clean up
- name: Stop services
  run: docker-compose down
```

This action automatically handles:
- Configuration validation
- Service startup with optional building
- Health checks with timeout
- Automatic cleanup on failure
