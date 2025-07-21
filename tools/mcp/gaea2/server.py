"""Gaea2 Terrain Generation MCP Server"""

import asyncio  # noqa: F401
import json
import logging  # noqa: F401
import os
import platform
import sys  # noqa: F401
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union  # noqa: F401

from aiohttp import web  # noqa: F401

from ..core.base_server import BaseMCPServer
from ..core.utils import check_container_environment, ensure_directory, setup_logging
from .cli import Gaea2CLIAutomation

# Import Gaea2 modules (will be reorganized into subdirectories)
from .generation import Gaea2ProjectGenerator, Gaea2Templates
from .optimization import Gaea2Optimizer, Gaea2WorkflowAnalyzer
from .repair import Gaea2Repairer
from .validation import Gaea2Validator


class Gaea2MCPServer(BaseMCPServer):
    """MCP Server for Gaea2 terrain generation with comprehensive tools"""

    def __init__(
        self,
        gaea_path: Optional[str] = None,
        output_dir: str = "/app/output/gaea2",
        port: int = 8007,
    ):
        # Check if running in container
        if check_container_environment() and platform.system() != "Windows":
            print("WARNING: Gaea2 MCP server typically runs on Windows with Gaea2 installed")
            print("Some features may not work correctly without the Gaea2 executable")

        super().__init__(
            name="Gaea2 MCP Server",
            version="1.0.0",
            port=port,
        )

        self.logger = setup_logging("Gaea2MCP")
        self.output_dir = ensure_directory(output_dir)

        # Initialize Gaea2 path
        self.gaea_path = gaea_path or os.environ.get("GAEA2_PATH")
        if self.gaea_path:
            self.gaea_path = Path(self.gaea_path)
            if not self.gaea_path.exists():
                self.logger.warning(f"Gaea2 executable not found at {self.gaea_path}")
                self.gaea_path = None

        # Initialize components
        self.generator = Gaea2ProjectGenerator()
        self.templates = Gaea2Templates()
        self.validator = Gaea2Validator()
        self.optimizer = Gaea2Optimizer()
        self.analyzer = Gaea2WorkflowAnalyzer()
        self.repairer = Gaea2Repairer()
        self.cli = Gaea2CLIAutomation(self.gaea_path) if self.gaea_path else None

        # Execution history for debugging
        self.execution_history = []

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        """Return available Gaea2 tools"""
        tools = {
            "create_gaea2_project": {
                "description": "Create a new Gaea2 terrain project with nodes and connections",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Name for the Gaea2 project",
                        },
                        "workflow": {
                            "type": "object",
                            "description": "Complete workflow with nodes and connections",
                            "properties": {
                                "nodes": {"type": "array", "items": {"type": "object"}},
                                "connections": {
                                    "type": "array",
                                    "items": {"type": "object"},
                                },
                            },
                        },
                        "nodes": {
                            "type": "array",
                            "description": "List of nodes (if not using workflow)",
                            "items": {"type": "object"},
                        },
                        "connections": {
                            "type": "array",
                            "description": "List of connections (if not using workflow)",
                            "items": {"type": "object"},
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path to save the .terrain file",
                        },
                        "auto_validate": {
                            "type": "boolean",
                            "default": True,
                            "description": "Automatically validate and fix workflow",
                        },
                    },
                    "required": ["project_name"],
                },
            },
            "create_gaea2_from_template": {
                "description": "Create a Gaea2 project from a predefined template",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "template_name": {
                            "type": "string",
                            "enum": [
                                "basic_terrain",
                                "detailed_mountain",
                                "volcanic_terrain",
                                "desert_canyon",
                                "modular_portal_terrain",
                                "mountain_range",
                                "volcanic_island",
                                "canyon_system",
                                "coastal_cliffs",
                                "arctic_terrain",
                                "river_valley",
                            ],
                            "description": "Template to use",
                        },
                        "project_name": {
                            "type": "string",
                            "description": "Name for the project",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path to save the .terrain file",
                        },
                    },
                    "required": ["template_name", "project_name"],
                },
            },
            "validate_and_fix_workflow": {
                "description": "Validate and automatically fix a Gaea2 workflow",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workflow": {
                            "type": "object",
                            "properties": {
                                "nodes": {"type": "array"},
                                "connections": {"type": "array"},
                            },
                        },
                        "strict_mode": {
                            "type": "boolean",
                            "default": False,
                            "description": "Use strict validation rules",
                        },
                    },
                    "required": ["workflow"],
                },
            },
            "analyze_workflow_patterns": {
                "description": "Analyze workflow patterns and suggest improvements",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "workflow": {
                            "type": "object",
                            "properties": {
                                "nodes": {"type": "array"},
                                "connections": {"type": "array"},
                            },
                        },
                        "analysis_type": {
                            "type": "string",
                            "enum": ["patterns", "performance", "quality", "all"],
                            "default": "all",
                        },
                    },
                    "required": ["workflow"],
                },
            },
            "optimize_gaea2_properties": {
                "description": "Optimize node properties for performance or quality",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nodes": {
                            "type": "array",
                            "description": "List of nodes to optimize",
                        },
                        "optimization_mode": {
                            "type": "string",
                            "enum": ["performance", "quality", "balanced"],
                            "default": "balanced",
                        },
                    },
                    "required": ["nodes"],
                },
            },
            "suggest_gaea2_nodes": {
                "description": "Get intelligent node suggestions based on current workflow",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "current_nodes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of current node types",
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context about desired terrain",
                        },
                    },
                    "required": ["current_nodes"],
                },
            },
            "repair_gaea2_project": {
                "description": "Repair a damaged or corrupted Gaea2 project file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_path": {
                            "type": "string",
                            "description": "Path to the .terrain file to repair",
                        },
                        "backup": {
                            "type": "boolean",
                            "default": True,
                            "description": "Create backup before repair",
                        },
                    },
                    "required": ["project_path"],
                },
            },
        }

        # Add CLI automation tools if Gaea2 is available
        if self.cli:
            tools.update(
                {
                    "run_gaea2_project": {
                        "description": "Run a Gaea2 project via CLI to generate terrain",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "project_path": {
                                    "type": "string",
                                    "description": "Path to the .terrain file",
                                },
                                "resolution": {
                                    "type": "string",
                                    "enum": ["512", "1024", "2048", "4096", "8192"],
                                    "default": "1024",
                                },
                                "format": {
                                    "type": "string",
                                    "enum": ["exr", "raw", "png", "tiff"],
                                    "default": "exr",
                                },
                                "bake_only": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of specific nodes to bake",
                                },
                                "timeout": {
                                    "type": "integer",
                                    "default": 300,
                                    "description": "Timeout in seconds",
                                },
                            },
                            "required": ["project_path"],
                        },
                    },
                    "analyze_execution_history": {
                        "description": "Analyze Gaea2 execution history for debugging",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "last_n": {
                                    "type": "integer",
                                    "default": 10,
                                    "description": "Number of recent executions to analyze",
                                }
                            },
                        },
                    },
                }
            )

        return tools

    async def create_gaea2_project(
        self,
        project_name: str,
        workflow: Optional[Dict[str, Any]] = None,
        nodes: Optional[List[Dict[str, Any]]] = None,
        connections: Optional[List[Dict[str, Any]]] = None,
        output_path: Optional[str] = None,
        auto_validate: bool = True,
    ) -> Dict[str, Any]:
        """Create a new Gaea2 terrain project"""
        try:
            # Handle both API formats
            if workflow:
                nodes = workflow.get("nodes", [])
                connections = workflow.get("connections", [])
            elif not nodes:
                return {
                    "success": False,
                    "error": "Either 'workflow' or 'nodes' must be provided",
                }

            # Validate and fix if requested
            if auto_validate:
                validation_result = await self.validator.validate_and_fix({"nodes": nodes, "connections": connections})
                if validation_result["fixed"]:
                    nodes = validation_result["workflow"]["nodes"]
                    connections = validation_result["workflow"]["connections"]

            # Generate project
            project_data = await self.generator.create_project(
                project_name=project_name, nodes=nodes, connections=connections or []
            )

            # Save to file
            if not output_path:
                output_path = os.path.join(
                    self.output_dir,
                    f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.terrain",
                )

            ensure_directory(os.path.dirname(output_path))

            with open(output_path, "w") as f:
                json.dump(project_data, f, indent=2)

            return {
                "success": True,
                "project_path": output_path,
                "node_count": len(nodes),
                "connection_count": len(connections or []),
                "validation_applied": auto_validate,
            }

        except Exception as e:
            self.logger.error(f"Failed to create Gaea2 project: {str(e)}")
            return {"success": False, "error": str(e)}

    async def create_gaea2_from_template(
        self,
        *,
        template_name: str,
        project_name: str,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Gaea2 project from template"""
        try:
            # Get template
            template = await self.templates.get_template(template_name)
            if not template:
                return {"success": False, "error": f"Unknown template: {template_name}"}

            # Create project from template
            result = await self.create_gaea2_project(
                project_name=project_name,
                workflow=template,
                output_path=output_path,
                auto_validate=True,
            )

            if result["success"]:
                result["template_used"] = template_name

            return result

        except Exception as e:
            self.logger.error(f"Failed to create from template: {str(e)}")
            return {"success": False, "error": str(e)}

    async def validate_and_fix_workflow(self, *, workflow: Dict[str, Any], strict_mode: bool = False) -> Dict[str, Any]:
        """Validate and fix a Gaea2 workflow"""
        try:
            result = await self.validator.validate_and_fix(workflow, strict_mode=strict_mode)

            return {
                "success": True,
                "valid": result["valid"],
                "fixed": result["fixed"],
                "errors": result["errors"],
                "fixes_applied": result.get("fixes_applied", []),
                "workflow": result["workflow"],
            }

        except Exception as e:
            self.logger.error(f"Validation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def analyze_workflow_patterns(self, *, workflow: Dict[str, Any], analysis_type: str = "all") -> Dict[str, Any]:
        """Analyze workflow patterns"""
        try:
            analysis = await self.analyzer.analyze(workflow, analysis_type=analysis_type)

            return {"success": True, "analysis": analysis}

        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def optimize_gaea2_properties(
        self, *, nodes: List[Dict[str, Any]], optimization_mode: str = "balanced"
    ) -> Dict[str, Any]:
        """Optimize node properties"""
        try:
            optimized_nodes = await self.optimizer.optimize_nodes(nodes, mode=optimization_mode)

            return {
                "success": True,
                "optimized_nodes": optimized_nodes,
                "optimization_mode": optimization_mode,
            }

        except Exception as e:
            self.logger.error(f"Optimization failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def suggest_gaea2_nodes(self, *, current_nodes: List[str], context: Optional[str] = None) -> Dict[str, Any]:
        """Get node suggestions"""
        try:
            suggestions = await self.analyzer.suggest_nodes(current_nodes, context=context)

            return {"success": True, "suggestions": suggestions}

        except Exception as e:
            self.logger.error(f"Suggestion failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def repair_gaea2_project(self, *, project_path: str, backup: bool = True) -> Dict[str, Any]:
        """Repair a Gaea2 project file"""
        try:
            result = await self.repairer.repair_project(project_path, backup=backup)

            return {
                "success": result["success"],
                "repaired": result.get("repaired", False),
                "backup_path": result.get("backup_path"),
                "issues_found": result.get("issues_found", []),
                "fixes_applied": result.get("fixes_applied", []),
            }

        except Exception as e:
            self.logger.error(f"Repair failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def run_gaea2_project(
        self,
        *,
        project_path: str,
        resolution: str = "1024",
        format: str = "exr",
        bake_only: Optional[List[str]] = None,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Run a Gaea2 project via CLI"""
        if not self.cli:
            return {
                "success": False,
                "error": "Gaea2 CLI automation not available. Set GAEA2_PATH environment variable.",
            }

        try:
            result = await self.cli.run_project(
                project_path=project_path,
                resolution=resolution,
                output_format=format,
                bake_only=bake_only,
                timeout=timeout,
            )

            # Store in history
            self.execution_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "project": project_path,
                    "result": result,
                }
            )

            return result

        except Exception as e:
            self.logger.error(f"CLI execution failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def analyze_execution_history(self, *, last_n: int = 10) -> Dict[str, Any]:
        """Analyze recent execution history"""
        try:
            recent = self.execution_history[-last_n:]

            analysis = {
                "total_executions": len(self.execution_history),
                "recent_executions": len(recent),
                "success_rate": (sum(1 for e in recent if e["result"].get("success")) / len(recent) if recent else 0),
                "executions": recent,
            }

            return {"success": True, "analysis": analysis}

        except Exception as e:
            self.logger.error(f"History analysis failed: {str(e)}")
            return {"success": False, "error": str(e)}


def main():
    """Run the Gaea2 MCP Server"""
    import argparse

    parser = argparse.ArgumentParser(description="Gaea2 Terrain Generation MCP Server")
    parser.add_argument(
        "--mode",
        choices=["http", "stdio"],
        default="http",
        help="Server mode (http or stdio)",
    )
    parser.add_argument("--gaea-path", help="Path to Gaea2 executable (Gaea.Swarm.exe)")
    parser.add_argument(
        "--output-dir",
        default="/app/output/gaea2",
        help="Output directory for generated terrain files",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8007,
        help="Port to run the HTTP server on (default: 8007)",
    )
    args = parser.parse_args()

    # For Windows, check common Gaea2 installation paths
    if not args.gaea_path and platform.system() == "Windows":
        common_paths = [
            r"C:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe",
            r"C:\Program Files (x86)\QuadSpinner\Gaea\Gaea.Swarm.exe",
            r"D:\Program Files\QuadSpinner\Gaea\Gaea.Swarm.exe",
        ]
        for path in common_paths:
            if os.path.exists(path):
                args.gaea_path = path
                print(f"Found Gaea2 at: {path}")
                break

    server = Gaea2MCPServer(gaea_path=args.gaea_path, output_dir=args.output_dir, port=args.port)
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
