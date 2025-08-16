# Documentation Migration Guide

This guide maps the old documentation paths to their new locations after the reorganization.

## Path Mappings

### Infrastructure Documentation
| Old Path | New Path |
|----------|----------|
| `docs/SELF_HOSTED_RUNNER_SETUP.md` | `docs/infrastructure/self-hosted-runner.md` |
| `docs/GITHUB_ENVIRONMENTS_SETUP.md` | `docs/infrastructure/github-environments.md` |
| `docs/CONTAINERIZED_CI.md` | `docs/infrastructure/containerization.md` |
| `docs/GIT_HOOKS.md` | `docs/infrastructure/git-hooks.md` |

### AI Agent Documentation
| Old Path | New Path |
|----------|----------|
| `docs/AI_AGENTS.md` | `docs/ai-agents/README.md` |
| `docs/AI_AGENTS_SECURITY.md` | `docs/ai-agents/security.md` |
| `docs/AI_AGENTS_CLAUDE_AUTH.md` | `docs/ai-agents/claude-auth.md` |
| `docs/AGENT_AVAILABILITY_MATRIX.md` | `docs/ai-agents/agent-matrix.md` |
| `docs/AGENT_CONTAINERIZATION_STRATEGY.md` | `docs/ai-agents/containerization-strategy.md` |
| `docs/GITHUB_ETIQUETTE_FOR_AI_AGENTS.md` | `docs/ai-agents/github-etiquette.md` |
| `docs/PR_MONITORING.md` | `docs/ai-agents/pr-monitoring.md` |
| `docs/AUTO_REVIEW.md` | `docs/ai-agents/auto-review.md` |

### MCP Documentation
| Old Path | New Path |
|----------|----------|
| `docs/MCP_SERVERS.md` | `docs/mcp/servers.md` |
| `docs/MCP_TOOLS.md` | `docs/mcp/tools.md` |
| `docs/mcp/STDIO_VS_HTTP_MODES.md` | `docs/mcp/architecture/stdio-vs-http.md` |
| `docs/mcp/AI_AGENT_TRAINING_GUIDE.md` | `docs/mcp/architecture/training-guide.md` |
| `docs/mcp/mcp-demo.gif` | `docs/mcp/architecture/demo.gif` |

### Integration Documentation
| Old Path | New Path |
|----------|----------|
| `docs/GEMINI_SETUP.md` | `docs/integrations/ai-services/gemini-setup.md` |
| `docs/OPENCODE_CRUSH_INTEGRATION.md` | `docs/integrations/ai-services/opencode-crush.md` |
| `docs/OPENCODE_CRUSH_QUICK_REFERENCE.md` | `docs/integrations/ai-services/opencode-crush-ref.md` |
| `docs/OPENCODE_OPENROUTER_SETUP.md` | `docs/integrations/ai-services/openrouter-setup.md` |
| `docs/AI_TOOLKIT_COMFYUI_INTEGRATION_GUIDE.md` | `docs/integrations/creative-tools/ai-toolkit-comfyui.md` |
| `docs/LORA_TRANSFER_DOCUMENTATION.md` | `docs/integrations/creative-tools/lora-transfer.md` |

### Developer Documentation
| Old Path | New Path |
|----------|----------|
| `docs/CLAUDE_CODE_HOOKS.md` | `docs/developer/claude-code-hooks.md` |

## Additional Documentation

The following documentation from `packages/github_ai_agents/docs/` has been integrated into the main docs:

| Old Path | New Path |
|----------|----------|
| `packages/github_ai_agents/docs/architecture.md` | `docs/ai-agents/architecture/architecture.md` |
| `packages/github_ai_agents/docs/autonomous_mode.md` | `docs/ai-agents/architecture/autonomous-mode.md` |
| `packages/github_ai_agents/docs/subagents.md` | `docs/ai-agents/architecture/subagents.md` |
| `packages/github_ai_agents/docs/security.md` | `docs/ai-agents/security-detailed.md` |
| `packages/github_ai_agents/docs/subagents/*.md` | `docs/ai-agents/architecture/subagents/*.md` |

## New Organization Benefits

1. **Clearer Categories**: Documentation is now organized into logical categories (infrastructure, ai-agents, mcp, integrations, developer)
2. **Consistent Naming**: All files use lowercase with hyphens for consistency
3. **Better Navigation**: Each category has its own README with navigation links
4. **Scalability**: Easy to add new documentation without cluttering the root docs folder

## Updating Your Bookmarks

If you have bookmarked documentation pages, please update them to the new paths listed above. All content remains the same, only the paths have changed.

## Questions?

If you can't find a document you're looking for, check the [main documentation index](./README.md) or search the repository.
