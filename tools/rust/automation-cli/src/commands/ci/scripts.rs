//! Bash snippets executed inside the CI containers.
//!
//! File discovery prunes VCS, build, cache and virtualenv directories (a
//! Rust `target/` alone can hold thousands of generated `.json` files) and
//! hands all files to a single tool invocation instead of spawning one
//! process per file.

/// `find` prefix shared by the lint scripts: prunes generated/vendored trees.
/// Must be followed by the file predicates and `-print0`.
macro_rules! find_sources {
    () => {
        "find . \\( -name .git -o -name target -o -name node_modules -o -name .venv \
         -o -name venv -o -name __pycache__ -o -name .mypy_cache -o -name .pytest_cache \
         -o -name .ruff_cache -o -name outputs \\) -prune -o -type f "
    };
}

/// yamllint + a strict `yaml.safe_load_all` parse of every YAML file.
pub const YAML_LINT: &str = concat!(
    "set -uo pipefail\n",
    "mapfile -d '' files < <(",
    find_sources!(),
    "\\( -name '*.yml' -o -name '*.yaml' \\) -print0 | sort -z)\n",
    "if [ ${#files[@]} -eq 0 ]; then echo 'OK: no YAML files found'; exit 0; fi\n",
    "echo \"Checking ${#files[@]} YAML files...\"\n",
    "ERRORS=0\n",
    "yamllint \"${files[@]}\" || ERRORS=$((ERRORS+1))\n",
    "python3 - \"${files[@]}\" <<'PY' || ERRORS=$((ERRORS+1))\n",
    "import sys, yaml\n",
    "bad = 0\n",
    "for path in sys.argv[1:]:\n",
    "    try:\n",
    "        with open(path, encoding='utf-8') as fh:\n",
    "            list(yaml.safe_load_all(fh))\n",
    "    except Exception as exc:\n",
    "        print(f'Invalid YAML: {path}: {exc}')\n",
    "        bad += 1\n",
    "sys.exit(1 if bad else 0)\n",
    "PY\n",
    "if [ $ERRORS -gt 0 ]; then echo 'FAIL: YAML validation errors found'; exit 1; fi\n",
    "echo 'OK: All YAML files valid'\n",
);

/// Strict JSON parse of every `.json` file.
pub const JSON_LINT: &str = concat!(
    "set -uo pipefail\n",
    "mapfile -d '' files < <(",
    find_sources!(),
    "-name '*.json' -print0 | sort -z)\n",
    "if [ ${#files[@]} -eq 0 ]; then echo 'OK: no JSON files found'; exit 0; fi\n",
    "echo \"Checking ${#files[@]} JSON files...\"\n",
    "python3 - \"${files[@]}\" <<'PY'\n",
    "import json, sys\n",
    "bad = 0\n",
    "for path in sys.argv[1:]:\n",
    "    try:\n",
    "        with open(path, encoding='utf-8') as fh:\n",
    "            json.load(fh)\n",
    "    except Exception as exc:\n",
    "        print(f'Invalid JSON: {path}: {exc}')\n",
    "        bad += 1\n",
    "if bad:\n",
    "    print(f'FAIL: {bad} JSON validation errors')\n",
    "    sys.exit(1)\n",
    "print('OK: All JSON files valid')\n",
    "PY\n",
);

/// shellcheck (warning severity and above) over every `.sh` file.
pub const SHELL_LINT: &str = concat!(
    "set -uo pipefail\n",
    "mapfile -d '' files < <(",
    find_sources!(),
    "-name '*.sh' -print0 | sort -z)\n",
    "if [ ${#files[@]} -eq 0 ]; then echo 'OK: no shell scripts found'; exit 0; fi\n",
    "echo \"Checking ${#files[@]} shell scripts...\"\n",
    "if shellcheck -S warning \"${files[@]}\"; then\n",
    "  echo 'OK: All shell scripts passed linting'\n",
    "else\n",
    "  echo 'FAIL: Shell linting failed'; exit 1\n",
    "fi\n",
);

/// Script that runs `cargo fmt --all` in each directory (relative to the
/// container workdir), continuing past failures and exiting non-zero if any
/// directory failed.
pub fn cargo_fmt_all(dirs: &[String]) -> String {
    let list: Vec<String> = dirs.iter().map(|d| shell_quote(d)).collect();
    format!(
        "FAILED=''\n\
         for d in {}; do\n\
         \x20 echo \"Formatting $d...\"\n\
         \x20 (cd \"$d\" && cargo fmt --all) || FAILED=\"$FAILED $d\"\n\
         done\n\
         if [ -n \"$FAILED\" ]; then echo \"cargo fmt failed in:$FAILED\"; exit 1; fi\n",
        list.join(" ")
    )
}

/// Single-quote a string for POSIX shells.
pub fn shell_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', r"'\''"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shell_quote_escapes_single_quotes() {
        assert_eq!(shell_quote("plain"), "'plain'");
        assert_eq!(shell_quote("it's"), r"'it'\''s'");
    }

    #[test]
    fn cargo_fmt_script_lists_all_dirs() {
        let s = cargo_fmt_all(&["tools/rust/a".into(), "packages/b c".into()]);
        assert!(s.contains("for d in 'tools/rust/a' 'packages/b c'; do"));
        assert!(s.contains("cargo fmt --all"));
        assert!(s.contains("exit 1"));
    }

    #[test]
    fn lint_scripts_prune_build_dirs() {
        for script in [YAML_LINT, JSON_LINT, SHELL_LINT] {
            assert!(script.contains("-name target"));
            assert!(script.contains("-name .git"));
            assert!(script.contains("-prune"));
            assert!(script.contains("-print0"));
        }
    }
}
