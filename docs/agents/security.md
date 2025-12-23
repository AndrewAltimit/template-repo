# AI Agents Security Configuration

## GitHub Token Management

### ⚠️ IMPORTANT: Never Commit Secrets!

Secrets should be managed through GitHub Environments, not files in the repository.

## Token Configuration Methods

### 1. GitHub Actions (Recommended)

The workflows use GitHub Environments for secure secret management:

```yaml
jobs:
  monitor-issues:
    environment: production  # Uses environment secrets
    steps:
      - name: Run agent
        env:
          GITHUB_TOKEN: ${{ secrets.AGENT_TOKEN }}
```

**Setup Required:**
1. Go to Settings → Environments → New environment
2. Create a "production" environment
3. Add secret: `AGENT_TOKEN` (your GitHub PAT)
4. Add variable: `ENABLE_AGENTS` = `true` (to enable the feature)
5. Configure protection rules as needed

See [GitHub Environments Setup Guide](../infrastructure/github-environments.md) for detailed instructions.

### 2. Local Development

For local testing:

```bash
# Option 1: Use environment variable
export GITHUB_TOKEN="your-token-here"
docker-compose run --rm ai-agents python -m github_agents.cli issue-monitor

# Option 2: Use gh CLI authentication (recommended)
gh auth login
docker-compose run --rm ai-agents python -m github_agents.cli issue-monitor
```

### 3. Self-Hosted Runners

Self-hosted runners will use the GitHub Environment secrets automatically. No additional configuration needed.

For runner-specific tokens (not recommended), you can:
```bash
# Add to runner's .env file:
GITHUB_TOKEN=your-token-here
```

## Human Training and Oversight

Before working with AI agents, team members should complete the [AI Safety Training Guide](human-training.md) to understand:

- **Deceptive Capabilities**: How AI systems can hide capabilities or develop backdoors
- **Specification Gaming**: How AI finds unintended ways to satisfy objectives
- **Trust Calibration**: Building appropriate levels of trust in AI systems
- **Emergency Procedures**: What to do if you suspect misalignment
- **Behavioral Monitoring**: Normal vs. warning sign behaviors

This training is essential for maintaining security when working with increasingly capable AI systems.

## sleeper agents System

The repository now includes an advanced **sleeper agents System** for identifying potential backdoors and hidden behaviors in AI models:

### What It Detects
- **Backdoor Triggers**: Hidden activation patterns that cause unexpected behavior
- **Deceptive Alignment**: Models pretending to be aligned during testing
- **Goal Misgeneralization**: Models pursuing different objectives than trained
- **Hidden Capabilities**: Abilities that only emerge under specific conditions

### Detection Methods
- **Residual Stream Analysis**: Using TransformerLens to examine internal model activations
- **Attention Pattern Analysis**: Identifying suspicious attention head behaviors
- **Layer-wise Probing**: Detecting hidden representations across model layers
- **Behavioral Testing**: Comprehensive test suites for various attack scenarios

### Usage
```bash
# Run sleeper agents tests in CI/CD
docker-compose run --rm sleeper-eval-cpu python -m packages.sleeper_agents.cli evaluate \
  --model "gpt2" --test-suite "robustness"

# Quick CPU-based detection
docker-compose run --rm sleeper-eval-cpu \
  python packages/sleeper_agents/scripts/test_cpu_mode.py
```

### Integration with CI/CD
The sleeper agents tests are automatically run as part of the PR validation pipeline when changes affect AI-related code. See the [sleeper agents Documentation](../../packages/sleeper_agents/README.md) for detailed usage instructions.

## Security Best Practices

### 1. Token Permissions

Create a fine-grained Personal Access Token with minimal permissions:
- Repository: Read & Write (for the specific repo)
- Issues: Read & Write
- Pull Requests: Read & Write
- Contents: Read & Write (for creating PRs)

### 2. Token Rotation

- Rotate tokens every 90 days
- Use GitHub's token expiration feature
- Monitor token usage in GitHub Settings

### 3. Runtime Security

The implementation includes multiple security layers:

1. **GitHub Environments**: Secrets are managed by GitHub, never touch the filesystem
2. **Environment Protection**: Optional approval requirements for production
3. **Automatic Injection**: GitHub injects secrets only when needed
4. **Logging Redaction**: All tokens are automatically redacted from logs

### 4. Automatic Secret Masking

The system includes **automatic, real-time secret masking** for all GitHub comments:

#### Configuration
Secrets are defined in `.secrets.yaml` in repository root:
```yaml
environment_variables:
  - GITHUB_TOKEN
  - OPENROUTER_API_KEY
  - DB_PASSWORD

patterns:
  - name: GITHUB_TOKEN
    pattern: "ghp_[A-Za-z0-9_]{36,}"

auto_detection:
  enabled: true
  include_patterns: ["*_TOKEN", "*_SECRET", "*_KEY"]
```

#### How It Works
- **PreToolUse Hooks**: Intercept all `gh` commands before execution
- **Pattern Matching**: Detect secrets by patterns and environment values
- **Automatic Masking**: Replace with `[MASKED_VARNAME]` placeholders
- **Transparent**: Agents don't know masking occurred

#### Testing
```bash
# Verify gh-validator is installed
which gh
# Should show: ~/.local/bin/gh

# Test emoji blocking
gh pr comment 1 --body "Test with emoji 🎉"
# Should be blocked with error about Unicode emoji

# Test secret masking
export TEST_SECRET="super-secret-value"
# Add TEST_SECRET to .secrets.yaml environment_variables
gh pr comment 1 --body "Secret is super-secret-value"
# Should mask the secret before posting
```

### 5. Verification

To verify your security setup:

```bash
# Check that gh-validator is installed and first in PATH
which gh  # Should show ~/.local/bin/gh

# Check that .secrets.yaml exists
test -f .secrets.yaml && echo "✓ Secrets config exists"

# Verify no secrets in git history
git log -p | grep -E "(ghp_|github_pat_)" || echo "✓ No tokens found"
```

## Common Issues

### Issue: "No GitHub token found"

**Solution**: Ensure one of these is configured:
1. `GITHUB_TOKEN` environment variable is set
2. `gh auth status` shows you're authenticated
3. Workflow uses `environment: production`

### Issue: Workflow can't access secrets

**Solution**:
- Verify the workflow job includes `environment: production`
- Check that secrets are defined in the production environment
- Ensure branch protection rules allow the workflow to run

### Issue: Secrets appearing in logs

**Solution**: Ensure all modules use secure logging:
```python
from logging_security import setup_secure_logging, get_secure_logger
setup_secure_logging()
logger = get_secure_logger(__name__)
```

## Never Do This!

❌ **NEVER** hardcode tokens in code
❌ **NEVER** commit tokens to the repository
❌ **NEVER** log tokens without redaction
❌ **NEVER** use tokens in command line arguments (they appear in process lists)
❌ **NEVER** share tokens between environments (use separate environments)
❌ **NEVER** disable environment protection rules for production
❌ **NEVER** disable automatic secret masking in `.secrets.yaml`
❌ **NEVER** bypass PreToolUse hooks when posting GitHub comments
