# Agent Containerization Strategy and Architecture Constraints

This document outlines the containerization approach for the multi-agent system, addressing both security concerns and architectural constraints while maintaining functionality.

## Overview

After careful analysis, we've determined that agents can be divided into two categories based on authentication and technical requirements:

1. **Host-Only Agents** (Cannot be containerized due to authentication constraints)
2. **Containerizable Agents** (Can run fully in Docker containers)

This division creates fundamental architectural constraints that affect how the system operates in automated workflows.

## Agent Classification

### Host-Only Agents

These agents MUST run on the host system due to authentication requirements:

#### Claude Code
- **Reason**: Requires machine-specific subscription authentication
- **Details**: Claude CLI uses browser-based OAuth flow tied to the host machine
- **Documentation**: See `docs/ai-agents/claude-auth.md`

#### Gemini CLI
- **Reason**: Requires Docker socket access for system operations
- **Details**: Gemini needs to spawn containers and access Docker daemon
- **Documentation**: See tools/mcp/gemini/docs/README.md

### Containerizable Agents

These agents can run in Docker containers with proper configuration:

#### OpenCode
- **Authentication**: API key via environment variable
- **Container**: `openrouter-agents`
- **Requirements**: Node.js runtime

#### Crush (Charm Bracelet)
- **Authentication**: API key via config file
- **Container**: `openrouter-agents`
- **Requirements**: Go runtime

## Architectural Constraints

When GitHub Actions workflows trigger the issue or PR monitors:

1. The monitor runs on the **host** to support Claude authentication
2. Container agents (OpenCode/Crush) are **not available** in this mode
3. Only Claude and Gemini can be used for automated workflows

### Practical Impact

For automated GitHub workflows:
- ✅ `[Approved][Claude]` - Works
- ✅ `[Approved][Gemini]` - Works
- ❌ `[Approved][OpenCode]` - Requires manual intervention
- ❌ `[Approved][Crush]` - Requires manual intervention

The system will post a helpful error message explaining the constraint and suggesting alternatives when container agents are requested in automated workflows.

### Workarounds

#### Option 1: Use Host Agents
Instead of `[Approved][OpenCode]`, use:
- `[Approved][Claude]` - Most capable agent
- `[Approved][Gemini]` - Good for code review

#### Option 2: Manual Container Execution
Run the monitor manually in the container:

```bash
# For issues
docker-compose --profile agents run --rm openrouter-agents \
  python -m github_ai_agents.cli issue-monitor

# For PRs
docker-compose --profile agents run --rm openrouter-agents \
  python -m github_ai_agents.cli pr-monitor
```

#### Option 3: Future Enhancement
A potential solution would be to create a bridge service that:
1. Runs on the host with Claude credentials
2. Proxies requests to containerized agents when needed
3. Handles the authentication handoff

### Why This Design?

1. **Security**: Container agents are isolated from the host system
2. **Authentication**: Claude's auth model requires host access
3. **Simplicity**: Running monitors in one environment avoids complex IPC
4. **Portability**: Containerized agents work consistently across environments

## Implementation

### Container Architecture

```yaml
# docker-compose.yml
services:
  # Existing AI agents container (for Claude when containerization becomes possible)
  ai-agents:
    build: docker/ai-agents.Dockerfile
    profiles: [agents]

  # New container for OpenRouter-compatible agents
  openrouter-agents:
    build: docker/openrouter-agents.Dockerfile
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    profiles: [agents, openrouter]
```

### Security Improvements

1. **Eliminated `curl | bash` Pattern**
   - Replaced with `install_agents_safe.sh` providing manual instructions
   - Users can review each installation step
   - No automatic execution of remote scripts

2. **No System-Level Dependencies**
   - Containerized agents don't require host installations
   - All dependencies contained within Docker images
   - Host remains clean and portable

3. **Environment Variable Management**
   - API keys passed securely via environment variables
   - No hardcoded credentials
   - Supports `.env` file for local development

## Usage Patterns

### Development (Mixed Mode)
```bash
# Host agents (Claude, Gemini)
claude --help
gemini --help

# Containerized agents
docker-compose run --rm openrouter-agents crush run -q "Write a function"
docker-compose run --rm openrouter-agents python -m github_ai_agents.cli issue-monitor
```

### Production (Recommended)
```bash
# All agents that can be containerized should be
docker-compose --profile openrouter up -d

# Only Claude and Gemini on host
python -m github_ai_agents.cli issue-monitor
```

## Migration Path

1. **Phase 1** (Current): Document exceptions, provide container option
2. **Phase 2**: Investigate Claude CLI API for potential containerization
3. **Phase 3**: Create authentication proxy for host-only agents
4. **Phase 4**: Full containerization when technically feasible

## Exceptions to Container-First Philosophy

This implementation creates documented exceptions to our container-first philosophy:

1. **Claude Code**: Authentication limitation (subscription-based)
2. **Gemini CLI**: Technical requirement (Docker access)
3. **AI Agents Runner**: Needs to coordinate both host and container agents

These exceptions are:
- Clearly documented in CLAUDE.md
- Technically justified
- Temporary (pending upstream changes)
- Security-reviewed

## Best Practices

1. **Prefer Containers**: Always use containerized versions when available
2. **Document Exceptions**: Any host requirement must be documented
3. **Secure Credentials**: Use environment variables, never hardcode
4. **Regular Updates**: Review containerization feasibility with each update
5. **Test Both Modes**: Ensure agents work in both host and container contexts

## Future Considerations

- Monitor Claude CLI for API-based authentication options
- Investigate credential proxy services for host agents
- Consider Kubernetes operators for production deployments
- Evaluate WebAssembly for lightweight agent isolation
