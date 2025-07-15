# Setting Up Gemini AI Code Review

This repository includes automatic AI-powered code review for pull requests using Google's Gemini AI CLI.

## Features

- Automatic code review on every pull request
- **Conversation history cleared before each review** for fresh, unbiased analysis
- Analyzes code changes and provides constructive feedback
- Posts review comments directly to the PR
- Non-blocking - won't fail your PR if the CLI is unavailable
- Uses official Gemini CLI with automatic authentication
- Receives project-specific context from PROJECT_CONTEXT.md

## Setup Instructions

### For GitHub-Hosted Runners

The workflow will attempt to install Gemini CLI automatically if Node.js is available.

### For Self-Hosted Runners

1. **Install Node.js 18+** (recommended version 22.16.0)

   ```bash
   # Using nvm
   nvm install 22.16.0
   nvm use 22.16.0
   ```

2. **Install Gemini CLI**

   ```bash
   npm install -g @google/gemini-cli
   ```

3. **Authenticate** (happens automatically on first use)

   ```bash
   # Run the gemini command - it will prompt for authentication
   gemini
   ```

That's it! The next time you open a pull request, Gemini will automatically review your code.

## How It Works

1. When a PR is opened or updated, the Gemini review job runs
2. **Conversation history is automatically cleared** using the `clear_gemini_history` MCP tool to ensure fresh, unbiased review
3. **Project context is loaded** from PROJECT_CONTEXT.md
4. It analyzes:
   - Project-specific context and philosophy
   - Changed files
   - Code diff
   - PR title and description
5. Gemini provides feedback on:
   - Container configurations and security
   - Code quality (with project standards in mind)
   - Potential bugs
   - Project-specific concerns
   - Positive aspects
6. The review is posted as a comment on the PR

### Why Clear History?

Clearing conversation history before each review ensures:
- No bias from previous reviews
- Fresh perspective on each PR
- Consistent quality of feedback
- No confusion from unrelated context

## Project Context

Gemini receives detailed project context from `PROJECT_CONTEXT.md`, which includes:

- Container-first philosophy
- Single-maintainer design
- What to prioritize in reviews
- Project-specific patterns and standards

This ensures Gemini "hits the ground running" with relevant, actionable feedback.

## CLI Usage

The Gemini CLI can be used directly:

```bash
# Basic usage
echo "Your question here" | gemini

# Specify a model
echo "Technical question" | gemini -m gemini-2.5-pro
```

## Configuration

Gemini CLI stores its configuration in `~/.gemini/settings.json`. This file is automatically created after authentication. For MCP integration with this project, configure it as follows:

```json
{
  "mcpServers": {
    "local-tools": {
      "command": "npx",
      "args": ["-y", "mcp-server-local-tools"],
      "env": {
        "SERVER_URL": "http://localhost:8000"
      }
    },
    "comfyui": {
      "command": "npx",
      "args": ["-y", "mcp-server-comfyui"],
      "env": {
        "COMFYUI_URL": "http://localhost:8189",
        "COMFYUI_SERVER_URL": "${COMFYUI_SERVER_URL}"
      }
    },
    "ai-toolkit": {
      "command": "npx",
      "args": ["-y", "mcp-server-ai-toolkit"],
      "env": {
        "AI_TOOLKIT_URL": "http://localhost:8190",
        "AI_TOOLKIT_SERVER_URL": "${AI_TOOLKIT_SERVER_URL}"
      }
    }
  },
  "model": "gemini-2.5-pro",
  "temperature": 0.7,
  "maxTokens": 8192,
  "logLevel": "INFO",
  "cache": {
    "enabled": true,
    "ttl": 3600
  }
}
```

### Configuration Options

- **mcpServers**: MCP server configurations for various tools
  - **local-tools**: Local MCP server for development tools
  - **comfyui**: ComfyUI integration for image generation
  - **ai-toolkit**: AI Toolkit for LoRA training
- **model**: Default model to use (e.g., "gemini-2.5-pro", "gemini-1.5-flash")
- **temperature**: Controls randomness (0.0-1.0, default 0.7)
- **maxTokens**: Maximum response length (default 8192)
- **logLevel**: Logging verbosity (DEBUG, INFO, WARN, ERROR)
- **cache**: Response caching configuration
  - **enabled**: Enable/disable caching
  - **ttl**: Cache time-to-live in seconds

You can manually edit this file to change defaults, or use command-line flags to override:

```bash
# Override model
echo "Question" | gemini -m gemini-1.5-flash

# Override temperature
echo "Question" | gemini --temperature 0.5
```

## Rate Limits

Free tier limits:

- 60 requests per minute
- 1,000 requests per day
- 4 million tokens per day

For most single-maintainer projects, these limits are more than sufficient.

## Customization

You can customize the review behavior by editing `scripts/gemini-pr-review.py`:

- Adjust the prompt to focus on specific aspects
- Change the model (default tries gemini-2.5-pro, falls back to default)
- Modify comment formatting

## Troubleshooting

If Gemini reviews aren't working:

1. **Check Node.js version**: `node --version` (must be 18+)
2. **Verify Gemini CLI installation**: `which gemini`
3. **Test authentication**: `echo "test" | gemini`
4. **Check workflow logs** in GitHub Actions tab
5. **Ensure repository permissions** for PR comments
6. **Verify MCP server** is accessible if using clear history feature
7. **Check rate limits** - free tier has 60 requests/minute

### Common Issues

- **"Command not found"**: Gemini CLI not installed or not in PATH
- **Authentication errors**: Run `gemini` directly to re-authenticate
- **Rate limit exceeded**: Wait a few minutes and retry
- **No review posted**: Check if PR has proper permissions

## Privacy Note

- Only the code diff and PR metadata are sent to Gemini
- No code is stored by the AI service
- Reviews are supplementary to human code review

## References

- [Gemini CLI Documentation](https://github.com/google/gemini-cli)
- [Setup Guide](https://gist.github.com/AndrewAltimit/fc5ba068b73e7002cbe4e9721cebb0f5)
