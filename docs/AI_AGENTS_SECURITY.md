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
          GITHUB_TOKEN: ${{ secrets.AI_AGENT_TOKEN }}
```

**Setup Required:**
1. Go to Settings → Environments → New environment
2. Create a "production" environment
3. Add secret: `AI_AGENT_TOKEN` (your GitHub PAT)
4. Add variable: `ENABLE_AI_AGENTS` = `true` (to enable the feature)
5. Configure protection rules as needed

See [GitHub Environments Setup Guide](./GITHUB_ENVIRONMENTS_SETUP.md) for detailed instructions.

### 2. Local Development

For local testing:

```bash
# Option 1: Use environment variable
export GITHUB_TOKEN="your-token-here"
docker-compose run --rm ai-agents python -m github_ai_agents.cli issue-monitor

# Option 2: Use gh CLI authentication (recommended)
gh auth login
docker-compose run --rm ai-agents python -m github_ai_agents.cli issue-monitor
```

### 3. Self-Hosted Runners

Self-hosted runners will use the GitHub Environment secrets automatically. No additional configuration needed.

For runner-specific tokens (not recommended), you can:
```bash
# Add to runner's .env file:
GITHUB_TOKEN=your-token-here
```

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

### 4. Verification

To verify your security setup:

```bash
# Check that .secrets is in .gitignore
grep -E "^\.secrets" .gitignore

# Verify no secrets in git history
git log -p | grep -E "(ghp_|github_pat_)" || echo "No tokens found"

# Test secret redaction
docker-compose run --rm ai-agents python -c "
from github_ai_agents.utils.logging import setup_secure_logging, get_secure_logger
setup_secure_logging()
logger = get_secure_logger('test')
logger.info('Token: ghp_1234567890abcdef1234567890abcdef12345678')
"
# Should output: Token: [REDACTED]
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
