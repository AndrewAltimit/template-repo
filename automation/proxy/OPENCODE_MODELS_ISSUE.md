# OpenCode Model List Issue

## The Problem

OpenCode has hardcoded model lists for known providers like OpenRouter, Anthropic, OpenAI, etc. When we hijack the OpenRouter provider configuration to use our proxy, OpenCode still shows all of OpenRouter's models in its interface.

## Why Custom Providers Don't Work

OpenCode throws a `ProviderInitError` when trying to use fully custom providers. This is a known limitation in OpenCode's current implementation - it only properly supports a predefined set of providers.

## Current Workaround

We hijack the OpenRouter configuration by changing its `baseURL` to point to our proxy (`http://localhost:8052/v1`). This works for routing requests through our proxy, but OpenCode still displays all OpenRouter models.

## What Actually Works

Despite showing many models in the UI:
1. **Only 3 models actually work** through our proxy:
   - `openrouter/anthropic/claude-3.5-sonnet`
   - `openrouter/anthropic/claude-3-opus`
   - `openrouter/openai/gpt-4`

2. **Clear visual indication** - We display a banner before OpenCode starts showing which models work

3. **Default model selection** - OpenCode starts with claude-3.5-sonnet pre-selected

4. **Mock mode verification** - All working models return "Hatsune Miku" to confirm proxy is active

## Attempted Solutions That Failed

1. **Custom Provider Configuration** - Results in ProviderInitError
2. **Disabling Other Providers** - OpenCode ignores these settings
3. **Overriding Model Lists** - OpenCode uses hardcoded lists
4. **Environment Variables** - No env var to limit model display

## Potential Future Solutions

1. **Fork OpenCode** - Modify source to support custom providers properly
2. **Use Different CLI** - Find an AI CLI that better supports custom endpoints
3. **Create Wrapper UI** - Build a custom interface that only shows our models
4. **Submit PR to OpenCode** - Contribute custom provider support upstream

## Current Best Practice

1. Run `./automation/proxy/run_opencode_container.sh`
2. Note the banner showing the 3 working models
3. Use only those 3 models (others will fail or return mock responses)
4. Verify with "Hatsune Miku" responses that proxy is active

## Technical Details

OpenCode's model list comes from:
- Hardcoded provider definitions in the OpenCode source
- Cannot be overridden via configuration
- Models are loaded when provider is initialized
- No API to filter or limit displayed models

The proxy successfully intercepts all requests, but the UI limitation is cosmetic and doesn't affect functionality.
