# Setting Up Gemini AI Code Review

This repository includes automatic AI-powered code review for pull requests using Google's Gemini AI CLI.

## Features

- Automatic code review on every pull request
- Analyzes code changes and provides constructive feedback
- Posts review comments directly to the PR
- Non-blocking - won't fail your PR if the CLI is unavailable
- Uses official Gemini CLI with automatic authentication

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
2. **Conversation history is cleared** to ensure fresh review
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

## Rate Limits

Free tier limits:
- 60 requests per minute
- 1,000 requests per day

## Customization

You can customize the review behavior by editing `scripts/gemini-pr-review.py`:

- Adjust the prompt to focus on specific aspects
- Change the model (default tries gemini-2.5-pro, falls back to default)
- Modify comment formatting

## Troubleshooting

If Gemini reviews aren't working:

1. Check that Node.js 18+ is installed: `node --version`
2. Verify Gemini CLI is installed: `which gemini`
3. Test authentication: `echo "test" | gemini`
4. Check the workflow logs for errors
5. Ensure the repository has proper permissions for PR comments

## Privacy Note

- Only the code diff and PR metadata are sent to Gemini
- No code is stored by the AI service
- Reviews are supplementary to human code review

## References

- [Gemini CLI Documentation](https://github.com/google/gemini-cli)
- [Setup Guide](https://gist.github.com/AndrewAltimit/fc5ba068b73e7002cbe4e9721cebb0f5)