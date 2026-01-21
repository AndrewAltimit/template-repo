# AWS AgentCore Infrastructure

Terraform/Terragrunt infrastructure for AWS Bedrock AgentCore with BYORT (Bring Your Own Runtime).

## Structure

```
infra/aws/
├── terragrunt.hcl              # Root config (remote state, providers)
├── iam/                        # IAM roles module
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── terragrunt.hcl
├── ecr/                        # ECR repository module
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── terragrunt.hcl
├── agentcore-runtime/          # AgentCore runtime module
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── terragrunt.hcl
├── docker/strands-runtime/     # Container image
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── agent.py
└── scripts/
    ├── bootstrap-state-backend.sh
    ├── build-and-push.sh
    └── deploy-all.sh
```

## Quick Start

```bash
# 1. Bootstrap state backend (one-time)
./scripts/bootstrap-state-backend.sh

# 2. Deploy everything
./scripts/deploy-all.sh -y

# Or deploy individually:
cd iam && terragrunt apply
cd ../ecr && terragrunt apply
../scripts/build-and-push.sh
cd ../agentcore-runtime && terragrunt apply
```

## Deployed Resources

- **IAM Roles**: Deployer role (Terraform) + Runtime execution role (AgentCore)
- **ECR Repository**: Container registry for runtime images
- **AgentCore Runtime**: Strands-based AI agent (HTTP protocol, port 8080)
- **CloudWatch Logs**: `/aws/bedrock-agentcore/runtimes/<runtime-name>`

## Testing

```bash
cd agentcore-runtime
RUNTIME_ID=$(terragrunt output -raw runtime_id)

aws bedrock-agentcore invoke-runtime \
  --runtime-id "${RUNTIME_ID}" \
  --body '{"prompt": "Hello!"}'
```

## Phase 2: Rust Runtime

See `docs/infrastructure/aws-agentcore-deployment.md` for the plan to convert from Python Strands to a Rust implementation.
