"""Enhanced Gaea 2 MCP Tools with support for advanced features"""

import base64
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


class EnhancedGaea2Tools:
    """Enhanced tools for Gaea 2 project creation with advanced features"""

    @staticmethod
    async def create_advanced_gaea2_project(
        project_name: str,
        nodes: List[Dict[str, Any]],
        connections: Optional[List[Dict[str, Any]]] = None,
        groups: Optional[List[Dict[str, Any]]] = None,
        variables: Optional[Dict[str, Any]] = None,
        build_config: Optional[Dict[str, Any]] = None,
        viewport_settings: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create an advanced Gaea 2 project with full feature support

        Parameters:
        - nodes: List of node definitions with properties, modifiers, and ports
        - connections: List of connections between nodes
        - groups: List of node groups for visual organization
        - variables: Automation variables for the project
        - build_config: Advanced build configuration settings
        - viewport_settings: 3D viewport and rendering settings
        """
        try:
            project_id = str(uuid.uuid4())
            terrain_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")

            # Enhanced build definition
            default_build_config = {
                "Type": "Standard",
                "Destination": "<Builds>\\[Filename]\\[+++]",
                "OverwriteMode": "Increment",
                "Resolution": 2048,
                "BakeResolution": 2048,
                "TileResolution": 1024,
                "BucketResolution": 2048,
                "BucketCount": 1,
                "WorldResolution": 2048,
                "NumberOfTiles": 2,
                "TotalTiles": 4,
                "BucketSizeWithMargin": 3072,
                "EdgeBlending": 0.25,
                "EdgeSize": 512,
                "TileZeroIndex": True,
                "TilePattern": "_y%Y%_x%X%",
                "OrganizeFiles": "NodeSubFolder",
                "PersistOnSave": True,
                "PostBuildScript": "",
                "OpenFolder": True,
                "CopyTerrain": True,
                "Regions": {"$id": "24", "$values": []},
            }

            if build_config:
                default_build_config.update(build_config)

            # Enhanced viewport settings
            default_viewport = {
                "Camera": {"$id": str(uuid.uuid4())},
                "RenderMode": "Realistic",
                "AutolevelMasks": True,
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
            }

            if viewport_settings:
                default_viewport.update(viewport_settings)

            # Create base project structure
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
                                    "Description": f"Enhanced project created by MCP on {timestamp}",
                                    "Version": "",  # Empty string like working files
                                    "DateCreated": timestamp,
                                    "DateLastBuilt": timestamp,
                                    "DateLastSaved": timestamp,
                                    "ModifiedVersion": "2.1.2.0",
                                },
                                "Nodes": {"$id": "6"},
                                "Groups": {"$id": "7"},
                                "Notes": {"$id": "8"},
                                "GraphTabs": {
                                    "$id": "9",
                                    "$values": [
                                        {
                                            "$id": "10",
                                            "Name": "Graph 1",
                                            "Color": "Brass",
                                            "ZoomFactor": 0.5,
                                            "ViewportLocation": {
                                                "$id": "11",
                                                "X": 25000.0,
                                                "Y": 25000.0,
                                            },
                                        }
                                    ],
                                },
                                "Width": 5000.0,
                                "Height": 2500.0,
                                "Ratio": 0.5,
                                "Regions": {"$id": "12", "$values": []},
                            },
                            "Automation": {
                                "$id": "13",
                                "Bindings": {"$id": "14", "$values": []},
                                "Expressions": {"$id": "15"},
                                "VariablesEx": {"$id": "16"},
                                "Variables": {"$id": "17"},
                                "BoundProperties": {"$id": "23", "$values": []},
                            },
                            "BuildDefinition": {"$id": "18", **default_build_config},
                            "State": {
                                "$id": "19",
                                "BakeResolution": 2048,
                                "PreviewResolution": 2048,
                                "SelectedNode": nodes[0]["id"] if nodes else 100,
                                "NodeBookmarks": {"$id": "20", "$values": []},
                                "Viewport": {"$id": "21", **default_viewport},
                            },
                        }
                    ],
                },
                "Id": project_id[:8],
                "Branch": 1,
                "Metadata": {
                    "$id": "22",
                    "Name": project_name,
                    "Description": "",
                    "Version": "",  # Empty string like working files
                    "Owner": "",
                    "DateCreated": timestamp,
                    "DateLastBuilt": timestamp,
                    "DateLastSaved": timestamp,
                    "ModifiedVersion": "2.1.2.0",
                },
            }

            # Add automation variables
            if variables:
                assets_obj = project["Assets"]
                assert isinstance(assets_obj, dict)
                assets_values = assets_obj["$values"]
                assert isinstance(assets_values, list) and len(assets_values) > 0
                first_asset = assets_values[0]
                assert isinstance(first_asset, dict)
                automation = first_asset["Automation"]
                assert isinstance(automation, dict)
                automation["Variables"] = variables

            # Process nodes with enhanced features
            nodes_dict: Dict[str, Any] = {}
            ref_id_counter = 23

            for node_data in nodes:
                node_id = node_data.get("id", 100 + len(nodes_dict))
                enhanced_node = await EnhancedGaea2Tools._create_enhanced_node(node_data, node_id, ref_id_counter)
                nodes_dict[str(node_id)] = enhanced_node["node"]
                ref_id_counter = enhanced_node["next_ref_id"]

            # Add connections
            if connections:
                ref_id_counter = await EnhancedGaea2Tools._add_connections(connections, nodes_dict, ref_id_counter)

            # Add groups
            if groups:
                groups_dict: Dict[str, Any] = {}
                for group in groups:
                    group_id = group.get("id", 300 + len(groups_dict))
                    groups_dict[str(group_id)] = {
                        "$id": str(ref_id_counter),
                        "Id": group_id,
                        "Name": group.get("name", "Group"),
                        "Color": group.get("color", "Gray"),
                        "Children": {
                            "$id": str(ref_id_counter + 1),
                            "$values": group.get("children", []),
                        },
                        "Position": {
                            "$id": str(ref_id_counter + 2),
                            "X": float(group.get("position", {}).get("x", 25000)),
                            "Y": float(group.get("position", {}).get("y", 25000)),
                        },
                        "Size": {
                            "$id": str(ref_id_counter + 3),
                            "X": float(group.get("size", {}).get("x", 500)),
                            "Y": float(group.get("size", {}).get("y", 500)),
                        },
                    }
                    ref_id_counter += 4
                assets_obj = project["Assets"]
                assert isinstance(assets_obj, dict)
                assets_values = assets_obj["$values"]
                assert isinstance(assets_values, list) and len(assets_values) > 0
                first_asset = assets_values[0]
                assert isinstance(first_asset, dict)
                terrain = first_asset["Terrain"]
                assert isinstance(terrain, dict)
                terrain["Groups"] = groups_dict

            # Assign nodes to project
            assets_obj = project["Assets"]
            assert isinstance(assets_obj, dict)
            assets_values = assets_obj["$values"]
            assert isinstance(assets_values, list) and len(assets_values) > 0
            first_asset = assets_values[0]
            assert isinstance(first_asset, dict)
            terrain = first_asset["Terrain"]
            assert isinstance(terrain, dict)
            terrain["Nodes"] = nodes_dict

            # Save project
            if output_path:
                import os

                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "w") as f:
                    json.dump(project, f, indent=2)

            return {
                "success": True,
                "project": project,
                "output_path": output_path,
                "node_count": len(nodes_dict),
                "connection_count": len(connections) if connections else 0,
                "group_count": len(groups) if groups else 0,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    async def _create_enhanced_node(node_data: Dict[str, Any], node_id: int, ref_id_counter: int) -> Dict[str, Any]:
        """Create an enhanced node with modifiers, ports, and save definitions"""

        node_type = node_data.get("type", "Mountain")
        node_name = node_data.get("name", node_type)
        position = node_data.get("position", {"x": 25000, "y": 25000})
        properties = node_data.get("properties", {})
        modifiers = node_data.get("modifiers", [])
        ports = node_data.get("ports", [])
        save_definition = node_data.get("save_definition")

        # Base node structure
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
            "Ports": {"$id": str(ref_id_counter + 2), "$values": []},
            "Modifiers": {"$id": str(ref_id_counter + 3), "$values": []},
        }

        ref_id_counter += 4

        # Add node-specific properties
        for prop, value in properties.items():
            # Handle special property types
            if isinstance(value, dict) and "x" in value and "y" in value:
                # Vector2 property
                node[prop] = {
                    "$id": str(ref_id_counter),
                    "X": float(value["x"]),
                    "Y": float(value["y"]),
                }
                ref_id_counter += 1
            elif prop == "StrokeData" and isinstance(value, str):
                # Binary stroke data
                node[prop] = value
            else:
                node[prop] = value

        # Create default ports
        default_ports = [
            {"name": "In", "type": "PrimaryIn"},
            {"name": "Out", "type": "PrimaryOut"},
        ]

        # Add node-specific ports
        if node_type == "Erosion2":
            default_ports.extend(
                [
                    {"name": "Flow", "type": "Out"},
                    {"name": "Wear", "type": "Out"},
                    {"name": "Deposits", "type": "Out"},
                ]
            )
        elif node_type == "Sandstone":
            default_ports.append({"name": "Layers", "type": "Out"})
        elif node_type == "Canyon":
            default_ports.append({"name": "Depth", "type": "Out"})
        elif node_type == "Unity":
            # Unity export node has many input/output pairs
            for i in range(1, 9):
                default_ports.extend(
                    [
                        {"name": f"Input{i}", "type": "In"},
                        {"name": f"Output{i}", "type": "Out"},
                    ]
                )

        # Override with custom ports if provided
        if ports:
            default_ports = ports

        # Create port objects
        for port_def in default_ports:
            port = {
                "$id": str(ref_id_counter),
                "Name": port_def["name"],
                "Type": port_def["type"],
                "IsExporting": True,
                "Parent": {"$ref": str(node["$id"])},
            }

            # Add portal state if specified
            if "portal_state" in port_def:
                port["PortalState"] = port_def["portal_state"]

            node["Ports"]["$values"].append(port)
            ref_id_counter += 1

        # Add modifiers
        for modifier in modifiers:
            mod_obj = {
                "$id": str(ref_id_counter),
                "$type": f"QuadSpinner.Gaea.Nodes.Modifiers.{modifier['type']}, Gaea.Nodes",
                "Name": modifier["type"],
                "Parent": {"$ref": str(node["$id"])},
                "Intrinsic": True,
            }

            # Add modifier-specific properties
            if "properties" in modifier:
                for prop, value in modifier["properties"].items():
                    if isinstance(value, dict) and "x" in value and "y" in value:
                        mod_obj[prop] = {
                            "$id": str(ref_id_counter + 1),
                            "X": float(value["x"]),
                            "Y": float(value["y"]),
                        }
                        ref_id_counter += 1
                    else:
                        mod_obj[prop] = value

            # Add UI flags
            if modifier.get("has_ui", False):
                mod_obj["HasUI"] = True

            if "order" in modifier:
                mod_obj["Order"] = modifier["order"]

            node["Modifiers"]["$values"].append(mod_obj)
            ref_id_counter += 1

        # Add save definition for export nodes
        if save_definition:
            node["SaveDefinition"] = {
                "$id": str(ref_id_counter),
                "Node": node_id,
                "Filename": save_definition.get("filename", node_name),
                "Format": save_definition.get("format", "PNG64"),
                "IsEnabled": save_definition.get("enabled", True),
                "DisabledInProfiles": {
                    "$id": str(ref_id_counter + 1),
                    "$values": save_definition.get("disabled_profiles", []),
                },
            }
            ref_id_counter += 2

        # Handle special node types
        if node_type == "Mixer":
            # Add layer definitions
            for i in range(1, 16):
                layer_key = f"Layer{i}"
                if layer_key in properties:
                    layer = properties[layer_key]
                    node[layer_key] = {
                        "$id": str(ref_id_counter),
                        "Range": {
                            "$id": str(ref_id_counter + 1),
                            "X": float(layer.get("range", {}).get("x", 0.0)),
                            "Y": float(layer.get("range", {}).get("y", 1.0)),
                        },
                        "Order": layer.get("order", i - 1),
                        "Index": i - 1,
                    }

                    if "color" in layer:
                        node[layer_key]["Color"] = {
                            "$id": str(ref_id_counter + 2),
                            "R": float(layer["color"].get("r", 1.0)),
                            "G": float(layer["color"].get("g", 1.0)),
                            "B": float(layer["color"].get("b", 1.0)),
                        }
                        ref_id_counter += 1

                    ref_id_counter += 2

        # Add node size
        if "node_size" in node_data:
            node["NodeSize"] = node_data["node_size"]

        # Add maskable flag
        if node_data.get("is_maskable", True):
            node["IsMaskable"] = True

        return {"node": node, "next_ref_id": ref_id_counter}

    @staticmethod
    async def _add_connections(
        connections: List[Dict[str, Any]],
        nodes_dict: Dict[str, Any],
        ref_id_counter: int,
    ) -> int:
        """Add connections between nodes with enhanced port handling"""

        for conn in connections:
            from_id = str(conn["from_node"])
            to_id = str(conn["to_node"])
            from_port = conn.get("from_port", "Out")
            to_port = conn.get("to_port", "In")

            if from_id in nodes_dict and to_id in nodes_dict:
                target_node = nodes_dict[to_id]

                # Find the port in the target node
                for port in target_node["Ports"]["$values"]:
                    if port["Name"] == to_port:
                        # Update port type to Required if it's an input
                        if "In" in port["Type"] and "Required" not in port["Type"]:
                            port["Type"] = f"{port['Type']}, Required"

                        # Add connection record
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

        return ref_id_counter

    @staticmethod
    async def create_draw_node(
        node_id: int,
        position: Dict[str, float],
        stroke_points: List[Dict[str, float]],
        brush_size: float = 10.0,
        soften: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Create a Draw node with binary stroke data

        Parameters:
        - stroke_points: List of points with x, y, and pressure values
        - brush_size: Size of the brush
        - soften: Softening amount for the strokes
        """
        # Encode stroke data (simplified version)
        # In reality, this would need proper binary encoding
        stroke_data = base64.b64encode(json.dumps(stroke_points).encode()).decode()

        return {
            "id": node_id,
            "type": "Draw",
            "name": "Draw",
            "position": position,
            "properties": {"Soften": soften, "StrokeData": stroke_data},
        }

    @staticmethod
    async def create_mixer_node(node_id: int, position: Dict[str, float], layers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a Mixer node with multiple layers

        Parameters:
        - layers: List of layer definitions with range, color, and order
        """
        properties: Dict[str, Any] = {
            "PortCount": max(10, len(layers)),
            "ShowSimplified": True,
            "Version": 2,
        }

        # Add layer definitions
        for i, layer in enumerate(layers, 1):
            layer_key = f"Layer{i}"
            properties[layer_key] = {
                "range": layer.get("range", {"x": 0.15 * i, "y": 1.0}),
                "order": layer.get("order", i - 1),
                "color": layer.get("color", {"r": 1.0, "g": 1.0, "b": 1.0}),
            }

        # Define ports for mixer
        ports = [
            {"name": "In", "type": "PrimaryIn, Required"},
            {"name": "Out", "type": "PrimaryOut"},
            {"name": "Terrain", "type": "In"},
        ]

        # Add layer input/output ports
        for i in range(1, len(layers) + 1):
            ports.extend(
                [
                    {"name": f"Layer{i}", "type": "In"},
                    {"name": f"Mask{i}", "type": "In"},
                    {"name": f"MaskOut{i}", "type": "Out"},
                ]
            )

        return {
            "id": node_id,
            "type": "Mixer",
            "name": "Mixer",
            "position": position,
            "properties": properties,
            "ports": ports,
            "save_definition": {"filename": "Mixer", "format": "EXR", "enabled": True},
        }

    @staticmethod
    async def create_export_node(
        node_id: int,
        position: Dict[str, float],
        filename: str,
        format: str = "PNG64",
        node_type: str = "Export",
    ) -> Dict[str, Any]:
        """
        Create an export node (Export or Unity)

        Parameters:
        - filename: Output filename
        - format: Export format (PNG64, EXR, RAW16, etc.)
        - node_type: Export or Unity
        """
        return {
            "id": node_id,
            "type": node_type,
            "name": f"{filename} Export",
            "position": position,
            "properties": {"Format": format},
            "save_definition": {
                "filename": filename,
                "format": format,
                "enabled": True,
            },
            "node_size": "Standard" if node_type == "Export" else None,
        }

    @staticmethod
    async def add_node_modifiers(node: Dict[str, Any], modifiers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Add modifiers to a node

        Parameters:
        - node: Node definition
        - modifiers: List of modifiers with type and properties

        Example modifiers:
        - {"type": "Height", "properties": {"Range": {"x": 0.4, "y": 0.5}, "Falloff": 0.15}}
        - {"type": "Blur", "properties": {"Factor": 0.94}}
        - {"type": "Invert"}
        - {"type": "Drop"}
        - {"type": "Max", "order": 66}
        """
        if "modifiers" not in node:
            node["modifiers"] = []

        node["modifiers"].extend(modifiers)
        return node

    @staticmethod
    async def build_gaea2_project(
        project_file: str,
        resolution: int = 2048,
        output_format: str = "png",
        enable_tiling: bool = False,
        tile_size: int = 1024,
        open_folder: bool = True,
        build_script: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute Gaea build process (placeholder for actual implementation)

        This would interface with Gaea CLI or API to build the project
        """
        return {
            "success": True,
            "message": "Build functionality would interface with Gaea CLI",
            "parameters": {
                "project_file": project_file,
                "resolution": resolution,
                "output_format": output_format,
                "enable_tiling": enable_tiling,
                "tile_size": tile_size,
                "open_folder": open_folder,
                "build_script": build_script,
            },
        }

    @staticmethod
    async def analyze_build_outputs(build_directory: str) -> Dict[str, Any]:
        """
        Analyze build outputs including reports and file sizes

        This would parse report.json and analyze output files
        """
        return {
            "success": True,
            "message": "Analysis functionality would parse build outputs",
            "directory": build_directory,
        }
