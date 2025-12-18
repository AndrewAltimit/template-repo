"""Enhanced Gaea 2 MCP Tools with support for advanced features"""

import base64
from datetime import datetime
import json
import os
from typing import Any, Dict, List, Optional
import uuid


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

            # Build definition matching Gaea2 2.2.6.0 format
            default_build_config = {
                "Type": "Standard",
                "Destination": "<Builds>\\[Filename]\\[+++]",
                "Resolution": 2048,
                "BakeResolution": 2048,
                "TileResolution": 1024,
                "BucketResolution": 2048,
                "NumberOfTiles": 3,
                "EdgeBlending": 0.25,
                "TileZeroIndex": True,
                "TilePattern": "_y%Y%_x%X%",
                "OrganizeFiles": "NodeSubFolder",
                "ColorSpace": "sRGB",
            }

            if build_config:
                default_build_config.update(build_config)

            if viewport_settings:
                pass  # Will be applied later

            # Create base project structure matching Gaea2 2.2.6.0 format
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
                                    "Description": "",
                                    "Version": "2.2.6.0",
                                    "DateCreated": timestamp,
                                    "DateLastBuilt": timestamp,
                                    "DateLastSaved": timestamp,
                                    "ModifiedVersion": "2.2.6.0",
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
                                            "ZoomFactor": 0.6299605249474372,
                                            "ViewportLocation": {
                                                "$id": "11",
                                                "X": 27690.082,
                                                "Y": 25804.441,
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
                                "Variables": {"$id": "16"},
                            },
                            "BuildDefinition": {"$id": "17", **default_build_config},
                            "State": {
                                "$id": "18",
                                "BakeResolution": 2048,
                                "PreviewResolution": 1024,
                                "HDResolution": 4096,
                                "SelectedNode": -1,
                                "NodeBookmarks": {"$id": "19", "$values": []},
                                "Viewport": {
                                    "$id": "20",
                                    "CameraPosition": {"$id": "21", "$values": []},
                                    "Camera": {"$id": "22"},
                                    "RenderMode": "Realistic",
                                    "AmbientOcclusion": True,
                                    "Shadows": True,
                                },
                            },
                            "BuildProfiles": {"$id": "23"},
                        }
                    ],
                },
                "Id": project_id[:8],
                "Branch": 1,
                "Metadata": {
                    "$id": "24",
                    "Name": project_name,
                    "Description": "",
                    "Version": "2.2.6.0",
                    "Edition": "G2P",
                    "Owner": "",
                    "DateCreated": timestamp,
                    "DateLastBuilt": timestamp,
                    "DateLastSaved": timestamp,
                    "ModifiedVersion": "2.2.6.0",
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
            ref_id_counter = 25  # Start after the last $id in project structure (24)

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

            # Assign nodes to project - preserve the $id from the original Nodes dict
            assets_obj = project["Assets"]
            assert isinstance(assets_obj, dict)
            assets_values = assets_obj["$values"]
            assert isinstance(assets_values, list) and len(assets_values) > 0
            first_asset = assets_values[0]
            assert isinstance(first_asset, dict)
            terrain = first_asset["Terrain"]
            assert isinstance(terrain, dict)
            # Keep the $id and add nodes to it
            nodes_with_id = {"$id": "6"}
            nodes_with_id.update(nodes_dict)
            terrain["Nodes"] = nodes_with_id

            # Save project
            if output_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
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
    def _get_default_ports(node_type: str) -> List[Dict[str, str]]:
        """Get default ports for a node type."""
        ports = [
            {"name": "In", "type": "PrimaryIn"},
            {"name": "Out", "type": "PrimaryOut"},
        ]

        if node_type == "Erosion2":
            ports.extend(
                [{"name": "Flow", "type": "Out"}, {"name": "Wear", "type": "Out"}, {"name": "Deposits", "type": "Out"}]
            )
        elif node_type == "Sandstone":
            ports.append({"name": "Layers", "type": "Out"})
        elif node_type == "Canyon":
            ports.append({"name": "Depth", "type": "Out"})
        elif node_type == "Unity":
            for i in range(1, 9):
                ports.extend([{"name": f"Input{i}", "type": "In"}, {"name": f"Output{i}", "type": "Out"}])

        return ports

    @staticmethod
    def _create_port_objects(
        port_defs: List[Dict[str, Any]], node_id_ref: str, ref_id_counter: int
    ) -> tuple[List[Dict[str, Any]], int]:
        """Create port objects from port definitions."""
        port_objects = []
        for port_def in port_defs:
            port = {
                "$id": str(ref_id_counter),
                "Name": port_def["name"],
                "Type": port_def["type"],
                "IsExporting": True,
                "Parent": {"$ref": node_id_ref},
            }
            if "portal_state" in port_def:
                port["PortalState"] = port_def["portal_state"]
            port_objects.append(port)
            ref_id_counter += 1
        return port_objects, ref_id_counter

    @staticmethod
    def _create_modifier_object(modifier: Dict[str, Any], node_id_ref: str, ref_id_counter: int) -> tuple[Dict[str, Any], int]:
        """Create a modifier object from modifier definition."""
        mod_obj = {
            "$id": str(ref_id_counter),
            "$type": f"QuadSpinner.Gaea.Nodes.Modifiers.{modifier['type']}, Gaea.Nodes",
            "Name": modifier["type"],
            "Parent": {"$ref": node_id_ref},
            "Intrinsic": True,
        }
        ref_id_counter += 1

        if "properties" in modifier:
            for prop, value in modifier["properties"].items():
                if isinstance(value, dict) and "x" in value and "y" in value:
                    mod_obj[prop] = {"$id": str(ref_id_counter), "X": float(value["x"]), "Y": float(value["y"])}
                    ref_id_counter += 1
                else:
                    mod_obj[prop] = value

        if modifier.get("has_ui", False):
            mod_obj["HasUI"] = True
        if "order" in modifier:
            mod_obj["Order"] = modifier["order"]

        return mod_obj, ref_id_counter

    @staticmethod
    def _create_save_definition(
        save_def: Dict[str, Any], node_id: int, node_name: str, ref_id_counter: int
    ) -> tuple[Dict[str, Any], int]:
        """Create save definition for export nodes."""
        save_obj = {
            "$id": str(ref_id_counter),
            "Node": node_id,
            "Filename": save_def.get("filename", node_name),
            "Format": save_def.get("format", "PNG64"),
            "IsEnabled": save_def.get("enabled", True),
            "DisabledInProfiles": {"$id": str(ref_id_counter + 1), "$values": save_def.get("disabled_profiles", [])},
        }
        return save_obj, ref_id_counter + 2

    @staticmethod
    def _process_mixer_layers(properties: Dict[str, Any], ref_id_counter: int) -> tuple[Dict[str, Any], int]:
        """Process Mixer node layer definitions."""
        layers = {}
        for i in range(1, 16):
            layer_key = f"Layer{i}"
            if layer_key not in properties:
                continue
            layer = properties[layer_key]
            layer_obj = {
                "$id": str(ref_id_counter),
                "Range": {
                    "$id": str(ref_id_counter + 1),
                    "X": float(layer.get("range", {}).get("x", 0.0)),
                    "Y": float(layer.get("range", {}).get("y", 1.0)),
                },
                "Order": layer.get("order", i - 1),
                "Index": i - 1,
            }
            ref_id_counter += 2
            if "color" in layer:
                layer_obj["Color"] = {
                    "$id": str(ref_id_counter),
                    "R": float(layer["color"].get("r", 1.0)),
                    "G": float(layer["color"].get("g", 1.0)),
                    "B": float(layer["color"].get("b", 1.0)),
                }
                ref_id_counter += 1
            layers[layer_key] = layer_obj
        return layers, ref_id_counter

    @staticmethod
    async def _create_enhanced_node(node_data: Dict[str, Any], node_id: int, ref_id_counter: int) -> Dict[str, Any]:
        """Create an enhanced node with modifiers, ports, and save definitions"""
        node_type = node_data.get("type", "Mountain")
        node_name = node_data.get("name", node_type)
        position = node_data.get("position", {"x": 25000, "y": 25000})
        properties = node_data.get("properties", {})

        # Base node structure
        node = {
            "$id": str(ref_id_counter),
            "$type": f"QuadSpinner.Gaea.Nodes.{node_type}, Gaea.Nodes",
            "Id": node_id,
            "Name": node_name,
            "Position": {"$id": str(ref_id_counter + 1), "X": float(position["x"]), "Y": float(position["y"])},
            "Ports": {"$id": str(ref_id_counter + 2), "$values": []},
            "Modifiers": {"$id": str(ref_id_counter + 3), "$values": []},
        }
        node_id_ref = str(ref_id_counter)
        ref_id_counter += 4

        # Add node-specific properties
        for prop, value in properties.items():
            if isinstance(value, dict) and "x" in value and "y" in value:
                node[prop] = {"$id": str(ref_id_counter), "X": float(value["x"]), "Y": float(value["y"])}
                ref_id_counter += 1
            elif prop == "StrokeData" and isinstance(value, str):
                node[prop] = value
            else:
                node[prop] = value

        # Create ports
        port_defs = node_data.get("ports") or EnhancedGaea2Tools._get_default_ports(node_type)
        node["Ports"]["$values"], ref_id_counter = EnhancedGaea2Tools._create_port_objects(
            port_defs, node_id_ref, ref_id_counter
        )

        # Add modifiers
        for modifier in node_data.get("modifiers", []):
            mod_obj, ref_id_counter = EnhancedGaea2Tools._create_modifier_object(modifier, node_id_ref, ref_id_counter)
            node["Modifiers"]["$values"].append(mod_obj)

        # Add save definition for export nodes
        if node_data.get("save_definition"):
            node["SaveDefinition"], ref_id_counter = EnhancedGaea2Tools._create_save_definition(
                node_data["save_definition"], node_id, node_name, ref_id_counter
            )

        # Handle Mixer node layers
        if node_type == "Mixer":
            layers, ref_id_counter = EnhancedGaea2Tools._process_mixer_layers(properties, ref_id_counter)
            node.update(layers)

        # Add optional attributes
        if "node_size" in node_data:
            node["NodeSize"] = node_data["node_size"]
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
        soften: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Create a Draw node with binary stroke data

        Parameters:
        - stroke_points: List of points with x, y, and pressure values
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
        export_format: str = "PNG64",
        node_type: str = "Export",
    ) -> Dict[str, Any]:
        """
        Create an export node (Export or Unity)

        Parameters:
        - filename: Output filename
        - export_format: Export format (PNG64, EXR, RAW16, etc.)
        - node_type: Export or Unity
        """
        return {
            "id": node_id,
            "type": node_type,
            "name": f"{filename} Export",
            "position": position,
            "properties": {"Format": export_format},
            "save_definition": {
                "filename": filename,
                "format": export_format,
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
