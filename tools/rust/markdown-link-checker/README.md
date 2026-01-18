# markdown-link-checker

Fast concurrent markdown link validator for CI/CD pipelines.

## Features

- Recursive markdown file discovery
- Concurrent HTTP link validation with configurable limits
- Local file link validation
- Configurable ignore patterns (regex)
- JSON output for CI integration
- Protocol-relative URL support
- Reference-style link detection
- Code block filtering (avoids false positives)

## Installation

```bash
# Build from source
cd tools/rust/markdown-link-checker
cargo build --release

# The binary will be at target/release/md-link-checker
```

## Usage

```bash
# Check all markdown files in current directory
md-link-checker .

# Check specific file
md-link-checker README.md

# Check only internal/local links (skip HTTP validation)
md-link-checker . --internal-only

# JSON output for CI integration
md-link-checker . --json

# Custom ignore pattern
md-link-checker . --ignore "example\\.com"

# Increase timeout and concurrency
md-link-checker . --timeout 30 --concurrent 20

# Verbose output
md-link-checker . -v
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--internal-only` | Skip HTTP/HTTPS link validation | false |
| `-i, --ignore` | Regex patterns to ignore (can specify multiple) | - |
| `--timeout` | HTTP request timeout in seconds | 10 |
| `--concurrent` | Maximum concurrent HTTP checks | 10 |
| `--json` | Output results as JSON | false |
| `-v, --verbose` | Enable verbose logging | false |

## Default Ignore Patterns

The following patterns are ignored by default:

- `http://localhost*` - Local development servers
- `http://127.0.0.1*` - Loopback addresses
- `http://192.168.*` - Private network addresses
- `http://0.0.0.0*` - All interfaces
- `#*` - Anchor links
- `mailto:*` - Email links
- `chrome://*` - Browser internal URLs
- `file://*` - Local file URLs
- `ftp://*` - FTP links
- `tel:*` - Phone links
- `javascript:*` - JavaScript links

## JSON Output Format

```json
{
  "success": true,
  "files_checked": 5,
  "total_links": 42,
  "broken_links": 2,
  "all_valid": false,
  "results": [
    {
      "file": "docs/README.md",
      "links": [
        {
          "url": "https://example.com",
          "valid": true
        },
        {
          "url": "./missing.md",
          "valid": false,
          "error": "File not found"
        }
      ],
      "broken_count": 1,
      "total_count": 2
    }
  ]
}
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All links valid |
| 1 | One or more broken links found |

## Performance

This tool is designed for CI/CD pipelines where speed matters:

- Concurrent HTTP checking (configurable limit)
- Semaphore-based rate limiting
- HEAD requests with GET fallback
- rustls for fast TLS (no OpenSSL dependency)

## Comparison with Python Version

| Feature | Python | Rust |
|---------|--------|------|
| Startup time | ~300ms | ~10ms |
| Binary size | requires Python | 3.6MB standalone |
| Concurrency | asyncio | tokio |
| Dependencies | aiohttp, mistune | reqwest, pulldown-cmark |

## License

MIT
