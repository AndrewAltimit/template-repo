# Gaea2 Validation Guide

> **Technical guide for the Gaea2 MCP server validation system**

## Overview

The Gaea2 MCP server provides two validation approaches:

| Approach | Scope | Default | Reliability |
|----------|-------|---------|-------------|
| Structural Validation | Node types, properties, connections | Enabled | High |
| Runtime CLI Validation | Full Gaea2 file loading | Disabled | Variable |

## Structural Validation

Structural validation operates in-memory without requiring the Gaea2 executable. It validates:

- Node types against the schema (184 supported types)
- Property types, ranges, and formats
- Connection compatibility between ports
- Required node presence (Export, SatMap)
- File format compliance with Gaea2 2.2.6.0

### Automatic Repairs

Structural validation includes automatic repair for common issues:

| Issue | Repair |
|-------|--------|
| Missing Export node | Auto-adds Export node |
| Missing color node | Auto-adds SatMap node |
| Property out of range | Clamps to valid range |
| Duplicate connections | Removes duplicates |
| Invalid property type | Converts to correct type |
| Orphaned nodes | Attempts connection to workflow |

### Usage

Structural validation is enabled by default:

```python
response = requests.post('http://localhost:8007/mcp/execute', json={
    'tool': 'create_gaea2_project',
    'parameters': {
        'project_name': 'my_terrain',
        'workflow': {...},
        'auto_validate': True  # Default
    }
})
```

## Runtime CLI Validation

Runtime validation uses Gaea.Swarm.exe to verify files by attempting a minimal resolution build. This catches issues that structural validation cannot detect.

### Current Status

Runtime CLI validation is disabled by default due to reliability issues:

- The CLI subprocess encounters "handle is invalid" IOException errors
- These errors occur even on valid files that open correctly in the Gaea2 GUI
- The issue appears to be related to console handle management in the .NET runtime

### Enabling Runtime Validation

If needed for specific debugging scenarios:

```bash
# Server-wide
python -m mcp_gaea2.server --mode http --enforce-file-validation
```

```python
# Per-request
response = requests.post('http://localhost:8007/mcp/execute', json={
    'tool': 'create_gaea2_project',
    'parameters': {
        'project_name': 'my_terrain',
        'workflow': {...},
        'runtime_validate': True
    }
})
```

### How Runtime Validation Works

1. Generates terrain file via structural validation
2. Launches Gaea.Swarm.exe with minimal resolution (512)
3. Monitors stdout/stderr for success/failure patterns
4. Terminates process after determination
5. Deletes file if validation fails

### Success Patterns

- `"Opening [filename]"` - File opened
- `"Loading devices"` - Hardware initialization
- `"Preparing Gaea"` - Application startup

### Failure Patterns

- `"corrupt"`, `"damaged"` - File corruption
- `"failed to load"` - Loading failure
- `"Unhandled exception"` - Runtime error
- `"IOException"` - I/O error

## Validation Tools

### validate_and_fix_workflow

Comprehensive structural validation with repair:

```python
response = requests.post('http://localhost:8007/mcp/execute', json={
    'tool': 'validate_and_fix_workflow',
    'parameters': {
        'workflow': {...}
    }
})
```

### validate_gaea2_runtime

Explicit runtime validation of existing file:

```python
response = requests.post('http://localhost:8007/mcp/execute', json={
    'tool': 'validate_gaea2_runtime',
    'parameters': {
        'project_path': 'C:\\path\\to\\file.terrain',
        'timeout': 60
    }
})
```

## Response Format

### Successful Creation

```json
{
  "success": true,
  "project_path": "C:\\path\\to\\file.terrain",
  "node_count": 5,
  "connection_count": 4,
  "validation_applied": true,
  "runtime_validation_performed": false,
  "runtime_validation_passed": false
}
```

### Validation Failure

```json
{
  "success": false,
  "error": "Validation failed: [details]",
  "validation_errors": ["error1", "error2"]
}
```

## Recommendations

1. **Use structural validation** (default) for normal operation
2. **Test critical files** manually in Gaea2 GUI when needed
3. **Enable runtime validation** only for debugging specific issues
4. **Use templates** for highest reliability

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Validation timeout | Complex file or Gaea2 hanging | Increase timeout parameter |
| File not found | Invalid path format | Use absolute Windows paths |
| Handle is invalid | CLI subprocess issue | Use structural validation only |
| Properties ignored | Wrong format | Use space-separated names |
