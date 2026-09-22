//! `gh` alias resolution.
//!
//! `gh alias set c 'pr comment 1 --body "$1"'` would otherwise hide a
//! content-posting command behind a name the wrapper does not recognise.
//! For any top-level command that is not a gh builtin, the alias table in
//! gh's `config.yml` is consulted and the invocation is expanded exactly as
//! gh would (positional `$N` substitution, otherwise append), so the
//! expanded command is validated and then executed directly.

use std::path::PathBuf;

/// Top-level gh commands (including cobra aliases such as `cs`, `ext`).
const BUILTINS: &[&str] = &[
    "accessibility",
    "a11y",
    "agent-task",
    "alias",
    "api",
    "attestation",
    "auth",
    "browse",
    "cache",
    "co",
    "codespace",
    "cs",
    "completion",
    "config",
    "copilot",
    "extension",
    "extensions",
    "ext",
    "gist",
    "gists",
    "gpg-key",
    "help",
    "issue",
    "label",
    "org",
    "pr",
    "preview",
    "project",
    "release",
    "repo",
    "ruleset",
    "rs",
    "run",
    "search",
    "secret",
    "ssh-key",
    "status",
    "variable",
    "workflow",
    "version",
];

/// Whether `name` is a builtin top-level command.
pub fn is_builtin(name: &str) -> bool {
    BUILTINS.contains(&name)
}

/// How a non-builtin command resolves.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Resolution {
    /// Expanded argument vector (replaces the whole invocation).
    Expanded(Vec<String>),
    /// Shell alias (`!cmd`).
    Shell(String),
    /// Not an alias: an extension or a typo.
    Unknown,
}

/// Resolve `args[cmd_index]` against gh's alias table.
pub fn resolve(args: &[String], cmd_index: usize) -> Resolution {
    match lookup(&args[cmd_index]) {
        Some(expansion) => resolve_with(args, cmd_index, &expansion),
        None => Resolution::Unknown,
    }
}

/// Expansion logic, separated from config lookup for testing.
pub fn resolve_with(args: &[String], cmd_index: usize, expansion: &str) -> Resolution {
    if let Some(shell) = expansion.strip_prefix('!') {
        return Resolution::Shell(shell.to_string());
    }
    let rest = &args[cmd_index + 1..];
    // Mirrors gh's ExpandAlias: substitute $N while the expansion still
    // contains '$'; otherwise append the argument.
    let mut exp = expansion.to_string();
    let mut extra = Vec::new();
    for (i, arg) in rest.iter().enumerate() {
        if exp.contains('$') {
            exp = exp.replace(&format!("${}", i + 1), arg);
        } else {
            extra.push(arg.clone());
        }
    }
    let Some(mut words) = shell_split(&exp) else {
        return Resolution::Unknown;
    };
    words.extend(extra);
    let mut out = args[..cmd_index].to_vec();
    out.extend(words);
    Resolution::Expanded(out)
}

/// gh's alias expansion string for `name`, from its config file.
fn lookup(name: &str) -> Option<String> {
    let content = std::fs::read_to_string(gh_config_path()?).ok()?;
    let doc: serde_yaml::Value = serde_yaml::from_str(&content).ok()?;
    doc.get("aliases")?.get(name)?.as_str().map(str::to_string)
}

/// Location of gh's `config.yml`, following gh's own rules.
fn gh_config_path() -> Option<PathBuf> {
    let var = |k: &str| std::env::var_os(k).filter(|v| !v.is_empty());
    let dir = if let Some(dir) = var("GH_CONFIG_DIR") {
        PathBuf::from(dir)
    } else if let Some(xdg) = var("XDG_CONFIG_HOME") {
        PathBuf::from(xdg).join("gh")
    } else if cfg!(windows) {
        PathBuf::from(var("APPDATA")?).join("GitHub CLI")
    } else {
        PathBuf::from(var("HOME")?).join(".config").join("gh")
    };
    Some(dir.join("config.yml"))
}

/// POSIX-shell-like word splitting (single/double quotes, backslash).
fn shell_split(s: &str) -> Option<Vec<String>> {
    let mut words = Vec::new();
    let mut cur = String::new();
    let mut in_word = false;
    let mut quote: Option<char> = None;
    let mut chars = s.chars().peekable();
    while let Some(c) = chars.next() {
        match (quote, c) {
            (Some(q), c) if c == q => quote = None,
            (Some('\''), c) => cur.push(c),
            (Some('"'), '\\') => match chars.peek() {
                Some(&n) if matches!(n, '"' | '\\' | '$' | '`') => {
                    cur.push(n);
                    chars.next();
                },
                _ => cur.push('\\'),
            },
            (None, '\\') => {
                cur.push(chars.next()?);
                in_word = true;
            },
            (None, '\'' | '"') => {
                quote = Some(c);
                in_word = true;
            },
            (None, c) if c.is_whitespace() => {
                if in_word {
                    words.push(std::mem::take(&mut cur));
                    in_word = false;
                }
            },
            (_, c) => {
                cur.push(c);
                in_word = true;
            },
        }
    }
    if quote.is_some() {
        return None;
    }
    if in_word {
        words.push(cur);
    }
    Some(words)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn a(s: &[&str]) -> Vec<String> {
        s.iter().map(|x| x.to_string()).collect()
    }

    #[test]
    fn builtins() {
        assert!(is_builtin("pr"));
        assert!(is_builtin("api"));
        assert!(!is_builtin("c"));
    }

    #[test]
    fn positional_substitution() {
        let r = resolve_with(
            &a(&["c", "42", "hello world"]),
            0,
            "pr comment $1 --body \"$2\"",
        );
        assert_eq!(
            r,
            Resolution::Expanded(a(&["pr", "comment", "42", "--body", "hello world"]))
        );
    }

    #[test]
    fn appended_arguments() {
        let r = resolve_with(&a(&["co", "12", "--force"]), 0, "pr checkout");
        assert_eq!(
            r,
            Resolution::Expanded(a(&["pr", "checkout", "12", "--force"]))
        );
    }

    #[test]
    fn shell_alias() {
        assert_eq!(
            resolve_with(&a(&["x"]), 0, "!echo hi"),
            Resolution::Shell("echo hi".into())
        );
    }

    #[test]
    fn unbalanced_quotes_are_unknown() {
        assert_eq!(
            resolve_with(&a(&["x"]), 0, "pr comment 'oops"),
            Resolution::Unknown
        );
    }

    #[test]
    fn shell_split_rules() {
        assert_eq!(
            shell_split(r#"a "b \"c\"" 'd e' f\ g"#).unwrap(),
            a(&["a", "b \"c\"", "d e", "f g"])
        );
    }
}
