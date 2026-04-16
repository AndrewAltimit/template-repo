# Agent Council Setup Guide

**Setting up multi-agent PR reviews and auto-fix on a Windows self-hosted GitHub Actions runner**

This guide walks you through replicating the Agent Council -- a multi-profile AI review pipeline that reviews every PR from multiple perspectives (security, quality, general) and optionally auto-fixes issues. It uses two Rust CLI tools from the [template-repo](https://github.com/AndrewAltimit/template-repo) project:

- **`github-agents`** -- orchestrates PR reviews (selects agent, builds prompt, posts comments)
- **`automation-cli`** -- handles review-response and CI-failure auto-fix loops

The agents currently supported are **Claude Code** (Anthropic CLI) and **OpenRouter** (HTTP API to any model, e.g. Qwen). You can run both or just one.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [Step 1: Build the CLI Tools](#step-1-build-the-cli-tools)
4. [Step 2: Install CLI Tools on the Runner](#step-2-install-cli-tools-on-the-runner)
5. [Step 3: Install Claude Code on the Runner](#step-3-install-claude-code-on-the-runner)
6. [Step 4: Configure Repository Secrets](#step-4-configure-repository-secrets)
7. [Step 5: Add Configuration Files to Your Repo](#step-5-add-configuration-files-to-your-repo)
8. [Step 6: Add GitHub Actions Workflows](#step-6-add-github-actions-workflows)
9. [Step 7: Add Composite Actions](#step-7-add-composite-actions)
10. [How It All Works Together](#how-it-all-works-together)
11. [Customization](#customization)
12. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
PR opened/updated
    |
    v
[GitHub Actions Workflow]
    |
    +---> [claude-security-review job]  --> github-agents pr-review <PR> --profile security
    |         uses Claude Code CLI              |
    |                                           v
    +---> [claude-quality-review job]   --> github-agents pr-review <PR> --profile quality
    |         uses Claude Code CLI              |
    |                                           v
    +---> [openrouter-review job]       --> github-agents pr-review <PR> --profile openrouter-general
    |         uses OpenRouter HTTP API          |
    |                                           v
    +---> [agent-review-response job]   --> automation-cli review respond <PR> <BRANCH> <ITER> <MAX>
    |         uses Claude Code CLI to fix       |
    |         issues found by reviewers         v
    +---> [agent-failure-handler job]   --> automation-cli review failure <PR> <BRANCH> <ITER> <MAX> "format,lint,test"
              uses Claude Code CLI to fix
              CI failures automatically
```

Reviews are **advisory** (non-blocking). CI is **blocking**. The auto-fix agent commits directly to the PR branch.

---

## Prerequisites

- **Windows self-hosted GitHub Actions runner** registered to your repo/org
- **Rust toolchain** installed on the runner (for building the CLI tools)
  - Install via [rustup](https://rustup.rs/) -- works on Windows
- **Node.js 18+** on the runner (Claude Code CLI is an npm package)
- **GitHub CLI (`gh`)** installed on the runner ([install guide](https://cli.github.com/))
- **Claude Code subscription** (Max or Pro plan) -- for the Claude-based reviews
- **OpenRouter API key** (free tier available) -- for the OpenRouter-based reviews
- **Git** available on the runner PATH

---

## Step 1: Build the CLI Tools

You have two options: build on the runner itself, or cross-compile and copy the binaries.

### Option A: Build directly on the Windows runner (recommended)

Create a setup script that clones template-repo and builds the two binaries. Save this as `setup-agent-tools.ps1` on your runner:

```powershell
# setup-agent-tools.ps1 -- Run once on your self-hosted runner
$ErrorActionPreference = "Stop"

$TOOLS_DIR = "$env:USERPROFILE\.agent-tools"
$BIN_DIR = "$env:USERPROFILE\.local\bin"

# Create directories
New-Item -ItemType Directory -Force -Path $TOOLS_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $BIN_DIR | Out-Null

# Clone template-repo (sparse checkout -- only the tools we need)
Set-Location $TOOLS_DIR
if (Test-Path "template-repo") { Remove-Item -Recurse -Force "template-repo" }

git clone --depth 1 --filter=blob:none --sparse `
    https://github.com/AndrewAltimit/template-repo.git
Set-Location template-repo
git sparse-checkout set tools/rust/github-agents-cli tools/rust/automation-cli tools/rust/wrapper-common

# Build github-agents CLI
Write-Host "Building github-agents..."
Set-Location tools/rust/github-agents-cli
cargo build --release
Copy-Item "target\release\github-agents.exe" "$BIN_DIR\github-agents.exe" -Force

# Build automation-cli
Write-Host "Building automation-cli..."
Set-Location ..\automation-cli
cargo build --release
Copy-Item "target\release\automation-cli.exe" "$BIN_DIR\automation-cli.exe" -Force

Write-Host "Done! Binaries installed to $BIN_DIR"
Write-Host ""
Write-Host "Make sure $BIN_DIR is in your system PATH."
```

### Option B: Build script for bash (WSL or Git Bash)

```bash
#!/bin/bash
# setup-agent-tools.sh -- Run once on your self-hosted runner
set -e

TOOLS_DIR="$HOME/.agent-tools"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$TOOLS_DIR" "$BIN_DIR"

cd "$TOOLS_DIR"
rm -rf template-repo

# Sparse clone -- only the Rust tools
git clone --depth 1 --filter=blob:none --sparse \
    https://github.com/AndrewAltimit/template-repo.git
cd template-repo
git sparse-checkout set tools/rust/github-agents-cli tools/rust/automation-cli tools/rust/wrapper-common

# Build github-agents
echo "Building github-agents..."
cd tools/rust/github-agents-cli
cargo build --release
cp target/release/github-agents "$BIN_DIR/github-agents"

# Build automation-cli
echo "Building automation-cli..."
cd ../automation-cli
cargo build --release
cp target/release/automation-cli "$BIN_DIR/automation-cli"

echo "Done! Binaries installed to $BIN_DIR"
echo "Make sure $BIN_DIR is in your PATH."
```

### Verify installation

```bash
github-agents --help
automation-cli --help
```

You should see the help text for both tools. If not, ensure `~/.local/bin` (or `%USERPROFILE%\.local\bin` on Windows) is in your PATH.

---

## Step 2: Install CLI Tools on the Runner

The runner's PATH must include the directory where you installed the binaries. For a Windows runner service:

1. Add `%USERPROFILE%\.local\bin` to the **system** PATH environment variable
2. **Restart the runner service** after changing PATH

For a runner running as a user process, adding to the user PATH and restarting is sufficient.

Verify from the runner's context:

```bash
# In a GitHub Actions step:
- name: Verify agent tools
  run: |
    github-agents --help || echo "github-agents not found"
    automation-cli --help || echo "automation-cli not found"
```

---

## Step 3: Install Claude Code on the Runner

Claude Code is the AI agent that performs the actual code review and auto-fix work.

```bash
npm install -g @anthropic-ai/claude-code
```

Then authenticate **on the runner** (this is a one-time interactive step):

```bash
claude --login
```

This stores credentials at `~/.claude.json`. The runner process must have access to this file.

**Important:** Claude Code needs `--print` and `--dangerously-skip-permissions` flags for non-interactive CI/CD use. These are passed automatically by `github-agents` and `automation-cli`.

---

## Step 4: Configure Repository Secrets

In your GitHub repo, go to **Settings > Secrets and variables > Actions** and add:

| Secret | Required For | Description |
|--------|-------------|-------------|
| `AGENT_TOKEN` | Auto-fix agent | A GitHub PAT with `contents: write` and `pull-requests: write` on this repo. Used by the fix agent to push commits. |
| `OPENROUTER_API_KEY` | OpenRouter reviews | Your OpenRouter API key from [openrouter.ai](https://openrouter.ai) |

**Note:** `GITHUB_TOKEN` is automatically provided by Actions and used for read-only operations (posting review comments). `AGENT_TOKEN` is a separate PAT with write permissions specifically for the auto-fix agent to push commits.

---

## Step 5: Add Configuration Files to Your Repo

### 5a. `.agents.yaml` (root of your repo)

This is the master configuration for all agents. Adapt to your needs:

```yaml
# .agents.yaml -- Multi-Agent System Configuration
#
# All agents run in AUTONOMOUS MODE for CI/CD automation.
# Interactive prompts are disabled.

enabled_agents:
  - claude       # Anthropic Claude Code CLI (must be installed on runner)
  - openrouter   # OpenRouter API (needs OPENROUTER_API_KEY secret)

# Agent priorities for different task types
agent_priorities:
  pr_reviews:
    - claude       # Primary reviewer (security + quality profiles)
    - openrouter   # Secondary reviewer (general profile)
  code_fixes:
    - claude       # Most capable for automated fixes

# Security settings
security:
  # Users who can trigger agent actions via comments (e.g., [CONTINUE])
  # CRITICAL: Only add trusted human users
  agent_admins:
    - YOUR_GITHUB_USERNAME    # <-- Change this

  # Trusted comment sources (context provided to AI, not action triggers)
  trusted_sources:
    - YOUR_GITHUB_USERNAME    # <-- Change this
    - github-actions[bot]
    - dependabot[bot]

  autonomous_mode: true
  require_sandbox: true
  max_prompt_length: 10000
  temp_file_cleanup: true
  subprocess_timeout: 600    # 10 minutes max per agent call
  memory_limit_mb: 500

# Rate limiting
rate_limits:
  requests_per_minute: 10
  requests_per_hour: 100
  claude:
    requests_per_minute: 20

# OpenRouter settings
openrouter:
  default_model: qwen/qwen3.6-plus
  fallback_models:
    - deepseek/deepseek-coder-v2-instruct

# PR Review settings
pr_review:
  default_agent: claude
  max_words: 500
  condensation_threshold: 600
  incremental_enabled: true
  include_comment_context: true
  verify_claims: true

# Auto-fix settings
automation:
  inline_feedback_loop: true
  max_auto_fix_iterations: 5
  autoformat_first: true
  auto_fix_categories:
    - formatting
    - linting
    - type_errors
    - unused_imports
  skip_labels:
    - no-auto-fix
    - needs-human-review

# Non-interactive flags per agent
advanced:
  debug_mode: false
  temp_directory: /tmp/agents
  max_retries: 2
  retry_delay_seconds: 5
  isolate_environment: true
  non_interactive_flags:
    claude: ["--print", "--dangerously-skip-permissions"]
```

### 5b. `review-profiles.yaml` (root of your repo)

Defines the different reviewer "perspectives" in the council:

```yaml
# review-profiles.yaml -- Reviewer Role Definitions
#
# Each profile is a different lens through which a PR is reviewed.
# Profiles are referenced by name via: github-agents pr-review <PR> --profile <name>

profiles:
  # Security-focused reviewer (Claude)
  security:
    display_name: "Security & Correctness Review"
    agent: claude
    model: sonnet
    focus: "Security vulnerabilities, correctness bugs, data safety"
    instructions: |
      You are a SECURITY-FOCUSED code reviewer. Prioritize these categories:

      **Primary Focus:**
      - Injection vulnerabilities (SQL, command, XSS, path traversal)
      - Authentication and authorization flaws
      - Secrets/credentials in code or config
      - Unsafe deserialization, SSRF, open redirects
      - Race conditions and TOCTOU bugs
      - Integer overflow/underflow, buffer issues
      - Cryptographic misuse (weak algorithms, hardcoded keys, bad RNG)
      - Missing input validation at trust boundaries

      **Secondary Focus:**
      - Logic errors that produce incorrect results
      - Off-by-one errors, boundary conditions
      - Resource leaks (file handles, connections, memory)
      - Error handling that swallows failures silently

      **Do NOT report:** style issues, naming preferences, missing docs, test coverage gaps,
      or anything already caught by linters/formatters.

  # Architecture-focused reviewer (Claude)
  quality:
    display_name: "Architecture & Quality Review"
    agent: claude
    model: sonnet
    focus: "Architecture, API design, maintainability, performance"
    instructions: |
      You are an ARCHITECTURE-FOCUSED code reviewer. Prioritize these categories:

      **Primary Focus:**
      - API design issues (breaking changes, inconsistent interfaces)
      - Architectural violations (wrong layer, circular dependencies)
      - Performance regressions (N+1 queries, unnecessary allocations, blocking in async)
      - Concurrency issues (deadlocks, data races, missing synchronization)
      - Error handling strategy (are errors propagated correctly?)
      - Resource management (connection pools, file handles, cleanup)

      **Secondary Focus:**
      - Code duplication that should be abstracted
      - Overly complex logic that could be simplified
      - Missing or incorrect type constraints
      - Backwards compatibility concerns

      **Do NOT report:** security issues (another reviewer handles those), style issues,
      naming preferences, missing docs, or anything caught by linters/formatters.

  # General reviewer (OpenRouter / Qwen)
  openrouter-general:
    display_name: "General Review"
    agent: openrouter
    model: "qwen/qwen3.6-plus"
    focus: "General code quality, logic errors, edge cases"
    instructions: |
      You are a GENERAL code reviewer providing a broad perspective. Focus on:

      **Primary Focus:**
      - Logic errors and incorrect behavior
      - Edge cases and boundary conditions not handled
      - Missing error handling for likely failure modes
      - Incorrect assumptions in comments vs actual code behavior
      - Copy-paste errors or incomplete refactoring

      **Secondary Focus:**
      - Unclear or misleading variable/function names
      - Dead code or unreachable branches
      - Inconsistency with patterns used elsewhere in the codebase
      - Test gaps for critical paths

      **Do NOT report:** style issues caught by formatters, security issues (another
      reviewer handles those), or architectural concerns (another reviewer handles those).
```

---

## Step 6: Add GitHub Actions Workflows

### 6a. Main PR validation workflow

Create `.github/workflows/pr-validation.yml`:

```yaml
---
name: Pull Request Validation

on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    branches: [main]
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write
  issues: write

concurrency:
  group: pr-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: true

jobs:
  # Block fork PRs from self-hosted runners (security)
  fork-guard:
    name: Fork PR Guard
    runs-on: ubuntu-latest
    if: >-
      github.event_name != 'pull_request' ||
      github.event.pull_request.head.repo.full_name == github.repository
    steps:
      - run: echo "Not a fork PR - proceeding"

  # -------------------------------------------------------------------------
  # YOUR CI JOBS GO HERE
  # -------------------------------------------------------------------------
  # Add your own CI job(s) -- build, test, lint, etc.
  # The example below is a placeholder. Replace with your actual CI.
  ci:
    name: CI
    needs: fork-guard
    runs-on: self-hosted
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          ref: ${{ github.head_ref }}

      # -- Replace this with your actual build/test/lint steps --
      - name: Build and test
        run: echo "Run your CI here"

  # -------------------------------------------------------------------------
  # AGENT COUNCIL -- Parallel AI Reviews
  # -------------------------------------------------------------------------

  # Claude Security Review
  claude-security-review:
    name: Claude Security Review
    needs: fork-guard
    if: >-
      github.event_name == 'pull_request' &&
      !github.event.pull_request.draft
    runs-on: self-hosted
    timeout-minutes: 30
    outputs:
      review_status: ${{ steps.review-action.outputs.review_status }}
      review_artifact_name: ${{ steps.review-action.outputs.review_artifact_name }}
    env:
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          clean: true
          ref: ${{ github.head_ref }}

      - name: Run Claude security review
        id: review-action
        uses: ./.github/actions/claude-review
        with:
          pr_number: ${{ github.event.pull_request.number }}
          profile: 'security'

  # Claude Quality Review
  claude-quality-review:
    name: Claude Quality Review
    needs: fork-guard
    if: >-
      github.event_name == 'pull_request' &&
      !github.event.pull_request.draft
    runs-on: self-hosted
    timeout-minutes: 30
    outputs:
      review_status: ${{ steps.review-action.outputs.review_status }}
      review_artifact_name: ${{ steps.review-action.outputs.review_artifact_name }}
    env:
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          clean: true
          ref: ${{ github.head_ref }}

      - name: Run Claude quality review
        id: review-action
        uses: ./.github/actions/claude-review
        with:
          pr_number: ${{ github.event.pull_request.number }}
          profile: 'quality'

  # OpenRouter General Review
  openrouter-review:
    name: OpenRouter General Review
    needs: fork-guard
    if: >-
      github.event_name == 'pull_request' &&
      !github.event.pull_request.draft
    runs-on: self-hosted
    timeout-minutes: 20
    continue-on-error: true
    outputs:
      review_status: ${{ steps.review-action.outputs.review_status }}
      review_artifact_name: ${{ steps.review-action.outputs.review_artifact_name }}
    env:
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          clean: true
          ref: ${{ github.head_ref }}

      - name: Run OpenRouter review
        id: review-action
        uses: ./.github/actions/openrouter-review
        with:
          pr_number: ${{ github.event.pull_request.number }}
          profile: 'openrouter-general'

  # -------------------------------------------------------------------------
  # AUTO-FIX AGENT -- Responds to review feedback
  # -------------------------------------------------------------------------
  agent-review-response:
    name: Agent Review Response
    needs: [ci, claude-security-review, claude-quality-review, openrouter-review]
    if: |
      always() &&
      !cancelled() &&
      github.event_name == 'pull_request' &&
      !github.event.pull_request.draft &&
      !contains(github.event.pull_request.labels.*.name, 'no-auto-fix')
    runs-on: self-hosted
    timeout-minutes: 30
    env:
      PR_NUMBER: ${{ github.event.pull_request.number }}
      GITHUB_TOKEN: ${{ secrets.AGENT_TOKEN }}
      GITHUB_REPOSITORY: ${{ github.repository }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          clean: false
          token: ${{ secrets.AGENT_TOKEN }}
          ref: ${{ github.head_ref }}

      - name: Clean working directory
        run: |
          git checkout -- . 2>/dev/null || true
          git clean -fd 2>/dev/null || true

      - name: Check iteration count
        id: iteration
        uses: ./.github/actions/agent-iteration-check
        with:
          pr_number: ${{ github.event.pull_request.number }}
          max_iterations: '5'
          agent_type: 'review-fix'
          github_token: ${{ secrets.GITHUB_TOKEN }}

      - name: Skip if max iterations reached
        if: steps.iteration.outputs.exceeded_max == 'true'
        run: |
          echo "Max iterations reached. Manual intervention required."
          echo "made_changes=false" >> $GITHUB_OUTPUT
          exit 0

      - name: Download review artifacts
        if: steps.iteration.outputs.should_skip != 'true'
        uses: actions/download-artifact@v4
        continue-on-error: true
        with:
          pattern: '*-review-${{ github.run_id }}-${{ github.run_attempt }}'
          merge-multiple: true
          path: .

      - name: Run agent review response
        id: agent-fix
        if: steps.iteration.outputs.should_skip != 'true'
        env:
          CLAUDE_SECURITY_REVIEW_PATH: claude-security-review.md
          CLAUDE_QUALITY_REVIEW_PATH: claude-quality-review.md
          OPENROUTER_REVIEW_PATH: openrouter-review.md
          BRANCH_NAME: ${{ github.head_ref }}
          ITERATION_COUNT: ${{ steps.iteration.outputs.iteration_count }}
        run: |
          if ! command -v automation-cli &>/dev/null; then
            echo "::warning::automation-cli not found on PATH - skipping review response"
            echo "made_changes=false" >> $GITHUB_OUTPUT
            exit 0
          fi

          automation-cli review respond \
            "$PR_NUMBER" \
            "$BRANCH_NAME" \
            "$ITERATION_COUNT" \
            "5"

  # -------------------------------------------------------------------------
  # FAILURE HANDLER -- Auto-fix CI failures
  # -------------------------------------------------------------------------
  agent-failure-handler:
    name: Agent Failure Handler
    needs: [ci, claude-security-review, claude-quality-review, openrouter-review, agent-review-response]
    if: |
      failure() &&
      github.event_name == 'pull_request' &&
      !github.event.pull_request.draft &&
      !contains(github.event.pull_request.labels.*.name, 'no-auto-fix') &&
      needs.ci.result == 'failure'
    runs-on: self-hosted
    timeout-minutes: 30
    env:
      PR_NUMBER: ${{ github.event.pull_request.number }}
      GITHUB_TOKEN: ${{ secrets.AGENT_TOKEN }}
      GITHUB_REPOSITORY: ${{ github.repository }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
          clean: false
          token: ${{ secrets.AGENT_TOKEN }}
          ref: ${{ github.head_ref }}

      - name: Clean working directory
        run: |
          git checkout -- . 2>/dev/null || true
          git clean -fd 2>/dev/null || true

      - name: Check iteration count
        id: iteration
        uses: ./.github/actions/agent-iteration-check
        with:
          pr_number: ${{ github.event.pull_request.number }}
          max_iterations: '5'
          agent_type: 'failure-fix'
          github_token: ${{ secrets.GITHUB_TOKEN }}

      - name: Skip if max iterations reached
        if: steps.iteration.outputs.exceeded_max == 'true'
        run: |
          echo "Max iterations reached. Manual intervention required."
          exit 0

      - name: Run agent failure handler
        id: agent-fix
        if: steps.iteration.outputs.exceeded_max != 'true'
        env:
          BRANCH_NAME: ${{ github.head_ref }}
          ITERATION_COUNT: ${{ steps.iteration.outputs.iteration_count }}
        run: |
          if ! command -v automation-cli &>/dev/null; then
            echo "::warning::automation-cli not found on PATH - skipping failure handler"
            echo "made_changes=false" >> $GITHUB_OUTPUT
            exit 0
          fi

          automation-cli review failure \
            "$PR_NUMBER" \
            "$BRANCH_NAME" \
            "$ITERATION_COUNT" \
            "5" \
            "format,lint,test"

  # -------------------------------------------------------------------------
  # STATUS SUMMARY
  # -------------------------------------------------------------------------
  pr-status:
    name: PR Status Summary
    needs: [ci, claude-security-review, claude-quality-review, openrouter-review, agent-review-response, agent-failure-handler]
    if: always()
    runs-on: self-hosted
    steps:
      - name: Generate status summary
        run: |
          echo "## PR Validation Summary" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "| Check | Status |" >> $GITHUB_STEP_SUMMARY
          echo "|-------|--------|" >> $GITHUB_STEP_SUMMARY
          echo "| CI | ${{ needs.ci.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Claude Security Review | ${{ needs.claude-security-review.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Claude Quality Review | ${{ needs.claude-quality-review.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| OpenRouter Review | ${{ needs.openrouter-review.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Review Response | ${{ needs.agent-review-response.result }} |" >> $GITHUB_STEP_SUMMARY
          echo "| Failure Handler | ${{ needs.agent-failure-handler.result }} |" >> $GITHUB_STEP_SUMMARY

          if [[ "${{ needs.ci.result }}" == "failure" ]]; then
            echo "" >> $GITHUB_STEP_SUMMARY
            echo "CI failed - review the logs" >> $GITHUB_STEP_SUMMARY
            exit 1
          fi
```

---

## Step 7: Add Composite Actions

These are reusable action definitions that the workflow references.

### 7a. `.github/actions/claude-review/action.yml`

```yaml
name: 'Claude Code AI Review'
description: 'Run Claude Code review on a PR using a configurable review profile'

inputs:
  pr_number:
    description: 'PR number to review'
    required: true
  profile:
    description: 'Review profile from review-profiles.yaml (e.g., security, quality)'
    required: true

outputs:
  review_status:
    description: 'Status: success, failure, rate_limited, unavailable, skipped'
    value: ${{ steps.review.outputs.status }}
  is_agent_commit:
    description: 'Whether the last commit was by an agent'
    value: ${{ steps.check-agent.outputs.is_agent_commit }}
  review_artifact_name:
    description: 'Name of the uploaded review artifact'
    value: claude-${{ inputs.profile }}-review-${{ github.run_id }}-${{ github.run_attempt }}

runs:
  using: 'composite'
  steps:
    - name: Check if agent commit
      id: check-agent
      shell: bash
      run: |
        LAST_AUTHOR=$(git log -1 --format='%an')
        IS_AGENT="false"
        for name in "AI Review Agent" "AI Pipeline Agent" "AI Agent Bot"; do
          if [[ "$LAST_AUTHOR" == "$name" ]]; then IS_AGENT="true"; fi
        done
        echo "is_agent_commit=$IS_AGENT" >> $GITHUB_OUTPUT

    - name: Run Claude Code Review
      id: review
      shell: bash
      env:
        PR_NUMBER: ${{ inputs.pr_number }}
        REVIEW_PROFILE: ${{ inputs.profile }}
      run: |
        echo "Starting Claude Code PR Review (profile: $REVIEW_PROFILE)..."

        if ! command -v github-agents &>/dev/null; then
          echo "::warning::github-agents not found on PATH - skipping Claude review"
          echo "status=skipped" >> $GITHUB_OUTPUT
          exit 0
        fi

        set +e
        OUTPUT=$(github-agents pr-review "$PR_NUMBER" --profile "$REVIEW_PROFILE" 2>&1)
        EXIT_CODE=$?
        set -e

        echo "$OUTPUT"
        echo "$OUTPUT" > claude-${REVIEW_PROFILE}-review.md

        if [ $EXIT_CODE -ne 0 ]; then
          if grep -qiE '429|rate.?limit|quota|usage.?limit|spending.?limit' <<< "$OUTPUT"; then
            echo "::warning::Claude API rate limit hit - skipping"
            echo "status=rate_limited" >> $GITHUB_OUTPUT
            exit 0
          elif grep -qiE '503|502|service.?unavailable|ECONNREFUSED|ETIMEDOUT' <<< "$OUTPUT"; then
            echo "::warning::Claude API unavailable - skipping"
            echo "status=unavailable" >> $GITHUB_OUTPUT
            exit 0
          else
            echo "status=failure" >> $GITHUB_OUTPUT
            exit $EXIT_CODE
          fi
        fi

        echo "status=success" >> $GITHUB_OUTPUT

    - name: Post unavailability notice
      if: steps.review.outputs.status == 'unavailable'
      shell: bash
      env:
        PR_NUMBER: ${{ inputs.pr_number }}
        REVIEW_PROFILE: ${{ inputs.profile }}
      run: |
        cat > /tmp/unavailable-notice.md <<'EOF'
        ## Claude AI Code Review

        **Warning:** Claude API was unavailable during this run.
        Review skipped -- will run on next push.

        ---
        Generated by AI review pipeline.
        EOF
        sed -i 's/^        //' /tmp/unavailable-notice.md
        gh pr comment "$PR_NUMBER" --body-file /tmp/unavailable-notice.md || true

    - name: Upload review artifact
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: claude-${{ inputs.profile }}-review-${{ github.run_id }}-${{ github.run_attempt }}
        path: claude-${{ inputs.profile }}-review.md
        retention-days: 7
        if-no-files-found: ignore

    - name: Clean up
      if: always()
      shell: bash
      run: |
        git checkout -- . 2>/dev/null || true
        git clean -fd 2>/dev/null || true
```

### 7b. `.github/actions/openrouter-review/action.yml`

```yaml
name: 'OpenRouter AI Code Review'
description: 'Run OpenRouter API-based code review on a PR'

inputs:
  pr_number:
    description: 'PR number to review'
    required: true
  profile:
    description: 'Review profile from review-profiles.yaml'
    required: false
    default: 'openrouter-general'

outputs:
  review_status:
    description: 'Status: success, failure, rate_limited, unavailable, skipped'
    value: ${{ steps.review.outputs.status }}
  is_agent_commit:
    description: 'Whether the last commit was by an agent'
    value: ${{ steps.check-agent.outputs.is_agent_commit }}
  review_artifact_name:
    description: 'Name of the uploaded review artifact'
    value: openrouter-review-${{ github.run_id }}-${{ github.run_attempt }}

runs:
  using: 'composite'
  steps:
    - name: Check if agent commit
      id: check-agent
      shell: bash
      run: |
        LAST_AUTHOR=$(git log -1 --format='%an')
        IS_AGENT="false"
        for name in "AI Review Agent" "AI Pipeline Agent" "AI Agent Bot"; do
          if [[ "$LAST_AUTHOR" == "$name" ]]; then IS_AGENT="true"; fi
        done
        echo "is_agent_commit=$IS_AGENT" >> $GITHUB_OUTPUT

    - name: Verify API key
      shell: bash
      run: |
        if [ -z "${OPENROUTER_API_KEY:-}" ]; then
          echo "::error::OPENROUTER_API_KEY is not set"
          exit 1
        fi

    - name: Run OpenRouter Code Review
      id: review
      shell: bash
      env:
        PR_NUMBER: ${{ inputs.pr_number }}
        REVIEW_PROFILE: ${{ inputs.profile }}
      run: |
        echo "Starting OpenRouter PR Review (profile: $REVIEW_PROFILE)..."

        if ! command -v github-agents &>/dev/null; then
          echo "::warning::github-agents not found on PATH - skipping"
          echo "status=skipped" >> $GITHUB_OUTPUT
          exit 0
        fi

        set +e
        OUTPUT=$(github-agents pr-review "$PR_NUMBER" --profile "$REVIEW_PROFILE" 2>&1)
        EXIT_CODE=$?
        set -e

        echo "$OUTPUT"
        echo "$OUTPUT" > openrouter-review.md

        if [ $EXIT_CODE -ne 0 ]; then
          if grep -qiE '429|rate.?limit|quota|usage.?limit' <<< "$OUTPUT"; then
            echo "::warning::OpenRouter rate limit hit - skipping"
            echo "status=rate_limited" >> $GITHUB_OUTPUT
            exit 0
          elif grep -qiE '503|502|service.?unavailable|ECONNREFUSED|ETIMEDOUT' <<< "$OUTPUT"; then
            echo "::warning::OpenRouter unavailable - skipping"
            echo "status=unavailable" >> $GITHUB_OUTPUT
            exit 0
          else
            echo "status=failure" >> $GITHUB_OUTPUT
            exit $EXIT_CODE
          fi
        fi

        echo "status=success" >> $GITHUB_OUTPUT

    - name: Upload review artifact
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: openrouter-review-${{ github.run_id }}-${{ github.run_attempt }}
        path: openrouter-review.md
        retention-days: 7
        if-no-files-found: ignore

    - name: Clean up
      if: always()
      shell: bash
      run: |
        git checkout -- . 2>/dev/null || true
        git clean -fd 2>/dev/null || true
```

### 7c. `.github/actions/agent-iteration-check/action.yml`

This tracks how many times the auto-fix agent has run, preventing infinite loops:

```yaml
name: 'Agent Iteration Check'
description: 'Track agent auto-fix iterations via PR comments to prevent infinite loops'

inputs:
  pr_number:
    description: 'PR number'
    required: true
  max_iterations:
    description: 'Maximum allowed iterations before stopping'
    required: false
    default: '5'
  agent_type:
    description: 'Agent type to track (review-fix or failure-fix)'
    required: true
  github_token:
    description: 'GitHub token for API operations'
    required: true

outputs:
  iteration_count:
    description: 'Current iteration count'
    value: ${{ steps.check.outputs.iteration_count }}
  effective_max:
    description: 'Effective max after [CONTINUE] multipliers'
    value: ${{ steps.check.outputs.effective_max }}
  continue_count:
    description: 'Number of [CONTINUE] comments from admins'
    value: ${{ steps.check.outputs.continue_count }}
  should_skip:
    description: 'Whether to skip this run'
    value: ${{ steps.check.outputs.should_skip }}
  exceeded_max:
    description: 'Whether max iterations have been exceeded'
    value: ${{ steps.check.outputs.exceeded_max }}

runs:
  using: 'composite'
  steps:
    - name: Check iteration count
      id: check
      shell: bash
      env:
        GH_TOKEN: ${{ inputs.github_token }}
        PR_NUMBER: ${{ inputs.pr_number }}
        MAX_ITERATIONS: ${{ inputs.max_iterations }}
        AGENT_TYPE: ${{ inputs.agent_type }}
      run: |
        echo "=== Agent Iteration Check ==="
        echo "PR: $PR_NUMBER | Max: $MAX_ITERATIONS | Type: $AGENT_TYPE"

        # Try github-agents CLI first (faster, more accurate)
        if command -v github-agents &>/dev/null; then
          RESULT=$(github-agents iteration-check \
            --pr "$PR_NUMBER" \
            --agent-type "$AGENT_TYPE" \
            --max-iterations "$MAX_ITERATIONS" \
            --format json 2>/dev/null || echo "")

          if [ -n "$RESULT" ] && echo "$RESULT" | jq -e . >/dev/null 2>&1; then
            echo "iteration_count=$(echo "$RESULT" | jq -r '.iteration_count')" >> $GITHUB_OUTPUT
            echo "effective_max=$(echo "$RESULT" | jq -r '.effective_max')" >> $GITHUB_OUTPUT
            echo "continue_count=$(echo "$RESULT" | jq -r '.continue_count')" >> $GITHUB_OUTPUT
            echo "exceeded_max=$(echo "$RESULT" | jq -r '.exceeded_max')" >> $GITHUB_OUTPUT
            echo "should_skip=$(echo "$RESULT" | jq -r '.should_skip')" >> $GITHUB_OUTPUT
            exit 0
          fi
        fi

        # Fallback: count agent metadata comments
        echo "Falling back to comment-based counting..."
        ITERATION_COUNT=$(gh api "repos/$GITHUB_REPOSITORY/issues/$PR_NUMBER/comments" \
          --paginate --jq "[.[] | select(.body | contains(\"agent-metadata:type=${AGENT_TYPE}\"))] | length" \
          2>/dev/null || echo "0")

        CONTINUE_COUNT=$(gh api "repos/$GITHUB_REPOSITORY/issues/$PR_NUMBER/comments" \
          --paginate --jq '[.[] | select(.body | test("\\[CONTINUE\\]"))] | length' \
          2>/dev/null || echo "0")

        EFFECTIVE_MAX=$(( MAX_ITERATIONS + CONTINUE_COUNT * MAX_ITERATIONS ))
        EXCEEDED_MAX="false"
        SHOULD_SKIP="false"
        if [ "$ITERATION_COUNT" -ge "$EFFECTIVE_MAX" ]; then
          EXCEEDED_MAX="true"
          SHOULD_SKIP="true"
        fi

        echo "iteration_count=$ITERATION_COUNT" >> $GITHUB_OUTPUT
        echo "effective_max=$EFFECTIVE_MAX" >> $GITHUB_OUTPUT
        echo "continue_count=$CONTINUE_COUNT" >> $GITHUB_OUTPUT
        echo "exceeded_max=$EXCEEDED_MAX" >> $GITHUB_OUTPUT
        echo "should_skip=$SHOULD_SKIP" >> $GITHUB_OUTPUT

        if [ "$EXCEEDED_MAX" = "true" ]; then
          COMMENT_FILE=$(mktemp)
          cat > "$COMMENT_FILE" <<COMMENT_EOF
        ## Agent Iteration Limit Reached
        <!-- agent-metadata:type=${AGENT_TYPE}:iteration=${ITERATION_COUNT}:limit-reached -->

        The auto-fix agent has reached the iteration limit (**${ITERATION_COUNT}/${EFFECTIVE_MAX}**).
        Further automated fixes have been paused.

        **To allow more iterations:**
        - An admin can comment \`[CONTINUE]\` to extend the limit
        - Or address the issues manually
        - Or add the \`no-auto-fix\` label to disable automated fixes
        COMMENT_EOF
          gh pr comment "$PR_NUMBER" --body-file "$COMMENT_FILE" || true
          rm -f "$COMMENT_FILE"
        fi
```

---

## How It All Works Together

### Review flow (read-only, advisory)

1. A PR is opened or updated on `main`
2. Three review jobs start **in parallel**:
   - `claude-security-review` -- calls `github-agents pr-review <PR> --profile security`
   - `claude-quality-review` -- calls `github-agents pr-review <PR> --profile quality`
   - `openrouter-review` -- calls `github-agents pr-review <PR> --profile openrouter-general`
3. Each review job:
   - Fetches the PR diff via the GitHub API
   - Loads the corresponding profile from `review-profiles.yaml`
   - Prepends profile-specific instructions to the review prompt
   - Invokes the agent (Claude CLI or OpenRouter HTTP API)
   - Posts the review as a PR comment
   - Uploads the review text as a GitHub Actions artifact
4. Reviews gracefully handle rate limits and API outages (skip instead of fail)

### Auto-fix flow (write access, commits to PR branch)

1. After all reviews complete, `agent-review-response` runs:
   - Downloads all review artifacts from the parallel review jobs
   - Checks iteration count (max 5, extensible via `[CONTINUE]` admin comments)
   - Calls `automation-cli review respond <PR> <BRANCH> <ITER> <MAX>`
   - This invokes Claude Code with `--dangerously-skip-permissions` to read the reviews, understand the issues, fix the code, and commit+push
2. If CI **fails**, `agent-failure-handler` runs instead:
   - Calls `automation-cli review failure <PR> <BRANCH> <ITER> <MAX> "format,lint,test"`
   - Claude reads the CI logs, fixes the issues, commits+pushes
3. The push triggers a new workflow run, creating a feedback loop until:
   - Everything passes, or
   - The iteration limit is reached (default 5)

### Safety mechanisms

| Mechanism | Purpose |
|-----------|---------|
| Fork guard | Blocks fork PRs from self-hosted runners |
| Iteration limit | Max 5 auto-fix attempts per agent type per PR |
| `[CONTINUE]` comments | Admins can extend the limit |
| `no-auto-fix` label | Disables auto-fix entirely for a PR |
| `AGENT_TOKEN` | Separate PAT scoped to only what the fix agent needs |
| Graceful degradation | If tools are missing, jobs skip with warnings |

---

## Customization

### Adding or removing review profiles

Edit `review-profiles.yaml`. Each profile needs:
- `display_name` -- shown in the PR comment header
- `agent` -- `claude` or `openrouter`
- `model` -- model name (e.g., `sonnet` for Claude, `qwen/qwen3.6-plus` for OpenRouter)
- `focus` -- one-line description
- `instructions` -- system prompt text prepended to the review

Then add/remove corresponding jobs in `pr-validation.yml`.

### Using only Claude (no OpenRouter)

Remove the `openrouter-review` job from the workflow and remove `openrouter` from `.agents.yaml`. The system works fine with just Claude.

### Using only OpenRouter (no Claude)

Remove the Claude review jobs, but note that `automation-cli review respond` currently uses Claude Code for the auto-fix step. Without Claude, you get reviews but no auto-fix.

### Changing iteration limits

Edit the `max_iterations` input in the iteration-check steps (default: 5). Each `[CONTINUE]` comment from an admin multiplies the limit.

### Changing the OpenRouter model

Edit the `model` field in the `openrouter-general` profile in `review-profiles.yaml`. Any model available on OpenRouter works (e.g., `anthropic/claude-sonnet-4`, `google/gemini-2.5-flash`, `meta-llama/llama-3.1-70b-instruct`).

---

## Troubleshooting

### "github-agents not found on PATH"

The binary is not accessible to the runner process. Check:
1. The binary exists: `ls ~/.local/bin/github-agents` (or `.exe` on Windows)
2. `~/.local/bin` is in the system PATH (not just the user's shell PATH)
3. The runner service was restarted after PATH changes

### "automation-cli not found on PATH"

Same as above but for `automation-cli`.

### Claude reviews fail with authentication errors

Run `claude --login` interactively on the runner machine. The credentials file (`~/.claude.json` or `~/.claude/`) must be readable by the user running the Actions runner service.

### OpenRouter reviews fail

Check that `OPENROUTER_API_KEY` is set as a repository secret and that the key is valid. Test manually:

```bash
OPENROUTER_API_KEY=sk-or-... github-agents pr-review 1 --profile openrouter-general
```

### Auto-fix agent is not pushing commits

The `AGENT_TOKEN` secret must be a GitHub PAT with `contents: write` permission on the repo. The checkout step must use `token: ${{ secrets.AGENT_TOKEN }}` (not `GITHUB_TOKEN`).

### Reviews keep running on agent commits (infinite loop)

The iteration check should catch this. If it is not working, verify that `github-agents iteration-check` works:

```bash
github-agents iteration-check --pr 1 --agent-type review-fix --max-iterations 5 --format json
```

### Windows-specific: bash scripts fail

The composite actions use `shell: bash`. On Windows runners, this requires Git Bash (installed with Git for Windows) or WSL. GitHub Actions on Windows defaults to PowerShell, but composite actions with `shell: bash` use Git Bash automatically if Git is installed.

### Updating the CLI tools

Re-run the setup script from Step 1. It will pull the latest code and rebuild:

```bash
cd ~/.agent-tools/template-repo
git pull origin main
cd tools/rust/github-agents-cli && cargo build --release
cp target/release/github-agents ~/.local/bin/
cd ../automation-cli && cargo build --release
cp target/release/automation-cli ~/.local/bin/
```

---

## File Checklist

After setup, your repo should have these files:

```
your-repo/
  .agents.yaml                              # Agent configuration
  review-profiles.yaml                      # Review profile definitions
  .github/
    workflows/
      pr-validation.yml                     # Main workflow
    actions/
      claude-review/
        action.yml                          # Claude review composite action
      openrouter-review/
        action.yml                          # OpenRouter review composite action
      agent-iteration-check/
        action.yml                          # Iteration tracking composite action
```

And on your self-hosted runner:

```
~/.local/bin/
  github-agents(.exe)                       # PR review CLI
  automation-cli(.exe)                      # Auto-fix CLI

# Claude Code installed globally via npm
claude                                      # Authenticated with --login
```
