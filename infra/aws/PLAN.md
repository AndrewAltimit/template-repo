# AWS AgentCore Deployment Plan

This document outlines the plan for deploying AWS Bedrock AgentCore with a Bring Your Own Runtime (BYORT) approach, starting with a Python Strands runtime and eventually migrating to a Rust implementation.

## Overview

### Goals

1. **Phase 1**: Deploy a Python Strands-based agent runtime to AWS AgentCore using Terraform/Terragrunt
2. **Phase 2**: Convert the Strands agent runtime to Rust for type safety, performance, and reliability
3. **Infrastructure as Code**: All AWS resources managed via Terraform with Terragrunt for environment management
4. **Security-First**: Dedicated deployer role with least-privilege permissions

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AWS Account                                   │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Terraform-Managed Resources                 │  │
│  │                                                                │  │
│  │  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐  │  │
│  │  │ IAM Roles   │    │     ECR      │    │ AgentCore        │  │  │
│  │  │             │    │  Repository  │    │ Runtime          │  │  │
│  │  │ - Deployer  │───▶│              │───▶│                  │  │  │
│  │  │ - Runtime   │    │ strands-     │    │ - HTTP Protocol  │  │  │
│  │  │   Execution │    │   runtime    │    │ - Port 8080      │  │  │
│  │  └─────────────┘    └──────────────┘    │ - ARM64          │  │  │
│  │                                          └──────────────────┘  │  │
│  │                                                                │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │                    Supporting Resources                  │  │  │
│  │  │  - CloudWatch Log Groups                                 │  │  │
│  │  │  - X-Ray Tracing                                        │  │  │
│  │  │  - Bedrock Model Access                                  │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
infrastructure/
├── terraform/
│   ├── modules/
│   │   ├── iam/                    # IAM roles (deployer, runtime execution)
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   ├── ecr/                    # ECR repository for runtime images
│   │   │   ├── main.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   └── agentcore-runtime/      # AgentCore runtime resource
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── outputs.tf
│   └── environments/
│       ├── dev/
│       │   └── terragrunt.hcl
│       └── prod/
│           └── terragrunt.hcl
├── terragrunt/
│   ├── terragrunt.hcl              # Root configuration
│   ├── environments/
│   │   ├── dev/
│   │   │   ├── env.hcl             # Environment-specific variables
│   │   │   ├── iam/
│   │   │   │   └── terragrunt.hcl
│   │   │   ├── ecr/
│   │   │   │   └── terragrunt.hcl
│   │   │   └── agentcore-runtime/
│   │   │       └── terragrunt.hcl
│   │   └── prod/
│   │       └── (same structure)
│   └── _envcommon/
│       ├── iam.hcl
│       ├── ecr.hcl
│       └── agentcore-runtime.hcl
└── docker/
    └── agentcore-strands/
        ├── Dockerfile              # ARM64 Python Strands runtime
        ├── pyproject.toml
        ├── uv.lock
        └── agent.py                # Strands agent implementation
```

## Phase 1: Python Strands Deployment

### Step 1: IAM Roles Setup

Create two IAM roles:

#### 1.1 Deployer Role

Purpose: Used by Terraform to deploy AgentCore resources

```hcl
# Permissions required:
- bedrock-agentcore:* (full access to AgentCore)
- ecr:* on bedrock-agentcore-* repositories
- iam:CreateRole, iam:PassRole for runtime roles
- logs:* for CloudWatch setup
- s3:* for state bucket (if using S3 backend)
```

#### 1.2 Runtime Execution Role

Purpose: Used by the AgentCore runtime at execution time

```hcl
# Trust Policy: Allow bedrock-agentcore.amazonaws.com to assume
# Permissions required:
- ecr:BatchGetImage, ecr:GetDownloadUrlForLayer (pull images)
- logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents
- xray:PutTraceSegments, xray:PutTelemetryRecords
- bedrock:InvokeModel, bedrock:InvokeModelWithResponseStream
- bedrock-agentcore:GetWorkloadAccessToken*
- cloudwatch:PutMetricData (namespace: bedrock-agentcore)
```

### Step 2: ECR Repository

Create an ECR repository for the Strands runtime container:

```hcl
resource "aws_ecr_repository" "strands_runtime" {
  name                 = "bedrock-agentcore-strands-runtime"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}
```

### Step 3: Python Strands Container

Build an ARM64 container implementing the HTTP protocol contract:

#### Required Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/invocations` | POST | Main agent invocation endpoint |
| `/ping` | GET | Health check (must return 200) |

#### Dockerfile

```dockerfile
# Use uv's ARM64 Python base image
FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Copy uv files
COPY pyproject.toml uv.lock ./

# Install dependencies (including strands-agents, bedrock-agentcore)
RUN uv sync --frozen --no-cache

# Copy agent implementation
COPY agent.py ./

# Expose AgentCore HTTP protocol port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -f http://localhost:8080/ping || exit 1

# Run with OpenTelemetry instrumentation
CMD ["uv", "run", "opentelemetry-instrument", "uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8080"]
```

#### Agent Implementation (agent.py)

```python
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

app = BedrockAgentCoreApp()

# Initialize Strands agent with Bedrock model
model = BedrockModel(
    model_id="anthropic.claude-sonnet-4-20250514",
    region_name="us-east-1"
)

agent = Agent(
    model=model,
    system_prompt="You are a helpful AI assistant.",
)

@app.entrypoint
async def invoke(request):
    """Main agent invocation endpoint."""
    prompt = request.get("prompt", "")
    response = agent(prompt)
    return {"completion": str(response)}
```

### Step 4: AgentCore Runtime Resource

Using the AWSCC provider (since aws_bedrockagentcore_agent_runtime isn't in the main AWS provider yet):

```hcl
terraform {
  required_providers {
    awscc = {
      source  = "hashicorp/awscc"
      version = "~> 1.0"
    }
  }
}

resource "awscc_bedrockagentcore_runtime" "strands" {
  agent_runtime_name = "strands-agent-runtime"
  description        = "Strands-based AI agent runtime"

  agent_runtime_artifact = {
    container_configuration = {
      container_uri = "${aws_ecr_repository.strands_runtime.repository_url}:latest"
    }
  }

  network_configuration = {
    network_mode = "PUBLIC"
  }

  protocol_configuration = "HTTP"

  role_arn = aws_iam_role.runtime_execution.arn

  environment_variables = {
    AWS_REGION     = var.aws_region
    LOG_LEVEL      = "INFO"
    OTEL_EXPORTER  = "otlp"
  }

  tags = {
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
```

### Step 5: Terragrunt Configuration

Root `terragrunt.hcl`:

```hcl
# Remote state configuration
remote_state {
  backend = "s3"
  config = {
    bucket         = "terraform-state-${get_aws_account_id()}"
    key            = "${path_relative_to_include()}/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

# Generate provider configuration
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    awscc = {
      source  = "hashicorp/awscc"
      version = "~> 1.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"

  assume_role {
    role_arn = "arn:aws:iam::${get_aws_account_id()}:role/TerraformDeployer"
  }
}

provider "awscc" {
  region = "us-east-1"
}
EOF
}
```

## Phase 2: Rust Runtime Conversion

### Why Rust?

| Concern | Python | Rust |
|---------|--------|------|
| Type Safety | Runtime errors | Compile-time guarantees |
| API Contracts | KeyError at 3am | Won't compile if field missing |
| Memory | Leaks in long sessions | Ownership system prevents |
| Async | Callback hell, footguns | Proper streams with backpressure |
| Performance | Interpreted | Native speed |
| Reliability | Dependency conflicts | Cargo lockfile, no conflicts |

### What Strands Wraps vs External Dependencies

```
Strands SDK
├── Convenience Wrappers ──────► Implement in Rust (~2000 lines)
│   ├── Agent loop
│   ├── Session managers
│   └── Tool executor
│
└── External Dependencies ─────► Already exist in Rust
    ├── AWS APIs (aws-sdk-rust)
    ├── MCP (rmcp crate)
    ├── OTEL (opentelemetry-rust)
    └── Model provider APIs
```

### Rust Implementation Path

| Feature | What It Is | Rust Implementation |
|---------|-----------|---------------------|
| IAM auth | SigV4 signing | `aws-sdk-rust` handles natively |
| Runtime credentials | IMDS/MMDS | Custom provider |
| AgentCore Memory | REST API | `aws-sdk-bedrockagentcore` crate |
| AgentCore Identity | OAuth 2.0 flows | Standard implementation |
| MCP | Open protocol | `rmcp` crate |
| Guardrails | Bedrock API call | `aws-sdk-bedrockruntime` |
| A2A protocol | HTTP/WebSocket + JSON | Implement spec |
| OTEL tracing | OpenTelemetry | `tracing` + `opentelemetry-rust` |
| Session management | State + Memory API | Trait implementation |

### Rust Crate Structure (Future)

```
packages/agentcore-runtime/
├── Cargo.toml
├── src/
│   ├── lib.rs
│   ├── agent/
│   │   ├── mod.rs
│   │   ├── loop.rs           # Agent execution loop
│   │   └── session.rs        # Session management
│   ├── protocol/
│   │   ├── mod.rs
│   │   ├── http.rs           # HTTP protocol handler
│   │   ├── mcp.rs            # MCP protocol support
│   │   └── a2a.rs            # Agent-to-agent
│   ├── tools/
│   │   ├── mod.rs
│   │   └── executor.rs       # Tool execution
│   ├── memory/
│   │   ├── mod.rs
│   │   └── agentcore.rs      # AgentCore Memory API
│   └── observability/
│       ├── mod.rs
│       └── tracing.rs        # OTEL integration
└── tests/
```

## Deployment Commands

### Initial Setup (One-time)

```bash
# 1. Create deployer role (using root credentials)
cd infrastructure/terragrunt/environments/dev/iam
terragrunt init
terragrunt apply

# 2. Switch to deployer role for subsequent operations
export AWS_PROFILE=deployer
```

### Deploy AgentCore Runtime

```bash
# 1. Build and push container to ECR
./infrastructure/scripts/build-and-push.sh

# 2. Deploy ECR repository (if not exists)
cd infrastructure/terragrunt/environments/dev/ecr
terragrunt apply

# 3. Deploy AgentCore runtime
cd infrastructure/terragrunt/environments/dev/agentcore-runtime
terragrunt apply
```

### Validate Deployment

```bash
# Get runtime endpoint
ENDPOINT=$(terragrunt output -raw runtime_endpoint)

# Test health check
curl -X GET "$ENDPOINT/ping"

# Test invocation (with SigV4)
aws bedrock-agentcore invoke-runtime \
  --runtime-id $(terragrunt output -raw runtime_id) \
  --body '{"prompt": "Hello, world!"}'
```

## Security Considerations

1. **Least Privilege**: Each role has minimal required permissions
2. **SigV4 Authentication**: All AgentCore endpoints require signed requests
3. **Container Scanning**: ECR scans images on push
4. **No Hardcoded Credentials**: All secrets via environment variables or IAM
5. **State Encryption**: Terraform state encrypted in S3
6. **State Locking**: DynamoDB prevents concurrent modifications

## Monitoring & Observability

- **CloudWatch Logs**: `/aws/bedrock-agentcore/runtimes/{runtime-name}`
- **X-Ray Tracing**: Transaction search enabled
- **CloudWatch Metrics**: Namespace `bedrock-agentcore`
- **Health Checks**: `/ping` endpoint monitored

## Cost Considerations

- AgentCore runtime pricing is based on invocations and compute time
- ECR storage costs are minimal
- CloudWatch logs have retention policies to control costs
- Use reserved capacity for production workloads

## Next Steps

1. [ ] Set up Terraform state backend (S3 + DynamoDB)
2. [ ] Create IAM deployer role
3. [ ] Deploy ECR repository
4. [ ] Build and push Python Strands container
5. [ ] Deploy AgentCore runtime
6. [ ] Validate with test invocations
7. [ ] Set up monitoring dashboards
8. [ ] Begin Rust runtime implementation (Phase 2)

## References

- [AWS AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [Strands Agents Documentation](https://strandsagents.com/latest/documentation/)
- [AWSCC Provider - bedrockagentcore_runtime](https://registry.terraform.io/providers/hashicorp/awscc/latest/docs/resources/bedrockagentcore_runtime)
- [CloudFormation AWS::BedrockAgentCore::Runtime](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-bedrockagentcore-runtime.html)
