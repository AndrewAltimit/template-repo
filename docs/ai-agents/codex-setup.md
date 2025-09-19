# Codex Agent Setup and Configuration

This guide covers the setup and usage of OpenAI Codex as an AI agent in the repository.

## Overview

Codex is OpenAI's AI system that translates natural language to code. It powers GitHub Copilot and can be used as a standalone CLI tool for code generation, completion, and refactoring tasks.

## Installation

### Host Installation

1. **Install Node.js** (if not already installed):
   ```bash
   # Check if Node.js is installed
   node --version

   # If not installed, use your package manager or visit nodejs.org
   ```

2. **Install Codex CLI globally**:
   ```bash
   npm install -g @openai/codex
   ```

3. **Authenticate with Codex** (Requires ChatGPT Plus Subscription):
   ```bash
   codex auth
   ```
   - **IMPORTANT**: You need a ChatGPT Plus subscription to bypass API key requirements
   - This command will open a browser for login/authentication
   - After successful authentication, it creates `~/.codex/auth.json`
   - This authentication file is required for all Codex operations

### Container Usage (Recommended)

For consistent environments and portability, use the containerized version:

```bash
# Run Codex in a container (auth from host is mounted automatically)
./tools/cli/containers/run_codex_container.sh
```

The container:
- Has Codex pre-installed
- Mounts your host's `~/.codex` directory for authentication
- Runs in an isolated environment
- Uses Node.js 20 LTS

## Usage

### Interactive Mode

**On Host:**
```bash
./tools/cli/agents/run_codex.sh
```

**In Container:**
```bash
./tools/cli/containers/run_codex_container.sh
```

This starts an interactive session where you can:
- Type prompts for code generation
- Get code suggestions and completions
- Refactor existing code

### Single Query Mode

**Generate code with a specific prompt:**
```bash
# On host
./tools/cli/agents/run_codex.sh -q "Write a Python function to calculate factorial"

# In container
./tools/cli/containers/run_codex_container.sh -q "Write a Python function to calculate factorial"
```

### With Context

**Provide existing code as context:**
```bash
# On host
./tools/cli/agents/run_codex.sh -q "Refactor this function for better performance" -c existing_code.py

# In container
./tools/cli/containers/run_codex_container.sh -q "Add error handling" -c src/main.py
```

## Docker Integration

### Building the Container

The Codex agent container is built automatically when you first run it, or manually:

```bash
docker-compose build codex-agent
```

### Direct Docker Usage

```bash
# Start the container
docker-compose up -d codex-agent

# Run commands inside
docker-compose exec codex-agent codex

# With mounted auth
docker-compose run --rm \
  -v ~/.codex:/home/node/.codex:ro \
  codex-agent codex
```

## Authentication

### Initial Setup

1. **On Host**: Run `codex auth` once to authenticate (requires ChatGPT Plus subscription)
   - Opens browser for login with your OpenAI account
   - Bypasses the need for manual API key configuration
2. **Auth File**: Created at `~/.codex/auth.json` after successful login
3. **Container**: Automatically mounts the auth directory from host

### Troubleshooting Auth Issues

If authentication fails:

1. **Check auth file exists**:
   ```bash
   ls -la ~/.codex/auth.json
   ```

2. **Re-authenticate if needed**:
   ```bash
   codex auth
   ```

3. **Verify container mount**:
   ```bash
   docker-compose run --rm codex-agent ls -la /home/node/.codex/
   ```

## Features and Capabilities

### Code Generation
- Generate functions, classes, and modules from descriptions
- Support for multiple programming languages
- Context-aware suggestions

### Code Completion
- Complete partial code snippets
- Fill in function implementations
- Generate boilerplate code

### Code Refactoring
- Improve code quality and performance
- Convert between programming paradigms
- Modernize legacy code

### Documentation
- Generate docstrings and comments
- Create README files
- Write API documentation

## Best Practices

### Effective Prompting

1. **Be Specific**: Clear, detailed prompts yield better results
2. **Provide Context**: Include relevant code or requirements
3. **Specify Language**: Mention the programming language explicitly
4. **Include Constraints**: Specify performance, style, or framework requirements

### Security Considerations

1. **Review Generated Code**: Always review AI-generated code before using
2. **No Secrets**: Never include API keys or secrets in prompts
3. **Validate Logic**: Test generated code thoroughly
4. **License Compliance**: Be aware of licensing implications

### Integration with Other Tools

Codex works well with:
- **Claude**: For architectural decisions and complex logic
- **OpenCode**: For comprehensive code generation tasks
- **Crush**: For quick code snippets and conversions
- **GitHub Copilot**: For in-editor suggestions

## Examples

### Example 1: Generate a REST API Endpoint

```bash
./tools/cli/agents/run_codex.sh -q "Create a FastAPI endpoint for user registration with email validation and password hashing"
```

### Example 2: Refactor with Context

```bash
./tools/cli/agents/run_codex.sh -q "Refactor to use async/await pattern" -c old_callback_code.js
```

### Example 3: Generate Tests

```bash
./tools/cli/agents/run_codex.sh -q "Write comprehensive unit tests for this module" -c src/calculator.py
```

### Example 4: Convert Code Between Languages

```bash
./tools/cli/agents/run_codex.sh -q "Convert this Python code to TypeScript" -c python_script.py
```

## Comparison with Other AI Agents

| Feature | Codex | Claude | OpenCode | Crush |
|---------|-------|--------|----------|-------|
| **Primary Use** | Code generation | Architecture & complex tasks | Comprehensive generation | Quick snippets |
| **Speed** | Fast | Moderate | Slower (thorough) | Very fast |
| **Context Window** | Moderate | Large | Large | Small |
| **Language Support** | Excellent | Good | Excellent | Good |
| **IDE Integration** | Yes (Copilot) | No | No | No |
| **Container Support** | Yes | Limited | Yes | Yes |

## Troubleshooting

### Common Issues

1. **"codex: command not found"**
   - Solution: Install with `npm install -g @openai/codex`
   - Alternative: Use the container version

2. **"Authentication required"**
   - Solution: Run `codex auth` on host (requires ChatGPT Plus subscription)
   - Check: `~/.codex/auth.json` exists
   - Note: This uses your OpenAI account with ChatGPT Plus subscription

3. **Container build fails**
   - Solution: Rebuild with `docker-compose build --no-cache codex-agent`
   - Check: Docker daemon is running

4. **Permission denied in container**
   - Solution: Check user ID matches: `id -u` on host
   - Fix: Update USER_ID in .env file

## Environment Variables

- `NODE_ENV`: Set to `production` in container
- `GITHUB_REPOSITORY`: Repository context for agent operations
- `USER_ID` / `GROUP_ID`: User permissions for container

## Related Documentation

- [AI Agents Overview](README.md)
- [OpenCode & Crush Integration](../integrations/ai-services/opencode-crush.md)
- [Gemini Setup](../integrations/ai-services/gemini-setup.md)
- [Claude Expression Philosophy](claude-expression.md)
- [Container Strategy](containerization-strategy.md)
