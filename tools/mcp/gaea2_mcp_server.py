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
import logging
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
# Removed unused import: create_accurate_validator
from tools.mcp.gaea2_connection_validator import Gaea2ConnectionValidator  # noqa: E402
from tools.mcp.gaea2_enhanced import EnhancedGaea2Tools  # noqa: E402
from tools.mcp.gaea2_error_recovery import Gaea2ErrorRecovery  # noqa: E402
from tools.mcp.gaea2_knowledge_graph import knowledge_graph  # noqa: E402

# Pattern knowledge is available as module functions, not a class
from tools.mcp.gaea2_project_repair import Gaea2ProjectRepair  # noqa: E402
from tools.mcp.gaea2_property_validator import Gaea2PropertyValidator  # noqa: E402
from tools.mcp.gaea2_schema import WORKFLOW_TEMPLATES, create_workflow_from_template  # noqa: E402
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
        # Set up logging
        self.logger = logging.getLogger(__name__)

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

    def _create_gaea2_project_structure(self, project_name: str, nodes: List[Dict], connections: List[Dict]) -> Dict[str, Any]:
        """Create a Gaea2 project structure in the correct .terrain format"""
        import uuid

        # Generate IDs
        project_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%SZ")

        # Initialize sequential ID counter starting from 1
        ref_id_counter = 1

        # Pre-process connections to know which nodes need Records
        node_connections = {}
        if connections:
            for conn in connections:
                to_id = conn.get("to_node")
                to_port = conn.get("to_port", "In")
                if to_id not in node_connections:
                    node_connections[to_id] = {}
                node_connections[to_id][to_port] = conn

        # Node type mapping to Gaea2 .NET types
        node_type_mapping = {
            # Terrain
            "Mountain": "QuadSpinner.Gaea.Nodes.Mountain, Gaea.Nodes",
            "Ridge": "QuadSpinner.Gaea.Nodes.Ridge, Gaea.Nodes",
            "Primitive": "QuadSpinner.Gaea.Nodes.Primitive, Gaea.Nodes",
            "Perlin": "QuadSpinner.Gaea.Nodes.Perlin, Gaea.Nodes",
            "Canyon": "QuadSpinner.Gaea.Nodes.Canyon, Gaea.Nodes",
            "Dunes": "QuadSpinner.Gaea.Nodes.Dunes, Gaea.Nodes",
            "Fault": "QuadSpinner.Gaea.Nodes.Fault, Gaea.Nodes",
            "Crater": "QuadSpinner.Gaea.Nodes.Crater, Gaea.Nodes",
            "Volcano": "QuadSpinner.Gaea.Nodes.Volcano, Gaea.Nodes",
            "Island": "QuadSpinner.Gaea.Nodes.Island, Gaea.Nodes",
            # Erosion
            "Erosion": "QuadSpinner.Gaea.Nodes.Erosion, Gaea.Nodes",
            "Erosion2": "QuadSpinner.Gaea.Nodes.Erosion2, Gaea.Nodes",
            "Thermal": "QuadSpinner.Gaea.Nodes.Thermal, Gaea.Nodes",
            "Rivers": "QuadSpinner.Gaea.Nodes.Rivers, Gaea.Nodes",
            "FlowMap": "QuadSpinner.Gaea.Nodes.FlowMap, Gaea.Nodes",
            "Snow": "QuadSpinner.Gaea.Nodes.Snow, Gaea.Nodes",
            "Snowfall": "QuadSpinner.Gaea.Nodes.Snowfall, Gaea.Nodes",
            "Stratify": "QuadSpinner.Gaea.Nodes.Stratify, Gaea.Nodes",
            "Slump": "QuadSpinner.Gaea.Nodes.Slump, Gaea.Nodes",
            "Shear": "QuadSpinner.Gaea.Nodes.Shear, Gaea.Nodes",
            "Crumble": "QuadSpinner.Gaea.Nodes.Crumble, Gaea.Nodes",
            # Water
            "Sea": "QuadSpinner.Gaea.Nodes.Sea, Gaea.Nodes",
            "Lakes": "QuadSpinner.Gaea.Nodes.Lakes, Gaea.Nodes",
            "Water": "QuadSpinner.Gaea.Nodes.Water, Gaea.Nodes",
            "Coast": "QuadSpinner.Gaea.Nodes.Coast, Gaea.Nodes",
            # Adjustment
            "Combine": "QuadSpinner.Gaea.Nodes.Combine, Gaea.Nodes",
            "FractalTerraces": "QuadSpinner.Gaea.Nodes.FractalTerraces, Gaea.Nodes",
            "Adjust": "QuadSpinner.Gaea.Nodes.Adjust, Gaea.Nodes",
            "Transform": "QuadSpinner.Gaea.Nodes.Transform, Gaea.Nodes",
            "Blur": "QuadSpinner.Gaea.Nodes.Blur, Gaea.Nodes",
            "Warp": "QuadSpinner.Gaea.Nodes.Warp, Gaea.Nodes",
            "Clamp": "QuadSpinner.Gaea.Nodes.Clamp, Gaea.Nodes",
            # Color
            "SatMap": "QuadSpinner.Gaea.Nodes.SatMap, Gaea.Nodes",
            "TextureBase": "QuadSpinner.Gaea.Nodes.TextureBase, Gaea.Nodes",
            "Texture": "QuadSpinner.Gaea.Nodes.Texture, Gaea.Nodes",
            "CLUTer": "QuadSpinner.Gaea.Nodes.CLUTer, Gaea.Nodes",
            # Data and Output
            "Export": "QuadSpinner.Gaea.Nodes.Export, Gaea.Nodes",
            "Unity": "QuadSpinner.Gaea.Nodes.Unity, Gaea.Nodes",
            "Unreal": "QuadSpinner.Gaea.Nodes.Unreal, Gaea.Nodes",
            "Data": "QuadSpinner.Gaea.Nodes.Data, Gaea.Nodes",
            "File": "QuadSpinner.Gaea.Nodes.File, Gaea.Nodes",
            # Selectors
            "Mask": "QuadSpinner.Gaea.Nodes.Mask, Gaea.Nodes",
            "Height": "QuadSpinner.Gaea.Nodes.Height, Gaea.Nodes",
            "Slope": "QuadSpinner.Gaea.Nodes.Slope, Gaea.Nodes",
            "HeightSelector": "QuadSpinner.Gaea.Nodes.HeightSelector, Gaea.Nodes",
            "SlopeSelector": "QuadSpinner.Gaea.Nodes.SlopeSelector, Gaea.Nodes",
            # Add more as discovered
        }

        # Process nodes
        node_id_base = 100
        node_id_map = {}  # Map from our IDs to Gaea numeric IDs
        gaea_nodes = {}

        for i, node in enumerate(nodes):
            node_id = node_id_base + i * 10
            node_id_map[node.get("id", f"node_{i}")] = node_id

            # Get node type
            node_type = node.get("type", "Mountain")
            gaea_type = node_type_mapping.get(node_type, f"QuadSpinner.Gaea.Nodes.{node_type}, Gaea.Nodes")

            # Create Gaea node structure with sequential IDs
            gaea_node = {
                "$id": str(ref_id_counter),
                "$type": gaea_type,
                "Id": node_id,
                "Name": node.get("name", node_type),
                "Position": {
                    "$id": str(ref_id_counter + 1),
                    "X": float(node.get("position", {}).get("x", 24000 + i * 500)),
                    "Y": float(node.get("position", {}).get("y", 26000)),
                },
                "Ports": {"$id": str(ref_id_counter + 2), "$values": []},
                "Modifiers": {"$id": str(ref_id_counter + 3), "$values": []},
                "SnapIns": {"$id": str(ref_id_counter + 4), "$values": []},
            }

            # Update counter for next elements
            ref_id_counter += 5

            # Add node properties
            properties = node.get("properties", {})
            for prop, value in properties.items():
                gaea_node[prop] = value

            # Handle Export node SaveDefinition
            if node_type == "Export" and node.get("save_definition"):
                save_def = node["save_definition"]
                gaea_node["SaveDefinition"] = {
                    "$id": str(ref_id_counter),
                    "Node": node_id,
                    "Filename": save_def.get("filename", node.get("name", "Export")),
                    "Format": save_def.get("format", "EXR").upper(),
                    "IsEnabled": save_def.get("enabled", True),
                }
                ref_id_counter += 1

            # Add ports based on node type
            node_str_id = node.get("id", f"node_{i}")

            if node_type in ["Export", "SatMap"]:
                # In port
                port_in = {
                    "$id": str(ref_id_counter),
                    "Name": "In",
                    "Type": "PrimaryIn, Required",
                    "IsExporting": True,
                    "Parent": {"$ref": gaea_node["$id"]},
                }
                ref_id_counter += 1

                # Check if this port has an incoming connection
                if node_str_id in node_connections and "In" in node_connections[node_str_id]:
                    conn = node_connections[node_str_id]["In"]
                    from_id = node_id_map.get(conn.get("from_node"))
                    if from_id:
                        port_in["Record"] = {
                            "$id": str(ref_id_counter),
                            "From": from_id,
                            "To": node_id,
                            "FromPort": conn.get("from_port", "Out"),
                            "ToPort": "In",
                            "IsValid": True,
                        }
                        ref_id_counter += 1

                gaea_node["Ports"]["$values"].append(port_in)

                # Out port
                gaea_node["Ports"]["$values"].append(
                    {
                        "$id": str(ref_id_counter),
                        "Name": "Out",
                        "Type": "PrimaryOut",
                        "IsExporting": True,
                        "Parent": {"$ref": gaea_node["$id"]},
                    }
                )
                ref_id_counter += 1

            elif node_type == "Combine":
                # Combine has multiple inputs
                for port_name in ["In", "Input2", "Mask"]:
                    port = {
                        "$id": str(ref_id_counter),
                        "Name": port_name,
                        "Type": "PrimaryIn" if port_name == "In" else "In",
                        "IsExporting": True,
                        "Parent": {"$ref": gaea_node["$id"]},
                    }
                    ref_id_counter += 1

                    # Check for connection
                    if node_str_id in node_connections and port_name in node_connections[node_str_id]:
                        conn = node_connections[node_str_id][port_name]
                        from_id = node_id_map.get(conn.get("from_node"))
                        if from_id:
                            port["Record"] = {
                                "$id": str(ref_id_counter),
                                "From": from_id,
                                "To": node_id,
                                "FromPort": conn.get("from_port", "Out"),
                                "ToPort": port_name,
                                "IsValid": True,
                            }
                            ref_id_counter += 1

                    gaea_node["Ports"]["$values"].append(port)

                # Out port
                gaea_node["Ports"]["$values"].append(
                    {
                        "$id": str(ref_id_counter),
                        "Name": "Out",
                        "Type": "PrimaryOut",
                        "IsExporting": True,
                        "Parent": {"$ref": gaea_node["$id"]},
                    }
                )
                ref_id_counter += 1

            else:
                # Standard nodes have In and Out
                # In port
                port_in = {
                    "$id": str(ref_id_counter),
                    "Name": "In",
                    "Type": "PrimaryIn",
                    "IsExporting": True,
                    "Parent": {"$ref": gaea_node["$id"]},
                }
                ref_id_counter += 1

                # Check for connection
                if node_str_id in node_connections and "In" in node_connections[node_str_id]:
                    conn = node_connections[node_str_id]["In"]
                    from_id = node_id_map.get(conn.get("from_node"))
                    if from_id:
                        port_in["Record"] = {
                            "$id": str(ref_id_counter),
                            "From": from_id,
                            "To": node_id,
                            "FromPort": conn.get("from_port", "Out"),
                            "ToPort": "In",
                            "IsValid": True,
                        }
                        ref_id_counter += 1

                gaea_node["Ports"]["$values"].append(port_in)

                # Out port
                gaea_node["Ports"]["$values"].append(
                    {
                        "$id": str(ref_id_counter),
                        "Name": "Out",
                        "Type": "PrimaryOut",
                        "IsExporting": True,
                        "Parent": {"$ref": gaea_node["$id"]},
                    }
                )
                ref_id_counter += 1

            gaea_nodes[str(node_id)] = gaea_node

        # Create the full project structure with sequential IDs
        project = {
            "$id": str(ref_id_counter),
            "Assets": {
                "$id": str(ref_id_counter + 1),
                "$values": [
                    {
                        "$id": str(ref_id_counter + 2),
                        "Terrain": {
                            "$id": str(ref_id_counter + 3),
                            "Id": project_id,
                            "Metadata": {
                                "$id": str(ref_id_counter + 4),
                                "Name": project_name,
                                "Description": "Created by Gaea2 MCP Server",
                                "Version": "2.0.6.0",
                                "DateCreated": timestamp,
                                "DateLastBuilt": timestamp,
                                "DateLastSaved": timestamp,
                                "ModifiedVersion": "2.0.6.0",
                            },
                            "Nodes": {
                                "$id": str(ref_id_counter + 5),
                                **gaea_nodes,  # Add nodes directly as properties
                            },
                            "Groups": {"$id": str(ref_id_counter + 6)},
                            "Notes": {"$id": str(ref_id_counter + 7)},
                            "GraphTabs": {
                                "$id": str(ref_id_counter + 8),
                                "$values": [
                                    {
                                        "$id": str(ref_id_counter + 9),
                                        "Name": "Graph 1",
                                        "Color": "Brass",
                                        "ZoomFactor": 0.5,
                                        "ViewportLocation": {
                                            "$id": str(ref_id_counter + 10),
                                            "X": 25000.0,
                                            "Y": 26000.0,
                                        },
                                    }
                                ],
                            },
                            "Width": 5000.0,
                            "Height": 2500.0,
                            "Ratio": 0.5,
                        },
                    }
                ],
            },
            "Id": project_id[:8],  # Short version
            "Branch": 1,
            "Metadata": {
                "$id": str(ref_id_counter + 11),
                "Name": project_name,
                "Description": "Created by Gaea2 MCP Server",
                "Version": "2.0.6.0",
                "Owner": "",
                "DateCreated": timestamp,
                "DateLastBuilt": timestamp,
                "DateLastSaved": timestamp,
            },
            "Automation": {
                "$id": str(ref_id_counter + 12),
                "Bindings": {"$id": str(ref_id_counter + 13), "$values": []},
                "Variables": {"$id": str(ref_id_counter + 14)},
                "BoundProperties": {"$id": str(ref_id_counter + 15), "$values": []},
            },
            "BuildDefinition": {
                "$id": str(ref_id_counter + 16),
                "Destination": "<Builds>\\[Filename]\\[+++]",
                "Resolution": 2048,
                "BakeResolution": 2048,
                "TileResolution": 1024,
                "BucketResolution": 2048,
                "BucketCount": 1,
                "WorldResolution": 2048,
                "NumberOfTiles": 1,
                "TotalTiles": 1,
                "BucketSizeWithMargin": 3072,
                "EdgeBlending": 0.25,
                "EdgeSize": 512,
                "TileZeroIndex": True,
                "TilePattern": "",
                "OrganizeFiles": "NodeSubFolder",
                "Regions": {"$id": str(ref_id_counter + 17), "$values": []},
                "PostBuildScript": "",
            },
            "State": {
                "$id": str(ref_id_counter + 18),
                "BakeResolution": 2048,
                "PreviewResolution": 512,
                "SelectedNode": node_id_base if nodes else 100,
                "NodeBookmarks": {"$id": str(ref_id_counter + 19), "$values": []},
                "Viewport": {
                    "$id": str(ref_id_counter + 20),
                    "Camera": {"$id": str(ref_id_counter + 21)},
                    "RenderMode": "Realistic",
                    "SunAltitude": 33.0,
                    "SunAzimuth": 45.0,
                    "SunIntensity": 1.0,
                    "AmbientOcclusion": True,
                    "Shadows": True,
                    "AirDensity": 1.0,
                    "AmbientIntensity": 1.0,
                    "Exposure": 1.0,
                    "FogDensity": 0.2,
                    "GroundBrightness": 0.8,
                    "Haze": 1.0,
                    "Ozone": 1.0,
                },
                "LockedNode": None,
            },
        }

        return project

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

    async def create_gaea2_project(
        self,
        project_name: str,
        workflow: Dict[str, Any],
        output_path: Optional[str] = None,
        auto_validate: bool = True,
        save_to_disk: bool = True,
    ) -> Dict[str, Any]:
        """Create a Gaea2 project from workflow definition"""
        try:
            # Extract nodes and connections
            nodes = workflow.get("nodes", [])
            connections = workflow.get("connections", [])

            # Validate and fix workflow if requested
            if auto_validate:
                validation_result = await self.validate_and_fix_workflow(workflow, fix_errors=True, add_missing_nodes=True)
                if validation_result.get("success"):
                    # Use fixed workflow
                    workflow = validation_result.get("fixed_workflow", workflow)
                    nodes = workflow.get("nodes", [])
                    connections = workflow.get("connections", [])

            # Create project structure with sequential IDs
            project_structure = self._create_gaea2_project_structure(project_name, nodes, connections)

            # Save to disk if requested
            saved_path = None
            if save_to_disk and output_path:
                # Ensure .terrain extension
                if not output_path.endswith(".terrain"):
                    output_path += ".terrain"

                # Save as minified JSON with Unix line endings
                json_content = json.dumps(project_structure, separators=(",", ":"))

                # Write with Unix line endings
                with open(output_path, "wb") as f:
                    f.write(json_content.encode("utf-8"))
                    f.write(b"\n")  # Add final newline

                saved_path = output_path
                self.logger.info(f"Saved project to: {saved_path}")

            return {
                "success": True,
                "project_name": project_name,
                "node_count": len(nodes),
                "connection_count": len(connections),
                "saved_path": saved_path,
                "project_structure": project_structure if not save_to_disk else None,
            }

        except Exception as e:
            self.logger.error(f"Error creating project: {str(e)}")
            return {"success": False, "error": str(e)}

    async def run_gaea2_project(
        self,
        project_path: str,
        output_dir: Optional[str] = None,
        verbose: bool = True,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """Run a Gaea2 project using the CLI"""
        try:
            if not os.path.exists(project_path):
                return {
                    "success": False,
                    "error": f"Project file not found: {project_path}",
                }

            # Prepare command
            cmd = [str(self.gaea_path), "--Filename", str(project_path)]

            if output_dir:
                cmd.extend(["--OutputDirectory", str(output_dir)])

            if verbose:
                cmd.append("--verbose")

            # Run the command
            self.logger.info(f"Running Gaea2 CLI: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                return {
                    "success": False,
                    "error": f"Execution timed out after {timeout} seconds",
                }

            # Parse output
            output_str = stdout.decode("utf-8", errors="replace")
            error_str = stderr.decode("utf-8", errors="replace")

            # Parse verbose output
            parsed_output = self._parse_gaea_output(output_str)

            # Store in history
            execution_record = {
                "timestamp": datetime.now().isoformat(),
                "project_path": project_path,
                "success": process.returncode == 0,
                "returncode": process.returncode,
                "stdout": output_str,
                "stderr": error_str,
                "parsed": parsed_output,
                "command": cmd,
            }
            self.execution_history.append(execution_record)

            return {
                "success": process.returncode == 0,
                "returncode": process.returncode,
                "output": output_str,
                "error": error_str if process.returncode != 0 else None,
                "parsed": parsed_output,
                "execution_time": execution_record.get("execution_time"),
            }

        except Exception as e:
            self.logger.error(f"Error running project: {str(e)}")
            return {"success": False, "error": str(e)}

    async def validate_and_fix_workflow(
        self,
        workflow: Union[str, List[Dict[str, Any]], Dict[str, Any]],
        fix_errors: bool = True,
        validate_connections: bool = True,
        validate_properties: bool = True,
        add_missing_nodes: bool = True,
        optimize_workflow: bool = False,
    ) -> Dict[str, Any]:
        """Comprehensive workflow validation and fixing"""
        try:
            # Handle different input types
            if isinstance(workflow, str):
                # It's a file path
                with open(workflow, "r") as f:
                    data = json.load(f)
                    workflow = data.get("workflow", data)
            elif isinstance(workflow, dict):
                # It's already a workflow dict with nodes and connections
                pass
            elif isinstance(workflow, list):
                # It's just a list of nodes, wrap it
                workflow = {"nodes": workflow, "connections": []}

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
                # Different validators have different methods
                if hasattr(validator, "validate_workflow"):
                    is_valid, errors = validator.validate_workflow(workflow)
                elif hasattr(validator, "validate_project"):
                    # AccurateGaea2Validator uses validate_project
                    validation_result = validator.validate_project(workflow.get("nodes", []), workflow.get("connections", []))
                    is_valid = validation_result.get("valid", False)
                    errors = validation_result.get("errors", [])
                else:
                    # Fallback for other validators
                    is_valid = True
                    errors = []

                results["validation_results"][name] = {
                    "valid": is_valid,
                    "errors": errors,
                }
                if not is_valid:
                    all_valid = False

            # Apply fixes if requested
            if fix_errors and not all_valid:
                recovery = Gaea2ErrorRecovery()
                # Get nodes and connections from workflow
                nodes = workflow.get("nodes", [])
                connections = workflow.get("connections", [])

                # Apply fixes
                fixed_result = recovery.auto_fix_project(nodes, connections)
                if fixed_result.get("success"):
                    workflow["nodes"] = fixed_result.get("nodes", nodes)
                    workflow["connections"] = fixed_result.get("connections", connections)
                    results["fixes_applied"] = fixed_result.get("fixes", [])
                else:
                    results["fix_errors"] = fixed_result.get("message", "Failed to fix")

            # Add missing essential nodes
            if add_missing_nodes:
                # Check for essential nodes like Export and SatMap
                nodes = workflow.get("nodes", [])
                node_types = [node.get("type") for node in nodes]

                if "Export" not in node_types:
                    # Add Export node
                    export_node = {
                        "id": max([n.get("id", 0) for n in nodes] + [0]) + 1,
                        "type": "Export",
                        "name": "AutoExport",
                        "properties": {"format": "png", "enabled": True},
                        "position": {"x": 1000, "y": 0},
                    }
                    workflow["nodes"].append(export_node)
                    results.setdefault("added_nodes", []).append("Export")

                if "SatMap" not in node_types and any(t in node_types for t in ["Mountain", "Erosion", "Erosion2"]):
                    # Add SatMap for visualization
                    satmap_node = {
                        "id": max([n.get("id", 0) for n in nodes] + [0]) + 2,
                        "type": "SatMap",
                        "name": "AutoSatMap",
                        "properties": {},
                        "position": {"x": 800, "y": 0},
                    }
                    workflow["nodes"].append(satmap_node)
                    results.setdefault("added_nodes", []).append("SatMap")

            # Optimize if requested
            if optimize_workflow:
                # Generate optimization suggestions based on workflow
                suggestions = []
                for node in workflow.get("nodes", []):
                    if node.get("type") == "Erosion2" and node.get("properties", {}).get("iterations", 20) > 30:
                        suggestions.append(
                            {
                                "node": node.get("name", node.get("id")),
                                "suggestion": "Consider reducing iterations for better performance",
                            }
                        )
                    elif node.get("type") == "SatMap" and not node.get("properties", {}).get("quality"):
                        suggestions.append(
                            {
                                "node": node.get("name", node.get("id")),
                                "suggestion": "Set quality mode for better results",
                            }
                        )

                if suggestions:
                    results["optimization_suggestions"] = suggestions

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

    async def create_from_template(
        self,
        template_name: str,
        project_name: str,
        output_path: Optional[str] = None,
        customizations: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a Gaea2 project from a template"""
        try:
            # Check if template exists
            if template_name not in WORKFLOW_TEMPLATES:
                available = list(WORKFLOW_TEMPLATES.keys())
                return {
                    "success": False,
                    "error": f"Unknown template: {template_name}. Available templates: {', '.join(available)}",
                }

            # Create workflow from template
            nodes, connections = create_workflow_from_template(template_name)

            # Apply customizations if provided
            if customizations:
                # Apply customizations to nodes
                for node in nodes:
                    if node["id"] in customizations.get("node_overrides", {}):
                        node["properties"].update(customizations["node_overrides"][node["id"]])

            # Create the project using the existing create_gaea2_project method
            workflow = {"nodes": nodes, "connections": connections}

            result = await self.create_gaea2_project(
                project_name=project_name,
                workflow=workflow,
                output_path=output_path,
                auto_validate=True,
            )

            if result.get("success"):
                result["template_used"] = template_name
                result["message"] = f"Project created from template '{template_name}'"

            return result

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create from template: {str(e)}",
            }

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
                "create_gaea2_from_template": self.create_from_template,
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

    async def _analyze_workflow_patterns(
        self,
        workflow_or_directory: Union[str, Dict[str, Any]],
        include_suggestions: bool = True,
    ) -> Dict[str, Any]:
        """Analyze workflow patterns"""
        analyzer = Gaea2WorkflowAnalyzer()

        if isinstance(workflow_or_directory, str):
            if os.path.isdir(workflow_or_directory):
                results = analyzer.analyze_directory(workflow_or_directory)
            else:
                # Analyze single project file
                results = analyzer.analyze_project(workflow_or_directory)
        else:
            # Direct workflow dict - analyze it in memory
            workflow = workflow_or_directory
            # Extract nodes and connections
            nodes = workflow.get("nodes", [])
            connections = workflow.get("connections", [])

            # Create a temporary analysis result
            results = {
                "node_count": len(nodes),
                "connection_count": len(connections),
                "node_types": list(set(node.get("type", "Unknown") for node in nodes)),
                "complexity": len(connections) / max(len(nodes), 1),
                "recommendations": analyzer.get_recommendations([node.get("type") for node in nodes]),
            }

        return {"success": True, "analysis": results}

    async def _suggest_nodes(self, current_nodes: List[str], context: Optional[str] = None, limit: int = 5) -> Dict[str, Any]:
        """Get node suggestions"""
        # Get suggestions from knowledge graph
        all_suggestions = knowledge_graph.get_suggested_next_nodes(current_nodes)

        # Sort by score and limit
        suggestions = [node for node, score in all_suggestions[:limit]]

        # Add context-based filtering if provided
        if context:
            # Simple context filtering based on keywords
            context_lower = context.lower()
            if "realistic" in context_lower or "erosion" in context_lower:
                # Prioritize erosion and detail nodes
                priority_nodes = ["Erosion2", "SatMap", "Texture", "Details"]
                suggestions = [n for n in suggestions if n in priority_nodes] + [
                    n for n in suggestions if n not in priority_nodes
                ]

        return {"success": True, "suggestions": suggestions[:limit]}

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

        # Optimize based on mode
        optimized = {
            "nodes": workflow.get("nodes", []),
            "connections": workflow.get("connections", []),
        }

        for node in optimized["nodes"]:
            if "properties" not in node:
                continue

            node_type = node.get("type", "")
            props = node["properties"]

            if optimization_mode == "performance":
                # Reduce quality settings for better performance
                if node_type == "Erosion2":
                    props["iterations"] = min(props.get("iterations", 20), 10)
                    props["detail"] = min(props.get("detail", 0.5), 0.3)
                elif node_type == "Terrace":
                    props["levels"] = min(props.get("levels", 16), 8)
                elif node_type == "SatMap":
                    props["quality"] = "Fast"

            elif optimization_mode == "quality":
                # Increase quality settings
                if node_type == "Erosion2":
                    props["iterations"] = max(props.get("iterations", 20), 30)
                    props["detail"] = max(props.get("detail", 0.5), 0.8)
                elif node_type == "Terrace":
                    props["levels"] = max(props.get("levels", 16), 32)
                elif node_type == "SatMap":
                    props["quality"] = "High"

            else:  # balanced
                # Moderate settings
                if node_type == "Erosion2":
                    props["iterations"] = 20
                    props["detail"] = 0.5
                elif node_type == "Terrace":
                    props["levels"] = 16

        return {
            "success": True,
            "optimized_workflow": optimized,
            "mode": optimization_mode,
        }

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
