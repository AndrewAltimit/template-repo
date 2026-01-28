# Code Review Processor

CLI tool for processing JSON responses from the AgentCore `/code-review` endpoint.

## Overview

This tool bridges the gap between AI-generated code reviews and GitHub actions. It takes the structured JSON output from the AgentCore code review endpoint and executes deterministic operations like posting comments, committing changes, and creating pull requests.

```
AgentCore                    code-review-processor           GitHub
┌─────────┐                  ┌────────────────────┐          ┌─────────┐
│ /code-  │  JSON response   │                    │  gh CLI  │         │
│ review  │ ─────────────► │  Parse & validate  │ ───────► │ Comment │
│ endpoint│                  │  Apply diffs       │          │ Commit  │
└─────────┘                  │  Create PR         │          │ PR      │
                             └────────────────────┘          └─────────┘
```

## Installation

```bash
# Build from source
cd tools/rust/code-review-processor
cargo build --release

# Binary location
./target/release/code-review-processor
```

## Usage

```bash
code-review-processor [OPTIONS] --input <FILE>

Options:
  -i, --input <FILE>           Input JSON file or '-' for stdin
  -r, --repository <REPO>      GitHub repository (owner/repo)
  -p, --post-comment           Post review as PR comment
  -n, --pr-number <N>          PR number for posting comment
  -c, --commit-changes         Apply file changes and commit
  -m, --commit-message <MSG>   Commit message [default: "Apply code review fixes"]
      --create-pr              Create a new PR with changes
  -b, --base-branch <BRANCH>   Base branch for new PR [default: main]
      --branch <BRANCH>        Branch name for new PR
      --dry-run                Print actions without executing
  -h, --help                   Print help
  -V, --version                Print version
```

## Examples

### Post Review as Comment

```bash
# From file
code-review-processor --input review.json --post-comment --pr-number 123 --repository owner/repo

# From stdin (piped from curl)
curl -s https://agentcore/code-review -d '...' | \
  code-review-processor --input - --post-comment --pr-number 123
```

### Apply Fixes and Commit

```bash
code-review-processor --input review.json \
  --commit-changes \
  --commit-message "fix: apply code review suggestions"
```

### Create PR with Fixes

```bash
code-review-processor --input review.json \
  --create-pr \
  --base-branch main \
  --branch code-review-fixes-$(date +%s)
```

### Combined Operations

```bash
# Post comment AND commit changes
code-review-processor --input review.json \
  --post-comment --pr-number 123 \
  --commit-changes

# Full workflow: comment, commit, and create PR
code-review-processor --input review.json \
  --post-comment --pr-number 123 \
  --commit-changes \
  --create-pr
```

### Dry Run

Preview what would happen without making changes:

```bash
code-review-processor --input review.json \
  --post-comment --pr-number 123 \
  --commit-changes \
  --dry-run
```

Output:
```
[DRY RUN] Would post comment to owner/repo PR #123
[DRY RUN] Would apply diff to src/main.rs
[DRY RUN] Would run: git add -A
[DRY RUN] Would run: git commit -m "Apply code review fixes"
```

## Input JSON Format

The tool accepts JSON matching the AgentCore code review response schema.

### Review Only

```json
{
  "review_markdown": "## Code Review\n\n### Issues Found\n...",
  "severity": "medium",
  "findings_count": 3
}
```

### Review with Fixes

```json
{
  "review_markdown": "## Code Review\n\n### Issues Found\n...",
  "severity": "high",
  "findings_count": 2,
  "file_changes": [
    {
      "path": "src/db.rs",
      "diff": "--- a/src/db.rs\n+++ b/src/db.rs\n@@ -1 +1 @@\n-bad\n+good",
      "original_sha": "abc123"
    }
  ],
  "pr_title": "fix(security): prevent SQL injection",
  "pr_description": "## Summary\nFixes vulnerability..."
}
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `review_markdown` | string | Yes | Review content in markdown |
| `severity` | string | Yes | `critical`, `high`, `medium`, `low`, `info` |
| `findings_count` | integer | Yes | Number of issues found |
| `file_changes` | array | No | List of file modifications |
| `file_changes[].path` | string | Yes | File path relative to repo root |
| `file_changes[].diff` | string | Yes | Unified diff format |
| `file_changes[].original_sha` | string | No | SHA of original content |
| `pr_title` | string | No | Suggested PR title |
| `pr_description` | string | No | Suggested PR description |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GITHUB_REPOSITORY` | Default repository if not specified via `--repository` |
| `GITHUB_TOKEN` / `GH_TOKEN` | GitHub token for `gh` CLI authentication |

## GitHub Actions Integration

Example workflow step:

```yaml
- name: Process code review
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    code-review-processor \
      --input review_response.json \
      --post-comment \
      --pr-number ${{ github.event.pull_request.number }} \
      --repository ${{ github.repository }}
```

## How It Works

### Posting Comments

Uses `gh pr comment` with `--body-file` to avoid shell escaping issues:

```bash
gh pr comment 123 --repo owner/repo --body-file /tmp/comment.md
```

### Applying Diffs

1. Writes diff to temp file
2. Tries `git apply --check` to verify
3. Falls back to `patch -p1` if git apply fails
4. Cleans up temp file

### Creating PRs

1. Creates new branch (auto-generated name if not specified)
2. Applies diffs and commits
3. Pushes to origin
4. Uses `gh pr create` with title and description from JSON

## Error Handling

- Invalid JSON: Exits with error and message
- Missing required fields: Context-aware error messages
- Git/patch failures: Detailed stderr output
- GitHub API errors: Full error response from `gh` CLI

## Testing

```bash
# Run tests
cargo test

# Run with verbose output
cargo test -- --nocapture
```

## Related

- [AgentCore Rust Runtime](../../../infra/aws/rust-runtime/README.md) - The `/code-review` endpoint
- [AgentCore Code Review Workflow](../../../.github/workflows/agentcore-code-review.yml) - GitHub Actions integration
