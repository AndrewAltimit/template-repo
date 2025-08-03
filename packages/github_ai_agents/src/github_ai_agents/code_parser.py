"""Code parser for extracting and applying code changes from AI responses."""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CodeBlock:
    """Represents a code block extracted from AI response."""

    def __init__(self, language: str, content: str, filename: Optional[str] = None):
        self.language = language
        self.content = content
        self.filename = filename

    def __repr__(self):
        return f"CodeBlock(language={self.language}, filename={self.filename}, lines={len(self.content.splitlines())})"


class CodeParser:
    """Parse and apply code changes from AI agent responses."""

    # Common patterns for file identification
    FILE_PATTERNS = [
        # Explicit file path comments
        r"#\s*(?:file|filename|path):\s*([^\n]+)",
        r"//\s*(?:file|filename|path):\s*([^\n]+)",
        r"--\s*(?:file|filename|path):\s*([^\n]+)",
        # File creation/modification statements
        r"(?:create|modify|update|edit)\s+(?:file\s+)?`([^`]+)`",
        r"(?:in|to)\s+file\s+`([^`]+)`",
        # Common file path patterns
        r"^([a-zA-Z0-9_\-./]+\.[a-zA-Z]+):\s*$",
    ]

    @classmethod
    def extract_code_blocks(cls, response: str) -> List[CodeBlock]:
        """Extract code blocks from AI response.

        Args:
            response: The AI agent's response containing code blocks

        Returns:
            List of CodeBlock objects
        """
        blocks = []

        # Pattern to match code blocks with optional language
        code_pattern = r"```(\w*)\n(.*?)```"
        matches = re.findall(code_pattern, response, re.DOTALL)

        # Keep track of the last mentioned file
        last_file = None

        for i, (language, content) in enumerate(matches):
            # Try to find associated filename
            filename = cls._find_associated_filename(response, content, i)
            if not filename:
                filename = last_file
            else:
                last_file = filename

            # Default language if not specified
            if not language:
                language = cls._infer_language(filename) if filename else "text"

            blocks.append(CodeBlock(language, content.strip(), filename))

        return blocks

    @classmethod
    def _find_associated_filename(cls, response: str, code_content: str, block_index: int) -> Optional[str]:
        """Find the filename associated with a code block."""
        # Look for filename patterns before the code block
        code_pos = response.find("```", 0)
        for _ in range(block_index):
            code_pos = response.find("```", response.find("```", code_pos) + 3)

        # Search backwards from code block for file indicators
        search_text = response[max(0, code_pos - 500) : code_pos]

        for pattern in cls.FILE_PATTERNS:
            match = re.search(pattern, search_text, re.MULTILINE | re.IGNORECASE)
            if match:
                filename = match.group(1).strip()
                # Clean up the filename
                filename = filename.strip("'\"`,. ")
                if filename and not filename.startswith("*"):
                    return filename

        return None

    @classmethod
    def _infer_language(cls, filename: str) -> str:
        """Infer language from filename extension."""
        if not filename:
            return "text"

        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "jsx",
            ".tsx": "tsx",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".h": "c",
            ".hpp": "cpp",
            ".go": "go",
            ".rs": "rust",
            ".rb": "ruby",
            ".php": "php",
            ".sh": "bash",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".md": "markdown",
            ".sql": "sql",
            ".dockerfile": "dockerfile",
        }

        ext = Path(filename).suffix.lower()
        return ext_map.get(ext, "text")

    @classmethod
    def apply_code_blocks(cls, blocks: List[CodeBlock], base_path: str = ".") -> Dict[str, str]:
        """Apply code blocks to files.

        Args:
            blocks: List of CodeBlock objects to apply
            base_path: Base directory for file operations

        Returns:
            Dictionary mapping filenames to their operation (created/modified)
        """
        results = {}
        base_path_obj = Path(base_path).resolve()

        for block in blocks:
            if not block.filename:
                logger.warning(f"Skipping code block without filename: {block}")
                continue

            # Sanitize filename to prevent path traversal
            filename = cls._sanitize_filename(block.filename)
            if not filename:
                logger.error(f"Invalid filename rejected: {block.filename}")
                results[block.filename] = "error: invalid filename"
                continue

            filepath = base_path_obj / filename

            # Ensure the resolved path is within the base directory
            try:
                filepath = filepath.resolve()
                filepath.relative_to(base_path_obj)
            except (ValueError, RuntimeError):
                logger.error(f"Path traversal attempt blocked: {block.filename}")
                results[block.filename] = "error: path traversal blocked"
                continue

            # Create parent directories if needed
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # Determine if file exists
            operation = "modified" if filepath.exists() else "created"

            try:
                # Write the content
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(block.content)
                    if not block.content.endswith("\n"):
                        f.write("\n")

                results[filename] = operation
                logger.info(f"{operation.capitalize()} file: {filename}")

            except Exception as e:
                logger.error(f"Failed to write file {filename}: {e}")
                results[filename] = f"error: {str(e)}"

        return results

    @classmethod
    def _sanitize_filename(cls, filename: str) -> Optional[str]:
        """Sanitize filename to prevent path traversal attacks.

        Args:
            filename: Raw filename from AI response

        Returns:
            Sanitized filename or None if invalid
        """
        if not filename:
            return None

        # Remove any leading/trailing whitespace
        filename = filename.strip()

        # Reject absolute paths
        if filename.startswith("/") or (len(filename) > 1 and filename[1] == ":"):
            logger.warning(f"Rejecting absolute path: {filename}")
            return None

        # Reject filenames with parent directory references
        parts = Path(filename).parts
        if ".." in parts:
            logger.warning(f"Rejecting path with parent directory reference: {filename}")
            return None

        # Reject filenames that try to escape using special characters
        if any(c in filename for c in ["\x00", "\n", "\r"]):
            logger.warning(f"Rejecting filename with special characters: {filename}")
            return None

        # Additional safety: ensure the filename doesn't start with a dot-slash
        if filename.startswith("./"):
            filename = filename[2:]

        return filename

    @classmethod
    def extract_and_apply(cls, response: str, base_path: str = ".") -> Tuple[List[CodeBlock], Dict[str, str]]:
        """Extract code blocks from response and apply them.

        Args:
            response: AI agent response containing code blocks
            base_path: Base directory for file operations

        Returns:
            Tuple of (extracted blocks, results dictionary)
        """
        blocks = cls.extract_code_blocks(response)

        if not blocks:
            logger.warning("No code blocks found in response")
            return blocks, {}

        logger.info(f"Found {len(blocks)} code blocks")
        for block in blocks:
            logger.info(f"  - {block}")

        # Apply the changes
        results = cls.apply_code_blocks(blocks, base_path)

        return blocks, results

    @classmethod
    def parse_edit_instructions(cls, response: str) -> List[Dict[str, str]]:
        """Parse edit instructions from AI response.

        Some AI responses contain edit instructions rather than full code blocks.
        This method extracts those instructions.

        Returns:
            List of edit instruction dictionaries
        """
        instructions = []

        # Pattern for edit instructions like "In file X, change Y to Z"
        edit_patterns = [
            (
                r"(?:In|Edit|Modify|Update)\s+(?:file\s+)?`([^`]+)`[,:]?\s*"
                r"(?:change|replace|update)\s+`([^`]+)`\s+(?:to|with)\s+`([^`]+)`"
            ),
            (
                r"(?:In|Edit|Modify|Update)\s+(?:file\s+)?([^\s,]+)[,:]?\s*"
                r"(?:change|replace|update)\s+\"([^\"]+)\"\s+(?:to|with)\s+\"([^\"]+)\""
            ),
        ]

        for pattern in edit_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                instructions.append(
                    {
                        "file": match[0],
                        "old": match[1],
                        "new": match[2],
                    }
                )

        return instructions
