#!/usr/bin/env python3
"""
Gaea2 workflow analyzer - learns patterns from real projects
"""

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.mcp.gaea2.utils.workflow_extractor import WorkflowExtractor

logger = logging.getLogger(__name__)


class WorkflowPattern:
    """Represents a common workflow pattern"""

    def __init__(self, name: str, nodes: List[str], frequency: int = 1):
        self.name = name
        self.nodes = nodes
        self.frequency = frequency
        self.connections: List[Dict[str, Any]] = []
        self.property_patterns: Dict[str, Dict[str, List[Any]]] = defaultdict(dict)

    def add_property_pattern(self, node_type: str, property_name: str, value: Any):
        """Add a property pattern"""
        if property_name not in self.property_patterns[node_type]:
            self.property_patterns[node_type][property_name] = []
        self.property_patterns[node_type][property_name].append(value)

    def get_common_properties(self, node_type: str) -> Dict[str, Any]:
        """Get most common property values for a node type"""
        common = {}
        if node_type in self.property_patterns:
            for prop, values in self.property_patterns[node_type].items():
                # Get most common value
                counter = Counter(values)
                common[prop] = counter.most_common(1)[0][0]
        return common


class Gaea2WorkflowAnalyzer:
    """Analyzes workflows to learn patterns and best practices"""

    def __init__(self):
        self.patterns = []
        self.node_sequences = defaultdict(list)  # What typically follows each node
        self.property_distributions = defaultdict(lambda: defaultdict(list))
        self.connection_patterns = defaultdict(int)
        self.node_frequency = Counter()
        self.projects_analyzed = 0

    def analyze_project(self, project_path: str) -> Dict[str, Any]:
        """Analyze a single project"""
        try:
            with open(project_path, "r") as f:
                project_data = json.load(f)

            nodes, connections = WorkflowExtractor.extract_workflow(project_data)

            if not nodes:
                return {"success": False, "error": "No nodes found"}

            # Update statistics
            self.projects_analyzed += 1

            # Analyze node frequency
            for node in nodes:
                self.node_frequency[node["type"]] += 1

            # Analyze sequences
            self._analyze_sequences(nodes, connections)

            # Analyze property distributions
            self._analyze_properties(nodes)

            # Find patterns
            pattern = self._extract_pattern(nodes, connections)
            if pattern:
                self._add_or_update_pattern(pattern)

            return {
                "success": True,
                "nodes_analyzed": len(nodes),
                "connections_analyzed": len(connections),
            }

        except Exception as e:
            logger.error(f"Failed to analyze {project_path}: {str(e)}")
            return {"success": False, "error": str(e)}

    def analyze_directory(self, directory_path: str) -> Dict[str, Any]:
        """Analyze all projects in a directory"""
        results = []
        path = Path(directory_path)

        for file_path in path.glob("*.terrain"):
            result = self.analyze_project(str(file_path))
            results.append({"file": file_path.name, "result": result})

        return {
            "projects_analyzed": self.projects_analyzed,
            "total_patterns": len(self.patterns),
            "node_frequency": dict(self.node_frequency.most_common(20)),
            "results": results,
        }

    def get_recommendations(self, current_nodes: List[str]) -> Dict[str, Any]:
        """Get recommendations based on learned patterns"""
        recommendations: Dict[str, Any] = {
            "next_nodes": [],
            "missing_nodes": [],
            "property_suggestions": {},
            "similar_patterns": [],
        }

        # Find what typically follows the last node
        if current_nodes:
            last_node = current_nodes[-1]
            if last_node in self.node_sequences:
                next_nodes = Counter(self.node_sequences[last_node])
                recommendations["next_nodes"] = [
                    {"node": node, "frequency": count} for node, count in next_nodes.most_common(5)
                ]

        # Find similar patterns
        for pattern in self.patterns:
            similarity = self._calculate_pattern_similarity(current_nodes, pattern.nodes)
            if similarity > 0.5:
                # Ensure we're working with a list
                similar_patterns = recommendations["similar_patterns"]
                assert isinstance(similar_patterns, list)
                similar_patterns.append(
                    {
                        "name": pattern.name,
                        "similarity": similarity,
                        "nodes": pattern.nodes,
                        "frequency": pattern.frequency,
                    }
                )

        # Sort by similarity
        similar_patterns_list = recommendations["similar_patterns"]
        assert isinstance(similar_patterns_list, list)
        similar_patterns_list.sort(key=lambda x: x["similarity"], reverse=True)

        # Find commonly used nodes that are missing
        common_nodes = [node for node, _ in self.node_frequency.most_common(10)]
        recommendations["missing_nodes"] = [node for node in common_nodes if node not in current_nodes]

        # Get property suggestions
        for node in current_nodes:
            if node in self.property_distributions:
                suggestions: Dict[str, Any] = {}
                for prop, values in self.property_distributions[node].items():
                    if values:
                        # Get median for numeric values
                        if all(isinstance(v, (int, float)) for v in values):
                            sorted_values = sorted(values)
                            median = sorted_values[len(sorted_values) // 2]
                            suggestions[prop] = median
                        else:
                            # Get most common for other types
                            counter = Counter(values)
                            suggestions[prop] = counter.most_common(1)[0][0]
                property_suggestions = recommendations["property_suggestions"]
                assert isinstance(property_suggestions, dict)
                property_suggestions[node] = suggestions

        return recommendations

    def get_workflow_template(self, pattern_name: str) -> Optional[Dict[str, Any]]:
        """Generate a workflow template from a pattern"""
        pattern = next((p for p in self.patterns if p.name == pattern_name), None)
        if not pattern:
            return None

        nodes = []
        x_offset = 0

        for i, node_type in enumerate(pattern.nodes):
            node = {
                "type": node_type,
                "name": node_type,
                "properties": pattern.get_common_properties(node_type),
                "position": {"x": 25000 + x_offset, "y": 25000},
            }
            nodes.append(node)
            x_offset += 1000

        return {"name": pattern.name, "nodes": nodes, "frequency": pattern.frequency}

    def get_statistics(self) -> Dict[str, Any]:
        """Get analysis statistics"""
        return {
            "projects_analyzed": self.projects_analyzed,
            "total_patterns": len(self.patterns),
            "unique_node_types": len(self.node_frequency),
            "most_common_nodes": dict(self.node_frequency.most_common(10)),
            "most_common_patterns": [
                {"name": p.name, "nodes": p.nodes, "frequency": p.frequency}
                for p in sorted(self.patterns, key=lambda x: x.frequency, reverse=True)[:10]
            ],
        }

    def _analyze_sequences(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]):
        """Analyze node sequences"""
        node_map = {n["id"]: n["type"] for n in nodes}

        for conn in connections:
            from_type = node_map.get(conn["from_node"])
            to_type = node_map.get(conn["to_node"])

            if from_type and to_type:
                self.node_sequences[from_type].append(to_type)
                self.connection_patterns[f"{from_type}->{to_type}"] += 1

    def _analyze_properties(self, nodes: List[Dict[str, Any]]):
        """Analyze property distributions"""
        for node in nodes:
            node_type = node["type"]
            for prop_name, prop_value in node.get("properties", {}).items():
                # Store property values for distribution analysis
                if isinstance(prop_value, (int, float, str, bool)):
                    self.property_distributions[node_type][prop_name].append(prop_value)

    def _extract_pattern(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> Optional[WorkflowPattern]:
        """Extract a workflow pattern from nodes"""
        if len(nodes) < 2:
            return None

        # Get the sequence of node types
        node_map = {n["id"]: n for n in nodes}

        # Find the starting node (no incoming connections)
        incoming = {c["to_node"] for c in connections}
        start_nodes = [n for n in nodes if n["id"] not in incoming]

        if not start_nodes:
            # If no clear start, pick the first node
            start_nodes = [nodes[0]]

        # Trace the main path
        pattern_nodes = []
        current: Optional[Dict[str, Any]] = start_nodes[0]
        visited = set()

        while current and current["id"] not in visited:
            pattern_nodes.append(current["type"])
            visited.add(current["id"])

            # Find next node
            next_conn = next((c for c in connections if c["from_node"] == current["id"]), None)
            if next_conn:
                current = node_map.get(next_conn["to_node"])
            else:
                current = None

        if len(pattern_nodes) >= 2:
            pattern_name = "->".join(pattern_nodes[:3])  # Use first 3 nodes as name
            pattern = WorkflowPattern(pattern_name, pattern_nodes)

            # Add property patterns
            for node in nodes:
                if node["type"] in pattern_nodes:
                    for prop_name, prop_value in node.get("properties", {}).items():
                        pattern.add_property_pattern(node["type"], prop_name, prop_value)

            return pattern

        return None

    def _add_or_update_pattern(self, new_pattern: WorkflowPattern):
        """Add or update a pattern"""
        # Check if pattern already exists
        for existing in self.patterns:
            if existing.nodes == new_pattern.nodes:
                existing.frequency += 1
                # Merge property patterns
                for node_type, props in new_pattern.property_patterns.items():
                    for prop_name, values in props.items():
                        existing.add_property_pattern(node_type, prop_name, values[0])
                return

        # New pattern
        self.patterns.append(new_pattern)

    def _calculate_pattern_similarity(self, nodes1: List[str], nodes2: List[str]) -> float:
        """Calculate similarity between two node sequences"""
        if not nodes1 or not nodes2:
            return 0.0

        # Use Jaccard similarity
        set1 = set(nodes1)
        set2 = set(nodes2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        return intersection / union if union > 0 else 0.0

    def save_analysis(self, output_path: str):
        """Save analysis results to file"""
        data = {
            "statistics": self.get_statistics(),
            "patterns": [
                {
                    "name": p.name,
                    "nodes": p.nodes,
                    "frequency": p.frequency,
                    "properties": {node: p.get_common_properties(node) for node in p.nodes},
                }
                for p in self.patterns
            ],
            "node_sequences": {node: Counter(sequences).most_common(5) for node, sequences in self.node_sequences.items()},
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_analysis(self, input_path: str):
        """Load previous analysis results"""
        with open(input_path, "r") as f:
            data = json.load(f)

        # Reconstruct patterns
        self.patterns = []
        for p_data in data.get("patterns", []):
            pattern = WorkflowPattern(p_data["name"], p_data["nodes"], p_data["frequency"])
            self.patterns.append(pattern)

        # Load statistics
        stats = data.get("statistics", {})
        self.projects_analyzed = stats.get("projects_analyzed", 0)

        # Load node sequences
        for node, sequences in data.get("node_sequences", {}).items():
            self.node_sequences[node] = [seq[0] for seq in sequences for _ in range(seq[1])]
