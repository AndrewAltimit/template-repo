# OpenCode Maintenance Guide

## Overview

This repo uses the upstream OpenCode CLI ([anomalyco/opencode](https://github.com/anomalyco/opencode), formerly
`sst/opencode`) in three places. All of them track the same release, currently **2.2.1** (2.x is upstream's current
major line; 1.19.x only receives maintenance releases).

| Where | How OpenCode gets there | Pin |
|-------|-------------------------|-----|
| `docker/mcp-opencode.Dockerfile` | Release tarball `opencode-linux-<arch>.tar.gz`, checksum-verified. The Rust MCP server does not call the CLI; the binary is shipped for `openrouter-agents`, which copies `/usr/local/bin/opencode`. | `OPENCODE_VERSION`, `OPENCODE_CHECKSUM_AMD64/ARM64` |
| `automation/corporate-proxy/opencode/docker/Dockerfile` | Release tarball `opencode-linux-<arch>-musl.tar.gz` (default), or built from the release tag with upstream's build script (`--build-arg OPENCODE_BUILD=source`). | `OPENCODE_VERSION`, `OPENCODE_CHECKSUM_AMD64/ARM64` |
| `tools/cli/containers/run_opencode_simple.sh` | npm package `@opencode/cli` (2.x; the old `opencode-ai` package only carries 1.x). | `OPENCODE_VERSION` in the script |

## Updating OpenCode

1. Pick the release and read its notes for CLI, config, and tool changes:
   ```bash
   gh api repos/anomalyco/opencode/releases --jq '.[] | select(.tag_name|startswith("v")) | .tag_name' | head
   ```
2. Take the checksums from the release's `SHA256SUMS` asset:
   ```bash
   curl -fsSL https://github.com/anomalyco/opencode/releases/download/v<version>/SHA256SUMS | grep 'opencode-linux'
   ```
   - mcp-opencode: `opencode-linux-x64.tar.gz` and `opencode-linux-arm64.tar.gz`
   - corporate proxy: `opencode-linux-x64-musl.tar.gz` and `opencode-linux-arm64-musl.tar.gz`
3. Update the three pins above, then build and check:
   ```bash
   docker compose build mcp-opencode
   docker compose run --rm --no-deps mcp-opencode opencode --version
   docker compose --profile proxy build opencode-proxy
   docker compose --profile proxy run --rm opencode-proxy opencode run "say hello"
   # Expected: "Hello! I'm running through a mock API. How can I help you today?"
   ```
4. Run the corporate proxy tests (`automation-cli ci run test-corporate-proxy`). If OpenCode changed its built-in
   tools, recapture their schema (see [Tool schema](#tool-schema)) and update the mappings.

## Corporate Proxy Integration

The proxy image routes OpenCode to the Company API through the shared translation layer
(`automation/corporate-proxy/shared/services/translation_wrapper.py`, port 8052) and, for local testing, the mock
Company API (`unified_tool_api.py`, port 8050).

### Configuration instead of source patches

The 1.0.x image cloned OpenCode at a fixed tag and overwrote upstream source files before a hand-rolled `bun build`.
That broke whenever upstream moved files, and it eventually stopped building at all. OpenCode 2.x supports everything
those overlays did through its configuration, so the image no longer patches source:

| Former overlay | What it did | 2.x replacement |
|----------------|-------------|-----------------|
| `shared/patches/models-company-simple.ts` (over `src/provider/models.ts`) plus `company-override.json` | Replaced the models.dev catalog with a static "openrouter" provider pointing at `http://localhost:8052/v1` and three Company models | `config/opencode.jsonc`: a custom `company` provider (`@opencode/ai/providers/openai-compatible`, `settings.baseURL` from `COMPANY_PROXY_BASE_URL`) with the same three models, plus `policies` that deny every other provider. `OPENCODE_DISABLE_MODELS_FETCH=1` stops catalog fetches. |
| `shared/patches/tui-company-fix.ts` (over `src/cli/cmd/tui.ts`) | Located a separately built Go TUI binary | Not needed: the 2.x TUI is part of the single CLI binary, so the Go build stage is gone too. |

The image installs `config/opencode.jsonc` as `/etc/opencode/opencode.jsonc`, OpenCode's managed (system)
configuration on Linux. Managed settings load last, so user or project `opencode.json` files cannot re-enable other
providers. It also sets `"update": "disable"` and `"share": "disabled"`.

### Building from source

`--build-arg OPENCODE_BUILD=source` follows the `build-cli` job of upstream's `.github/workflows/release.yml`: Bun
1.4.4 (the root `packageManager`), `bun install --frozen-lockfile`, a models.dev snapshot fetched with
`packages/core/script/update-models-snapshot.ts`, then `bun run build` in `packages/cli` with
`OPENCODE_TARGET=linux-<arch>-musl` so only the one target is built. It needs network access to GitHub, npm and
models.dev, and several GB of memory and disk. Use it only when policy requires building from source; otherwise use
the default release tarball.

### Tool schema

The Company API has no native tool calling, so the wrapper injects tool instructions into the prompt and parses tool
calls out of the answer (see `automation/corporate-proxy/opencode/patches/fix-tool-execution.md`). That path depends on
OpenCode's tool names and parameters:

- `shared/configs/opencode_param_mappings.json`: `tool_renames` (for example `bash` to `shell`) and
  `parameter_mappings` (2.x `read`/`write`/`edit` take `path`, not 1.x `filePath`; `shell` has no `description`).
- `shared/services/tool_prompts.py`: the OpenCode prompt examples (`Write(path=...)`, `Shell(command=...)`).
- `shared/configs/tool_config.json`: the parser's tool allow list (includes `shell`).
- `tests/test_opencode_param_mapping.py`: `OPENCODE_TOOL_SCHEMA` holds the parameters OpenCode 2.2.1 declares and
  every mapping target is checked against it.

To recapture the schema after an upgrade, point a provider at any OpenAI-compatible endpoint that logs request bodies
and look at the `tools` array OpenCode sends with a `opencode run` request.

### Paths and environment

| Item | Value |
|------|-------|
| Managed config | `/etc/opencode/opencode.jsonc` (from `automation/corporate-proxy/opencode/config/opencode.jsonc`) |
| OpenCode state | `$HOME/.local/share/opencode`; `start-services.sh` falls back to `HOME=/tmp/opencode-home` when the container runs as a UID that cannot write `HOME` |
| OpenCode to wrapper | `COMPANY_PROXY_BASE_URL` (default `http://localhost:8052/v1`), `COMPANY_PROXY_API_KEY` (placeholder; the wrapper does not check it) |
| Wrapper to Company API | `COMPANY_API_BASE`, `COMPANY_API_TOKEN`; the mock is only started when `COMPANY_API_BASE` is the local mock address |
| Service logs | `/tmp/logs/mock_api.log`, `/tmp/logs/translation_wrapper.log` |

## OpenCode 2.x behavior to keep in mind

- **Background service.** `opencode` and `opencode run` talk to a background server they start on demand. It keeps
  the environment it was started with and keeps running after the command exits. Automation passes `--standalone` so
  each run gets a private server with the caller's environment (`github-agents-cli`, the `board-agent-work` action,
  `tools/cli` scripts).
- **Prompt on stdin.** `opencode run` reads the prompt from stdin when no message argument is given.
- **Model selection.** `-m provider/model`; OpenRouter models are `openrouter/<vendor>/<model>`. Without `-m`, the CLI
  falls back to its own default, which may not be an OpenRouter model, so automation always passes one.
- **Permissions.** The default policy allows everything except reading `.env` files. In `run`, any permission request
  that would prompt is rejected unless `--auto` is given.
- **Network.** The binary uses the system CA store (`install-corporate-certs.sh` adds corporate CAs there) and honors
  `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY`; keep loopback in `NO_PROXY`, because the CLI reaches its server over
  localhost. `NODE_EXTRA_CA_CERTS` also works.

## Troubleshooting

```bash
# Services inside the proxy container
docker compose --profile proxy run --rm opencode-proxy bash
curl -fsS http://localhost:8052/health
tail -f /tmp/logs/translation_wrapper.log

# Models OpenCode can use (should list only company/*)
opencode models

# Configuration sources the server loaded (managed file first)
opencode --standalone debug config

# Data, config and cache directories
opencode debug paths

# Test the wrapper directly
curl -X POST http://localhost:8052/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-3.5-sonnet","messages":[{"role":"user","content":"test"}]}'
```

- **`Model unavailable: <provider>/<model>`**: the provider is denied by the managed policy (expected for anything
  but `company/*`) or the model ID is not in `opencode.jsonc`.
- **Tool calls not executed**: check the wrapper log for `Found N tool calls in text` and
  `Rejected unauthorized tool call`; the tool name or parameters probably no longer match OpenCode's schema.
- **`Model not found` from the wrapper (404)**: the model ID in `opencode.jsonc` has no entry in
  `shared/configs/models.json`.

## References

- [OpenCode repository](https://github.com/anomalyco/opencode)
- OpenCode docs: [providers](https://opencode.ai/v2/docs/providers), [policies](https://opencode.ai/v2/docs/policies),
  [network](https://opencode.ai/v2/docs/network), [migrating from 1.x](https://opencode.ai/v2/docs/migrate-v1)
- [Corporate proxy documentation](../../../automation/corporate-proxy/README.md)
- [OpenCode corporate proxy](../../../automation/corporate-proxy/opencode/README.md)
