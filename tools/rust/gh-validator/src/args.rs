//! Command-line model of a `gh` invocation.
//!
//! `gh` uses cobra/pflag, so this parser follows pflag rules: `--flag=value`
//! or `--flag value` for long flags; short flags may be clustered (`-wb`)
//! with a value-taking flag consuming the rest of the cluster (`-bBODY`,
//! `-b=BODY`) or the next argument; `--` ends flag parsing.
//!
//! The parser records every place user *content* can enter a request
//! ("slots"): body/title/notes text, content files, and `gh api` fields and
//! input files. Each slot remembers where its value lives in the argument
//! vector so the value can be sanitized in place.
//!
//! Meaning of a short flag depends on the command: `-F` is `--body-file` for
//! `pr`/`issue`, `--notes-file` for `release`, and `--field` for `api`; `-t`
//! is `--title` except for `api` (`--template`). The command is identified
//! first with a generic pass, then the arguments are parsed with the
//! command's table.

/// What a content slot holds.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SlotKind {
    /// Markdown body text (`--body`, `--notes`): full checks.
    Body,
    /// Short text (`--title`, `--subject`, `--description`).
    Title,
    /// Plain value that is published but not rendered as markdown
    /// (`gh variable set --body`): masked and emoji-checked only.
    Plain,
    /// File whose contents become a markdown body (`--body-file`,
    /// `--notes-file`, `pr create --template`).
    BodyFile,
    /// `gh api -f key=value` / `-F key=value`.
    ApiField,
    /// `gh api -F key=@file`: file contents become the field value.
    ApiFieldFile,
    /// `gh api --input file`: raw request body.
    ApiInput,
}

impl SlotKind {
    pub fn is_file(self) -> bool {
        matches!(
            self,
            SlotKind::BodyFile | SlotKind::ApiFieldFile | SlotKind::ApiInput
        )
    }
}

/// A place in the argument vector that carries user content.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Slot {
    pub kind: SlotKind,
    /// Index of the argument holding the value.
    pub index: usize,
    /// Byte offset of the value inside that argument (`--body=` -> 7).
    pub offset: usize,
    /// For api fields: the field name (`body` in `-f body=...`).
    pub field: Option<String>,
    /// Flag as written, for messages.
    pub flag: String,
}

impl Slot {
    /// The slot's current value.
    pub fn value<'a>(&self, args: &'a [String]) -> &'a str {
        args[self.index].get(self.offset..).unwrap_or("")
    }

    /// Replace the slot's value in `args`.
    pub fn set_value(&self, args: &mut [String], value: &str) {
        let arg = &mut args[self.index];
        arg.truncate(self.offset);
        arg.push_str(value);
    }

    /// Whether the text is markdown that GitHub renders (mentions notify).
    pub fn is_markdown(&self) -> bool {
        match self.kind {
            SlotKind::Body | SlotKind::Title | SlotKind::BodyFile => true,
            SlotKind::ApiField | SlotKind::ApiFieldFile => self.is_api_text_field(),
            SlotKind::ApiInput | SlotKind::Plain => false,
        }
    }

    fn is_api_text_field(&self) -> bool {
        matches!(
            self.field.as_deref(),
            Some("body" | "title" | "description" | "message")
        )
    }
}

/// A parsed invocation.
#[derive(Debug, Clone, Default)]
pub struct Parsed {
    /// Positional arguments (index, value). `[0]` is the command.
    pub positionals: Vec<(usize, String)>,
    /// Content slots.
    pub slots: Vec<Slot>,
    /// Boolean flags that matter to policy (`editor`).
    pub editor: bool,
}

impl Parsed {
    pub fn command(&self) -> Option<&str> {
        self.positionals.first().map(|(_, s)| s.as_str())
    }

    pub fn subcommand(&self) -> Option<&str> {
        self.positionals.get(1).map(|(_, s)| s.as_str())
    }

    /// Positionals after command and subcommand.
    pub fn operands(&self) -> impl Iterator<Item = &(usize, String)> {
        self.positionals.iter().skip(2)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Role {
    /// Flag without a value.
    Bool,
    /// Value-taking flag whose value is not content.
    Value,
    /// Value-taking flag whose value is content of this kind.
    Content(SlotKind),
    /// `--editor` / `-e` (bool).
    Editor,
    /// `gh api -f` (raw string field).
    ApiRawField,
    /// `gh api -F` (typed field; `@file` reads a file).
    ApiTypedField,
}

impl Role {
    fn takes_value(self) -> bool {
        !matches!(self, Role::Bool | Role::Editor)
    }
}

/// Long flags that take a value, for every command (no content meaning).
const LONG_VALUE_FLAGS: &[&str] = &[
    "repo",
    "hostname",
    "jq",
    "json",
    "search",
    "state",
    "label",
    "assignee",
    "author",
    "base",
    "head",
    "milestone",
    "project",
    "reviewer",
    "limit",
    "add-label",
    "remove-label",
    "add-assignee",
    "remove-assignee",
    "add-reviewer",
    "remove-reviewer",
    "add-project",
    "remove-project",
    "match-head-commit",
    "author-email",
    "homepage",
    "target",
    "discussion-category",
    "notes-start-tag",
    "branch",
    "remote",
    "ref",
    "env",
    "org",
    "visibility",
    "color",
    "filename",
    "workflow",
    "commit",
    "method",
    "header",
    "preview",
    "cache",
    "sort",
    "order",
    "created",
    "event",
    "status",
    "user",
    "app",
    "field-id",
    "id",
    "owner",
    "language",
    "topic",
    "template",
];

/// Short flags that take a value (non-api commands, no content meaning).
const SHORT_VALUE_FLAGS: &[char] = &[
    'R', 'L', 'S', 's', 'q', 'l', 'a', 'A', 'B', 'H', 'm', 'p', 'r', 'j', 'T',
];

/// Short flags that take a value for `gh api`.
const API_SHORT_VALUE_FLAGS: &[char] = &['R', 'X', 'H', 'p', 'q', 't'];

fn long_role(command: Option<&str>, subcommand: Option<&str>, name: &str) -> Role {
    if let Some(role) = value_command_role(command, name) {
        return role;
    }
    if command == Some("api") {
        return match name {
            "raw-field" => Role::ApiRawField,
            "field" => Role::ApiTypedField,
            "input" => Role::Content(SlotKind::ApiInput),
            n if LONG_VALUE_FLAGS.contains(&n) => Role::Value,
            _ => Role::Bool,
        };
    }
    match name {
        "body" | "notes" | "message" => Role::Content(SlotKind::Body),
        "title" | "subject" | "description" | "desc" => Role::Content(SlotKind::Title),
        "body-file" | "notes-file" => Role::Content(SlotKind::BodyFile),
        "template" if command == Some("pr") && subcommand == Some("create") => {
            Role::Content(SlotKind::BodyFile)
        },
        "editor" => Role::Editor,
        n if LONG_VALUE_FLAGS.contains(&n) => Role::Value,
        _ => Role::Bool,
    }
}

fn short_role(command: Option<&str>, subcommand: Option<&str>, c: char) -> Role {
    if c == 'b'
        && let Some(role) = value_command_role(command, "body")
    {
        return role;
    }
    if command == Some("api") {
        return match c {
            'f' => Role::ApiRawField,
            'F' => Role::ApiTypedField,
            c if API_SHORT_VALUE_FLAGS.contains(&c) => Role::Value,
            _ => Role::Bool,
        };
    }
    if command == Some("gist") {
        return match c {
            'd' => Role::Content(SlotKind::Title),
            'f' | 'R' => Role::Value,
            _ => Role::Bool,
        };
    }
    match c {
        'b' | 'n' => Role::Content(SlotKind::Body),
        't' => Role::Content(SlotKind::Title),
        'F' => Role::Content(SlotKind::BodyFile),
        'T' if command == Some("pr") && subcommand == Some("create") => {
            Role::Content(SlotKind::BodyFile)
        },
        'e' => Role::Editor,
        c if SHORT_VALUE_FLAGS.contains(&c) => Role::Value,
        _ => Role::Bool,
    }
}

/// `gh secret set --body` is the secret itself (encrypted, never shown):
/// rewriting it would corrupt the secret. `gh variable set --body` is a
/// plain value.
fn value_command_role(command: Option<&str>, name: &str) -> Option<Role> {
    match (command, name) {
        (Some("secret"), "body") => Some(Role::Value),
        (Some("variable"), "body") => Some(Role::Content(SlotKind::Plain)),
        _ => None,
    }
}

/// Parse `args` (without argv\[0\]).
pub fn parse(args: &[String]) -> Parsed {
    // Pass 1: find command/subcommand with command-agnostic rules.
    let generic = parse_with(args, None, None);
    let command = generic.command().map(str::to_string);
    let subcommand = generic.subcommand().map(str::to_string);
    // Pass 2: command-specific flag meanings.
    parse_with(args, command.as_deref(), subcommand.as_deref())
}

fn parse_with(args: &[String], command: Option<&str>, subcommand: Option<&str>) -> Parsed {
    let mut parsed = Parsed::default();
    let mut i = 0;
    let mut flags_done = false;

    while i < args.len() {
        let arg = &args[i];
        let idx = i;
        i += 1;

        if flags_done || !arg.starts_with('-') || arg == "-" {
            parsed.positionals.push((idx, arg.clone()));
            continue;
        }
        if arg == "--" {
            flags_done = true;
            continue;
        }

        if let Some(long) = arg.strip_prefix("--") {
            let (name, inline) = match long.split_once('=') {
                Some((n, _)) => (n, true),
                None => (long, false),
            };
            let role = long_role(command, subcommand, name);
            if role == Role::Editor {
                parsed.editor = true;
            }
            if !role.takes_value() {
                continue;
            }
            let (vidx, offset) = if inline {
                (idx, 2 + name.len() + 1)
            } else if i < args.len() {
                i += 1;
                (i - 1, 0)
            } else {
                continue;
            };
            add_slot(&mut parsed, args, role, vidx, offset, arg);
            continue;
        }

        // Short flag cluster.
        let cluster = &arg[1..];
        for (pos, c) in cluster.char_indices() {
            let role = short_role(command, subcommand, c);
            if role == Role::Editor {
                parsed.editor = true;
            }
            if !role.takes_value() {
                continue;
            }
            let rest_start = 1 + pos + c.len_utf8();
            let (vidx, offset) = if rest_start < arg.len() {
                // pflag: `-b=value` strips the `=`.
                let skip_eq = usize::from(arg[rest_start..].starts_with('='));
                (idx, rest_start + skip_eq)
            } else if i < args.len() {
                i += 1;
                (i - 1, 0)
            } else {
                break;
            };
            add_slot(&mut parsed, args, role, vidx, offset, &format!("-{c}"));
            break;
        }
    }
    parsed
}

fn add_slot(
    parsed: &mut Parsed,
    args: &[String],
    role: Role,
    index: usize,
    offset: usize,
    flag: &str,
) {
    let value = args[index].get(offset..).unwrap_or("");
    let slot = |kind, offset, field: Option<&str>| Slot {
        kind,
        index,
        offset,
        field: field.map(str::to_string),
        flag: flag.to_string(),
    };
    match role {
        Role::Content(kind) => parsed.slots.push(slot(kind, offset, None)),
        Role::ApiRawField | Role::ApiTypedField => {
            let (key, eq) = match value.split_once('=') {
                Some((k, _)) => (k, true),
                None => (value, false),
            };
            let value_offset = offset + key.len() + usize::from(eq);
            let field_value = args[index].get(value_offset..).unwrap_or("");
            if role == Role::ApiTypedField && field_value.starts_with('@') {
                parsed
                    .slots
                    .push(slot(SlotKind::ApiFieldFile, value_offset + 1, Some(key)));
            } else {
                parsed
                    .slots
                    .push(slot(SlotKind::ApiField, value_offset, Some(key)));
            }
        },
        Role::Bool | Role::Value | Role::Editor => {},
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn a(s: &[&str]) -> Vec<String> {
        s.iter().map(|x| x.to_string()).collect()
    }

    fn slots(args: &[&str]) -> Vec<(SlotKind, String)> {
        let args = a(args);
        let p = parse(&args);
        p.slots
            .iter()
            .map(|s| (s.kind, s.value(&args).to_string()))
            .collect()
    }

    #[test]
    fn command_detection() {
        let p = parse(&a(&["pr", "-R", "o/r", "create", "--title", "t"]));
        assert_eq!(p.command(), Some("pr"));
        assert_eq!(p.subcommand(), Some("create"));
        let p = parse(&a(&["--version"]));
        assert_eq!(p.command(), None);
    }

    #[test]
    fn body_forms() {
        use SlotKind::*;
        assert_eq!(
            slots(&["pr", "comment", "1", "--body", "x"]),
            [(Body, "x".into())]
        );
        assert_eq!(
            slots(&["pr", "comment", "1", "--body=x=y"]),
            [(Body, "x=y".into())]
        );
        assert_eq!(
            slots(&["pr", "comment", "1", "-b", "x"]),
            [(Body, "x".into())]
        );
        assert_eq!(
            slots(&["pr", "comment", "1", "-bxyz"]),
            [(Body, "xyz".into())]
        );
        assert_eq!(
            slots(&["pr", "comment", "1", "-b=xyz"]),
            [(Body, "xyz".into())]
        );
        // Clustered with a boolean flag first (pflag semantics).
        assert_eq!(
            slots(&["issue", "create", "-wbhello"]),
            [(Body, "hello".into())]
        );
        assert_eq!(
            slots(&["issue", "create", "-wb", "hello"]),
            [(Body, "hello".into())]
        );
    }

    #[test]
    fn file_forms() {
        use SlotKind::*;
        assert_eq!(
            slots(&["pr", "create", "-F", "b.md"]),
            [(BodyFile, "b.md".into())]
        );
        assert_eq!(
            slots(&["pr", "create", "-Fb.md"]),
            [(BodyFile, "b.md".into())]
        );
        assert_eq!(
            slots(&["pr", "create", "--body-file=-"]),
            [(BodyFile, "-".into())]
        );
        assert_eq!(
            slots(&["release", "create", "v1", "-F", "n.md"]),
            [(BodyFile, "n.md".into())]
        );
        assert_eq!(
            slots(&["release", "create", "v1", "--notes-file", "n.md"]),
            [(BodyFile, "n.md".into())]
        );
        assert_eq!(
            slots(&["pr", "create", "--template", "t.md"]),
            [(BodyFile, "t.md".into())]
        );
        // issue create --template is a template *name*, not a file.
        assert!(slots(&["issue", "create", "--template", "Bug report"]).is_empty());
    }

    #[test]
    fn title_and_notes() {
        use SlotKind::*;
        assert_eq!(
            slots(&["pr", "create", "-t", "T", "-b", "B"]),
            [(Title, "T".into()), (Body, "B".into())]
        );
        assert_eq!(
            slots(&["release", "create", "v1", "-n", "N"]),
            [(Body, "N".into())]
        );
        assert_eq!(
            slots(&["pr", "merge", "1", "--subject", "S"]),
            [(Title, "S".into())]
        );
    }

    #[test]
    fn api_fields() {
        use SlotKind::*;
        let args = a(&[
            "api",
            "repos/o/r/issues/1/comments",
            "-f",
            "body=hello",
            "-Ftitle=x",
            "--field",
            "body=@b.md",
            "--raw-field=k=v",
            "--input",
            "in.json",
            "-X",
            "POST",
        ]);
        let p = parse(&args);
        let got: Vec<_> = p
            .slots
            .iter()
            .map(|s| (s.kind, s.field.clone(), s.value(&args).to_string()))
            .collect();
        assert_eq!(
            got,
            vec![
                (ApiField, Some("body".into()), "hello".into()),
                (ApiField, Some("title".into()), "x".into()),
                (ApiFieldFile, Some("body".into()), "b.md".into()),
                (ApiField, Some("k".into()), "v".into()),
                (ApiInput, None, "in.json".into()),
            ]
        );
        assert_eq!(p.positionals.len(), 2);
    }

    #[test]
    fn secret_and_variable_values() {
        assert!(slots(&["secret", "set", "X", "--body", "v@lue"]).is_empty());
        assert!(slots(&["secret", "set", "X", "-b", "v@lue"]).is_empty());
        assert_eq!(
            slots(&["variable", "set", "X", "--body", "v"]),
            [(SlotKind::Plain, "v".into())]
        );
    }

    #[test]
    fn api_template_is_not_title() {
        assert!(slots(&["api", "user", "-t", "{{.login}}"]).is_empty());
    }

    #[test]
    fn editor_detection() {
        assert!(parse(&a(&["pr", "comment", "1", "--editor"])).editor);
        assert!(parse(&a(&["issue", "comment", "1", "-e"])).editor);
        assert!(parse(&a(&["pr", "create", "-we"])).editor);
        assert!(!parse(&a(&["pr", "view", "1"])).editor);
    }

    #[test]
    fn double_dash_stops_flags() {
        let p = parse(&a(&["pr", "comment", "--", "--body", "x"]));
        assert!(p.slots.is_empty());
        assert_eq!(p.positionals.len(), 4);
    }

    #[test]
    fn set_value_rewrites_in_place() {
        let mut args = a(&["pr", "comment", "--body=old", "-bold2", "-f", "body=old3"]);
        let p = parse(&args);
        for s in &p.slots {
            s.set_value(&mut args, "new");
        }
        assert_eq!(
            args,
            a(&["pr", "comment", "--body=new", "-bnew", "-f", "body=old3"])
        );

        let mut args = a(&["api", "x", "-f", "body=old3", "-F", "k=@f.md"]);
        let p = parse(&args);
        for s in &p.slots {
            s.set_value(&mut args, "new");
        }
        assert_eq!(args, a(&["api", "x", "-f", "body=new", "-F", "k=@new"]));
    }

    #[test]
    fn missing_value_does_not_panic() {
        assert!(slots(&["pr", "comment", "--body"]).is_empty());
        assert!(slots(&["pr", "comment", "-b"]).is_empty());
        assert!(slots(&["api", "x", "-f"]).is_empty());
        let _ = parse(&a(&["-", "--", "-\u{e9}b"]));
        let _ = parse(&a(&["pr", "comment", "-\u{e9}bvalue"]));
    }
}
