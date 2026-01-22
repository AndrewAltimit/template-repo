# Strands Rust Runtime

A Rust-based agent runtime for AWS Bedrock AgentCore, implementing the AgentCore HTTP protocol with Claude model integration.

## Overview

This workspace provides a complete runtime for deploying AI agents to AWS Bedrock AgentCore. It's built with a modular architecture allowing easy extension and customization.

## Architecture

```
strands-runtime/          # Main HTTP server (AgentCore protocol)
    ├── handlers.rs       # /ping and /invocations endpoints
    ├── server.rs         # Axum server with request logging
    ├── config.rs         # Environment-based configuration
    ├── secrets.rs        # AWS Secrets Manager integration
    └── telemetry.rs      # OpenTelemetry tracing

strands-agent/            # Agent orchestration
    ├── agent.rs          # Main agent loop with iteration control
    ├── conversation.rs   # Conversation state management
    └── model.rs          # Model trait definition

strands-core/             # Core types and traits
    ├── message.rs        # Message and Role types
    ├── content.rs        # ContentBlock (text, tool use, tool result)
    ├── tool.rs           # Tool trait and definitions
    └── error.rs          # Error types

strands-models/           # Model implementations
    └── bedrock.rs        # AWS Bedrock Converse API client

strands-session/          # Session management
    ├── session.rs        # Session state
    ├── manager.rs        # Session lifecycle
    └── memory.rs         # In-memory session store

strands-tools/            # Tool framework
    └── registry.rs       # Tool registration and discovery
```

## AgentCore Protocol

The runtime implements the AWS Bedrock AgentCore HTTP protocol:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ping` | GET | Health check - returns `{"status": "Healthy", "time_of_last_update": <timestamp>}` |
| `/invocations` | POST | Agent invocation - accepts JSON with `prompt` field |

### Request Format

```json
{
  "prompt": "Your message to the agent",
  "session_id": "optional-session-id",
  "stream": false
}
```

### Response Format

```json
{
  "invocation_id": "uuid",
  "session_id": "uuid",
  "response": "Agent's response text",
  "stop_reason": "EndTurn",
  "usage": {
    "input_tokens": 10,
    "output_tokens": 25,
    "total_tokens": 35
  },
  "iterations": 1
}
```

## Configuration

Configuration is done via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | HTTP server port | `8080` |
| `MODEL_ID` | Bedrock model/inference profile ID | `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| `AWS_REGION` | AWS region | `us-east-1` |
| `MAX_TOKENS` | Maximum response tokens | `4096` |
| `MAX_ITERATIONS` | Maximum agent loop iterations | `10` |
| `SYSTEM_PROMPT` | Optional system prompt | None |
| `BEDROCK_CREDENTIALS_SECRET` | Secrets Manager secret name (optional) | None |

## Credential Management

### Option 1: Direct Credentials

Pass AWS credentials directly via environment variables:

```bash
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

### Option 2: Secrets Manager (Recommended)

Store Bedrock credentials in AWS Secrets Manager for better security:

1. Create a secret with JSON format:
   ```json
   {
     "AWS_ACCESS_KEY_ID": "AKIA...",
     "AWS_SECRET_ACCESS_KEY": "..."
   }
   ```

2. Set environment variable pointing to the secret:
   ```bash
   BEDROCK_CREDENTIALS_SECRET=strands-runtime/bedrock-credentials
   ```

3. Use minimal credentials in runtime env vars (only needs `secretsmanager:GetSecretValue`)

## Building

### Local Development

```bash
# Check compilation
cargo check --workspace

# Run tests
cargo test --workspace

# Build release binary
cargo build --release --package strands-runtime
```

### Docker (for AgentCore)

```bash
# From infra/aws directory
docker build --platform linux/arm64 \
  -f docker/strands-runtime-rust/Dockerfile \
  -t strands-runtime-rust:latest .
```

## Deployment to AgentCore

See [docs/AGENTCORE_DEPLOYMENT_STATUS.md](docs/AGENTCORE_DEPLOYMENT_STATUS.md) for detailed deployment instructions and current status.

### Quick Deploy

```bash
# Build and push to ECR
./scripts/build-and-push-rust.sh bedrock-agentcore-strands-runtime-dev latest

# Create/update runtime via AWS CLI
aws bedrock-agentcore-control create-agent-runtime \
  --agent-runtime-name my-runtime \
  --agent-runtime-artifact '{"containerConfiguration": {"containerUri": "<ecr-uri>"}}' \
  --role-arn <execution-role-arn> \
  --network-configuration '{"networkMode": "PUBLIC"}' \
  --environment-variables '{"MODEL_ID": "us.anthropic.claude-sonnet-4-20250514-v1:0", ...}'
```

## Key Learnings

1. **AgentCore does NOT inject AWS credentials** - You must provide them via environment variables
2. **Use inference profile IDs** - Raw model IDs don't work with on-demand throughput (use `us.anthropic.claude-*` prefix)
3. **Firecracker VMs don't support IMDS** - EC2 metadata service returns 405
4. **Model agreements required** - Submit Anthropic use case form in Bedrock console before using Claude models

## Dependencies

- **Rust 1.88+** - Latest stable Rust
- **Tokio** - Async runtime
- **Axum** - HTTP framework
- **AWS SDK for Rust** - Bedrock and Secrets Manager clients
- **OpenTelemetry** - Distributed tracing

## License

MIT
