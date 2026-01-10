# Code Quality MCP Server

> Enterprise security boundary for controlled CI/CD operations. Provides AI agents with approved code quality tools without granting unrestricted shell access.

## Purpose

This MCP server is designed for **enterprise environments** where AI agents cannot have direct shell/bash access. Instead of granting unrestricted command execution, this server provides:

```
+---------------------------------+
|         AI Agent (Claude)       |
|  Can call:     Cannot call:     |
|  format_check  subprocess.run   |
|  lint          os.system        |
|  run_tests     arbitrary bash   |
|  security_scan file deletion    |
|  type_check    network access   |
+---------------------------------+
              |
              v
+---------------------------------+
|   Code Quality MCP Server       |
|   (Security Boundary)           |
|                                 |
| - Path validation               |
| - Tool allowlist                |
| - Timeout enforcement           |
| - Audit logging                 |
| - Rate limiting                 |
+---------------------------------+
              |
              v
+---------------------------------+
|       Underlying Tools          |
|  black, pytest, mypy, bandit    |
|  (Controlled execution only)    |
+---------------------------------+
```

## Enterprise Pitch

> "Instead of granting your AI coding assistant unrestricted shell access,
> deploy the Code Quality MCP Server as a security boundary. The agent can
> run tests, check formatting, and scan for vulnerabilities - but only
> through approved, audited operations. No arbitrary command execution."

## Validation Status

| Component | Status | Description |
|-----------|--------|-------------|
| Format Checking | Validated | Python, JavaScript, TypeScript, Go, Rust |
| Linting | Validated | flake8, pylint, eslint, golint, clippy |
| Auto-formatting | Validated | Automatic code formatting |
| Test Running | Validated | pytest with coverage support |
| Type Checking | Validated | mypy with strict mode |
| Security Scanning | Validated | bandit vulnerability detection |
| Dependency Auditing | Validated | pip-audit CVE checking |
| Markdown Links | Validated | Link validation in markdown files |
| Path Validation | Validated | Allowlist-based path security |
| Audit Logging | Validated | All operations logged to file |
| Rate Limiting | Validated | Configurable per-operation limits |

## Quick Start

```bash
# Using docker-compose (recommended)
docker-compose up -d mcp-code-quality

# Or run directly
python -m mcp_code_quality.server --mode http

# Test health
curl http://localhost:8010/health

# Check server status and available tools
curl http://localhost:8010/mcp/execute -X POST \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_status", "parameters": {}}'
```

## Available Tools

### Code Quality Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `format_check` | Check code formatting | `path`, `language` |
| `lint` | Run static analysis | `path`, `linter`, `config` |
| `autoformat` | Auto-fix formatting issues | `path`, `language` |

### Testing & Verification Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `run_tests` | Execute pytest tests | `path`, `coverage`, `verbose`, `fail_fast`, `markers` |
| `type_check` | Run mypy type checking | `path`, `strict`, `config` |
| `security_scan` | Run bandit security analysis | `path`, `severity`, `confidence` |
| `audit_dependencies` | Check for CVEs in dependencies | `requirements_file` |
| `check_markdown_links` | Validate links in markdown | `path`, `check_external`, `timeout` |

### Administrative Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `get_status` | Server status and tool versions | (none) |
| `get_audit_log` | Retrieve audit log entries | `limit`, `operation` |

## Security Features

### Path Validation

Operations are restricted to approved directories only:

```bash
# Default allowed paths
MCP_CODE_QUALITY_ALLOWED_PATHS=/workspace,/app,/home

# Attempting to access /etc/passwd will fail:
# {"success": false, "error_type": "path_validation", "error": "Path not allowed: /etc/passwd"}
```

### Audit Logging

All operations are logged to a persistent file (JSON Lines format):

```json
{"timestamp": "2024-01-15T10:30:00Z", "operation": "format_check", "path": "/workspace/src/main.py", "success": true, "details": {"language": "python", "formatted": true}}
{"timestamp": "2024-01-15T10:30:05Z", "operation": "security_scan", "path": "/workspace/src/", "success": true, "details": {"finding_count": 0}}
```

### Rate Limiting

Generous rate limits protect against runaway operations:

| Operation | Limit | Period |
|-----------|-------|--------|
| format_check | 100 calls | per minute |
| lint | 50 calls | per minute |
| run_tests | 20 calls | per minute |
| security_scan | 20 calls | per minute |

### Timeout Protection

All subprocess operations have a 10-minute timeout (configurable) to prevent hanging processes from freezing the server.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_CODE_QUALITY_TIMEOUT` | `600` | Subprocess timeout in seconds |
| `MCP_CODE_QUALITY_ALLOWED_PATHS` | `/workspace,/app,/home` | Comma-separated allowed paths |
| `MCP_CODE_QUALITY_AUDIT_LOG` | `/var/log/mcp-code-quality/audit.log` | Audit log file path |
| `MCP_CODE_QUALITY_RATE_LIMIT` | `true` | Enable/disable rate limiting |

### Linting Configuration

Each linter supports its own configuration format:

| Linter | Config Files |
|--------|--------------|
| flake8 | `.flake8`, `setup.cfg` |
| pylint | `.pylintrc` |
| eslint | `.eslintrc.json`, `.eslintrc.js` |
| mypy | `mypy.ini`, `pyproject.toml` |

## Supported Languages

| Language | Formatter | Linters |
|----------|-----------|---------|
| Python | black | flake8, pylint, mypy, bandit |
| JavaScript | prettier | eslint |
| TypeScript | prettier | eslint |
| Go | gofmt | golint |
| Rust | rustfmt | clippy |

## Docker Support

```bash
# Using docker-compose
docker-compose up -d mcp-code-quality

# View logs
docker-compose logs -f mcp-code-quality

# Rebuild after changes
docker-compose build mcp-code-quality

# Access audit logs (persisted in Docker volume)
docker-compose exec mcp-code-quality cat /var/log/mcp-code-quality/audit.log
```

### Docker Volume for Audit Logs

The audit log is stored in a Docker volume for persistence:

```yaml
# In docker-compose.yml
volumes:
  - mcp-code-quality-logs:/var/log/mcp-code-quality
```

## Testing

```bash
# Run unit tests
cd tools/mcp/mcp_code_quality
pytest tests/ -v

# Run the integration test script
python tools/mcp/mcp_code_quality/scripts/test_server.py

# Health check
curl -s http://localhost:8010/health | jq
```

## Usage Examples

### Format Check
```bash
curl -X POST http://localhost:8010/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "format_check", "parameters": {"path": "/workspace/src/main.py", "language": "python"}}'
```

### Run Tests with Coverage
```bash
curl -X POST http://localhost:8010/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "run_tests", "parameters": {"path": "/workspace/tests/", "coverage": true, "verbose": true}}'
```

### Security Scan
```bash
curl -X POST http://localhost:8010/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "security_scan", "parameters": {"path": "/workspace/src/", "severity": "medium"}}'
```

### Get Audit Log
```bash
curl -X POST http://localhost:8010/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"tool": "get_audit_log", "parameters": {"limit": 50, "operation": "security_scan"}}'
```

## Error Types

All errors include an `error_type` field for programmatic handling:

| Error Type | Description |
|------------|-------------|
| `path_validation` | Path outside allowed directories |
| `rate_limit` | Too many requests |
| `timeout` | Operation timed out |
| `tool_not_found` | Required tool not installed |
| `unsupported_language` | Language not supported |
| `unsupported_linter` | Linter not supported |
| `exception` | Unexpected error |

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| Path not allowed | File outside allowed dirs | Add path to `MCP_CODE_QUALITY_ALLOWED_PATHS` |
| Rate limit exceeded | Too many requests | Wait or disable rate limiting |
| Tool not found | Formatter/linter not installed | Install required tool or use Docker |
| Timeout | Long-running operation | Increase `MCP_CODE_QUALITY_TIMEOUT` |
| Audit log permission denied | Cannot write log | Check directory permissions |

## Migration from v1.0

Version 2.0 adds enterprise security features. Key changes:

1. **Path validation** - Operations now require paths in allowed directories
2. **Audit logging** - All operations logged by default
3. **Rate limiting** - Enabled by default (disable with `MCP_CODE_QUALITY_RATE_LIMIT=false`)
4. **New tools** - `run_tests`, `type_check`, `security_scan`, `audit_dependencies`, `get_status`, `get_audit_log`
5. **Error types** - All errors now include `error_type` field

## License

Part of the template-repo project. See repository LICENSE file.
