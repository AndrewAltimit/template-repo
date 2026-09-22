//! Parsing tests against realistic AI-response fixtures.

use code_parser::{CodeBlock, CodeParser, CodeParserError, HunkLine};

const MULTI_FILE: &str = include_str!("fixtures/multi_file.md");
const NESTED: &str = include_str!("fixtures/nested_markdown.md");
const SEARCH_REPLACE: &str = include_str!("fixtures/search_replace.md");
const UNIFIED_DIFF: &str = include_str!("fixtures/unified_diff.md");

fn names(blocks: &[CodeBlock]) -> Vec<Option<&str>> {
    blocks.iter().map(|b| b.filename.as_deref()).collect()
}

#[test]
fn multi_file_response() {
    let blocks = CodeParser::extract_code_blocks(MULTI_FILE);
    assert_eq!(
        names(&blocks),
        vec![
            Some("src/config.rs"),
            Some("src/main.rs"),
            None, // "Run it with:" must not inherit src/main.rs
            Some("app.toml"),
            Some("scripts/setup.sh"),
        ]
    );
    let langs: Vec<&str> = blocks.iter().map(|b| b.language.as_str()).collect();
    assert_eq!(langs, vec!["rust", "rust", "bash", "toml", "bash"]);
    assert!(blocks.iter().all(|b| b.terminated));

    // Indented fence (inside a list item): fence indentation is stripped, relative
    // indentation is kept.
    assert_eq!(
        blocks[3].content,
        "name = \"demo\"\n    nested_indent = true"
    );
    assert_eq!(blocks[3].info, "toml app.toml");
    assert!(blocks[0].content.starts_with("use std::path::Path;"));
    assert!(!blocks[0].content.ends_with('\n'));
}

#[test]
fn nested_fences() {
    let blocks = CodeParser::extract_code_blocks(NESTED);
    assert_eq!(blocks.len(), 2);

    assert_eq!(blocks[0].language, "markdown");
    assert_eq!(blocks[0].filename.as_deref(), Some("docs/USAGE.md"));
    assert!(blocks[0].content.contains("```python\nimport demo"));
    assert!(blocks[0].content.ends_with("Done."));

    // Same-length nested fence inside a markdown block.
    assert!(blocks[1].content.contains("```bash\nmake test\n```"));
    assert!(blocks[1].content.ends_with("End of example."));
}

#[test]
fn tilde_fences_and_crlf() {
    let response = "Save as `a.py`:\r\n\r\n~~~\r\nprint('hi')\r\n```\r\nnot a close\r\n~~~\r\n";
    let blocks = CodeParser::extract_code_blocks(response);
    assert_eq!(blocks.len(), 1);
    assert_eq!(blocks[0].filename.as_deref(), Some("a.py"));
    assert_eq!(blocks[0].language, "python");
    assert_eq!(blocks[0].content, "print('hi')\n```\nnot a close");
}

#[test]
fn unterminated_block_is_flagged() {
    let response = "Create `x.rs`:\n```rust\nfn main() {\n    // truncated";
    let blocks = CodeParser::extract_code_blocks(response);
    assert_eq!(blocks.len(), 1);
    assert!(!blocks[0].terminated);
    assert_eq!(blocks[0].content, "fn main() {\n    // truncated");
}

#[test]
fn inline_backticks_do_not_open_blocks() {
    let response = "Use ```inline``` sparingly.\n\n```js\nlet a = 1;\n```";
    let blocks = CodeParser::extract_code_blocks(response);
    assert_eq!(blocks.len(), 1);
    assert_eq!(blocks[0].content, "let a = 1;");
}

#[test]
fn filename_from_first_line_comment() {
    let response = "```python\n# file: pkg/mod.py\nx = 1\n```\n\n```\n<!-- path: web/index.html -->\n<p/>\n```";
    let blocks = CodeParser::extract_code_blocks(response);
    assert_eq!(
        names(&blocks),
        vec![Some("pkg/mod.py"), Some("web/index.html")]
    );
    assert_eq!(blocks[1].language, "html");
}

#[test]
fn multibyte_prose_before_block_does_not_panic() {
    // The old implementation sliced 500 bytes back from the fence, which could split
    // a multi-byte character.
    let prose = "\u{00e9}\u{4e2d}\u{1f600}".repeat(200);
    let response = format!("{prose}\nCreate `a.txt`:\n```\nx\n```");
    let blocks = CodeParser::extract_code_blocks(&response);
    assert_eq!(blocks[0].filename.as_deref(), Some("a.txt"));
}

#[test]
fn search_replace_blocks() {
    let edits = CodeParser::parse_edit_instructions(SEARCH_REPLACE);
    let files: Vec<&str> = edits.iter().map(|e| e.file.as_str()).collect();
    assert_eq!(
        files,
        vec!["src/app.py", "src/app.py", "tests/test_app.py", "setup.cfg"]
    );

    assert_eq!(
        edits[0].old,
        "def greet(name):\n    return \"Hello \" + name"
    );
    assert_eq!(edits[1].new, "VERSION = \"1.1\"");
    assert!(edits[2].old.is_empty());
    assert!(edits[2].new.starts_with("from app import greet"));
    assert_eq!(edits[3].old, "version = 1.0");
    assert_eq!(edits[3].new, "version = 1.1");
}

#[test]
fn search_replace_without_file_is_dropped() {
    let response = "Some change:\n<<<<<<< SEARCH\na\n=======\nb\n>>>>>>> REPLACE\n";
    assert!(CodeParser::parse_edit_instructions(response).is_empty());
    let unterminated = "f.py\n<<<<<<< SEARCH\na\n=======\nb\n";
    assert!(CodeParser::parse_edit_instructions(unterminated).is_empty());
}

#[test]
fn legacy_inline_edit_forms() {
    let edits = CodeParser::parse_edit_instructions(
        r#"In file `main.py`, change `print("hello")` to `print("goodbye")`"#,
    );
    assert_eq!(edits.len(), 1);
    assert_eq!(edits[0].file, "main.py");
    assert_eq!(edits[0].old, r#"print("hello")"#);
    assert_eq!(edits[0].new, r#"print("goodbye")"#);

    let edits = CodeParser::parse_edit_instructions(
        r#"Update config.py: replace "DEBUG = True" with "DEBUG = False""#,
    );
    assert_eq!(edits.len(), 1);
    assert_eq!(edits[0].file, "config.py");
}

#[test]
fn unified_diff_from_response() {
    let blocks = CodeParser::extract_code_blocks(UNIFIED_DIFF);
    assert_eq!(blocks.len(), 1);
    assert!(blocks[0].is_diff());

    let patches = CodeParser::extract_patches(UNIFIED_DIFF);
    assert_eq!(patches.len(), 2);
    assert_eq!(patches[0].path(), Some("src/app.py"));
    assert_eq!(patches[0].hunks.len(), 2);
    assert_eq!(patches[0].hunks[1].old_start, 10);
    assert_eq!(
        patches[0].hunks[1].lines.last(),
        Some(&HunkLine::Added("    return 0".to_string()))
    );
    assert!(patches[1].is_new_file());
    assert_eq!(patches[1].path(), Some("CHANGELOG.md"));

    // Also parses straight from the prose-wrapped response.
    assert_eq!(
        CodeParser::parse_unified_diff(UNIFIED_DIFF).unwrap(),
        patches
    );
}

#[test]
fn apply_diff_in_memory() {
    let patches = CodeParser::extract_patches(UNIFIED_DIFF);
    let original = "import os\n\ndef greet(name):\n    return \"Hello \" + name\n\n\n\n\n\
                    def main():\n    greet(\"world\")\n";
    let updated = patches[0].apply(original).unwrap();
    assert_eq!(
        updated,
        "import os\n\ndef greet(name: str) -> str:\n    return f\"Hello {name}\"\n\n\n\n\n\
         def main():\n    greet(\"world\")\n    return 0\n"
    );
    assert!(matches!(
        patches[0].apply("unrelated\n"),
        Err(CodeParserError::PatchConflict { hunk: 1, .. })
    ));
}

#[test]
fn sanitize_filename_public_contract() {
    assert_eq!(
        CodeParser::sanitize_filename("src/main.rs").unwrap(),
        "src/main.rs"
    );
    assert_eq!(
        CodeParser::sanitize_filename("./test.py").unwrap(),
        "test.py"
    );
    assert!(CodeParser::sanitize_filename("/etc/passwd").is_err());
    assert!(CodeParser::sanitize_filename("C:\\Windows\\system32").is_err());
    assert!(CodeParser::sanitize_filename("../secret.txt").is_err());
    assert!(CodeParser::sanitize_filename("foo/../../../etc/passwd").is_err());
    assert!(CodeParser::sanitize_filename("..\\..\\evil").is_err());
    assert!(CodeParser::sanitize_filename(".git/hooks/post-checkout").is_err());
    assert!(CodeParser::sanitize_filename("file\x00name").is_err());
    assert!(CodeParser::sanitize_filename("file\nname").is_err());
}

#[test]
fn infer_language_public_contract() {
    assert_eq!(CodeParser::infer_language("test.py"), "python");
    assert_eq!(CodeParser::infer_language("test.rs"), "rust");
    assert_eq!(CodeParser::infer_language("test.js"), "javascript");
    assert_eq!(CodeParser::infer_language("test.unknown"), "text");
}
