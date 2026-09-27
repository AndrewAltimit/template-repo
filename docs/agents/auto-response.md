# Review Auto-Response

This document describes how agents respond automatically to AI code review feedback on pull requests.

> Earlier versions of this page described a Gemini-specific auto-response mode (Gemini review detection, `DISABLE_GEMINI_AUTO_RESPONSE`, `ai-agent-gemini-response` markers). Gemini is legacy and not allowed in the lab; see [Legacy agents](agent-matrix.md#legacy-agents-gemini-and-codex-not-allowed). The current flow is below.

## Current Flow

The `agent-review-response` job in `.github/workflows/pr-validation.yml` runs after the three AI reviews finish:

1. **Claude security review** (`security` profile in `review-profiles.yaml`)
2. **Claude quality review** (`quality` profile)
3. **OpenRouter general review** (`openrouter-general` profile, `qwen/qwen3.7-max`)

The job calls `automation/ci-cd/agent-review-response.sh`, a thin wrapper around `automation-cli review respond`. That command:

- Feeds the reviewer output and trusted PR discussion to Claude
- Verifies Claude actually edited files
- Runs a lint-fix pass
- Commits and pushes with remote verification

## When It Runs

The job is skipped unless all of these hold:

- The event is a `pull_request` and the PR is not a draft
- The repository variable `ENABLE_AGENTS` is `'true'`
- The PR does not carry the `no-auto-fix` label

Iterations are tracked per PR by `.github/actions/agent-iteration-check` (default limit 5). Agent admins can extend the limit with `[CONTINUE]` in a PR comment (see `.agents.yaml`).

## Disabling Auto-Response

- **Per PR**: add the `no-auto-fix` label.
- **Globally**: set the repository variable `ENABLE_AGENTS` to anything other than `'true'`.

## Confidence Assessment

`board-manager` includes an `AgentJudgement` module (`tools/rust/board-manager/src/security/judgement.rs`) that classifies review items as auto-fix or ask-owner. Low-confidence items (architectural changes, API changes, dependency updates, multiple valid approaches) should wait for an `[Approved]` trigger from an agent admin.

## Related

- [PR Monitoring](pr-monitoring.md)
- [Auto Review](auto-review.md)
- [Security Model](security.md)
