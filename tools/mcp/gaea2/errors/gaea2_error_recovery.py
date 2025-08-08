#!/usr/bin/env python3
"""
Error recovery and auto-fix system for Gaea2 projects
"""

import logging
from copy import deepcopy
from typing import Any, Dict, List, Tuple

from tools.mcp.gaea2.utils.gaea2_pattern_knowledge import get_next_node_suggestions, suggest_properties_for_node
from tools.mcp.gaea2.validation.gaea2_connection_validator import Gaea2ConnectionValidator
from tools.mcp.gaea2.validation.gaea2_format_fixes import generate_non_sequential_id
from tools.mcp.gaea2.validation.gaea2_property_validator import Gaea2PropertyValidator

logger = logging.getLogger(__name__)


class Gaea2ErrorRecovery:
    """Automated error recovery and fix suggestions for Gaea2 projects"""

    def __init__(self):
        self.property_validator = Gaea2PropertyValidator()
        self.connection_validator = Gaea2ConnectionValidator()
        self.fixes_applied = []
        self.fix_log = []

    def auto_fix_project(
        self,
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]],
        aggressive: bool = False,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
        """
        Automatically fix common issues in a project

        Args:
            nodes: List of nodes
            connections: List of connections
            aggressive: If True, applies more aggressive fixes

        Returns:
            - Fixed nodes
            - Fixed connections
            - List of fixes applied
        """
        from tools.mcp.gaea2.utils.gaea2_connection_utils import normalize_connections

        self.fixes_applied = []
        fixed_nodes = deepcopy(nodes)
        fixed_connections = normalize_connections(deepcopy(connections))

        # Fix 1: Remove duplicate connections
        fixed_connections = self._fix_duplicate_connections(fixed_connections)

        # Fix 2: Fix node properties
        fixed_nodes = self._fix_node_properties(fixed_nodes)

        # Fix 3: Add missing required nodes
        if aggressive:
            fixed_nodes, fixed_connections = self._add_missing_required_nodes(fixed_nodes, fixed_connections)

        # Fix 4: Connect orphaned nodes
        fixed_connections = self._fix_orphaned_nodes(fixed_nodes, fixed_connections, aggressive)

        # Fix 5: Optimize workflow
        if aggressive:
            fixed_nodes, fixed_connections = self._optimize_workflow(fixed_nodes, fixed_connections)

        # Fix 6: Do NOT add Export node - they aren't needed for working files!
        # Working Gaea2 files often have no Export node at all
        # fixed_nodes = self._ensure_export_node(fixed_nodes)

        return fixed_nodes, fixed_connections, self.fixes_applied

    def _fix_duplicate_connections(self, connections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate connections"""
        seen = set()
        fixed = []
        duplicates = 0

        for conn in connections:
            # Handle both formats: from_node/to_node and source/target
            from_node = conn.get("from_node") or conn.get("source")
            to_node = conn.get("to_node") or conn.get("target")
            from_port = conn.get("from_port") or conn.get("source_port", "Out")
            to_port = conn.get("to_port") or conn.get("target_port", "In")

            key = (from_node, to_node, from_port, to_port)
            if key not in seen:
                seen.add(key)
                fixed.append(conn)
            else:
                duplicates += 1

        if duplicates > 0:
            self.fixes_applied.append(f"Removed {duplicates} duplicate connections")

        return fixed

    def _fix_node_properties(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fix invalid properties on nodes"""
        for node in nodes:
            node_type = node.get("type", "")
            properties = node.get("properties", {})

            if properties:
                is_valid, errors, fixed_props = self.property_validator.validate_properties(node_type, properties)

                if not is_valid or fixed_props != properties:
                    node["properties"] = fixed_props
                    node_name = node.get("name", f'node_{node.get("id", "unknown")}')
                    self.fixes_applied.append(
                        f"Fixed properties on {node_name} ({node_type}): {', '.join(self.property_validator.warnings)}"
                    )
            else:
                # Add default properties
                suggestions = self.property_validator.suggest_missing_properties(node_type, {})
                if suggestions:
                    node["properties"] = suggestions
                    self.fixes_applied.append(f"Added default properties to {node.get('name', 'Unnamed')} ({node_type})")

        return nodes

    def _add_missing_required_nodes(
        self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Add missing required nodes based on workflow patterns"""
        node_types = [n.get("type", "Unknown") for n in nodes]
        nodes_added = []

        # Check for missing colorization
        if "SatMap" not in node_types and any(t in node_types for t in ["Mountain", "Canyon", "Ridge"]):
            # Need to add TextureBase -> SatMap
            if "TextureBase" not in node_types:
                # Add TextureBase
                texture_node = self._create_node("TextureBase", len(nodes) + 100)
                nodes.append(texture_node)
                nodes_added.append("TextureBase")

            # Add SatMap
            satmap_node = self._create_node("SatMap", len(nodes) + 101)
            nodes.append(satmap_node)
            nodes_added.append("SatMap")

            # Connect them
            texture_id = next(n["id"] for n in nodes if n["type"] == "TextureBase")
            satmap_id = next(n["id"] for n in nodes if n["type"] == "SatMap")

            connections.append(
                {
                    "from_node": texture_id,
                    "to_node": satmap_id,
                    "from_port": "Out",
                    "to_port": "In",
                }
            )

            self.fixes_applied.append(f"Added missing colorization nodes: {', '.join(nodes_added)}")

        # Check for Rivers without Erosion
        if "Rivers" in node_types and "Erosion2" not in node_types:
            erosion_node = self._create_node("Erosion2", len(nodes) + 102)
            nodes.append(erosion_node)
            self.fixes_applied.append("Added Erosion2 node (required for Rivers)")

            # Connect before Rivers
            rivers_id = next(n["id"] for n in nodes if n["type"] == "Rivers")

            # Find what connects to Rivers
            for conn in connections:
                if conn["to_node"] == rivers_id:
                    # Insert erosion between
                    conn["to_node"] = erosion_node["id"]
                    connections.append(
                        {
                            "from_node": erosion_node["id"],
                            "to_node": rivers_id,
                            "from_port": "Out",
                            "to_port": "In",
                        }
                    )
                    break

        return nodes, connections

    def _fix_orphaned_nodes(
        self,
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]],
        aggressive: bool = False,
    ) -> List[Dict[str, Any]]:
        """Connect orphaned nodes based on patterns"""
        # Find orphaned nodes
        connected_ids = set()
        for conn in connections:
            connected_ids.add(conn["from_node"])
            connected_ids.add(conn["to_node"])

        orphaned = [n for n in nodes if n["id"] not in connected_ids]

        if not orphaned:
            return connections

        # Try to connect orphaned nodes
        for orphan in orphaned:
            orphan_type = orphan["type"]

            # Skip standalone nodes
            if orphan_type in ["Export", "Unity", "Unreal"]:
                continue

            # Find best connection based on patterns
            suggestions = get_next_node_suggestions(orphan_type)

            for suggestion in suggestions:
                target_type = suggestion["node"]
                # Find a node of this type
                target_nodes = [n for n in nodes if n["type"] == target_type and n["id"] != orphan["id"]]

                if target_nodes:
                    # Connect to first available
                    connections.append(
                        {
                            "from_node": orphan["id"],
                            "to_node": target_nodes[0]["id"],
                            "from_port": "Out",
                            "to_port": "In",
                        }
                    )
                    orphan_name = orphan.get("name", f'node_{orphan.get("id", "unknown")}')
                    target_name = target_nodes[0].get("name", f'node_{target_nodes[0].get("id", "unknown")}')
                    self.fixes_applied.append(f"Connected orphaned {orphan_name} to {target_name}")
                    break
            else:
                # No pattern match, try reverse connection
                for node in nodes:
                    if node["id"] == orphan["id"]:
                        continue

                    node_suggestions = get_next_node_suggestions(node["type"])
                    if any(s["node"] == orphan_type for s in node_suggestions):
                        connections.append(
                            {
                                "from_node": node["id"],
                                "to_node": orphan["id"],
                                "from_port": "Out",
                                "to_port": "In",
                            }
                        )
                        node_name = node.get("name", f'node_{node.get("id", "unknown")}')
                        orphan_name = orphan.get("name", f'node_{orphan.get("id", "unknown")}')
                        self.fixes_applied.append(f"Connected {node_name} to orphaned {orphan_name}")
                        break

        return connections

    def _optimize_workflow(
        self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Optimize workflow based on best practices"""

        # Optimization 1: Ensure proper node order
        node_types = [n.get("type", "Unknown") for n in nodes]

        # Check if erosion comes before rivers
        if "Erosion2" in node_types and "Rivers" in node_types:
            erosion_nodes = [n for n in nodes if n["type"] == "Erosion2"]
            rivers_nodes = [n for n in nodes if n["type"] == "Rivers"]

            # Make sure at least one erosion connects to rivers
            for river in rivers_nodes:
                river_id = river["id"]
                # Check if river has erosion input
                has_erosion_input = any(
                    conn["to_node"] == river_id
                    and any(n["id"] == conn["from_node"] and n["type"] == "Erosion2" for n in nodes)
                    for conn in connections
                )

                if not has_erosion_input and erosion_nodes:
                    # Connect nearest erosion to river
                    connections.append(
                        {
                            "from_node": erosion_nodes[0]["id"],
                            "to_node": river_id,
                            "from_port": "Out",
                            "to_port": "In",
                        }
                    )
                    self.fixes_applied.append("Connected Erosion2 to Rivers for proper water flow")

        # Optimization 2: Optimize properties for performance
        for node in nodes:
            if node["type"] in ["Erosion2", "Rivers", "Thermal2"]:
                original_props = node.get("properties", {}).copy()
                optimized_props = self.property_validator.get_performance_optimized_properties(node["type"], original_props)
                if optimized_props != original_props:
                    node["properties"] = optimized_props
                    node_name = node.get("name", f'node_{node.get("id", "unknown")}')
                    self.fixes_applied.append(f"Optimized {node_name} properties for performance")

        return nodes, connections

    def _ensure_export_node(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure project has an export node configured for .terrain output"""
        export_types = ["Export", "Unity", "Unreal"]

        # Check if there's already an Export node configured for terrain
        has_terrain_export = False
        for node in nodes:
            if node["type"] == "Export":
                # Check both old and new property structures
                props = node.get("properties", {})
                save_def = node.get("save_definition", {})

                # Check new structure (Format in properties)
                if props.get("Format") == "Terrain":
                    has_terrain_export = True
                    break
                # Check old structure (format in properties)
                elif props.get("format") == "Terrain":
                    has_terrain_export = True
                    break
                # Check save_definition
                elif save_def.get("format") == "Terrain":
                    has_terrain_export = True
                    break

        if not has_terrain_export:
            # Check if there's any export node at all
            export_nodes = [n for n in nodes if n["type"] in export_types]

            if not export_nodes:
                # Add new Export node with updated structure
                # Generate non-sequential ID for the Export node
                used_ids = [int(n.get("id", 0)) for n in nodes if str(n.get("id", "0")).isdigit()]
                export_id = generate_non_sequential_id(base=100, used_ids=used_ids)
                export_node = self._create_node("Export", export_id)
                export_node["name"] = "TerrainExport"
                export_node["properties"] = {
                    "Format": "Terrain",  # Use new property name
                }
                export_node["save_definition"] = {
                    "filename": "outputs/mcp-gaea2/terrain",
                    "format": "Terrain",
                    "enabled": True,
                }
                nodes.append(export_node)
                self.fixes_applied.append("Added Export node configured for .terrain output")
            else:
                # Update existing Export node to output terrain
                for node in export_nodes:
                    if node["type"] == "Export":
                        # Update to new structure
                        node["properties"]["Format"] = "Terrain"

                        # Ensure save_definition exists
                        if "save_definition" not in node:
                            node["save_definition"] = {}

                        node["save_definition"]["format"] = "Terrain"
                        node["save_definition"]["enabled"] = True
                        if "filename" not in node["save_definition"]:
                            node["save_definition"]["filename"] = "outputs/mcp-gaea2/terrain"

                        # Clean up old properties if they exist
                        if "format" in node["properties"]:
                            del node["properties"]["format"]
                        if "filename" in node["properties"]:
                            del node["properties"]["filename"]
                        if "enabled" in node["properties"]:
                            del node["properties"]["enabled"]

                        self.fixes_applied.append(
                            f"Updated {node.get('name', 'Export')} to export .terrain format with new structure"
                        )
                        break

        return nodes

    def _create_node(self, node_type: str, node_id: int) -> Dict[str, Any]:
        """Create a new node with default properties"""
        node = {
            "id": node_id,
            "type": node_type,
            "name": node_type,
            "position": {"x": 25000 + (node_id % 10) * 1000, "y": 25000},
            "properties": {},
        }

        # Add default properties
        props = suggest_properties_for_node(node_type)
        node_properties = node["properties"]
        assert isinstance(node_properties, dict)  # Type hint for mypy
        for prop_name, prop_info in props.items():
            if isinstance(prop_info, dict) and "default" in prop_info:
                node_properties[prop_name] = prop_info["default"]

        return node

    def _get_essential_properties(self, node_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Get the most essential properties for a node type (max 3)"""
        # Define essential properties for each limited node type
        essential_props_map = {
            "Snow": ["Duration", "SnowLine", "Melt"],
            "Beach": ["Width", "Slope"],
            "Coast": ["Width", "Height", "Slope"],
            "Lakes": ["Count", "Size"],
            "Glacier": ["Flow", "Depth", "Melt"],
            "SeaLevel": ["Level", "Swell"],
            "LavaFlow": ["Temperature", "Viscosity"],
            "ThermalShatter": ["Intensity", "Scale"],
            "Ridge": ["Scale", "Complexity"],
            "Strata": ["Layers", "Scale", "Distortion"],
            "Voronoi": ["Scale", "Cells", "Randomness"],
            "Terrace": ["Steps", "Sharpness", "Uniformity"],
        }

        essential_keys = essential_props_map.get(node_type, [])

        # If we have defined essential properties, use them
        if essential_keys:
            result = {}
            for key in essential_keys:
                if key in properties:
                    result[key] = properties[key]
            # If we have fewer than 3, add some other properties
            if len(result) < 3:
                for key, value in properties.items():
                    if key not in result and len(result) < 3:
                        result[key] = value
            return result
        else:
            # For unknown nodes, just take the first 3 properties
            return dict(list(properties.items())[:3])

    def fix_workflow(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fix workflow issues automatically"""
        # Nodes that must have <= 3 properties to open in Gaea2
        PROPERTY_LIMITED_NODES = {
            "Snow",
            "Beach",
            "Coast",
            "Lakes",
            "Glacier",
            "SeaLevel",
            "LavaFlow",
            "ThermalShatter",
            "Ridge",
            "Strata",
            "Voronoi",
            "Terrace",
        }

        fixed_nodes = self._fix_node_properties(nodes)
        fixed_connections = self._fix_duplicate_connections(connections)
        # Do NOT add Export nodes - they aren't needed for working files
        # fixed_nodes = self._ensure_export_node(fixed_nodes)

        fixes_applied = []
        if len(fixed_connections) != len(connections):
            fixes_applied.append("Removed duplicate connections")
        if len(fixed_nodes) != len(nodes):
            fixes_applied.append("Added missing Export node")

        # Check if properties were fixed
        for i, node in enumerate(nodes):
            if i < len(fixed_nodes) and node.get("properties", {}) != fixed_nodes[i].get("properties", {}):
                fixes_applied.append(f"Fixed properties for {node.get('type', 'unknown')} node")
                break

        # Fix property count limits for problematic nodes
        for node in fixed_nodes:
            node_type = node.get("type")
            if node_type in PROPERTY_LIMITED_NODES:
                props = node.get("properties", {})
                if len(props) > 3:
                    # Get the most important properties for this node type
                    essential_props = self._get_essential_properties(node_type, props)
                    node["properties"] = essential_props
                    fixes_applied.append(f"Limited {node_type} node to 3 essential properties (had {len(props)})")
                    logger.warning(f"Node {node_type} had {len(props)} properties, limited to 3 for Gaea2 compatibility")

        return {
            "nodes": fixed_nodes,
            "connections": fixed_connections,
            "fixed": len(fixes_applied) > 0,
            "fixes_applied": fixes_applied,
        }

    def suggest_fixes(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Suggest fixes without applying them"""
        suggestions = []

        # Check properties
        for node in nodes:
            node_type = node.get("type", "")
            properties = node.get("properties", {})

            is_valid, errors, fixed_props = self.property_validator.validate_properties(node_type, properties)

            if errors:
                suggestions.append(
                    {
                        "type": "property_error",
                        "node": node["name"],
                        "errors": errors,
                        "fix": "Update properties according to schema",
                    }
                )

        # Check connections
        is_valid, errors, warnings = self.connection_validator.validate_connections(nodes, connections)

        for error in errors:
            suggestions.append(
                {
                    "type": "connection_error",
                    "error": error,
                    "fix": "Fix connection references",
                }
            )

        for warning in warnings:
            suggestions.append(
                {
                    "type": "connection_warning",
                    "warning": warning,
                    "fix": "Consider adjusting connections",
                }
            )

        # Check for missing nodes
        node_types = [n.get("type", "Unknown") for n in nodes]

        if not any(t in ["Export", "Unity", "Unreal"] for t in node_types):
            suggestions.append(
                {
                    "type": "missing_node",
                    "node_type": "Export",
                    "fix": "Add Export node to save terrain",
                }
            )

        if "SatMap" not in node_types:
            suggestions.append(
                {
                    "type": "missing_node",
                    "node_type": "SatMap",
                    "fix": "Add SatMap for terrain colorization",
                }
            )

        return suggestions
