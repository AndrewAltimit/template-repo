//! What git-guard blocks, and why.
//!
//! The policy is intentionally narrow: it protects the review workflow, not
//! the local working tree.
//!
//! 1. **Force pushes** - `--force`/`-f` (also inside short-flag clusters such
//!    as `-uf`), `--force-with-lease`, `--force-if-includes`, `+refspec`,
//!    `--mirror`, and any configured `remote.<name>.push` refspec with `+`.
//! 2. **Skipping hooks** - `--no-verify` on any command, `-n` on `commit`,
//!    and hook redirection via `core.hooksPath` or config includes injected
//!    with `-c`, `--config-env`, `GIT_CONFIG_PARAMETERS`,
//!    `GIT_CONFIG_KEY_<n>`, or written with `git config`.
//! 3. **Pushes that can update a protected branch** (`main`, `master`) -
//!    explicit refspecs (`main`, `HEAD:main`, `:main`, `refs/heads/main`,
//!    wildcards), `HEAD` / bare `git push` while on or tracking a protected
//!    branch, `--all`/`--branches`, `--prune`, the `:` matching refspec,
//!    `push.default=matching`, and low-level `send-pack` / `http-push`.
//!
//! Long options are matched the way git's parse-options matches them,
//! including unique-prefix abbreviations (`--forc`, `--no-verif`); an
//! ambiguous abbreviation is blocked too (git would reject it anyway).
//! Aliases are expanded (recursively) before checking.

use crate::cli::{self, Invocation, normalize_config_key};

/// Branches that must only change through pull requests.
pub const PROTECTED_BRANCHES: &[&str] = &["main", "master"];

/// Maximum alias expansion depth (git itself detects loops).
const MAX_ALIAS_DEPTH: usize = 16;

const FORCE_WHY: &str = "Force push can overwrite remote history";
const NO_VERIFY_WHY: &str = "Skipping hooks bypasses pre-commit/pre-push checks";
const HOOKS_WHY: &str = "Redirecting hooks bypasses pre-commit/pre-push checks";
const PROTECTED_WHY: &str = "Direct push to a protected branch bypasses PR review";

/// A blocked operation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Violation {
    /// What triggered the block (flag, refspec, ...).
    pub what: String,
    /// Why it is blocked.
    pub why: &'static str,
}

impl Violation {
    fn new(what: impl Into<String>, why: &'static str) -> Self {
        Self {
            what: what.into(),
            why,
        }
    }
}

/// Information the policy needs from the repository. Implemented by
/// [`crate::query::RealGit`]; tests use a fake.
pub trait GitContext {
    /// Value of `alias.<name>`, if defined.
    fn alias(&self, name: &str) -> Option<String>;
    /// Short name of the checked-out branch (`None` when detached).
    fn current_branch(&self) -> Option<String>;
    /// Where a bare `git push` would push, as `<remote>/<branch>`.
    fn push_destination(&self) -> Option<String>;
    /// Single config value.
    fn config_get(&self, key: &str) -> Option<String>;
    /// `(key, value)` pairs for keys matching the regex.
    fn config_get_regexp(&self, pattern: &str) -> Vec<(String, String)>;
    /// Whether the wrapper runs setgid (hardened mode).
    fn setgid_elevated(&self) -> bool;
}

/// Check a parsed invocation. `env` holds the process environment (only
/// `GIT_CONFIG_*` entries matter).
pub fn check(inv: &Invocation, env: &[(String, String)], ctx: &dyn GitContext) -> Vec<Violation> {
    let mut out = Vec::new();

    for ov in &inv.config_overrides {
        if let Some(why) = dangerous_config_key(&ov.key) {
            out.push(Violation::new(ov.origin.clone(), why));
        }
    }
    for key in env_config_keys(env) {
        if let Some(why) = dangerous_config_key(&key.0) {
            out.push(Violation::new(format!("{} ({})", key.1, key.0), why));
        }
    }

    let Some(mut sub) = inv.subcommand.clone() else {
        return out;
    };
    let mut args = inv.args.clone();

    // Expand aliases. Builtins cannot be aliased, so only unknown names are
    // looked up (keeps the common path free of extra processes).
    let mut seen = Vec::new();
    while !is_builtin(&sub) {
        if seen.len() >= MAX_ALIAS_DEPTH || seen.contains(&sub) {
            break;
        }
        let Some(expansion) = ctx.alias(&sub) else {
            break;
        };
        seen.push(sub.clone());
        if let Some(shell) = expansion.strip_prefix('!') {
            if ctx.setgid_elevated() {
                out.push(Violation::new(
                    format!("shell alias '{sub}' (!{shell})"),
                    "Shell aliases run with the wrapper-guard group in hardened mode",
                ));
            }
            return out;
        }
        let Some(mut words) = cli::split_cmdline(&expansion) else {
            out.push(Violation::new(
                format!("alias '{sub}'"),
                "Alias could not be parsed for safety checks",
            ));
            return out;
        };
        if words.is_empty() {
            break;
        }
        let first = words.remove(0);
        words.extend(args);
        args = words;
        sub = first;
    }

    match sub.as_str() {
        "push" => check_push(&args, ctx, &mut out),
        "commit" => check_commit(&args, &mut out),
        "send-pack" | "http-push" => out.push(Violation::new(
            format!("git {sub}"),
            "Low-level push commands bypass git-guard's push checks",
        )),
        "subtree" => check_subtree(&args, ctx, &mut out),
        "config" => {
            check_config_write(&args, &mut out);
            check_generic_no_verify(&args, &mut out);
        },
        _ => check_generic_no_verify(&args, &mut out),
    }
    out
}

/// Config keys that must not be injected or written: they redirect or
/// disable hooks, or pull in arbitrary config (which could do the same).
fn dangerous_config_key(key: &str) -> Option<&'static str> {
    let (section, sub, name) = normalize_config_key(key);
    match (section.as_str(), sub.is_some(), name.as_str()) {
        ("core", false, "hookspath") => Some(HOOKS_WHY),
        ("include", false, "path") | ("includeif", true, "path") => {
            Some("Config includes can redirect hooks (core.hooksPath)")
        },
        _ => None,
    }
}

/// Keys injected through the environment, with the variable they came from.
fn env_config_keys(env: &[(String, String)]) -> Vec<(String, String)> {
    let mut keys = Vec::new();
    for (name, value) in env {
        if name.starts_with("GIT_CONFIG_KEY_") {
            keys.push((value.clone(), name.clone()));
        } else if name == "GIT_CONFIG_PARAMETERS" {
            match cli::split_cmdline(value) {
                Some(entries) => {
                    for entry in entries {
                        let key = entry.split_once('=').map_or(entry.as_str(), |(k, _)| k);
                        keys.push((key.to_string(), name.clone()));
                    }
                },
                // Unparseable: fail closed if it mentions a dangerous key.
                None => {
                    let lower = value.to_ascii_lowercase();
                    if lower.contains("hookspath") {
                        keys.push(("core.hooksPath".to_string(), name.clone()));
                    }
                    if lower.contains("include") {
                        keys.push(("include.path".to_string(), name.clone()));
                    }
                },
            }
        }
    }
    keys
}

/// How a long option name (without `--`) matches a table entry, following
/// git's abbreviation rules.
fn long_matches(name: &str, option: &str, min_len: usize) -> bool {
    !name.is_empty() && name.len() >= min_len.min(option.len()) && option.starts_with(name)
}

/// `--no-verify` or an abbreviation of it (`--no-veri`). Prefixes shorter
/// than `--no-v` are ignored: they are ambiguous with every `--no-*` option.
fn is_no_verify(name: &str) -> bool {
    long_matches(name, "no-verify", 4)
}

fn check_generic_no_verify(args: &[String], out: &mut Vec<Violation>) {
    for arg in args {
        if arg == "--" {
            break;
        }
        if let Some(long) = arg.strip_prefix("--") {
            let name = long.split_once('=').map_or(long, |(n, _)| n);
            if is_no_verify(name) {
                out.push(Violation::new(arg.clone(), NO_VERIFY_WHY));
            }
        }
    }
}

/// `git commit`: `--no-verify` / `-n`, aware of options that take values
/// (so `-m -n` or `-mn` is a message, not a flag).
fn check_commit(args: &[String], out: &mut Vec<Violation>) {
    const LONG_WITH_VALUE: &[&str] = &[
        "message",
        "file",
        "author",
        "date",
        "reuse-message",
        "reedit-message",
        "fixup",
        "squash",
        "template",
        "cleanup",
        "trailer",
        "pathspec-from-file",
    ];
    let mut i = 0;
    while i < args.len() {
        let arg = &args[i];
        i += 1;
        if arg == "--" {
            break;
        }
        if let Some(long) = arg.strip_prefix("--") {
            let (name, has_value) = long
                .split_once('=')
                .map_or((long, false), |(n, _)| (n, true));
            if is_no_verify(name) {
                out.push(Violation::new(arg.clone(), NO_VERIFY_WHY));
            }
            if !has_value && LONG_WITH_VALUE.contains(&name) {
                i += 1;
            }
        } else if let Some(cluster) = arg.strip_prefix('-')
            && !cluster.is_empty()
        {
            for (pos, c) in cluster.char_indices() {
                match c {
                    'n' => out.push(Violation::new(
                        format!("-n (--no-verify) in {arg}"),
                        NO_VERIFY_WHY,
                    )),
                    'm' | 'F' | 'C' | 'c' | 't' => {
                        if pos + c.len_utf8() == cluster.len() {
                            i += 1;
                        }
                        break;
                    },
                    // Optional values, only when attached.
                    'u' | 'S' => break,
                    _ => {},
                }
            }
        }
    }
}

/// `git push`.
fn check_push(args: &[String], ctx: &dyn GitContext, out: &mut Vec<Violation>) {
    const DANGEROUS_LONG: &[(&str, usize, &str)] = &[
        ("force", 1, FORCE_WHY),
        ("force-with-lease", 1, FORCE_WHY),
        ("force-if-includes", 1, FORCE_WHY),
        (
            "mirror",
            1,
            "Mirror push force-updates and deletes remote refs",
        ),
        ("all", 1, "Pushing all branches includes protected branches"),
        (
            "branches",
            1,
            "Pushing all branches includes protected branches",
        ),
        ("prune", 1, "Prune can delete remote branches"),
        ("no-verify", 4, NO_VERIFY_WHY),
    ];
    const LONG_WITH_VALUE: &[&str] = &["repo", "receive-pack", "exec", "push-option"];

    let mut positionals: Vec<&str> = Vec::new();
    let mut only_positional = false;
    let mut i = 0;
    while i < args.len() {
        let arg = &args[i];
        i += 1;
        if only_positional || !arg.starts_with('-') || arg == "-" {
            positionals.push(arg);
            continue;
        }
        if arg == "--" {
            only_positional = true;
            continue;
        }
        if let Some(long) = arg.strip_prefix("--") {
            let (name, has_value) = long
                .split_once('=')
                .map_or((long, false), |(n, _)| (n, true));
            let mut flagged = false;
            for &(option, min_len, why) in DANGEROUS_LONG {
                if !flagged && long_matches(name, option, min_len) {
                    out.push(Violation::new(arg.clone(), why));
                    flagged = true;
                }
            }
            if !has_value && LONG_WITH_VALUE.contains(&name) {
                i += 1;
            }
        } else {
            let cluster = &arg[1..];
            for (pos, c) in cluster.char_indices() {
                match c {
                    'f' => out.push(Violation::new(format!("-f in {arg}"), FORCE_WHY)),
                    'o' => {
                        if pos + 1 == cluster.len() {
                            i += 1;
                        }
                        break;
                    },
                    _ => {},
                }
            }
        }
    }

    let refspecs = positionals.get(1..).unwrap_or_default();
    let mut branch_cache: Option<Option<String>> = None;
    let mut current_branch = || {
        branch_cache
            .get_or_insert_with(|| ctx.current_branch())
            .clone()
    };

    if refspecs.is_empty() {
        check_implicit_push(ctx, &mut current_branch, out);
    } else {
        for spec in refspecs {
            check_refspec(spec, "", &mut current_branch, out);
        }
    }
}

/// A bare `git push [<remote>]`: what would it update?
fn check_implicit_push(
    ctx: &dyn GitContext,
    current_branch: &mut dyn FnMut() -> Option<String>,
    out: &mut Vec<Violation>,
) {
    if let Some(branch) = current_branch()
        && is_protected(&branch)
    {
        out.push(Violation::new(
            format!("push while on '{branch}'"),
            PROTECTED_WHY,
        ));
        return;
    }
    if let Some(dest) = ctx.push_destination() {
        let branch = dest.split_once('/').map_or(dest.as_str(), |(_, b)| b);
        if is_protected(branch) {
            out.push(Violation::new(
                format!("push to upstream '{dest}'"),
                PROTECTED_WHY,
            ));
        }
    }
    if ctx
        .config_get("push.default")
        .is_some_and(|v| v.eq_ignore_ascii_case("matching"))
    {
        out.push(Violation::new(
            "push.default=matching",
            "Matching push includes protected branches",
        ));
    }
    for (key, value) in ctx.config_get_regexp(r"^remote\..*\.(push|mirror)$") {
        let (_, _, name) = normalize_config_key(&key);
        if name == "mirror" {
            if is_truthy(&value) {
                out.push(Violation::new(
                    format!("{key}={value}"),
                    "Mirror push force-updates and deletes remote refs",
                ));
            }
        } else {
            check_refspec(&value, &format!(" (from {key})"), current_branch, out);
        }
    }
}

/// Check one refspec. `origin` is appended to messages (config source).
fn check_refspec(
    spec: &str,
    origin: &str,
    current_branch: &mut dyn FnMut() -> Option<String>,
    out: &mut Vec<Violation>,
) {
    let (forced, spec_body) = match spec.strip_prefix('+') {
        Some(rest) => (true, rest),
        None => (false, spec),
    };
    if forced {
        out.push(Violation::new(
            format!("+ refspec '{spec}'{origin}"),
            FORCE_WHY,
        ));
    }
    if spec_body.is_empty() || spec_body == ":" {
        out.push(Violation::new(
            format!("matching refspec '{spec}'{origin}"),
            "Matching push includes protected branches",
        ));
        return;
    }

    let dst = match spec_body.split_once(':') {
        Some((src, "")) => src.to_string(),
        Some((_, dst)) if dst == "HEAD" || dst == "@" => {
            out.push(Violation::new(
                format!("refspec '{spec}'{origin}"),
                "Pushing to the remote HEAD updates its default branch",
            ));
            return;
        },
        Some((_, dst)) => dst.to_string(),
        None if spec_body == "HEAD" || spec_body == "@" => match current_branch() {
            Some(branch) => branch,
            None => return,
        },
        None => spec_body.to_string(),
    };

    let hit = if dst.contains('*') {
        PROTECTED_BRANCHES
            .iter()
            .any(|p| glob_one_star(&dst, p) || glob_one_star(&dst, &format!("refs/heads/{p}")))
    } else {
        is_protected(&dst)
    };
    if hit {
        out.push(Violation::new(
            format!("push to '{dst}' (refspec '{spec}'){origin}"),
            PROTECTED_WHY,
        ));
    }
}

/// `git subtree push [-P <prefix>] <repository> <ref>`.
fn check_subtree(args: &[String], ctx: &dyn GitContext, out: &mut Vec<Violation>) {
    const WITH_VALUE: &[&str] = &[
        "-P",
        "--prefix",
        "-m",
        "--message",
        "-b",
        "--branch",
        "--onto",
    ];
    let mut positionals = Vec::new();
    let mut i = 0;
    while i < args.len() {
        let arg = &args[i];
        i += 1;
        if arg.starts_with('-') {
            if WITH_VALUE.contains(&arg.as_str()) {
                i += 1;
            }
            continue;
        }
        positionals.push(arg.as_str());
    }
    if positionals.first() == Some(&"push") {
        let mut current = || ctx.current_branch();
        for spec in positionals.iter().skip(2) {
            check_refspec(spec, " (git subtree push)", &mut current, out);
        }
    }
    check_generic_no_verify(args, out);
}

/// `git config` writes of hook-redirecting keys.
fn check_config_write(args: &[String], out: &mut Vec<Violation>) {
    const WITH_VALUE: &[&str] = &[
        "-f",
        "--file",
        "--blob",
        "--type",
        "--default",
        "--comment",
        "--value",
    ];
    const READ_OR_REMOVE: &[&str] = &[
        "--get",
        "--get-all",
        "--get-regexp",
        "--get-urlmatch",
        "--get-color",
        "--get-colorbool",
        "-l",
        "--list",
        "--unset",
        "--unset-all",
        "--rename-section",
        "--remove-section",
        "-e",
        "--edit",
    ];
    let mut positionals = Vec::new();
    let mut read_or_remove = false;
    let mut i = 0;
    while i < args.len() {
        let arg = &args[i];
        i += 1;
        if arg.starts_with('-') {
            if READ_OR_REMOVE.contains(&arg.as_str()) {
                read_or_remove = true;
            }
            if WITH_VALUE.contains(&arg.as_str()) {
                i += 1;
            }
            continue;
        }
        positionals.push(arg.as_str());
    }

    let (key, has_value) = match positionals.first() {
        Some(&"set") => (positionals.get(1), positionals.len() >= 3),
        Some(&("get" | "list" | "unset" | "rename-section" | "remove-section" | "edit")) => {
            (None, false)
        },
        Some(_) if !read_or_remove => (positionals.first(), positionals.len() >= 2),
        _ => (None, false),
    };
    if let Some(key) = key
        && has_value
        && let Some(why) = dangerous_config_key(key)
    {
        out.push(Violation::new(format!("git config {key}"), why));
    }
}

fn is_protected(branch: &str) -> bool {
    let name = branch
        .strip_prefix("refs/heads/")
        .or_else(|| branch.strip_prefix("heads/"))
        .unwrap_or(branch);
    PROTECTED_BRANCHES.contains(&name)
}

fn is_truthy(value: &str) -> bool {
    matches!(
        value.to_ascii_lowercase().as_str(),
        "true" | "yes" | "on" | "1" | ""
    )
}

/// Match `text` against a pattern with at most one `*` (git refspec globs).
fn glob_one_star(pattern: &str, text: &str) -> bool {
    match pattern.split_once('*') {
        Some((prefix, suffix)) => {
            text.len() >= prefix.len() + suffix.len()
                && text.starts_with(prefix)
                && text.ends_with(suffix)
        },
        None => pattern == text,
    }
}

/// Git builtins and bundled commands (these can never be aliases).
fn is_builtin(name: &str) -> bool {
    const BUILTINS: &[&str] = &[
        "add",
        "am",
        "annotate",
        "apply",
        "archive",
        "backfill",
        "bisect",
        "blame",
        "branch",
        "bugreport",
        "bundle",
        "cat-file",
        "check-attr",
        "check-ignore",
        "check-mailmap",
        "check-ref-format",
        "checkout",
        "checkout-index",
        "cherry",
        "cherry-pick",
        "citool",
        "clean",
        "clone",
        "column",
        "commit",
        "commit-graph",
        "commit-tree",
        "config",
        "count-objects",
        "credential",
        "credential-cache",
        "credential-store",
        "describe",
        "diagnose",
        "diff",
        "diff-files",
        "diff-index",
        "diff-pairs",
        "diff-tree",
        "difftool",
        "fast-export",
        "fast-import",
        "fetch",
        "fetch-pack",
        "filter-branch",
        "fmt-merge-msg",
        "for-each-ref",
        "for-each-repo",
        "format-patch",
        "fsck",
        "fsck-objects",
        "gc",
        "get-tar-commit-id",
        "grep",
        "gui",
        "hash-object",
        "help",
        "hook",
        "http-backend",
        "http-fetch",
        "http-push",
        "index-pack",
        "init",
        "init-db",
        "instaweb",
        "interpret-trailers",
        "log",
        "ls-files",
        "ls-remote",
        "ls-tree",
        "mailinfo",
        "mailsplit",
        "maintenance",
        "merge",
        "merge-base",
        "merge-file",
        "merge-index",
        "merge-one-file",
        "merge-tree",
        "mergetool",
        "mktag",
        "mktree",
        "multi-pack-index",
        "mv",
        "name-rev",
        "notes",
        "pack-objects",
        "pack-refs",
        "patch-id",
        "prune",
        "prune-packed",
        "pull",
        "push",
        "range-diff",
        "read-tree",
        "rebase",
        "receive-pack",
        "reflog",
        "refs",
        "remote",
        "repack",
        "replace",
        "replay",
        "request-pull",
        "rerere",
        "reset",
        "restore",
        "rev-list",
        "rev-parse",
        "revert",
        "rm",
        "send-email",
        "send-pack",
        "shortlog",
        "show",
        "show-branch",
        "show-index",
        "show-ref",
        "sparse-checkout",
        "stage",
        "stash",
        "status",
        "stripspace",
        "submodule",
        "subtree",
        "switch",
        "symbolic-ref",
        "tag",
        "unpack-file",
        "unpack-objects",
        "update-index",
        "update-ref",
        "update-server-info",
        "upload-archive",
        "upload-pack",
        "var",
        "verify-commit",
        "verify-pack",
        "verify-tag",
        "version",
        "whatchanged",
        "worktree",
        "write-tree",
    ];
    BUILTINS.contains(&name)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    #[derive(Default)]
    struct Fake {
        aliases: HashMap<String, String>,
        branch: Option<String>,
        push_dest: Option<String>,
        config: HashMap<String, String>,
        regexp: Vec<(String, String)>,
        setgid: bool,
    }

    impl GitContext for Fake {
        fn alias(&self, name: &str) -> Option<String> {
            self.aliases.get(name).cloned()
        }
        fn current_branch(&self) -> Option<String> {
            self.branch.clone()
        }
        fn push_destination(&self) -> Option<String> {
            self.push_dest.clone()
        }
        fn config_get(&self, key: &str) -> Option<String> {
            self.config.get(key).cloned()
        }
        fn config_get_regexp(&self, _pattern: &str) -> Vec<(String, String)> {
            self.regexp.clone()
        }
        fn setgid_elevated(&self) -> bool {
            self.setgid
        }
    }

    fn feature() -> Fake {
        Fake {
            branch: Some("feature".into()),
            push_dest: Some("origin/feature".into()),
            ..Fake::default()
        }
    }

    fn run_with(ctx: &Fake, env: &[(&str, &str)], args: &[&str]) -> Vec<Violation> {
        let args: Vec<String> = args.iter().map(|s| s.to_string()).collect();
        let env: Vec<(String, String)> = env
            .iter()
            .map(|(k, v)| (k.to_string(), v.to_string()))
            .collect();
        check(&cli::parse(&args), &env, ctx)
    }

    fn blocked(args: &[&str]) -> bool {
        !run_with(&feature(), &[], args).is_empty()
    }

    fn assert_blocked(cases: &[&[&str]]) {
        for args in cases {
            assert!(blocked(args), "expected block: git {}", args.join(" "));
        }
    }

    fn assert_allowed(cases: &[&[&str]]) {
        for args in cases {
            let v = run_with(&feature(), &[], args);
            assert!(
                v.is_empty(),
                "expected allow: git {} -> {v:?}",
                args.join(" ")
            );
        }
    }

    // ---- force push -------------------------------------------------------

    #[test]
    fn force_flags_blocked() {
        assert_blocked(&[
            &["push", "--force"],
            &["push", "-f"],
            &["push", "--force-with-lease"],
            &["push", "--force-with-lease=main:abc123"],
            &["push", "--force-if-includes"],
            &["push", "origin", "feature", "--force"],
        ]);
    }

    #[test]
    fn force_in_short_clusters_blocked() {
        assert_blocked(&[
            &["push", "-uf", "origin", "feature"],
            &["push", "-fu", "origin", "feature"],
            &["push", "-qvf"],
        ]);
        // `-o` takes a value: `-of` is push-option "f", not force.
        assert_allowed(&[&["push", "-of", "origin", "feature"]]);
        assert_allowed(&[&["push", "-o", "ci.skip", "origin", "feature"]]);
    }

    #[test]
    fn abbreviated_long_options_blocked() {
        assert_blocked(&[
            &["push", "--forc"],
            &["push", "--for"],
            &["push", "--force-w"],
            &["push", "--force-wi=main"],
            &["push", "--mirr"],
            &["push", "--no-verif"],
            &["push", "--no-ve"],
            &["commit", "--no-veri", "-m", "x"],
        ]);
        // Unrelated options that share a prefix are fine.
        assert_allowed(&[&["push", "--follow-tags", "origin", "feature"]]);
    }

    #[test]
    fn plus_refspecs_blocked() {
        assert_blocked(&[
            &["push", "origin", "+feature"],
            &["push", "origin", "+HEAD:feature"],
            &["push", "origin", "+refs/heads/x:refs/heads/x"],
        ]);
    }

    #[test]
    fn mirror_all_prune_blocked() {
        assert_blocked(&[
            &["push", "--mirror"],
            &["push", "--all", "origin"],
            &["push", "--branches", "origin"],
            &["push", "--prune", "origin", "refs/heads/*:refs/heads/*"],
        ]);
    }

    #[test]
    fn force_on_other_commands_is_fine() {
        assert_allowed(&[
            &["checkout", "--force", "feature"],
            &["clean", "-f"],
            &["fetch", "origin", "+refs/heads/*:refs/remotes/origin/*"],
            &["branch", "-f", "x", "HEAD"],
        ]);
    }

    // ---- global options ---------------------------------------------------

    #[test]
    fn global_options_before_push_do_not_hide_it() {
        assert_blocked(&[
            &["-C", "/tmp", "push", "--force"],
            &["-c", "user.name=x", "push", "-f"],
            &["--git-dir", "/r/.git", "push", "origin", "main"],
            &["--work-tree=/r", "--no-pager", "push", "--force"],
            &["--", "push", "-f"],
        ]);
    }

    // ---- no-verify / hooks ------------------------------------------------

    #[test]
    fn no_verify_blocked_everywhere() {
        assert_blocked(&[
            &["commit", "--no-verify", "-m", "x"],
            &["commit", "-n", "-m", "x"],
            &["commit", "-anm", "x"],
            &["commit", "-an", "-m", "x"],
            &["push", "--no-verify"],
            &["merge", "--no-verify", "feature"],
            &["rebase", "--no-verify", "main"],
            &["am", "--no-verify", "x.patch"],
            &["pull", "--no-verify"],
        ]);
    }

    #[test]
    fn commit_message_values_are_not_flags() {
        assert_allowed(&[
            &["commit", "-m", "-n"],
            &["commit", "-mn"],
            &["commit", "-m", "--no-verify"],
            &["commit", "--message", "--no-verify"],
            &["commit", "-F", "-n"],
            &["commit", "--", "-n"],
        ]);
    }

    #[test]
    fn short_n_is_not_no_verify_elsewhere() {
        assert_allowed(&[
            &["log", "-n", "5"],
            &["cherry-pick", "-n", "abc123"],
            &["revert", "-n", "abc123"],
            &["merge", "-n", "feature"],
            &["push", "-n", "origin", "feature"],
            &["clean", "-n"],
        ]);
    }

    #[test]
    fn hooks_path_injection_blocked() {
        assert_blocked(&[
            &["-c", "core.hooksPath=/dev/null", "commit", "-m", "x"],
            &["-c", "CORE.HOOKSPATH=/dev/null", "commit", "-m", "x"],
            &["--config-env=core.hooksPath=EMPTY", "push"],
            &["-c", "include.path=/tmp/evil", "commit"],
            &["-c", "includeIf.gitdir:/.path=/tmp/evil", "commit"],
        ]);
    }

    #[test]
    fn env_config_injection_blocked() {
        let ctx = feature();
        let v = run_with(
            &ctx,
            &[
                ("GIT_CONFIG_COUNT", "1"),
                ("GIT_CONFIG_KEY_0", "core.hooksPath"),
                ("GIT_CONFIG_VALUE_0", "/dev/null"),
            ],
            &["commit", "-m", "x"],
        );
        assert_eq!(v.len(), 1);
        let v = run_with(
            &ctx,
            &[("GIT_CONFIG_PARAMETERS", "'core.hooksPath'='/dev/null'")],
            &["commit", "-m", "x"],
        );
        assert_eq!(v.len(), 1);
        let v = run_with(
            &ctx,
            &[(
                "GIT_CONFIG_PARAMETERS",
                "'core.hookspath=/x' 'user.name'='y'",
            )],
            &["status"],
        );
        assert_eq!(v.len(), 1);
        // Harmless injected config is fine.
        let v = run_with(
            &ctx,
            &[("GIT_CONFIG_PARAMETERS", "'user.name'='bot'")],
            &["commit", "-m", "x"],
        );
        assert!(v.is_empty());
    }

    #[test]
    fn config_writes_of_hooks_path_blocked() {
        assert_blocked(&[
            &["config", "core.hooksPath", "/dev/null"],
            &["config", "--local", "core.hooksPath", "/dev/null"],
            &["config", "set", "core.hooksPath", "/dev/null"],
            &["config", "--add", "include.path", "/tmp/x"],
            &["config", "-f", ".git/config", "core.hooksPath", "x"],
        ]);
        assert_allowed(&[
            &["config", "core.hooksPath"],
            &["config", "--get", "core.hooksPath"],
            &["config", "--unset", "core.hooksPath"],
            &["config", "get", "core.hooksPath"],
            &["config", "user.name", "Bot"],
            &["config", "--list"],
        ]);
    }

    // ---- protected branches -----------------------------------------------

    #[test]
    fn explicit_protected_targets_blocked() {
        assert_blocked(&[
            &["push", "origin", "main"],
            &["push", "origin", "master"],
            &["push", "origin", "HEAD:main"],
            &["push", "origin", "feature:refs/heads/main"],
            &["push", "origin", "refs/heads/main"],
            &["push", "origin", "heads/main"],
            &["push", "origin", ":main"],
            &["push", "origin", "--delete", "main"],
            &["push", "-u", "origin", "main"],
            &["push", "origin", "feature", "main"],
            &["push", "origin", "main:"],
            &["push", "https://github.com/o/r.git", "x:main"],
            &["push", "origin", "refs/heads/*:refs/heads/*"],
            &["push", "origin", "feature:HEAD"],
            &["push", "origin", ":"],
            &["push", "--repo", "origin", "origin", "--", "main"],
        ]);
    }

    #[test]
    fn feature_pushes_allowed() {
        assert_allowed(&[
            &["push", "origin", "feature"],
            &["push", "-u", "origin", "feature"],
            &["push", "origin", "HEAD"],
            &["push", "origin", "HEAD:feature"],
            &["push", "origin", "--delete", "old-branch"],
            &["push", "origin", "main-fix"],
            &["push", "origin", "origin/main"],
            &["push", "origin", "v1.0.0"],
            &["push", "--tags", "origin"],
            &["push", "origin"],
            &["push"],
            &["push", "--push-option", "main", "origin", "feature"],
        ]);
    }

    #[test]
    fn head_resolves_to_current_branch() {
        let ctx = Fake {
            branch: Some("main".into()),
            ..Fake::default()
        };
        assert!(!run_with(&ctx, &[], &["push", "origin", "HEAD"]).is_empty());
        assert!(!run_with(&ctx, &[], &["push", "origin", "@"]).is_empty());
        assert!(!run_with(&ctx, &[], &["push"]).is_empty());
        assert!(!run_with(&ctx, &[], &["push", "origin"]).is_empty());
    }

    #[test]
    fn upstream_tracking_protected_branch_blocked() {
        let ctx = Fake {
            branch: Some("feature".into()),
            push_dest: Some("origin/main".into()),
            ..Fake::default()
        };
        assert!(!run_with(&ctx, &[], &["push"]).is_empty());
        // Explicit feature refspec does not use the upstream.
        assert!(run_with(&ctx, &[], &["push", "origin", "feature"]).is_empty());
    }

    #[test]
    fn push_config_checked_for_bare_push() {
        let matching = Fake {
            config: HashMap::from([("push.default".into(), "matching".into())]),
            ..feature()
        };
        assert!(!run_with(&matching, &[], &["push"]).is_empty());

        let forced_cfg = Fake {
            regexp: vec![(
                "remote.origin.push".into(),
                "+refs/heads/*:refs/heads/*".into(),
            )],
            ..feature()
        };
        assert!(!run_with(&forced_cfg, &[], &["push", "origin"]).is_empty());

        let mirror = Fake {
            regexp: vec![("remote.origin.mirror".into(), "true".into())],
            ..feature()
        };
        assert!(!run_with(&mirror, &[], &["push"]).is_empty());

        let benign = Fake {
            regexp: vec![(
                "remote.origin.push".into(),
                "refs/heads/feature:refs/heads/feature".into(),
            )],
            ..feature()
        };
        assert!(run_with(&benign, &[], &["push"]).is_empty());
    }

    #[test]
    fn plumbing_push_blocked() {
        assert_blocked(&[
            &["send-pack", "--force", "origin", "main"],
            &["send-pack", "origin", "feature"],
            &["http-push", "https://x/r.git", "main"],
            &["subtree", "push", "-P", "lib", "origin", "main"],
            &["subtree", "push", "--prefix", "lib", "origin", "+feature"],
        ]);
        assert_allowed(&[&["subtree", "push", "-P", "lib", "origin", "lib-split"]]);
    }

    // ---- aliases ----------------------------------------------------------

    #[test]
    fn aliases_are_expanded() {
        let ctx = Fake {
            aliases: HashMap::from([
                ("p".into(), "push --force".into()),
                ("pm".into(), "push origin main".into()),
                ("pp".into(), "p".into()),
                ("ci".into(), "commit --no-verify".into()),
                ("st".into(), "status -sb".into()),
                ("loop".into(), "loop".into()),
            ]),
            ..feature()
        };
        assert!(!run_with(&ctx, &[], &["p"]).is_empty());
        assert!(!run_with(&ctx, &[], &["pm"]).is_empty());
        assert!(!run_with(&ctx, &[], &["pp", "origin", "x"]).is_empty());
        assert!(!run_with(&ctx, &[], &["ci", "-m", "x"]).is_empty());
        assert!(!run_with(&ctx, &[], &["-C", "/r", "p"]).is_empty());
        assert!(run_with(&ctx, &[], &["st"]).is_empty());
        assert!(run_with(&ctx, &[], &["loop"]).is_empty());
        assert!(run_with(&ctx, &[], &["unknown-cmd"]).is_empty());
    }

    #[test]
    fn builtins_are_never_alias_expanded() {
        let ctx = Fake {
            aliases: HashMap::from([("status".into(), "push --force".into())]),
            ..feature()
        };
        assert!(run_with(&ctx, &[], &["status"]).is_empty());
    }

    #[test]
    fn shell_aliases_blocked_only_when_setgid() {
        let mut ctx = Fake {
            aliases: HashMap::from([("x".into(), "!git push --force".into())]),
            ..feature()
        };
        // Non-hardened: the inner `git` goes through the wrapper again.
        assert!(run_with(&ctx, &[], &["x"]).is_empty());
        ctx.setgid = true;
        assert!(!run_with(&ctx, &[], &["x"]).is_empty());
    }

    #[test]
    fn everyday_commands_allowed() {
        assert_allowed(&[
            &["status"],
            &["--version"],
            &[],
            &["commit", "-m", "fix: thing"],
            &["commit", "-am", "fix"],
            &["commit", "--amend", "--no-edit"],
            &["log", "--oneline", "-5"],
            &["diff", "--no-color"],
            &["rebase", "-i", "HEAD~3"],
            &["reset", "--hard", "HEAD~1"],
            &["tag", "-f", "v1"],
        ]);
    }

    #[test]
    fn violation_messages_are_specific() {
        let v = run_with(&feature(), &[], &["push", "origin", "HEAD:main"]);
        assert_eq!(v.len(), 1);
        assert!(v[0].what.contains("main"));
        assert_eq!(v[0].why, PROTECTED_WHY);
    }
}
