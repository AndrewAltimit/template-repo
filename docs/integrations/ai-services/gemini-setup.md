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

   **⚠️ IMPORTANT: Authentication Method & Costs**

   The Gemini CLI uses **Google web login (OAuth)** which provides a **FREE TIER** with generous limits:
   - 60 requests per minute
   - 1,000 requests per day
   - 4 million tokens per day

   **CAUTION: Do NOT use API keys!** If you configure Gemini with an API key instead of web login, you will be **charged** for usage. The web login method is recommended as it provides the free tier suitable for most single-maintainer projects.

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

## MCP Server Integration

This project includes a dedicated Gemini MCP server that provides AI consultation capabilities:

### Running the Gemini MCP Server

```bash
# Run on the host system (cannot run in container)
python -m tools.mcp.gemini.server

# Or with HTTP mode
./tools/mcp/gemini/scripts/start_server.sh --mode http
```

**Important: Why Gemini MCP Server Must Run on Host**

The Gemini MCP server is an exception to the project's container-first approach and must run on the host system because:

1. **Docker Access Required**: The server needs to execute Docker commands to interact with other containerized services
2. **Docker-in-Docker Complexity**: Running Docker inside a container would require privileged mode and complex socket mounting
3. **Security Considerations**: Avoiding nested Docker layers reduces security risks and complexity
4. **Integration Requirements**: The server needs direct access to the host's Docker daemon for service orchestration

This is a deliberate architectural decision to maintain simplicity and security while still providing seamless AI integration.

The server runs on port 8006 and provides:
- `consult_gemini` - Get AI assistance for technical questions
- `clear_gemini_history` - Clear conversation history
- `gemini_status` - Check integration status
- `toggle_gemini_auto_consult` - Control auto-consultation

### Configuration via .mcp.json

Configure the Gemini MCP server in your `.mcp.json` file:

```json
{
  "servers": {
    "gemini": {
      "url": "http://localhost:8006",
      "timeout": 60,
      "rateLimit": {
        "requests": 10,
        "period": 60
      }
    }
  }
}
```

### Environment Variables

Configure Gemini behavior with these environment variables:

- `GEMINI_ENABLED` - Enable/disable Gemini (default: "true")
- `GEMINI_AUTO_CONSULT` - Enable auto-consultation (default: "true")
- `GEMINI_CLI_COMMAND` - Gemini CLI command (default: "gemini")
- `GEMINI_TIMEOUT` - Request timeout in seconds (default: 60)
- `GEMINI_RATE_LIMIT` - Rate limit delay in seconds (default: 2)
- `GEMINI_MAX_CONTEXT` - Maximum context length (default: 4000)
- `GEMINI_MODEL` - Default model (default: "gemini-2.5-flash")

## CLI Usage

The Gemini CLI can be used directly:

```bash
# Basic usage
echo "Your question here" | gemini

# Specify a model
echo "Technical question" | gemini -m gemini-2.5-pro
```

## Rate Limits

**Free tier limits (when using Google web login/OAuth):**

- 60 requests per minute
- 1,000 requests per day
- 4 million tokens per day

For most single-maintainer projects, these limits are more than sufficient.

**⚠️ Remember:** These free tier limits only apply when using the **Google web login method**. Using API keys will result in charges based on usage!

## Customization

You can customize the review behavior by editing `scripts/gemini-pr-review.py`:

- Adjust the prompt to focus on specific aspects
- Change the model (default tries gemini-2.5-pro, falls back to flash)
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
- **MCP server errors**: Ensure Gemini MCP server is running on host (not in container)

## Privacy Note

- Only the code diff and PR metadata are sent to Gemini
- No code is stored by the AI service
- Reviews are supplementary to human code review

## References

- [Gemini MCP Server Docs](../../../tools/mcp/gemini/docs/README.md)
- [Setup Guide](https://gist.github.com/AndrewAltimit/fc5ba068b73e7002cbe4e9721cebb0f5)
