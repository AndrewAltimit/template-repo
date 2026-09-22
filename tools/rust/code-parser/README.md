# code-parser

> A Rust library for parsing and applying code changes from AI agent responses.

AI responses deliver changes in three shapes. This crate parses all of them and can
apply them safely to a directory tree:

| Shape | Parse | Apply |
|-------|-------|-------|
| Fenced code blocks (whole files) | `CodeParser::extract_code_blocks` | `CodeParser::apply_code_blocks_with` |
| SEARCH/REPLACE blocks and "change X to Y" sentences | `CodeParser::parse_edit_instructions` | `CodeParser::apply_edit_instructions` / `CodeParser::apply_edit` |
| Unified diffs | `CodeParser::parse_unified_diff` / `CodeParser::extract_patches` | `CodeParser::apply_patches` / `FilePatch::apply` |

## Installation

```toml
[dependencies]
code-parser = { path = "tools/rust/code-parser" }

# Parsing only, without the file-system helpers
code-parser = { path = "tools/rust/code-parser", default-features = false }
```

The `fs` feature (default) enables the `apply_*` functions. It only uses `std`.

## Code blocks

```rust
use code_parser::CodeParser;

let response = "Create `src/utils.py`:\n\n```python\ndef helper():\n    pass\n```\n";
let blocks = CodeParser::extract_code_blocks(response);
assert_eq!(blocks[0].language, "python");
assert_eq!(blocks[0].filename.as_deref(), Some("src/utils.py"));
assert!(blocks[0].terminated);
```

Fence handling:

- Backtick and tilde fences of any length. A closing fence must use the same
  character, be at least as long, and have no info string.
- Nested fences: a ```` ````markdown ```` block can contain ```` ``` ```` blocks, and a
  ```` ```markdown ```` block can contain ```` ```python ```` ... ```` ``` ```` pairs.
- Indented fences (for example inside list items). The fence indentation is removed
  from the content. Other indentation is kept.
- CRLF input. Content is normalized to `\n`, blank lines at the start and end are
  dropped, and there is no trailing newline.
- A block with no closing fence is returned with `terminated == false`. Apply skips
  it by default because the response was probably truncated.

Filename detection, in order of preference:

1. The fence info string: ```` ```rust src/lib.rs ````, ```` ```rust:src/lib.rs ````,
   ```` ```src/lib.rs ````, or ```` ```rust title="src/lib.rs" ```` (`file=`, `path=`,
   and `filename=` also work).
2. A comment on the block's first line: `# file: x.py`, `// path: x.rs`,
   `<!-- filename: x.html -->`.
3. The three non-blank prose lines above the block. Recognized forms include
   ``Create `x.py`:``, ``### `src/main.rs` ``, ``**File:** `a.rs` ``,
   ``Here's the updated `config.yaml`:``, and `in the file `x``.

If none of these match, `filename` is `None`. A block never inherits the filename of
an earlier block. This stops a "run it with" shell snippet from overwriting the file
shown before it.

If the info string has no language, the language is inferred from the filename
(`CodeParser::infer_language`). If there is no filename either, it is `"text"`.

## Edit instructions

```rust
use code_parser::CodeParser;

let response = "\
src/app.py
<<<<<<< SEARCH
VERSION = \"1.0\"
=======
VERSION = \"1.1\"
>>>>>>> REPLACE
";
let edits = CodeParser::parse_edit_instructions(response);
assert_eq!(edits[0].file, "src/app.py");

let updated = CodeParser::apply_edit("VERSION = \"1.0\"\n", &edits[0]).unwrap();
assert_eq!(updated, "VERSION = \"1.1\"\n");
```

- SEARCH/REPLACE blocks (Aider style) take the filename from the line above the block
  or from the enclosing fence's info string. Several blocks in a row inherit the
  previous block's file. An empty SEARCH section creates the file or appends to it.
- Inline sentences are also parsed: ``In file `main.py`, change `a` to `b` `` and
  `Update config.py: replace "a" with "b"`.
- `apply_edit` requires exactly one match. Otherwise it returns `SearchNotFound` or
  `AmbiguousEdit`. It keeps CRLF line endings, and if there is no exact match it
  retries line by line with trailing whitespace ignored.

## Unified diffs

```rust
use code_parser::CodeParser;

let diff = "--- a/x.txt\n+++ b/x.txt\n@@ -1,2 +1,2 @@\n a\n-b\n+c\n";
let patches = CodeParser::parse_unified_diff(diff).unwrap();
assert_eq!(patches[0].path(), Some("x.txt"));
assert_eq!(patches[0].apply("a\nb\n").unwrap(), "a\nc\n");
```

The parser accepts the common flaws in AI-written diffs:

- Hunk headers with no numbers (`@@ ... @@`) or wrong counts.
- Blank context lines that lost their leading space.
- Line numbers that have drifted. Each hunk is matched to the nearest position,
  first exactly and then with trailing whitespace ignored.

It supports git `a/` and `b/` prefixes, `/dev/null` for created and deleted files,
renames, `\ No newline at end of file`, and CRLF files. It ignores any prose around
the diff.

## Applying to disk (`fs` feature)

```rust,no_run
use code_parser::{ApplyOptions, CodeParser};
use std::path::Path;

let response = std::fs::read_to_string("response.md").unwrap();
let blocks = CodeParser::extract_code_blocks(&response);
let report = CodeParser::apply_code_blocks_with(
    &blocks,
    Path::new("."),
    ApplyOptions { dry_run: true, ..ApplyOptions::default() },
)
.unwrap();
for entry in &report.entries {
    println!("{}: {}", entry.path, entry.status);
}
```

- `apply_code_blocks_with`, `apply_patches`, and `apply_edit_instructions` return an
  `ApplyReport`. It has one `ApplyEntry { path, status }` per operation, with status
  `Created`, `Modified`, `Unchanged`, `Deleted`, `Skipped(reason)`, or
  `Failed(error)`. A failure for one file does not stop the others. A top-level
  `Err` means only that the base directory could not be created or resolved.
- Diff blocks passed to `apply_code_blocks_with` are applied as patches. They are
  never written to disk as file content.
- Later operations in the same run see the results of earlier ones, including in
  `dry_run` mode.
- Files are written through a temp file and a rename, and existing file permissions
  are kept. If a file uses CRLF, a full-file replacement is converted to CRLF.
- The older `apply_code_blocks` and `extract_and_apply` still return a
  `HashMap<path, status string>` ("created", "modified", "unchanged", "skipped: ...",
  "error: ...").

## Security

Paths in AI responses are untrusted. `CodeParser::sanitize_filename`:

- Rejects absolute paths: `/x`, `C:\x`, `c:x`, `\\server\share`, and `~/x`.
- Rejects any `..` component. Backslashes count as separators.
- Rejects any path inside `.git`, since writing there, for example to hooks, can
  execute code.
- Rejects control characters, `:` (which also blocks NTFS alternate data streams),
  empty paths, and paths ending in a separator.
- Normalizes what remains: removes `./` and `//` and uses `/` separators.

When writing, the base directory is canonicalized. Every existing path component that
is a symlink must resolve inside the base directory, and dangling symlinks are
rejected. The crate does not defend against another process swapping directories for
symlinks during the write (a time-of-check to time-of-use race).

## API reference

Types: `CodeBlock`, `EditInstruction`, `FilePatch`, `Hunk`, `HunkLine`,
`CodeParserError` (`#[non_exhaustive]`), and `Result`. With `fs`, also
`ApplyOptions`, `ApplyReport`, `ApplyEntry`, and `ApplyStatus`.

`CodeParser` functions:

| Function | Notes |
|----------|-------|
| `extract_code_blocks(response)` | All fenced blocks |
| `infer_language(filename)` | Extension or well-known name to language tag |
| `sanitize_filename(filename)` | Validate and normalize a relative path |
| `parse_edit_instructions(response)` | SEARCH/REPLACE and inline edits |
| `apply_edit(content, edit)` | In-memory edit |
| `parse_unified_diff(text)` | Patches from diff text |
| `extract_patches(response)` | Patches from all diff blocks |
| `apply_code_blocks(blocks, base)` | Legacy status map (`fs`) |
| `apply_code_blocks_with(blocks, base, opts)` | `ApplyReport` (`fs`) |
| `apply_patches(patches, base, opts)` | `ApplyReport` (`fs`) |
| `apply_edit_instructions(edits, base, opts)` | `ApplyReport` (`fs`) |
| `extract_and_apply(response, base)` | Extract and apply with the legacy map (`fs`) |

## License

Part of the template-repo project. See repository LICENSE file.
