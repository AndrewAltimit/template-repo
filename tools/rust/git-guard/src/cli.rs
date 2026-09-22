//! Parsing of git's *global* options (everything before the subcommand).
//!
//! Mirrors `handle_options()` in git's `git.c`: the subcommand is the first
//! argument that is not a global option or the value of one. Getting this
//! right matters for security: `git -C repo push --force` or
//! `git -c k=v push -f` must be recognised as a push.

/// Global options that take the *next* argument as their value.
const GLOBAL_OPTS_WITH_VALUE: &[&str] = &[
    "-C",
    "-c",
    "--config-env",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--attr-source",
];

/// Global options that change which repository / config git sees. They are
/// replayed when git-guard queries git for context (aliases, branches).
const CONTEXT_OPTS: &[&str] = &[
    "-C",
    "-c",
    "--config-env",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--bare",
];

/// A `-c` / `--config-env` override from the command line.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ConfigOverride {
    /// Config key as written (`core.hooksPath`).
    pub key: String,
    /// The raw option, for messages (`-c core.hooksPath=/dev/null`).
    pub origin: String,
}

/// A parsed git invocation.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Invocation {
    /// Global options (with values) that affect repository/config lookup.
    pub context_opts: Vec<String>,
    /// Config overrides given with `-c` / `--config-env`.
    pub config_overrides: Vec<ConfigOverride>,
    /// The subcommand (`push`, `commit`, an alias, ...), if any.
    pub subcommand: Option<String>,
    /// Arguments after the subcommand.
    pub args: Vec<String>,
}

/// Split `args` (without argv\[0\]) into global options, subcommand, and the
/// subcommand's arguments.
pub fn parse(args: &[String]) -> Invocation {
    let mut inv = Invocation::default();
    let mut i = 0;
    while i < args.len() {
        let arg = &args[i];
        if !arg.starts_with('-') || arg == "-" {
            inv.subcommand = Some(arg.clone());
            inv.args = args[i + 1..].to_vec();
            return inv;
        }
        if arg == "--" {
            if let Some(sub) = args.get(i + 1) {
                inv.subcommand = Some(sub.clone());
                inv.args = args[i + 2..].to_vec();
            }
            return inv;
        }

        let (name, inline_value) = match arg.split_once('=') {
            Some((n, v)) if n.starts_with("--") => (n, Some(v.to_string())),
            _ => (arg.as_str(), None),
        };

        let mut value = inline_value.clone();
        let mut consumed_next = false;
        if value.is_none() && GLOBAL_OPTS_WITH_VALUE.contains(&name) {
            value = args.get(i + 1).cloned();
            consumed_next = value.is_some();
        }

        match name {
            "-c" => {
                if let Some(v) = &value {
                    let key = v.split_once('=').map_or(v.as_str(), |(k, _)| k);
                    inv.config_overrides.push(ConfigOverride {
                        key: key.to_string(),
                        origin: format!("-c {v}"),
                    });
                }
            },
            "--config-env" => {
                if let Some(v) = &value {
                    let key = v.split_once('=').map_or(v.as_str(), |(k, _)| k);
                    inv.config_overrides.push(ConfigOverride {
                        key: key.to_string(),
                        origin: format!("--config-env {v}"),
                    });
                }
            },
            _ => {},
        }

        if CONTEXT_OPTS.contains(&name) {
            match (&inline_value, consumed_next) {
                (Some(_), _) => inv.context_opts.push(arg.clone()),
                (None, true) => {
                    inv.context_opts.push(arg.clone());
                    inv.context_opts.push(args[i + 1].clone());
                },
                (None, false) => inv.context_opts.push(arg.clone()),
            }
        }

        i += if consumed_next { 2 } else { 1 };
    }
    inv
}

/// Split an alias definition into words the way git's `split_cmdline()`
/// does: whitespace separates words, single and double quotes group, and a
/// backslash escapes the next character (outside single quotes).
///
/// Returns `None` for unbalanced quotes (git refuses such aliases too).
pub fn split_cmdline(s: &str) -> Option<Vec<String>> {
    let mut words = Vec::new();
    let mut cur = String::new();
    let mut in_word = false;
    let mut quote: Option<char> = None;
    let mut chars = s.chars();

    while let Some(c) = chars.next() {
        match (quote, c) {
            (Some('\''), '\'') | (Some('"'), '"') => quote = None,
            (Some('\''), c) => cur.push(c),
            (_, '\\') => {
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

/// Split a config key into (lower-cased section, subsection, lower-cased
/// name). Section and name are case-insensitive in git; the subsection is not.
pub fn normalize_config_key(key: &str) -> (String, Option<String>, String) {
    let Some((section, rest)) = key.split_once('.') else {
        return (key.to_ascii_lowercase(), None, String::new());
    };
    match rest.rsplit_once('.') {
        Some((sub, name)) => (
            section.to_ascii_lowercase(),
            Some(sub.to_string()),
            name.to_ascii_lowercase(),
        ),
        None => (
            section.to_ascii_lowercase(),
            None,
            rest.to_ascii_lowercase(),
        ),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn a(s: &[&str]) -> Vec<String> {
        s.iter().map(|x| x.to_string()).collect()
    }

    #[test]
    fn plain_subcommand() {
        let inv = parse(&a(&["push", "--force"]));
        assert_eq!(inv.subcommand.as_deref(), Some("push"));
        assert_eq!(inv.args, a(&["--force"]));
    }

    #[test]
    fn global_options_with_values_are_skipped() {
        let inv = parse(&a(&[
            "-C",
            "/repo",
            "-c",
            "user.name=x",
            "--git-dir",
            "/repo/.git",
            "--work-tree=/repo",
            "--no-pager",
            "push",
            "-f",
        ]));
        assert_eq!(inv.subcommand.as_deref(), Some("push"));
        assert_eq!(inv.args, a(&["-f"]));
        assert_eq!(
            inv.context_opts,
            a(&[
                "-C",
                "/repo",
                "-c",
                "user.name=x",
                "--git-dir",
                "/repo/.git",
                "--work-tree=/repo"
            ])
        );
        assert_eq!(inv.config_overrides.len(), 1);
        assert_eq!(inv.config_overrides[0].key, "user.name");
    }

    #[test]
    fn config_env_override() {
        let inv = parse(&a(&["--config-env=core.hooksPath=HP", "commit"]));
        assert_eq!(inv.config_overrides[0].key, "core.hooksPath");
        let inv = parse(&a(&["--config-env", "core.hooksPath=HP", "commit"]));
        assert_eq!(inv.config_overrides[0].key, "core.hooksPath");
        assert_eq!(inv.subcommand.as_deref(), Some("commit"));
    }

    #[test]
    fn double_dash_then_subcommand() {
        let inv = parse(&a(&["--", "push", "-f"]));
        assert_eq!(inv.subcommand.as_deref(), Some("push"));
        assert_eq!(inv.args, a(&["-f"]));
    }

    #[test]
    fn no_subcommand() {
        let inv = parse(&a(&["--version"]));
        assert_eq!(inv.subcommand, None);
        let inv = parse(&a(&["-C"]));
        assert_eq!(inv.subcommand, None);
    }

    #[test]
    fn split_cmdline_quotes() {
        assert_eq!(
            split_cmdline("push --force").unwrap(),
            a(&["push", "--force"])
        );
        assert_eq!(
            split_cmdline(r#"commit -m "two words" --no-verify"#).unwrap(),
            a(&["commit", "-m", "two words", "--no-verify"])
        );
        assert_eq!(
            split_cmdline(r"push '--for''ce' x\ y").unwrap(),
            a(&["push", "--force", "x y"])
        );
        assert!(split_cmdline("push 'unterminated").is_none());
        assert_eq!(split_cmdline("  ").unwrap(), Vec::<String>::new());
    }

    #[test]
    fn config_key_normalization() {
        assert_eq!(
            normalize_config_key("Core.HooksPath"),
            ("core".into(), None, "hookspath".into())
        );
        assert_eq!(
            normalize_config_key("includeIf.gitdir:~/X/.path"),
            (
                "includeif".into(),
                Some("gitdir:~/X/".into()),
                "path".into()
            )
        );
        assert_eq!(
            normalize_config_key("remote.Origin.Push"),
            ("remote".into(), Some("Origin".into()), "push".into())
        );
    }
}
