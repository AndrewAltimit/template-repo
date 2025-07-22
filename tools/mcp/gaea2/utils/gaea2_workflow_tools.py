"""Gaea 2 Workflow Management and Optimization Tools"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional


class Gaea2WorkflowTools:
    """Advanced workflow management tools for Gaea 2 projects"""

    @staticmethod
    async def analyze_workflow_patterns(project_file: str) -> Dict[str, Any]:
        """
        Analyze workflow patterns in a Gaea project and suggest optimizations

        Returns:
        - Pattern analysis including node types, connections, and complexity
        - Performance bottlenecks
        - Optimization suggestions
        """
        try:
            with open(project_file, "r") as f:
                project = json.load(f)

            terrain = project["Assets"]["$values"][0]["Terrain"]
            nodes = terrain.get("Nodes", {})

            # Analyze node types and their frequencies
            node_types: Dict[str, int] = {}
            node_connections: Dict[str, Dict[str, Any]] = {}
            erosion_chains: List[List[str]] = []
            export_nodes: List[Dict[str, Any]] = []

            for node_id, node in nodes.items():
                node_type = node.get("$type", "").split(".")[-2]
                node_types[node_type] = node_types.get(node_type, 0) + 1

                # Track connections
                node_connections[node_id] = {
                    "inputs": [],
                    "outputs": [],
                    "type": node_type,
                }

                # Identify special nodes
                if node_type in ["Export", "Unity", "Unreal"]:
                    export_nodes.append({"id": node_id, "type": node_type, "name": node.get("Name", "")})

                # Analyze ports for connections
                ports = node.get("Ports", {}).get("$values", [])
                for port in ports:
                    if port.get("Record"):
                        record = port["Record"]
                        if port["Name"] in ["In", "Input"]:
                            node_connections[node_id]["inputs"].append(
                                {
                                    "from": str(record["From"]),
                                    "port": record["FromPort"],
                                }
                            )
                        else:
                            # Track as output in the source node
                            from_id = str(record["From"])
                            if from_id in node_connections:
                                node_connections[from_id]["outputs"].append({"to": node_id, "port": port["Name"]})

            # Identify erosion chains
            for node_id, connections in node_connections.items():
                if connections["type"] in ["Erosion", "Erosion2", "Wizard"]:
                    chain = [node_id]
                    current = node_id

                    # Follow the chain downstream
                    while True:
                        outputs = node_connections.get(current, {}).get("outputs", [])
                        next_erosion = None

                        for output in outputs:
                            to_node = output["to"]
                            if node_connections.get(to_node, {}).get("type") in [
                                "Erosion",
                                "Erosion2",
                                "Wizard",
                            ]:
                                next_erosion = to_node
                                break

                        if next_erosion:
                            chain.append(next_erosion)
                            current = next_erosion
                        else:
                            break

                    if len(chain) > 1:
                        erosion_chains.append(chain)

            # Calculate workflow complexity
            total_connections = sum(len(conn["inputs"]) + len(conn["outputs"]) for conn in node_connections.values()) // 2

            complexity_score = len(nodes) * 1.0 + total_connections * 0.5 + len(erosion_chains) * 2.0

            # Generate optimization suggestions
            suggestions = []

            # Check for excessive erosion chains
            for chain in erosion_chains:
                if len(chain) > 3:
                    suggestions.append(
                        {
                            "type": "performance",
                            "severity": "high",
                            "message": (
                                f"Long erosion chain detected ({len(chain)} nodes). "
                                "Consider consolidating erosion operations."
                            ),
                            "nodes": chain,
                        }
                    )

            # Check for disconnected nodes
            for node_id, connections in node_connections.items():
                if not connections["inputs"] and not connections["outputs"]:
                    suggestions.append(
                        {
                            "type": "workflow",
                            "severity": "medium",
                            "message": f"Disconnected node found: {connections['type']} (ID: {node_id})",
                            "nodes": [node_id],
                        }
                    )

            # Check for missing export nodes
            if not export_nodes:
                suggestions.append(
                    {
                        "type": "workflow",
                        "severity": "high",
                        "message": "No export nodes found. Add Export or Unity nodes to save outputs.",
                        "nodes": [],
                    }
                )

            # Analyze node distribution
            primary_nodes = [t for t, c in node_types.items() if t in ["Mountain", "Ridge", "Dunes", "Canyon"]]
            if len(primary_nodes) > 5:
                suggestions.append(
                    {
                        "type": "complexity",
                        "severity": "medium",
                        "message": (
                            f"Multiple primary terrain nodes detected ({len(primary_nodes)}). " "Consider using Combine nodes."
                        ),
                        "nodes": [],
                    }
                )

            return {
                "success": True,
                "analysis": {
                    "node_count": len(nodes),
                    "connection_count": total_connections,
                    "node_types": node_types,
                    "erosion_chains": erosion_chains,
                    "export_nodes": export_nodes,
                    "complexity_score": complexity_score,
                    "complexity_level": (
                        "simple" if complexity_score < 20 else "moderate" if complexity_score < 50 else "complex"
                    ),
                },
                "suggestions": suggestions,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    async def optimize_build_settings(project_file: str, target_use_case: str = "game") -> Dict[str, Any]:
        """
        Suggest optimal build settings based on target use case

        Target use cases:
        - "game": Optimized for game engines (tiled, normal maps, lower res)
        - "film": High quality for cinematics (high res, 32-bit)
        - "visualization": Balanced for real-time viz
        - "prototype": Fast iteration (low res, minimal outputs)
        """

        presets: Dict[str, Dict[str, Any]] = {
            "game": {
                "Resolution": 2048,
                "TileResolution": 1024,
                "NumberOfTiles": 2,
                "EdgeBlending": 0.25,
                "export_formats": {
                    "heightmap": "RAW16",
                    "textures": "PNG",
                    "normals": "PNG",
                    "masks": "PNG8",
                },
                "suggestions": [
                    "Use tiling for large worlds",
                    "Export normal maps for detail",
                    "Consider LOD exports at multiple resolutions",
                    "Use compressed formats for textures",
                ],
            },
            "film": {
                "Resolution": 8192,
                "TileResolution": 2048,
                "NumberOfTiles": 4,
                "EdgeBlending": 0.5,
                "export_formats": {
                    "heightmap": "EXR",
                    "textures": "EXR",
                    "normals": "EXR",
                    "masks": "EXR",
                },
                "suggestions": [
                    "Use 32-bit formats for maximum precision",
                    "Enable all output maps",
                    "Consider displacement maps for close-ups",
                    "Export at maximum resolution",
                ],
            },
            "visualization": {
                "Resolution": 4096,
                "TileResolution": 1024,
                "NumberOfTiles": 2,
                "EdgeBlending": 0.33,
                "export_formats": {
                    "heightmap": "PNG16",
                    "textures": "PNG",
                    "normals": "PNG",
                    "masks": "PNG",
                },
                "suggestions": [
                    "Balance quality with performance",
                    "Use PNG for good compression",
                    "Export key masks for runtime effects",
                    "Consider real-time friendly resolutions",
                ],
            },
            "prototype": {
                "Resolution": 1024,
                "TileResolution": 512,
                "NumberOfTiles": 1,
                "EdgeBlending": 0.1,
                "export_formats": {
                    "heightmap": "PNG",
                    "textures": "PNG8",
                    "normals": None,
                    "masks": None,
                },
                "suggestions": [
                    "Use low resolution for fast iteration",
                    "Minimal exports for quick testing",
                    "Disable unnecessary outputs",
                    "Focus on terrain shape only",
                ],
            },
        }

        preset = presets.get(target_use_case, presets["game"])

        # Generate build configuration
        resolution = int(preset["Resolution"])
        tile_resolution = int(preset["TileResolution"])
        num_tiles = int(preset["NumberOfTiles"])
        edge_blending = float(preset["EdgeBlending"])

        build_config = {
            "Type": "Standard",
            "Resolution": resolution,
            "BakeResolution": resolution,
            "TileResolution": tile_resolution,
            "NumberOfTiles": num_tiles,
            "TotalTiles": num_tiles**2,
            "EdgeBlending": edge_blending,
            "EdgeSize": int(tile_resolution * edge_blending),
            "TilePattern": "_y%Y%_x%X%" if num_tiles > 1 else "",
            "OrganizeFiles": "NodeSubFolder",
            "export_formats": preset["export_formats"],
        }

        return {
            "success": True,
            "target_use_case": target_use_case,
            "build_config": build_config,
            "suggestions": preset["suggestions"],
            "estimated_memory": {
                "heightmap": f"{(resolution ** 2 * 4) / (1024 ** 3):.2f} GB",
                "per_texture": f"{(resolution ** 2 * 3) / (1024 ** 3):.2f} GB",
            },
        }

    @staticmethod
    async def batch_process_projects(
        project_files: List[str],
        common_settings: Dict[str, Any],
        output_directory: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process multiple Gaea projects with common settings

        Common settings can include:
        - Resolution overrides
        - Export format changes
        - Build configuration
        - Node property updates
        """
        results = []

        for project_file in project_files:
            try:
                # Load project
                with open(project_file, "r") as f:
                    project = json.load(f)

                project_name = os.path.basename(project_file).replace(".terrain", "")

                # Apply resolution settings
                if "resolution" in common_settings:
                    build_def = project["Assets"]["$values"][0].get("BuildDefinition", {})
                    build_def["Resolution"] = common_settings["resolution"]
                    build_def["BakeResolution"] = common_settings["resolution"]
                    build_def["WorldResolution"] = common_settings["resolution"]

                # Apply export format changes
                if "export_formats" in common_settings:
                    nodes = project["Assets"]["$values"][0]["Terrain"].get("Nodes", {})
                    for node_id, node in nodes.items():
                        node_type = node.get("$type", "").split(".")[-2]
                        if node_type in ["Export", "Unity", "Unreal"]:
                            format_key = "heightmap" if "height" in node.get("Name", "").lower() else "textures"
                            new_format = common_settings["export_formats"].get(format_key)
                            if new_format:
                                node["Format"] = new_format
                                if "SaveDefinition" in node:
                                    node["SaveDefinition"]["Format"] = new_format

                # Apply node property updates
                if "node_updates" in common_settings:
                    nodes = project["Assets"]["$values"][0]["Terrain"].get("Nodes", {})
                    for update in common_settings["node_updates"]:
                        for node_id, node in nodes.items():
                            node_type = node.get("$type", "").split(".")[-2]
                            if node_type == update.get("type"):
                                for prop, value in update.get("properties", {}).items():
                                    node[prop] = value

                # Save updated project
                if output_directory:
                    output_path = os.path.join(output_directory, f"{project_name}_batch.terrain")
                    os.makedirs(output_directory, exist_ok=True)
                else:
                    output_path = project_file.replace(".terrain", "_batch.terrain")

                with open(output_path, "w") as f:
                    json.dump(project, f, indent=2)

                results.append(
                    {
                        "project": project_name,
                        "status": "success",
                        "output_path": output_path,
                    }
                )

            except Exception as e:
                results.append(
                    {
                        "project": os.path.basename(project_file),
                        "status": "failed",
                        "error": str(e),
                    }
                )

        success_count = sum(1 for r in results if r["status"] == "success")

        return {
            "success": True,
            "total_projects": len(project_files),
            "successful": success_count,
            "failed": len(project_files) - success_count,
            "results": results,
        }

    @staticmethod
    async def export_node_preset(
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]],
        preset_name: str,
        category: str = "custom",
        description: str = "",
    ) -> Dict[str, Any]:
        """
        Export a selection of nodes as a reusable preset

        Categories: custom, erosion, texturing, masking, effects
        """
        preset = {
            "name": preset_name,
            "category": category,
            "description": description,
            "created": datetime.utcnow().isoformat(),
            "nodes": nodes,
            "connections": connections,
            "metadata": {
                "node_count": len(nodes),
                "connection_count": len(connections),
                "node_types": list(set(n.get("type", "Unknown") for n in nodes)),
            },
        }

        # Save to preset file
        preset_dir = "gaea_presets"
        os.makedirs(preset_dir, exist_ok=True)

        filename = re.sub(r"[^\w\-_\. ]", "_", preset_name)
        preset_path = os.path.join(preset_dir, f"{filename}.json")

        with open(preset_path, "w") as f:
            json.dump(preset, f, indent=2)

        return {"success": True, "preset": preset, "path": preset_path}

    @staticmethod
    async def import_node_preset(preset_name: str, position: Dict[str, float], id_offset: int = 1000) -> Dict[str, Any]:
        """
        Import a node preset at the specified position

        The id_offset is added to all node IDs to avoid conflicts
        """
        try:
            # Look for preset file
            preset_dir = "gaea_presets"
            filename = re.sub(r"[^\w\-_\. ]", "_", preset_name)
            preset_path = os.path.join(preset_dir, f"{filename}.json")

            if not os.path.exists(preset_path):
                # Try exact match
                for file in os.listdir(preset_dir):
                    if file.endswith(".json") and preset_name.lower() in file.lower():
                        preset_path = os.path.join(preset_dir, file)
                        break

            with open(preset_path, "r") as f:
                preset = json.load(f)

            # Offset all node IDs and positions
            imported_nodes = []
            id_mapping = {}

            for node in preset["nodes"]:
                old_id = node["id"]
                new_id = old_id + id_offset
                id_mapping[old_id] = new_id

                # Create new node with offset position
                new_node = node.copy()
                new_node["id"] = new_id
                new_node["position"] = {
                    "x": node["position"]["x"] + position["x"],
                    "y": node["position"]["y"] + position["y"],
                }

                imported_nodes.append(new_node)

            # Update connections with new IDs
            imported_connections = []
            for conn in preset["connections"]:
                new_conn = conn.copy()
                new_conn["from_node"] = id_mapping.get(conn["from_node"], conn["from_node"])
                new_conn["to_node"] = id_mapping.get(conn["to_node"], conn["to_node"])
                imported_connections.append(new_conn)

            return {
                "success": True,
                "nodes": imported_nodes,
                "connections": imported_connections,
                "preset_info": {
                    "name": preset["name"],
                    "category": preset["category"],
                    "description": preset["description"],
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    async def compare_projects(project_a: str, project_b: str) -> Dict[str, Any]:
        """
        Compare two Gaea projects and identify differences

        Returns differences in:
        - Node counts and types
        - Property values
        - Connections
        - Build settings
        """
        try:
            # Load both projects
            with open(project_a, "r") as f:
                proj_a = json.load(f)
            with open(project_b, "r") as f:
                proj_b = json.load(f)

            terrain_a = proj_a["Assets"]["$values"][0]["Terrain"]
            terrain_b = proj_b["Assets"]["$values"][0]["Terrain"]

            nodes_a = terrain_a.get("Nodes", {})
            nodes_b = terrain_b.get("Nodes", {})

            # Compare node counts
            differences: Dict[str, Any] = {
                "node_count": {
                    "project_a": len(nodes_a),
                    "project_b": len(nodes_b),
                    "difference": len(nodes_b) - len(nodes_a),
                },
                "added_nodes": [],
                "removed_nodes": [],
                "modified_nodes": [],
                "connection_changes": [],
                "build_settings": {},
            }

            # Find added/removed nodes
            ids_a = set(nodes_a.keys())
            ids_b = set(nodes_b.keys())

            for node_id in ids_b - ids_a:
                node = nodes_b[node_id]
                differences["added_nodes"].append(
                    {
                        "id": node_id,
                        "type": node.get("$type", "").split(".")[-2],
                        "name": node.get("Name", ""),
                    }
                )

            for node_id in ids_a - ids_b:
                node = nodes_a[node_id]
                differences["removed_nodes"].append(
                    {
                        "id": node_id,
                        "type": node.get("$type", "").split(".")[-2],
                        "name": node.get("Name", ""),
                    }
                )

            # Compare common nodes
            for node_id in ids_a & ids_b:
                node_a = nodes_a[node_id]
                node_b = nodes_b[node_id]

                # Compare properties
                props_changed = []

                # Get all property keys
                all_keys = set(node_a.keys()) | set(node_b.keys())
                ignore_keys = {"$id", "$ref", "Ports", "Position"}

                for key in all_keys - ignore_keys:
                    val_a = node_a.get(key)
                    val_b = node_b.get(key)

                    if val_a != val_b:
                        props_changed.append({"property": key, "old_value": val_a, "new_value": val_b})

                if props_changed:
                    differences["modified_nodes"].append(
                        {
                            "id": node_id,
                            "type": node_a.get("$type", "").split(".")[-2],
                            "name": node_a.get("Name", ""),
                            "changes": props_changed,
                        }
                    )

            # Compare build settings
            build_a = proj_a["Assets"]["$values"][0].get("BuildDefinition", {})
            build_b = proj_b["Assets"]["$values"][0].get("BuildDefinition", {})

            for key in set(build_a.keys()) | set(build_b.keys()):
                if build_a.get(key) != build_b.get(key):
                    differences["build_settings"][key] = {
                        "project_a": build_a.get(key),
                        "project_b": build_b.get(key),
                    }

            return {
                "success": True,
                "differences": differences,
                "summary": {
                    "total_changes": (
                        len(differences["added_nodes"])
                        + len(differences["removed_nodes"])
                        + len(differences["modified_nodes"])
                    ),
                    "has_structural_changes": bool(differences["added_nodes"] or differences["removed_nodes"]),
                    "has_property_changes": bool(differences["modified_nodes"]),
                    "has_build_changes": bool(differences["build_settings"]),
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    async def profile_project_performance(project_file: str) -> Dict[str, Any]:
        """
        Analyze project for performance bottlenecks

        Identifies:
        - Heavy computation nodes
        - Memory-intensive operations
        - Inefficient node chains
        - Optimization opportunities
        """
        # Node performance weights (relative computation cost)
        node_weights = {
            "Erosion": 10,
            "Erosion2": 12,
            "Wizard": 15,
            "RiverErosion": 8,
            "Alluvium": 7,
            "Snowfall": 6,
            "Thermal": 5,
            "SlopeBlur": 4,
            "Blur": 2,
            "Mountain": 1,
            "Ridge": 1,
            "Constant": 0.1,
            "SatMap": 3,
            "Texture": 4,
            "TextureBase": 4,
            "Combine": 1,
            "Transform": 2,
            "Warp": 3,
            "Export": 1,
            "Unity": 1,
        }

        try:
            with open(project_file, "r") as f:
                project = json.load(f)

            terrain = project["Assets"]["$values"][0]["Terrain"]
            nodes = terrain.get("Nodes", {})

            performance_analysis: Dict[str, Any] = {
                "total_cost": 0.0,
                "heavy_nodes": [],
                "optimization_suggestions": [],
                "memory_estimate_mb": 0,
                "node_costs": {},
            }

            # Get resolution for memory calculations
            build_def = project["Assets"]["$values"][0].get("BuildDefinition", {})
            resolution = build_def.get("Resolution", 2048)

            # Analyze each node
            for node_id, node in nodes.items():
                node_type = node.get("$type", "").split(".")[-2]
                base_weight = node_weights.get(node_type, 3)

                # Adjust weight based on properties
                adjusted_weight = float(base_weight)

                # Erosion nodes scale with duration/iterations
                if node_type in ["Erosion", "Erosion2"]:
                    duration = float(node.get("Duration", 10))
                    adjusted_weight *= duration / 10

                # Iterative nodes scale with iterations
                if "Iterations" in node:
                    iterations = float(node.get("Iterations", 1))
                    adjusted_weight *= iterations / 10

                # High resolution nodes
                if "Resolution" in node:
                    node_res = float(node.get("Resolution", 1))
                    adjusted_weight *= node_res / 1000

                performance_analysis["node_costs"][node_id] = {
                    "type": node_type,
                    "name": node.get("Name", node_type),
                    "cost": adjusted_weight,
                }

                performance_analysis["total_cost"] += adjusted_weight

                # Identify heavy nodes
                if adjusted_weight > 8:
                    performance_analysis["heavy_nodes"].append(
                        {
                            "id": node_id,
                            "type": node_type,
                            "name": node.get("Name", node_type),
                            "cost": adjusted_weight,
                        }
                    )

                # Memory estimate (rough)
                if node_type in ["Export", "Unity", "Unreal"]:
                    # Each export adds memory for the output buffer
                    bytes_per_pixel = 4  # Assuming 32-bit float
                    performance_analysis["memory_estimate_mb"] += (resolution * resolution * bytes_per_pixel) / (1024 * 1024)

            # Generate optimization suggestions
            suggestions = performance_analysis["optimization_suggestions"]

            # Check for multiple heavy erosion nodes
            erosion_count = sum(
                1 for n in performance_analysis["heavy_nodes"] if n["type"] in ["Erosion", "Erosion2", "Wizard"]
            )
            if erosion_count > 2:
                suggestions.append(
                    {
                        "type": "performance",
                        "priority": "high",
                        "message": (
                            f"Found {erosion_count} heavy erosion nodes. "
                            "Consider reducing duration or combining operations."
                        ),
                        "potential_savings": "30-50%",
                    }
                )

            # Check total complexity
            if performance_analysis["total_cost"] > 100:
                suggestions.append(
                    {
                        "type": "complexity",
                        "priority": "medium",
                        "message": (
                            "High overall complexity. Consider simplifying the node graph "
                            "or using lower resolution previews."
                        ),
                        "potential_savings": "20-40%",
                    }
                )

            # Memory warnings
            total_memory = performance_analysis["memory_estimate_mb"]
            if total_memory > 4096:
                suggestions.append(
                    {
                        "type": "memory",
                        "priority": "high",
                        "message": (
                            f"High memory usage estimated ({total_memory:.0f} MB). "
                            "Consider reducing resolution or export count."
                        ),
                        "potential_savings": "Variable",
                    }
                )

            # Calculate performance grade
            if performance_analysis["total_cost"] < 50:
                grade = "A"
                grade_desc = "Excellent - Fast processing"
            elif performance_analysis["total_cost"] < 100:
                grade = "B"
                grade_desc = "Good - Reasonable processing time"
            elif performance_analysis["total_cost"] < 200:
                grade = "C"
                grade_desc = "Fair - May be slow on lower-end systems"
            else:
                grade = "D"
                grade_desc = "Poor - Expect long processing times"

            return {
                "success": True,
                "analysis": performance_analysis,
                "performance_grade": {"grade": grade, "description": grade_desc},
                "estimated_build_time": {
                    "fast_cpu": f"{performance_analysis['total_cost'] * 0.1:.1f} minutes",
                    "average_cpu": f"{performance_analysis['total_cost'] * 0.3:.1f} minutes",
                    "slow_cpu": f"{performance_analysis['total_cost'] * 0.6:.1f} minutes",
                },
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
