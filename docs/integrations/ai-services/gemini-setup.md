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

3. **Set up API Key** (Required for PR reviews)

   **Get your FREE API key from Google AI Studio:**

   1. Visit https://aistudio.google.com/app/apikey
   2. Create a new API key (free tier available)
   3. Set it as a repository secret:
      - Go to: Settings → Secrets and variables → Actions
      - Add new repository secret: `GOOGLE_API_KEY`

   For local development, add it to `.env`:
   ```bash
   cp .env.example .env
   # Edit .env and add: GOOGLE_API_KEY=your_api_key_here
   ```

   **✅ FREE TIER AVAILABLE**

   Google AI Studio API keys include a **generous free tier** with:
   - Access to latest models (including Gemini 3.0 Pro Preview)
   - 60 requests per minute
   - 1,500 requests per day on free tier
   - No credit card required for free tier

   **Why API Key instead of OAuth?**

   We switched from OAuth to API keys because:
   - ✅ Works reliably in CI/CD (no browser-based auth)
   - ✅ No timeouts from PTY/terminal requirements
   - ✅ Explicit model selection (no 404 errors)
   - ✅ Still free tier with same generous limits
   - ✅ Better retry logic for rate limiting

That's it! The next time you open a pull request, Gemini will automatically review your code using the latest models.

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

## Interactive Gemini CLI

### Using the Run Script

For interactive development sessions, use the provided runner script:

```bash
./tools/cli/agents/run_gemini.sh
```

This script provides:
- **Node.js 22.16.0 setup** via NVM
- **Three approval modes**:
  - Normal mode - prompts for each tool approval (default)
  - Auto-edit mode - auto-approves edit tools only
  - YOLO mode - auto-approves ALL tools (use with caution)
- **Optional checkpointing** for file edits (restore with `/restore`)

## MCP Server Integration

This project includes a dedicated Gemini MCP server that provides AI consultation capabilities:

### Running the Gemini MCP Server

```bash
# Run on the host system (cannot run in container)
python -m mcp_gemini.server

# Or with HTTP mode
./tools/mcp/mcp_gemini/scripts/start_server.sh --mode http
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

- `GOOGLE_API_KEY` - **REQUIRED** - API key from Google AI Studio (free tier available)
- `GEMINI_ENABLED` - Enable/disable Gemini (default: "true")
- `GEMINI_AUTO_CONSULT` - Enable auto-consultation (default: "true")
- `GEMINI_CLI_COMMAND` - Gemini CLI command (default: "gemini")
- `GEMINI_TIMEOUT` - Request timeout in seconds (default: 60)
- `GEMINI_RATE_LIMIT` - Rate limit delay in seconds (default: 2)
- `GEMINI_MAX_CONTEXT` - Maximum context length (default: 4000)

**Model Selection:**

PR reviews use explicit model specification with automatic fallback:
- Primary: `gemini-3.0-pro-preview` (latest, most capable model)
- Fallback: `gemini-2.5-flash` (faster, still highly capable)

Both models are available on the free tier!

## CLI Usage

The Gemini CLI can be used directly:

```bash
# Basic usage - the CLI automatically selects the best model
echo "Your question here" | gemini

# With prompt flag for non-interactive mode
gemini -p "Your question here"
```

## Rate Limits

**Free tier limits (Google AI Studio API Key):**

- 60 requests per minute
- 1,500 requests per day (free tier)
- No credit card required

For most single-maintainer projects, these limits are more than sufficient.

**Automatic Rate Limit Handling:**

The PR review script includes smart retry logic with exponential backoff:
- Automatically retries on rate limit errors (429)
- Waits 5s, 10s, 20s, 40s, 80s between retries
- Falls back to Flash model if Pro model is rate limited
- Up to 5 retry attempts to ensure reviews complete

## Customization

You can customize the review behavior by editing `scripts/gemini-pr-review.py`:

- Adjust the prompt to focus on specific aspects
- Modify comment formatting
- Configure rate limiting and timeout values

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

- [Gemini MCP Server Docs](../../../tools/mcp/mcp_gemini/docs/README.md)
- [Setup Guide](https://gist.github.com/AndrewAltimit/fc5ba068b73e7002cbe4e9721cebb0f5)
