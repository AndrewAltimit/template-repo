# OpenCode Corporate Proxy Integration

## Overview

This integration runs the OpenCode CLI (2.x, pinned in `docker/Dockerfile`) against corporate AI services. OpenCode
talks to the shared translation wrapper, which converts OpenAI chat-completions requests into the Company's
Bedrock-based API format and back, including text-based tool calling for endpoints without native tool support.

## Architecture

```
OpenCode CLI ("company" provider) -> Translation Wrapper (:8052) -> Company Bedrock API
                                                                -> Mock Company API (:8050, for testing)
```

OpenCode is configured entirely through its managed configuration, `config/opencode.jsonc`, which the image installs
as `/etc/opencode/opencode.jsonc`:

- a custom OpenAI-compatible provider `company` whose `baseURL` is the translation wrapper
  (`COMPANY_PROXY_BASE_URL`, default `http://localhost:8052/v1`)
- the Company models (`company/claude-3.5-sonnet`, `company/claude-3-opus`, `company/gpt-4`)
- policies that deny every other provider, so OpenCode cannot reach public APIs or OpenCode's hosted models
- no self-updates (`update: disable`, `OPENCODE_DISABLE_AUTOUPDATE=1`), no session sharing, no models.dev fetches

No OpenCode source files are patched; see
[opencode-maintenance.md](../../../docs/integrations/ai-services/opencode-maintenance.md) for what the former source
overlays did and how upgrades work.

## Quick Start

```bash
# Build (from anywhere; uses the repository root as build context)
./scripts/build.sh

# One-off prompt against the mock Company API
./scripts/run.sh "say hello"
# Expected: Hello! I'm running through a mock API. How can I help you today?

# TUI
./scripts/run.sh

# Shell with the services running (then `opencode`, `opencode run "..."`)
./scripts/run-interactive.sh
```

With Docker Compose:

```bash
docker compose --profile proxy build opencode-proxy
docker compose --profile proxy run --rm opencode-proxy opencode run "say hello"
docker compose --profile proxy up -d opencode-proxy    # services only; health on :8052/health
```

The image entrypoint (`scripts/start-services.sh`) starts the mock Company API and the translation wrapper, then runs
the given command, a shell when attached to a terminal, or keeps serving when detached.

## Production Deployment

```bash
export COMPANY_API_BASE="https://bedrock.internal.company.com"
export COMPANY_API_TOKEN="your-actual-company-token"
./scripts/run-production.sh
```

When `COMPANY_API_BASE` points anywhere other than the local mock, the mock is not started and the wrapper sends
requests to the Company API with `COMPANY_API_TOKEN`. OpenCode itself never sees the Company token.

## Model Mapping

| OpenCode model | Wrapper model ID | Company endpoint |
|----------------|------------------|------------------|
| `company/claude-3.5-sonnet` | `claude-3.5-sonnet` | `ai-coe-bedrock-claude35-sonnet-200k:analyze=null` |
| `company/claude-3-opus` | `claude-3-opus` | `ai-coe-bedrock-claude3-opus:analyze=null` |
| `company/gpt-4` | `gpt-4` | `ai-coe-bedrock-gpt4:analyze=null` |

To add a model, add it to `shared/configs/models.json` (endpoint) and to the `company` provider in
`config/opencode.jsonc` (same model ID).

## Building

`docker/Dockerfile` defaults to the checksum-verified upstream release tarball (musl build, Alpine runtime). To build
OpenCode from the release tag with upstream's own build script instead:

```bash
docker build --build-arg OPENCODE_BUILD=source \
  -f automation/corporate-proxy/opencode/docker/Dockerfile -t opencode-corporate:source .
```

Corporate CA certificates go in `shared/scripts/install-corporate-certs.sh`, which runs in every build stage. The
OpenCode binary uses the system CA store.

## Directory Structure

```
opencode/
├── config/
│   └── opencode.jsonc          # Managed OpenCode configuration (company provider + policies)
├── docker/
│   └── Dockerfile              # Release tarball or source build, Alpine runtime with the services
├── docs/
│   └── API_FORMAT.md           # Response formats OpenCode expects from the wrapper
├── patches/
│   └── fix-tool-execution.md   # How tool calls work without native tool support
├── scripts/
│   ├── build.sh                # Build opencode-corporate:latest
│   ├── run.sh                  # TUI or one-off prompt with mock services
│   ├── run-interactive.sh      # Shell with services running
│   ├── run-production.sh       # Against the real Company API
│   └── start-services.sh       # Image entrypoint
└── README.md
```

## Shared Services

From `automation/corporate-proxy/shared/`:
- `services/translation_wrapper.py` - OpenAI format to Company format, tool injection and text tool parsing
- `services/unified_tool_api.py` - Mock Company API for testing
- `configs/models.json` - Model to endpoint mapping
- `configs/opencode_param_mappings.json` - OpenCode 2.x tool names and parameters for parsed tool calls

## Troubleshooting

- **Model unavailable**: only `company/*` models are allowed; check the model is in `config/opencode.jsonc`.
- **Wrapper returns 404 "Model not found"**: the model ID is missing from `shared/configs/models.json`.
- **Tool calls not executed**: look for `Found N tool calls in text` or `Rejected unauthorized tool call` in
  `/tmp/logs/translation_wrapper.log`.
- **Connection refused**: check `curl http://localhost:8052/health` inside the container and that nothing else uses
  ports 8050/8052.

## Security Notes

- The Company token is passed to the wrapper via environment variables; never commit real tokens.
- `COMPANY_PROXY_API_KEY` is a placeholder; the wrapper does not authenticate OpenCode.
- The mock API only returns canned responses.
- Managed policies keep OpenCode on the Company provider even if a user or project config adds others.
