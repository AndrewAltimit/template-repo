# MCP Server Modes: STDIO vs HTTP

## Critical Understanding

MCP servers in this project support **two different modes** that serve different purposes:

### STDIO Mode (for Claude Desktop/Code)
- **Configuration**: `.mcp.json`
- **Usage**: `mcp__<server>__<tool>` functions in Claude
- **How it works**: Claude spawns the server process and communicates via stdin/stdout
- **Lifecycle**: Started/stopped automatically by Claude as needed

### HTTP Mode (for Web APIs/Testing)
- **Configuration**: `docker-compose.yml`
- **Usage**: Direct HTTP calls to `http://localhost:<port>`
- **How it works**: Runs as a persistent service
- **Lifecycle**: Started with `docker-compose up`, runs continuously

## Common Confusion Points

### ❌ WRONG: Starting HTTP server for Claude
```bash
# This starts HTTP mode - Claude CANNOT use this!
docker-compose up mcp-content-creation
```

### ✅ RIGHT: Claude uses STDIO automatically
```python
# Claude reads .mcp.json and starts STDIO server automatically
# Just use the tool directly:
result = mcp__content-creation__compile_latex(content="...")
```

## Server-Specific Configurations

### Content Creation Server
- **STDIO**: Auto-started by Claude when using `mcp__content-creation__*` tools
- **HTTP**: `docker-compose up mcp-content-creation` (port 8011)

### Code Quality Server
- **STDIO**: Auto-started by Claude when using `mcp__code-quality__*` tools
- **HTTP**: `docker-compose up mcp-code-quality` (port 8010)

### Gemini Server
- **STDIO**: Must run on host (not in container)
- **HTTP**: Also runs on host (port 8006)

### Gaea2 Server
- **STDIO**: Can run locally or connect to remote
- **HTTP**: Can run locally or at `192.168.0.152:8007`

## Volume Mounts and Output Directories

Both modes can use the same output directories:

### STDIO Mode
The `.mcp.json` configuration uses `docker-compose run` which respects volume mounts:
```json
{
  "content-creation": {
    "command": "docker-compose",
    "args": ["run", "--rm", "-T", "mcp-content-creation", ...]
  }
}
```

### HTTP Mode
The `docker-compose.yml` defines persistent volume mounts:
```yaml
volumes:
  - ./outputs/mcp-content:/output
```

Both modes will write to `./outputs/mcp-content/` on the host.

## Troubleshooting

### "mcp__<server>__<tool> not found"
- The MCP server is not connected in this Claude session
- Claude manages STDIO connections automatically
- Try using the tool - Claude should start it

### "Connection refused on port"
- You're trying to use HTTP mode
- For Claude, don't start services manually
- Let Claude handle STDIO connections

### Multiple containers running
- Clean up with: `docker ps | grep mcp | awk '{print $1}' | xargs docker stop`
- Remove stopped containers: `docker container prune`

## Best Practices

1. **For Claude Code**: Never manually start MCP servers
2. **For testing/debugging**: Use HTTP mode with `docker-compose up`
3. **For output files**: Both modes use the same `outputs/` directory
4. **For development**: Edit servers knowing they support both modes

## Summary

- **Claude uses STDIO** - Configured in `.mcp.json`, started automatically
- **HTTP is for APIs** - Configured in `docker-compose.yml`, started manually
- **Don't mix them up** - They serve different purposes!
