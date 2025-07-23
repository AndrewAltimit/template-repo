# GitHub Environments Setup for AI Agents

This guide explains how to set up GitHub Environments for secure secret management with the AI agents.

## Why GitHub Environments?

GitHub Environments provide:
- **Environment-specific secrets** - Different tokens for dev/staging/prod
- **Protection rules** - Require reviews before deployment
- **Deployment history** - Track when agents run
- **Access control** - Limit who can trigger deployments

## Setup Instructions

### 1. Create the Production Environment

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Environments**
3. Click **New environment**
4. Name it: `production`
5. Click **Configure environment**

### 2. Add Environment Secrets

In the production environment, add these secrets:

#### Secrets (sensitive values):
| Secret Name | Description | Required |
|------------|-------------|----------|
| `AI_AGENT_TOKEN` | GitHub Personal Access Token with appropriate permissions | Yes |

#### Variables (configuration values):
| Variable Name | Description | Default | Effect |
|--------------|-------------|---------|--------|
| `ENABLE_AI_AGENTS` | Master switch for AI agents | `false` | When `true`: Enables scheduled runs AND auto-fix capabilities |

#### Creating a Fine-Grained Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Click **Generate new token**
3. Set token details:
   - **Token name**: `AI-Agents-Production` (or similar)
   - **Expiration**: 90 days (recommended)
   - **Repository access**: Select only your specific repository

4. **Required Repository Permissions** (exactly 5):

   | Permission | Access Level | Purpose |
   |------------|--------------|---------|
   | **Actions** | Read | View workflow runs and logs |
   | **Commit statuses** | Read | See CI/CD status on PRs |
   | **Contents** | Read + Write | Read files, create branches, push commits |
   | **Issues** | Read + Write | Read issues/comments, post comments |
   | **Pull requests** | Read + Write | Read PRs/reviews, create PRs, post comments |
   | **Metadata** | Read | (Automatically included) |

5. **Account Permissions**: Leave all unchecked (0 selected)

6. Click **Generate token** and save it securely

### 3. Configure Protection Rules (Optional but Recommended)

Add protection rules to the production environment:

1. **Required reviewers**: Require approval before agent runs
2. **Deployment branches**: Limit to `main` branch only
3. **Environment secrets**: Only available to workflows using this environment

Example protection rules:
```
✓ Required reviewers: 1
✓ Restrict deployment branches: main
✓ Deployment branch policy: Protected branches only
```

### 4. Workflow Configuration

The workflows are already configured to use the production environment:

```yaml
jobs:
  monitor-issues:
    runs-on: self-hosted
    environment: production  # This line enables environment secrets
    steps:
      - name: Run issue monitor
        env:
          GITHUB_TOKEN: ${{ secrets.AI_AGENT_TOKEN }}  # From environment secret
          ENABLE_AI_AGENTS: ${{ vars.ENABLE_AI_AGENTS || 'false' }}  # From environment variable
```

## Testing Your Setup

### 1. Manual Trigger Test

```bash
# Trigger issue monitor manually
gh workflow run issue-monitor.yml --repo YOUR_OWNER/YOUR_REPO

# Trigger PR review monitor manually
gh workflow run pr-review-monitor.yml --repo YOUR_OWNER/YOUR_REPO
```

### 2. Check Workflow Runs

1. Go to **Actions** tab in your repository
2. Select the workflow (Issue Monitor or PR Review Monitor)
3. Check that it shows "production" environment was used
4. Verify no secret exposure in logs

### 3. Verify Token Permissions

Create a test issue with the keyword trigger:
```
This is a test issue to verify the AI agent setup.

Expected behavior: The agent should respond
Steps to reproduce: Just this issue creation
Version: main branch

[Approved][Claude]
```

## Security Best Practices

### 1. Token Rotation

- Rotate PATs every 90 days
- Use GitHub's token expiration reminders
- Keep tokens minimal in scope

### 2. Environment Protection

- Always use protection rules for production
- Require reviews for sensitive operations
- Limit environment to specific branches

### 3. Monitoring

- Review deployment history regularly
- Check for unexpected workflow runs
- Monitor token usage in GitHub settings

### 4. Secret Management

- **Never** commit tokens to the repository
- Use environment-specific tokens
- Enable secret scanning in repository settings

## Troubleshooting

### Issue: "Bad credentials" or "Resource not accessible by personal access token"

**Solution**:
- Verify your PAT has all 5 required repository permissions listed above
- Check that the token hasn't expired
- Ensure you selected the correct repository when creating the token
- Confirm no Account permissions are selected (should show "0 selected")

### Issue: Workflow waits for approval

**Solution**: This is expected if you have protection rules. Approve in the Actions tab.

### Issue: Environment not found

**Solution**: Ensure the environment name in the workflow matches exactly (`production`).

### Issue: Token not available in workflow

**Solution**: Verify the workflow job includes `environment: production`.

## Multiple Environments (Advanced)

You can create multiple environments for different purposes:

```yaml
# Development environment - more permissive
environment: development

# Staging environment - test changes
environment: staging

# Production environment - restricted
environment: production
```

Each environment can have:
- Different tokens with varying permissions
- Different protection rules
- Different deployment branch restrictions

## Migration from File-Based Secrets

If you were previously using file-based secrets:

1. Remove any `.secrets/` directories
2. Update workflows to use environment variables
3. Ensure `get_github_token()` prioritizes environment variables
4. Test thoroughly before removing old setup

## Benefits of This Approach

1. **No filesystem operations** - Secrets stay in GitHub
2. **Better audit trail** - See who accessed secrets when
3. **Environment isolation** - Dev can't access prod secrets
4. **Native GitHub feature** - No custom implementation needed
5. **Protection rules** - Additional security layer
