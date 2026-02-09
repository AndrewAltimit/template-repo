//! Code Parser Library
//!
//! Parse and apply code blocks from AI responses. This library provides
//! safe extraction of code blocks from markdown-formatted AI responses,
//! with security features to prevent path traversal attacks.
//!
//! # Example
//!
//! ```rust
//! use code_parser::CodeParser;
//!
//! let response = "Here's code:\n\n```python\ndef hello():\n    pass\n```\n";
//!
//! let blocks = CodeParser::extract_code_blocks(response);
//! assert_eq!(blocks.len(), 1);
//! assert_eq!(blocks[0].language, "python");
//! ```

use regex::Regex;
use std::collections::HashMap;
use std::path::Path;
use thiserror::Error;
#[cfg(feature = "fs")]
use tracing::debug;
use tracing::warn;

/// Errors that can occur during code parsing or application
#[derive(Error, Debug)]
pub enum CodeParserError {
    /// Path traversal attempt detected
    #[error("Path traversal attempt blocked: {0}")]
    PathTraversal(String),

    /// Invalid filename
    #[error("Invalid filename: {0}")]
    InvalidFilename(String),

    /// I/O error during file operations
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    /// Regex compilation error
    #[error("Regex error: {0}")]
    Regex(#[from] regex::Error),
}

/// Result type for code parser operations
pub type Result<T> = std::result::Result<T, CodeParserError>;

/// Represents a code block extracted from an AI response
#[derive(Debug, Clone, PartialEq)]
pub struct CodeBlock {
    /// Programming language of the code block
    pub language: String,
    /// The code content
    pub content: String,
    /// Optional filename associated with the code block
    pub filename: Option<String>,
}

impl CodeBlock {
    /// Create a new code block
    pub fn new(language: impl Into<String>, content: impl Into<String>) -> Self {
        Self {
            language: language.into(),
            content: content.into(),
            filename: None,
        }
    }

    /// Create a new code block with a filename
    pub fn with_filename(
        language: impl Into<String>,
        content: impl Into<String>,
        filename: impl Into<String>,
    ) -> Self {
        Self {
            language: language.into(),
            content: content.into(),
            filename: Some(filename.into()),
        }
    }
}

/// Represents an edit instruction extracted from AI response
#[derive(Debug, Clone, PartialEq)]
pub struct EditInstruction {
    /// The file to edit
    pub file: String,
    /// The old text to replace
    pub old: String,
    /// The new text to insert
    pub new: String,
}

/// Code parser for extracting and applying code changes from AI responses
pub struct CodeParser;

impl CodeParser {
    /// Patterns to detect file identification in AI responses
    const FILE_PATTERNS: &'static [&'static str] = &[
        // Explicit file path comments
        r"#\s*(?:file|filename|path):\s*([^\n]+)",
        r"//\s*(?:file|filename|path):\s*([^\n]+)",
        r"--\s*(?:file|filename|path):\s*([^\n]+)",
        // File creation/modification statements
        r"(?:create|modify|update|edit)\s+(?:file\s+)?`([^`]+)`",
        r"(?:in|to)\s+file\s+`([^`]+)`",
        // Common file path patterns
        r"^([a-zA-Z0-9_\-./]+\.[a-zA-Z]+):\s*$",
    ];

    /// Extract code blocks from an AI response
    ///
    /// # Arguments
    ///
    /// * `response` - The AI agent's response containing code blocks
    ///
    /// # Returns
    ///
    /// A vector of `CodeBlock` objects
    pub fn extract_code_blocks(response: &str) -> Vec<CodeBlock> {
        let mut blocks = Vec::new();
        let code_pattern = Regex::new(r"```(\w*)\n([\s\S]*?)```").unwrap();
        let mut last_file: Option<String> = None;

        for (i, caps) in code_pattern.captures_iter(response).enumerate() {
            let language_raw = caps.get(1).map_or("", |m| m.as_str());
            let content = caps.get(2).map_or("", |m| m.as_str()).trim();

            // Try to find associated filename
            let filename =
                Self::find_associated_filename(response, i).or_else(|| last_file.clone());

            if let Some(ref f) = filename {
                last_file = Some(f.clone());
            }

            // Determine language
            let language = if language_raw.is_empty() {
                filename
                    .as_ref()
                    .map(|f| Self::infer_language(f))
                    .unwrap_or_else(|| "text".to_string())
            } else {
                language_raw.to_string()
            };

            let mut block = CodeBlock::new(language, content);
            block.filename = filename;
            blocks.push(block);
        }

        blocks
    }

    /// Find the filename associated with a code block
    fn find_associated_filename(response: &str, block_index: usize) -> Option<String> {
        // Find the position of the nth code block
        let code_pattern = Regex::new(r"```").unwrap();
        let positions: Vec<_> = code_pattern.find_iter(response).collect();

        // Each code block has two ``` markers (open and close)
        let block_start_index = block_index * 2;
        if block_start_index >= positions.len() {
            return None;
        }

        let code_pos = positions[block_start_index].start();

        // Search backwards from code block for file indicators (up to 500 chars)
        let search_start = code_pos.saturating_sub(500);
        let search_text = &response[search_start..code_pos];

        for pattern_str in Self::FILE_PATTERNS {
            if let Ok(pattern) = Regex::new(&format!("(?i){}", pattern_str))
                && let Some(caps) = pattern.captures(search_text)
                && let Some(filename_match) = caps.get(1)
            {
                let filename = filename_match.as_str().trim();
                // Clean up the filename
                let filename = filename.trim_matches(|c| {
                    c == '\'' || c == '"' || c == '`' || c == ',' || c == '.' || c == ' '
                });
                if !filename.is_empty() && !filename.starts_with('*') {
                    return Some(filename.to_string());
                }
            }
        }

        None
    }

    /// Infer programming language from filename extension
    pub fn infer_language(filename: &str) -> String {
        let ext_map: HashMap<&str, &str> = [
            (".py", "python"),
            (".js", "javascript"),
            (".ts", "typescript"),
            (".jsx", "jsx"),
            (".tsx", "tsx"),
            (".java", "java"),
            (".cpp", "cpp"),
            (".c", "c"),
            (".h", "c"),
            (".hpp", "cpp"),
            (".go", "go"),
            (".rs", "rust"),
            (".rb", "ruby"),
            (".php", "php"),
            (".sh", "bash"),
            (".yaml", "yaml"),
            (".yml", "yaml"),
            (".json", "json"),
            (".xml", "xml"),
            (".html", "html"),
            (".css", "css"),
            (".scss", "scss"),
            (".md", "markdown"),
            (".sql", "sql"),
            (".dockerfile", "dockerfile"),
            (".toml", "toml"),
        ]
        .into_iter()
        .collect();

        Path::new(filename)
            .extension()
            .and_then(|ext| ext.to_str())
            .map(|ext| format!(".{}", ext.to_lowercase()))
            .and_then(|ext| ext_map.get(ext.as_str()).copied())
            .unwrap_or("text")
            .to_string()
    }

    /// Sanitize a filename to prevent path traversal attacks
    ///
    /// # Arguments
    ///
    /// * `filename` - Raw filename from AI response
    ///
    /// # Returns
    ///
    /// Sanitized filename or error if invalid
    pub fn sanitize_filename(filename: &str) -> Result<String> {
        let filename = filename.trim();

        if filename.is_empty() {
            return Err(CodeParserError::InvalidFilename(
                "empty filename".to_string(),
            ));
        }

        // Reject absolute paths
        if filename.starts_with('/') || (filename.len() > 1 && filename.chars().nth(1) == Some(':'))
        {
            warn!("Rejecting absolute path: {}", filename);
            return Err(CodeParserError::PathTraversal(filename.to_string()));
        }

        // Reject filenames with parent directory references
        let path = Path::new(filename);
        for component in path.components() {
            if let std::path::Component::ParentDir = component {
                warn!(
                    "Rejecting path with parent directory reference: {}",
                    filename
                );
                return Err(CodeParserError::PathTraversal(filename.to_string()));
            }
        }

        // Reject filenames with special characters
        if filename.contains('\0') || filename.contains('\n') || filename.contains('\r') {
            warn!("Rejecting filename with special characters: {}", filename);
            return Err(CodeParserError::InvalidFilename(
                "contains special characters".to_string(),
            ));
        }

        // Remove leading ./
        let filename = filename.strip_prefix("./").unwrap_or(filename);

        Ok(filename.to_string())
    }

    /// Apply code blocks to files
    ///
    /// # Arguments
    ///
    /// * `blocks` - List of CodeBlock objects to apply
    /// * `base_path` - Base directory for file operations
    ///
    /// # Returns
    ///
    /// HashMap mapping filenames to their operation status
    #[cfg(feature = "fs")]
    pub fn apply_code_blocks(blocks: &[CodeBlock], base_path: &Path) -> HashMap<String, String> {
        use std::fs;
        use std::io::Write;

        let mut results = HashMap::new();
        let base_path = base_path
            .canonicalize()
            .unwrap_or_else(|_| base_path.to_path_buf());

        for block in blocks {
            let Some(filename) = &block.filename else {
                debug!("Skipping code block without filename");
                continue;
            };

            // Sanitize the filename
            let sanitized = match Self::sanitize_filename(filename) {
                Ok(f) => f,
                Err(e) => {
                    results.insert(filename.clone(), format!("error: {}", e));
                    continue;
                },
            };

            let filepath = base_path.join(&sanitized);

            // Ensure the resolved path is within the base directory
            let resolved = match filepath.canonicalize() {
                Ok(p) => p,
                Err(_) => {
                    // File doesn't exist yet, check parent
                    if let Some(parent) = filepath.parent() {
                        if let Err(e) = fs::create_dir_all(parent) {
                            results.insert(sanitized.clone(), format!("error: {}", e));
                            continue;
                        }
                    }
                    filepath.clone()
                },
            };

            // Security check: ensure path is within base_path
            if resolved.strip_prefix(&base_path).is_err()
                && filepath.strip_prefix(&base_path).is_err()
            {
                results.insert(
                    sanitized.clone(),
                    "error: path traversal blocked".to_string(),
                );
                continue;
            }

            // Determine operation
            let operation = if filepath.exists() {
                "modified"
            } else {
                "created"
            };

            // Write the content
            match fs::File::create(&filepath) {
                Ok(mut file) => {
                    let mut content = block.content.clone();
                    if !content.ends_with('\n') {
                        content.push('\n');
                    }
                    if let Err(e) = file.write_all(content.as_bytes()) {
                        results.insert(sanitized, format!("error: {}", e));
                        continue;
                    }
                    debug!("{} file: {}", operation, sanitized);
                    results.insert(sanitized, operation.to_string());
                },
                Err(e) => {
                    results.insert(sanitized, format!("error: {}", e));
                },
            }
        }

        results
    }

    /// Parse edit instructions from AI response
    ///
    /// Some AI responses contain edit instructions rather than full code blocks.
    /// This method extracts those instructions.
    ///
    /// # Arguments
    ///
    /// * `response` - The AI response text
    ///
    /// # Returns
    ///
    /// A vector of edit instructions
    pub fn parse_edit_instructions(response: &str) -> Vec<EditInstruction> {
        let mut instructions = Vec::new();

        let edit_patterns = [
            r"(?i)(?:In|Edit|Modify|Update)\s+(?:file\s+)?`([^`]+)`[,:]?\s*(?:change|replace|update)\s+`([^`]+)`\s+(?:to|with)\s+`([^`]+)`",
            r#"(?i)(?:In|Edit|Modify|Update)\s+(?:file\s+)?([^\s,]+)[,:]?\s*(?:change|replace|update)\s+"([^"]+)"\s+(?:to|with)\s+"([^"]+)""#,
        ];

        for pattern_str in edit_patterns {
            if let Ok(pattern) = Regex::new(pattern_str) {
                for caps in pattern.captures_iter(response) {
                    if let (Some(file), Some(old), Some(new)) =
                        (caps.get(1), caps.get(2), caps.get(3))
                    {
                        instructions.push(EditInstruction {
                            file: file.as_str().to_string(),
                            old: old.as_str().to_string(),
                            new: new.as_str().to_string(),
                        });
                    }
                }
            }
        }

        instructions
    }

    /// Extract code blocks and apply them to files
    ///
    /// Convenience method that combines extraction and application.
    ///
    /// # Arguments
    ///
    /// * `response` - AI agent response containing code blocks
    /// * `base_path` - Base directory for file operations
    ///
    /// # Returns
    ///
    /// Tuple of (extracted blocks, results dictionary)
    #[cfg(feature = "fs")]
    pub fn extract_and_apply(
        response: &str,
        base_path: &Path,
    ) -> (Vec<CodeBlock>, HashMap<String, String>) {
        let blocks = Self::extract_code_blocks(response);

        if blocks.is_empty() {
            warn!("No code blocks found in response");
            return (blocks, HashMap::new());
        }

        debug!("Found {} code blocks", blocks.len());

        let results = Self::apply_code_blocks(&blocks, base_path);
        (blocks, results)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_single_code_block() {
        let response = r#"
Here's a Python function:

```python
def hello():
    print("Hello, world!")
```
"#;

        let blocks = CodeParser::extract_code_blocks(response);
        assert_eq!(blocks.len(), 1);
        assert_eq!(blocks[0].language, "python");
        assert!(blocks[0].content.contains("def hello()"));
    }

    #[test]
    fn test_extract_multiple_code_blocks() {
        let response = r#"
First, the Python code:

```python
def foo():
    pass
```

Then the Rust code:

```rust
fn bar() {}
```
"#;

        let blocks = CodeParser::extract_code_blocks(response);
        assert_eq!(blocks.len(), 2);
        assert_eq!(blocks[0].language, "python");
        assert_eq!(blocks[1].language, "rust");
    }

    #[test]
    fn test_extract_code_block_without_language() {
        let response = r#"
```
some code here
```
"#;

        let blocks = CodeParser::extract_code_blocks(response);
        assert_eq!(blocks.len(), 1);
        assert_eq!(blocks[0].language, "text");
    }

    #[test]
    fn test_infer_language() {
        assert_eq!(CodeParser::infer_language("test.py"), "python");
        assert_eq!(CodeParser::infer_language("test.rs"), "rust");
        assert_eq!(CodeParser::infer_language("test.js"), "javascript");
        assert_eq!(CodeParser::infer_language("test.unknown"), "text");
    }

    #[test]
    fn test_sanitize_filename_valid() {
        assert_eq!(
            CodeParser::sanitize_filename("src/main.rs").unwrap(),
            "src/main.rs"
        );
        assert_eq!(
            CodeParser::sanitize_filename("./test.py").unwrap(),
            "test.py"
        );
    }

    #[test]
    fn test_sanitize_filename_rejects_absolute() {
        assert!(CodeParser::sanitize_filename("/etc/passwd").is_err());
        assert!(CodeParser::sanitize_filename("C:\\Windows\\system32").is_err());
    }

    #[test]
    fn test_sanitize_filename_rejects_parent_dir() {
        assert!(CodeParser::sanitize_filename("../secret.txt").is_err());
        assert!(CodeParser::sanitize_filename("foo/../../../etc/passwd").is_err());
    }

    #[test]
    fn test_sanitize_filename_rejects_special_chars() {
        assert!(CodeParser::sanitize_filename("file\x00name").is_err());
        assert!(CodeParser::sanitize_filename("file\nname").is_err());
    }

    #[test]
    fn test_parse_edit_instructions() {
        let response = r#"In file `main.py`, change `print("hello")` to `print("goodbye")`"#;

        let instructions = CodeParser::parse_edit_instructions(response);
        assert_eq!(instructions.len(), 1);
        assert_eq!(instructions[0].file, "main.py");
        assert_eq!(instructions[0].old, r#"print("hello")"#);
        assert_eq!(instructions[0].new, r#"print("goodbye")"#);
    }

    #[test]
    fn test_extract_with_filename_hint() {
        let response = r#"
Create file `src/utils.py`:

```python
def helper():
    pass
```
"#;

        let blocks = CodeParser::extract_code_blocks(response);
        assert_eq!(blocks.len(), 1);
        assert_eq!(blocks[0].filename, Some("src/utils.py".to_string()));
    }
}
