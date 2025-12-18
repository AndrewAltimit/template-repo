# Gaea2 File Validation

> **Documentation for the Gaea2 MCP server validation system**

## Validation Overview

The Gaea2 MCP server provides two levels of validation:

| Level | Default | Description |
|-------|---------|-------------|
| Structural Validation | Enabled | Validates node types, properties, and connections |
| Runtime CLI Validation | Disabled | Tests files with Gaea.Swarm.exe |

## Structural Validation (Default)

Structural validation is automatically applied to all generated terrain files:

- Node type verification against schema
- Property type and range validation
- Connection compatibility checking
- Automatic repair of common issues
- Missing node detection (Export, SatMap)
- Duplicate connection removal

This validation runs in-memory and does not require the Gaea2 executable.

## Runtime CLI Validation (Optional)

Runtime validation uses Gaea.Swarm.exe to verify files can be opened by Gaea2. This feature is disabled by default due to reliability issues with the CLI subprocess.

**Note**: Files that fail CLI validation may still open correctly in the Gaea2 GUI. The CLI subprocess encounters "handle is invalid" errors that do not indicate actual file corruption.

### Enabling Runtime Validation

#### Server Startup

```bash
# Enable runtime validation at server start
python -m mcp_gaea2.server --mode http --enforce-file-validation
```

#### Per-Request

```python
# Enable for specific request
response = requests.post('http://localhost:8007/mcp/execute', json={
    'tool': 'create_gaea2_project',
    'parameters': {
        'project_name': 'my_terrain',
        'workflow': {...},
        'runtime_validate': True  # Enable for this request
    }
})
```

### Disabling for Tests

Integration tests can bypass all validation:

```python
import os

# Set before making requests
os.environ["GAEA2_BYPASS_FILE_VALIDATION_FOR_TESTS"] = "1"

# Test code here...

# Clean up
os.environ.pop("GAEA2_BYPASS_FILE_VALIDATION_FOR_TESTS", None)
```

## Requirements

Runtime CLI validation requires:

- Windows host system
- Gaea2 installation with Gaea.Swarm.exe
- `GAEA2_PATH` environment variable or `--gaea-path` argument

## Response Format

API responses include validation status:

```json
{
  "success": true,
  "project_path": "/path/to/file.terrain",
  "runtime_validation_performed": false,
  "runtime_validation_passed": false,
  "bypass_for_tests": false
}
```

With runtime validation enabled and successful:

```json
{
  "success": true,
  "project_path": "/path/to/file.terrain",
  "runtime_validation_performed": true,
  "runtime_validation_passed": true
}
```

Failed runtime validation:

```json
{
  "success": false,
  "error": "Generated file failed Gaea2 validation: [error message]",
  "validation_error": "[error message]",
  "file_deleted": true
}
```

## Recommendations

- Use structural validation (default) for most use cases
- Enable runtime validation only when debugging specific issues
- Files that pass structural validation typically work correctly in Gaea2
- Test critical files manually in the Gaea2 GUI if needed
