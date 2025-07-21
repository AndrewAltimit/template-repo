# Gaea2 Server Deployment Issue

## Summary

The Gaea2 integration tests are failing because the deployed server is using the wrong implementation.

## Problem

There are two Gaea2 servers in the codebase:

1. **Standalone Server** (`/tools/mcp/gaea2_mcp_server.py`):
   - Has full implementation of all Gaea2 features
   - Originally expected `parameters` field in requests
   - Now fixed to accept both `parameters` and `arguments`

2. **Modular Server** (`/tools/mcp/gaea2/server.py`):
   - Inherits from `BaseMCPServer`
   - Uses FastAPI with strict validation (only accepts `arguments`)
   - Currently uses **stub implementations** that don't actually work
   - Returns error `'type'` because stubs don't implement real functionality

## Current Deployment

The server at `192.168.0.152:8007` is running the **modular version** with stubs, not the standalone version with actual implementation.

## Solution

Deploy the standalone server instead:

```bash
# On the Windows host with Gaea2 installed:
cd /path/to/template-repo
python tools/mcp/gaea2_mcp_server.py
```

This will start the server with:
- Full Gaea2 functionality
- Support for both `parameters` and `arguments` fields
- Actual terrain generation capabilities

## Alternative Solution

If you must use the modular server, the stub implementations in `/tools/mcp/gaea2/generation/stub_implementations.py` need to be replaced with actual implementations that import from the main `gaea2_mcp_server.py` or related modules.

## Test Compatibility

The tests have been updated to handle both server response formats:
- Standalone server: Direct response
- Modular server: Wrapped response with `result` field

However, the tests will still fail with the modular server until the stub implementations are replaced with real ones.
