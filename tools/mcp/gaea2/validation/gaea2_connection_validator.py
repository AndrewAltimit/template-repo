#!/usr/bin/env python3
"""
Connection validation for Gaea2 workflows based on real patterns
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from ..utils.gaea2_pattern_knowledge import COMMON_NODE_SEQUENCES, NODE_CONNECTION_FREQUENCY, WORKFLOW_TEMPLATES

logger = logging.getLogger(__name__)


class Gaea2ConnectionValidator:
    """Validates and suggests connections based on real workflow patterns"""

    def __init__(self):
        self.warnings = []
        self.suggestions = []

    def validate_workflow(self, workflow: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate workflow connections (wrapper for compatibility)

        Returns:
            - is_valid: Whether connections are valid
            - errors: List of error messages
        """
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", [])
        is_valid, errors, warnings = self.validate_connections(nodes, connections)
        # Return only validity and errors for compatibility
        return is_valid, errors

    def validate_connections(
        self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate connections in a workflow

        Returns:
            - is_valid: Whether connections are valid
            - errors: List of error messages
            - warnings: List of warning messages
        """
        errors = []
        warnings = []

        # Build lookup structures
        node_map = {n.get("id", f"node_{i}"): n for i, n in enumerate(nodes)}
        node_types = {n.get("id", f"node_{i}"): n.get("type", "Unknown") for i, n in enumerate(nodes)}

        # Check basic connection validity
        for conn in connections:
            # Handle both formats: from_node/to_node and source/target
            from_id = conn.get("from_node") or conn.get("source")
            to_id = conn.get("to_node") or conn.get("target")

            # Check if nodes exist
            if from_id not in node_map:
                errors.append(f"Connection references non-existent source node ID: {from_id}")
                continue
            if to_id not in node_map:
                errors.append(f"Connection references non-existent target node ID: {to_id}")
                continue

            from_type = node_types[from_id]
            to_type = node_types[to_id]

            # Check if connection makes sense based on patterns
            if from_type in NODE_CONNECTION_FREQUENCY:
                valid_targets = NODE_CONNECTION_FREQUENCY[from_type]
                if to_type not in valid_targets:
                    # Check if it's in common sequences
                    if from_type in COMMON_NODE_SEQUENCES:
                        if to_type not in COMMON_NODE_SEQUENCES[from_type]:
                            warnings.append(
                                f"Unusual connection: {from_type} → {to_type} "
                                f"(common: {', '.join(list(valid_targets.keys())[:3])})"
                            )
                else:
                    # Connection exists but might be rare
                    probability = valid_targets[to_type]
                    # Ensure probability is numeric for comparison
                    if isinstance(probability, str):
                        try:
                            probability = float(probability)
                        except ValueError:
                            probability = 0.5  # Default if conversion fails
                    if probability < 0.1:
                        warnings.append(f"Rare connection: {from_type} → {to_type} " f"(only {probability:.0%} of cases)")

        # Check for orphaned nodes
        connected_ids = set()
        for conn in connections:
            # Handle both formats
            from_id = conn.get("from_node") or conn.get("source")
            to_id = conn.get("to_node") or conn.get("target")
            connected_ids.add(from_id)
            connected_ids.add(to_id)

        for node in nodes:
            node_id = node.get("id", f"node_{nodes.index(node)}")
            if node_id not in connected_ids:
                node_type = node.get("type", "Unknown")
                # Some nodes can be standalone
                standalone_types = ["Export", "Unity", "Unreal", "File"]
                if node_type not in standalone_types:
                    node_name = node.get("name", f"node_{node_id}")
                    warnings.append(f"Node '{node_name}' ({node_type}) is not connected")

        # Check for cycles
        cycles = self._detect_cycles(connections)
        if cycles:
            for cycle in cycles:
                # Cycles are errors in Gaea2, not just warnings
                errors.append(f"Circular dependency detected: {' → '.join(str(n) for n in cycle)}")
                logger.warning(f"Detected circular dependency: {cycle}")

        # Check for missing common patterns
        self._check_workflow_patterns(nodes, connections, warnings)

        self.warnings = warnings
        is_valid = len(errors) == 0

        return is_valid, errors, warnings

    def suggest_connections(
        self, nodes: List[Dict[str, Any]], existing_connections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Suggest missing connections based on patterns"""
        suggestions = []

        # Build existing connection map
        existing = set()
        for conn in existing_connections:
            existing.add((conn["from_node"], conn["to_node"]))

        # Check each node for missing connections

        for node in nodes:
            node_id = node.get("id", f"node_{nodes.index(node)}")
            node_type = node.get("type", "Unknown")

            # Skip if node already has outgoing connections
            has_outgoing = any(conn["from_node"] == node_id for conn in existing_connections)

            if not has_outgoing and node_type in NODE_CONNECTION_FREQUENCY:
                # Get most likely target
                targets = NODE_CONNECTION_FREQUENCY[node_type]

                # Find nodes of target types
                for target_node in nodes:
                    if target_node["id"] == node_id:
                        continue

                    target_type = target_node.get("type", "Unknown")
                    if target_type in targets:
                        probability = targets[target_type]

                        # Check if connection already exists
                        if (node_id, target_node["id"]) not in existing:
                            suggestions.append(
                                {
                                    "from_node": node_id,
                                    "to_node": target_node["id"],
                                    "from_type": node_type,
                                    "to_type": target_type,
                                    "probability": probability,
                                    "reason": f"Common pattern: {node_type} → {target_type} ({probability:.0%})",
                                }
                            )

        # Sort by probability
        suggestions.sort(key=lambda x: x["probability"], reverse=True)
        self.suggestions = suggestions

        return suggestions[:5]  # Return top 5 suggestions

    def optimize_connections(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Optimize connections for better workflow"""
        optimized = []

        # Remove redundant connections
        seen = set()
        for conn in connections:
            key = (conn["from_node"], conn["to_node"])
            if key not in seen:
                seen.add(key)
                optimized.append(conn)

        # Check for bypass opportunities
        # (e.g., A→B→C where A→C would be more efficient)
        node_types = {n.get("id", f"node_{i}"): n.get("type", "Unknown") for i, n in enumerate(nodes)}

        # Build adjacency for path finding
        adjacency = defaultdict(list)
        for conn in optimized:
            adjacency[conn["from_node"]].append(conn["to_node"])

        # Look for long chains that could be shortened
        for start_node in nodes:
            if start_node.get("type", "Unknown") in [
                "Mountain",
                "Canyon",
                "Ridge",
                "Island",
            ]:
                # These are typically starting nodes
                paths = self._find_paths_to_type(
                    start_node.get("id", ""),
                    "SatMap",
                    adjacency,
                    node_types,
                    max_length=6,
                )

                if paths:
                    shortest = min(paths, key=len)
                    if len(shortest) > 4:
                        logger.info(f"Long path detected from {start_node['type']} to SatMap: " f"{len(shortest)} nodes")

        return optimized

    def _detect_cycles(self, connections: List[Dict[str, Any]]) -> List[List[int]]:
        """Detect cycles in the connection graph"""
        # Build adjacency list
        graph = defaultdict(list)
        for conn in connections:
            # Handle both formats
            from_node = conn.get("from_node") or conn.get("source")
            to_node = conn.get("to_node") or conn.get("target")
            graph[from_node].append(to_node)

        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node, path):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor, path.copy()):
                        return True
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])

            rec_stack.remove(node)
            return False

        # Check all nodes - use list() to avoid dictionary size change during iteration
        for node in list(graph.keys()):
            if node not in visited:
                dfs(node, [])

        return cycles

    def _check_workflow_patterns(
        self,
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]],
        warnings: List[str],
    ):
        """Check for missing common workflow patterns"""
        node_types = [n.get("type", "Unknown") for n in nodes]

        # Check for common required nodes
        if "Erosion2" in node_types and "TextureBase" not in node_types:
            warnings.append("Workflow has Erosion2 but no TextureBase (usually needed for texturing)")

        if any(t in node_types for t in ["Mountain", "Canyon", "Ridge"]) and "SatMap" not in node_types:
            warnings.append("Terrain generator present but no SatMap for colorization")

        if "Rivers" in node_types and "Erosion2" not in node_types:
            warnings.append("Rivers node without Erosion2 (Rivers usually follows erosion)")

        # Check for export nodes
        export_types = ["Export", "Unity", "Unreal"]
        if not any(n.get("type", "Unknown") in export_types for n in nodes):
            warnings.append("No export node found - add Export node to save terrain")

    def _find_paths_to_type(
        self,
        start: int,
        target_type: str,
        adjacency: Dict[int, List[int]],
        node_types: Dict[int, str],
        max_length: int = 10,
    ) -> List[List[int]]:
        """Find all paths from start node to any node of target type"""
        paths = []

        def dfs(current, path, visited):
            if len(path) > max_length:
                return

            if node_types.get(current) == target_type and len(path) > 1:
                paths.append(path.copy())
                return

            for neighbor in adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    path.append(neighbor)
                    dfs(neighbor, path, visited)
                    path.pop()
                    visited.remove(neighbor)

        dfs(start, [start], {start})
        return paths

    def get_connection_quality_score(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> float:
        """Calculate a quality score for the connections (0-100)"""
        score = 100.0

        node_types = {n.get("id", f"node_{i}"): n.get("type", "Unknown") for i, n in enumerate(nodes)}

        # Penalize unusual connections
        for conn in connections:
            from_type = node_types.get(conn["from_node"])
            to_type = node_types.get(conn["to_node"])

            if from_type and to_type and from_type in NODE_CONNECTION_FREQUENCY:
                if to_type in NODE_CONNECTION_FREQUENCY[from_type]:
                    probability = NODE_CONNECTION_FREQUENCY[from_type][to_type]
                    # Ensure probability is numeric
                    if isinstance(probability, str):
                        try:
                            probability = float(probability)
                        except ValueError:
                            probability = 0.5
                    if probability < 0.1:
                        score -= 5  # Rare connection
                else:
                    score -= 10  # Unusual connection

        # Penalize orphaned nodes
        connected_ids = set()
        for conn in connections:
            connected_ids.add(conn["from_node"])
            connected_ids.add(conn["to_node"])

        orphaned_count = sum(1 for n in nodes if n["id"] not in connected_ids)
        score -= orphaned_count * 10

        # Bonus for following common patterns
        node_sequence = self._extract_main_sequence(nodes, connections)
        for template in WORKFLOW_TEMPLATES.values():
            if isinstance(template, dict) and "nodes" in template:
                if self._sequence_matches_template(node_sequence, template["nodes"]):
                    score += 10
                    break

        return max(0.0, min(100.0, score))

    def _extract_main_sequence(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> List[str]:
        """Extract the main node sequence from the workflow"""
        if not nodes or not connections:
            return []

        # Find start nodes (no incoming connections)
        incoming = {c["to_node"] for c in connections}
        start_nodes = [n for n in nodes if n["id"] not in incoming]

        if not start_nodes:
            start_nodes = [nodes[0]]

        # Follow main path
        sequence = []
        current: Optional[Dict[str, Any]] = start_nodes[0]
        visited = set()

        while current and current["id"] not in visited:
            sequence.append(current["type"])
            visited.add(current["id"])

            # Find next node
            next_conn = next((c for c in connections if c["from_node"] == current["id"]), None)
            if next_conn:
                current = next((n for n in nodes if n["id"] == next_conn["to_node"]), None)
            else:
                current = None

        return sequence

    def _sequence_matches_template(self, sequence: List[str], template: List[str]) -> bool:
        """Check if a sequence matches a template pattern"""
        if len(sequence) < len(template):
            return False

        # Check if template is a subsequence
        j = 0
        for i in range(len(sequence)):
            if j < len(template) and sequence[i] == template[j]:
                j += 1

        return j == len(template)
