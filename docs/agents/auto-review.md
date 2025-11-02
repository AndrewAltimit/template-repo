# Auto Review Pipeline

The Auto Review pipeline allows AI agents to analyze and comment on GitHub issues and pull requests without making any code changes.

## Key Differences from Issue/PR Monitors

- **No Approval Required**: Reviews ALL open issues/PRs without needing `[COMMAND][AGENT]` keywords
- **No User Allowlist**: Works on all issues/PRs regardless of who created them
- **Read-Only**: Cannot make any code changes, only posts review comments
- **Batch Processing**: Can review multiple items in a single run

## Features

- **Multiple AI Agents**: Choose from Claude, Gemini, OpenCode, and Crush
- **Flexible Targeting**: Review issues, pull requests, or both
- **Review Depth Options**: Quick, standard, or thorough analysis
- **Comment Styles**: Consolidated, inline, or summary comments
- **Scheduled or Manual**: Run automatically on schedule or trigger manually

## Usage

### GitHub Actions Workflow

The workflow can be triggered manually from the Actions tab with the following options:

- **Agents**: Comma-separated list of agents (e.g., `claude,gemini`)
- **Target**: What to review (`issues`, `pull-requests`, or `both`)
- **Issue Numbers**: Specific issues to review (optional)
- **PR Numbers**: Specific PRs to review (optional)
- **Review Depth**: `quick`, `standard`, or `thorough`
- **Comment Style**: `consolidated`, `inline`, or `summary`

### Local Testing

Use the test script for local testing:

```bash
# Review all open issues and PRs with Claude and Gemini
./automation/ci-cd/test-auto-review.sh

# Review only PRs with OpenCode
./automation/ci-cd/test-auto-review.sh "opencode" "pull-requests"

# Thorough review with all agents
./automation/ci-cd/test-auto-review.sh "claude,gemini,opencode,crush" "both" "thorough"
```

## Configuration

The pipeline respects the following environment variables:

- `REVIEW_ONLY_MODE`: Always set to `true` to prevent file modifications
- `REVIEW_AGENTS`: Comma-separated list of agents to use
- `REVIEW_TARGET`: What to review (`issues`, `pull-requests`, `both`)
- `REVIEW_DEPTH`: Review depth (`quick`, `standard`, `thorough`)
- `COMMENT_STYLE`: How to post comments (`consolidated`, `inline`, `summary`)

## Security

- The pipeline runs in read-only mode and cannot modify files
- All agent access is controlled by the existing security framework
- Comments are clearly marked as automated reviews

## Agent Capabilities

Each agent brings different strengths to the review process:

- **Claude**: Comprehensive analysis and architectural insights
- **Gemini**: Technical accuracy and best practices
- **OpenCode**: Code quality and optimization suggestions
- **Crush**: Security and performance considerations
