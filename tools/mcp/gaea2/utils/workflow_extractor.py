"""
Common workflow extraction utilities for Gaea2 projects.

This module provides a centralized implementation for extracting nodes and connections
from Gaea2 project data, reducing code duplication across the codebase.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from ..exceptions import Gaea2ParseError, Gaea2StructureError

logger = logging.getLogger(__name__)


class WorkflowExtractor:
    """Extracts workflow information from Gaea2 project data"""

    @staticmethod
    def extract_workflow(
        project_data: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Extract nodes and connections from project data.

        Args:
            project_data: The Gaea2 project data dictionary

        Returns:
            Tuple of (nodes, connections) where:
                - nodes: List of node dictionaries with id, type, name, and properties
                - connections: List of connection dictionaries with from/to nodes and ports
        """
        nodes: List[Dict[str, Any]] = []
        connections: List[Dict[str, Any]] = []

        try:
            # Navigate the project structure
            terrain = WorkflowExtractor._get_terrain_data(project_data)
            if not terrain:
                return nodes, connections

            nodes_dict = terrain.get("Nodes", {})

            # Extract nodes
            nodes = WorkflowExtractor._extract_nodes(nodes_dict)

            # Extract connections
            connections = WorkflowExtractor._extract_connections(nodes_dict)

            return nodes, connections

        except Gaea2ParseError:
            # Re-raise parse errors
            raise
        except Exception as e:
            logger.error(f"Failed to extract workflow: {str(e)}")
            raise Gaea2ParseError(f"Failed to extract workflow: {str(e)}") from e

    @staticmethod
    def _get_terrain_data(project_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Navigate project structure to find terrain data"""
        if not isinstance(project_data, dict):
            raise Gaea2StructureError("Project data must be a dictionary")

        # Try to get Assets
        assets = project_data.get("Assets", {})

        # Handle both direct assets and $values format
        if "$values" in assets and isinstance(assets["$values"], list):
            assets_list = assets["$values"]
            if assets_list and isinstance(assets_list[0], dict):
                terrain = assets_list[0].get("Terrain", {})
                return terrain if isinstance(terrain, dict) else {}

        # Some projects might have terrain directly
        terrain = project_data.get("Terrain", {})
        if terrain and isinstance(terrain, dict):
            # Explicit type assertion for mypy
            terrain_dict: Dict[str, Any] = terrain
            return terrain_dict

        # Try legacy format
        if isinstance(assets, dict) and "$values" not in assets:
            # Look for first asset with Terrain
            for key, value in assets.items():
                if isinstance(value, dict) and "Terrain" in value:
                    terrain_data = value["Terrain"]
                    return terrain_data if isinstance(terrain_data, dict) else None

        return None

    @staticmethod
    def _extract_nodes(nodes_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract nodes from nodes dictionary"""
        nodes = []

        for node_id, node_data in nodes_dict.items():
            # Skip non-dict entries
            if not isinstance(node_data, dict):
                continue

            # Extract node type from $type field
            node_type = WorkflowExtractor._extract_node_type(node_data)

            node = {
                "id": node_data.get("Id", int(node_id) if node_id.isdigit() else 1),
                "type": node_type,
                "name": node_data.get("Name", ""),
                "properties": WorkflowExtractor._extract_properties(node_data),
                "position": node_data.get("Position", {}),
            }

            nodes.append(node)

        return nodes

    @staticmethod
    def _extract_node_type(node_data: Dict[str, Any]) -> str:
        """Extract and clean node type from node data"""
        node_type_raw = node_data.get("$type", "")
        node_type = str(node_type_raw) if node_type_raw else ""

        if not node_type:
            return "Unknown"

        # Extract type from full class name
        parts = node_type.split(".")
        if len(parts) >= 2:
            node_type = parts[-2]

        # Remove ", Gaea" suffix if present
        if node_type.endswith(", Gaea"):
            node_type = node_type[:-6]

        return node_type

    @staticmethod
    def _extract_properties(node_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract properties from node data"""
        properties = {}

        # List of keys that are not properties
        system_keys = {
            "$id",
            "$type",
            "Id",
            "Name",
            "Position",
            "Ports",
            "Modifiers",
            "SnapIns",
            "NodeSize",
            "PortCount",
            "IsMaskable",
        }

        for key, value in node_data.items():
            if key not in system_keys:
                properties[key] = value

        return properties

    @staticmethod
    def _extract_connections(nodes_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract connections from node ports"""
        connections = []

        for node_id, node_data in nodes_dict.items():
            # Skip non-dict entries
            if not isinstance(node_data, dict):
                continue

            ports = node_data.get("Ports", {})
            port_values = ports.get("$values", []) if isinstance(ports, dict) else []

            for port in port_values:
                if not isinstance(port, dict):
                    continue

                record = port.get("Record")
                if record and isinstance(record, dict):
                    connection = {
                        "from_node": record.get("From"),
                        "to_node": record.get("To"),
                        "from_port": record.get("FromPort", "Out"),
                        "to_port": record.get("ToPort", "In"),
                    }

                    # Only add if we have valid from/to nodes
                    if connection["from_node"] is not None and connection["to_node"] is not None:
                        connections.append(connection)

        return connections

    @staticmethod
    def analyze_workflow_structure(nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze workflow structure for common patterns and issues.

        Args:
            nodes: List of node dictionaries
            connections: List of connection dictionaries

        Returns:
            Dictionary with analysis results including:
                - node_count: Number of nodes
                - connection_count: Number of connections
                - orphaned_nodes: Nodes with no connections
                - start_nodes: Nodes with no incoming connections
                - end_nodes: Nodes with no outgoing connections
                - node_types: Count of each node type
        """
        analysis: Dict[str, Any] = {
            "node_count": len(nodes),
            "connection_count": len(connections),
            "orphaned_nodes": [],
            "start_nodes": [],
            "end_nodes": [],
            "node_types": {},
        }

        # Build connection maps
        incoming = {conn["to_node"] for conn in connections}
        outgoing = {conn["from_node"] for conn in connections}

        # Count node types and find special nodes
        for node in nodes:
            # Count node types
            node_type = node["type"]
            analysis["node_types"][node_type] = analysis["node_types"].get(node_type, 0) + 1

            node_id = node["id"]

            # Check for orphaned nodes
            if node_id not in incoming and node_id not in outgoing:
                analysis["orphaned_nodes"].append(node)

            # Check for start nodes (no incoming)
            if node_id not in incoming and node_id in outgoing:
                analysis["start_nodes"].append(node)

            # Check for end nodes (no outgoing)
            if node_id in incoming and node_id not in outgoing:
                analysis["end_nodes"].append(node)

        return analysis
