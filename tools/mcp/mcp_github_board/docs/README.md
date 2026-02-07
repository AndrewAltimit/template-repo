# GitHub Board MCP Server

> A Model Context Protocol server for GitHub Projects v2 board operations, enabling work queue management, claim coordination, and multi-agent task assignment.

## Features

- **Work Queue Management**: Query ready work (unblocked, unclaimed TODO issues)
- **Claim System**: Claim, renew, and release work with timeout management
- **Dependency Tracking**: Add blockers and parent-child relationships
- **Status Updates**: Update issue status on the board
- **Agent Coordination**: Multi-agent support with conflict prevention
- **Native Rust Performance**: Fast execution with minimal overhead

## Installation

### Pre-built Binary

Download from GitHub Releases:

```bash
# Linux x64
curl -L https://github.com/AndrewAltimit/template-repo/releases/latest/download/mcp-github-board-linux-x64 -o mcp-github-board
chmod +x mcp-github-board
```

### Build from Source

```bash
cd tools/mcp/mcp_github_board
cargo build --release
# Binary will be at target/release/mcp-github-board
```

### Requirements

- **board-manager CLI**: Must be installed and in PATH (or at a known location)
- **GitHub token**: With repository and project access
- **Environment Variables**:
  ```bash
  export GITHUB_TOKEN=ghp_your_token_here
  export GITHUB_REPOSITORY=owner/repo
  ```

## Running the Server

### Standalone Mode (Recommended)

```bash
# Start server on port 8022
mcp-github-board --mode standalone --port 8022

# Or with custom settings
mcp-github-board --mode standalone --port 8022 --log-level debug
```

### STDIO Mode

For direct MCP client integration:

```bash
mcp-github-board --mode standalone
```

### Server Mode (REST API only)

```bash
mcp-github-board --mode server --port 8022
```

### Test Endpoints

```bash
# Health check
curl http://localhost:8022/health

# List tools
curl http://localhost:8022/mcp/tools

# Execute tool
curl -X POST http://localhost:8022/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "query_ready_work",
    "arguments": {"limit": 5}
  }'
```

## Available Tools

### 1. query_ready_work

Get ready work from the board (unblocked, unclaimed TODO issues).

**Parameters:**
- `agent_name` (optional): Filter for specific agent
- `limit` (optional, default: 10): Maximum issues to return

**Example:**
```json
{
  "tool": "query_ready_work",
  "arguments": {
    "agent_name": "claude",
    "limit": 5
  }
}
```

### 2. claim_work

Claim an issue for implementation.

**Parameters:**
- `issue_number` (required): Issue to claim
- `agent_name` (required): Agent claiming the issue
- `session_id` (required): Unique session identifier

**Example:**
```json
{
  "tool": "claim_work",
  "arguments": {
    "issue_number": 42,
    "agent_name": "claude",
    "session_id": "claude-session-123"
  }
}
```

### 3. renew_claim

Renew an active claim for long-running tasks.

**Parameters:**
- `issue_number` (required): Issue with active claim
- `agent_name` (required): Agent renewing the claim
- `session_id` (required): Session ID from original claim

### 4. release_work

Release claim on an issue.

**Parameters:**
- `issue_number` (required): Issue to release
- `agent_name` (required): Agent releasing the claim
- `reason` (optional): Release reason (completed/blocked/abandoned/error)

### 5. update_status

Update issue status on the board.

**Parameters:**
- `issue_number` (required): Issue to update
- `status` (required): New status (Todo/In Progress/Blocked/Done/Abandoned)

### 6. add_blocker

Add a blocking dependency between issues.

**Parameters:**
- `issue_number` (required): Issue that is blocked
- `blocker_number` (required): Issue that blocks

### 7. mark_discovered_from

Mark an issue as discovered from another (parent-child relationship).

**Parameters:**
- `issue_number` (required): Child issue
- `parent_number` (required): Parent issue

### 8. get_issue_details

Get full details for a specific issue.

**Parameters:**
- `issue_number` (required): Issue to query

### 9. get_dependency_graph

Get dependency graph for an issue.

**Parameters:**
- `issue_number` (required): Issue to query

### 10. list_agents

Get list of enabled agents for this board.

**Parameters:** None

### 11. get_board_config

Get current board configuration.

**Parameters:** None

### 12. board_status

Get server status and board-manager CLI availability.

**Parameters:** None

## Configuration

### Integration with .mcp.json

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "github-board": {
      "command": "mcp-github-board",
      "args": ["--mode", "standalone"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "GITHUB_REPOSITORY": "${GITHUB_REPOSITORY}"
      }
    }
  }
}
```

### Board Configuration

The server uses the `board-manager` CLI which reads configuration from `.github/board_config.yaml`. See the [Board Manager documentation](../../../rust/board-manager/README.md) for configuration details.

## Architecture

### Components

- **MCP Server**: Built on mcp-core Rust library
- **board-manager CLI**: Handles all GitHub API interactions
- **Async Runtime**: Tokio for high-performance async operations

### Flow

1. Client sends tool request to server
2. Server validates parameters and constructs CLI command
3. board-manager CLI executes operation against GitHub API
4. JSON response returned to client

### Error Handling

- **MCPError::InvalidParameters**: Missing or invalid tool parameters
- **MCPError::Internal**: board-manager CLI errors or JSON parsing failures
- CLI errors include stderr output for debugging

## Troubleshooting

### board-manager Not Found

**Issue:** `board-manager CLI not found`

**Solution:**
- Install board-manager or ensure it's in PATH
- Build from source: `cd tools/rust/board-manager && cargo build --release`
- Check common locations: `~/.local/bin/board-manager`

### GitHub API Errors

**Issue:** `board-manager error: ...`

**Solution:**
- Verify GITHUB_TOKEN has proper scopes (repo, project)
- Check GITHUB_REPOSITORY format (owner/repo)
- Ensure project number is correct in board config

## Related Documentation

- [Board Manager CLI](../../../rust/board-manager/README.md)
- [MCP Core Rust](../../mcp_core_rust/README.md)
- [GitHub Agents CLI](../../../rust/github-agents-cli/README.md)

## License

Part of the template-repo project. See repository root [LICENSE](../../../../LICENSE) file.
