# Strands Rust Runtime

> **A production-ready Rust runtime for AWS Bedrock AgentCore, demonstrating that the entire agent stack can be implemented in any language - there's no proprietary magic, just well-defined APIs and protocols.**

## Overview

This workspace provides a complete runtime for deploying AI agents to AWS Bedrock AgentCore. It's built with a **modular architecture** allowing easy extension and customization.

This is a **from-scratch Rust implementation** inspired by the [Strands Agents SDK](https://github.com/strands-agents/sdk-python) (Python). The key insight: **everything in the Python SDK is just API plumbing** - AWS SDKs, HTTP endpoints, JSON schemas, and standard protocols that all have excellent Rust equivalents.

## Feature Mapping

When porting from Strands Python SDK to Rust, we mapped each "feature" to its actual underlying technology:

| Feature | What It Actually Is | Rust Implementation |
|---------|---------------------|---------------------|
| IAM Authentication | AWS SigV4 request signing | `aws-sdk-rust` handles natively |
| Runtime Credentials | Environment variables or Secrets Manager | Custom `SecretsCredentialsProvider` |
| AgentCore Protocol | HTTP REST endpoints (`/ping`, `/invocations`) | `axum` web framework |
| Bedrock Converse API | REST API with SigV4 | `aws-sdk-bedrockruntime` crate |
| Agent Loop | Iterative tool-calling pattern | Custom implementation in `strands-agent` |
| Tool Framework | JSON Schema + function dispatch | Trait-based `Tool` abstraction |
| Session Management | In-memory or external state store | `strands-session` with pluggable backends |
| OTEL Tracing | OpenTelemetry standard | `tracing` + `opentelemetry-rust` |
| Model Abstraction | Trait for LLM providers | `Model` trait in `strands-agent` |
| Message Types | Structured conversation data | `Message`, `ContentBlock` in `strands-core` |

### What This Runtime Implements vs What It Wraps

```
strands-rust-runtime
├── Custom Implementations (~3000 lines)
│   ├── Agent loop with iteration control
│   ├── Conversation state management
│   ├── Tool executor and registry
│   ├── Message/ContentBlock types
│   ├── Session managers
│   ├── AgentCore HTTP protocol handlers
│   └── Secrets Manager credential provider
│
└── External Dependencies (existing Rust ecosystem)
    ├── AWS APIs ─────────► aws-sdk-rust (bedrockruntime, secretsmanager)
    ├── HTTP Server ──────► axum + tokio
    ├── Serialization ────► serde + serde_json
    ├── Tracing ──────────► tracing + opentelemetry
    └── Error Handling ───► thiserror + anyhow
```

### Python Strands SDK to Rust Mapping

| Python Strands Component | Rust Equivalent | Notes |
|--------------------------|-----------------|-------|
| `strands.Agent` | `strands-agent::Agent` | Main orchestration loop |
| `strands.Model` (trait) | `strands-agent::Model` | Abstract model interface |
| `strands.models.BedrockModel` | `strands-models::BedrockModel` | Bedrock Converse API client |
| `strands.types.Message` | `strands-core::Message` | Conversation messages |
| `strands.types.ContentBlock` | `strands-core::ContentBlock` | Text, ToolUse, ToolResult |
| `strands.tools.Tool` | `strands-core::Tool` (trait) | Tool interface |
| `strands.tools.ToolRegistry` | `strands-tools::ToolRegistry` | Tool discovery/dispatch |
| `strands.session.SessionManager` | `strands-session::SessionManager` | Session state |
| Environment config | `strands-runtime::Config` | Type-safe config struct |

## Architecture

```
strands-runtime/          # Main HTTP server (AgentCore protocol)
    ├── handlers.rs       # /ping and /invocations endpoints
    ├── server.rs         # Axum server with request logging middleware
    ├── config.rs         # Environment-based configuration
    ├── secrets.rs        # AWS Secrets Manager credential provider
    └── telemetry.rs      # OpenTelemetry tracing setup

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

### Data Flow

```
HTTP Request (/invocations)
         │
         ▼
┌─────────────────┐
│  Request Logging │  ◄── Middleware logs method, URI, headers, body
│    Middleware    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Handlers     │  ◄── Parse JSON, create/resume session
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│     Agent       │  ◄── Main orchestration loop
│                 │
│  ┌───────────┐  │
│  │Conversation│  │  ◄── Manages message history
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │   Model   │  │  ◄── Calls Bedrock Converse API
│  └─────┬─────┘  │
│        │        │
│  ┌─────▼─────┐  │
│  │   Tools   │  │  ◄── Execute tool calls (if any)
│  └───────────┘  │
└────────┬────────┘
         │
         ▼
    JSON Response
```

### Agent Loop Detail

The agent loop implements a standard tool-calling pattern:

```
1. Add user message to conversation
2. Loop (up to MAX_ITERATIONS):
   a. Call model with conversation history
   b. Extract response content blocks
   c. If any ToolUse blocks:
      - Execute each tool
      - Add ToolResult blocks to conversation
      - Continue loop
   d. If EndTurn or no tool calls:
      - Break loop
3. Return final response with usage stats
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

### Stop Reasons

| Stop Reason | Description |
|-------------|-------------|
| `EndTurn` | Model completed response naturally |
| `ToolUse` | Model requested tool execution (handled internally) |
| `MaxTokens` | Response truncated due to token limit |
| `StopSequence` | Hit a stop sequence |
| `MaxIterations` | Agent loop hit iteration limit |

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

> **Critical**: AgentCore runs containers in Firecracker microVMs that do **not** have access to EC2 Instance Metadata Service (IMDS). This means you **cannot** use IAM roles attached to the execution role for Bedrock API calls inside your container code.

### Understanding the Two Credential Contexts

```
┌─────────────────────────────────────────────────────────────────┐
│                    AgentCore Control Plane                       │
│                                                                  │
│  Uses: Execution Role (IAM Role ARN)                            │
│  For:  Pulling ECR images, CloudWatch logs, Secrets Manager     │
│        (if configured)                                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           │ Launches container
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Your Container (Firecracker VM)               │
│                                                                  │
│  Has:  Environment variables you configured                      │
│  NOT:  IMDS access (returns 405)                                │
│  NOT:  Automatic IAM role credentials                           │
│                                                                  │
│  For Bedrock API calls, you need explicit credentials:          │
│  - Option 1: AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY          │
│  - Option 2: Fetch from Secrets Manager (recommended)           │
└─────────────────────────────────────────────────────────────────┘
```

### Option 1: Direct Credentials (Not Recommended)

Pass AWS credentials directly via environment variables:

```bash
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
```

This works but exposes credentials in AgentCore configuration.

### Option 2: Secrets Manager (Recommended)

Store Bedrock credentials in AWS Secrets Manager for better security:

1. **Create the secret** with JSON format:
   ```json
   {
     "AWS_ACCESS_KEY_ID": "AKIA...",
     "AWS_SECRET_ACCESS_KEY": "..."
   }
   ```

2. **Create two IAM users/roles**:

   | User | Permissions | Purpose |
   |------|-------------|---------|
   | Secrets Reader | `secretsmanager:GetSecretValue` on specific secret | Bootstrap credentials |
   | Bedrock User | `bedrock:InvokeModel`, `bedrock:Converse` | Actual Bedrock calls |

3. **Configure the runtime**:
   ```bash
   # These are the "bootstrap" credentials (secrets reader)
   AWS_ACCESS_KEY_ID=AKIA_SECRETS_READER...
   AWS_SECRET_ACCESS_KEY=...

   # This tells the runtime to fetch Bedrock credentials from Secrets Manager
   BEDROCK_CREDENTIALS_SECRET=strands-runtime/bedrock-credentials
   ```

4. **How it works at runtime**:
   ```
   Container starts
        │
        ▼
   Use bootstrap credentials (env vars)
        │
        ▼
   Fetch secret from Secrets Manager
        │
        ▼
   Extract Bedrock credentials from secret JSON
        │
        ▼
   Create Bedrock client with extracted credentials
        │
        ▼
   Make Bedrock API calls
   ```

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

AgentCore requires ARM64 containers:

```bash
# From infra/aws directory
docker build --platform linux/arm64 \
  -f docker/strands-runtime-rust/Dockerfile \
  -t strands-runtime-rust:latest .
```

### Dockerfile Requirements

Key requirements for AgentCore compatibility:

```dockerfile
# Must use ARM64
FROM --platform=linux/arm64 rust:1.88-slim-bookworm AS builder

# Must expose port 8080
EXPOSE 8080

# Must have health check capability (optional but recommended)
HEALTHCHECK CMD curl -f http://localhost:8080/ping || exit 1

# Binary must be statically linked or have all deps
# Using debian slim works well
```

## Deployment to AgentCore

### Quick Deploy

```bash
# Build and push to ECR
./scripts/build-and-push-rust.sh bedrock-agentcore-strands-runtime-dev latest

# Create runtime
aws bedrock-agentcore-control create-agent-runtime \
  --agent-runtime-name my-runtime \
  --agent-runtime-artifact '{"containerConfiguration": {"containerUri": "<ecr-uri>"}}' \
  --role-arn <execution-role-arn> \
  --network-configuration '{"networkMode": "PUBLIC"}' \
  --environment-variables '{
    "MODEL_ID": "us.anthropic.claude-sonnet-4-20250514-v1:0",
    "AWS_REGION": "us-east-1",
    "BEDROCK_CREDENTIALS_SECRET": "strands-runtime/bedrock-credentials"
  }'

# Update existing runtime
aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id <runtime-id> \
  --agent-runtime-artifact '{"containerConfiguration": {"containerUri": "<new-ecr-uri>"}}'

# Invoke
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-id <runtime-id> \
  --payload '{"prompt": "Hello!"}'
```

## Key Learnings

> **Hard-won lessons from deploying to AgentCore** - each of these cost hours of debugging.

### 1. AgentCore Does NOT Inject AWS Credentials

The execution role is used by AgentCore itself (for ECR pull, CloudWatch logs), not by your container code. You must provide credentials explicitly.

### 2. Use Inference Profile IDs

Raw model IDs like `anthropic.claude-sonnet-4-20250514-v1:0` don't work with on-demand throughput. Use the regional inference profile format:

```
# Wrong
anthropic.claude-sonnet-4-20250514-v1:0

# Correct
us.anthropic.claude-sonnet-4-20250514-v1:0
```

### 3. Firecracker VMs Don't Support IMDS

Attempting to reach the EC2 metadata service returns HTTP 405. This is by design - AgentCore VMs are isolated.

```rust
// This will NOT work in AgentCore:
let provider = ImdsCredentialsProvider::builder().build();

// This WILL work:
let provider = EnvironmentVariableCredentialsProvider::new();
// Or use Secrets Manager as shown above
```

### 4. Model Agreements Required

Before using Claude models, you must submit the Anthropic use case form in the AWS Bedrock console. Check with:

```bash
aws bedrock get-foundation-model-availability \
  --model-id anthropic.claude-sonnet-4-20250514-v1:0 \
  --query 'agreementAvailability.status'
```

If it returns `NOT_AVAILABLE`, go to Bedrock console > Model access > Submit use case.

### 5. CloudWatch Logs Are Your Friend

AgentCore streams container stdout/stderr to CloudWatch. Log group format:
```
/aws/bedrock-agentcore/runtimes/<runtime-name>-<runtime-id>-DEFAULT
```

Use structured logging (JSON) with `tracing-subscriber` for easy parsing.

### 6. Request Logging Middleware is Essential

When debugging 400/415/422 errors, having request logging middleware saved hours of debugging. The middleware logs:
- HTTP method and URI
- All headers (with sensitive values masked)
- Request body (truncated if large)

## Extending the Runtime

### Adding a New Tool

1. Implement the `Tool` trait:

```rust
use strands_core::{Tool, ToolDefinition, ToolResult};
use async_trait::async_trait;

pub struct MyTool;

#[async_trait]
impl Tool for MyTool {
    fn definition(&self) -> ToolDefinition {
        ToolDefinition {
            name: "my_tool".to_string(),
            description: "Does something useful".to_string(),
            input_schema: serde_json::json!({
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                },
                "required": ["input"]
            }),
        }
    }

    async fn execute(&self, input: serde_json::Value) -> ToolResult {
        let input_str = input["input"].as_str().unwrap_or("");
        ToolResult::success(format!("Processed: {}", input_str))
    }
}
```

2. Register it:

```rust
let mut registry = ToolRegistry::new();
registry.register(Box::new(MyTool));
```

### Adding a New Model Provider

1. Implement the `Model` trait:

```rust
use strands_agent::Model;
use strands_core::{Message, ModelResponse};
use async_trait::async_trait;

pub struct MyModel {
    // client, config, etc.
}

#[async_trait]
impl Model for MyModel {
    async fn converse(
        &self,
        messages: &[Message],
        tools: &[ToolDefinition],
        system_prompt: Option<&str>,
    ) -> Result<ModelResponse, Error> {
        // Call your model API
    }
}
```

## Dependencies

| Crate | Version | Purpose |
|-------|---------|---------|
| `tokio` | 1.x | Async runtime |
| `axum` | 0.7 | HTTP framework |
| `aws-sdk-bedrockruntime` | latest | Bedrock Converse API |
| `aws-sdk-secretsmanager` | latest | Secrets Manager client |
| `serde` | 1.x | Serialization |
| `tracing` | 0.1 | Structured logging |
| `opentelemetry` | 0.22 | Distributed tracing |
| `uuid` | 1.x | UUID generation |
| `thiserror` | 1.x | Error types |
| `http-body-util` | 0.1 | Body extraction for middleware |

## Related Documentation

- [Strands Agents SDK (Python)](https://github.com/strands-agents/sdk-python) - Original Python implementation
- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html) - Official AWS docs

## License

Part of the template-repo project. See repository LICENSE file.
