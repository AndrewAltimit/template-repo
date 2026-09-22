# gh-validator

> A `gh` wrapper that validates and sanitizes everything an AI agent posts to
> GitHub: secrets are masked, Unicode emoji rejected, @mentions neutralized,
> reaction images verified.

The binary is named `gh`. Installed ahead of the real GitHub CLI on `PATH`
(or as the setgid `/usr/bin/gh` in [hardened mode](../../../docs/infrastructure/wrapper-guard.md)),
it passes commands without user content straight to the real `gh` (via
`exec()` on Unix) and validates the rest first.

## What counts as content

Arguments are parsed with pflag semantics (`--flag=value`, `--flag value`,
clustered short flags such as `-wbTEXT`, `-b=TEXT`, `--` terminator), and
short flags are interpreted per command (`-F` is `--body-file` for
`pr`/`issue`, `--notes-file` for `release`, `--field` for `api`).

| Source | Flags / form |
|--------|--------------|
| Markdown text | `--body`/`-b`, `--notes`/`-n`, `--message` |
| Short text | `--title`/`-t`, `--subject`, `--description`, `--desc` |
| Content files | `--body-file`/`-F`, `--notes-file`/`-F`, `pr create --template`/`-T` |
| API fields | `gh api -f/--raw-field k=v`, `-F/--field k=v` |
| API files | `gh api -F k=@file`, `gh api --input file` |
| Gist uploads | `gh gist create <files>` |
| Aliases | `gh <alias> ...` is expanded from gh's `config.yml` and checked as the expanded command |

`gh secret set --body` is the secret value itself and is passed through
untouched; `gh variable set --body` is masked and emoji-checked only.

## Checks

| Check | Inline text | Content files | Result |
|-------|-------------|---------------|--------|
| Secrets (config env vars, auto-detected env vars, config patterns, built-in baseline) | all arguments | yes | masked (`[MASKED_NAME]`) |
| Unicode emoji (emoji blocks, `U+FE0F`, keycaps, tag characters) | all arguments | yes | rejected |
| Escaped emoji (JSON `\u` surrogate pairs, `\u{...}`) | `gh api` fields | `gh api` files | rejected |
| Reaction image passed inline | `--body`, api `body=` | - | rejected (use `--body-file`) |
| Reaction image URLs | - | markdown files | verified (HTTPS, GitHub hosts only, no credentials/ports, HEAD 200, redirects only within GitHub hosts) |
| @mentions other than the allow-list | markdown text | markdown files | wrapped in backticks (no notification) |

The **built-in secret baseline** is always active, even with a weakened
config: values of `GITHUB_TOKEN`, `GH_TOKEN`, `GH_ENTERPRISE_TOKEN`,
`GITHUB_ENTERPRISE_TOKEN`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, and
GitHub token, AWS key, Anthropic key, Slack token, and private-key-block
formats.

**Mentions**: `@user` and `@org/team` outside code spans and fenced code
blocks are neutralized unless the handle is in `allowed_mentions` (config;
default `AndrewAltimit`). E-mail addresses, URLs, and paths are untouched.
`gh api` payloads are only rewritten for text fields (`body`, `title`,
`description`, `message`); `--input` JSON is never rewritten.

**Content files are never modified.** Each file is read once, validated,
sanitized, and written to a private (`0600`) temporary copy that replaces
the path in the arguments; the copy is deleted when gh exits. gh therefore
posts exactly the bytes that were validated. Missing, non-regular,
non-UTF-8, or oversized (> 25 MiB) files are errors.

`gh gist create` files are uploaded verbatim, so a file containing a secret
is rejected rather than rewritten.

## Blocked operations

| Blocked | Why |
|---------|-----|
| `gh alias set`, `gh alias import` | aliases hide commands from the wrapper |
| `gh extension install`, `gh extension upgrade` | extensions run unvalidated code |
| `--editor`/`-e` on `pr`/`issue` `create`/`comment` | editor content (or `$GH_EDITOR` output) is never seen |
| Content from stdin: `--body-file -`, `-F -`, `--notes-file -`, `api -F k=@-`, `api --input -`, `gist create` with `-` or no files | stdin cannot be validated |
| Any content check failure above | fail-closed |
| No `.secrets.yaml` found (content commands only) | fail-closed |
| Hardened mode: shell aliases and unknown top-level commands (extensions) | they would run with the `wrapper-guard` group |

## Configuration

`.secrets.yaml` is searched in this order (first existing file wins):

1. `/etc/wrapper-guard/.secrets.yaml` (system config, e.g. hardened container)
2. the current directory and its ancestors, up to the git root
3. the binary's directory and its ancestors, up to a git root
4. `~/.secrets.yaml`
5. `$XDG_CONFIG_HOME/gh-validator/.secrets.yaml` (default `~/.config/...`)

See the repository [.secrets.yaml](../../../.secrets.yaml) for the format.
Optional `allowed_mentions: [handle, ...]` overrides the mention allow-list.
Commands without content never read the config, so the fast path stays
cheap.

## Special flags

- `--wrapper-integrity` (first argument): print `wrapper=`, `source_hash=`,
  `common_hash=`, `binary=` and exit.
- `--gh-validator-strip-invalid-images`: remove invalid reaction images
  instead of failing (the flag is consumed, never passed to gh). If nothing
  but invalid images remains, the command is skipped with exit 0. Used by
  the automated reviewers.

After a successful `gh pr create`, a reminder to run `pr-monitor` for the
new PR is printed to stderr.

## Installation

```bash
# From a checkout: builds from source and installs to ~/.local/bin/gh
./tools/rust/gh-validator/install.sh

# Or download a release binary
curl -sSL https://raw.githubusercontent.com/AndrewAltimit/template-repo/main/tools/rust/gh-validator/install.sh | bash

export PATH="$HOME/.local/bin:$PATH"   # must precede the real gh
gh --wrapper-integrity
```

`uninstall.sh` removes the binary only after confirming via
`--wrapper-integrity` that it really is gh-validator.

## Architecture

```
src/
  main.rs            entry point: plan (exec / validate+run / skip), audit, notices
  lib.rs             library root (everything testable)
  args.rs            pflag-compatible parsing into content slots
  aliases.rs         gh alias expansion from config.yml
  policy.rs          operations refused outright
  sanitize.rs        per-slot checks, masking, private temp copies
  error.rs           fail-closed error type with help text
  config/            .secrets.yaml discovery and types
  validation/
    secrets.rs       secret masking (config + built-in baseline)
    comments.rs      emoji, escaped emoji, reaction images, mentions
    urls.rs          reaction URL validation (SSRF-safe, manual redirects)
```

Binary lookup, `exec`/spawn with signal and exit-code passthrough, audit
logging, and integrity hashing come from [`wrapper-common`](../wrapper-common/README.md).

## Known limitations

- `gh pr create --fill*` builds the body from commit messages, which are not
  validated.
- Non-hardened mode: extensions and shell aliases still run (their inner
  `gh` calls go through the wrapper again, direct API calls do not).
- `gh api --input` JSON is checked for emoji and masked, but mentions inside
  it are not rewritten.
- Hardened mode shares git-guard's limitation: processes started by the real
  gh inherit the `wrapper-guard` group.

## Development

```bash
docker compose --profile ci run --rm -w /app/tools/rust/gh-validator rust-ci \
  bash -c "cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test"
```

`tests/cli.rs` runs the built binary against a fake `gh` script.

## License

Part of the template-repo project. See repository LICENSE file.
