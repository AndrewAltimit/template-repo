# Real Agents Implementation Status

## Summary
As requested, I've updated all three containerized agents to use their actual CLI tools instead of the generic `mods` tool.

## Current Implementation

### 1. OpenCode (SST)
- **Tool**: `opencode` from https://github.com/sst/opencode
- **Version**: v0.3.112
- **Command**: `opencode run "prompt"`
- **Status**: ❌ Not working - requires provider configuration
- **Issue**: Returns "no providers found" error despite configuration file
- **Config**: Created `/home/node/.config/opencode/.opencode.json` with OpenRouter setup

### 2. Codex (OpenAI)
- **Tool**: `@openai/codex` npm package
- **Version**: 0.11.0
- **Command**: `codex exec "prompt"`
- **Status**: ⚠️ Partially working - runs but requires real OpenAI API key
- **Issue**: Expects `OPENAI_API_KEY` with actual OpenAI credentials, not OpenRouter
- **Note**: This is OpenAI's experimental Codex CLI tool

### 3. Crush (Charm Bracelet)
- **Tool**: `crush` from https://github.com/charmbracelet/crush
- **Version**: v0.2.1
- **Command**: `crush -y run -q "prompt"` (with YOLO and quiet flags)
- **Status**: ⚠️ Partially working - runs but without AI provider
- **Issue**: Provider configuration not being loaded from JSON file
- **Config**: Created provider config at `/home/node/.config/crush/providers.json`
- **Behavior**: Falls back to built-in responses without AI integration
- **Note**: Crush appears to expect interactive setup or database-based config

## Key Changes Made

1. **Removed mods**:
   - Removed the symlink from crush -> mods
   - Installed actual Crush binary via Go
   - Each agent now uses its real CLI tool

2. **Updated Agent Classes**:
   - `OpenCodeAgent`: Uses `opencode` executable with `run` subcommand
   - `CodexAgent`: Uses `codex` executable with `exec` subcommand
   - `CrushAgent`: Uses `crush` executable with `run` subcommand

3. **Configuration Files**:
   - Created OpenCode config at `configs/opencode-config.json`
   - Updated Dockerfile to copy configs to proper locations

## Challenges

1. **Authentication**: Each tool has its own authentication mechanism:
   - OpenCode: Expects provider configuration but still fails
   - Codex: Requires real OpenAI API key (not OpenRouter)
   - Crush: Needs interactive provider setup

2. **Non-Interactive Usage**: These tools are primarily designed for interactive use:
   - OpenCode: Has `run` command but provider setup is complex
   - Codex: Has `exec` command and works well for non-interactive
   - Crush: Primarily a TUI, `run` command exists but needs provider config

3. **Bypass/YOLO Flags**:
   - OpenCode: No bypass flags found
   - Codex: Has `--approval never` flag
   - Crush: Documentation mentions `--yolo` flag but not available in v0.2.1

## Recommendations

1. **For Production Use**: Consider using tools specifically designed for non-interactive CLI usage
2. **Authentication**: May need to implement provider-specific authentication for each tool
3. **Alternative**: Could create wrapper scripts that handle the authentication and configuration for each tool

## Testing Commands

```bash
# Test OpenCode
docker-compose run --rm -T -e OPENROUTER_API_KEY="${OPENROUTER_API_KEY}" \
  openrouter-agents opencode run "Write a hello world function"

# Test Codex (needs real OpenAI key)
docker-compose run --rm -T -e OPENAI_API_KEY="${OPENAI_API_KEY}" \
  openrouter-agents codex exec "Write a hello world function"

# Test Crush
docker-compose run --rm -T -e OPENROUTER_API_KEY="${OPENROUTER_API_KEY}" \
  openrouter-agents crush run "Write a hello world function"
```

## Conclusion

All three agents are now using their actual CLI tools as requested. However, none of them are fully functional due to authentication and configuration requirements. Each tool was designed with different use cases in mind, and adapting them for automated, non-interactive pipeline usage presents challenges.
