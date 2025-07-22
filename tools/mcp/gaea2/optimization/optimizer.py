"""Gaea2 workflow optimizer"""

import logging
from typing import Any, Dict, List

# Use stubs for now
from ..stubs import Gaea2PropertyValidator, OptimizedGaea2Validator


class Gaea2Optimizer:
    """Optimize Gaea2 workflows for performance or quality"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.validator = OptimizedGaea2Validator()
        self.property_validator = Gaea2PropertyValidator()

    async def optimize_nodes(self, nodes: List[Dict[str, Any]], mode: str = "balanced") -> List[Dict[str, Any]]:
        """Optimize node properties based on mode"""

        optimized_nodes = []

        for node in nodes:
            node_type = node.get("type", node.get("node_type"))
            if not node_type:
                # Skip nodes without a type
                self.logger.warning("Node without type found, skipping optimization")
                optimized_nodes.append(node.copy())
                continue

            properties = node.get("properties", {})

            # Optimize based on mode
            if mode == "performance":
                optimized_props = self._optimize_for_performance(node_type, properties)
            elif mode == "quality":
                optimized_props = self._optimize_for_quality(node_type, properties)
            else:  # balanced
                optimized_props = self._optimize_balanced(node_type, properties)

            optimized_node = node.copy()
            optimized_node["properties"] = optimized_props
            optimized_nodes.append(optimized_node)

        return optimized_nodes

    def _optimize_for_performance(self, node_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize properties for faster generation"""
        optimized = properties.copy()

        # Lower quality settings for performance
        if node_type == "Erosion2":
            optimized["Duration"] = min(properties.get("Duration", 15), 10)
            optimized["Downcutting"] = min(properties.get("Downcutting", 0.5), 0.3)

        elif node_type == "SatMap":
            # Use lower resolution for previews
            if "Resolution" in optimized:
                optimized["Resolution"] = min(optimized["Resolution"], 1024)

        return optimized

    def _optimize_for_quality(self, node_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize properties for best quality"""
        optimized = properties.copy()

        # Higher quality settings
        if node_type == "Erosion2":
            optimized["Duration"] = max(properties.get("Duration", 15), 25)
            optimized["Downcutting"] = max(properties.get("Downcutting", 0.5), 0.7)

        elif node_type == "SatMap":
            # Use higher resolution
            if "Resolution" in optimized:
                optimized["Resolution"] = max(optimized["Resolution"], 2048)

        return optimized

    def _optimize_balanced(self, node_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Balance between performance and quality"""
        # For now, just validate and correct properties
        _, _, corrected = self.property_validator.validate_properties(node_type, properties)
        # Ensure we're returning a dict
        if not isinstance(corrected, dict):
            return properties.copy()
        return corrected
