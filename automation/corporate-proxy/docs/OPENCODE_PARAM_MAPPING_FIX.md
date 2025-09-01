# OpenCode Parameter Mapping Fix

## Problem

OpenCode was rejecting tool calls with parameter validation errors:
- `write` tool expected `filePath` but received `file_path`
- `bash` tool required a `description` parameter that wasn't being provided
- All tools expected camelCase parameter names but the text parser extracted snake_case

### Error Examples
```
Invalid input for tool write:
Expected: "filePath" (string)
Received: undefined
Value: {"file_path":"hello.md","content":"hello"}

Invalid input for tool bash:
Expected: "description" (string, required)
Received: undefined
Value: {"command":"cat hello.md"}
```

## Root Cause

OpenCode follows JavaScript/TypeScript conventions and expects:
1. **camelCase parameter names** (e.g., `filePath` not `file_path`)
2. **Required parameters** that may not be obvious from the command (e.g., `description` for bash)

Our text parser extracts parameters in snake_case format, which is the Python convention.

## Solution Implemented

### 1. Parameter Name Mapping Configuration
Created `opencode_param_mappings.json` with mappings for all tools:
```json
{
  "write": {
    "file_path": "filePath",
    "content": "content"
  },
  "bash": {
    "command": "command",
    "_required_defaults": {
      "description": "Execute bash command"
    }
  },
  "edit": {
    "file_path": "filePath",
    "old_string": "oldString",
    "new_string": "newString",
    "replace_all": "replaceAll"
  }
}
```

### 2. Enhanced Tool Call Formatting
Updated `format_tool_calls_for_openai()` to:
1. Map snake_case to camelCase using the configuration
2. Add required default parameters when missing
3. Preserve unmapped parameters as-is

### 3. Automatic Transformation
The transformation happens automatically:
```python
# Input from text parser
{"name": "write", "parameters": {"file_path": "test.md", "content": "hello"}}

# Output to OpenCode
{"name": "write", "arguments": {"filePath": "test.md", "content": "hello"}}
```

## Configuration File

The mapping configuration supports:
- **Parameter renaming**: `"snake_case": "camelCase"`
- **Required defaults**: `"_required_defaults": {"param": "default_value"}`
- **Per-tool customization**: Each tool can have its own mappings

## Benefits

1. **Compatibility**: OpenCode now accepts all tool calls with proper parameter names
2. **Maintainability**: Mappings are centralized in a JSON file
3. **Extensibility**: Easy to add new tools or modify mappings
4. **Fallback Support**: Works even if config file is missing (uses defaults)

## Testing

Comprehensive tests verify:
- Snake_case to camelCase conversion
- Required default parameters are added
- Multiple tools with different mappings
- Streaming mode compatibility
- Unmapped tools preserve original names

## Usage

The fix is automatic - no changes needed to existing code:
1. Text parser extracts tool calls with snake_case parameters
2. Translation wrapper applies mappings based on tool name
3. OpenCode receives properly formatted camelCase parameters

## Future Improvements

- Could auto-detect parameter naming convention from OpenCode's tool schemas
- Could validate parameters against OpenCode's expected types
- Could provide better error messages when validation fails
