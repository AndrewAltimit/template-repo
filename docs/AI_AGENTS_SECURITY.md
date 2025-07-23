# AI Agents Security Configuration

## GitHub Token Management

### ⚠️ IMPORTANT: Never Commit Secrets!

The `.secrets/` directory is used for runtime secrets only and should **NEVER** contain committed files.

## Token Configuration Methods

### 1. GitHub Actions (Production)

GitHub Actions automatically creates the secret file at runtime:

```yaml
- name: Create GitHub token secret file
  run: |
    echo "${{ secrets.GITHUB_TOKEN }}" > .secrets/github_token.txt
    chmod 600 .secrets/github_token.txt

- name: Cleanup secrets
  if: always()
  run: |
    rm -rf .secrets
```

**Setup Required:**
1. Go to your repository Settings → Secrets and variables → Actions
2. Ensure `GITHUB_TOKEN` secret exists (it's provided by default)
3. For enhanced permissions, create a fine-grained PAT and add it as a secret

### 2. Local Development

For local testing only:

```bash
# Option 1: Use the setup script (creates .secrets locally)
./scripts/agents/setup-docker-secrets.sh

# Option 2: Use environment variable
export GITHUB_TOKEN="your-token-here"
docker-compose run --rm ai-agents python scripts/agents/run_agents.py

# Option 3: Use gh CLI authentication
gh auth login
docker-compose run --rm ai-agents python scripts/agents/run_agents.py
```

### 3. Self-Hosted Runners

For self-hosted runners, use one of these approaches:

```bash
# Option 1: Environment variable in runner service
# Add to .env file on runner:
GITHUB_TOKEN=your-token-here

# Option 2: Use systemd credentials (Linux)
sudo systemctl set-environment GITHUB_TOKEN=your-token-here

# Option 3: Use Docker secrets (Swarm mode)
echo "your-token" | docker secret create github_token -
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

1. **Docker Secrets**: Tokens are mounted as read-only files
2. **Automatic Cleanup**: Secrets are deleted after workflow runs
3. **No Environment Exposure**: Tokens aren't exposed in environment variables
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
from scripts.agents.logging_security import setup_secure_logging, get_secure_logger
setup_secure_logging()
logger = get_secure_logger('test')
logger.info('Token: ghp_1234567890abcdef1234567890abcdef12345678')
"
# Should output: Token: [REDACTED]
```

## Common Issues

### Issue: "No GitHub token found"

**Solution**: Ensure one of these is configured:
1. `.secrets/github_token.txt` exists (local only)
2. `GITHUB_TOKEN` environment variable is set
3. `gh auth status` shows you're authenticated

### Issue: Container can't read secrets

**Solution**: Check permissions:
```bash
ls -la .secrets/
# Should show: drwx------ (700) for directory
# Should show: -rw------- (600) for files
```

### Issue: Secrets appearing in logs

**Solution**: Ensure all modules use secure logging:
```python
from logging_security import setup_secure_logging, get_secure_logger
setup_secure_logging()
logger = get_secure_logger(__name__)
```

## Never Do This!

❌ **NEVER** commit `.secrets/github_token.txt` to the repository
❌ **NEVER** hardcode tokens in code
❌ **NEVER** log tokens without redaction
❌ **NEVER** use tokens in command line arguments (they appear in process lists)
❌ **NEVER** share tokens between environments (dev/staging/prod)
