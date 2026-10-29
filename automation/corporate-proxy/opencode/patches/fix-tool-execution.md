# OpenCode Tool Execution Through the Text-Parsing Wrapper

## Problem

The Company API endpoints do not support native tool calls. The translation
wrapper works around this: it injects the tool definitions into the prompt,
parses tool calls out of the model's text answer, and returns them to OpenCode
as OpenAI `tool_calls`. OpenCode only executes tool calls for models it
considers tool-capable, so the two sides must be configured differently on
purpose.

## Configuration

**OpenCode** (`automation/corporate-proxy/opencode/config/opencode.jsonc`,
installed as `/etc/opencode/opencode.jsonc`): every Company model keeps
`"capabilities": { "tools": true }` so OpenCode sends its tool definitions and
executes the calls it gets back.

```jsonc
"claude-3.5-sonnet": {
  "capabilities": { "tools": true, "temperature": true }
}
```

**Translation wrapper** (`automation/corporate-proxy/shared/configs/models.json`):
`"supports_tools": false`, which makes the wrapper use prompt injection and
text parsing instead of forwarding native tools to the Company API.

```json
"supports_tools": false
```

## Tool names and parameters (OpenCode 2.x)

The wrapper maps parsed calls to OpenCode's tool schema using
`shared/configs/opencode_param_mappings.json`:

- `tool_renames`: names a model may still emit (for example `bash`) mapped to
  OpenCode 2.x tools (`shell`).
- `parameter_mappings`: parsed parameter names mapped to OpenCode's names.
  OpenCode 2.x `read`, `write` and `edit` take `path` (1.x used `filePath`),
  multi-word parameters are camelCase (`oldString`, `replaceAll`), and `shell`
  has no `description` parameter (listed under `_drop`).

The OpenCode prompt templates in `shared/services/tool_prompts.py` teach the
same syntax (`Write(path=...)`, `Shell(command=...)`).
`tests/test_opencode_param_mapping.py` checks every mapping target against the
tool schema OpenCode 2.2.1 sends; recapture it when upgrading OpenCode.

## Why This Works

- OpenCode sees a tool-capable model and executes the calls it receives.
- The wrapper sees `supports_tools: false` and parses tool calls from text.
- The wrapper returns the calls in OpenAI format with OpenCode's tool and
  parameter names.
- OpenCode executes them as if they came from a native tool-calling API and
  sends the results back, which the wrapper forwards as `Tool result:` text.
