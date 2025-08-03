# Real Agents Implementation Status

## Summary
This document describes the current implementation status of containerized AI agents using their actual CLI tools.

## Current Implementation

### 1. OpenCode (SST)
- **Tool**: `opencode` from https://github.com/sst/opencode
- **Version**: v0.3.112
- **Command**: `opencode run "prompt"`
- **Status**: ✅ Fully working with OpenRouter
- **Config**: Automatically detects `OPENROUTER_API_KEY` environment variable
- **Note**: Works seamlessly both locally and in containers

### 2. Crush (Charm Bracelet)
- **Tool**: `mods` CLI (crush is an alias)
- **Version**: v1.8.1
- **Command**: `mods -a openrouter "prompt"`
- **Status**: ✅ Fully working with OpenRouter
- **Config**: Uses modsrc configuration file
- **Note**: Requires `OPENAI_API_KEY` to be set to OpenRouter key value

## Removed Agents

### Codex (OpenAI)
- **Reason**: Does not support OpenRouter, requires real OpenAI API key
- **Alternative**: Use OpenCode or Crush for similar functionality

## Key Implementation Details

1. **OpenCode**:
   - Automatically detects and uses OpenRouter when `OPENROUTER_API_KEY` is set
   - Supports model selection with `-m` flag
   - No additional configuration needed

2. **Crush/Mods**:
   - Uses `mods` CLI with OpenRouter API
   - Configured via modsrc file
   - Requires workaround: `OPENAI_API_KEY` must be set to OpenRouter key

## Configuration Files

### OpenCode Configuration
Located at `/home/node/.config/opencode/.opencode.json`:
```json
{
  "providers": {
    "openrouter": {
      "apiKey": "${OPENROUTER_API_KEY}",
      "baseURL": "https://openrouter.ai/api/v1",
      "models": {...}
    }
  },
  "defaultModel": "openrouter/qwen-coder"
}
```

### Mods Configuration
Located at `/home/node/.config/mods/mods.yml`:
```yaml
default-model: qwen/qwen-2.5-coder-32b-instruct
default-api: openrouter
apis:
  openrouter:
    base-url: https://openrouter.ai/api/v1
    api-key-env: OPENROUTER_API_KEY
```

## Testing Commands

```bash
# Test OpenCode
docker-compose run --rm openrouter-agents opencode run "Write a hello world function"

# Test Crush/Mods
docker-compose run --rm -T -e OPENAI_API_KEY="${OPENROUTER_API_KEY}" \
  openrouter-agents mods -a openrouter "Write a hello world function"
```

## Conclusion

Both OpenCode and Crush are fully functional with OpenRouter. OpenCode provides the best experience with automatic detection of OpenRouter, while Crush/Mods requires a small workaround but offers reliable performance.
