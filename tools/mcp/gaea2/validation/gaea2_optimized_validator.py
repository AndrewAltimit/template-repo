"""
Optimized Gaea2 validation with caching and efficient data structures
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, cast

from ..schema.gaea2_schema import NODE_PROPERTY_DEFINITIONS, validate_node_properties
from ..utils.gaea2_cache import Gaea2Cache
from ..utils.gaea2_connection_utils import normalize_connections


class OptimizedGaea2Validator:
    """Optimized validator with caching and efficient data structures."""

    def __init__(self):
        self.cache = Gaea2Cache()
        self._validation_cache = {}
        self._property_cache_hits = 0
        self._connection_cache_hits = 0

    def validate_workflow(
        self,
        nodes: List[Dict[str, Any]],
        connections: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Optimized workflow validation with caching and efficient lookups.

        Returns:
            Dictionary with validation results
        """
        # Normalize connections once
        normalized_conns: List[Dict[str, Any]] = []
        if connections:
            normalized_conns = normalize_connections(connections)

        # Build lookup structures once
        lookup_structures = self._build_lookup_structures(nodes, normalized_conns)

        # Validate nodes with caching
        node_results = self._validate_nodes_batch(nodes, lookup_structures)

        # Validate connections efficiently
        connection_results = self._validate_connections_batch(normalized_conns, lookup_structures)

        # Combine results
        all_errors = node_results["errors"] + connection_results["errors"]
        all_warnings = node_results["warnings"] + connection_results["warnings"]

        return {
            "valid": len(all_errors) == 0,
            "errors": all_errors,
            "warnings": all_warnings,
            "fixed_nodes": node_results["fixed_nodes"],
            "stats": {
                "nodes_validated": len(nodes),
                "connections_validated": len(normalized_conns),
                "cache_hits": self._get_cache_stats(),
            },
        }

    def _build_lookup_structures(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build all lookup structures in a single pass."""
        node_by_id = {}
        node_type_by_id = {}
        node_name_by_id = {}
        connections_by_source = defaultdict(list)
        connections_by_target = defaultdict(list)
        node_ids = set()

        # Single pass over nodes
        for node in nodes:
            node_id = node.get("id")
            if node_id is not None:
                node_by_id[node_id] = node
                node_type_by_id[node_id] = node.get("type", "Unknown")
                node_name_by_id[node_id] = node.get("name", f"Node_{node_id}")
                node_ids.add(node_id)

        # Single pass over connections
        for conn in connections:
            from_id = conn.get("from_node")
            to_id = conn.get("to_node")
            if from_id is not None:
                connections_by_source[from_id].append(conn)
            if to_id is not None:
                connections_by_target[to_id].append(conn)

        # Calculate derived sets efficiently
        connected_node_ids = set(connections_by_source.keys()) | set(connections_by_target.keys())
        orphaned_node_ids = node_ids - connected_node_ids

        return {
            "node_by_id": node_by_id,
            "node_type_by_id": node_type_by_id,
            "node_name_by_id": node_name_by_id,
            "connections_by_source": connections_by_source,
            "connections_by_target": connections_by_target,
            "node_ids": node_ids,
            "connected_node_ids": connected_node_ids,
            "orphaned_node_ids": orphaned_node_ids,
        }

    def _validate_nodes_batch(self, nodes: List[Dict[str, Any]], lookup: Dict[str, Any]) -> Dict[str, Any]:
        """Validate all nodes in a single efficient pass."""
        errors = []
        warnings = []
        fixed_nodes = []

        for node in nodes:
            node_type = node.get("type", "Unknown")
            node_id = node.get("id")
            node_name = node.get("name", f"Node_{node_id}")
            properties = node.get("properties", {})

            # Check cache first
            cache_key = self._get_node_cache_key(node_type, properties)
            if cache_key in self._validation_cache:
                self._property_cache_hits += 1
                cached_result = self._validation_cache[cache_key]
                if cached_result["errors"]:
                    errors.extend([f"Node '{node_name}': {e}" for e in cached_result["errors"]])
                if cached_result["warnings"]:
                    warnings.extend([f"Node '{node_name}': {w}" for w in cached_result["warnings"]])
                if cached_result.get("fixed_properties"):
                    fixed_node = node.copy()
                    fixed_node["properties"] = cached_result["fixed_properties"]
                    fixed_nodes.append(fixed_node)
                continue

            # Validate properties
            node_errors, node_warnings = validate_node_properties(node_type, properties)

            # Apply default properties efficiently
            fixed_properties = self._apply_defaults_efficiently(node_type, properties)

            # Cache the result
            self._validation_cache[cache_key] = {
                "errors": node_errors,
                "warnings": node_warnings,
                "fixed_properties": (fixed_properties if fixed_properties != properties else None),
            }

            # Add to results
            if node_errors:
                errors.extend([f"Node '{node_name}': {e}" for e in node_errors])
            if node_warnings:
                warnings.extend([f"Node '{node_name}': {w}" for w in node_warnings])
            if fixed_properties and fixed_properties != properties:
                fixed_node = node.copy()
                fixed_node["properties"] = fixed_properties
                fixed_nodes.append(fixed_node)

        return {"errors": errors, "warnings": warnings, "fixed_nodes": fixed_nodes}

    def _validate_connections_batch(self, connections: List[Dict[str, Any]], lookup: Dict[str, Any]) -> Dict[str, Any]:
        """Validate all connections efficiently."""
        errors = []
        warnings = []

        # Pre-calculate valid connections set for duplicate detection
        seen_connections = set()

        for conn in connections:
            from_id = conn.get("from_node")
            to_id = conn.get("to_node")
            from_port = conn.get("from_port", "Out")
            to_port = conn.get("to_port", "In")

            # Quick existence check using lookup
            if from_id not in lookup["node_ids"]:
                errors.append(f"Connection references non-existent source node: {from_id}")
                continue
            if to_id not in lookup["node_ids"]:
                errors.append(f"Connection references non-existent target node: {to_id}")
                continue

            # Duplicate detection using set
            conn_key = (from_id, to_id, from_port, to_port)
            if conn_key in seen_connections:
                warnings.append(
                    f"Duplicate connection: {lookup['node_name_by_id'][from_id]} -> " f"{lookup['node_name_by_id'][to_id]}"
                )
            else:
                seen_connections.add(conn_key)

            # Port compatibility check (simplified for now)
            from_type = lookup["node_type_by_id"][from_id]
            to_type = lookup["node_type_by_id"][to_id]

            # Basic compatibility rules
            if not self._check_port_compatibility(from_type, to_type, from_port, to_port):
                warnings.append(f"Potentially incompatible connection: {from_type}:{from_port} -> " f"{to_type}:{to_port}")

        return {"errors": errors, "warnings": warnings}

    def _get_node_cache_key(self, node_type: str, properties: Dict[str, Any]) -> str:
        """Generate a cache key for node validation results."""
        # Create a stable key from node type and properties
        # Convert dict to a hashable string representation
        import json

        prop_str = json.dumps(properties, sort_keys=True)
        return f"{node_type}:{hash(prop_str)}"

    def _apply_defaults_efficiently(self, node_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default properties efficiently."""
        if node_type not in NODE_PROPERTY_DEFINITIONS:
            return properties

        # Only copy if we need to add defaults
        prop_defs = cast(Dict[str, Any], NODE_PROPERTY_DEFINITIONS[node_type])
        needs_update = False

        for prop_name, prop_def in prop_defs.items():
            if prop_name not in properties and "default" in prop_def:
                needs_update = True
                break

        if not needs_update:
            return properties

        # Create copy and add defaults
        fixed_props = properties.copy()
        for prop_name, prop_def in prop_defs.items():
            if prop_name not in fixed_props and "default" in prop_def:
                fixed_props[prop_name] = prop_def["default"]

        return fixed_props

    def _check_port_compatibility(self, from_type: str, to_type: str, from_port: str, to_port: str) -> bool:
        """Check if ports are compatible (simplified version)."""
        # Basic rules for common cases
        if from_port == "Out" and to_port == "In":
            return True
        if from_port == "Mask" and to_port == "Mask":
            return True
        if to_port.startswith("in") and from_port == "Out":
            return True  # Multi-input nodes
        return False

    def _get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "validation_cache_size": len(self._validation_cache),
            "property_cache_hits": self._property_cache_hits,
            "connection_cache_hits": self._connection_cache_hits,
            "gaea2_cache_size": len(self.cache.cache),
        }


# Singleton instance for reuse
_optimized_validator_instance = None


def get_optimized_validator() -> OptimizedGaea2Validator:
    """Get or create the singleton optimized validator instance."""
    global _optimized_validator_instance
    if _optimized_validator_instance is None:
        _optimized_validator_instance = OptimizedGaea2Validator()
    return _optimized_validator_instance
