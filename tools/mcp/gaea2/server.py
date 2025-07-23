"""Gaea2 Terrain Generation MCP Server"""

import asyncio  # noqa: F401
import base64
import json
import logging  # noqa: F401
import os
import platform
import sys  # noqa: F401
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Any, Dict, List, Optional, Union  # noqa: F401

from aiohttp import web  # noqa: F401
from fastapi import Request, Response
from fastapi.responses import FileResponse

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
        enforce_file_validation: bool = True,
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

        # Use temp directory if in test mode or if default directory is not writable
        if os.environ.get("GAEA2_TEST_MODE") == "1" or os.environ.get("CI") == "true":
            import tempfile

            self.output_dir = tempfile.mkdtemp(prefix="gaea2_test_")
            self.logger.info(f"Using temporary directory for tests: {self.output_dir}")
        else:
            self.output_dir = ensure_directory(output_dir)

        # File validation enforcement - can be disabled via env var for tests
        self.enforce_file_validation = (
            enforce_file_validation and os.environ.get("GAEA2_BYPASS_FILE_VALIDATION_FOR_TESTS") != "1"
        )

        # Initialize Gaea2 path
        self.gaea_path: Optional[Path] = None
        gaea_path_str = gaea_path or os.environ.get("GAEA2_PATH")
        if gaea_path_str:
            self.gaea_path = Path(gaea_path_str)
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
        self.execution_history: List[Dict[str, Any]] = []

        # Add custom routes for file download
        self._setup_custom_routes()

    def _setup_custom_routes(self):
        """Setup custom routes for Gaea2 server"""
        self.app.get("/download/{filename}")(self.download_file_http)
        self.app.get("/files/{filename}")(self.download_file_http)
        self.app.get("/list")(self.list_files_http)

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

        # Add download tool
        tools["download_gaea2_project"] = {
            "description": "Download a previously created Gaea2 terrain file",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "The terrain filename (e.g., 'two_mountains_river_20250722_113730.terrain')",
                    },
                    "full_path": {
                        "type": "string",
                        "description": "Full path to the terrain file (optional, overrides filename)",
                    },
                    "encoding": {
                        "type": "string",
                        "enum": ["base64", "raw"],
                        "default": "base64",
                        "description": "How to encode the file data",
                    },
                },
                "required": ["filename"],
            },
        }

        tools["list_gaea2_projects"] = {
            "description": "List all terrain files in the output directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "default": "*.terrain",
                        "description": "File pattern to match",
                    },
                },
            },
        }

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
            # Validate input parameters
            if workflow is None and nodes is None:
                return {
                    "success": False,
                    "error": "Either 'workflow' or 'nodes' must be provided",
                }

            # Handle both API formats
            if workflow is not None:
                if not isinstance(workflow, dict):
                    return {
                        "success": False,
                        "error": "Workflow must be a dictionary with 'nodes' and 'connections'",
                    }
                nodes = workflow.get("nodes", [])
                connections = workflow.get("connections", [])

            # Validate and fix if requested
            if auto_validate:
                validation_result = await self.validator.validate_and_fix({"nodes": nodes, "connections": connections})
                if validation_result["fixed"]:
                    nodes = validation_result["workflow"]["nodes"]
                    connections = validation_result["workflow"]["connections"]

            # Generate project
            project_data = await self.generator.create_project(
                project_name=project_name,
                nodes=nodes or [],
                connections=connections or [],
            )

            # Save to file
            if not output_path:
                output_path = os.path.join(
                    self.output_dir,
                    f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.terrain",
                )

            ensure_directory(os.path.dirname(output_path))

            # Extract just the project data (not the wrapper with success, node_count, etc.)
            if isinstance(project_data, dict) and "project" in project_data:
                terrain_data = project_data["project"]
            else:
                terrain_data = project_data

            with open(output_path, "w") as f:
                json.dump(terrain_data, f, indent=2)

            # Perform file validation by opening in Gaea2
            file_validation_performed = False
            file_validation_passed = False
            file_validation_error = None

            # Check if we should bypass validation (for tests only)
            bypass_for_tests = os.environ.get("GAEA2_BYPASS_FILE_VALIDATION_FOR_TESTS") == "1"

            if self.enforce_file_validation and self.gaea_path and not bypass_for_tests:
                try:
                    from .validation.gaea2_file_validator import Gaea2FileValidator

                    self.logger.info(f"Validating generated file in Gaea2: {output_path}")
                    file_validator = Gaea2FileValidator(self.gaea_path)
                    validation_result = await file_validator.validate_file(output_path, timeout=30)

                    file_validation_performed = True
                    file_validation_passed = validation_result["success"]

                    if not file_validation_passed:
                        file_validation_error = validation_result.get("error", "File failed to open in Gaea2")
                        self.logger.error(f"File validation failed: {file_validation_error}")

                        # Delete the invalid file
                        try:
                            os.remove(output_path)
                            self.logger.info(f"Deleted invalid file: {output_path}")
                        except Exception as e:
                            self.logger.error(f"Failed to delete invalid file: {e}")

                        # Return failure
                        return {
                            "success": False,
                            "error": f"Generated file failed Gaea2 validation: {file_validation_error}",
                            "validation_error": file_validation_error,
                            "file_deleted": True,
                        }
                    else:
                        self.logger.info(f"File validation passed: {output_path}")

                except Exception as e:
                    self.logger.error(f"File validation error: {str(e)}")
                    # If validation system fails, still fail the generation
                    try:
                        os.remove(output_path)
                    except Exception:
                        pass
                    return {
                        "success": False,
                        "error": f"File validation system error: {str(e)}",
                    }
            elif bypass_for_tests:
                self.logger.warning("File validation bypassed for testing")
            elif not self.gaea_path:
                self.logger.warning("File validation skipped: Gaea2 path not configured")

            return {
                "success": True,
                "project_path": output_path,
                "node_count": len(nodes or []),
                "connection_count": len(connections or []),
                "validation_applied": auto_validate,
                "file_validation_performed": file_validation_performed,
                "file_validation_passed": file_validation_passed,
                "bypass_for_tests": bypass_for_tests,
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
            # Validate workflow structure
            if not isinstance(workflow, dict):
                return {"success": False, "error": "Workflow must be a dictionary"}

            if "nodes" in workflow and not isinstance(workflow["nodes"], list):
                return {"success": False, "error": "Workflow 'nodes' must be a list"}

            if "connections" in workflow and not isinstance(workflow["connections"], list):
                return {
                    "success": False,
                    "error": "Workflow 'connections' must be a list",
                }

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

    async def analyze_workflow_patterns(
        self,
        *,
        workflow: Optional[Dict[str, Any]] = None,
        workflow_or_directory: Optional[Union[Dict[str, Any], str]] = None,
        workflow_type: Optional[str] = None,
        analysis_type: str = "all",
        include_suggestions: bool = False,
    ) -> Dict[str, Any]:
        """Analyze workflow patterns

        Parameters:
        - workflow: Direct workflow dict (legacy)
        - workflow_or_directory: Workflow dict or directory path
        - workflow_type: Terrain type for pattern analysis (e.g., 'mountain', 'desert')
        - analysis_type: Type of analysis to perform
        """
        try:
            # Handle different parameter formats
            if workflow_type:
                # For terrain type analysis, create a basic workflow
                # This is used by regression tests
                from .templates.templates import Gaea2Templates

                templates = Gaea2Templates()
                template_map = {
                    "mountain": "mountain_range",
                    "desert": "desert_canyon",
                    "coastal": "coastal_cliffs",
                    "volcanic": "volcanic_terrain",
                    "arctic": "arctic_terrain",
                }
                template_name = template_map.get(workflow_type, "basic_terrain")
                template = await templates.get_template(template_name)
                workflow_data = {
                    "nodes": template["nodes"],
                    "connections": template["connections"],
                }
            elif workflow_or_directory:
                if isinstance(workflow_or_directory, dict):
                    workflow_data = workflow_or_directory
                else:
                    # Load from directory if string path provided
                    return {
                        "success": False,
                        "error": "Directory loading not implemented",
                    }
            elif workflow:
                workflow_data = workflow
            else:
                return {"success": False, "error": "No workflow data provided"}

            analysis = await self.analyzer.analyze(workflow_data, analysis_type=analysis_type)
            return {"success": True, "analysis": analysis}

        except Exception as e:
            self.logger.error(f"Analysis failed: {str(e)}")
            return {"success": False, "error": str(e)}

    async def optimize_gaea2_properties(
        self,
        *,
        nodes: Optional[List[Dict[str, Any]]] = None,
        workflow: Optional[Dict[str, Any]] = None,
        optimization_mode: str = "balanced",
    ) -> Dict[str, Any]:
        """Optimize node properties

        Parameters:
        - nodes: List of nodes to optimize
        - workflow: Workflow dict containing nodes (alternative format)
        - optimization_mode: 'performance', 'quality', or 'balanced'
        """
        try:
            # Handle different parameter formats
            if workflow and "nodes" in workflow:
                nodes_to_optimize = workflow["nodes"]
            elif nodes:
                nodes_to_optimize = nodes
            else:
                return {"success": False, "error": "No nodes provided for optimization"}

            optimized_nodes = await self.optimizer.optimize_nodes(nodes_to_optimize, mode=optimization_mode)

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

    async def download_gaea2_project(
        self,
        *,
        filename: str,
        full_path: Optional[str] = None,
        encoding: str = "base64",
    ) -> Dict[str, Any]:
        """Download a previously created Gaea2 terrain file"""
        try:
            # Determine file path
            if full_path and os.path.exists(full_path):
                file_path = full_path
            else:
                # Remove any path separators from filename for security
                safe_filename = os.path.basename(filename)
                file_path = os.path.join(self.output_dir, safe_filename)

            # Check if file exists
            if not os.path.exists(file_path):
                # Try with Windows path separator if not found
                if "\\" in filename:
                    safe_filename = os.path.basename(filename.split("\\")[-1])
                    file_path = os.path.join(self.output_dir, safe_filename)

                if not os.path.exists(file_path):
                    return {
                        "success": False,
                        "error": f"File not found: {safe_filename}",
                        "searched_path": file_path,
                    }

            # Read file
            with open(file_path, "rb") as f:
                file_data = f.read()

            # Get file info
            file_stats = os.stat(file_path)

            # Encode based on requested format
            if encoding == "base64":
                encoded_data = base64.b64encode(file_data).decode("utf-8")
                return {
                    "success": True,
                    "filename": os.path.basename(file_path),
                    "size": file_stats.st_size,
                    "modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                    "encoding": "base64",
                    "data": encoded_data,
                }
            else:
                # For raw, we'll return the file as JSON string (terrain files are JSON)
                try:
                    json_data = json.loads(file_data.decode("utf-8"))
                    return {
                        "success": True,
                        "filename": os.path.basename(file_path),
                        "size": file_stats.st_size,
                        "modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                        "encoding": "raw",
                        "data": json_data,
                    }
                except Exception:
                    # If not JSON, still return base64
                    encoded_data = base64.b64encode(file_data).decode("utf-8")
                    return {
                        "success": True,
                        "filename": os.path.basename(file_path),
                        "size": file_stats.st_size,
                        "modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                        "encoding": "base64",
                        "data": encoded_data,
                    }

        except Exception as e:
            self.logger.error(f"Failed to download file: {str(e)}")
            return {"success": False, "error": str(e)}

    async def list_gaea2_projects(
        self,
        *,
        pattern: str = "*.terrain",
    ) -> Dict[str, Any]:
        """List all terrain files in the output directory"""
        try:
            # Find matching files
            search_pattern = os.path.join(self.output_dir, pattern)
            files = glob(search_pattern)

            # Get file info
            file_list = []
            for file_path in files:
                try:
                    stats = os.stat(file_path)
                    file_list.append(
                        {
                            "filename": os.path.basename(file_path),
                            "path": file_path,
                            "size": stats.st_size,
                            "modified": datetime.fromtimestamp(stats.st_mtime).isoformat(),
                        }
                    )
                except Exception:
                    pass

            # Sort by modified time (newest first)
            file_list.sort(key=lambda x: str(x["modified"]), reverse=True)

            return {
                "success": True,
                "count": len(file_list),
                "files": file_list,
                "output_dir": self.output_dir,
            }

        except Exception as e:
            self.logger.error(f"Failed to list files: {str(e)}")
            return {"success": False, "error": str(e)}

    async def download_file_http(self, filename: str, request: Request):
        """HTTP endpoint for direct file download"""
        try:
            # Remove any path separators for security
            safe_filename = os.path.basename(filename)
            file_path = os.path.join(self.output_dir, safe_filename)

            if not os.path.exists(file_path):
                return Response(content="File not found", status_code=404)

            # Check if we should extract just the project field
            extract_project = request.query_params.get("extract_project", "").lower() == "true"

            if extract_project and file_path.endswith(".terrain"):
                # Read the file and extract project field if it exists
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)

                    # If it has the wrapper structure, extract just the project
                    if isinstance(data, dict) and "project" in data and "success" in data:
                        project_data = data["project"]
                        # Return as JSON response
                        return Response(
                            content=json.dumps(project_data, indent=2),
                            media_type="application/json",
                            headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
                        )
                except Exception:
                    # If JSON parsing fails, just return the file as-is
                    pass

            # Return file response as-is
            return FileResponse(
                path=file_path,
                filename=safe_filename,
                media_type="application/octet-stream",
            )

        except Exception as e:
            self.logger.error(f"HTTP download failed: {str(e)}")
            return Response(content=f"Download failed: {str(e)}", status_code=500)

    async def list_files_http(self):
        """HTTP endpoint to list files"""
        result = await self.list_gaea2_projects()
        return result


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
    parser.add_argument(
        "--no-enforce-file-validation",
        action="store_true",
        help="Disable mandatory file validation (not recommended for production)",
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

    server = Gaea2MCPServer(
        gaea_path=args.gaea_path,
        output_dir=args.output_dir,
        port=args.port,
        enforce_file_validation=not args.no_enforce_file_validation,
    )
    server.run(mode=args.mode)


if __name__ == "__main__":
    main()
