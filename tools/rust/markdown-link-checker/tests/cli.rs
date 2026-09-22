//! End-to-end tests of the `md-link-checker` binary against fixture trees.

mod common;

use std::collections::BTreeSet;
use std::path::Path;
use std::process::{Command, Output};

use serde_json::Value;

fn run(dir: &Path, args: &[&str]) -> Output {
    Command::new(common::binary())
        .arg(dir)
        .arg("--root")
        .arg(dir)
        .args(args)
        .output()
        .expect("run binary")
}

fn json(output: &Output) -> Value {
    serde_json::from_slice(&output.stdout).unwrap_or_else(|e| {
        panic!(
            "invalid JSON ({e}): {}",
            String::from_utf8_lossy(&output.stdout)
        )
    })
}

type Broken = BTreeSet<(String, String, u64)>;

/// `(file name, url, first line)` of every broken link.
fn broken(report: &Value) -> Broken {
    let mut out = BTreeSet::new();
    for file in report["results"].as_array().unwrap() {
        let name = Path::new(file["file"].as_str().unwrap())
            .file_name()
            .unwrap()
            .to_string_lossy()
            .into_owned();
        for link in file["links"].as_array().unwrap() {
            if !link["valid"].as_bool().unwrap() {
                out.insert((
                    name.clone(),
                    link["url"].as_str().unwrap().to_string(),
                    link["lines"][0].as_u64().unwrap(),
                ));
            }
        }
    }
    out
}

fn set(items: &[(&str, &str, u64)]) -> Broken {
    items
        .iter()
        .map(|&(f, u, l)| (f.to_string(), u.to_string(), l))
        .collect()
}

#[test]
fn fixture_site_internal_json() {
    let site = common::materialize("site");
    let output = run(site.path(), &["--internal-only", "--json"]);
    assert_eq!(output.status.code(), Some(1));
    let report = json(&output);

    assert_eq!(report["success"], true);
    assert_eq!(report["all_valid"], false);
    assert_eq!(report["files_checked"], 3);
    assert_eq!(report["total_links"], 20);
    assert_eq!(report["broken_links"], 8);
    assert_eq!(report["file_errors"], 0);
    assert_eq!(
        broken(&report),
        set(&[
            ("README.md", "docs/missing.md", 7),
            ("README.md", "#nope", 7),
            ("README.md", "docs/GUIDE.md", 10),
            ("README.md", "images/gone.png", 11),
            ("README.md", "images/missing.png", 13),
            ("README.md", "docs/undefined-target.md", 27),
            ("guide.md", "#duplicate-2", 14),
            ("guide.md", "../README.md#missing-section", 14),
        ])
    );

    // External links are reported as skipped, not silently dropped.
    let readme = report["results"]
        .as_array()
        .unwrap()
        .iter()
        .find(|f| f["file"].as_str().unwrap().ends_with("README.md"))
        .unwrap();
    let external = readme["links"]
        .as_array()
        .unwrap()
        .iter()
        .find(|l| l["url"] == "https://example.invalid/page")
        .unwrap();
    assert_eq!(external["skipped"], true);
    assert_eq!(external["valid"], true);
}

#[test]
fn fixture_site_human_output() {
    let site = common::materialize("site");
    let output = run(site.path(), &["--internal-only"]);
    assert_eq!(output.status.code(), Some(1));
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert!(
        stdout.contains("=== Markdown Link Check Results ==="),
        "{stdout}"
    );
    assert!(stdout.contains("Files checked: 3"), "{stdout}");
    assert!(stdout.contains("Broken links:  8"), "{stdout}");
    assert!(
        stdout.contains("README.md:7 -> docs/missing.md (File not found)"),
        "{stdout}"
    );
    assert!(
        stdout.contains("guide.md:14 -> ../README.md#missing-section (Anchor #missing-section"),
        "{stdout}"
    );
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        stderr.contains("Link check failed with 8 broken link(s)"),
        "{stderr}"
    );
}

#[test]
fn flags_change_what_is_reported() {
    let site = common::materialize("site");

    let report = json(&run(
        site.path(),
        &["--internal-only", "--json", "--skip-anchors"],
    ));
    assert_eq!(report["broken_links"], 5);

    let report = json(&run(
        site.path(),
        &["--internal-only", "--json", "--check-undefined-refs"],
    ));
    assert_eq!(report["broken_links"], 9);
    assert_eq!(report["total_links"], 21);
    assert!(broken(&report).contains(&(
        "README.md".to_string(),
        "[reference][nolabel]".to_string(),
        16
    )));

    let report = json(&run(
        site.path(),
        &[
            "--internal-only",
            "--json",
            "-i",
            "^docs/missing",
            "--ignore=gone",
        ],
    ));
    assert_eq!(report["broken_links"], 6);

    let report = json(&run(
        site.path(),
        &["--internal-only", "--json", "--no-ignore-files"],
    ));
    assert_eq!(report["files_checked"], 4);
    assert_eq!(report["broken_links"], 9);

    let report = json(&run(
        site.path(),
        &["--internal-only", "--json", "--exclude", "docs/"],
    ));
    assert_eq!(report["files_checked"], 1);
}

#[test]
fn ignore_file_flag() {
    let site = common::materialize("site");
    let patterns = site.path().join("patterns.txt");
    std::fs::write(&patterns, "# broken on purpose\n^images/\n").unwrap();
    let output = run(
        site.path(),
        &[
            "--internal-only",
            "--json",
            "--ignore-file",
            patterns.to_str().unwrap(),
        ],
    );
    assert_eq!(json(&output)["broken_links"], 6);
}

#[test]
fn clean_tree_exits_zero() {
    let dir = common::write_tree(&[
        (
            "README.md",
            "# Top\n\n[docs](docs/a.md#part-one) [self](#top)\n",
        ),
        ("docs/a.md", "## Part One\n\n[back](../README.md)\n"),
    ]);
    let output = run(dir.path(), &["--internal-only"]);
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert_eq!(output.status.code(), Some(0), "{stdout}");
    assert!(stdout.contains("Broken links:  0"), "{stdout}");
}

#[test]
fn explicit_files_and_multiple_paths() {
    let dir = common::write_tree(&[
        ("a.md", "[b](b.md)\n"),
        ("b.md", "[missing](nope.md)\n"),
        ("c.md", "# C\n"),
    ]);
    let output = Command::new(common::binary())
        .arg(dir.path().join("a.md"))
        .arg(dir.path().join("c.md"))
        .arg("--json")
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(0));
    assert_eq!(json(&output)["files_checked"], 2);
}

#[test]
fn fatal_errors_exit_two() {
    let dir = common::write_tree(&[("a.md", "# A\n")]);

    let output = Command::new(common::binary())
        .arg(dir.path().join("does-not-exist"))
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&output.stderr).contains("path does not exist"));

    let output = run(dir.path(), &["--ignore", "("]);
    assert_eq!(output.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&output.stderr).contains("invalid ignore pattern"));

    let output = run(dir.path(), &["--concurrent", "0"]);
    assert_eq!(output.status.code(), Some(2));
}

#[test]
fn unreadable_file_fails_run() {
    let dir = common::write_tree(&[("ok.md", "# Fine\n")]);
    std::fs::write(dir.path().join("bad.md"), [0xff, 0xfe, 0x00, 0x80]).unwrap();
    let output = run(dir.path(), &["--json"]);
    assert_eq!(output.status.code(), Some(1));
    let report = json(&output);
    assert_eq!(report["file_errors"], 1);
    assert_eq!(report["broken_links"], 0);
    assert_eq!(report["all_valid"], false);
}

#[tokio::test]
async fn external_links_via_mock_server() {
    use wiremock::matchers::path;
    use wiremock::{Mock, MockServer, ResponseTemplate};

    let server = MockServer::start().await;
    Mock::given(path("/ok"))
        .respond_with(ResponseTemplate::new(200))
        .mount(&server)
        .await;
    Mock::given(path("/gone"))
        .respond_with(ResponseTemplate::new(404))
        .mount(&server)
        .await;

    let base = server.uri();
    let content = format!("[ok]({base}/ok) [gone]({base}/gone) [ok again]({base}/ok#frag)\n");
    let dir = common::write_tree(&[("a.md", content.as_str())]);
    let dir_path = dir.path().to_path_buf();

    // Built-in defaults ignore 127.0.0.1, so the mock server is skipped...
    let skipped = {
        let dir_path = dir_path.clone();
        tokio::task::spawn_blocking(move || run(&dir_path, &["--json"]))
            .await
            .unwrap()
    };
    assert_eq!(skipped.status.code(), Some(0));
    assert_eq!(json(&skipped)["total_links"], 0);

    // ...unless they are disabled.
    let output = tokio::task::spawn_blocking(move || {
        run(
            &dir_path,
            &["--json", "--no-default-ignores", "--max-retries", "0"],
        )
    })
    .await
    .unwrap();
    assert_eq!(output.status.code(), Some(1));
    let report = json(&output);
    assert_eq!(report["total_links"], 3);
    let gone = format!("{base}/gone");
    assert_eq!(broken(&report), set(&[("a.md", gone.as_str(), 1)]));
    let error = report["results"][0]["links"]
        .as_array()
        .unwrap()
        .iter()
        .find(|l| l["valid"] == false)
        .unwrap()["error"]
        .clone();
    assert_eq!(error, "HTTP 404 Not Found");
}
