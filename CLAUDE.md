# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

This is a **single-maintainer project** by @AndrewAltimit with a **container-first philosophy**:

- All Python operations run in Docker containers
- Self-hosted infrastructure for zero-cost operation
- Designed for maximum portability - works on any Linux system with Docker
- No contributors model - optimized for individual developer efficiency

## AI Agent Collaboration

You are working alongside two other AI agents:

1. **Gemini CLI** - Handles automated PR code reviews
2. **GitHub Copilot** - Provides code review suggestions in PRs

Your role as Claude Code is the primary development assistant, handling:

- Architecture decisions and implementation
- Complex refactoring and debugging
- Documentation and test writing
- CI/CD pipeline development

### AI Agent Security

**IMPORTANT**: AI agents (Issue Monitor and PR Review Monitor) implement strict security measures:
- Only authorized users can trigger AI agent actions
- Allow list is configured in `scripts/agents/config.json`
- Unauthorized requests are blocked to prevent prompt injection attacks
- See `scripts/agents/README.md` for complete security documentation

## Commands

### Running Tests

```bash
# Run all tests with coverage (containerized)
docker-compose run --rm python-ci pytest tests/ -v --cov=. --cov-report=xml

# Run a specific test file
docker-compose run --rm python-ci pytest tests/test_mcp_tools.py -v

# Run tests with specific test name pattern
docker-compose run --rm python-ci pytest -k "test_format" -v

# Quick test run using helper script
./scripts/run-ci.sh test
```

### Code Quality

```bash
# Using containerized CI scripts (recommended)
./scripts/run-ci.sh format      # Check formatting
./scripts/run-ci.sh lint-basic   # Basic linting
./scripts/run-ci.sh lint-full    # Full linting suite
./scripts/run-ci.sh autoformat   # Auto-format code

# Direct Docker Compose commands
docker-compose run --rm python-ci black --check .
docker-compose run --rm python-ci flake8 .
docker-compose run --rm python-ci pylint tools/ scripts/
docker-compose run --rm python-ci mypy . --ignore-missing-imports

# Note: All Python CI/CD tools run in containers to ensure consistency

# Run all checks at once
./scripts/run-ci.sh full
```

### Development

```bash
# MODULAR MCP SERVERS (Container-First Approach)

# Start servers in Docker (recommended for consistency)
docker-compose up -d mcp-code-quality        # Port 8010 - Code formatting/linting
docker-compose up -d mcp-content-creation    # Port 8011 - Manim & LaTeX
docker-compose up -d mcp-gaea2               # Port 8007 - Terrain generation

# For local development (when actively developing server code)
python -m tools.mcp.code_quality.server      # Port 8010
python -m tools.mcp.content_creation.server  # Port 8011
python -m tools.mcp.gaea2.server             # Port 8007

# Gemini MUST run on host (requires Docker access)
python -m tools.mcp.gemini.server            # Port 8006 - AI integration (host only)
./tools/mcp/gemini/scripts/start_server.sh --mode http

# Test all MCP servers at once
python scripts/mcp/test_all_servers.py

# Quick test of running servers
python scripts/mcp/test_all_servers.py --quick

# View logs for specific servers
docker-compose logs -f mcp-code-quality

# Test individual servers
python tools/mcp/code_quality/scripts/test_server.py
python tools/mcp/content_creation/scripts/test_server.py
python tools/mcp/gemini/scripts/test_server.py
python tools/mcp/gaea2/scripts/test_server.py

# For Gemini (MUST run on host)
./tools/mcp/gemini/scripts/start_server.sh --mode http

# Run the main application
python main.py

# For local development without Docker
pip install -r requirements.txt
```

### Docker Operations

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f mcp-server
docker-compose logs -f python-ci

# Stop services
docker-compose down

# Rebuild after changes
docker-compose build mcp-server
docker-compose build python-ci
```

### Helper Scripts

```bash
# CI/CD operations script
./scripts/run-ci.sh [stage]
# Stages: format, lint-basic, lint-full, security, test, yaml-lint, json-lint, autoformat

# Lint stage helper (used in workflows)
./scripts/run-lint-stage.sh [stage]
# Stages: format, basic, full

# Fix runner permission issues
./scripts/fix-runner-permissions.sh
```

## Architecture

### MCP Server Architecture (Modular Design)

The project uses a modular collection of Model Context Protocol (MCP) servers, each specialized for specific functionality:

1. **Code Quality MCP Server** (`tools/mcp/code_quality/`): HTTP API on port 8010
   - **Code Formatting & Linting**:
     - `format_check` - Check code formatting (Python, JS, TS, Go, Rust)
     - `lint` - Run static analysis with multiple linters
     - `autoformat` - Automatically format code files
   - See `tools/mcp/code_quality/docs/README.md` for documentation

2. **Content Creation MCP Server** (`tools/mcp/content_creation/`): HTTP API on port 8011
   - **Manim & LaTeX Tools**:
     - `create_manim_animation` - Create mathematical/technical animations
     - `compile_latex` - Generate PDF/DVI/PS documents from LaTeX
     - `render_tikz` - Render TikZ diagrams as standalone images
   - See `tools/mcp/content_creation/docs/README.md` for documentation

3. **Gemini MCP Server** (`tools/mcp/gemini/`): HTTP API on port 8006
   - **MUST run on host system** (not in container) due to Docker requirements
   - **AI Integration**:
     - `consult_gemini` - Get AI assistance for technical questions
     - `clear_gemini_history` - Clear conversation history for fresh responses
     - `gemini_status` - Get integration status and statistics
     - `toggle_gemini_auto_consult` - Control auto-consultation
   - See `tools/mcp/gemini/docs/README.md` for documentation

4. **Gaea2 MCP Server** (`tools/mcp/gaea2/`): HTTP API on port 8007
   - **Terrain Generation** (185 nodes supported):
     - `create_gaea2_project` - Create custom terrain projects
     - `create_gaea2_from_template` - Use professional templates
     - `validate_and_fix_workflow` - Comprehensive validation and repair
     - `analyze_workflow_patterns` - Pattern-based workflow analysis
     - `optimize_gaea2_properties` - Performance/quality optimization
     - `suggest_gaea2_nodes` - Intelligent node suggestions
     - `repair_gaea2_project` - Fix damaged project files
     - `run_gaea2_project` - CLI automation (Windows only)
   - Can run locally or on remote server (192.168.0.152:8007)
   - See `tools/mcp/gaea2/docs/README.md` for complete documentation

5. **Remote Services**: ComfyUI (image generation), AI Toolkit (LoRA training)

6. **Shared Core Components** (`tools/mcp/core/`):
   - `BaseMCPServer` - Base class for all MCP servers
   - `HTTPBridge` - Bridge for remote MCP servers
   - Common utilities and helpers

7. **Containerized CI/CD**:
   - **Python CI Container** (`docker/python-ci.Dockerfile`): All Python tools
   - **Helper Scripts**: Centralized CI operations
   - **Individual MCP Containers**: Each server can run in its own optimized container

8. **Configuration**: Each server has its own configuration options

### GitHub Actions Integration

The repository includes comprehensive CI/CD workflows:

- **PR Validation**: Automatic Gemini AI code review with history clearing
- **Testing Pipeline**: Containerized pytest with coverage reporting
- **Code Quality**: Multi-stage linting in Docker containers
- **Self-hosted Runners**: All workflows run on self-hosted infrastructure
- **Runner Maintenance**: Automated cleanup and health checks

### Container Architecture Philosophy

1. **Everything Containerized**:
   - Python CI/CD tools run in `python-ci` container (Python 3.11)
   - MCP server runs in its own container
   - Only exception: Gemini CLI (would require Docker-in-Docker)
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
   - Gemini API for code review (runs on host due to Docker requirements)
   - Support for Claude and OpenAI integrations
   - Remote ComfyUI workflows for image generation

2. **Testing Strategy**:
   - All tests run in containers with Python 3.11
   - Mock external dependencies (subprocess, HTTP calls)
   - Async test support with pytest-asyncio
   - Coverage reporting with pytest-cov
   - No pytest cache to avoid permission issues

3. **Client Pattern** (`main.py`):
   - MCPClient class for interacting with MCP server
   - Example workflow demonstrating tool usage
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
  ./scripts/run-ci.sh full

  # Or individual checks
  ./scripts/run-ci.sh format
  ./scripts/run-ci.sh lint-basic
  ./scripts/run-ci.sh lint-full
  ```
- NEVER commit changes unless the user explicitly asks you to
- Always follow the container-first philosophy - use Docker for all Python operations
- Remember that Gemini CLI cannot be containerized (needs Docker access)
- Use pytest fixtures and mocks for testing external dependencies

## AI Toolkit & ComfyUI Integration Notes

When working with the remote MCP servers (AI Toolkit and ComfyUI):

1. **Dataset Paths**: Always use absolute paths in AI Toolkit configs:
   - ✅ `/ai-toolkit/datasets/dataset_name`
   - ❌ `dataset_name` (will fail with "No such file or directory")

2. **LoRA Transfer**: For files >100MB, use chunked upload:
   - See `transfer_lora_between_services.py` for working implementation
   - Parameters: `upload_id` (provide UUID), `total_size` (bytes), `chunk` (not `chunk_data`)

3. **FLUX Workflows**: Different from SD workflows:
   - Use FluxGuidance node (guidance ~3.5)
   - KSampler: cfg=1.0, sampler="heunpp2", scheduler="simple"
   - Negative prompt cannot be null (use empty string)

4. **MCP Tool Discovery**: The `/mcp/tools` endpoint may not list all tools
   - Check the gist source directly for complete tool list
   - Chunked upload tools exist even if not shown

See `docs/AI_TOOLKIT_COMFYUI_INTEGRATION_GUIDE.md` for comprehensive details.

## Gaea2 MCP Integration (✅ Fixed - Requires Server Restart)

The repository includes a comprehensive Gaea2 terrain generation system that is now fully functional with proper ID formatting and terrain file generation:

### Key Capabilities

1. **Complete Node Support**: All 185 documented Gaea2 nodes across 9 categories
2. **Intelligent Validation**: Multi-level validation with automatic error correction
3. **Pattern Intelligence**: Learning from 31 real projects (374 nodes, 440 connections)
4. **Performance Optimization**: 19x speedup through intelligent caching
5. **Professional Templates**: Ready-to-use workflows for common terrain types
6. **✅ Fixed ID Generation**: Non-sequential ID formatting for better Gaea2 compatibility
7. **✅ Working Terrain Files**: Successfully generates .terrain files that open in Gaea2
8. **✅ Robust API**: Supports both workflow dict and separate nodes/connections parameters
9. **✅ Node Properties**: Automatically adds NodeSize, PortCount, IsMaskable as needed
10. **✅ Range Formatting**: Range objects now have proper $id references

### Recent Fixes Applied

1. **✅ API Format**: Now supports both `workflow` dict and separate `nodes`/`connections` parameters
2. **✅ Property Names**: Automatically fixes property names using mapping ("RockSoftness" → "Rock Softness")
3. **✅ Missing Properties**: Nodes automatically get `PortCount`, `NodeSize`, `IsMaskable` when appropriate
4. **✅ Range Format**: Range properties now correctly include their own `$id` values
5. **✅ Variables Object**: Already had correct format `{"$id":"XX"}`
6. **✅ Connection Handling**: Fixed critical node ID mapping issue where connections failed when target nodes appeared before source nodes in the node list
7. **✅ Type Consistency**: All node IDs are now handled as strings internally to prevent type mismatch issues
8. **✅ Connection Records**: Connections are properly embedded in port definitions with Record objects

**Important**: The Gaea2 MCP server needs to be restarted to use these fixes!

### ⚠️ CRITICAL: Property Limitations for Certain Nodes

Through extensive testing, we discovered that some Gaea2 nodes **fail to open** when they have too many properties:

**Nodes that MUST have ≤ 3 properties:**
- **Snow** (most problematic - appears in many templates)
- Beach, Coast, Lakes, Glacier, SeaLevel
- LavaFlow, ThermalShatter, Ridge, Strata, Voronoi, Terrace

**Examples:**
- Snow with 1-3 properties: ✅ Opens successfully
- Snow with 8+ properties: ❌ File won't open in Gaea2

**The fix:** Smart mode (`property_mode="smart"`) now limits these nodes to their essential properties only:
- Snow: Duration, SnowLine, Melt (max 3)
- Beach: Width, Slope (max 2)
- Lakes: Count, Size (max 2)
- etc.

This is handled automatically when using templates or when `property_mode="smart"` is specified.

### Correct API Usage

```bash
# Using templates (most reliable)
curl -X POST http://192.168.0.152:8007/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "create_gaea2_from_template",
    "parameters": {
      "template_name": "mountain_range",
      "project_name": "my_terrain"
    }
  }'

# Available templates:
# basic_terrain, detailed_mountain, volcanic_terrain, desert_canyon,
# modular_portal_terrain, mountain_range, volcanic_island, canyon_system,
# coastal_cliffs, arctic_terrain, river_valley
```

##### Common Commands

```bash
# Test Gaea2 features
python tests/gaea2/test_gaea2_enhancements.py
python tests/gaea2/test_gaea2_robustness.py

# Run Gaea2-specific tests
docker-compose run --rm python-ci pytest tests/gaea2/ -v
```

### Connection System Details

**Critical**: Understanding how Gaea2 handles connections is essential for successful terrain generation:

1. **Connection Storage**: Unlike the API format, Gaea2 stores connections within port definitions as `Record` objects
2. **Node ID Mapping**: The server builds a complete node_id_map before processing connections to ensure all IDs are available
3. **Port Types**: Different nodes have different port configurations:
   - Standard nodes: Usually have "In" and "Out" ports
   - Combine nodes: Have "In", "Input2", and "Mask" ports
   - Rivers nodes: Have special output ports like "Rivers", "Depth", "Surface"
   - Sea nodes: Have output ports like "Water", "Shore", "Depth"

### Debugging Connections

If connections are missing in generated terrain files, check:

Common issues:
- **Node ordering**: Ensure node IDs are mapped before processing connections
- **Port names**: Use exact port names (case-sensitive)
- **Type consistency**: All node IDs should be strings in the API

### Development Tips

1. **Automatic Validation**: All Gaea2 projects created through MCP have **automatic validation built-in by default**
   - `create_gaea2_project` automatically validates and fixes workflows
   - Missing essential nodes (Export, SatMap) are added automatically
   - Invalid connections are repaired
   - Property values are corrected to valid ranges
   - Set `auto_validate=False` only if you need to bypass validation

2. **Pattern-Based Development**: Use `analyze_workflow_patterns` to get suggestions based on real projects
3. **Manual Validation**: Use `validate_and_fix_workflow` for existing projects or custom validation needs
4. **Performance vs Quality**: Use `optimize_gaea2_properties` with appropriate mode
5. **Templates First**: Start with templates for common terrain types, then customize

### Common Patterns (from 31 real projects)

- Most common workflow: Slump → FractalTerraces → Combine → Shear
- Most used nodes: SatMap (47), Combine (38), Erosion2 (29)
- Average project complexity: 12.1 nodes, 14.2 connections

### Automatic Error Recovery (Built-in)

**All Gaea2 projects are automatically validated and fixed during creation:**
- ✅ Duplicate connections are removed
- ✅ Out-of-range property values are corrected
- ✅ Missing required nodes (Export, SatMap) are added
- ✅ Orphaned nodes are connected or removed
- ✅ Workflow optimization issues are resolved
- ✅ Invalid node properties are fixed
- ✅ Connection validity is ensured
- ✅ File format is guaranteed to be Gaea2-compatible

**No manual intervention needed** - the MCP server handles all validation automatically!

For complete documentation, see:
- `docs/gaea2/INDEX.md` - Complete Gaea2 documentation index
- `docs/gaea2/README.md` - Main Gaea2 MCP documentation
- `docs/gaea2/GAEA2_API_REFERENCE.md` - Complete API reference
- `docs/gaea2/GAEA2_EXAMPLES.md` - Usage examples and patterns
