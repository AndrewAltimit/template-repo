# OpenCode Company Integration Project

## Overview

This project customizes [OpenCode](https://github.com/sst/opencode) (an AI code assistant) to work exclusively with internal company AI APIs instead of public providers. The goal is to create a containerized version that can be toggled between official OpenCode and a company-specific build.

## Problem Specification

### Requirements

1. **Model Limitation**: Show ONLY 3 company models in OpenCode UI (not hundreds from models.dev)
2. **Custom API Format**: Use company's unique Bedrock-based API format
3. **Model Naming**: Use `company/modelname` format (e.g., `company/claude-3.5-sonnet`)
4. **Containerized**: Fully containerized solution for easy deployment
5. **Toggleable**: Ability to switch between official OpenCode and company version
6. **Mock Testing**: Support testing outside company network with mock endpoints

### Company API Format

The company uses a unique API format different from standard OpenAI/Anthropic APIs:

**Endpoint Format:**
```
https://{your-company-api-gateway}/api/v1/AI/{your-lab}/Models/{model-endpoint}
```

**Model Endpoints:**
- `ai-coe-bedrock-claude35-sonnet-200k:analyze=null` → Claude 3.5 Sonnet
- `ai-coe-bedrock-claude3-opus:analyze=null` → Claude 3 Opus
- `ai-coe-bedrock-gpt4:analyze=null` → GPT-4

**Request Format:**
```json
{
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 1000,
    "system": "You are a helpful AI assistant",
    "messages": [
        {"role": "user", "content": "Hello"}
    ]
}
```

**Response Format:**
```json
{
    "id": "msg_bdrk_01LK9E5YAExpxxbmpf17cwok",
    "type": "message",
    "role": "assistant",
    "model": "claude-3-5-sonnet-20240620",
    "content": [
        {"type": "text", "text": "Response text"}
    ],
    "stop_reason": "end_turn",
    "usage": {
        "input_tokens": 18,
        "output_tokens": 97
    }
}
```

## Current Implementation Status

### ✅ What's Working

1. **Model Limiting**: Successfully patched OpenCode to show only 3 models
   - Verified with `opencode models` command
   - Console shows: "[Company] Using Company models: company/claude-3.5-sonnet, company/claude-3-opus, company/gpt-4"

2. **API Translation Layer**: Created `company_translation_wrapper.py`
   - Translates OpenAI format → Company Bedrock format
   - Handles responses back to OpenAI format
   - Runs on port 8052

3. **Mock API**: Created `mock_company_api.py`
   - Simulates exact company API format
   - Returns "Hatsune Miku" responses for testing
   - Runs on port 8050

4. **Docker Images Built**:
   - `opencode-company-tui`: **FULLY WORKING VERSION with TUI support**
   - `opencode-company-final`: Old version (TUI broken)
   - `opencode-company-fixed`: Alternative build

5. **All Modes Working**:
   - `opencode` - Interactive TUI mode ✅
   - `opencode serve` - Headless server mode ✅
   - `opencode run "prompt"` - CLI mode ✅
   - `opencode models` - Lists only 3 models ✅

### ✅ Fixed Issues (TUI Now Working!)

1. **TUI Mode**: FIXED - The interactive terminal UI now works correctly
   - Root cause: TUI is a separate Go binary that wasn't being compiled/included
   - Solution: Build TUI binary separately and include it in the container
   - The TUI binary is placed at `/home/bun/.cache/opencode/tui/tui-linux-x64`

2. **Binary Compilation**: FIXED - OpenCode binary now properly finds TUI
   - Added patch to search for TUI binary in multiple locations
   - Set `OPENCODE_TUI_BINARY` environment variable as fallback
   - TUI launches without needing Go runtime

3. **Auto-Start Services**: ENHANCED - Mock services start automatically
   - Set `COMPANY_MOCK_MODE=true` to auto-start mock API and wrapper
   - Services run in background with logging to `/tmp/`
   - Cleanup on container exit
   - Ready to use immediately - no manual commands needed!

4. **Provider Initialization**: FIXED - OpenCode now correctly initializes provider
   - Root cause: Missing `npm` package specification and incorrect package name
   - Solution: Use `@ai-sdk/openai-compatible` package with `api` field set
   - Provider now loads successfully and makes API calls

## Technical Architecture

### Build Process

1. **Source Modification**:
   - Clone OpenCode from GitHub
   - Patch `models.ts` to return only company models
   - Override models list with `company-override.json`

2. **Compilation**:
   - Uses Bun to compile TypeScript to binary
   - Command: `bun build ./src/index.ts --compile --outfile opencode`

3. **Container Stack**:
   ```
   OpenCode (patched)
       ↓
   Translation Wrapper (port 8052)
       ↓
   Mock Company API (port 8050)
   ```

### Key Files

#### Docker Files
- `docker/opencode-company-tui-working.Dockerfile` - **FIXED VERSION with working TUI**
- `docker/opencode-company-tui-fixed.Dockerfile` - Alternative TUI fix approach
- `docker/opencode-company-final.Dockerfile` - Previous version (TUI broken)
- `docker/opencode-company-simple.Dockerfile` - Simplified approach
- `docker/opencode-company-with-go.Dockerfile` - Earlier attempt to fix Go issue

#### Patches
- `docker/patches/company-override.json` - Models definition (only 3)
- `docker/patches/models-company-simple.ts` - TypeScript patch for models.ts
- `docker/patches/tui-company-fix.ts` - **NEW: Patch to fix TUI binary detection**
- `docker/patches/company-provider-direct.ts` - Custom provider (unused)

#### Services
- `automation/proxy/mock_company_api.py` - Mock company API
- `automation/proxy/company_translation_wrapper.py` - Format translator
- `automation/proxy/api_translation_wrapper.py` - Earlier proxy version

#### Scripts
- `automation/proxy/build-company-tui.sh` - **Build fixed TUI version**
- `automation/proxy/run-company-tui.sh` - **Run with auto-start mock services**
- `automation/proxy/run-company-production.sh` - **Run with real company API**
- `automation/proxy/stop-mock-services.sh` - **Stop host mock services**
- `automation/proxy/test-company-tui.sh` - **Test TUI functionality**
- `automation/proxy/run-company-final.sh` - Old container (TUI broken)
- `automation/proxy/test-company-success.sh` - Verify models list

## Testing Outside Company Network

Since development happens outside the company network, we use mock endpoints:

```bash
# Environment variables for mock mode
export COMPANY_API_BASE=http://localhost:8050
export COMPANY_API_TOKEN=test-secret-token-123

# Mock API returns "Hatsune Miku" for all requests
```

For production on company network:
```bash
export COMPANY_API_BASE=https://{your-company-api-gateway}
export COMPANY_API_TOKEN=actual-token-here
```

## How to Use

### Option 1: Official OpenCode
```bash
docker run --rm -it opencode/opencode:latest
```

### Option 2: Company OpenCode with Working TUI (FIXED VERSION)

#### Quick Start with Mock Mode (Auto-starts services)
```bash
# Build the fixed image with TUI support
./automation/proxy/build-company-tui.sh

# Run with auto-start mock services
./automation/proxy/run-company-tui.sh

# Services start automatically! Just use OpenCode:
opencode                    # TUI mode (NOW WORKS!)
opencode serve              # Headless server mode
opencode run "your prompt"  # CLI mode
opencode models             # List models (shows only 3)
```

#### Production Mode (Real Company API)
```bash
# Set your company credentials
export COMPANY_API_BASE="https://{your-company-api-gateway}"
export COMPANY_API_TOKEN="your-real-token"

# Run in production mode
./automation/proxy/run-company-production.sh
```

#### Manual Mode (Control services yourself)
```bash
# Run without auto-start
docker run -it --rm \
  -e COMPANY_MOCK_MODE="false" \
  opencode-company-tui:latest

# Then manually start services inside container:
python3 mock_company_api.py &
python3 company_translation_wrapper.py &
opencode
```

### Option 3: Test TUI Functionality
```bash
# Run automated tests
./automation/proxy/test-company-tui.sh
```

## Remaining Work

### ✅ FIXED: TUI Compilation Issue

The TUI compilation issue has been resolved! The solution involved:
1. Building the Go TUI binary separately in a multi-stage Docker build
2. Placing the TUI binary in `/home/bun/.cache/opencode/tui/`
3. Patching the TUI TypeScript code to search for the binary in known locations
4. Setting the `OPENCODE_TUI_BINARY` environment variable as a fallback

### Nice to Have (Future Improvements)

1. **Streaming Support**: Add streaming responses for real-time output
2. **Better Model Names**: Show as "Company Claude 3.5" instead of full path
3. **CI/CD Pipeline**: Automated builds when OpenCode updates
4. **Configuration Management**: Environment-based config switching

## Success Criteria

The integration is considered complete when:

1. ✅ OpenCode shows ONLY 3 company models (DONE)
2. ✅ All API calls use company format (DONE)
3. ✅ Works with mock endpoints outside network (DONE)
4. ✅ TUI mode works without errors (FIXED!)
5. ✅ Can toggle between official/company builds (DONE)

**🎉 ALL SUCCESS CRITERIA MET!**

## For Future Developers

### Key Insights

1. OpenCode hardcodes model fetching from models.dev
2. The provider system expects certain structures (Zod schemas with `.openapi()`)
3. Bun compilation has limitations for complex Node.js apps
4. OpenCode uses `openrouter/` prefix for provider detection

### Debugging Tips

1. Check logs at: `/home/bun/.local/share/opencode/log/dev.log`
2. Test models list with: `opencode models`
3. Console output shows patch status: "[Company] Using Company models..."
4. The TUI spawn issue happens in the `tui` service

### Solution Details (Complete Fix)

1. **TUI Binary Issue**: OpenCode's TUI is a separate Go application
   - Built with Go 1.23 and `GOTOOLCHAIN=auto` for Go 1.24 compatibility
   - Compiled separately and placed in `/home/bun/.cache/opencode/tui/`
   - Patched TypeScript code to find the binary

2. **Provider Initialization Issue**: OpenCode couldn't load the provider
   - Added `"npm": "@ai-sdk/openai-compatible"` to provider config
   - Added `"api": "http://localhost:8052/v1"` for baseURL
   - Provider now initializes correctly with mock API

3. **Key Files**:
   - `docker/opencode-company-tui-working.Dockerfile` - Complete working build
   - `docker/patches/company-override.json` - Provider configuration with npm and api fields
   - `docker/patches/tui-company-fix.ts` - TUI binary detection patch
   - `docker/patches/models-company-simple.ts` - Models limiting patch

### Next Steps (Optional Improvements)

1. **Optimize Build Size**: Use Alpine-based images to reduce container size
2. **Embed TUI in Bun Binary**: Research Bun's embedding capabilities for true single-binary distribution
3. **OpenCode Fork**: Consider maintaining a fork with native company integration
4. **Upstream Contribution**: Propose plugin system to OpenCode for custom providers

## Contact

This integration was developed for internal company use. When on company network, use actual API endpoints. Outside network, use mock endpoints that return "Hatsune Miku" for testing.

---

*Note: Integration complete! All modes including TUI are now fully functional. The company-specific OpenCode build successfully limits models to only 3 company models and works with the company's unique API format.*
