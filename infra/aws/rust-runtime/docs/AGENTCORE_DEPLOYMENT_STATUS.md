# Strands Rust Runtime - AgentCore Deployment Status

**Date:** 2026-01-22
**Status:** WORKING

## Successful Deployment

The Rust-based Strands runtime is now successfully deployed and working on AWS Bedrock AgentCore.

### Working Configuration

| Setting | Value |
|---------|-------|
| Runtime | `strands_rust_runtime_v3-daRLe95kFQ` |
| Model | `us.anthropic.claude-sonnet-4-20250514-v1:0` (inference profile) |
| Status | READY |

### Environment Variables

#### Option 1: Direct Credentials (Simple)
```json
{
  "AWS_REGION": "us-east-1",
  "AWS_DEFAULT_REGION": "us-east-1",
  "AWS_ACCESS_KEY_ID": "<iam_user_access_key>",
  "AWS_SECRET_ACCESS_KEY": "<iam_user_secret_key>",
  "MODEL_ID": "us.anthropic.claude-sonnet-4-20250514-v1:0"
}
```

#### Option 2: Secrets Manager (Recommended, Currently Active)
```json
{
  "AWS_REGION": "us-east-1",
  "AWS_DEFAULT_REGION": "us-east-1",
  "AWS_ACCESS_KEY_ID": "<secrets_reader_access_key>",
  "AWS_SECRET_ACCESS_KEY": "<secrets_reader_secret_key>",
  "BEDROCK_CREDENTIALS_SECRET": "strands-runtime/bedrock-credentials",
  "MODEL_ID": "us.anthropic.claude-sonnet-4-20250514-v1:0"
}
```

With Secrets Manager approach:
- The credentials in env vars only have permission to read the secret
- Bedrock credentials are stored encrypted in Secrets Manager
- Credential rotation is easier (just update the secret)

### AWS Resources

| Resource | ARN/Name |
|----------|----------|
| ECR Repository | `bedrock-agentcore-strands-runtime-dev` |
| Runtime | `strands_rust_runtime_v3-daRLe95kFQ` |
| Current Image | `secrets-v1` |
| Secrets Manager Secret | `strands-runtime/bedrock-credentials` |
| Secrets Reader IAM User | `strands-runtime-secrets` |
| Secrets Policy | `StrandsRuntimeSecretsReadOnly` |
| Bedrock IAM User | `strands-runtime-test` |

### Secrets Integration Status

The runtime successfully loads credentials from AWS Secrets Manager at startup:
```
Fetching Bedrock credentials from Secrets Manager secret_name=strands-runtime/bedrock-credentials
Successfully retrieved Bedrock credentials from Secrets Manager
Applied credentials from Secrets Manager to environment
```

This allows for:
- Minimal permissions in runtime env vars (secrets reader only)
- Encrypted credential storage in Secrets Manager
- Easy credential rotation without runtime redeployment

### Key Learnings

1. **AgentCore does NOT inject AWS credentials** - Must provide via environment variables
2. **Use inference profile IDs** - Raw model IDs like `anthropic.claude-sonnet-4-20250514-v1:0` don't work with on-demand; use `us.anthropic.claude-sonnet-4-20250514-v1:0` instead
3. **Firecracker VMs don't support IMDS** - EC2 metadata service returns 405

---

## Overview

This document tracks the deployment status of our Rust-based Strands runtime to AWS Bedrock AgentCore.

## Python SDK Analysis (bedrock-agentcore v1.2.0)

We analyzed the official `bedrock-agentcore` Python package from PyPI to understand the expected protocol.

### Key Findings

#### 1. HTTP Protocol
The `BedrockAgentCoreApp` is a **Starlette-based web server** with:
- `GET /ping` - Health check endpoint
- `POST /invocations` - Agent invocation endpoint
- `WebSocket /ws` - Bidirectional streaming

#### 2. Header Constants (from `bedrock_agentcore.runtime.models`)
```python
SESSION_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id"
REQUEST_ID_HEADER = "X-Amzn-Bedrock-AgentCore-Runtime-Request-Id"
ACCESS_TOKEN_HEADER = "WorkloadAccessToken"  # NOT AWS credentials!
OAUTH2_CALLBACK_URL_HEADER = "OAuth2CallbackUrl"
AUTHORIZATION_HEADER = "Authorization"
CUSTOM_HEADER_PREFIX = "X-Amzn-Bedrock-AgentCore-Runtime-Custom-"
```

#### 3. Credential Architecture (CRITICAL)
- **AgentCore does NOT inject AWS credentials** into containers
- Instead, AgentCore provides a `WorkloadAccessToken` header
- This token is for the **AgentCore Identity service** (OAuth2 flows, API keys for external services)
- For AWS API calls (like Bedrock), the Python SDK uses `boto3.Session()` which relies on:
  1. Environment variables (`AWS_ACCESS_KEY_ID`, etc.)
  2. Shared credentials file
  3. IAM role credentials via IMDS
  4. Container credentials

#### 4. Ping Response Format
```json
{
  "status": "Healthy",  // or "HealthyBusy"
  "time_of_last_update": <unix_timestamp_int>
}
```

### Implications for Rust Runtime

1. **Our HTTP protocol is correct** - We match the expected endpoints and response formats
2. **Credentials must be provided** - Either via environment variables or implementing the WorkloadAccessToken flow
3. **The 400 error is a separate issue** - Likely routing/proxy problem, not credential-related

## What Works

### Container Build & Local Execution
- Docker image builds successfully for ARM64 architecture
- Container starts and listens on port 8080
- Health endpoint (`GET /ping`) returns correct AgentCore format:
  ```json
  {"status": "Healthy", "time_of_last_update": <unix_timestamp>}
  ```
- Invocation endpoint (`POST /invocations`) receives and parses requests correctly

### AgentCore Deployment
- Runtime deploys to AgentCore successfully
- Runtime shows `READY` status
- Container starts in AgentCore environment
- Environment variables can be passed through runtime configuration
- CloudWatch logs are created and accessible

## Current Issues

### Issue 1: AWS Credentials Not Automatically Provided

**Problem:** AgentCore does NOT automatically inject AWS credentials into BYORT (Bring Your Own Runtime) containers.

**Evidence from CloudWatch logs:**
```
Credential env check env_var=AWS_ACCESS_KEY_ID value=(not set)
Credential env check env_var=AWS_SECRET_ACCESS_KEY value=(not set)
Credential env check env_var=AWS_SESSION_TOKEN value=(not set)
Credential env check env_var=AWS_CONTAINER_CREDENTIALS_RELATIVE_URI value=(not set)
Credential env check env_var=AWS_WEB_IDENTITY_TOKEN_FILE value=(not set)
```

**Attempted Workaround:** Pass IAM user credentials via environment variables:
- Created IAM user `strands-runtime-test` with `AmazonBedrockFullAccess` policy
- Configured credentials in runtime's `EnvironmentVariables`
- Credentials appear in container logs as `(set, hidden)`

### Issue 2: Invocations Not Reaching Container

**Problem:** After configuration changes, invocations return 400 errors but never reach our application code.

**Observations:**
- Container starts successfully (startup logs visible)
- Server listens on port 8080
- No invocation logs appear (no "Processing invocation" or "Request header" logs)
- 400 error returned by AgentCore before request reaches our code

**Possible Causes:**
1. AgentCore routing/caching issue
2. Container warmup timing
3. Proxy layer returning 400 before forwarding to container

## Infrastructure State

### Current Resources

| Resource | Status | Notes |
|----------|--------|-------|
| ECR Repository | Active | `bedrock-agentcore-strands-runtime-dev` |
| Runtime (old) | Deleted | `strands_agent_runtime_dev-QLv8rVAB4X` |
| Runtime (new) | Active | `strands_rust_runtime_v2-4J3Fgs4dz4` |
| IAM User | Active | `strands-runtime-test` (for credential testing) |
| IAM Execution Role | Active | `AgentCoreRuntimeExecution-dev` |

### Runtime Configuration

```json
{
  "AgentRuntimeName": "strands_rust_runtime_v2",
  "Status": "READY",
  "ImageUri": "112565945478.dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-strands-runtime-dev:debug-headers",
  "EnvironmentVariables": {
    "AWS_REGION": "us-east-1",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_ACCESS_KEY_ID": "<set>",
    "AWS_SECRET_ACCESS_KEY": "<set>",
    "ENVIRONMENT": "dev",
    "LOG_LEVEL": "DEBUG"
  }
}
```

## Code Changes Made for Debugging

### handlers.rs
- Added `HeaderMap` import for request header logging
- Added header logging in `invoke` handler to trace incoming requests

### server.rs
- Added credential environment variable logging at startup
- Logs all AWS credential-related env vars to verify configuration

## Investigation Needed

1. ~~**Analyze official Strands Python SDK**~~ - DONE (see Python SDK Analysis above)
   - ~~Credential acquisition in AgentCore environment~~
   - ~~Container startup and health checks~~
   - ~~Request handling protocol~~

2. **Investigate 400 error routing issue**:
   - Why invocations stopped reaching container after env var changes
   - Check if there's a cache invalidation issue
   - Test with a fresh runtime deployment

3. **Explore AWS credential options for BYORT**:
   - Environment variables work but invocations not reaching container
   - Check if AgentCore execution role provides credentials differently
   - Research if there's a credential provider endpoint in Firecracker

## Next Steps

1. ~~Clone `strands-agents/sdk-python` for reference~~ - DONE
2. ~~Study their AgentCore runtime implementation~~ - DONE
3. ~~Compare with our Rust implementation~~ - DONE (protocol matches)
4. **Create fresh runtime** to rule out routing/caching issues
5. **Test without IAM credentials in env vars** to see if invocations reach container
6. **If invocations work**, add credentials back and test Bedrock API calls

## Related Files

- `/infra/aws/rust-runtime/strands-runtime/src/handlers.rs` - HTTP handlers
- `/infra/aws/rust-runtime/strands-runtime/src/server.rs` - Server startup
- `/infra/aws/rust-runtime/strands-models/src/bedrock.rs` - Bedrock API client
- `/infra/aws/docker/strands-runtime-rust/Dockerfile` - Container build
