# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**For Claude's expression philosophy and communication style, see** `docs/agents/claude-expression.md`

## Project Context

This is a **single-maintainer project** by @AndrewAltimit with a **container-first philosophy**:

- All Python operations run in Docker containers
- Self-hosted infrastructure for zero-cost operation
- Designed for maximum portability - works on any Linux system with Docker
- No contributors model - optimized for individual developer efficiency

## AI Agent Collaboration

You are working alongside five other AI agents in a comprehensive ecosystem:

1. **Gemini CLI** - Handles automated PR code reviews
2. **GitHub Copilot** - Provides code review suggestions in PRs
3. **Issue Monitor Agent** - Automatically creates PRs from well-described issues
4. **PR Review Monitor Agent** - Automatically implements fixes based on review feedback
5. **Codex** - AI-powered code generation and completion (OpenAI's code model)

Your role as Claude Code is the primary development assistant, handling:

- Architecture decisions and implementation
- Complex refactoring and debugging
- Documentation and test writing
- CI/CD pipeline development

### AI Agent Security Model

The AI agents implement a comprehensive multi-layer security model with command-based control, user authorization, commit-level validation, and deterministic security processes. Key features include:

- **Keyword Triggers**: `[Action][Agent]` format (e.g., `[Approved][Claude]`)
- **Allow List**: Only pre-approved users can trigger agents
- **Commit Validation**: Prevents code injection after approval
- **Implementation Requirements**: Only complete, working code is accepted

**For complete security documentation, see** `packages/github_agents/docs/security.md`

### Remote Infrastructure

**IMPORTANT**: The Gaea2 MCP server can run on a dedicated remote machine at `192.168.0.152:8007`:
- Gaea2 requires Windows with the Gaea2 software installed
- Health checks gracefully handle when the server is unavailable
- Do NOT change remote addresses to localhost in PR reviews

## Commands

### PR Monitoring

```bash
# Monitor a PR for admin/Gemini comments
./automation/monitoring/pr/monitor-pr.sh 48

# Monitor with custom timeout (30 minutes)
./automation/monitoring/pr/monitor-pr.sh 48 --timeout 1800

# Monitor from a specific commit (for post-push feedback)
./automation/monitoring/pr/monitor-pr.sh 48 --since-commit abc1234

# Get JSON output for automation
./automation/monitoring/pr/monitor-pr.sh 48 --json

# When asked to "monitor the PR for new comments", use:
python automation/monitoring/pr/pr_monitor_agent.py PR_NUMBER

# After pushing commits, monitor from that commit:
python automation/monitoring/pr/pr_monitor_agent.py PR_NUMBER --since-commit SHA
```

**PR Monitoring Usage**: When users ask you to monitor a PR or end requests with "and monitor for comments", automatically start the monitoring agent. It will:
1. Watch for new comments from admin (AndrewAltimit) or Gemini reviews
2. Return structured data when relevant comments are detected
3. Allow you to respond appropriately based on comment type

**Post-Push Monitoring**: After pushing commits, a hook will remind you to monitor for feedback and show the exact command with the commit SHA. This enables tight feedback loops during pair programming sessions.

See `docs/agents/pr-monitoring.md` for full documentation.

### Running Tests

```bash
# Run all tests with coverage (containerized)
docker-compose run --rm python-ci pytest tests/ -v --cov=. --cov-report=xml

# Run a specific test file
docker-compose run --rm python-ci pytest tests/test_mcp_tools.py -v

# Run tests with specific test name pattern
docker-compose run --rm python-ci pytest -k "test_format" -v

# Quick test run using helper script (excludes gaea2 tests)
./automation/ci-cd/run-ci.sh test

# Run only Gaea2 tests (requires remote server at 192.168.0.152:8007)
./automation/ci-cd/run-ci.sh test-gaea2

# Run all tests including Gaea2 (gaea2 tests may fail if server unavailable)
./automation/ci-cd/run-ci.sh test-all
```

**Note**: Gaea2 integration tests are separated from the main test suite because they require the remote Gaea2 MCP server to be available. In PR validation, these tests run in a separate job that checks server availability first.

### Code Quality

```bash
# Using containerized CI scripts (recommended)
./automation/ci-cd/run-ci.sh format      # Check formatting
./automation/ci-cd/run-ci.sh lint-basic   # Basic linting
./automation/ci-cd/run-ci.sh lint-full    # Full linting suite
./automation/ci-cd/run-ci.sh autoformat   # Auto-format code

# Direct Docker Compose commands
docker-compose run --rm python-ci black --check .
docker-compose run --rm python-ci flake8 .
docker-compose run --rm python-ci pylint tools/ automation/
docker-compose run --rm python-ci mypy . --ignore-missing-imports

# Note: All Python CI/CD tools run in containers to ensure consistency

# Run all checks at once
./automation/ci-cd/run-ci.sh full
```

### Development

```bash
# MODULAR MCP SERVERS (Container-First Approach)

# Start servers in Docker (recommended for consistency)
docker-compose up -d mcp-code-quality        # Port 8010 - Code formatting/linting
docker-compose up -d mcp-content-creation    # Port 8011 - Manim & LaTeX
docker-compose up -d mcp-gaea2               # Port 8007 - Terrain generation

# For local development (when actively developing server code)
python -m mcp_code_quality.server      # Port 8010
python -m mcp_content_creation.server  # Port 8011
python -m mcp_gaea2.server             # Port 8007
python -m mcp_opencode.server          # Port 8014 - AI code generation (HTTP mode)
python -m mcp_crush.server             # Port 8015 - Fast code generation (HTTP mode)

# Note: AI Toolkit and ComfyUI MCP servers run on remote machine (192.168.0.152)
# Ports 8012 and 8013 are used by the remote servers, not local instances

# Note: OpenCode and Crush use STDIO mode (local process) through .mcp.json,
# HTTP mode is only needed for cross-machine access or remote deployment

# Gemini can run on host or in container
python -m mcp_gemini.server            # Port 8006 - AI integration
./tools/mcp/mcp_gemini/scripts/start_server.sh --mode http
# Or use containerized version:
./tools/cli/containers/run_gemini_container.sh  # Containerized Gemini CLI with host auth
./automation/corporate-proxy/gemini/gemini      # Corporate proxy version (mock mode)

# Test all MCP servers at once
python automation/testing/test_all_servers.py

# Quick test of running servers
python automation/testing/test_all_servers.py --quick

# View logs for specific servers
docker-compose logs -f mcp-code-quality

# Test individual servers
python tools/mcp/mcp_code_quality/scripts/test_server.py
python tools/mcp/mcp_content_creation/scripts/test_server.py
python tools/mcp/mcp_gemini/scripts/test_server.py
python tools/mcp/mcp_gaea2/scripts/test_server.py
# AI Toolkit and ComfyUI tests require remote servers to be running
python tools/mcp/mcp_ai_toolkit/scripts/test_server.py  # Tests connection to 192.168.0.152:8012
python tools/mcp/mcp_comfyui/scripts/test_server.py     # Tests connection to 192.168.0.152:8013

# For local development without Docker
pip install -r config/python/requirements.txt
```

### AI Agents

```bash
# IMPORTANT: Agent Containerization Strategy
# Some agents run on host, others can be containerized
# See docs/agents/containerization-strategy.md for complete details

# Host-Only Agents (authentication constraints):
# 1. Claude CLI - requires subscription auth (machine-specific)
# See docs/agents/claude-auth.md for Claude auth details

# Containerized Gemini:
# Gemini CLI can now run in containers - see tools/cli/containers/run_gemini_container.sh

# Containerized Codex:
# Codex can run in containers with auth mounted from host
./tools/cli/containers/run_codex_container.sh  # Interactive Codex with mounted auth
docker-compose run --rm -v ~/.codex:/home/node/.codex:ro codex-agent codex

# Containerized Agents (OpenRouter-compatible):
# OpenCode, Crush - run in openrouter-agents container
docker-compose run --rm openrouter-agents python -m github_agents.cli issue-monitor

# Or use specific containerized agents:
docker-compose run --rm openrouter-agents crush run -q "Write a Python function"

# Direct host execution with helper scripts:
./tools/cli/agents/run_claude.sh     # Interactive Claude session with Node.js 22
./tools/cli/agents/run_opencode.sh   # OpenCode CLI for comprehensive code generation
./tools/cli/agents/run_crush.sh      # Crush CLI for fast code generation
./tools/cli/agents/run_gemini.sh     # Interactive Gemini CLI session with approval modes
./tools/cli/agents/run_codex.sh      # Codex CLI for AI-powered code generation (requires auth)

# Host agent execution (Claude, Gemini only):
python3 -m github_agents.cli issue-monitor
python3 -m github_agents.cli pr-monitor
# Or use the installed commands directly:
issue-monitor
pr-monitor

# GitHub Actions automatically run agents on schedule:
# - Issue Monitor: Every hour (runs on host)
# - PR Review Monitor: Every hour (runs on host)

# Installation:
# Step 1: Install the GitHub AI agents package (required for all agents):
pip3 install -e ./packages/github_agents

# Step 2: If running Claude or Gemini on host, install host-specific dependencies:
pip3 install --user -r docker/requirements/requirements-agents.txt

# Step 3: For Codex (optional):
npm install -g @openai/codex  # Install Codex CLI
codex auth                     # Authenticate (creates ~/.codex/auth.json)

# Note: Step 2 is only needed if you plan to use Claude or Gemini agents.
# Containerized agents (OpenCode, Crush, Codex) can run without host dependencies.
```

### Docker Operations

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f mcp-code-quality
docker-compose logs -f mcp-content-creation
docker-compose logs -f mcp-gaea2
docker-compose logs -f python-ci

# Stop services
docker-compose down

# Rebuild after changes
docker-compose build mcp-code-quality
docker-compose build mcp-content-creation
docker-compose build mcp-gaea2
docker-compose build python-ci
```

### Helper Scripts

```bash
# CI/CD operations script
./automation/ci-cd/run-ci.sh [stage]
# Stages: format, lint-basic, lint-full, security, test, yaml-lint, json-lint, autoformat

# Lint stage helper (used in workflows)
./automation/ci-cd/run-lint-stage.sh [stage]
# Stages: format, basic, full

# Fix runner permission issues
./automation/setup/runner/fix-runner-permissions.sh

# Check markdown links locally
python automation/analysis/check-markdown-links.py                # Check all links in all markdown files
python automation/analysis/check-markdown-links.py --internal-only # Check only internal links
python automation/analysis/check-markdown-links.py --file docs/   # Check only files in docs directory
```

## Architecture

### MCP Server Architecture (Modular Design)

The project uses a modular collection of Model Context Protocol (MCP) servers, each specialized for specific functionality:

**Transport Modes**:
- **STDIO**: For local processes running on the same machine as the client
- **HTTP**: For remote machines or cross-machine communication due to hardware/software constraints

1. **Code Quality MCP Server** (`tools/mcp/mcp_code_quality/`): STDIO (local) or HTTP port 8010
   - **Code Formatting & Linting**:
     - `format_check` - Check code formatting (Python, JS, TS, Go, Rust)
     - `lint` - Run static analysis with multiple linters
     - `autoformat` - Automatically format code files
   - See `tools/mcp/mcp_code_quality/docs/README.md` for documentation

2. **Content Creation MCP Server** (`tools/mcp/mcp_content_creation/`): STDIO (local) or HTTP port 8011
   - **Manim & LaTeX Tools**:
     - `create_manim_animation` - Create mathematical/technical animations
     - `compile_latex` - Generate PDF/DVI/PS documents from LaTeX
     - `render_tikz` - Render TikZ diagrams as standalone images
   - See `tools/mcp/mcp_content_creation/docs/README.md` for documentation

3. **Gemini MCP Server** (`tools/mcp/mcp_gemini/`): STDIO (local) or HTTP port 8006
   - Can run on host or in container (see `automation/corporate-proxy/gemini/`)
   - **AI Integration**:
     - `consult_gemini` - Get AI assistance for technical questions
     - `clear_gemini_history` - Clear conversation history for fresh responses
     - `gemini_status` - Get integration status and statistics
     - `toggle_gemini_auto_consult` - Control auto-consultation
   - See `tools/mcp/mcp_gemini/docs/README.md` for documentation

4. **Gaea2 MCP Server** (`tools/mcp/mcp_gaea2/`): HTTP port 8007 (remote Windows machine)
   - **Terrain Generation**:
     - `create_gaea2_project` - Create custom terrain projects
     - `create_gaea2_from_template` - Use professional templates
     - `validate_and_fix_workflow` - Comprehensive validation and repair
     - `analyze_workflow_patterns` - Pattern-based workflow analysis
     - `optimize_gaea2_properties` - Performance/quality optimization
     - `suggest_gaea2_nodes` - Intelligent node suggestions
     - `repair_gaea2_project` - Fix damaged project files
     - `run_gaea2_project` - CLI automation (Windows only)
   - Can run locally or on remote server (192.168.0.152:8007)
   - See `tools/mcp/mcp_gaea2/docs/README.md` for complete documentation

5. **AI Toolkit MCP Server** (`tools/mcp/mcp_ai_toolkit/`): HTTP port 8012 (remote GPU machine)
   - **LoRA Training Management**:
     - Training configurations, dataset uploads, job monitoring
     - Model export and download capabilities
   - Connects to remote AI Toolkit instance at `192.168.0.152:8012`
   - See `tools/mcp/mcp_ai_toolkit/docs/README.md` for documentation

6. **ComfyUI MCP Server** (`tools/mcp/mcp_comfyui/`): HTTP port 8013 (remote GPU machine)
   - **AI Image Generation**:
     - Image generation with workflows
     - LoRA model management and transfer
     - Custom workflow execution
   - Connects to remote ComfyUI instance at `192.168.0.152:8013`
   - See `tools/mcp/mcp_comfyui/docs/README.md` for documentation

7. **OpenCode MCP Server** (`tools/mcp/mcp_opencode/`): STDIO (local) or HTTP port 8014
   - **AI-Powered Code Generation**:
     - `consult_opencode` - Generate, refactor, review, or explain code
     - `clear_opencode_history` - Clear conversation history
     - `opencode_status` - Get integration status and statistics
     - `toggle_opencode_auto_consult` - Control auto-consultation
   - Uses OpenRouter API with Qwen 2.5 Coder model
   - Runs locally via stdio for better integration
   - See `tools/mcp/mcp_opencode/docs/README.md` for documentation

8. **Crush MCP Server** (`tools/mcp/mcp_crush/`): STDIO (local) or HTTP port 8015
   - **Fast Code Generation**:
     - `consult_crush` - Quick code generation and conversion
     - `clear_crush_history` - Clear conversation history
     - `crush_status` - Get integration status and statistics
     - `toggle_crush_auto_consult` - Control auto-consultation
   - Uses OpenRouter API with optimized models for speed
   - Runs locally via stdio for better integration
   - See `tools/mcp/mcp_crush/docs/README.md` for documentation

9. **Meme Generator MCP Server** (`tools/mcp/mcp_meme_generator/`): STDIO (local)
   - **Meme Creation**:
     - `generate_meme` - Generate memes from templates with text overlays
     - `list_meme_templates` - List all available templates
     - `get_meme_template_info` - Get detailed template information
   - 7+ built-in templates with cultural context documentation
   - Auto-upload to 0x0.st for sharing
   - See `tools/mcp/mcp_meme_generator/docs/README.md` for documentation

10. **ElevenLabs Speech MCP Server** (`tools/mcp/mcp_elevenlabs_speech/`): STDIO (local) or HTTP port 8018
   - **Advanced Text-to-Speech**:
     - `synthesize_speech_v3` - Main synthesis with audio tag support
     - `synthesize_emotional` - Add emotional context
     - `synthesize_dialogue` - Multi-character dialogue
     - `generate_sound_effect` - Create sound effects (up to 22 seconds)
   - Supports emotions, pauses, sounds, effects with audio tags
   - Multi-model support (v2 Pro plan, v3 future)
   - See `tools/mcp/mcp_elevenlabs_speech/docs/README.md` for documentation

11. **Video Editor MCP Server** (`tools/mcp/mcp_video_editor/`): STDIO (local) or HTTP port 8019
   - **AI-Powered Video Editing**:
     - `process_video` - Transcription, diarization, scene detection
     - `compose_videos` - Combine videos with transitions
     - `extract_clips` - Extract clips by keywords/speakers
     - `generate_captions` - Multi-language caption generation
   - GPU acceleration with CUDA support
   - Async job processing for long operations
   - See `tools/mcp/mcp_video_editor/docs/README.md` for documentation

12. **Blender MCP Server** (`tools/mcp/mcp_blender/`): STDIO (local) or HTTP port 8016
   - **3D Content Creation**:
     - `create_blender_project` - Create projects from templates
     - `render_image` - Render single frames with Cycles/Eevee
     - `render_animation` - Render animation sequences
     - `setup_physics` - Configure physics simulations
     - `create_animation` - Keyframe animation creation
     - `add_modifier` - Apply modifiers to objects
     - `setup_camera` - Camera configuration and tracking
     - `setup_compositor` - Post-processing nodes
   - Support for geometry nodes, particle systems, UV mapping
   - Import/export various 3D formats (FBX, OBJ, GLTF, STL)
   - See `tools/mcp/mcp_blender/docs/README.md` for documentation

13. **Virtual Character MCP Server** (`tools/mcp/mcp_virtual_character/`): STDIO (local) or HTTP port 8020
   - **AI Agent Embodiment Middleware**:
     - `connect_backend` - Connect to virtual world platforms
     - `send_animation` - Send canonical animation data
     - `send_audio` - Audio with lip-sync metadata
     - `get_state` - Retrieve environment state
     - `capture_video` - Get agent's visual perspective
     - `list_backends` - Available backend plugins
     - `switch_backend` - Hot-swap between platforms
   - Plugin-based architecture for extensibility
   - Supports VRChat (OSC), Blender, Unity (WebSocket)
   - Remote Windows support for VRChat backend
   - See `tools/mcp/mcp_virtual_character/README.md` for documentation

14. **Shared Core Components** (`tools/mcp/mcp_core/`):
   - `BaseMCPServer` - Base class for all MCP servers
   - `HTTPProxy` - HTTP proxy for remote MCP servers
   - Common utilities and helpers

15. **Containerized CI/CD**:
   - **Python CI Container** (`docker/python-ci.Dockerfile`): All Python tools
   - **Helper Scripts**: Centralized CI operations
   - **Individual MCP Containers**: Each server can run in its own optimized container

**For comprehensive MCP architecture documentation, see** `docs/mcp/README.md`

### GitHub Actions Integration

The repository includes comprehensive CI/CD workflows:

- **PR Validation**: Automatic Gemini AI code review with history clearing
- **Testing Pipeline**: Containerized pytest with coverage reporting
- **Code Quality**: Multi-stage linting in Docker containers
- **Link Checking**: Automated markdown link validation with weekly scheduled runs
- **Self-hosted Runners**: All workflows run on self-hosted infrastructure
- **Runner Maintenance**: Automated cleanup and health checks

### Container Architecture Philosophy

1. **Everything Containerized** (with documented exceptions):
   - Python CI/CD tools run in `python-ci` container (Python 3.11)
   - MCP servers run in their own containers
   - **Exceptions due to authentication requirements**:
     - AI Agents using Claude CLI (requires host subscription auth - see `docs/agents/claude-auth.md`)
   - **Now containerized**: Gemini CLI (see `automation/corporate-proxy/gemini/` and `tools/cli/containers/run_gemini_container.sh`)
   - All containers run with user permissions (non-root)

2. **Zero Local Dependencies**:
   - No need to install Python, Node.js, or any tools locally
   - All operations available through Docker Compose
   - Portable across any Linux system

3. **Self-Hosted Infrastructure**:
   - All GitHub Actions run on self-hosted runners
   - No cloud costs or external dependencies
   - Full control over build environment

### Key Integration Points

1. **AI Services**:
   - Gemini API for code review (can run on host or in container)
   - Support for Claude and OpenAI integrations
   - Remote ComfyUI workflows for image generation

2. **Testing Strategy**:
   - All tests run in containers with Python 3.11
   - Mock external dependencies (subprocess, HTTP calls)
   - Async test support with pytest-asyncio
   - Coverage reporting with pytest-cov
   - No pytest cache to avoid permission issues

3. **Client Pattern** (`tools/mcp/mcp_core/client.py`):
   - MCPClient class for interacting with MCP servers
   - Supports all MCP server endpoints (ports 8006-8015)
   - Environment-based configuration

### Security Considerations

- API key management via environment variables
- Rate limiting configured in .mcp.json
- Docker network isolation for services
- No hardcoded credentials in codebase
- Containers run as non-root user

## Development Reminders

- **MCP Servers**: The project uses modular MCP servers. See `docs/mcp/README.md` for architecture details.
- IMPORTANT: When you have completed a task, you MUST run the lint and quality checks:
  ```bash
  # Run full CI checks
  ./automation/ci-cd/run-ci.sh full

  # Or individual checks
  ./automation/ci-cd/run-ci.sh format
  ./automation/ci-cd/run-ci.sh lint-basic
  ./automation/ci-cd/run-ci.sh lint-full
  ```
- NEVER commit changes unless the user explicitly asks you to
- Always follow the container-first philosophy - use Docker for all Python operations
- Gemini CLI is now containerized (see `automation/corporate-proxy/gemini/` for corporate proxy version)
- Use pytest fixtures and mocks for testing external dependencies
- **NEVER use Unicode emoji characters** in code, commits, or comments - they may display as corrupted characters. Use reaction images instead for GitHub interactions

## GitHub Etiquette

**IMPORTANT**: When working with GitHub issues, PRs, and comments:

- **NEVER use @ mentions** unless referring to actual repository maintainers
- Do NOT use @Gemini, @Claude, @OpenAI, etc. - these may ping unrelated GitHub users
- Instead, refer to AI agents without the @ symbol: "Gemini", "Claude", "OpenAI"
- Only @ mention users who are:
  - The repository owner (@AndrewAltimit)
  - Active contributors listed in the repository
  - Users who have explicitly asked to be mentioned
- When referencing AI reviews, use phrases like:
  - "As noted in Gemini's review..."
  - "Addressing Claude's feedback..."
  - "Per the AI agent's suggestion..."

This prevents accidentally notifying random GitHub users who happen to share names with our AI tools.

### PR Comments and Reactions

**Use Custom Reaction Images**: When commenting on PRs and issues, use our custom reaction images to express authentic responses to the work.

- **Available reactions** are defined in: https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/config.yaml
- **Format**: `![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/[filename])`

**Important Note**: These reaction images are specifically for GitHub interactions (PR comments, issue discussions). Claude Code's CLI interface cannot render images - reactions will appear as markdown syntax in the terminal. Reserve visual reactions for online interactions where they can be properly displayed and appreciated.

#### Expression Philosophy

**Prioritize authenticity over optimism**. Choose reactions that genuinely reflect the experience:
- Debugging can be exhausting - it's okay to show that
- Not every fix is a triumph - sometimes it's just relief
- Confusion and frustration are valid parts of development
- Partial success deserves acknowledgment too

#### Situational Reaction Guide

**When starting work:**
- `miku_typing.webp` - Thoughtful, methodical approach
- `konata_typing.webp` - Determined focus on complex problems
- `yuki_typing.webp` - Urgent or intense debugging sessions
- `hifumi_studious.png` - Deep analysis or research

**When encountering issues:**
- `confused.gif` - Genuinely puzzling behavior
- `kagami_annoyed.png` - When the same error persists
- `miku_confused.png` - Unexpected test failures
- `thinking_foxgirl.png` - Contemplating tricky solutions

**After completing work:**
- `teamwork.webp` - True collaborative success (not default!)
- `felix.webp` - Genuine excitement about elegant solutions
- `miku_shrug.png` - "It works, mostly" situations
- `miku_laughing.png` - When you find a silly bug
- `aqua_happy.png` - Unexpectedly smooth implementations

**Responding to feedback:**
- `youre_absolutely_right.webp` - Genuine realization moments
- `thinking_girl.png` - Considering complex suggestions
- `noire_not_amused.png` - When asked to add "just one more thing"
- `kanna_facepalm.png` - Realizing obvious mistakes

**Best practices**:
- Match the reaction to the actual experience, not the ideal outcome
- It's okay to take time finding the right reaction
- One thoughtful reaction > multiple generic ones
- Build a consistent "personality" through reaction choices over time

Example usage:
```markdown
Thanks for the review! Working on the fixes now.

![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/miku_typing.webp)
```

**CRITICAL: Proper Method for GitHub Comments with Reaction Images**

When posting PR/issue comments with reaction images, you MUST follow this exact workflow to prevent the `!` character from being escaped:

**The ONLY Correct Method:**
1. **Use the Write tool** to create a temporary markdown file (e.g., `/tmp/comment.md`)
2. Use `gh pr comment --body-file /tmp/filename.md` to post the comment

**DO NOT USE (these will escape the `!` in `![Reaction]`):**
- ❌ Direct `--body` flag with gh command
- ❌ Heredocs (`cat <<EOF`)
- ❌ echo or printf commands
- ❌ Bash string concatenation

**Correct Example:**
```python
# Step 1: Use Write tool
Write("/tmp/pr_comment.md", """
Thanks for the review! Working on the fixes now.

![Reaction](https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction/miku_typing.webp)
""")

# Step 2: Post with gh command
Bash("gh pr comment 47 --body-file /tmp/pr_comment.md")
```

**Why this matters:** Shell escaping will turn `![Reaction]` into `\![Reaction]`, breaking the image display. The Write tool preserves the markdown exactly as intended.

## Additional Documentation

For detailed information on specific topics, refer to these documentation files:

### Infrastructure & Setup
- `docs/infrastructure/self-hosted-runner.md` - Self-hosted GitHub Actions runner configuration
- `docs/infrastructure/github-environments.md` - GitHub environments and secrets setup
- `docs/infrastructure/containerization.md` - Container-based CI/CD philosophy and implementation
- `docs/developer/claude-code-hooks.md` - Claude Code hook system for enforcing best practices

### AI Agents & Security
- `packages/github_agents/docs/security.md` - Comprehensive AI agent security documentation
- `docs/agents/README.md` - AI agent system overview
- `docs/agents/security.md` - Security-focused agent documentation
- `docs/agents/human-training.md` - **AI safety training guide for human-AI collaboration** (essential reading)
- `docs/agents/claude-auth.md` - Why AI agents run on host (Claude auth limitation)
- `docs/agents/claude-expression.md` - Claude's expression philosophy and communication style
- `docs/agents/gemini-expression.md` - Gemini's expression philosophy and review patterns

### MCP Servers
- `docs/mcp/README.md` - MCP architecture and design patterns
- `docs/mcp/servers.md` - Individual server documentation
- `docs/mcp/tools.md` - Available MCP tools reference

### Integrations
- `docs/integrations/ai-services/opencode-crush.md` - **Comprehensive OpenCode & Crush documentation** (MCP calls, CLI usage, git workflows)
- `docs/integrations/creative-tools/ai-toolkit-comfyui.md` - LoRA training and image generation
- `docs/integrations/creative-tools/lora-transfer.md` - LoRA model transfer between services
- `docs/integrations/ai-services/gemini-setup.md` - Gemini CLI setup and configuration
- `docs/agents/codex-setup.md` - Codex agent setup and configuration

### Gaea2 Terrain Generation
- `tools/mcp/mcp_gaea2/docs/INDEX.md` - Complete Gaea2 documentation index
- `tools/mcp/mcp_gaea2/docs/README.md` - Main Gaea2 MCP documentation
- `tools/mcp/mcp_gaea2/docs/GAEA2_QUICK_REFERENCE.md` - Quick reference guide

## AI Toolkit & ComfyUI Integration

The AI Toolkit and ComfyUI MCP servers provide interfaces to remote instances for LoRA training and image generation. Key points:

- **Dataset Paths**: Use absolute paths starting with `/ai-toolkit/datasets/`
- **Chunked Upload**: Required for files >100MB
- **FLUX Workflows**: Different from SD workflows (cfg=1.0, special nodes)

**For comprehensive integration guide, see** `docs/integrations/creative-tools/ai-toolkit-comfyui.md`

## Gaea2 MCP Integration

The Gaea2 MCP server provides comprehensive terrain generation capabilities:

- **Intelligent Validation**: Automatic error correction and optimization
- **Professional Templates**: Ready-to-use terrain workflows
- **Windows Requirement**: Must run on Windows with Gaea2 installed

**For complete Gaea2 documentation:**
- `tools/mcp/mcp_gaea2/docs/INDEX.md` - Documentation index
- `tools/mcp/mcp_gaea2/docs/README.md` - Main documentation
- `tools/mcp/mcp_gaea2/docs/GAEA2_API_REFERENCE.md` - API reference
- `tools/mcp/mcp_gaea2/docs/GAEA2_EXAMPLES.md` - Usage examples
