# Corporate Proxy Testing Guide

This directory contains comprehensive tests for the Crush and OpenCode corporate proxy integrations, particularly focusing on tool execution functionality.

## Quick Start

```bash
# 1. Build containers (if not already built)
./build-containers.sh

# 2. Run all tests
./test-container-tools.sh
```

## Test Files

### Integration Tests

#### `test-tool-integration.py`
Full integration test that:
- Starts mock API and translation wrapper servers
- Sends properly formatted tool call responses
- Runs Crush/OpenCode containers with test requests
- Verifies tools actually execute (files are created)

```bash
python3 test-tool-integration.py
```

#### `test-container-tools.sh`
Direct container testing that:
- Tests write, list, and view tools
- Verifies actual file operations
- Works with the existing mock services

```bash
./test-container-tools.sh
```

### Unit Tests

#### `test-tool-flow.sh`
Tests the tool call flow without containers:
- Mock API tool detection
- Translation wrapper forwarding
- Response format conversion
- Pattern matching for different tools

```bash
./test-tool-flow.sh
```

### Manual Tests

#### `test-file-operations.sh`
Tests basic file operations (UID fix verification):
```bash
./test-file-operations.sh
```

#### `test-tool-execution.sh`
Tests tool execution with various commands:
```bash
./test-tool-execution.sh
```

## Building Containers

If containers aren't built:

```bash
# Option 1: Use the build script
./build-containers.sh

# Option 2: Build manually
cd automation/corporate-proxy
docker build -f crush/docker/Dockerfile -t crush-corporate:latest .
docker build -f opencode/docker/Dockerfile -t opencode-corporate:latest .
```

## How Tool Execution Works

### 1. Request Flow
```
Crush/OpenCode → Translation Wrapper → Mock API
                        ↓                  ↓
                 (forwards tools)    (detects patterns)
                        ↓                  ↓
                 OpenAI format ← Tool call response
```

### 2. Tool Call Format

**OpenAI Format (what Crush/OpenCode expect):**
```json
{
  "choices": [{
    "message": {
      "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
          "name": "write",
          "arguments": "{\"file_path\":\"test.txt\",\"content\":\"Hello\"}"
        }
      }]
    }
  }]
}
```

**Company Format (what mock API returns):**
```json
{
  "tool_calls": [{
    "id": "toolu_123",
    "type": "function",
    "function": {
      "name": "write",
      "arguments": "{\"file_path\":\"test.txt\",\"content\":\"Hello\"}"
    }
  }]
}
```

### 3. Tool Detection Patterns

The mock API detects these patterns in messages:

| Tool | Patterns | Example |
|------|----------|---------|
| ls | "list", "show files", "what files" | "List files in current directory" |
| view | "view", "read", "show" + filename | "View README.md" |
| write | "write", "create", "save" + filename | "Create file test.txt" |
| bash | "run", "execute", "command" | "Run ls -la" |
| grep | "grep", "search", "find" | "Search for TODO" |
| edit | "edit", "modify", "change" + filename | "Edit config.json" |

## Debugging

### Check Service Logs

When tests fail, check the service logs:

```bash
# In running containers
docker exec -it crush-corporate cat /tmp/logs/mock_api.log
docker exec -it crush-corporate cat /tmp/logs/translation_wrapper.log

# Or from test output
cat /tmp/mock_api_test.log
cat /tmp/wrapper_test.log
```

### Common Issues

1. **Tools not executing**
   - Check UID matches: `id -u` on host should match container user
   - Verify services are running: `curl http://localhost:8050/health`
   - Check tool detection patterns in `mock_api_with_tools.py`

2. **Container build failures**
   - Ensure Docker is running
   - Check network connectivity for downloading dependencies
   - Review Dockerfile for path issues

3. **Permission denied**
   - Containers must run with `--user $(id -u):$(id -g)`
   - Check mount permissions on `/workspace`

4. **Tool calls hanging**
   - Mock API must return proper tool_calls format
   - Translation wrapper must forward tools
   - Check for infinite loops in tool execution

## Test Coverage

The test suite covers:

- ✅ **UID Permission Fix**: Files can be written in mounted volumes
- ✅ **Tool Detection**: Pattern matching identifies tool requests
- ✅ **Tool Call Format**: Proper JSON structure for tool calls
- ✅ **Tool Execution**: Tools actually run and create/modify files
- ✅ **Response Handling**: Tool results are properly returned
- ✅ **Service Communication**: Mock API ↔ Translation Wrapper ↔ Client

## Adding New Tests

To add a new tool test:

1. Add pattern to `mock_api_with_tools.py`:
```python
tool_patterns = {
    "new_tool": r"\b(pattern1|pattern2)\b",
}
```

2. Add parameter extraction:
```python
elif tool_name == "new_tool":
    # Extract parameters
    params["param"] = extract_from_message(message)
```

3. Add test case:
```bash
test_patterns "Test new tool" "new_tool"
```

## CI/CD Integration

These tests can be integrated into CI/CD:

```yaml
# .github/workflows/test-corporate-proxy.yml
- name: Build containers
  run: ./automation/corporate-proxy/build-containers.sh

- name: Run integration tests
  run: python3 ./automation/corporate-proxy/test-tool-integration.py

- name: Run container tests
  run: ./automation/corporate-proxy/test-container-tools.sh
```

## Performance Testing

For performance testing:

```bash
# Time tool execution
time ./crush/scripts/run.sh run "Create 10 files"

# Test concurrent requests
for i in {1..5}; do
    ./opencode/scripts/run.sh run "Create file$i.txt" &
done
wait
```

## Security Notes

- Mock API uses a test token (`test-secret-token-123`)
- Services only bind to localhost in production
- Containers run as non-root users
- File operations are restricted to mounted volumes
