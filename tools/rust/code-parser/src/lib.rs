//! Parse and apply code changes from AI agent responses.
//!
//! AI responses deliver changes in three common shapes, all supported here:
//!
//! - **Fenced code blocks** holding whole files (```` ```rust src/lib.rs ````, ```` ~~~ ````,
//!   nested fences inside ```` ```markdown ````, CRLF input, unterminated blocks).
//!   See [`CodeParser::extract_code_blocks`].
//! - **Edit instructions**: Aider-style `<<<<<<< SEARCH` / `=======` / `>>>>>>> REPLACE`
//!   blocks and inline ``In `x.py`, change `a` to `b` `` sentences.
//!   See [`CodeParser::parse_edit_instructions`].
//! - **Unified diffs** (`--- a/x` / `+++ b/x` / `@@`), applied leniently.
//!   See [`CodeParser::parse_unified_diff`].
//!
//! Paths from responses are untrusted: [`CodeParser::sanitize_filename`] rejects
//! absolute paths, `..`, `.git/`, and control characters, and the `fs` feature
//! (on by default) additionally refuses symlinks that lead outside the base directory.
//!
//! # Example
//!
//! ```rust
//! use code_parser::CodeParser;
//!
//! let response = "Create `src/hello.py`:\n\n```python\ndef hello():\n    pass\n```\n";
//!
//! let blocks = CodeParser::extract_code_blocks(response);
//! assert_eq!(blocks.len(), 1);
//! assert_eq!(blocks[0].language, "python");
//! assert_eq!(blocks[0].filename.as_deref(), Some("src/hello.py"));
//! ```

#[cfg(feature = "fs")]
mod apply;
mod block;
mod diff;
mod edit;
mod error;
mod language;
mod path;
mod text;

#[cfg(feature = "fs")]
use std::collections::HashMap;
#[cfg(feature = "fs")]
use std::path::Path;

#[cfg(feature = "fs")]
pub use apply::{ApplyEntry, ApplyOptions, ApplyReport, ApplyStatus};
pub use block::CodeBlock;
pub use diff::{FilePatch, Hunk, HunkLine};
pub use edit::EditInstruction;
pub use error::{CodeParserError, Result};
use tracing::warn;

/// Compiles and runs the README examples as doctests.
#[cfg(all(doctest, feature = "fs"))]
#[doc = include_str!("../README.md")]
pub struct ReadmeDoctests;

/// Entry point for extracting and applying code changes from AI responses.
///
/// All methods are associated functions; the type carries no state.
pub struct CodeParser;

impl CodeParser {
    /// Extract all fenced code blocks from an AI response, in document order.
    ///
    /// Handles backtick and tilde fences of any length (a closing fence must use the
    /// same character and be at least as long), indented fences (e.g. inside list
    /// items), CRLF line endings, and unterminated blocks (returned with
    /// `terminated == false`).
    ///
    /// A block's filename is taken from, in order of preference: the fence info string
    /// (`rust src/lib.rs`, `rust:src/lib.rs`, `title="src/lib.rs"`), a `file:`/`path:`
    /// comment on the block's first line, or the nearest prose lines above the block
    /// (`Create `src/lib.rs`:`, `### src/lib.rs`, `**File:** src/lib.rs`). Blocks
    /// without a recognizable filename get `None`; filenames are never inherited from
    /// earlier blocks.
    pub fn extract_code_blocks(response: &str) -> Vec<CodeBlock> {
        block::extract(response)
    }

    /// Infer a language tag from a filename's extension (or well-known name such as
    /// `Dockerfile`). Unknown extensions yield `"text"`.
    pub fn infer_language(filename: &str) -> String {
        language::infer_language(filename)
    }

    /// Validate and normalize a relative path from an AI response.
    ///
    /// Returns the path with `/` separators and redundant `./` segments removed.
    ///
    /// # Errors
    ///
    /// - [`CodeParserError::PathTraversal`] for absolute paths (`/x`, `C:\x`, `\\srv\x`,
    ///   `~/x`), any `..` component, or any path inside a `.git` directory.
    /// - [`CodeParserError::InvalidFilename`] for empty paths, control characters, `:`,
    ///   or paths ending in a separator.
    pub fn sanitize_filename(filename: &str) -> Result<String> {
        path::sanitize(filename)
    }

    /// Parse edit instructions from an AI response, in document order.
    ///
    /// Recognizes Aider-style SEARCH/REPLACE blocks (filename on the line above, or in
    /// the enclosing fence's info string) and inline sentences such as
    /// ``In file `main.py`, change `a` to `b` `` or `Update main.py: replace "a" with "b"`.
    pub fn parse_edit_instructions(response: &str) -> Vec<EditInstruction> {
        edit::parse(response)
    }

    /// Apply a single edit instruction to in-memory file content.
    ///
    /// # Errors
    ///
    /// [`CodeParserError::SearchNotFound`] if the old text is absent, or
    /// [`CodeParserError::AmbiguousEdit`] if it occurs more than once.
    pub fn apply_edit(content: &str, edit: &EditInstruction) -> Result<String> {
        edit::apply(content, edit)
    }

    /// Parse a unified diff (possibly embedded in prose) into per-file patches.
    ///
    /// # Errors
    ///
    /// [`CodeParserError::InvalidPatch`] if no file header with hunks is found.
    pub fn parse_unified_diff(diff: &str) -> Result<Vec<FilePatch>> {
        diff::parse(diff)
    }

    /// Parse every diff code block in a response into patches. Blocks that fail to
    /// parse are logged and skipped.
    pub fn extract_patches(response: &str) -> Vec<FilePatch> {
        block::extract(response)
            .iter()
            .filter(|b| b.is_diff())
            .filter_map(|b| match diff::parse(&b.content) {
                Ok(p) => Some(p),
                Err(e) => {
                    warn!("Ignoring diff block at line {}: {e}", b.start_line);
                    None
                },
            })
            .flatten()
            .collect()
    }

    /// Apply code blocks to files under `base_path` (legacy interface).
    ///
    /// Returns a map from path to status string (`"created"`, `"modified"`,
    /// `"unchanged"`, `"deleted"`, `"skipped: ..."`, or `"error: ..."`). Prefer
    /// [`CodeParser::apply_code_blocks_with`] for a structured report.
    #[cfg(feature = "fs")]
    pub fn apply_code_blocks(blocks: &[CodeBlock], base_path: &Path) -> HashMap<String, String> {
        match apply::apply_blocks(blocks, base_path, ApplyOptions::default()) {
            Ok(report) => report.to_status_map(),
            Err(e) => blocks
                .iter()
                .filter_map(|b| b.filename.clone())
                .map(|f| (f, format!("error: {e}")))
                .collect(),
        }
    }

    /// Apply code blocks to files under `base_path`.
    ///
    /// Blocks without a filename are ignored. Diff blocks are applied as patches.
    /// Unterminated blocks are skipped unless [`ApplyOptions::allow_unterminated`] is set.
    /// Per-file failures are reported in the [`ApplyReport`] rather than aborting.
    ///
    /// # Errors
    ///
    /// Only if `base_path` cannot be created or resolved.
    #[cfg(feature = "fs")]
    pub fn apply_code_blocks_with(
        blocks: &[CodeBlock],
        base_path: &Path,
        options: ApplyOptions,
    ) -> Result<ApplyReport> {
        apply::apply_blocks(blocks, base_path, options)
    }

    /// Apply unified-diff patches to files under `base_path`, including creations,
    /// deletions, and renames.
    ///
    /// # Errors
    ///
    /// Only if `base_path` cannot be created or resolved.
    #[cfg(feature = "fs")]
    pub fn apply_patches(
        patches: &[FilePatch],
        base_path: &Path,
        options: ApplyOptions,
    ) -> Result<ApplyReport> {
        apply::apply_patches(patches, base_path, options)
    }

    /// Apply edit instructions to files under `base_path`, in order. An edit with an
    /// empty `old` creates the file if it does not exist.
    ///
    /// # Errors
    ///
    /// Only if `base_path` cannot be created or resolved.
    #[cfg(feature = "fs")]
    pub fn apply_edit_instructions(
        edits: &[EditInstruction],
        base_path: &Path,
        options: ApplyOptions,
    ) -> Result<ApplyReport> {
        apply::apply_edits(edits, base_path, options)
    }

    /// Extract code blocks from `response` and apply them under `base_path`.
    ///
    /// Returns the extracted blocks and the legacy status map
    /// (see [`CodeParser::apply_code_blocks`]).
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
        let results = Self::apply_code_blocks(&blocks, base_path);
        (blocks, results)
    }
}
