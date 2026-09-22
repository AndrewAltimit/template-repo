# Code Review Processor

CLI tool for processing JSON responses from the AgentCore `/code-review` endpoint.

## Overview

The AgentCore endpoint produces a structured review (markdown, severity, findings count, and optionally
proposed fixes as unified diffs). This tool performs the deterministic follow-up actions:

- post the review as a PR comment (`gh pr comment`)
- apply the proposed diffs and commit them (`git apply`, falling back to `patch -p1`)
- push the fixes to a new branch and open a PR (`gh pr create`)
- gate CI on review severity (`--fail-on-severity`)

```
AgentCore            code-review-processor                   GitHub / git
+-----------+  JSON  +-------------------------------+  gh   +-----------+
| /code-    | -----> | parse + validate response     | ----> | comment   |
| review    |        | normalize + safety-check diffs| git   | commit    |
| endpoint  |        | apply atomically, commit, PR  | ----> | branch/PR |
+-----------+        +-------------------------------+       +-----------+
```

Used by `.github/workflows/agentcore-code-review.yml`. Built in CI by `pr-validation.yml` and `main-ci.yml`
(released as `code-review-processor-linux-x64`).

## Installation

```bash
cd tools/rust/code-review-processor
cargo build --release
./target/release/code-review-processor --help
```

Requires `git` for fix application and `gh` (authenticated via `GH_TOKEN`/`GITHUB_TOKEN`) for comments and PRs.
`patch` is optional (used only as a fallback).

## Usage

```
code-review-processor [OPTIONS]

Options:
  -i, --input <INPUT>                    Path to JSON file from AgentCore (or '-' for stdin) [default: -]
      --post-comment                     Post review as a GitHub comment (requires --pr-number and a repository)
      --commit-changes                   Apply the proposed file changes and commit them on the current branch
      --create-pr                        Apply the proposed file changes on a new branch, push it, and open a PR
      --push                             Push the current branch to origin after --commit-changes
      --pr-number <PR_NUMBER>            PR number to comment on (for --post-comment)
      --repository <REPOSITORY>          Repository (owner/repo format) [env: GITHUB_REPOSITORY]
      --branch <BRANCH>                  Name of the branch --create-pr creates (default: code-review-fixes-<unix time>)
      --base-branch <BASE_BRANCH>        Base branch for PR [default: main]
      --commit-message <COMMIT_MESSAGE>  Commit message for changes [default: "Apply code review fixes"]
      --dry-run                          Dry run - print actions without executing (patches are still checked)
      --output-format <OUTPUT_FORMAT>    Output format for stdout [default: text] [possible values: text, json]
      --raw-comment                      Post the review markdown verbatim, without the metadata footer
      --fail-on-severity <LEVEL>         Exit with code 3 when the review severity is at or above this level
  -h, --help                             Print help
  -V, --version                          Print version
```

Without any action flag the tool only parses and validates the input (useful with `--output-format json` or
`--fail-on-severity`).

### Flag interactions

| Flags | Behavior |
|-------|----------|
| `--post-comment` | Needs `--pr-number` and `--repository`/`GITHUB_REPOSITORY`. Posted first, so the review is visible even if fixes fail. |
| `--commit-changes` | Applies all diffs and commits only the touched files on the current branch. No repository needed. |
| `--commit-changes --push` | Additionally pushes the current branch (`git push -u origin HEAD:refs/heads/<branch>`). |
| `--create-pr` | Creates `--branch` (or `code-review-fixes-<unix time>`) from HEAD, applies and commits the fixes there, pushes it, and opens a PR against `--base-branch`. Combining with `--commit-changes` still produces a single commit. |
| `--branch` without `--create-pr` | Ignored with a warning. |
| `--dry-run` | No comment, commit, push, or PR. Diffs are still normalized and checked with `git apply --check`, so a dry run fails if the fixes would not apply. |

If the review has no `file_changes`, `--commit-changes`/`--create-pr` are no-ops.

### Stdout, stderr, and exit codes

Logs always go to **stderr** (level via `RUST_LOG`, default `code_review_processor=info`). Stdout carries only
the result:

- `--output-format text` (default): the PR URL, if `--create-pr` created one; otherwise nothing.
- `--output-format json`: a summary object:

```json
{
  "dry_run": false,
  "severity": "critical",
  "findings_count": 2,
  "review_id": "rev-7f3a2c",
  "review_status": "completed",
  "comment_posted": true,
  "files_changed": ["src/db.rs", "README.md"],
  "apply_method": "git-apply",
  "commit_sha": "3f2c...",
  "made_changes": true,
  "branch": "code-review-fixes-1790000000",
  "pushed": true,
  "pr_number": 412,
  "pr_url": "https://github.com/owner/repo/pull/412",
  "severity_threshold": null,
  "threshold_exceeded": false
}
```

`apply_method` is one of `git-apply`, `git-apply-ignore-whitespace`, `patch`.

| Exit code | Meaning |
|-----------|---------|
| 0 | Success |
| 1 | Invalid input (unparseable JSON, security-denied or error response, unsafe diff) or a git/GitHub failure |
| 2 | Invalid command-line arguments |
| 3 | Severity at or above `--fail-on-severity` (all requested actions still ran) |

## Examples

```bash
# Post review as a comment
code-review-processor --input review.json --post-comment --pr-number 123 --repository owner/repo

# From stdin
curl -s "$AGENTCORE_ENDPOINT/code-review" -d @request.json | \
  code-review-processor --post-comment --pr-number 123

# Apply fixes, commit, and push the current branch
code-review-processor --input review.json --commit-changes --push \
  --commit-message "fix: apply code review suggestions"

# Open a PR with the fixes
code-review-processor --input review.json --create-pr --base-branch main --branch review-fixes-123

# Comment, then fail the job on high/critical findings
code-review-processor --input review.json --post-comment --pr-number 123 --fail-on-severity high

# Check that everything would work, and get a JSON summary
code-review-processor --input review.json --post-comment --pr-number 123 --commit-changes \
  --dry-run --output-format json
```

## Input JSON Format

Three shapes are accepted.

**1. Endpoint envelope** (what `POST /code-review` returns with HTTP 200):

```json
{
  "review_id": "rev-7f3a2c",
  "status": "completed",
  "result": {
    "type": "with_fixes",
    "review_markdown": "## Code Review\n...",
    "severity": "high",
    "findings_count": 2,
    "file_changes": [{"path": "src/db.rs", "diff": "--- a/src/db.rs\n+++ b/src/db.rs\n@@ ..."}],
    "pr_title": "fix(security): prevent SQL injection",
    "pr_description": "## Summary\n..."
  },
  "usage": {"input_tokens": 5120, "output_tokens": 870, "total_tokens": 5990},
  "validation_attempts": 1,
  "iterations": 4
}
```

`status: "failed"` means the agent never committed a validated result; the markdown is its raw output. The
comment then starts with a warning note.

**2. Flat review object** (the agent's committed JSON), i.e. the contents of `result` above without `type`.

**3. Legacy tagged object**: the flat object plus `"type": "review_only"` or `"with_fixes"`.

The 403 security-denied body (`{"denied": true, ...}`) and endpoint error bodies (`{"error": ..., "code": ...}`)
are recognized and reported as errors (exit 1).

### Field Reference

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `review_markdown` | string | Yes | Review content in markdown |
| `severity` | string | No (default `info`) | `critical`, `high`, `medium`, `low`, `info`; case-insensitive; synonyms such as `blocker`, `major`, `warning`, `minor`, `none` are mapped; unknown values become `info` with a warning |
| `findings_count` | integer | No (default 0) | Integral floats and numeric strings are accepted; negative values are rejected |
| `file_changes` | array or null | No | Exact duplicates are dropped |
| `file_changes[].path` | string | Yes | Repository-relative path |
| `file_changes[].diff` | string | Yes | Unified diff for that path |
| `file_changes[].original_sha` | string | No | Git blob SHA (may be abbreviated); a mismatch with the working tree is logged as a warning |
| `pr_title` | string | No | First non-empty line used, truncated to 256 characters |
| `pr_description` | string | No | Defaults to the review markdown |

Input may have a UTF-8 BOM, or be wrapped in a markdown code fence / surrounding prose. Inputs over 64 MiB are
rejected.

## How It Works

### Comments

The comment body is the review markdown followed by a footer (`Severity`, `Findings`, number of proposed fixes,
review ID) and a hidden `<!-- code-review-processor -->` marker. `--raw-comment` posts the markdown verbatim.
Bodies are truncated to GitHub's 65,536-character limit at a line boundary, closing any open code fence, with a
note stating how much was omitted. Bodies are passed to `gh` on stdin (`--body-file -`); no temp files are used.

### Applying diffs

Model-generated diffs are normalized before anything is applied:

- CRLF converted to LF; a surrounding code fence and surrounding prose removed
- missing `---`/`+++` headers synthesized from `path`; headers rewritten to `a/<path>`/`b/<path>`
  (`/dev/null` kept for file creation/deletion); `diff --git`/`index` lines dropped
- hunk line counts recounted from the hunk body (models often get them wrong)
- blank context lines whose leading space was stripped are restored

Safety checks reject a change (before anything is modified) when its path is absolute, contains `..`, or points
into `.git`, or when its diff headers name a different file than `path`.

All diffs are then combined into one patch and applied atomically: `git apply --check` then `git apply`; if
that fails, the same with `--ignore-whitespace`; then `patch -p1 --forward` (dry-run first) if installed. Either
every file changes or none does.

Only the files named in `file_changes` are staged and committed; unrelated untracked or staged files are left
alone.

## Testing

```bash
cargo test
```

Integration tests in `tests/cli.rs` run the binary against fixtures in `tests/fixtures/` inside throwaway git
repositories (no network or GitHub access needed).

## Related

- [AgentCore Rust Runtime](../../../infra/aws/rust-runtime/README.md) - The `/code-review` endpoint
- [AgentCore Code Review Workflow](../../../.github/workflows/agentcore-code-review.yml) - GitHub Actions integration
