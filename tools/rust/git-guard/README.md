# git-guard

> A `git` wrapper that stops AI agents from force-pushing, skipping hooks, or
> pushing to protected branches (`main`, `master`).

The binary is named `git`. Installed ahead of the real git on `PATH` (or as
the setgid `/usr/bin/git` in [hardened mode](../../../docs/infrastructure/wrapper-guard.md)),
it inspects every invocation, refuses dangerous ones with exit code 1, and
hands everything else to the real git with `exec()` (Unix), so stdio,
signals, the terminal, and exit codes pass through untouched.

## Blocked operations

### Force pushes

| Form | Example |
|------|---------|
| `--force`, `-f` (also inside short-flag clusters) | `git push -uf origin x` |
| `--force-with-lease[=...]`, `--force-if-includes` | `git push --force-with-lease` |
| `+` refspecs | `git push origin +feature`, `+HEAD:feature` |
| `--mirror` | `git push --mirror` |
| Configured forced refspec used by a bare push | `remote.origin.push = +refs/heads/*:refs/heads/*` |
| Configured mirror remote used by a bare push | `remote.origin.mirror = true` |

### Skipping or redirecting hooks

| Form | Example |
|------|---------|
| `--no-verify` on any command | `git commit --no-verify`, `git merge --no-verify` |
| `-n` on `git commit` (also clustered) | `git commit -anm msg` |
| `core.hooksPath` or config includes via `-c` / `--config-env` | `git -c core.hooksPath=/dev/null commit` |
| ...via environment | `GIT_CONFIG_PARAMETERS`, `GIT_CONFIG_KEY_<n>` |
| ...written with `git config` | `git config core.hooksPath /dev/null`, `git config set ...`, `include.path`, `includeIf.<cond>.path` |

Reading or unsetting these keys (`git config --get core.hooksPath`,
`git config --unset core.hooksPath`) is allowed.

### Pushes that can update a protected branch

| Form | Example |
|------|---------|
| Explicit destination | `git push origin main`, `HEAD:main`, `x:refs/heads/main`, `heads/main`, `main:` |
| Deletion | `git push origin :main`, `git push origin --delete main` |
| Any refspec in the list | `git push origin feature main` |
| Wildcards matching a protected branch | `git push origin 'refs/heads/*:refs/heads/*'` |
| Remote `HEAD` as destination | `git push origin feature:HEAD` |
| `HEAD` / `@` while on a protected branch | `git push origin HEAD` on `main` |
| Bare `git push [remote]` on, or tracking, a protected branch | upstream resolved with `@{push}` |
| All / matching branches | `--all`, `--branches`, `:` refspec, `push.default=matching` |
| Pruning remote branches | `--prune` |
| Low-level push commands | `git send-pack`, `git http-push` |
| `git subtree push` to a protected branch | `git subtree push -P lib origin main` |

### Parsing rules that close bypasses

- **Global options** before the subcommand are parsed like `git.c` does:
  `git -C dir push -f`, `git -c k=v push -f`, `git --git-dir d push ...`,
  and `git -- push -f` are all recognised as pushes.
- **Abbreviated long options** are matched the way git's parse-options
  does: `--forc`, `--force-w`, `--mirr`, `--no-verif` are blocked. An
  ambiguous abbreviation is blocked too (git would reject it anyway).
- **Aliases** are expanded (recursively, including aliases defined with
  `-c alias.x=...`) by asking the real git for `alias.<name>` whenever the
  subcommand is not a builtin, then checked like the expanded command.
- Option **values** are not mistaken for flags: `git commit -m -n`,
  `git commit -mn`, `git push -o f` are allowed.

In **hardened mode** (the wrapper runs setgid `wrapper-guard`), shell aliases
(`alias.x = !...`) are also blocked, because they would run with the
group that can execute the real binaries.

### Deliberately not blocked

`--force` on other commands (`checkout`, `clean`, `branch -f`, `tag -f`),
`-n` on commands where it does not skip hooks (`log`, `cherry-pick`,
`revert`, `merge` (`--no-stat`), `push` (`--dry-run`), `clean`), local
history rewriting (`reset --hard`, `rebase`), and forced fetches.
git-guard protects the review workflow, not the local working tree.

## Example output

```
============================================================
GIT-GUARD: OPERATION BLOCKED
============================================================

The following operation(s) are not allowed:

  - push to 'main' (refspec 'HEAD:main') : Direct push to a protected branch bypasses PR review

This safety mechanism prevents AI assistants from performing
destructive git operations or bypassing code review.

If a human needs this operation, run the real git binary directly:

  /usr/bin/git <command>

============================================================
```

## How it works

1. `--wrapper-integrity` as the first argument prints `wrapper=`,
   `source_hash=`, `common_hash=` and `binary=` lines and exits 0.
2. The real git is located by `wrapper-common` (hardened path, then
   absolute `PATH` entries, never itself or another wrapper on the chain).
3. Global options, subcommand, and aliases are resolved (`src/cli.rs`).
4. The policy (`src/policy.rs`) is evaluated. It only asks git for context
   when needed (`src/query.rs`): alias lookup for non-builtin subcommands,
   current branch / `@{push}` / `push.default` / `remote.*.push` for pushes
   without an explicit destination. Queries replay `-C`, `-c`, `--git-dir`,
   etc., so they see the same repository and config as the real command.
5. Blocked: audit entry, banner on stderr, exit 1. Allowed: audit entry,
   then `exec()` of the real git with the original (byte-exact) arguments.

Every invocation is appended to the JSONL audit log
(`~/.local/share/wrapper-guard/audit.log`, override with
`WRAPPER_GUARD_LOG_DIR`), with credentials in URLs and `Authorization`
headers redacted.

## Installation

```bash
# Build and install to ~/.local/bin/git (always rebuilds from source)
./tools/rust/git-guard/install.sh

# ~/.local/bin must come before /usr/bin
export PATH="$HOME/.local/bin:$PATH"

git --wrapper-integrity        # wrapper=git-guard ...
git push --force --dry-run     # blocked
```

`./tools/rust/git-guard/uninstall.sh` removes it (only after confirming via
`--wrapper-integrity` that the file really is git-guard).

## Emergency bypass

Non-hardened: run the real git by absolute path (printed in the block
message), e.g. `/usr/bin/git push --force-with-lease origin feature`.
Hardened: `sudo /usr/lib/wrapper-guard/git.real <command>`.

## Known limitations

- **Anything git executes in hardened mode inherits the `wrapper-guard`
  group**: hooks, `core.pager`, `core.sshCommand`, credential helpers,
  `rebase --exec`, external `git-<name>` commands. A process that can write
  a hook or repository config can therefore reach
  `/usr/lib/wrapper-guard/git.real` directly. The setgid design cannot close
  this; treat hardened mode as a strong speed bump, not a sandbox.
- Hooks can still be disabled by editing `.git/config` or deleting
  `.git/hooks/*` with ordinary file tools; only the git-command routes are
  blocked. Hook-framework switches such as pre-commit's `SKIP=` variable are
  not inspected.
- Bare `git push` relies on git's own answers (`symbolic-ref`, `@{push}`);
  if those queries fail (no repository, no upstream), only explicit checks
  apply and git itself decides.
- Protected branch names are fixed (`main`, `master`) and case-sensitive.

## Development

```bash
# From the repository root (container-first)
docker compose --profile ci run --rm -w /app/tools/rust/git-guard rust-ci \
  bash -c "cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test"
```

`tests/cli.rs` runs the built binary against a fake `git` script to cover
exit-code, stdin, and nested-invocation passthrough end to end.

## License

Part of the template-repo project. See repository LICENSE file.
