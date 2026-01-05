# Code Quality MCP Server

> A Model Context Protocol server for checking and enforcing code formatting and linting standards across multiple programming languages.

## Validation Status

| Component | Status | Description |
|-----------|--------|-------------|
| Format Checking | Validated | Python, JavaScript, TypeScript, Go, Rust |
| Linting | Validated | flake8, pylint, eslint, golint, clippy |
| Auto-formatting | Validated | Automatic code formatting |
| Markdown Links | Validated | Link validation in markdown files |

**Scope**: This server provides code quality checking and formatting. It requires the underlying tools (black, flake8, prettier, etc.) to be installed in the environment.

## Quick Start

```bash
# Using docker-compose (recommended)
docker-compose up -d mcp-code-quality

# Or run directly
python -m mcp_code_quality.server --mode http

# Test health
curl http://localhost:8010/health
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `format_check` | Check code formatting | `path` (required), `language` |
| `lint` | Run static analysis | `path` (required), `linter`, `config` |
| `autoformat` | Auto-fix formatting | `path` (required), `language` |
| `check_markdown_links` | Validate markdown links | `path` (required), `check_external`, `timeout` |

### Supported Languages

| Language | Formatter | Linters |
|----------|-----------|---------|
| Python | black | flake8, pylint |
| JavaScript | prettier | eslint |
| TypeScript | prettier | eslint |
| Go | gofmt | golint |
| Rust | rustfmt | clippy |

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MCP_CODE_QUALITY_PORT` | `8010` | Server listen port |
| `MCP_CODE_QUALITY_LOG_LEVEL` | `INFO` | Logging level |

### Linting Configuration

Each linter supports its own configuration format:

| Linter | Config Files |
|--------|--------------|
| flake8 | `.flake8`, `setup.cfg` |
| pylint | `.pylintrc` |
| eslint | `.eslintrc.json`, `.eslintrc.js` |

## Requirements

The following tools must be installed for full functionality:

| Language | Required Tools |
|----------|---------------|
| Python | `black`, `flake8`, `pylint` (optional) |
| JavaScript/TypeScript | `prettier`, `eslint` |
| Go | `gofmt`, `golint` |
| Rust | `rustfmt`, `clippy` |

## Docker Support

```bash
# Using docker-compose
docker-compose up -d mcp-code-quality

# View logs
docker-compose logs -f mcp-code-quality

# Rebuild after changes
docker-compose build mcp-code-quality
```

## Testing

```bash
# Run the test script
python tools/mcp/mcp_code_quality/scripts/test_server.py

# Health check
curl -s http://localhost:8010/health | jq
```

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| Tool not found | Formatter/linter not installed | Install required tool for language |
| Path not found | Invalid file path | Verify file exists |
| Config error | Invalid linter config | Check config file syntax |
| Timeout | Large directory | Use specific file paths |

## Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Sequential processing | Large directories slow | Target specific files |
| No caching | Repeated checks re-run | Implement client-side caching |
| Tool dependency | Requires external tools | Use Docker container |

## License

Part of the template-repo project. See repository LICENSE file.
