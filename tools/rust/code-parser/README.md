# code-parser

A Rust library for parsing and applying code blocks from AI agent responses.

## Features

- **Code Block Extraction**: Parse markdown code blocks with language detection
- **Filename Detection**: Automatically extract filenames from AI response context
- **Language Inference**: Map file extensions to programming languages
- **Security**: Path traversal prevention and filename sanitization
- **Edit Instructions**: Parse structured edit instructions ("change X to Y")
- **File Application**: Optionally write extracted code to files (with `fs` feature)

## Installation

Add to your `Cargo.toml`:

```toml
[dependencies]
code-parser = { path = "tools/rust/code-parser" }

# Enable file system operations
code-parser = { path = "tools/rust/code-parser", features = ["fs"] }
```

## Usage

### Basic Code Block Extraction

```rust
use code_parser::CodeParser;

let response = r#"
Here's a Python function:

```python
def hello():
    print("Hello, world!")
```
"#;

let blocks = CodeParser::extract_code_blocks(response);
for block in blocks {
    println!("Language: {}", block.language);
    println!("Content: {}", block.content);
    if let Some(filename) = block.filename {
        println!("File: {}", filename);
    }
}
```

### Language Inference

```rust
use code_parser::CodeParser;

assert_eq!(CodeParser::infer_language("main.rs"), "rust");
assert_eq!(CodeParser::infer_language("script.py"), "python");
assert_eq!(CodeParser::infer_language("app.tsx"), "tsx");
```

### Filename Sanitization

```rust
use code_parser::CodeParser;

// Valid filenames
assert!(CodeParser::sanitize_filename("src/main.rs").is_ok());
assert!(CodeParser::sanitize_filename("./test.py").is_ok());

// Blocked paths (security)
assert!(CodeParser::sanitize_filename("/etc/passwd").is_err());
assert!(CodeParser::sanitize_filename("../secret.txt").is_err());
```

### Parse Edit Instructions

```rust
use code_parser::CodeParser;

let response = r#"In file `main.py`, change `print("hello")` to `print("goodbye")`"#;

let instructions = CodeParser::parse_edit_instructions(response);
for inst in instructions {
    println!("File: {}, Replace '{}' with '{}'", inst.file, inst.old, inst.new);
}
```

### Apply Code Blocks to Files (requires `fs` feature)

```rust
use code_parser::CodeParser;
use std::path::Path;

let response = r#"
Create file `src/utils.py`:

```python
def helper():
    pass
```
"#;

let (blocks, results) = CodeParser::extract_and_apply(response, Path::new("."));
for (file, status) in results {
    println!("{}: {}", file, status);
}
```

## Security Features

The library includes several security measures:

1. **Absolute Path Rejection**: Paths starting with `/` or drive letters are blocked
2. **Parent Directory Traversal**: Paths containing `..` are blocked
3. **Special Character Filtering**: Null bytes and newlines in filenames are rejected
4. **Base Path Enforcement**: When writing files, all paths are verified to be within the specified base directory

## API Reference

### Types

- `CodeBlock` - Represents an extracted code block
- `EditInstruction` - Represents a parsed edit instruction
- `CodeParserError` - Error type for parsing/application operations

### Functions

- `CodeParser::extract_code_blocks(response)` - Extract all code blocks
- `CodeParser::infer_language(filename)` - Infer language from extension
- `CodeParser::sanitize_filename(filename)` - Sanitize and validate a filename
- `CodeParser::parse_edit_instructions(response)` - Parse edit instructions
- `CodeParser::apply_code_blocks(blocks, base_path)` - Write blocks to files (fs feature)
- `CodeParser::extract_and_apply(response, base_path)` - Combined operation (fs feature)

## License

MIT
