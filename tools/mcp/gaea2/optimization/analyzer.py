"""Gaea2 workflow analyzer"""

import logging
from collections import Counter
from typing import Any, Dict, List, Optional

# Use stubs for now
from ..stubs import knowledge_graph  # noqa: F401
from ..stubs import COMMON_NODE_SEQUENCES, NODE_COMPATIBILITY, PROPERTY_RANGES  # noqa: F401
from ..stubs import Gaea2WorkflowAnalyzer as OriginalAnalyzer


class Gaea2WorkflowAnalyzer:
    """Analyze Gaea2 workflows for patterns and improvements"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.original_analyzer = OriginalAnalyzer()

    async def analyze(self, workflow: Dict[str, Any], analysis_type: str = "all") -> Dict[str, Any]:
        """Analyze workflow based on type"""

        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", [])

        analysis = {}

        if analysis_type in ["patterns", "all"]:
            analysis["patterns"] = self._analyze_patterns(nodes, connections)

        if analysis_type in ["performance", "all"]:
            analysis["performance"] = self._analyze_performance(nodes)

        if analysis_type in ["quality", "all"]:
            analysis["quality"] = self._analyze_quality(nodes)

        return analysis

    def _analyze_patterns(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze workflow patterns"""

        node_types = [n.get("type", n.get("node_type", "")) for n in nodes]
        # Filter out empty strings to ensure we only have valid node types
        node_types = [nt for nt in node_types if nt]

        # Find common sequences
        found_sequences = []
        for seq_name, sequence in COMMON_NODE_SEQUENCES.items():
            if self._contains_sequence(node_types, sequence):
                found_sequences.append(seq_name)

        # Analyze node distribution
        node_distribution = Counter(node_types)

        return {
            "node_count": len(nodes),
            "connection_count": len(connections),
            "common_sequences": found_sequences,
            "node_distribution": dict(node_distribution),
            "most_used_nodes": node_distribution.most_common(5),
        }

    def _analyze_performance(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance characteristics"""

        heavy_nodes = []
        for node in nodes:
            node_type = node.get("type", node.get("node_type"))

            # Identify computationally expensive nodes
            if node_type in ["Erosion2", "Rivers", "Snow", "Vegetation"]:
                heavy_nodes.append({"id": node.get("id", node.get("node_id")), "type": node_type})

        return {
            "heavy_nodes": heavy_nodes,
            "estimated_complexity": self._estimate_complexity(nodes),
            "optimization_suggestions": self._get_performance_suggestions(nodes),
        }

    def _analyze_quality(self, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze quality characteristics"""

        quality_issues = []

        # Check for missing essential nodes
        node_types = [n.get("type", n.get("node_type")) for n in nodes]

        if "Export" not in node_types:
            quality_issues.append("Missing Export node")

        if "SatMap" not in node_types and "ColorTerrain" not in node_types:
            quality_issues.append("Missing color/texture node")

        return {
            "quality_issues": quality_issues,
            "enhancement_suggestions": self._get_quality_suggestions(nodes),
        }

    async def suggest_nodes(self, current_nodes: List[str], context: Optional[str] = None) -> List[Dict[str, Any]]:
        """Suggest nodes based on current workflow"""

        suggestions = []

        # Basic compatibility rules for common nodes
        basic_compatibility = {
            "Mountain": [
                "Erosion",
                "Erosion2",
                "TextureBase",
                "SatMap",
                "Rivers",
                "Snow",
            ],
            "Erosion": ["TextureBase", "SatMap", "Adjust", "Terrace"],
            "Erosion2": ["TextureBase", "SatMap", "Rivers", "Adjust"],
            "Rivers": ["SatMap", "TextureBase", "Lakes"],
            "TextureBase": ["SatMap", "Export"],
            "SatMap": ["Export"],
        }

        # Use knowledge graph for suggestions or fall back to basic rules
        for node_type in current_nodes:
            compatible = NODE_COMPATIBILITY.get(node_type, [])
            if not compatible:
                # Use basic compatibility if no knowledge graph data
                compatible = basic_compatibility.get(node_type, [])

            for suggested in compatible[:3]:  # Top 3 suggestions
                if suggested not in current_nodes:
                    suggestions.append(
                        {
                            "node_type": suggested,
                            "reason": f"Compatible with {node_type}",
                            "category": knowledge_graph.get_node_category(suggested),
                        }
                    )

        # Add context-based suggestions
        if context and "realistic" in context.lower():
            if "Erosion2" not in current_nodes and "Erosion" not in current_nodes:
                suggestions.append(
                    {
                        "node_type": "Erosion2",
                        "reason": "Recommended for realistic terrain",
                        "category": "Erosion",
                    }
                )
            if "SatMap" not in current_nodes:
                suggestions.append(
                    {
                        "node_type": "SatMap",
                        "reason": "Required for color output",
                        "category": "ColorAndData",
                    }
                )

        # Remove duplicates
        seen = set()
        unique_suggestions = []
        for s in suggestions:
            if s["node_type"] not in seen:
                seen.add(s["node_type"])
                unique_suggestions.append(s)

        return unique_suggestions[:5]  # Return top 5 suggestions

    def _contains_sequence(self, node_types: List[str], sequence: List[str]) -> bool:
        """Check if node types contain a sequence"""
        for i in range(len(node_types) - len(sequence) + 1):
            if node_types[i : i + len(sequence)] == sequence:
                return True
        return False

    def _estimate_complexity(self, nodes: List[Dict[str, Any]]) -> str:
        """Estimate workflow complexity"""
        heavy_count = sum(
            1 for n in nodes if n.get("type", n.get("node_type")) in ["Erosion2", "Rivers", "Snow", "Vegetation"]
        )

        if heavy_count >= 5:
            return "high"
        elif heavy_count >= 2:
            return "medium"
        else:
            return "low"

    def _get_performance_suggestions(self, nodes: List[Dict[str, Any]]) -> List[str]:
        """Get performance optimization suggestions"""
        suggestions = []

        # Count heavy nodes
        erosion_count = sum(1 for n in nodes if n.get("type", n.get("node_type")) == "Erosion2")

        if erosion_count > 2:
            suggestions.append("Consider reducing Erosion2 nodes or lowering Duration")

        return suggestions

    def _get_quality_suggestions(self, nodes: List[Dict[str, Any]]) -> List[str]:
        """Get quality enhancement suggestions"""
        suggestions = []
        node_types = [n.get("type", n.get("node_type")) for n in nodes]

        if "Erosion2" not in node_types:
            suggestions.append("Add Erosion2 for more realistic terrain")

        if "SatMap" not in node_types:
            suggestions.append("Add SatMap for color mapping")

        return suggestions
