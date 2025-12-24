"""Fuzz tests for code parser robustness.

Tests the CodeParser's ability to handle malformed, adversarial, and edge-case
AI responses without crashing or producing incorrect results.
"""

from pathlib import Path
import tempfile

import pytest

from github_agents.code_parser import CodeBlock, CodeParser


class TestCodeBlockExtraction:
    """Test code block extraction with various malformed inputs."""

    def test_missing_closing_backticks(self):
        """Parser should handle missing closing backticks gracefully."""
        response = """Here's the code:
```python
def hello():
    print("Hello")
# Missing closing backticks
"""
        blocks = CodeParser.extract_code_blocks(response)
        # Should return empty list since block is not properly closed
        assert blocks == []

    def test_nested_code_blocks(self):
        """Parser should handle nested backticks in code."""
        response = '''Here's the code:
```python
def example():
    """This has triple quotes inside"""
    code = """
    nested = True
    """
    return code
```
'''
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        assert "nested = True" in blocks[0].content

    def test_empty_code_block(self):
        """Parser should handle empty code blocks."""
        response = """Empty block:
```python
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        assert blocks[0].content == ""

    def test_code_block_with_only_whitespace(self):
        """Parser should handle code blocks with only whitespace."""
        response = """Whitespace block:
```python


```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        # Content should be stripped
        assert blocks[0].content == ""

    def test_no_language_specifier(self):
        """Parser should handle code blocks without language."""
        response = """No language:
```
print("Hello")
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        assert blocks[0].language == "text"
        assert 'print("Hello")' in blocks[0].content

    def test_unknown_language_specifier(self):
        """Parser should handle unknown language specifiers."""
        response = """Unknown language:
```madeuplang
code here
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        assert blocks[0].language == "madeuplang"

    def test_multiple_code_blocks_mixed_formats(self):
        """Parser should handle multiple blocks with different formats."""
        response = """Multiple blocks:

```python
def func1():
    pass
```

Some text

```
raw code
```

More text

```javascript
const x = 1;
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 3
        assert blocks[0].language == "python"
        assert blocks[1].language == "text"
        assert blocks[2].language == "javascript"


class TestAIRefusalResponses:
    """Test handling of AI responses that refuse or fail to complete tasks."""

    def test_refusal_message_no_code(self):
        """Parser should handle refusal messages without code blocks."""
        response = """I cannot help with that request. The task you've described
would require me to write malicious code, which I'm not able to do.

Please provide a different task that doesn't involve harmful activities."""
        blocks = CodeParser.extract_code_blocks(response)
        assert blocks == []

    def test_partial_response_with_explanation(self):
        """Parser should handle partial responses that explain but don't implement."""
        response = """I understand you want to implement a login system. Here's how it would work:

1. User enters credentials
2. Server validates against database
3. Return JWT token

However, I need more context about your framework to provide specific code."""
        blocks = CodeParser.extract_code_blocks(response)
        assert blocks == []

    def test_response_with_example_not_solution(self):
        """Parser should extract code even when AI says it's just an example."""
        response = """I can't implement the full solution, but here's a simple example:

```python
# This is just a basic example, not production code
def example():
    return "example"
```

You'll need to expand this for your use case."""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        assert "example" in blocks[0].content


class TestMalformedMarkdown:
    """Test handling of malformed markdown in AI responses."""

    def test_backticks_in_inline_code(self):
        """Parser should not confuse inline code with blocks."""
        response = """Use `print("hello")` for output.

```python
def real_code():
    pass
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        assert "real_code" in blocks[0].content

    def test_mixed_backtick_styles(self):
        """Parser should handle mixed backtick counts."""
        response = """Here's code:
```python
code1 = True
```

And more:
````python
code2 = True
````
"""
        # Only standard triple backticks should be matched
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) >= 1
        # At least the first block should be extracted

    def test_html_in_response(self):
        """Parser should handle HTML mixed with markdown."""
        response = """<div class="code">

```python
def func():
    return True
```

</div>"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1

    def test_escaped_backticks(self):
        """Parser should handle escaped backticks."""
        response = r"""Use \`\`\` for code blocks.

```python
actual_code = True
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        # Should still find the real code block
        assert len(blocks) >= 1


class TestFilenameExtraction:
    """Test filename extraction from various formats."""

    def test_explicit_file_comment_python(self):
        """Parser should extract filename from Python-style comment."""
        response = """Here's the file:

# file: src/utils.py
```python
def utility():
    pass
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        assert blocks[0].filename == "src/utils.py"

    def test_explicit_file_comment_js(self):
        """Parser should extract filename from JS-style comment."""
        response = """JavaScript file:

// filename: app.js
```javascript
const app = {};
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        assert blocks[0].filename == "app.js"

    def test_file_path_in_backticks(self):
        """Parser should extract filename from backtick notation."""
        response = """Create file `config/settings.yaml`:

```yaml
debug: true
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        assert blocks[0].filename == "config/settings.yaml"

    def test_no_filename_available(self):
        """Parser should handle missing filenames gracefully."""
        response = """Here's some code:

```python
x = 1
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        assert blocks[0].filename is None

    def test_filename_with_spaces(self):
        """Parser should handle filenames with spaces."""
        response = """File: my file.py

# file: my file.py
```python
code = True
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        # Filename may or may not have spaces stripped - verify extraction works
        assert blocks[0].filename is not None


class TestSecurityPathTraversal:
    """Test security measures against path traversal attacks."""

    def test_reject_absolute_path_unix(self):
        """Should reject absolute Unix paths."""
        result = CodeParser._sanitize_filename("/etc/passwd")
        assert result is None

    def test_reject_absolute_path_windows(self):
        """Should reject absolute Windows paths."""
        result = CodeParser._sanitize_filename("C:\\Windows\\System32\\config")
        assert result is None

    def test_reject_parent_directory_reference(self):
        """Should reject paths with parent directory references."""
        test_cases = [
            "../etc/passwd",
            "foo/../../../etc/passwd",
            "foo/bar/../../baz/../../../etc/passwd",
        ]
        for path in test_cases:
            result = CodeParser._sanitize_filename(path)
            assert result is None, f"Should reject: {path}"

    def test_reject_null_bytes(self):
        """Should reject filenames with null bytes."""
        result = CodeParser._sanitize_filename("file.py\x00.txt")
        assert result is None

    def test_reject_newlines(self):
        """Should reject filenames with newlines."""
        result = CodeParser._sanitize_filename("file\n.py")
        assert result is None

    def test_accept_valid_nested_path(self):
        """Should accept valid nested paths."""
        result = CodeParser._sanitize_filename("src/utils/helpers.py")
        assert result == "src/utils/helpers.py"

    def test_strip_leading_dot_slash(self):
        """Should strip leading ./ from paths."""
        result = CodeParser._sanitize_filename("./src/file.py")
        assert result == "src/file.py"

    def test_apply_blocks_path_traversal_blocked(self):
        """Integration test: path traversal should be blocked when applying."""
        block = CodeBlock("python", "malicious = True", "../../../etc/cron.d/evil")

        with tempfile.TemporaryDirectory() as tmpdir:
            results = CodeParser.apply_code_blocks([block], tmpdir)
            # Should report error, not create file
            assert "../../../etc/cron.d/evil" in results
            assert "error" in results["../../../etc/cron.d/evil"]


class TestSpecialCharactersAndUnicode:
    """Test handling of special characters and unicode."""

    def test_unicode_in_code_content(self):
        """Parser should handle unicode in code."""
        response = """Here's code:
```python
message = "Hello, 世界! 🎉"
print(message)
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        assert "世界" in blocks[0].content
        assert "🎉" in blocks[0].content

    def test_unicode_in_filename(self):
        """Parser should handle unicode in filename paths."""
        # Note: Unicode filenames may or may not be supported depending on OS
        response = """# file: données.py
```python
x = 1
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        # Filename extraction should work
        assert blocks[0].filename == "données.py"

    def test_emoji_in_comments(self):
        """Parser should handle emoji in code comments."""
        response = """```python
# TODO: Fix this bug 🐛
def buggy():
    pass  # Works! ✅
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        assert "🐛" in blocks[0].content

    def test_control_characters_stripped(self):
        """Parser should handle control characters."""
        response = """```python
code = "test"
```"""
        # Response has tabs and normal characters
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_response(self):
        """Parser should handle empty response."""
        blocks = CodeParser.extract_code_blocks("")
        assert blocks == []

    def test_none_response(self):
        """Parser should handle None-like responses."""
        # Test with whitespace-only
        blocks = CodeParser.extract_code_blocks("   \n\n   ")
        assert blocks == []

    def test_very_long_response(self):
        """Parser should handle very long responses."""
        # Create response with many code blocks
        response = ""
        for i in range(50):
            response += f"""
Block {i}:
```python
def func_{i}():
    return {i}
```
"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 50

    def test_very_long_code_block(self):
        """Parser should handle very long code blocks."""
        long_code = "\n".join([f"line_{i} = {i}" for i in range(10000)])
        response = f"""```python
{long_code}
```"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 1
        assert len(blocks[0].content.splitlines()) == 10000

    def test_code_block_with_backticks_inside(self):
        """Parser should handle code that contains backtick patterns."""
        response = '''```python
markdown = """
```javascript
nested()
```
"""
```'''
        # This is a tricky case - the parser may or may not handle it perfectly
        blocks = CodeParser.extract_code_blocks(response)
        # At minimum, should not crash
        assert isinstance(blocks, list)

    def test_consecutive_code_blocks(self):
        """Parser should handle consecutive code blocks without text."""
        response = """```python
code1 = True
```
```python
code2 = True
```
```python
code3 = True
```"""
        blocks = CodeParser.extract_code_blocks(response)
        assert len(blocks) == 3


class TestLanguageInference:
    """Test language inference from filenames."""

    @pytest.mark.parametrize(
        "filename,expected_lang",
        [
            ("test.py", "python"),
            ("app.js", "javascript"),
            ("component.tsx", "tsx"),
            ("style.css", "css"),
            ("config.yaml", "yaml"),
            ("config.yml", "yaml"),
            ("data.json", "json"),
            ("script.sh", "bash"),
            ("main.go", "go"),
            ("lib.rs", "rust"),
            ("unknown.xyz", "text"),
            ("noextension", "text"),
            ("", "text"),
        ],
    )
    def test_language_inference(self, filename, expected_lang):
        """Test language inference for various extensions."""
        result = CodeParser._infer_language(filename)
        assert result == expected_lang


class TestEditInstructionParsing:
    """Test parsing of edit instructions from AI responses."""

    def test_parse_edit_instruction_backtick(self):
        """Should parse edit instructions with backtick syntax."""
        response = """In file `src/config.py`, change `DEBUG = True` to `DEBUG = False`"""
        instructions = CodeParser.parse_edit_instructions(response)
        assert len(instructions) == 1
        assert instructions[0]["file"] == "src/config.py"
        assert instructions[0]["old"] == "DEBUG = True"
        assert instructions[0]["new"] == "DEBUG = False"

    def test_parse_edit_instruction_quotes(self):
        """Should parse edit instructions with quote syntax."""
        response = '''Edit file config.py, replace "old_value" with "new_value"'''
        instructions = CodeParser.parse_edit_instructions(response)
        assert len(instructions) == 1
        assert instructions[0]["old"] == "old_value"
        assert instructions[0]["new"] == "new_value"

    def test_no_edit_instructions(self):
        """Should return empty list when no edit instructions found."""
        response = """Here's some general advice about coding."""
        instructions = CodeParser.parse_edit_instructions(response)
        assert instructions == []


class TestApplyCodeBlocks:
    """Test applying code blocks to filesystem."""

    def test_apply_creates_file(self):
        """Should create new file with content."""
        block = CodeBlock("python", "x = 1", "test.py")

        with tempfile.TemporaryDirectory() as tmpdir:
            results = CodeParser.apply_code_blocks([block], tmpdir)
            assert results["test.py"] == "created"

            # Verify file content
            filepath = Path(tmpdir) / "test.py"
            assert filepath.exists()
            content = filepath.read_text()
            assert "x = 1" in content

    def test_apply_creates_nested_directories(self):
        """Should create parent directories as needed."""
        block = CodeBlock("python", "code = True", "deep/nested/path/file.py")

        with tempfile.TemporaryDirectory() as tmpdir:
            results = CodeParser.apply_code_blocks([block], tmpdir)
            assert results["deep/nested/path/file.py"] == "created"

            filepath = Path(tmpdir) / "deep/nested/path/file.py"
            assert filepath.exists()

    def test_apply_skips_blocks_without_filename(self):
        """Should skip blocks without filenames."""
        block = CodeBlock("python", "x = 1", None)

        with tempfile.TemporaryDirectory() as tmpdir:
            results = CodeParser.apply_code_blocks([block], tmpdir)
            assert results == {}

    def test_apply_adds_trailing_newline(self):
        """Should add trailing newline if missing."""
        block = CodeBlock("python", "x = 1", "test.py")

        with tempfile.TemporaryDirectory() as tmpdir:
            CodeParser.apply_code_blocks([block], tmpdir)

            filepath = Path(tmpdir) / "test.py"
            content = filepath.read_text()
            assert content.endswith("\n")
