# board-manager

GitHub Projects v2 board manager for AI agent coordination.

`board-manager` is the single entry point the agent workflows use to talk to the
project board: it finds ready work, records claims as issue comments (with
conflict resolution), updates board fields, tracks dependencies, verifies
`[Approved][Agent]` triggers, and cleans up stale claims. It also ships a few
offline helpers (comment trust bucketing, review-fix assessment).

## Installation

```bash
# Container-first (from the repo root)
docker compose --profile ci run --rm -w /app/tools/rust/board-manager rust-ci \
  cargo build --release

# Or natively
cd tools/rust/board-manager && cargo build --release
./install.sh      # copies target/release/board-manager to ~/.local/bin
./uninstall.sh
```

## Global options

| Option | Description |
|--------|-------------|
| `--format human\|json` | Output format (default `human`, case-insensitive). May appear before or after the subcommand. |
| `-v, --verbose` | Debug logging. `RUST_LOG` overrides the filter. |
| `--config <PATH>` | Board config file (see [Configuration](#configuration)). |

Output contract: with `--format json` each successful command prints exactly one
JSON document on stdout. All logs go to **stderr**, so `$(board-manager --format json ...)`
is always parseable. Any failure exits with status `1` and prints `Error: ...` to stderr.

## Commands

### Board commands (need a token and board config)

| Command | Description |
|---------|-------------|
| `ready [-a AGENT] [-l LIMIT] [--approved-only] [--include-labels L,..] [--exclude-labels L,..]` | Open `Todo` issues whose blockers are resolved, not assigned to another agent, sorted by priority then age. `LIMIT` defaults to 10. Label filters are case-insensitive, comma-separated and repeatable. `--approved-only` keeps only issues with an `[Approved][..]` trigger from an allowed approver, naming `AGENT` when `--agent` is given (checked in batches, in priority order). JSON: array of issues. |
| `claim ISSUE -a AGENT [-s SESSION]` | Claim an issue: posts an `[Agent Claim]` comment and sets `In Progress`. Session ID is generated if omitted. JSON: `{success, issue, agent, session_id}` plus `reason`, `claimed_by`, `claimed_session` when the claim failed. |
| `renew ISSUE -a AGENT -s SESSION` | Post a `[Claim Renewal]` comment if AGENT holds the active claim. JSON: `{success, issue, agent}`. |
| `release ISSUE -a AGENT [-r REASON]` | Post an `[Agent Release]` comment. `REASON`: `completed` (default) and `pr_created` keep the status, `blocked` sets `Blocked`, `abandoned`/`error` set `Abandoned`. JSON: `{success, issue, agent, reason}`. |
| `status ISSUE STATUS` / `status ISSUE -s STATUS` | Set the board status (`Todo`, `In Progress`, `Blocked`, `Done`, `Abandoned`; case/separator-insensitive, e.g. `in_progress`). JSON: `{success, issue, status}`. |
| `block ISSUE -b BLOCKER` | Add BLOCKER to ISSUE's `Blocked By` field. JSON: `{success, issue, blocker, blocked_by}`. |
| `unblock ISSUE -b BLOCKER` | Remove BLOCKER from `Blocked By` (clears the field when empty). |
| `discover-from ISSUE -p PARENT` | Set ISSUE's `Discovered From` field. JSON: `{success, issue, parent}`. |
| `info ISSUE` | Board details for one issue. JSON: the issue, or `null` if it is not on the board. |
| `deps ISSUE` (alias `graph`) | Dependency graph: blockers (and ones missing from the board), issues it blocks, parent, children, and whether it is ready. JSON: graph or `null`. |
| `agents` | Enabled agents from config. JSON: array of names. |
| `config` | Effective board configuration. JSON: config object. |
| `find-approved [-a AGENT] [--unverified]` | Search open issues with `[Approved][AGENT]` comments (default agent `claude`). By default each hit is verified to come from an authorized user and unverified hits are dropped; `--unverified` returns raw search hits. JSON: `[{number, title, on_board, approver?}]`. |
| `add-to-board ISSUE` (alias `add`) `[-s STATUS] [-p PRIORITY] [-t TYPE] [--size SIZE] [-a AGENT]` | Add an issue with initial fields. Status defaults to `Todo`, agent to `Claude Code`; workflow agent names (`claude`) are mapped to board names. Optional fields that do not exist on the board are reported as warnings. JSON: `{success, issue, already_on_board, status, warnings?}`. |
| `check-approval ISSUE [-a AGENT]` | Whether ISSUE has an `[Approved][..]` trigger from an allowed approver (naming AGENT, if given; see [Approval](#approval)). JSON: `{approved, issue, approver}`. |
| `janitor [-a AGENT] [--threshold HOURS] [--reset-status STATUS] [--dry-run]` | For open `In Progress` issues, release claims with no activity for `HOURS` (default: `work_claims.timeout`) and reset the status (default `Todo`). Issues without any claim comment are reported, not touched. JSON: `{dry_run, threshold_hours, reset_status, inspected, cleaned_count, stale[], unclaimed_in_progress[], failed[]}`. |

### Local commands (no GitHub access)

| Command | Description |
|---------|-------------|
| `bucket-comments [JSON\|-] [--config-path P] [--filter-noise[=BOOL]] [--include-empty]` | Group comments by author trust level from `.agents.yaml`. Input is a JSON array on stdin (default `-`) or as an argument; both GraphQL/`gh --json` shape (`author.login`, `createdAt`) and REST shape (`user.login`, `created_at`) are accepted. Noise (claim/renewal/release comments, bare triggers) is filtered unless `--filter-noise=false`. Human output: markdown sections. JSON: `{admin, trusted, community, buckets: {admin: [...], ...}}` (counts plus comments). |
| `trust-level USERNAME [--config-path P]` | Trust level of a user. JSON: `{username, trust_level}`. |
| `assess-fix COMMENT [options]` | Heuristic decision on whether a review suggestion should be auto-applied, needs owner input, or is a false positive. Context options: `--file-path`, `--diff-file`, `--security-related`, `--draft`, `--touches-api`, `--touches-database`, `--existing-tests`, `--pipeline-status TEXT`, `--job-result NAME=RESULT` (repeatable), `--recent-commit MSG` (repeatable). JSON: judgement result. |

## Examples

```bash
board-manager --format json ready --agent claude --limit 5 --approved-only
board-manager claim 123 --agent claude --session "run-42"
board-manager status 123 "In Progress"
board-manager release 123 --agent claude --reason pr_created
board-manager block 123 --blocker 120 && board-manager deps 123
board-manager add 123 --priority High --type "Tech Debt" --size M --agent claude
board-manager --format json janitor --agent claude --threshold 2 --dry-run
gh api repos/OWNER/REPO/issues/123/comments | board-manager bucket-comments
```

## How claims work

Claims are structured issue comments (`**[Agent Claim]**`, `**[Claim Renewal]**`,
`**[Agent Release]**`), so they are auditable and need no extra storage. The active
claim is rebuilt by replaying the last 100 comments in order, using the server-side
comment timestamps.

Only claim, renewal and release comments written by a user in
`security.agent_admins` or `security.trusted_sources` of `.agents.yaml` count
(case-insensitive; GitHub App authors such as the Actions bot match their
`name[bot]` entry, e.g. `github-actions[bot]`). Look-alike comments from anyone
else are ignored (logged at debug level), so they cannot squat on, renew or release
a claim. If `.agents.yaml` cannot be loaded, only comments by the repository owner
count (fail closed). This applies to `claim`, `renew`, `janitor` and every other
command that reads claims.

Replay rules:

- a claim only takes effect if no other unexpired claim is active at that moment,
  so when two agents claim concurrently the first comment wins; `claim` re-reads
  after posting and reports `lost_race` instead of proceeding;
- a renewal refreshes the claim of the same agent;
- a release clears the active claim;
- a claim expires after `work_claims.timeout` seconds without renewal.

An issue is **ready** when it is open, has status `Todo`, is unassigned or assigned
to the requesting agent, has no excluded label, and every blocker is closed or
`Done`/`Abandoned` (blockers not on the board count as unresolved). When the board
`Priority`/`Type` fields are empty, `work_queue.priority_labels` / `type_labels` are
used as a fallback.

## Configuration

Board config resolution order:

1. `--config PATH` (must exist)
2. `BOARD_CONFIG_PATH` (used if the file exists; otherwise a warning is logged)
3. `ai-agents-board.yml` / `.yaml` (optionally dot-prefixed) in the current directory or any parent
4. Environment: `BOARD_PROJECT_NUMBER`, `BOARD_REPOSITORY` (or `GITHUB_REPOSITORY`), `BOARD_OWNER` (defaults to the repository owner)

Relevant keys of `ai-agents-board.yml`:

| Key | Meaning |
|-----|---------|
| `project.number`, `project.owner` | Projects v2 board (user- or org-owned) |
| `repository` | `owner/repo` the issues live in |
| `fields.*` | Board field names for `status`, `priority`, `agent`, `type`, `blocked_by`, `discovered_from`, `size` |
| `agents.enabled_agents` | Agents listed by `agents` (claiming with another name logs a warning) |
| `work_claims.timeout` | Claim expiry in seconds (default 86400) |
| `work_queue.exclude_labels` | Labels never returned by `ready` |
| `work_queue.priority_labels`, `work_queue.type_labels` | Label fallbacks for Priority / Type |

### Approval

Only an `[Approved][Agent]` trigger (case-insensitive) in the issue body or a comment
approves an issue, and only when written by the project owner, the repository owner,
or a user in `security.agent_admins` of `.agents.yaml` (searched from the current
directory upwards; `trusted_sources` cannot approve). Other `[Action][Agent]`
keywords such as `[Review]`, `[Close]`, `[Summarize]` or `[Debug]` are not approvals.

When an agent is given (`ready --agent A --approved-only`, `check-approval --agent A`,
`find-approved --agent A`), the trigger must name that agent; workflow and board
names are equivalent (`[Approved][Claude]` and `[Approved][Claude Code]` both approve
for `claude`). Without an agent, `[Approved]` for any agent counts.

`bucket-comments` / `trust-level` also use `security.trusted_sources` and fail if no
`.agents.yaml` is found.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `GITHUB_PROJECTS_TOKEN` | Preferred token (classic PAT with `project` and `repo` scopes) |
| `GITHUB_TOKEN`, `GH_TOKEN` | Fallback tokens (empty values are ignored) |
| `GITHUB_GRAPHQL_URL`, `GITHUB_API_URL` | API endpoints (set automatically in Actions; enables GHES) |
| `BOARD_MANAGER_HTTP_TIMEOUT_SECS` | Per-request timeout (default 30) |
| `BOARD_CONFIG_PATH`, `BOARD_PROJECT_NUMBER`, `BOARD_OWNER`, `BOARD_REPOSITORY` | See [Configuration](#configuration) |

## API usage and resilience

- One query at startup resolves the project and all field definitions.
- Single-issue commands look the issue up directly through `Issue.projectItems`
  instead of paginating the whole board.
- Approval checks for many issues are batched into aliased queries (20 per request).
- Full board scans (`ready`, `deps`, `janitor`, `find-approved`) paginate up to 5000 items.
- Rate limits (HTTP 403/429 with `retry-after`/`x-ratelimit-*` headers, or GraphQL
  `RATE_LIMITED`) are waited out for up to 5 minutes; longer waits fail fast.
- 5xx and transient GraphQL errors are retried with exponential backoff for queries.
  Mutations are never replayed once the server may have processed them, so claim
  comments are not duplicated. Permanent errors (401, 404, validation) fail immediately.
- Mutations with any GraphQL error fail instead of being reported as success.

## Testing

```bash
docker compose --profile ci run --rm -w /app/tools/rust/board-manager rust-ci \
  bash -c "cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test"
```

Parsing, selection, claim resolution, approval batching, retry classification and
CLI argument compatibility are unit-tested without network access.

## See Also

- [GitHub Agents CLI](../github-agents-cli/README.md) - Full-featured agent CLI
- [Board Agent Work Action](../../../.github/actions/board-agent-work/README.md) - GitHub Action wrapper
- [GitHub Board MCP server](../../mcp/mcp_github_board/README.md) - MCP wrapper around this CLI
