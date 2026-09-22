# github-agents-cli

> Rust CLI (`github-agents`) for the GitHub AI Agents system: trigger-based
> issue/PR automation, AI PR reviews, backlog refinement, codebase analysis,
> iteration limits and the security primitives behind them.

## Installation

```bash
cd tools/rust/github-agents-cli
cargo build --release          # binary: target/release/github-agents
./install.sh                   # optional: copy to ~/.local/bin
```

Requirements: GitHub CLI (`gh`) installed and authenticated (`GITHUB_TOKEN`
/`GH_TOKEN` or `gh auth login`), `git`, and the agent CLIs you intend to use.

## Agents

| Agent | Backend | Notes |
|-------|---------|-------|
| `claude` | Claude Code CLI (`claude --print`, prompt on stdin) | Default/highest priority. Path override: `CLAUDE_PATH`, model: `CLAUDE_MODEL` |
| `opencode` | OpenCode CLI (`opencode run -m openrouter/<model>`) | Needs `OPENROUTER_API_KEY`; model: `OPENCODE_MODEL` (default `qwen/qwen3.7-max`) |
| `crush` | Crush CLI (`crush run -q`) | Needs `OPENROUTER_API_KEY`; model: `CRUSH_MODEL` |
| `openrouter` | OpenRouter API (text only) | Needs `OPENROUTER_API_KEY`; model: `OPENROUTER_MODEL` |
| `gemini`, `codex` | -- | **Disabled by project policy.** Requests fail with exit code 5; in agent lists (`--agents claude,gemini`) they are skipped with a warning |

An explicitly requested agent (`[Approved][Crush]`, `--agent crush`) is never
silently replaced by another one: if it is unknown, disabled or not installed
the request fails with a clear message.

## Commands

Global flag: `-v, --verbose` (debug logging). Logs always go to stderr, so
`--format json` output on stdout is machine-readable.

### `issue-monitor` / `pr-monitor`

```bash
github-agents issue-monitor [--continuous] [--interval 300]
github-agents pr-monitor    [--continuous] [--interval 300]
```

Scans open issues/PRs updated in the last 24 hours for trigger comments from
allow-listed users and acts on them once.

| Trigger | Issue | PR |
|---------|-------|----|
| `[Approved][Agent]` | Agent proposes an implementation | Agent addresses review feedback (commit-pinned, see below) |
| `[Review][Agent]` | Agent reviews the issue | Agent reviews the diff |
| `[Debug][Agent]` | Root-cause analysis | Defect analysis of the diff |
| `[Summarize]` | Deterministic summary | Deterministic summary |
| `[Close]` | Closes the issue | Closes the PR |

`[Agent]` is optional; without it the highest-priority available agent is used.

Environment: `GITHUB_REPOSITORY` (required), `AGENTS_CONFIG_PATH` (default
`.agents.yaml`), `TARGET_ISSUE_NUMBERS` / `TARGET_PR_NUMBERS` (comma-separated
filters), `REVIEW_ONLY_MODE=true` (refuse `[Approved]`), `AGENT_TIMEOUT_SECS`
(default 600).

### `refinement-monitor`

```bash
github-agents refinement-monitor [--agents claude] [--max-issues 5] [--max-comments 2] \
    [--min-age-days 3] [--dry-run] [--format text|json]
```

Each agent reviews open issues aged `min-age-days`..365 days from its own
perspective (architecture, maintainability, implementation, quality/security)
and posts only novel insights, with a 14-day per-agent cooldown. Issues labeled
`blocked`, `wontfix` or `in-progress` are skipped. JSON output is an array of
`{issue_number, issue_title, insights_added, insights_skipped, agents_reviewed,
actions_taken, error}`.

### `pr-review`

```bash
github-agents pr-review <PR> [--agent claude|openrouter|opencode|crush] [--profile NAME] \
    [--full] [--dry-run] [--format text|json] [--editor] [--editor-agent claude]
```

Reviews the PR diff (`origin/<base>...HEAD`, so run it from a checkout of the
PR head). A `--profile` from `review-profiles.yaml` selects agent, model and
focus (and overrides `--agent`). Incremental reviews resume from the last
review marker posted by a trusted account (bots, `agent_admins`,
`trusted_sources`). Claims about files/lines are verified; reviews over the
word threshold are condensed. Text mode prints `Review posted to PR #N`; dry
runs print a preview; JSON prints `{pr_number, review, dry_run}`.

Transient agent/API outages surface as `service unavailable (transient)` in
the error message so workflows can skip gracefully.

### `iteration-check`

```bash
github-agents iteration-check --pr N --agent-type review-fix|failure-fix \
    [--max-iterations 5] [--format text|json|github-actions] [--config .agents.yaml]
```

Counts `<!-- agent-metadata:type=TYPE:iteration=N -->` markers (limit-reached
notices excluded). Each `[CONTINUE]` from an agent admin extends the limit by
`--max-iterations`. `github-actions` format appends the results to
`$GITHUB_OUTPUT`. Requires `GITHUB_REPOSITORY`.

### `analyze`

```bash
github-agents analyze [--agents claude] [--include-paths "**/*.py,**/*.rs,..."] \
    [--exclude-paths "**/tests/**,..."] [--categories security,performance,quality,tech_debt] \
    [--min-priority P2] [--max-issues 5] [--dry-run] [--format text|json]
```

Agents analyze a bounded sample of matching files and report findings, which
are deduplicated by fingerprint against the last 30 days of
`agentic-analysis` issues and filed (with labels and a project-board entry via
`board-manager`). JSON output: `{findings, count, created, skipped, dry_run,
results}`.

### `security`

```bash
github-agents security [--config .agents.yaml] [--format text|json] <command>
  check-user --username NAME             # exit 8 if not allow-listed
  check-action --action issue_approved   # exit 8 if not allowed
  validate-pr-commit --pr N --expected-sha SHA [--repo owner/repo]   # exit 8 on mismatch
  parse-trigger --comment "TEXT"         # prints action/agent (or "No trigger found")
```

## Security Model

- **Allow-list**: `security.agent_admins` in `.agents.yaml`, plus
  `AI_AGENT_ALLOWED_USERS` (comma-separated) and the repository owner.
  `AI_AGENT_DEFAULT_ADMIN` overrides the built-in default admin when no config
  exists. Bot accounts are never authorized. A config file that exists but is
  invalid is a hard error for the monitors (fail secure).
- **Trigger parsing**: triggers inside code spans/blocks, blockquotes and HTML
  comments are ignored, as is anything in comments generated by this tool.
  Only the latest authorized trigger counts, and each is acted on once (a
  monitor reply marks it handled).
- **Prompt-injection hardening**: all model output is neutralized before
  posting (`[Approved]` becomes `\[Approved\]`) so an agent cannot approve its
  own work, even when it posts with a maintainer token; prompts label PR/issue
  content as untrusted.
- **Commit pinning for PR approvals**: the head commit must not be newer than
  the approval, must be unchanged when the agent starts, and must be unchanged
  when it finishes, otherwise the output is discarded and re-approval is
  requested. (Commit dates are client-supplied; the before/after SHA checks are
  authoritative.)
- **Trusted configuration in PR runs**: in workflows triggered by pull request
  events, `.agents.yaml`, `review-profiles.yaml`, `README.md`/`CLAUDE.md`
  context and `.mcp.json` are taken from the base branch when the PR modifies
  them (`.mcp.json` is skipped entirely in that case).

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error (configuration, I/O, API, review agent failure) |
| 2 | GitHub CLI not found or not authenticated |
| 5 | Agent not available (unknown, disabled by policy, or not installed) |
| 6 | Agent execution failed (includes transient outages) |
| 7 | Agent timed out |
| 8 | Security check failed / denied |
| 130 | Interrupted (Ctrl+C) |

## Development

```bash
# From the repository root (container-first)
MSYS_NO_PATHCONV=1 docker compose --profile ci run --rm -w /app/tools/rust/github-agents-cli \
  rust-ci bash -c "cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test"
```

For simple PR comment watching without automation, use the separate
`pr-monitor` tool (`tools/rust/pr-monitor`).

## License

Part of the template-repo project. See repository LICENSE file.
