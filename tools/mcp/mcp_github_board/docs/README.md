# GitHub Board MCP Server

> A Model Context Protocol server for GitHub Projects v2 board operations, enabling work queue management, claim coordination, and multi-agent task assignment.

## Features

- **Work Queue Management**: Query ready work (unblocked, unclaimed TODO issues)
- **Claim System**: Claim, renew, and release work with timeout management
- **Dependency Tracking**: Add blockers and parent-child relationships
- **Status Updates**: Update issue status on the board
- **Agent Coordination**: Multi-agent support with conflict prevention

## Installation

The server is included in the template repository's MCP server collection.

### Requirements

- Python 3.11+
- GitHub token with repository and project access
- github-ai-agents package installed

### Environment Variables

```bash
# Required
GITHUB_TOKEN=ghp_your_token_here
GITHUB_REPOSITORY=owner/repo

# Optional - Board Configuration
GITHUB_PROJECT_NUMBER=1
GITHUB_OWNER=owner
GITHUB_BOARD_CONFIG=.github/board_config.yaml
```

## Running the Server

### HTTP Mode (Recommended)

```bash
# Start server on port 8022
python -m mcp_github_board.server

# Or with custom port
uvicorn mcp_github_board.server:app --host 0.0.0.0 --port 8022
```

### Docker Mode

```bash
# Using docker-compose
docker-compose up -d mcp-github-board

# View logs
docker-compose logs -f mcp-github-board
```

### STDIO Mode

```bash
# For local MCP client integration
python -m mcp_github_board.server --stdio
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

**Response:**
```json
{
  "success": true,
  "result": {
    "count": 3,
    "issues": [
      {
        "number": 42,
        "title": "Implement authentication",
        "status": "Todo",
        "priority": "High",
        "type": "Feature",
        "url": "https://github.com/owner/repo/issues/42",
        "labels": ["backend", "security"],
        "blocked_by": []
      }
    ]
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

**Response:**
```json
{
  "success": true,
  "result": {
    "claimed": true,
    "issue_number": 42,
    "agent": "claude",
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

**Example:**
```json
{
  "tool": "renew_claim",
  "arguments": {
    "issue_number": 42,
    "agent_name": "claude",
    "session_id": "claude-session-123"
  }
}
```

### 4. release_work

Release claim on an issue.

**Parameters:**
- `issue_number` (required): Issue to release
- `agent_name` (required): Agent releasing the claim
- `reason` (optional): Release reason (completed/blocked/abandoned/error)

**Example:**
```json
{
  "tool": "release_work",
  "arguments": {
    "issue_number": 42,
    "agent_name": "claude",
    "reason": "completed"
  }
}
```

### 5. update_status

Update issue status on the board.

**Parameters:**
- `issue_number` (required): Issue to update
- `status` (required): New status (Todo/In Progress/Blocked/Done/Abandoned)

**Example:**
```json
{
  "tool": "update_status",
  "arguments": {
    "issue_number": 42,
    "status": "Done"
  }
}
```

### 6. add_blocker

Add a blocking dependency between issues.

**Parameters:**
- `issue_number` (required): Issue that is blocked
- `blocker_number` (required): Issue that blocks

**Example:**
```json
{
  "tool": "add_blocker",
  "arguments": {
    "issue_number": 43,
    "blocker_number": 42
  }
}
```

### 7. mark_discovered_from

Mark an issue as discovered from another (parent-child relationship).

**Parameters:**
- `issue_number` (required): Child issue
- `parent_number` (required): Parent issue

**Example:**
```json
{
  "tool": "mark_discovered_from",
  "arguments": {
    "issue_number": 44,
    "parent_number": 42
  }
}
```

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

**Example:**
```json
{
  "tool": "list_agents",
  "arguments": {}
}
```

### 11. get_board_config

Get current board configuration.

**Parameters:** None

**Example:**
```json
{
  "tool": "get_board_config",
  "arguments": {}
}
```

## Configuration

### Board Configuration File

Create `.github/board_config.yaml`:

```yaml
project:
  number: 1
  owner: "your-username"

repository: "your-username/your-repo"

fields:
  status: "Status"
  priority: "Priority"
  agent: "Agent"
  type: "Type"
  blocked_by: "Blocked By"
  discovered_from: "Discovered From"
  size: "Estimated Size"

agents:
  enabled_agents:
    - "claude"
    - "opencode"
    - "gemini"
  auto_discover: true

work_claims:
  timeout: 86400  # 24 hours
  renewal_interval: 3600  # 1 hour

work_queue:
  exclude_labels:
    - "wontfix"
    - "duplicate"
  priority_labels:
    critical:
      - "security"
      - "data-loss"
    high:
      - "bug"
      - "performance"
```

## Testing

### Run Tests

```bash
# Test the server
python tools/mcp/github_board/scripts/test_server.py

# Test with custom URL
python tools/mcp/github_board/scripts/test_server.py --url http://localhost:8022
```

### Manual Testing

```bash
# Health check
curl http://localhost:8022/health

# List tools
curl http://localhost:8022/mcp/tools

# Execute tool
curl -X POST http://localhost:8022/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "list_agents",
    "arguments": {}
  }'
```

## Integration with .mcp.json

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "github-board": {
      "command": "python",
      "args": [
        "-m",
        "mcp_github_board.server"
      ],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}",
        "GITHUB_REPOSITORY": "${GITHUB_REPOSITORY}",
        "GITHUB_PROJECT_NUMBER": "1"
      }
    }
  }
}
```

## Architecture

### Components

- **GitHubBoardMCPServer**: Main MCP server class
- **BoardManager**: Core board operations (from github_agents package)
- **BoardConfig**: Configuration management
- **GraphQL Client**: GitHub Projects v2 API integration

### Flow

1. Client sends tool request to `/mcp/execute`
2. Server validates and routes to appropriate handler
3. Handler calls BoardManager methods
4. BoardManager executes GraphQL operations
5. Response returned to client

### Error Handling

- **BoardNotFoundError**: Project not found for owner
- **GraphQLError**: GitHub API errors
- **ValidationError**: Invalid parameters
- **TimeoutError**: Claim timeout exceeded

## Troubleshooting

### Server Won't Start

**Issue:** `Board manager not initialized`

**Solution:**
- Check `GITHUB_TOKEN` environment variable is set
- Verify token has `repo` and `project` scopes
- Check network connectivity to GitHub API

### Claims Not Working

**Issue:** `Failed to claim work`

**Solution:**
- Verify issue exists and is in TODO status
- Check issue isn't already claimed
- Ensure agent name matches enabled_agents in config

### GraphQL Errors

**Issue:** `GraphQL error: Failed to fetch project items`

**Solution:**
- Verify project number is correct
- Check owner has access to project
- Ensure project is a Projects v2 board (not classic project)

## Development

### Running Locally

```bash
# Install dependencies
pip install -e packages/github_agents

# Set environment
export GITHUB_TOKEN=your_token
export GITHUB_REPOSITORY=owner/repo

# Run server
python -m mcp_github_board.server
```

### Adding New Tools

1. Add tool definition to `get_tools()`
2. Add route handler in `execute_tool()`
3. Implement tool method (e.g., `_my_new_tool()`)
4. Update documentation

## Related Documentation

- [Board Manager CLI](../../../../tools/rust/board-manager/README.md)
- [GitHub Agents CLI](../../../../tools/rust/github-agents-cli/README.md)
- [MCP Core Documentation](../../mcp_core/docs/README.md)

## License

MIT License - See repository LICENSE file for details.
