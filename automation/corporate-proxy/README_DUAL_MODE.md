# Per-Model Tool Support for Corporate Proxy

## Overview

The corporate proxy now supports **per-model tool mode configuration**, allowing different handling for each API endpoint:

1. **Native Mode**: Uses tool-enabled API endpoints with structured tool calls
2. **Text Mode**: Parses tool calls from text responses for non-tool-enabled endpoints

Each model can be configured independently based on its API capabilities:
- Modern APIs (Claude 3.5, GPT-4) use native mode
- Legacy or limited APIs use text mode
- Automatic mode selection based on model configuration

## Configuration

### Per-Model Configuration

Models are configured in `gemini-config.json` with individual tool modes:

```json
{
  "models": {
    "gemini-2.5-flash": {
      "endpoint": "claude-3.5-sonnet",
      "tool_mode": "native",
      "supports_tools": true
    },
    "gemini-1.5-flash": {
      "endpoint": "legacy-api",
      "tool_mode": "text",
      "supports_tools": false
    }
  }
}
```

### Environment Variables

```bash
# Default tool mode for models without explicit configuration
DEFAULT_TOOL_MODE=native  # or "text"

# Override specific model's tool mode (see transformation rules below)
GEMINI_MODEL_OVERRIDE_gemini_2_5_flash_tool_mode=text

# Maximum iterations for tool execution in text mode (default: 5)
MAX_TOOL_ITERATIONS=5

# Other existing variables
USE_MOCK_API=true
GEMINI_PROXY_PORT=8053
```

#### Environment Variable Name Transformation

When constructing environment variable names for model overrides, the model name undergoes the following transformation:

1. Replace all hyphens (`-`) with underscores (`_`)
2. Replace all dots (`.`) with underscores (`_`)
3. Prefix with `GEMINI_MODEL_OVERRIDE_`
4. Suffix with `_tool_mode`

**Examples:**

| Model Name | Environment Variable |
|------------|---------------------|
| `gemini-2.5-flash` | `GEMINI_MODEL_OVERRIDE_gemini_2_5_flash_tool_mode` |
| `gemini-1.5-pro` | `GEMINI_MODEL_OVERRIDE_gemini_1_5_pro_tool_mode` |
| `claude-3.5-sonnet` | `GEMINI_MODEL_OVERRIDE_claude_3_5_sonnet_tool_mode` |
| `gpt-4-turbo` | `GEMINI_MODEL_OVERRIDE_gpt_4_turbo_tool_mode` |
| `llama-2-70b-chat` | `GEMINI_MODEL_OVERRIDE_llama_2_70b_chat_tool_mode` |
| `model.v2.5.final` | `GEMINI_MODEL_OVERRIDE_model_v2_5_final_tool_mode` |

**Python code for reference:**
```python
def get_env_var_name(model_name):
    # Replace - and . with _
    safe_name = model_name.replace('-', '_').replace('.', '_')
    return f"GEMINI_MODEL_OVERRIDE_{safe_name}_tool_mode"
```

### Model Examples

```json
{
  "models": {
    // Modern API with tool support
    "gemini-2.5-flash": {
      "endpoint": "ai-coe-bedrock-claude35-sonnet-200k",
      "tool_mode": "native",
      "supports_tools": true,
      "description": "Claude 3.5 Sonnet with native tool support"
    },

    // Legacy API without tool support
    "gemini-1.5-flash": {
      "endpoint": "ai-coe-legacy-model",
      "tool_mode": "text",
      "supports_tools": false,
      "description": "Legacy model using text-based tool parsing"
    },

    // Experimental model
    "gemini-experimental": {
      "endpoint": "ai-coe-experimental",
      "tool_mode": "text",
      "supports_tools": false,
      "description": "Experimental model with text parsing"
    }
  },
  "default_tool_mode": "native",
  "max_tool_iterations": 5
}
```

## How It Works

### Automatic Mode Selection

The proxy automatically selects the appropriate mode based on the model:

1. **Request arrives** with model name (e.g., `gemini-2.5-flash`)
2. **Proxy checks** model configuration for `tool_mode`
3. **Mode selected**:
   - If `tool_mode: "native"` → Use structured tool calls
   - If `tool_mode: "text"` → Parse tools from text
   - If not specified → Use `default_tool_mode`

### Native Mode (for tool-enabled APIs)

Models configured with `"tool_mode": "native"`:
1. Forward tool definitions to the API
2. Expect structured tool calls in response
3. Return tool calls in Gemini format for the CLI to execute

### Text Mode (for non-tool-enabled APIs)

Models configured with `"tool_mode": "text"`:
1. Embed tool definitions in the prompt
2. Parse tool calls from the text response
3. Execute tools and feed results back to the AI
4. Continue until the task is complete

### Tool Call Format

The AI should respond with tool calls in this format:

```tool_call
{
  "tool": "read_file",
  "parameters": {
    "path": "/path/to/file.txt"
  }
}
```

Alternative format (also supported):
```xml
<tool>read_file(path="/path/to/file.txt")</tool>
```

### Example Flow

```
1. Gemini CLI → Proxy → Inject tools into prompt → Corporate API
2. Corporate API → Text with embedded tool calls → Proxy
3. Proxy → Parse tool calls → Execute tools → Format results
4. Proxy → Send results back → Corporate API → Continue task
5. Repeat until complete
```

### Continuation Endpoint

For text mode, use the continuation endpoint to handle the feedback loop:

```
POST /v1/models/{model}/continueWithTools
```

Request body:
```json
{
  "previous_response": "AI's previous response with tool calls",
  "tool_results": [
    {
      "tool": "read_file",
      "parameters": {"path": "test.txt"},
      "result": {"success": true, "content": "file contents"}
    }
  ],
  "original_request": {...},
  "conversation_history": [...]
}
```

## Usage Examples

### Starting the Proxy

```bash
# Start with default configuration (models use their configured modes)
python automation/corporate-proxy/gemini/gemini_proxy_wrapper.py

# Override default tool mode for unconfigured models
DEFAULT_TOOL_MODE=text python automation/corporate-proxy/gemini/gemini_proxy_wrapper.py

# Override specific model's tool mode (note the underscore transformation)
GEMINI_MODEL_OVERRIDE_gemini_2_5_flash_tool_mode=text python automation/corporate-proxy/gemini/gemini_proxy_wrapper.py

# Override multiple models
GEMINI_MODEL_OVERRIDE_gemini_2_5_flash_tool_mode=text \
GEMINI_MODEL_OVERRIDE_claude_3_5_sonnet_tool_mode=native \
GEMINI_MODEL_OVERRIDE_gpt_4_turbo_tool_mode=text \
python automation/corporate-proxy/gemini/gemini_proxy_wrapper.py

# With mock API for testing
USE_MOCK_API=true python automation/corporate-proxy/gemini/gemini_proxy_wrapper.py
```

### Checking Model Configuration

```bash
# Check health endpoint to see all model configurations
curl http://localhost:8053/health | jq .model_tool_modes

# Check available tools and their modes
curl http://localhost:8053/tools | jq .model_tool_modes

# Get full configuration
curl http://localhost:8053/ | jq .models
```

### Testing Both Modes

```bash
# Run the test script
python automation/corporate-proxy/tests/test_dual_mode.py

# Test with mock API
cd automation/corporate-proxy
USE_MOCK_API=true python shared/services/unified_tool_api.py &  # Start mock API
python gemini/gemini_proxy_wrapper.py &  # Start proxy
python tests/test_dual_mode.py  # Run tests
```

### Using with Gemini CLI

```bash
# Configure Gemini CLI to use the proxy
export GEMINI_API_BASE=http://localhost:8053/v1

# Use Gemini CLI normally - it will use the proxy
gemini "List the files in the current directory"
```

## Implementation Details

### Text Tool Parser

The `text_tool_parser.py` module provides:
- `TextToolParser`: Parses and executes tools from text
- `ToolInjector`: Injects tool definitions into prompts
- Tool result formatting for feedback

### Key Components

1. **Mode Detection**: Checks `TOOL_MODE` environment variable
2. **Prompt Enhancement**: Adds tool instructions for text mode
3. **Response Parsing**: Extracts tool calls from text
4. **Tool Execution**: Runs tools using existing executor
5. **Feedback Loop**: Continues conversation with results
6. **Completion Detection**: Identifies when task is done

## Benefits of Per-Model Configuration

- **Flexibility**: Each model uses the optimal mode for its capabilities
- **Mixed Environments**: Support both modern and legacy APIs simultaneously
- **Gradual Migration**: Transition models from text to native mode as APIs upgrade
- **Performance**: Native mode for capable APIs, text parsing only when needed
- **Transparency**: Clear per-model configuration visible in all endpoints
- **Dynamic Override**: Change model behavior without code changes via environment
- **Backward Compatible**: Existing configurations continue to work

## Troubleshooting

### Common Issues

1. **Tools not being parsed in text mode**
   - Check that `TOOL_MODE=text` is set
   - Verify the AI is using the correct tool call format
   - Check logs for parsing errors

2. **Infinite tool loops**
   - Adjust `MAX_TOOL_ITERATIONS` to limit iterations
   - Ensure completion detection is working

3. **Mode not switching**
   - Restart the proxy after changing `TOOL_MODE`
   - Check the `/health` endpoint for current mode

### Debug Mode

Enable debug logging:
```bash
FLASK_DEBUG=true python gemini_proxy_wrapper.py
```

## Future Enhancements

- Auto-detect optimal mode based on API capabilities
- Support for streaming responses in text mode
- Tool call batching for efficiency
- Custom parsing formats per API
- Tool execution caching
