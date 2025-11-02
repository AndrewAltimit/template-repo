# Gemini Project Context: MCP-Enabled Project Template

## Project Overview

This is a comprehensive, container-first development ecosystem designed for building and deploying complex applications with a strong focus on AI and automation. The project provides a template with a suite of pre-configured services, AI agents, and a complete CI/CD pipeline.

The core philosophy is a **container-first approach**, where all tools and services run in Docker containers for maximum portability and consistency. This eliminates the need for external dependencies beyond Docker itself. The architecture is modular, with specialized services called "MCP servers" that provide specific functionalities.

**Key Technologies:**

*   **Backend:** Python
*   **Containerization:** Docker, Docker Compose
*   **CI/CD:** GitHub Actions (self-hosted)
*   **AI Agents:** A sophisticated, multi-agent system including Claude, Gemini, OpenCode, Crush, and custom automation agents.
*   **MCP Servers:** A suite of custom servers for code quality, content creation, 3D graphics, video editing, and more.

## AI-Driven Development Workflow

This project leverages a multi-agent AI system to automate the development process, from issue creation to pull request merging.

1.  **Issue Creation:** An issue is created on GitHub.
2.  **Automated PR Creation:** The `Issue Monitor Agent` automatically creates a pull request to address the issue.
3.  **Automated PR Review:** The `Gemini CLI` agent automatically reviews the pull request for security, container configuration, and project standards.
4.  **Automated Review Response:** The `PR Review Monitor Agent` automatically implements fixes based on the feedback from the Gemini review.
5.  **Manual Intervention:** For more complex tasks, the `Claude Code` agent is the primary development assistant.

## Building and Running

The project is designed to be run entirely within Docker containers.

**1. Initial Setup:**

```bash
# Clone the repository
git clone https://github.com/AndrewAltimit/template-repo
cd template-repo

# Install the AI agents package (for CLI tools)
pip3 install -e ./packages/github_agents

# Set up API keys (if using AI features)
export OPENROUTER_API_KEY="your-key-here"
export GEMINI_API_KEY="your-key-here"
```

**2. Running Services:**

The primary way to run the services is through Docker Compose. The `docker-compose.yml` file defines various service profiles.

*   **Start all services:**
    ```bash
    docker-compose up -d
    ```
*   **Start a specific service:**
    ```bash
    docker-compose up -d <service-name>
    ```
    (e.g., `docker-compose up -d mcp-code-quality`)

**3. Running Tests:**

Tests are run using `pytest` within the `python-ci` container. The recommended way to run tests is by using the provided helper scripts.

*   **Run all tests (excluding Gaea2):**
    ```bash
    ./automation/ci-cd/run-ci.sh test
    ```
*   **Run all tests (including Gaea2):**
    ```bash
    ./automation/ci-cd/run-ci.sh test-all
    ```
*   **Run a specific test file:**
    ```bash
    docker-compose run --rm python-ci pytest tests/test_basic.py
    ```

**4. Linting and Formatting:**

The project uses `black` for formatting and `pylint` for linting. These are also run within the `python-ci` container via helper scripts.

*   **Check formatting:**
    ```bash
    ./automation/ci-cd/run-ci.sh format
    ```
*   **Run linting:**
    ```bash
    ./automation/ci-cd/run-ci.sh lint-basic
    ```
*   **Auto-format code:**
    ```bash
    ./automation/ci-cd/run-ci.sh autoformat
    ```

## Development Conventions

*   **Container-First:** All development, testing, and CI/CD operations should be performed within the provided Docker containers to ensure consistency.
*   **Code Style:** Python code is formatted with `black` and `isort`. The `pyproject.toml` file contains the specific configurations for these tools.
*   **Linting:** `pylint` and `bandit` are used for static analysis. The configurations are in `pyproject.toml`.
*   **Type Checking:** `mypy` is used for static type checking. The configuration is in `pyproject.toml`.
*   **Testing:** Tests are written using `pytest` and are located in the `tests/` directory.
*   **MCP Servers:** The project's core functionalities are exposed as "MCP servers." These can be run in either "stdio" or "http" mode. The `.mcp.json` file configures how AI agents interact with these servers.
*   **AI Integration:** The project is deeply integrated with various AI agents. The `CLAUDE.md`, `CRUSH.md`, and `docs/ai-agents/README.md` files provide extensive documentation on how to use and configure them.
*   **GitHub Etiquette:** There are strict rules for interacting with GitHub, such as not using "@" mentions for AI agents and using custom reaction images for comments.

## Documentation Hub

This project has extensive documentation. Here is a map to the most important documents:

**Core Documents:**

*   [README.md](README.md): The main entry point to the project.
*   [CLAUDE.md](CLAUDE.md): Instructions and guidelines for the Claude Code AI agent.
*   [CRUSH.md](CRUSH.md): Instructions and guidelines for the Crush AI agent.
*   [GEMINI.md](GEMINI.md): This file, providing context for the Gemini AI agent.

**AI Agents:**

*   [docs/ai-agents/README.md](docs/ai-agents/README.md): An overview of the AI agent ecosystem.
*   [docs/ai-agents/security.md](docs/ai-agents/security.md): A detailed explanation of the AI agent security model.
*   [docs/ai-agents/pr-monitoring.md](docs/ai-agents/pr-monitoring.md): How to monitor pull requests with AI agents.
*   [docs/ai-agents/containerization-strategy.md](docs/ai-agents/containerization-strategy.md): The strategy for containerizing AI agents.

**MCP Servers:**

*   [docs/mcp/README.md](docs/mcp/README.md): An overview of the Modular Command Protocol (MCP) server architecture.
*   [docs/mcp/servers.md](docs/mcp/servers.md): Detailed documentation for each MCP server.
*   [docs/mcp/tools.md](docs/mcp/tools.md): A reference for all the tools available through the MCP servers.

**Infrastructure:**

*   [docs/infrastructure/README.md](docs/infrastructure/README.md): An overview of the project's infrastructure.
*   [docs/infrastructure/self-hosted-runner.md](docs/infrastructure/self-hosted-runner.md): How to set up a self-hosted GitHub Actions runner.
*   [docs/infrastructure/containerization.md](docs/infrastructure/containerization.md): The philosophy and implementation of the container-based CI/CD.

**Integrations:**

*   [docs/integrations/README.md](docs/integrations/README.md): An overview of the project's integrations.
*   [docs/integrations/ai-services/README.md](docs/integrations/ai-services/README.md): How to integrate with various AI services.
*   [docs/integrations/creative-tools/README.md](docs/integrations/creative-tools/README.md): How to integrate with creative tools like AI Toolkit and ComfyUI.

**Developer Documentation:**

*   [docs/developer/README.md](docs/developer/README.md): An overview of the developer documentation.
*   [docs/developer/claude-code-hooks.md](docs/developer/claude-code-hooks.md): How to use Claude Code hooks to enforce best practices.
