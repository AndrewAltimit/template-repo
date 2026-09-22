# markdown-link-checker

> Fast concurrent markdown link validator for CI/CD pipelines.

The binary is `md-link-checker`. CI runs it over the whole repository with
`--internal-only` (via `automation-cli ci run lint-full` and the `pre-push`
hook). The code-quality MCP server runs it with `--json`.

## Features

- **Real CommonMark parsing** (pulldown-cmark with GFM tables, footnotes,
  strikethrough and task lists). Fenced (backtick or tilde, any length),
  indented and inline code never produce false positives. Escaped brackets,
  link titles, angle-bracket destinations and footnotes are all handled.
- **Every link form**: inline, reference-style (used and unused definitions),
  autolinks, images, and raw HTML `href`/`src` attributes. Links inside HTML
  comments are skipped.
- **Local links**: relative paths, `/repo-root` paths, percent-encoded names
  (`my%20file.md`), `?query` suffixes, directories. On Windows and macOS it
  also catches links whose case differs from the file on disk, which work
  locally but break on GitHub.
- **Anchor validation** using GitHub's slug rules, including duplicate
  headings (`#details-1`), HTML `id`/`name` targets, `#top`, the
  `user-content-` prefix, and a "did you mean" hint for near misses.
  Directory links are checked against their README. Fragments into
  non-markdown files (`code.rs#L10`) are accepted.
- **External links**: each unique URL is requested once across all files
  (fragments ignored). HEAD falls back to GET. There is a global concurrency
  limit and a per-host limit. Timeouts, connection errors, 408, 429 and 5xx
  are retried with exponential backoff, and `Retry-After` is honored.
- **File discovery** honors `.gitignore` and `.mdlinkignore`, includes hidden
  directories such as `.github/`, and never descends into `.git/`.
- **Inline suppression** with HTML comments.
- JSON output with line numbers, and distinct exit codes.

## Installation

```bash
cd tools/rust/markdown-link-checker
cargo build --release
# Binary: target/release/md-link-checker  (or run ./install.sh)
```

## Usage

```bash
md-link-checker .                                # Check every markdown file under .
md-link-checker README.md docs/                  # Several files/directories
md-link-checker . --internal-only                # Skip HTTP/HTTPS validation
md-link-checker . --json                         # Machine-readable output
md-link-checker . --ignore "example\\.com"       # Skip links matching a regex
md-link-checker . --exclude "vendor/" -e "**/fixtures"
md-link-checker . --timeout 30 --concurrent 20 --per-host 2
md-link-checker . --accept 403,429               # Treat these statuses as valid
md-link-checker . -v                             # Debug logging (stderr)
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `[PATHS]...` | Markdown files or directories to check | `.` |
| `--internal-only` | Skip HTTP/HTTPS validation. External links are listed as `skipped` | off |
| `--skip-anchors` | Skip `#fragment` validation (same-page and cross-file) | off |
| `-i, --ignore <REGEX>` | Skip links matching the regex (repeatable). Matched against the link as written | - |
| `--ignore-file <FILE>` | Read ignore regexes from a file, one per line (`#` comments). Repeatable | - |
| `--no-default-ignores` | Do not apply the [built-in ignore patterns](#default-ignore-patterns) | off |
| `-e, --exclude <GLOB>` | Skip files/directories matching a gitignore-style glob, relative to each walked path (repeatable) | - |
| `--no-ignore-files` | Do not honor `.gitignore` / `.mdlinkignore` when walking directories | off |
| `--root <DIR>` | Directory that `/absolute` links resolve against | nearest ancestor with `.git`, else the current directory |
| `--check-undefined-refs` | Also report `[text][label]` / `[text][]` references with no matching definition. GitHub renders these as literal text. Off by default because prose like `[Approved][Claude]` is often intentional | off |
| `--timeout <SECS>` | Per-request HTTP timeout (min 1) | 10 |
| `--concurrent <N>` | Maximum HTTP requests in flight (min 1) | 10 |
| `--per-host <N>` | Maximum HTTP requests in flight to one host (min 1) | 4 |
| `--max-retries <N>` | Retries for transient HTTP failures | 2 |
| `--accept <CODES>` | Extra HTTP status codes to treat as valid, comma-separated | - |
| `--json` | Print JSON to stdout. Logging is disabled | off |
| `-v, --verbose` | Debug logging | off |

Logs go to stderr. The report goes to stdout.

## What gets skipped

A skipped link is not validated and does not count toward `total_links`.

- Links matching an ignore pattern.
- Non-HTTP schemes (`mailto:`, `tel:`, `data:`, `ssh://`, `vscode:`, ...),
  including `<user@example.com>` email autolinks.
- Anything in code, in HTML comments, or in a suppressed region.

### Default ignore patterns

- `^https?://localhost`, `^https?://127\.`, `^https?://0\.0\.0\.0`, `^https?://\[::1?\]`
- Private networks: `^https?://10\.`, `^https?://172\.(1[6-9]|2[0-9]|3[01])\.`, `^https?://192\.168\.`
- `^mailto:`, `^chrome://`, `^file://`, `^ftp://`, `^tel:`, `^javascript:`

### Excluding files

Put a `.mdlinkignore` file (gitignore syntax) in any directory to exclude
markdown files below it without touching `.gitignore`. For example:

```text
# .mdlinkignore
generated/
CHANGELOG.md
```

### Suppressing links inline

```markdown
<!-- md-link-checker-disable-next-line -->
[example of a broken link](does-not-exist.md)

<!-- md-link-checker-disable -->
Everything here is ignored.
<!-- md-link-checker-enable -->
```

## Output

Human-readable output (stdout):

```text
=== Markdown Link Check Results ===

Files checked: 68
Total links:   561
Broken links:  1

Broken links:

  docs/guide.md:42 -> ./missing.md (File not found)
```

Each broken link is printed as `<file>:<line> -> <url> (<error>)`. The line
is the first occurrence of that link. Files that could not be read are listed
under `Unreadable files:`.

### JSON format

```json
{
  "success": true,
  "files_checked": 2,
  "total_links": 3,
  "broken_links": 1,
  "file_errors": 0,
  "all_valid": false,
  "results": [
    {
      "file": "docs/README.md",
      "links": [
        { "url": "https://example.com", "valid": true, "lines": [3], "skipped": true },
        { "url": "#setup", "valid": true, "lines": [5, 12] },
        {
          "url": "./missing.md",
          "valid": false,
          "error": "File not found",
          "lines": [8]
        }
      ],
      "broken_count": 1,
      "total_count": 3
    }
  ]
}
```

- `results` is sorted by path. `links` has one entry per unique link in a file,
  in order of first appearance.
- `lines` holds every 1-based line where the link occurs.
- `skipped` is present only when true: an external link under `--internal-only`.
- `error` on a file entry means the file could not be read, for example
  because it is not UTF-8. Such files count in `file_errors` and fail the run.
- `success` is always `true` when JSON is printed. Fatal errors exit before
  any output.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | All links valid |
| 1 | One or more broken links, or an unreadable markdown file |
| 2 | Usage or fatal error: bad arguments, invalid regex or glob, nonexistent path, unreadable `--ignore-file` |

## Development

```bash
# From the repository root (container-first)
docker compose --profile ci run --rm -w /app/tools/rust/markdown-link-checker rust-ci \
  bash -c "cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test"
```

Layout:

| Module | Responsibility |
|--------|----------------|
| `src/main.rs` | CLI flags, logging, exit codes |
| `src/checker.rs` | Orchestration and cross-file URL deduplication |
| `src/discover.rs` | File discovery and repository-root detection |
| `src/parse.rs` | Link, anchor and undefined-reference extraction |
| `src/html.rs` | Raw HTML attributes, comments and suppression markers |
| `src/slug.rs` | GitHub heading slugs |
| `src/target.rs` | Link classification and percent-decoding |
| `src/local.rs` | File, case and anchor validation |
| `src/http.rs` | HTTP probing, rate limiting and retries |
| `src/filters.rs` | Ignore patterns |
| `src/report.rs` | Result types (JSON schema) and human output |

Integration-test fixtures live in `tests/fixtures/` with an extra `.in`
suffix (`README.md.in`). That keeps the repository-wide link check from
flagging their intentionally broken links. The tests copy them into a temp
directory and strip the suffix.

## License

Part of the template-repo project. See repository LICENSE file.
