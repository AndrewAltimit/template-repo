#!/usr/bin/env python
"""
Standalone Gaea2 MCP Server

This server runs on the host system (Windows) where Gaea2 is installed and provides:
- All existing Gaea2 project creation and manipulation features
- CLI automation capabilities for running Gaea2 projects
- Verbose logging for debugging and learning

Must be run on the host system with access to Gaea2 executable.
"""

import asyncio
import json
import os
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from aiohttp import web

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# Import all Gaea2 modules
from tools.mcp.gaea2_accurate_validation import create_accurate_validator  # noqa: E402
from tools.mcp.gaea2_connection_validator import Gaea2ConnectionValidator  # noqa: E402
from tools.mcp.gaea2_enhanced import EnhancedGaea2Tools  # noqa: E402
from tools.mcp.gaea2_error_recovery import Gaea2ErrorRecovery  # noqa: E402
from tools.mcp.gaea2_knowledge_graph import knowledge_graph  # noqa: E402

# Pattern knowledge is available as module functions, not a class
from tools.mcp.gaea2_project_repair import Gaea2ProjectRepair  # noqa: E402
from tools.mcp.gaea2_property_validator import Gaea2PropertyValidator  # noqa: E402
from tools.mcp.gaea2_schema import apply_default_properties  # noqa: E402
from tools.mcp.gaea2_structure_validator import Gaea2StructureValidator  # noqa: E402
from tools.mcp.gaea2_workflow_analyzer import Gaea2WorkflowAnalyzer  # noqa: E402
from tools.mcp.gaea2_workflow_tools import Gaea2WorkflowTools  # noqa: E402


class Gaea2MCPServer:
    """Standalone Gaea2 MCP Server with CLI automation"""

    def __init__(self, gaea_path: Optional[str] = None):
        """
        Initialize the Gaea2 MCP server.

        Args:
            gaea_path: Path to Gaea2 executable (Gaea.Swarm.exe).
                      If not provided, will look for GAEA2_PATH env var.
        """
        self.gaea_path = gaea_path or os.environ.get("GAEA2_PATH")
        if self.gaea_path:
            self.gaea_path = Path(self.gaea_path)
            if not self.gaea_path.exists():
                print(f"Warning: Gaea2 executable not found at {self.gaea_path}")
                self.gaea_path = None

        self.host = "0.0.0.0"
        self.port = 8007  # Different port from main MCP (8005) and Gemini (8006)

        # Initialize enhanced tools
        self.enhanced_tools = EnhancedGaea2Tools()
        self.workflow_tools = Gaea2WorkflowTools()

        # Execution history for debugging
        self.execution_history = []

        # Check if running in container
        if os.path.exists("/.dockerenv") or os.environ.get("DOCKER_CONTAINER"):
            print("ERROR: Gaea2 MCP server must run on host system with Gaea2 installed")
            print("This server needs direct access to the Gaea2 executable")
            sys.exit(1)

    def _ensure_property_types(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure property values have correct types"""
        if not isinstance(properties, dict):
            return properties

        result = {}
        for key, value in properties.items():
            if isinstance(value, dict):
                result[key] = self._ensure_property_types(value)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                result[key] = float(value)
            else:
                result[key] = value

        return result

    async def create_gaea2_project(
        self,
        project_name: str,
        workflow: List[Dict[str, Any]],
        auto_validate: bool = True,
    ) -> Dict[str, Any]:
        """Create a Gaea2 project file with automatic validation"""
        try:
            # Apply default properties
            for node in workflow:
                apply_default_properties(node)
                if "properties" in node:
                    node["properties"] = self._ensure_property_types(node["properties"])

            # Auto-validate and fix workflow
            if auto_validate:
                validator = create_accurate_validator()
                is_valid, errors = validator.validate_workflow(workflow)

                if not is_valid:
                    # Try to fix the workflow
                    fixed_workflow = validator.fix_workflow(workflow)
                    workflow = fixed_workflow

                    # Validate again
                    is_valid, remaining_errors = validator.validate_workflow(workflow)
                    if not is_valid:
                        return {
                            "success": False,
                            "error": f"Validation failed after auto-fix: {remaining_errors}",
                        }

            # Create project structure
            project = {
                "version": "1.0",
                "name": project_name,
                "workflow": workflow,
                "created": datetime.now().isoformat(),
                "metadata": {
                    "created_by": "Gaea2 MCP Server",
                    "auto_validated": auto_validate,
                },
            }

            return {"success": True, "project": project}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def run_gaea2_project(
        self,
        project_path: str,
        output_dir: Optional[str] = None,
        variables: Optional[Dict[str, Any]] = None,
        verbose: bool = True,
        ignore_cache: bool = False,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run a Gaea2 project using CLI automation"""
        if not self.gaea_path:
            return {
                "success": False,
                "error": "Gaea2 executable path not configured. Set GAEA2_PATH environment variable.",
            }

        try:
            # Prepare command
            cmd = [str(self.gaea_path), "-filename", project_path]

            # Add optional parameters
            if verbose:
                cmd.append("-verbose")
            if ignore_cache:
                cmd.append("-ignorecache")
            if seed is not None:
                cmd.extend(["-seed", str(seed)])

            # Add variables
            if variables:
                for key, value in variables.items():
                    cmd.extend(["-v", f"{key}={value}"])

            # Create output directory if specified
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                # Note: Gaea2 may need specific export nodes configured
                # to output to a specific directory

            # Log execution
            execution_log = {
                "timestamp": datetime.now().isoformat(),
                "command": " ".join(cmd),
                "project": project_path,
                "variables": variables,
            }

            # Run Gaea2
            print(f"Executing Gaea2: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(project_path) if output_dir is None else output_dir,
            )

            stdout, stderr = await process.communicate()

            # Decode output
            stdout_text = stdout.decode("utf-8", errors="replace")
            stderr_text = stderr.decode("utf-8", errors="replace")

            execution_log.update(
                {
                    "return_code": process.returncode,
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "success": process.returncode == 0,
                }
            )

            # Store in history
            self.execution_history.append(execution_log)

            # Parse output for useful information
            result = {
                "success": process.returncode == 0,
                "return_code": process.returncode,
                "command": " ".join(cmd),
                "output": {"stdout": stdout_text, "stderr": stderr_text},
            }

            # Try to extract useful information from verbose output
            if verbose and stdout_text:
                result["parsed_output"] = self._parse_gaea_output(stdout_text)

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _parse_gaea_output(self, output: str) -> Dict[str, Any]:
        """Parse Gaea2 verbose output for useful information"""
        parsed = {
            "nodes_processed": [],
            "errors": [],
            "warnings": [],
            "timings": {},
            "exports": [],
        }

        lines = output.split("\n")
        for line in lines:
            line = line.strip()

            # Look for node processing
            if "Processing node:" in line:
                parsed["nodes_processed"].append(line.split("Processing node:")[-1].strip())

            # Look for errors
            elif "ERROR:" in line or "Error:" in line:
                parsed["errors"].append(line)

            # Look for warnings
            elif "WARNING:" in line or "Warning:" in line:
                parsed["warnings"].append(line)

            # Look for timing information
            elif "Time:" in line or "Duration:" in line:
                parts = line.split(":")
                if len(parts) >= 2:
                    key = parts[0].strip()
                    value = ":".join(parts[1:]).strip()
                    parsed["timings"][key] = value

            # Look for export information
            elif "Exported" in line or "Saved" in line:
                parsed["exports"].append(line)

        return parsed

    async def validate_and_fix_workflow(
        self,
        workflow: Union[str, List[Dict[str, Any]]],
        fix_errors: bool = True,
        validate_connections: bool = True,
        validate_properties: bool = True,
        add_missing_nodes: bool = True,
        optimize_workflow: bool = False,
    ) -> Dict[str, Any]:
        """Comprehensive workflow validation and fixing"""
        try:
            # Load workflow if it's a file path
            if isinstance(workflow, str):
                with open(workflow, "r") as f:
                    data = json.load(f)
                    workflow = data.get("workflow", data)

            results = {
                "original_workflow": workflow,
                "validation_results": {},
                "fixes_applied": [],
                "final_workflow": None,
                "is_valid": False,
            }

            # Multi-level validation
            validators = []

            if validate_properties:
                validators.append(("properties", Gaea2PropertyValidator()))

            if validate_connections:
                validators.append(("connections", Gaea2ConnectionValidator()))

            # Structure validation
            validators.append(("structure", Gaea2StructureValidator()))

            # Run all validators
            all_valid = True
            for name, validator in validators:
                is_valid, errors = validator.validate_workflow(workflow)
                results["validation_results"][name] = {
                    "valid": is_valid,
                    "errors": errors,
                }
                if not is_valid:
                    all_valid = False

            # Apply fixes if requested
            if fix_errors and not all_valid:
                recovery = Gaea2ErrorRecovery()
                fixed_workflow, fixes = recovery.fix_workflow(workflow)
                results["fixes_applied"] = fixes
                workflow = fixed_workflow

            # Add missing essential nodes
            if add_missing_nodes:
                validator = create_accurate_validator()
                workflow = validator.fix_workflow(workflow)

            # Optimize if requested
            if optimize_workflow:
                # Use workflow analyzer for optimization suggestions
                analyzer = Gaea2WorkflowAnalyzer()
                analysis = analyzer.analyze_workflow(workflow)
                if analysis.get("suggestions"):
                    results["optimization_suggestions"] = analysis["suggestions"]

            results["final_workflow"] = workflow
            results["is_valid"] = all_valid or fix_errors

            return {"success": True, "results": results}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def analyze_execution_history(self) -> Dict[str, Any]:
        """Analyze execution history to learn from runs"""
        if not self.execution_history:
            return {
                "success": True,
                "message": "No execution history available",
                "history": [],
            }

        analysis = {
            "total_runs": len(self.execution_history),
            "successful_runs": sum(1 for h in self.execution_history if h.get("success")),
            "failed_runs": sum(1 for h in self.execution_history if not h.get("success")),
            "common_errors": {},
            "average_duration": None,
            "recent_runs": self.execution_history[-10:],  # Last 10 runs
        }

        # Analyze common errors
        for history in self.execution_history:
            if not history.get("success") and history.get("stderr"):
                stderr = history["stderr"]
                # Extract error patterns
                if "ERROR:" in stderr:
                    error_lines = [line for line in stderr.split("\n") if "ERROR:" in line]
                    for error in error_lines:
                        error_type = error.split("ERROR:")[-1].strip()[:50]  # First 50 chars
                        analysis["common_errors"][error_type] = analysis["common_errors"].get(error_type, 0) + 1

        return {"success": True, "analysis": analysis}

    async def handle_tools(self, request: web.Request) -> web.Response:
        """List available tools"""
        tools = [
            {
                "name": "create_gaea2_project",
                "description": "Create a Gaea2 terrain project with automatic validation",
                "parameters": {
                    "project_name": "Name of the project",
                    "workflow": "List of nodes and connections",
                    "auto_validate": "Automatically validate and fix (default: true)",
                },
            },
            {
                "name": "run_gaea2_project",
                "description": "Run a Gaea2 project using CLI automation",
                "parameters": {
                    "project_path": "Path to the .terrain file",
                    "output_dir": "Output directory (optional)",
                    "variables": "Variables to pass to Gaea2 (optional)",
                    "verbose": "Enable verbose logging (default: true)",
                    "ignore_cache": "Ignore baked cache (default: false)",
                    "seed": "Mutation seed (optional)",
                },
            },
            {
                "name": "validate_and_fix_workflow",
                "description": "Comprehensive workflow validation and fixing",
                "parameters": {
                    "workflow": "Workflow or path to workflow file",
                    "fix_errors": "Automatically fix errors (default: true)",
                    "validate_connections": "Validate node connections (default: true)",
                    "validate_properties": "Validate node properties (default: true)",
                    "add_missing_nodes": "Add missing essential nodes (default: true)",
                    "optimize_workflow": "Suggest optimizations (default: false)",
                },
            },
            {
                "name": "analyze_execution_history",
                "description": "Analyze execution history to learn from runs",
                "parameters": {},
            },
            {
                "name": "create_gaea2_from_template",
                "description": "Create project from template",
                "parameters": {
                    "template_name": "Template name",
                    "project_name": "Project name",
                    "customizations": "Optional customizations",
                },
            },
            {
                "name": "analyze_workflow_patterns",
                "description": "Analyze workflow patterns",
                "parameters": {
                    "workflow_or_directory": "Workflow or directory path",
                    "include_suggestions": "Include suggestions (default: true)",
                },
            },
            {
                "name": "suggest_gaea2_nodes",
                "description": "Get intelligent node suggestions",
                "parameters": {
                    "current_nodes": "List of current nodes",
                    "context": "Optional context",
                    "limit": "Max suggestions (default: 5)",
                },
            },
            {
                "name": "repair_gaea2_project",
                "description": "Repair damaged Gaea2 project",
                "parameters": {
                    "project_path": "Path to project file",
                    "backup": "Create backup (default: true)",
                    "aggressive": "Aggressive repair (default: false)",
                },
            },
            {
                "name": "optimize_gaea2_properties",
                "description": "Optimize node properties",
                "parameters": {
                    "workflow": "Workflow to optimize",
                    "optimization_mode": "Mode: 'performance', 'quality', or 'balanced'",
                },
            },
        ]

        return web.json_response({"tools": tools})

    async def handle_execute(self, request: web.Request) -> web.Response:
        """Execute a tool"""
        try:
            data = await request.json()
            tool_name = data.get("tool")
            params = data.get("parameters", {})

            # Map tool names to methods
            tool_map = {
                "create_gaea2_project": self.create_gaea2_project,
                "run_gaea2_project": self.run_gaea2_project,
                "validate_and_fix_workflow": self.validate_and_fix_workflow,
                "analyze_execution_history": self.analyze_execution_history,
                "create_gaea2_from_template": self.enhanced_tools.create_from_template,
                "analyze_workflow_patterns": self._analyze_workflow_patterns,
                "suggest_gaea2_nodes": self._suggest_nodes,
                "repair_gaea2_project": self._repair_project,
                "optimize_gaea2_properties": self._optimize_properties,
            }

            if tool_name not in tool_map:
                return web.json_response({"error": f"Unknown tool: {tool_name}"}, status=400)

            # Execute tool
            result = await tool_map[tool_name](**params)

            return web.json_response(result)

        except Exception as e:
            return web.json_response({"error": str(e), "success": False}, status=500)

    async def _analyze_workflow_patterns(self, workflow_or_directory: str, include_suggestions: bool = True) -> Dict[str, Any]:
        """Analyze workflow patterns"""
        analyzer = Gaea2WorkflowAnalyzer()

        if os.path.isdir(workflow_or_directory):
            results = analyzer.analyze_directory(workflow_or_directory)
        else:
            # Load workflow
            with open(workflow_or_directory, "r") as f:
                workflow = json.load(f)
            results = analyzer.analyze_workflow(workflow.get("workflow", workflow))

        return {"success": True, "analysis": results}

    async def _suggest_nodes(self, current_nodes: List[str], context: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        """Get node suggestions"""
        suggestions = knowledge_graph.suggest_next_nodes(current_nodes, context, limit)
        return {"success": True, "suggestions": suggestions}

    async def _repair_project(self, project_path: str, backup: bool = True, aggressive: bool = False) -> Dict[str, Any]:
        """Repair project"""
        repair = Gaea2ProjectRepair()

        # Load project
        project = repair.load_project(project_path)
        if not project:
            return {"success": False, "error": "Failed to load project"}

        # Create backup if requested
        if backup:
            backup_path = f"{project_path}.backup"
            shutil.copy2(project_path, backup_path)

        # Repair
        repaired, report = repair.repair_project(project, aggressive)

        # Save
        if repair.save_project(repaired, project_path):
            return {"success": True, "report": report}
        else:
            return {"success": False, "error": "Failed to save repaired project"}

    async def _optimize_properties(
        self,
        workflow: Union[str, List[Dict[str, Any]]],
        optimization_mode: str = "balanced",
    ) -> Dict[str, Any]:
        """Optimize properties"""
        if isinstance(workflow, str):
            with open(workflow, "r") as f:
                data = json.load(f)
                workflow = data.get("workflow", data)

        # Use workflow tools for optimization
        if optimization_mode == "performance":
            optimized = self.workflow_tools.optimize_for_performance(workflow)
        elif optimization_mode == "quality":
            optimized = self.workflow_tools.optimize_for_quality(workflow)
        else:
            # Balanced mode - moderate settings
            optimized = workflow
            for node in optimized:
                if node["type"] == "Erosion" and "properties" in node:
                    node["properties"]["iterations"] = 15
                    node["properties"]["downcutting"] = 0.3

        return {"success": True, "optimized_workflow": optimized}

    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint"""
        health = {
            "status": "healthy",
            "server": "Gaea2 MCP Server",
            "version": "1.0.0",
            "gaea_configured": self.gaea_path is not None,
            "platform": platform.system(),
            "execution_history_count": len(self.execution_history),
        }

        if self.gaea_path:
            health["gaea_path"] = str(self.gaea_path)

        return web.json_response(health)

    def create_app(self) -> web.Application:
        """Create the web application"""
        app = web.Application()

        # Add routes
        app.router.add_get("/health", self.handle_health)
        app.router.add_get("/mcp/tools", self.handle_tools)
        app.router.add_post("/mcp/execute", self.handle_execute)

        return app

    async def start(self):
        """Start the server"""
        app = self.create_app()

        print(f"Starting Gaea2 MCP Server on {self.host}:{self.port}")
        if self.gaea_path:
            print(f"Gaea2 executable: {self.gaea_path}")
        else:
            print("WARNING: Gaea2 executable not configured. CLI features disabled.")
            print("Set GAEA2_PATH environment variable to enable CLI automation.")

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)

        await site.start()
        print(f"Server started at http://{self.host}:{self.port}")

        # Keep running
        await asyncio.Event().wait()


def main():
    """Main entry point"""
    # Get Gaea2 path from command line or environment
    gaea_path = None
    if len(sys.argv) > 1:
        gaea_path = sys.argv[1]

    server = Gaea2MCPServer(gaea_path)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nShutting down Gaea2 MCP Server...")


if __name__ == "__main__":
    main()
