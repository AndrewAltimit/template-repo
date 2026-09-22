//! Language inference from file names.

/// Map a path to a language tag, or `None` if the extension is unknown.
pub(crate) fn language_for_path(path: &str) -> Option<&'static str> {
    let name = path.rsplit(['/', '\\']).next().unwrap_or(path);
    let lower = name.to_ascii_lowercase();

    match lower.as_str() {
        "dockerfile" | "containerfile" => return Some("dockerfile"),
        "makefile" | "gnumakefile" => return Some("makefile"),
        "cmakelists.txt" => return Some("cmake"),
        "justfile" => return Some("just"),
        "gemfile" | "rakefile" => return Some("ruby"),
        "jenkinsfile" => return Some("groovy"),
        _ => {},
    }
    if lower.starts_with("dockerfile.") {
        return Some("dockerfile");
    }

    let (_, ext) = lower.rsplit_once('.')?;
    let lang = match ext {
        "py" | "pyi" => "python",
        "js" | "mjs" | "cjs" => "javascript",
        "ts" | "mts" | "cts" => "typescript",
        "jsx" => "jsx",
        "tsx" => "tsx",
        "java" => "java",
        "kt" | "kts" => "kotlin",
        "scala" => "scala",
        "swift" => "swift",
        "c" | "h" => "c",
        "cc" | "cpp" | "cxx" | "hpp" | "hh" | "hxx" => "cpp",
        "cs" => "csharp",
        "go" => "go",
        "rs" => "rust",
        "rb" => "ruby",
        "php" => "php",
        "sh" | "bash" => "bash",
        "zsh" => "zsh",
        "fish" => "fish",
        "ps1" | "psm1" => "powershell",
        "lua" => "lua",
        "pl" | "pm" => "perl",
        "r" => "r",
        "dart" => "dart",
        "ex" | "exs" => "elixir",
        "erl" | "hrl" => "erlang",
        "hs" => "haskell",
        "ml" | "mli" => "ocaml",
        "clj" | "cljs" => "clojure",
        "zig" => "zig",
        "nix" => "nix",
        "sql" => "sql",
        "yaml" | "yml" => "yaml",
        "json" => "json",
        "jsonc" => "jsonc",
        "toml" => "toml",
        "ini" | "cfg" => "ini",
        "xml" => "xml",
        "html" | "htm" => "html",
        "css" => "css",
        "scss" => "scss",
        "sass" => "sass",
        "less" => "less",
        "md" | "markdown" => "markdown",
        "rst" => "rst",
        "tex" => "latex",
        "vue" => "vue",
        "svelte" => "svelte",
        "graphql" | "gql" => "graphql",
        "proto" => "protobuf",
        "tf" | "hcl" => "hcl",
        "dockerfile" => "dockerfile",
        "diff" | "patch" => "diff",
        "txt" => "text",
        _ => return None,
    };
    Some(lang)
}

/// Infer a language tag from a filename; unknown extensions map to `"text"`.
pub(crate) fn infer_language(filename: &str) -> String {
    language_for_path(filename).unwrap_or("text").to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn common_extensions() {
        assert_eq!(infer_language("a/b/test.py"), "python");
        assert_eq!(infer_language("main.RS"), "rust");
        assert_eq!(infer_language("x.tsx"), "tsx");
        assert_eq!(infer_language("x.unknown"), "text");
        assert_eq!(infer_language("noext"), "text");
    }

    #[test]
    fn special_filenames() {
        assert_eq!(infer_language("docker/Dockerfile"), "dockerfile");
        assert_eq!(infer_language("Dockerfile.dev"), "dockerfile");
        assert_eq!(infer_language("Makefile"), "makefile");
        assert_eq!(infer_language("CMakeLists.txt"), "cmake");
    }
}
