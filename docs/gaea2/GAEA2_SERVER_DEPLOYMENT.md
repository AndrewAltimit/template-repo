# Gaea2 MCP Server Deployment Guide

## Running the Gaea2 MCP Server

The Gaea2 MCP server must be run as a Python module from the repository root directory to resolve imports correctly.

### Correct Command

From the repository root (`D:\Unreal\Repos\template-repo`):

```powershell
# Run in HTTP mode (default)
python -m tools.mcp.gaea2.server

# Run with specific port (default is 8007)
python -m tools.mcp.gaea2.server --port 8007

# Run with custom Gaea path
python -m tools.mcp.gaea2.server --gaea-path "C:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe"

# Run with all options
python -m tools.mcp.gaea2.server --port 8007 --gaea-path "C:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe" --output-dir "D:\Gaea\Output"
```

### Important Notes

1. **Always run from repository root**: The server uses relative imports that require it to be run as a module
2. **Use `-m` flag**: This tells Python to run the file as a module, resolving imports correctly
3. **Default port**: 8007
4. **Default mode**: HTTP

### Common Issues

1. **ImportError**: If you see `ImportError: attempted relative import with no known parent package`, you're not running it as a module. Use `python -m tools.mcp.gaea2.server` instead.

2. **Module not found**: Make sure you're in the repository root directory when running the command.

3. **Port already in use**: If port 8007 is already in use, specify a different port with `--port`

### Verifying the Server

Once running, you can verify it's working:

```powershell
# Check health endpoint
curl http://localhost:8007/health

# Or use Invoke-WebRequest in PowerShell
Invoke-WebRequest -Uri http://localhost:8007/health | Select-Object -ExpandProperty Content
```

### File Locations

- **New modular server**: `tools/mcp/gaea2/server.py` (use this one!)
- **Old server**: `tools/mcp/gaea2_mcp_server.py` (deprecated, has old method mappings)
