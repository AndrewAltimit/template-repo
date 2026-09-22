//! File-system application tests (`fs` feature).
#![cfg(feature = "fs")]

use std::fs;

use code_parser::{ApplyOptions, ApplyStatus, CodeBlock, CodeParser, EditInstruction};
use tempfile::TempDir;

const MULTI_FILE: &str = include_str!("fixtures/multi_file.md");
const SEARCH_REPLACE: &str = include_str!("fixtures/search_replace.md");
const UNIFIED_DIFF: &str = include_str!("fixtures/unified_diff.md");

fn read(dir: &TempDir, rel: &str) -> String {
    fs::read_to_string(dir.path().join(rel)).unwrap()
}

#[test]
fn extract_and_apply_multi_file() {
    let dir = TempDir::new().unwrap();
    let (blocks, results) = CodeParser::extract_and_apply(MULTI_FILE, dir.path());
    assert_eq!(blocks.len(), 5);
    assert_eq!(results.len(), 4, "{results:?}");
    assert_eq!(results["src/config.rs"], "created");
    assert_eq!(results["scripts/setup.sh"], "created");
    assert!(read(&dir, "src/main.rs").starts_with("mod config;"));
    assert!(read(&dir, "app.toml").ends_with("nested_indent = true\n"));

    // Re-applying identical content is a no-op.
    let (_, again) = CodeParser::extract_and_apply(MULTI_FILE, dir.path());
    assert_eq!(again["src/main.rs"], "unchanged");
}

#[test]
fn traversal_and_absolute_paths_are_blocked() {
    let dir = TempDir::new().unwrap();
    let inner = dir.path().join("work");
    let blocks = vec![
        CodeBlock::with_filename("text", "x", "../escape.txt"),
        CodeBlock::with_filename("text", "x", "/tmp/abs.txt"),
        CodeBlock::with_filename("text", "x", ".git/hooks/pre-commit"),
        CodeBlock::with_filename("text", "ok", "fine.txt"),
    ];
    let report =
        CodeParser::apply_code_blocks_with(&blocks, &inner, ApplyOptions::default()).unwrap();
    let statuses: Vec<bool> = report.entries.iter().map(|e| e.status.is_error()).collect();
    assert_eq!(statuses, vec![true, true, true, false]);
    assert!(!dir.path().join("escape.txt").exists());
    assert_eq!(read(&dir, "work/fine.txt"), "ok\n");
}

#[cfg(unix)]
#[test]
fn symlink_escape_is_blocked() {
    let outside = TempDir::new().unwrap();
    let dir = TempDir::new().unwrap();
    std::os::unix::fs::symlink(outside.path(), dir.path().join("link")).unwrap();
    std::os::unix::fs::symlink("/nonexistent/target", dir.path().join("dangling")).unwrap();

    let blocks = vec![
        CodeBlock::with_filename("text", "pwned", "link/new/evil.txt"),
        CodeBlock::with_filename("text", "pwned", "dangling"),
    ];
    let results = CodeParser::apply_code_blocks(&blocks, dir.path());
    assert!(
        results["link/new/evil.txt"].starts_with("error:"),
        "{results:?}"
    );
    assert!(results["dangling"].starts_with("error:"), "{results:?}");
    assert!(!outside.path().join("new").exists());
}

#[test]
fn unterminated_blocks_are_skipped_by_default() {
    let dir = TempDir::new().unwrap();
    let blocks = CodeParser::extract_code_blocks("Create `a.rs`:\n```rust\nfn main() {");
    let report =
        CodeParser::apply_code_blocks_with(&blocks, dir.path(), ApplyOptions::default()).unwrap();
    assert!(matches!(report.entries[0].status, ApplyStatus::Skipped(_)));
    assert!(!dir.path().join("a.rs").exists());

    let opts = ApplyOptions {
        allow_unterminated: true,
        ..ApplyOptions::default()
    };
    let report = CodeParser::apply_code_blocks_with(&blocks, dir.path(), opts).unwrap();
    assert_eq!(report.entries[0].status, ApplyStatus::Created);
}

#[test]
fn dry_run_touches_nothing() {
    let dir = TempDir::new().unwrap();
    let opts = ApplyOptions {
        dry_run: true,
        ..ApplyOptions::default()
    };
    let blocks = CodeParser::extract_code_blocks(MULTI_FILE);
    let report = CodeParser::apply_code_blocks_with(&blocks, dir.path(), opts).unwrap();
    assert_eq!(report.changed_paths().count(), 4);
    assert_eq!(fs::read_dir(dir.path()).unwrap().count(), 0);
}

#[test]
fn diff_blocks_are_applied_as_patches() {
    let dir = TempDir::new().unwrap();
    fs::create_dir_all(dir.path().join("src")).unwrap();
    fs::write(
        dir.path().join("src/app.py"),
        "import os\n\ndef greet(name):\n    return \"Hello \" + name\n\ndef main():\n    greet(\"world\")\n",
    )
    .unwrap();

    let (_, results) = CodeParser::extract_and_apply(UNIFIED_DIFF, dir.path());
    assert_eq!(results["src/app.py"], "modified", "{results:?}");
    assert_eq!(results["CHANGELOG.md"], "created");
    let app = read(&dir, "src/app.py");
    assert!(app.contains("def greet(name: str) -> str:"));
    assert!(app.ends_with("    greet(\"world\")\n    return 0\n"));
    assert_eq!(read(&dir, "CHANGELOG.md"), "# Changelog\n- typed greet\n");
}

#[test]
fn patch_delete_and_rename() {
    let dir = TempDir::new().unwrap();
    fs::write(dir.path().join("old.txt"), "a\nb\n").unwrap();
    fs::write(dir.path().join("gone.txt"), "bye\n").unwrap();
    let diff = "\
--- a/old.txt
+++ b/new.txt
@@ -1,2 +1,2 @@
 a
-b
+c
--- a/gone.txt
+++ /dev/null
@@ -1 +0,0 @@
-bye
";
    let patches = CodeParser::parse_unified_diff(diff).unwrap();
    let report = CodeParser::apply_patches(&patches, dir.path(), ApplyOptions::default()).unwrap();
    assert!(!report.has_errors(), "{report:?}");
    assert_eq!(read(&dir, "new.txt"), "a\nc\n");
    assert!(!dir.path().join("old.txt").exists());
    assert!(!dir.path().join("gone.txt").exists());
}

#[test]
fn search_replace_edits_apply_in_sequence() {
    let dir = TempDir::new().unwrap();
    fs::create_dir_all(dir.path().join("src")).unwrap();
    fs::write(
        dir.path().join("src/app.py"),
        "VERSION = \"1.0\"\r\n\r\ndef greet(name):\r\n    return \"Hello \" + name\r\n",
    )
    .unwrap();
    fs::write(dir.path().join("setup.cfg"), "[metadata]\nversion = 1.0\n").unwrap();

    let edits = CodeParser::parse_edit_instructions(SEARCH_REPLACE);
    let report =
        CodeParser::apply_edit_instructions(&edits, dir.path(), ApplyOptions::default()).unwrap();
    assert!(!report.has_errors(), "{report:?}");

    // CRLF preserved, both edits applied to the same file.
    assert_eq!(
        read(&dir, "src/app.py"),
        "VERSION = \"1.1\"\r\n\r\ndef greet(name: str) -> str:\r\n    return f\"Hello {name}\"\r\n"
    );
    assert!(read(&dir, "tests/test_app.py").starts_with("from app import greet\n"));
    assert_eq!(read(&dir, "setup.cfg"), "[metadata]\nversion = 1.1\n");
}

#[test]
fn failing_edit_is_reported_not_fatal() {
    let dir = TempDir::new().unwrap();
    fs::write(dir.path().join("a.txt"), "x x\n").unwrap();
    let edits = vec![
        EditInstruction {
            file: "a.txt".into(),
            old: "x".into(),
            new: "y".into(),
        },
        EditInstruction {
            file: "missing.txt".into(),
            old: "q".into(),
            new: "r".into(),
        },
    ];
    let report =
        CodeParser::apply_edit_instructions(&edits, dir.path(), ApplyOptions::default()).unwrap();
    assert!(report.entries.iter().all(|e| e.status.is_error()));
    assert!(report.to_status_map()["a.txt"].contains("ambiguous"));
    assert_eq!(read(&dir, "a.txt"), "x x\n");
}

#[cfg(unix)]
#[test]
fn permissions_are_preserved() {
    use std::os::unix::fs::PermissionsExt;
    let dir = TempDir::new().unwrap();
    let script = dir.path().join("run.sh");
    fs::write(&script, "echo old\n").unwrap();
    fs::set_permissions(&script, fs::Permissions::from_mode(0o755)).unwrap();

    let blocks = vec![CodeBlock::with_filename("bash", "echo new", "run.sh")];
    let results = CodeParser::apply_code_blocks(&blocks, dir.path());
    assert_eq!(results["run.sh"], "modified");
    assert_eq!(
        fs::metadata(&script).unwrap().permissions().mode() & 0o777,
        0o755
    );
}
