# Gaea2 File Validation Guide

This guide explains how to use the Gaea2 file validation system to test if terrain files can be opened successfully in Gaea2.

## Overview

The validation system uses `Gaea.Swarm.exe --validate` to test terrain files without fully processing them. It monitors Gaea2's output in real-time to detect success or failure patterns.

## Key Features

- **Real-time monitoring**: Detects success/failure without waiting for process completion
- **Pattern detection**: Identifies specific success and error messages
- **Smart timeouts**: Prevents hanging on problematic files
- **Accurate results**: Proven to correctly identify working vs corrupted files

## Validation Tools

### 1. validate_gaea2_file

Validates a single terrain file.

```bash
curl -X POST http://192.168.0.152:8007/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "validate_gaea2_file",
    "parameters": {
      "file_path": "C:\\Gaea2\\MCP_Projects\\my_terrain.terrain",
      "timeout": 30
    }
  }'
```

**Response for successful file:**
```json
{
  "success": true,
  "file_path": "C:\\Gaea2\\MCP_Projects\\my_terrain.terrain",
  "duration": 3.61,
  "success_detected": true,
  "error_detected": false,
  "stdout": "Preparing Gaea Build Swarm 2.2.0.1...\nLoading devices...\nOpening my_terrain.terrain..."
}
```

**Response for corrupted file:**
```json
{
  "success": false,
  "file_path": "C:\\Gaea2\\MCP_Projects\\bad_terrain.terrain",
  "error": "File is corrupt or missing additional data",
  "duration": 2.06,
  "success_detected": false,
  "error_detected": true,
  "error_info": {
    "error_types": ["file_corrupt", "general_load_error"],
    "error_messages": ["Swarm failed to load the file: File is corrupt or missing additional data"]
  }
}
```

### 2. validate_gaea2_batch

Validates multiple files concurrently.

```bash
curl -X POST http://192.168.0.152:8007/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "validate_gaea2_batch",
    "parameters": {
      "file_paths": [
        "C:\\Gaea2\\MCP_Projects\\terrain1.terrain",
        "C:\\Gaea2\\MCP_Projects\\terrain2.terrain"
      ],
      "concurrent": 4
    }
  }'
```

### 3. test_gaea2_template

Tests a template by generating variations and validating them.

```bash
curl -X POST http://192.168.0.152:8007/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "test_gaea2_template",
    "parameters": {
      "template_name": "basic_terrain",
      "variations": 3,
      "server_url": "http://192.168.0.152:8007"
    }
  }'
```

## How It Works

### Success Detection

The validator looks for these patterns to confirm successful file opening:
- `"Opening [filename]"` - Gaea2 is opening the file
- `"Loading devices"` - Hardware initialization
- `"Activated [processor]"` - CPU/GPU detection
- `"Preparing Gaea"` - Gaea2 startup

When a success pattern is detected, the validator waits 3 seconds to ensure no errors follow.

### Error Detection

The validator immediately fails when detecting:
- `"corrupt"` or `"damaged"` - File corruption
- `"failed to load"` - Loading failure
- `"cannot open"` - Unable to open file
- `"missing data"` - Incomplete file format
- `"invalid file"` - Invalid format
- `"error loading"` - General loading error

### Process Flow

1. Launch Gaea2 with `--validate` flag
2. Monitor stdout/stderr in real-time
3. Check each output line for success/error patterns
4. On success pattern: wait 3s for confirmation
5. On error pattern: fail immediately
6. Kill Gaea2 process after determining result
7. Return detailed validation results

## Test Scripts

### test_improved_validation.py
Simple test to verify the validation system works:
```bash
python test_improved_validation.py
```

### test_validation_comprehensive.py
Comprehensive test with various file types:
```bash
python test_validation_comprehensive.py
```

### investigate_arctic_failure.py
Specific test for the corrupted arctic template:
```bash
python investigate_arctic_failure.py
```

## Proven Results

The validation system has been tested and proven accurate:

| Test Case | File Type | Validation Result | Correct? |
|-----------|-----------|-------------------|----------|
| Simple terrain | Mountain node only | ✅ Success | ✓ |
| Complex terrain | Multiple nodes/connections | ✅ Success | ✓ |
| Template: basic_terrain | 4 nodes | ✅ Success | ✓ |
| Template: detailed_mountain | 6 nodes | ✅ Success | ✓ |
| Template: volcanic_terrain | 6 nodes | ✅ Success | ✓ |
| Template: desert_canyon | 6 nodes | ✅ Success | ✓ |
| Template: mountain_range | 5 nodes | ✅ Success | ✓ |
| Template: river_valley | 6 nodes | ✅ Success | ✓ |
| Template: modular_portal_terrain | 11 nodes | ❌ Corrupt | ✓ |
| Template: volcanic_island | 9 nodes | ❌ Corrupt | ✓ |
| Template: canyon_system | 7 nodes | ❌ Corrupt | ✓ |
| Template: coastal_cliffs | 7 nodes | ❌ Corrupt | ✓ |
| Template: arctic_terrain | 7 nodes | ❌ Corrupt | ✓ |
| Empty file | No content | ❌ Failure | ✓ |
| Corrupted JSON | Invalid format | ❌ Failure | ✓ |

**Summary**: 6 out of 11 templates (55%) work correctly. The corrupted templates appear to have issues with certain node properties that exceed limits, causing file corruption.

## Common Issues and Solutions

### Issue: Validation times out
**Cause**: File might be very complex or Gaea2 is hanging
**Solution**: Increase timeout parameter (default 30s)

### Issue: "File not found" error
**Cause**: File path doesn't exist or wrong format
**Solution**: Use absolute Windows paths (C:\\path\\to\\file.terrain)

### Issue: False positives/negatives
**Cause**: Outdated validation system
**Solution**: Ensure you're using v2 with real-time monitoring

## Integration Example

```python
import asyncio
from tools.mcp.gaea2_file_validator import Gaea2FileValidator

async def validate_my_files():
    validator = Gaea2FileValidator()

    # Validate single file
    result = await validator.validate_file(
        "C:\\Gaea2\\MCP_Projects\\my_terrain.terrain",
        timeout=30
    )

    if result["success"]:
        print(f"✅ File opens successfully!")
        print(f"Duration: {result['duration']:.2f}s")
    else:
        print(f"❌ File failed validation")
        print(f"Error: {result['error']}")

    # Generate validation report
    report = validator.generate_report("validation_report.txt")
    print(report)

asyncio.run(validate_my_files())
```

## Conclusion

The Gaea2 validation system provides reliable, automated testing of terrain files. It accurately distinguishes between working files that open successfully in Gaea2 and corrupted files that fail to load. This eliminates the need for manual testing and provides immediate feedback during development.
