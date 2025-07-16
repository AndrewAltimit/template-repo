#!/usr/bin/env python3
"""
MCP Server - Model Context Protocol Server
Provides various tools for development, AI assistance, and content creation
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import mcp.server.stdio
import mcp.types as types
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

try:
    from gaea2_knowledge_graph import enhance_workflow_with_knowledge, knowledge_graph
    from gaea2_schema_v2 import (
        VALID_NODE_TYPES,
        WORKFLOW_TEMPLATES,
        apply_default_properties,
        create_workflow_from_template,
        validate_gaea2_project,
    )
except ImportError:
    # If running as a module
    from tools.mcp.gaea2_knowledge_graph import enhance_workflow_with_knowledge, knowledge_graph
    from tools.mcp.gaea2_schema_v2 import (
        VALID_NODE_TYPES,
        WORKFLOW_TEMPLATES,
        apply_default_properties,
        create_workflow_from_template,
        validate_gaea2_project,
    )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="MCP Server", version="1.0.0")


class ToolRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any]


class ToolResponse(BaseModel):
    success: bool
    result: Any
    error: Optional[str] = None


class MCPTools:
    """Collection of MCP tools"""

    @staticmethod
    def _ensure_property_types(node_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure properties have the correct data types based on node definitions"""
        from tools.mcp.gaea2_schema_v2 import COMMON_NODE_PROPERTIES, NODE_PROPERTY_DEFINITIONS

        corrected = properties.copy()

        # Get property definitions for this node type
        prop_defs = {}
        if node_type in NODE_PROPERTY_DEFINITIONS:
            prop_defs.update(NODE_PROPERTY_DEFINITIONS[node_type])
        prop_defs.update(COMMON_NODE_PROPERTIES)

        # Correct the types
        for prop_name, prop_value in corrected.items():
            if prop_name in prop_defs:
                expected_type = prop_defs[prop_name].get("type", "float")

                if expected_type == "int" and isinstance(prop_value, float):
                    corrected[prop_name] = int(round(prop_value))
                elif expected_type == "float" and isinstance(prop_value, int):
                    corrected[prop_name] = float(prop_value)
                elif expected_type == "bool" and not isinstance(prop_value, bool):
                    corrected[prop_name] = bool(prop_value)

        return corrected

    @staticmethod
    async def format_check(path: str, language: str = "python") -> Dict[str, Any]:
        """Check code formatting"""
        formatters = {
            "python": ["black", "--check", path],
            "javascript": ["prettier", "--check", path],
            "typescript": ["prettier", "--check", path],
            "go": ["gofmt", "-l", path],
            "rust": ["rustfmt", "--check", path],
        }

        if language not in formatters:
            return {"error": f"Unsupported language: {language}"}

        try:
            result = subprocess.run(formatters[language], capture_output=True, text=True)
            return {
                "formatted": result.returncode == 0,
                "output": result.stdout or result.stderr,
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def lint(path: str, config: Optional[str] = None) -> Dict[str, Any]:
        """Run code linting"""
        cmd = ["flake8", path]
        if config:
            cmd.extend(["--config", config])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {
                "success": result.returncode == 0,
                "issues": result.stdout.splitlines() if result.stdout else [],
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def create_manim_animation(script: str, output_format: str = "mp4") -> Dict[str, Any]:
        """Create Manim animation from script"""
        try:
            # Create temporary file for script
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(script)
                script_path = f.name

            # Output path
            output_dir = "/app/output/manim"
            os.makedirs(output_dir, exist_ok=True)

            # Run Manim
            cmd = [
                "manim",
                "-qm",
                "-f",
                output_format,
                "--output_dir",
                output_dir,
                script_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            # Clean up
            os.unlink(script_path)

            if result.returncode == 0:
                # Find output file
                output_files = [f for f in os.listdir(output_dir) if f.endswith(f".{output_format}")]
                if output_files:
                    return {
                        "success": True,
                        "output_path": os.path.join(output_dir, output_files[0]),
                        "format": output_format,
                    }

            return {
                "success": False,
                "error": result.stderr or "Animation creation failed",
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def compile_latex(content: str, format: str = "pdf") -> Dict[str, Any]:
        """Compile LaTeX document"""
        try:
            # Create temporary directory
            with tempfile.TemporaryDirectory() as tmpdir:
                # Write LaTeX file
                tex_file = os.path.join(tmpdir, "document.tex")
                with open(tex_file, "w") as f:
                    f.write(content)

                # Compile based on format
                if format == "pdf":
                    cmd = ["pdflatex", "-interaction=nonstopmode", tex_file]
                elif format == "dvi":
                    cmd = ["latex", "-interaction=nonstopmode", tex_file]
                elif format == "ps":
                    cmd = ["latex", "-interaction=nonstopmode", tex_file]
                else:
                    return {"error": f"Unsupported format: {format}"}

                # Run compilation (twice for references)
                for _ in range(2):
                    result = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True)

                # Convert DVI to PS if needed
                if format == "ps" and result.returncode == 0:
                    dvi_file = os.path.join(tmpdir, "document.dvi")
                    ps_file = os.path.join(tmpdir, "document.ps")
                    subprocess.run(["dvips", dvi_file, "-o", ps_file])

                # Check for output
                output_file = os.path.join(tmpdir, f"document.{format}")
                if os.path.exists(output_file):
                    # Copy to output directory
                    output_dir = "/app/output/latex"
                    os.makedirs(output_dir, exist_ok=True)

                    import shutil

                    output_path = os.path.join(output_dir, f"document_{os.getpid()}.{format}")
                    shutil.copy(output_file, output_path)

                    return {
                        "success": True,
                        "output_path": output_path,
                        "format": format,
                    }

                return {
                    "success": False,
                    "error": result.stderr or "Compilation failed",
                }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def create_gaea2_project(
        project_name: str,
        nodes: List[Dict[str, Any]],
        connections: Optional[List[Dict[str, Any]]] = None,
        resolution: int = 2048,
        world_size: int = 5000,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Gaea 2 project file with nodes and connections"""
        try:
            # Initialize project structure
            project_id = str(uuid.uuid4())
            terrain_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")

            # Create the base project structure
            project = {
                "$id": "1",
                "Assets": {
                    "$id": "2",
                    "$values": [
                        {
                            "$id": "3",
                            "Terrain": {
                                "$id": "4",
                                "Id": terrain_id,
                                "Metadata": {
                                    "$id": "5",
                                    "Name": project_name,
                                    "Description": (f"Generated by MCP Server on {timestamp}"),
                                    "Version": "2.0",
                                    "DateCreated": timestamp,
                                    "DateLastBuilt": timestamp,
                                    "DateLastSaved": timestamp,
                                },
                                "Nodes": {"$id": "6"},
                                "Groups": {"$id": "221"},
                                "Notes": {"$id": "222"},
                                "GraphTabs": {
                                    "$id": "223",
                                    "$values": [
                                        {
                                            "$id": "224",
                                            "Name": "Graph 1",
                                            "Color": "Brass",
                                            "ZoomFactor": 0.5,
                                            "ViewportLocation": {
                                                "$id": "225",
                                                "X": 25000.0,
                                                "Y": 25000.0,
                                            },
                                        }
                                    ],
                                },
                                "Width": float(world_size),
                                "Height": float(world_size / 2),
                                "Ratio": 0.5,
                            },
                            "Automation": {
                                "$id": "226",
                                "Bindings": {"$id": "227", "$values": []},
                                "Variables": {"$id": "228"},
                                "BoundProperties": {"$id": "229", "$values": []},
                            },
                            "BuildDefinition": {
                                "$id": "230",
                                "Destination": "<Builds>\\[Filename]\\[+++]",
                                "Resolution": resolution,
                                "BakeResolution": resolution,
                                "TileResolution": 1024,
                                "BucketResolution": resolution,
                                "BucketCount": 1,
                                "WorldResolution": resolution,
                                "NumberOfTiles": 3,
                                "TotalTiles": 9,
                                "BucketSizeWithMargin": 3072,
                                "EdgeBlending": 0.25,
                                "EdgeSize": 512,
                                "TileZeroIndex": True,
                                "TilePattern": "_y%Y%_x%X%",
                                "OrganizeFiles": "NodeSubFolder",
                                "Regions": {"$id": "231", "$values": []},
                                "PostBuildScript": "",
                                "OpenFolder": True,
                            },
                            "State": {
                                "$id": "232",
                                "BakeResolution": resolution,
                                "PreviewResolution": resolution * 2,
                                "SelectedNode": None,
                                "NodeBookmarks": {"$id": "233", "$values": []},
                                "Viewport": {
                                    "$id": "234",
                                    "Camera": {"$id": "235"},
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
                            },
                        }
                    ],
                },
                "Id": project_id[:8],
                "Branch": 1,
                "Metadata": {
                    "$id": "236",
                    "Name": project_name,
                    "Description": "",
                    "Version": "1.0",
                    "Owner": "",
                    "DateCreated": timestamp,
                    "DateLastBuilt": timestamp,
                    "DateLastSaved": timestamp,
                },
            }

            # Process nodes
            nodes_dict = {}
            node_id_counter = 100
            ref_id_counter = 7

            for node_data in nodes:
                node_id = node_data.get("id", node_id_counter)
                node_type = node_data.get("type", "Mountain")
                node_name = node_data.get("name", node_type)
                position = node_data.get("position", {"x": 25000, "y": 25000})
                properties = node_data.get("properties", {})

                # Validate node type
                if node_type not in VALID_NODE_TYPES:
                    logger.warning(f"Unknown node type: {node_type}")
                    # Continue anyway to allow experimentation

                # Create node structure
                node = {
                    "$id": str(ref_id_counter),
                    "$type": f"QuadSpinner.Gaea.Nodes.{node_type}, Gaea.Nodes",
                    "Id": node_id,
                    "Name": node_name,
                    "Position": {
                        "$id": str(ref_id_counter + 1),
                        "X": float(position["x"]),
                        "Y": float(position["y"]),
                    },
                    "Ports": {
                        "$id": str(ref_id_counter + 2),
                        "$values": [
                            {
                                "$id": str(ref_id_counter + 3),
                                "Name": "In",
                                "Type": "PrimaryIn",
                                "IsExporting": True,
                                "Parent": {"$ref": str(ref_id_counter)},
                            },
                            {
                                "$id": str(ref_id_counter + 4),
                                "Name": "Out",
                                "Type": "PrimaryOut",
                                "IsExporting": True,
                                "Parent": {"$ref": str(ref_id_counter)},
                            },
                        ],
                    },
                    "Modifiers": {"$id": str(ref_id_counter + 5), "$values": []},
                    "SnapIns": {"$id": str(ref_id_counter + 6), "$values": []},
                }

                # Apply default properties first
                default_props = apply_default_properties(node_type, properties)

                # Ensure correct data types
                corrected_props = MCPTools._ensure_property_types(node_type, default_props)

                # Add all properties (user-specified override defaults)
                for prop, value in corrected_props.items():
                    if prop not in node:
                        node[prop] = value

                # Add user-specified properties (these override defaults)
                user_props = MCPTools._ensure_property_types(node_type, properties)
                for prop, value in user_props.items():
                    node[prop] = value

                nodes_dict[str(node_id)] = node
                node_id_counter += 1
                ref_id_counter += 10

            # Add connections
            if connections:
                for conn in connections:
                    from_id = str(conn["from_node"])
                    to_id = str(conn["to_node"])
                    from_port = conn.get("from_port", "Out")
                    to_port = conn.get("to_port", "In")

                    if from_id in nodes_dict and to_id in nodes_dict:
                        # Find the port in the target node
                        target_node = nodes_dict[to_id]
                        for port in target_node["Ports"]["$values"]:
                            if port["Name"] == to_port:
                                port["Type"] = "PrimaryIn, Required"
                                port["Record"] = {
                                    "$id": str(ref_id_counter),
                                    "From": int(from_id),
                                    "To": int(to_id),
                                    "FromPort": from_port,
                                    "ToPort": to_port,
                                    "IsValid": True,
                                }
                                ref_id_counter += 1
                                break

            # Assign nodes to the project
            project["Assets"]["$values"][0]["Terrain"]["Nodes"] = nodes_dict

            # Set selected node if any
            if nodes:
                project["Assets"]["$values"][0]["State"]["SelectedNode"] = nodes[0].get("id", 100)

            # Save the project file
            if output_path is None:
                output_dir = "/app/output/gaea2"
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, f"{project_name}_{os.getpid()}.terrain")

            with open(output_path, "w") as f:
                json.dump(project, f, separators=(",", ":"))

            return {
                "success": True,
                "output_path": output_path,
                "project_id": project_id,
                "terrain_id": terrain_id,
                "node_count": len(nodes),
                "connection_count": len(connections) if connections else 0,
            }

        except Exception as e:
            return {"error": str(e), "success": False}

    @staticmethod
    async def validate_gaea2_project(
        project_file: Optional[str] = None,
        project_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Validate a Gaea 2 project file or data structure"""
        try:
            # Load project data if file path provided
            if project_file and not project_data:
                if not os.path.exists(project_file):
                    return {
                        "success": False,
                        "error": f"File not found: {project_file}",
                        "valid": False,
                    }

                with open(project_file, "r") as f:
                    project_data = json.load(f)

            elif not project_data:
                return {
                    "success": False,
                    "error": "Either project_file or project_data must be provided",
                    "valid": False,
                }

            # Validate the project
            validation_result = validate_gaea2_project(project_data)

            # Add success flag
            validation_result["success"] = True
            validation_result["file"] = project_file if project_file else None

            # Add summary
            validation_result["summary"] = {
                "valid": validation_result["valid"],
                "error_count": len(validation_result["errors"]),
                "warning_count": len(validation_result["warnings"]),
                "node_count": validation_result.get("node_count", 0),
                "connection_count": validation_result.get("connection_count", 0),
            }

            return validation_result

        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON: {str(e)}",
                "valid": False,
                "errors": [f"JSON parsing error: {str(e)}"],
                "warnings": [],
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "valid": False,
                "errors": [f"Validation error: {str(e)}"],
                "warnings": [],
            }

    @staticmethod
    async def create_gaea2_from_template(
        template_name: str,
        project_name: Optional[str] = None,
        start_position: Optional[Dict[str, float]] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a Gaea 2 project from a workflow template"""
        try:
            # Validate template name
            if template_name not in WORKFLOW_TEMPLATES:
                return {
                    "success": False,
                    "error": f"Unknown template: {template_name}",
                    "available_templates": list(WORKFLOW_TEMPLATES.keys()),
                }

            # Set defaults
            if project_name is None:
                project_name = f"{template_name.replace('_', ' ').title()} Project"

            if start_position is None:
                start_position = {"x": 25000, "y": 26000}

            # Create nodes and connections from template
            nodes, connections = create_workflow_from_template(template_name, (start_position["x"], start_position["y"]))

            # Create the project using the existing create_gaea2_project tool
            result = await MCPTools.create_gaea2_project(
                project_name=project_name,
                nodes=nodes,
                connections=connections,
                output_path=output_path,
            )

            # Add template info to result
            if result.get("success"):
                result["template_used"] = template_name
                result["template_description"] = {
                    "basic_terrain": "Simple terrain with erosion and texturing",
                    "detailed_mountain": "Advanced mountain with dual peaks, rivers, and snow",
                    "volcanic_terrain": "Volcanic landscape with thermal weathering",
                    "desert_canyon": "Desert canyon with rock stratification and sand",
                }.get(template_name, "Custom terrain template")

            return result

        except Exception as e:
            return {"error": str(e), "success": False}

    @staticmethod
    async def list_gaea2_templates() -> Dict[str, Any]:
        """List available Gaea 2 workflow templates"""
        templates = {}

        for name, workflow in WORKFLOW_TEMPLATES.items():
            templates[name] = {
                "name": name.replace("_", " ").title(),
                "node_count": len(workflow),
                "nodes": [{"type": node["type"], "name": node["name"]} for node in workflow],
                "description": {
                    "basic_terrain": (
                        "Simple terrain with erosion and texturing. " "Ideal for beginners and quick prototypes."
                    ),
                    "detailed_mountain": (
                        "Advanced mountain terrain with dual peaks, erosion, " "rivers, and snow caps. Professional quality."
                    ),
                    "volcanic_terrain": (
                        "Volcanic landscape combining volcano and island with " "lava erosion and thermal weathering."
                    ),
                    "desert_canyon": (
                        "Desert canyon with stratified rock layers, terraces, " "wind erosion, and sand accumulation."
                    ),
                }.get(name, "Custom terrain workflow template"),
            }

        return {
            "success": True,
            "templates": templates,
            "total_count": len(templates),
        }

    @staticmethod
    async def analyze_gaea2_workflow(
        nodes: List[Dict[str, Any]], connections: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Analyze a Gaea 2 workflow using the knowledge graph for validation and suggestions"""
        try:
            # Enhance workflow with knowledge graph insights
            result = enhance_workflow_with_knowledge(nodes, connections or [])

            # Add workflow validation from knowledge graph
            node_names = [node.get("name", node.get("type", "Unknown")) for node in nodes]
            connection_pairs = []
            if connections:
                connection_pairs = [(c.get("from_node", ""), c.get("to_node", "")) for c in connections]

            kg_validation = knowledge_graph.validate_workflow(node_names, connection_pairs)

            # Find similar patterns
            similar_patterns = knowledge_graph.find_similar_patterns(node_names)

            # Get suggested next nodes
            next_nodes = knowledge_graph.get_suggested_next_nodes(node_names)

            return {
                "success": True,
                "analysis": result,
                "validation": kg_validation,
                "similar_patterns": [
                    {"name": p.name, "description": p.description, "tags": p.tags} for p in similar_patterns[:3]
                ],
                "suggested_next_nodes": [
                    {
                        "node": node,
                        "confidence": confidence,
                        "reason": "Based on common workflow patterns",
                    }
                    for node, confidence in next_nodes[:5]
                ],
                "summary": {
                    "total_issues": len(kg_validation.get("issues", [])),
                    "total_warnings": len(kg_validation.get("warnings", [])),
                    "total_suggestions": len(kg_validation.get("suggestions", []))
                    + len(result.get("property_suggestions", [])),
                    "workflow_valid": kg_validation.get("valid", True),
                },
            }

        except Exception as e:
            return {"error": str(e), "success": False}

    @staticmethod
    async def suggest_gaea2_nodes(current_nodes: List[str], context: Optional[str] = None) -> Dict[str, Any]:
        """Get intelligent node suggestions based on current workflow and knowledge graph"""
        try:
            # Get suggestions from knowledge graph
            suggestions = knowledge_graph.get_suggested_next_nodes(current_nodes)

            # Get relationships for context
            relationships = []
            for node in current_nodes[:3]:  # Limit to avoid too much data
                rels = knowledge_graph.get_relationships(node)
                for rel in rels[:5]:  # Limit relationships per node
                    relationships.append(
                        {
                            "from": rel.from_node,
                            "to": rel.to_node,
                            "type": rel.relation_type.value,
                            "strength": rel.strength,
                            "description": rel.description,
                        }
                    )

            # Find patterns containing current nodes
            matching_patterns = []
            for pattern in knowledge_graph.patterns:
                if any(node in pattern.nodes for node in current_nodes):
                    match_count = sum(1 for node in current_nodes if node in pattern.nodes)
                    matching_patterns.append(
                        {
                            "pattern": pattern.name,
                            "description": pattern.description,
                            "match_strength": match_count / len(current_nodes),
                            "missing_nodes": [n for n in pattern.nodes if n not in current_nodes],
                        }
                    )

            # Sort patterns by match strength
            matching_patterns.sort(key=lambda x: x["match_strength"], reverse=True)

            return {
                "success": True,
                "current_nodes": current_nodes,
                "suggestions": [
                    {
                        "node": node,
                        "confidence": confidence,
                        "category": knowledge_graph.node_categories.get(node, "unknown"),
                    }
                    for node, confidence in suggestions
                ],
                "relationships": relationships[:10],  # Limit total relationships
                "matching_patterns": matching_patterns[:5],
                "context_applied": context is not None,
            }

        except Exception as e:
            return {"error": str(e), "success": False}

    @staticmethod
    async def optimize_gaea2_properties(nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Optimize node properties based on knowledge graph constraints and relationships"""
        try:
            # Get property suggestions
            suggestions = knowledge_graph.suggest_property_values(nodes)

            # Apply suggestions to create optimized nodes
            optimized_nodes = []
            applied_suggestions = []

            # Create lookup for easy access
            node_map = {node["name"]: node.copy() for node in nodes}

            for suggestion in suggestions:
                node_name = suggestion["node"]
                if node_name in node_map:
                    # Apply suggestion
                    if "properties" not in node_map[node_name]:
                        node_map[node_name]["properties"] = {}

                    old_value = node_map[node_name]["properties"].get(suggestion["property"], "not set")
                    node_map[node_name]["properties"][suggestion["property"]] = suggestion["suggested_value"]

                    applied_suggestions.append(
                        {
                            "node": node_name,
                            "property": suggestion["property"],
                            "old_value": old_value,
                            "new_value": suggestion["suggested_value"],
                            "reason": suggestion["reason"],
                        }
                    )

            # Convert back to list
            optimized_nodes = list(node_map.values())

            return {
                "success": True,
                "optimized_nodes": optimized_nodes,
                "applied_suggestions": applied_suggestions,
                "suggestion_count": len(applied_suggestions),
                "summary": {
                    "nodes_modified": len(set(s["node"] for s in applied_suggestions)),
                    "properties_adjusted": len(applied_suggestions),
                },
            }

        except Exception as e:
            return {"error": str(e), "success": False}


# Tool registry
TOOLS = {
    "format_check": MCPTools.format_check,
    "lint": MCPTools.lint,
    "create_manim_animation": MCPTools.create_manim_animation,
    "compile_latex": MCPTools.compile_latex,
    "create_gaea2_project": MCPTools.create_gaea2_project,
    "validate_gaea2_project": MCPTools.validate_gaea2_project,
    "create_gaea2_from_template": MCPTools.create_gaea2_from_template,
    "list_gaea2_templates": MCPTools.list_gaea2_templates,
    "analyze_gaea2_workflow": MCPTools.analyze_gaea2_workflow,
    "suggest_gaea2_nodes": MCPTools.suggest_gaea2_nodes,
    "optimize_gaea2_properties": MCPTools.optimize_gaea2_properties,
}


@app.get("/")
async def root():
    """Root endpoint"""
    return {"name": "MCP Server", "version": "1.0.0", "tools": list(TOOLS.keys())}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/tools/execute", response_model=ToolResponse)
async def execute_tool(request: ToolRequest):
    """Execute a tool"""
    if request.tool not in TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool not found: {request.tool}")

    try:
        result = await TOOLS[request.tool](**request.arguments)
        return ToolResponse(success=True, result=result)
    except Exception as e:
        logger.error(f"Tool execution failed: {str(e)}")
        return ToolResponse(success=False, result=None, error=str(e))


@app.get("/tools")
async def list_tools():
    """List available tools"""
    tools_info = {}
    for name, func in TOOLS.items():
        tools_info[name] = {
            "name": name,
            "description": func.__doc__.strip() if func.__doc__ else "No description",
            "parameters": {},  # Could be enhanced with parameter inspection
        }
    return tools_info


async def serve_mcp():
    """Serve MCP protocol"""
    server = mcp.server.Server("mcp-server")

    @server.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        tools = []
        for name, func in TOOLS.items():
            tools.append(
                types.Tool(
                    name=name,
                    description=(func.__doc__.strip() if func.__doc__ else "No description"),
                    inputSchema={
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                )
            )
        return tools

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
        if name not in TOOLS:
            return [types.TextContent(type="text", text=f"Tool not found: {name}")]

        try:
            result = await TOOLS[name](**arguments)
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error: {str(e)}")]

    # Run the server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import sys

    if "--mcp" in sys.argv:
        # Run as MCP server
        asyncio.run(serve_mcp())
    else:
        # Run as HTTP API
        import uvicorn

        uvicorn.run(
            app,
            host=os.getenv("MCP_SERVER_HOST", "0.0.0.0"),
            port=int(os.getenv("MCP_SERVER_PORT", "8000")),
        )
