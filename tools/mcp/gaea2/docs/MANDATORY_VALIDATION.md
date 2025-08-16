# Gaea2 Mandatory File Validation

As of the latest update, the Gaea2 MCP server now enforces **mandatory file validation** for all generated terrain files. This ensures that every `.terrain` file created can actually be opened in Gaea2 before being delivered to users.

## How It Works

1. **Automatic Validation**: After generating a terrain file, the server automatically attempts to open it in Gaea2
2. **Validation Failure**: If the file cannot be opened:
   - The file is immediately deleted
   - An error is returned to the user
   - The generation is marked as failed
3. **Validation Success**: Only files that successfully open in Gaea2 are kept and returned

## Benefits

- **No Bad Files**: Users will never receive terrain files that won't open
- **Early Detection**: Problems are caught immediately during generation
- **Clean Output**: Invalid files are automatically cleaned up

## For Integration Testing

Integration tests that specifically need to test invalid terrain files can bypass validation:

### Method 1: Environment Variable
```python
import os

# Set this before making requests
os.environ["GAEA2_BYPASS_FILE_VALIDATION_FOR_TESTS"] = "1"

# Your test code here...

# Clean up after
os.environ.pop("GAEA2_BYPASS_FILE_VALIDATION_FOR_TESTS", None)
```

### Method 2: Server Command Line
```bash
# Start server with validation disabled (NOT for production!)
python -m tools.mcp.gaea2.server --no-enforce-file-validation
```

## Requirements

- **Gaea2 Installation**: The server must have access to Gaea2 executable
- **Windows Environment**: File validation requires Windows with Gaea2 installed
- **GAEA2_PATH**: Environment variable or command line argument pointing to `Gaea.Swarm.exe`

## Response Format

The API response now includes validation information:

```json
{
  "success": true,
  "project_path": "/path/to/file.terrain",
  "file_validation_performed": true,
  "file_validation_passed": true,
  "bypass_for_tests": false
}
```

Failed validation response:
```json
{
  "success": false,
  "error": "Generated file failed Gaea2 validation: File corrupt or invalid",
  "validation_error": "File corrupt or invalid",
  "file_deleted": true
}
```

## Important Notes

1. **Production Use**: Never disable validation in production environments
2. **Performance**: Validation adds ~5-30 seconds to generation time
3. **Error Details**: Validation errors include specific Gaea2 error messages when available
4. **Automatic Cleanup**: Failed files are automatically deleted - no manual cleanup needed

## Example Usage

```python
# Normal usage - validation enforced
response = requests.post(
    "http://localhost:8007/mcp/execute",
    json={
        "tool": "create_gaea2_from_template",
        "parameters": {
            "template_name": "mountain_range",
            "project_name": "my_terrain"
        }
    }
)

result = response.json()
if result["success"]:
    print(f"File created and validated: {result['project_path']}")
else:
    print(f"Generation failed: {result['error']}")
    # No need to clean up - file already deleted
```
