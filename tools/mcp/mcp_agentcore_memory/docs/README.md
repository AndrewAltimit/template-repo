# AgentCore Memory MCP Server

> A Model Context Protocol server for persistent AI agent memory, supporting AWS Bedrock AgentCore (managed) or ChromaDB (self-hosted) with semantic search capabilities.

## Overview

This MCP server provides persistent memory for AI agents, enabling:
- **Short-term memory**: Session-based events for conversation context
- **Long-term memory**: Facts and patterns stored indefinitely
- **Semantic search**: Find relevant memories by meaning, not just keywords

## Quick Start

### Using ChromaDB (Self-Hosted, Recommended for Development)

1. Start ChromaDB:
```bash
docker-compose --profile memory-chromadb up -d
```

2. The MCP server will auto-connect when invoked via Claude Code.

### Using AWS AgentCore (Managed)

1. Set up IAM role with required permissions (see below)
2. Create memory instance:
```bash
python -m mcp_agentcore_memory.scripts.setup_memory --name my-agent-memory
```
3. Configure environment:
```bash
export MEMORY_PROVIDER=agentcore
export AGENTCORE_MEMORY_ID=mem-xxxxxxxxxxxx
export AWS_REGION=us-east-1
```

## MCP Tools

### `store_event`
Store a short-term memory event.

**Note**: AWS AgentCore is rate-limited to 0.25 req/sec per session. Only use for sparse, high-value events.

```python
# Example usage via Claude Code
"Store this event: Starting work on authentication refactoring"
```

### `store_facts`
Store facts for long-term retention. No rate limits - use this for patterns and learnings.

```python
# Example
"Store these facts in codebase/patterns:
- The API uses JWT tokens with 15-minute expiry
- Refresh tokens are stored in httpOnly cookies"
```

### `search_memories`
Search memories using semantic similarity.

```python
# Example
"Search my memories for authentication patterns in codebase/patterns"
```

### `list_session_events`
List events from a specific session.

### `list_namespaces`
List available predefined namespaces.

### `memory_status`
Get provider status and info.

## Namespaces

Memories are organized into hierarchical namespaces:

| Namespace | Purpose |
|-----------|---------|
| `codebase/patterns` | Code patterns and idioms |
| `codebase/architecture` | Architectural decisions |
| `codebase/conventions` | Coding conventions |
| `reviews/pr` | PR review context |
| `preferences/user` | User preferences |
| `agents/claude` | Claude-specific learnings |

## Provider Comparison

| Feature | AWS AgentCore | ChromaDB |
|---------|---------------|----------|
| Managed | Yes | No |
| Rate Limits | 0.25 req/sec (events) | None |
| Cost | ~$2/month | Free |
| Setup | IAM + Memory ID | Docker one-liner |
| Best For | Enterprise, compliance | Development, prototyping |

## AWS IAM Permissions

### Runtime Role (for MCP server)
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreateEvent",
                "bedrock-agentcore:ListEvents",
                "bedrock-agentcore:BatchCreateMemoryRecords",
                "bedrock-agentcore:RetrieveMemoryRecords",
                "bedrock-agentcore:ListMemoryRecords"
            ],
            "Resource": "arn:aws:bedrock-agentcore:*:*:memory/*"
        }
    ]
}
```

### Bootstrap Role (for setup scripts)
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock-agentcore:CreateMemory",
                "bedrock-agentcore:GetMemory",
                "bedrock-agentcore:DeleteMemory"
            ],
            "Resource": "arn:aws:bedrock-agentcore:*:*:memory/*"
        }
    ]
}
```

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `MEMORY_PROVIDER` | `agentcore` or `chromadb` | `chromadb` |
| `AGENTCORE_MEMORY_ID` | AWS memory instance ID | (required for agentcore) |
| `AWS_REGION` | AWS region | `us-east-1` |
| `CHROMADB_HOST` | ChromaDB host | `localhost` |
| `CHROMADB_PORT` | ChromaDB port | `8000` |

## Development

### Run tests
```bash
cd tools/mcp/mcp_agentcore_memory
pytest tests/ -v
```

### Build container
```bash
docker-compose build mcp-agentcore-memory
```

### Run in HTTP mode (for debugging)
```bash
docker-compose --profile memory up -d
curl http://localhost:8023/health
```

## Security

- **Content Sanitization**: All content is scanned for secrets (API keys, tokens, passwords) before storage
- **Entropy Analysis**: High-entropy strings that look like secrets are redacted
- **No Secrets Policy**: Credentials are never stored in memory

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Server (agentcore-memory)                │
│                                                                 │
│  Tools: store_event, store_facts, search_memories, etc.        │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              MemoryProvider (Abstract Interface)            ││
│  └─────────────────────────────────────────────────────────────┘│
│                           │                                     │
│           ┌───────────────┴───────────────┐                    │
│           ▼                               ▼                    │
│  ┌─────────────────┐             ┌─────────────────┐          │
│  │  AgentCore      │             │  ChromaDB       │          │
│  │  Provider       │             │  Provider       │          │
│  │  (AWS)          │             │  (Local)        │          │
│  └─────────────────┘             └─────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## License

Part of the template-repo project. See repository LICENSE file.
