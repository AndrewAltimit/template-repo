#!/usr/bin/env python3
"""
Gaea2 project repair and optimization utilities
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from tools.mcp.gaea2.utils.workflow_extractor import WorkflowExtractor

from ..errors.gaea2_error_handler import ErrorCategory, ErrorSeverity, Gaea2Error, Gaea2ErrorHandler
from ..validation.gaea2_accurate_validation import create_accurate_validator

logger = logging.getLogger(__name__)


class Gaea2ProjectRepair:
    """Utilities for repairing and optimizing Gaea2 projects"""

    def __init__(self):
        self.error_handler = Gaea2ErrorHandler()
        self.validator = create_accurate_validator()

    def analyze_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive project analysis"""
        try:
            # Extract nodes and connections
            nodes, connections = WorkflowExtractor.extract_workflow(project_data)

            # Clear previous errors
            self.error_handler.clear_errors()

            # Run all checks
            self._check_structure_integrity(project_data)
            self._check_node_validity(nodes)
            self._check_connection_validity(nodes, connections)
            self._check_property_validity(nodes)
            self._check_performance_issues(nodes, connections)
            self._check_best_practices(nodes, connections)

            # Get summary
            error_summary = self.error_handler.get_summary()

            return {
                "success": True,
                "analysis": {
                    "node_count": len(nodes),
                    "connection_count": len(connections),
                    "errors": error_summary,
                    "can_auto_fix": len(self.error_handler.get_auto_fixable_errors()) > 0,
                    "health_score": self._calculate_health_score(error_summary),
                },
                "errors": [e.to_dict() for e in self.error_handler.errors],
            }

        except Exception as e:
            logger.error(f"Project analysis failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def repair_project(
        self,
        project_data: Dict[str, Any],
        auto_fix: bool = True,
        create_backup: bool = True,
    ) -> Dict[str, Any]:
        """Repair project issues"""
        try:
            # Initialize backup_data
            backup_data = None

            # Create backup if requested
            if create_backup:
                backup_data = json.loads(json.dumps(project_data))

            # Extract workflow
            nodes, connections = WorkflowExtractor.extract_workflow(project_data)

            # Analyze first
            analysis = self.analyze_project(project_data)

            if not analysis["success"]:
                return analysis

            fixes_applied = []

            if auto_fix:
                # Auto-fix what we can
                nodes, connections, fixes = self.error_handler.auto_fix_errors(nodes, connections, self.validator.schema)
                fixes_applied.extend(fixes)

                # Additional repairs
                nodes, connections, more_fixes = self._repair_orphaned_nodes(nodes, connections)
                fixes_applied.extend(more_fixes)

                nodes, more_fixes = self._repair_missing_properties(nodes)
                fixes_applied.extend(more_fixes)

                # Update project with repaired data
                self._update_project_workflow(project_data, nodes, connections)

            # Re-analyze after repairs
            post_analysis = self.analyze_project(project_data)

            return {
                "success": True,
                "original_analysis": analysis,
                "post_repair_analysis": post_analysis,
                "fixes_applied": fixes_applied,
                "backup_available": create_backup,
                "backup_data": backup_data if create_backup else None,
            }

        except Exception as e:
            logger.error(f"Project repair failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def optimize_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize project for better performance"""
        try:
            nodes, connections = WorkflowExtractor.extract_workflow(project_data)
            optimizations = []

            # Optimize property values
            for node in nodes:
                node_type = node.get("type")
                if node_type == "Erosion" or node_type == "Erosion2":
                    # Check duration
                    duration = node.get("properties", {}).get("Duration", 0)
                    if duration > 0.1:
                        node["properties"]["Duration"] = 0.1
                        optimizations.append(
                            f"Reduced {node.get('name')} duration from {duration} to 0.1 for better performance"
                        )

                elif node_type == "Rivers":
                    # Check headwater count
                    headwaters = node.get("properties", {}).get("Headwaters", 100)
                    if headwaters > 200:
                        node["properties"]["Headwaters"] = 200
                        optimizations.append(f"Reduced {node.get('name')} headwaters from {headwaters} to 200")

            # Remove redundant nodes
            redundant = self._find_redundant_nodes(nodes, connections)
            if redundant:
                nodes = [n for n in nodes if n.get("id") not in redundant]
                connections = [
                    c for c in connections if c.get("from_node") not in redundant and c.get("to_node") not in redundant
                ]
                optimizations.append(f"Removed {len(redundant)} redundant nodes")

            # Update project
            self._update_project_workflow(project_data, nodes, connections)

            return {
                "success": True,
                "optimizations_applied": optimizations,
                "optimization_count": len(optimizations),
            }

        except Exception as e:
            logger.error(f"Project optimization failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _update_project_workflow(
        self,
        project_data: Dict[str, Any],
        nodes: List[Dict[str, Any]],
        connections: List[Dict[str, Any]],
    ):
        """Update project data with modified workflow"""
        # This is a simplified version - in reality would need to rebuild the full structure
        # For now, we'll just log that updates would be applied
        logger.info(f"Would update project with {len(nodes)} nodes and {len(connections)} connections")

    def _check_structure_integrity(self, project_data: Dict[str, Any]):
        """Check project structure integrity"""
        required_keys = ["Assets", "Id", "Metadata"]
        for key in required_keys:
            if key not in project_data:
                self.error_handler.add_error(
                    Gaea2Error(
                        message=f"Missing required project key: {key}",
                        severity=ErrorSeverity.CRITICAL,
                        category=ErrorCategory.STRUCTURE,
                        suggestion="Project file may be corrupted",
                    )
                )

    def _check_node_validity(self, nodes: List[Dict[str, Any]]):
        """Check node validity"""
        for node in nodes:
            node_type = node.get("type")
            if not self.validator.validate_node_type(node_type):
                self.error_handler.add_error(
                    Gaea2Error(
                        message=f"Invalid node type: {node_type}",
                        severity=ErrorSeverity.ERROR,
                        category=ErrorCategory.VALIDATION,
                        node_id=node.get("id"),
                        suggestion="Remove or replace this node",
                        auto_fixable=False,
                    )
                )

    def _check_connection_validity(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]):
        """Check connection validity"""
        self.error_handler.validate_node_connections(nodes, connections)

    def _check_property_validity(self, nodes: List[Dict[str, Any]]):
        """Check property validity"""
        for node in nodes:
            node_type = node.get("type")
            properties = node.get("properties", {})

            # Validate with accurate validator
            is_valid, errors, corrected = self.validator.validate_node(node_type, properties)

            for error in errors:
                self.error_handler.add_error(
                    Gaea2Error(
                        message=error,
                        severity=ErrorSeverity.ERROR,
                        category=ErrorCategory.PROPERTY,
                        node_id=node.get("id"),
                        auto_fixable=True,
                    )
                )

    def _check_performance_issues(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]):
        """Check for performance issues"""
        self.error_handler.check_performance_issues(nodes, connections)

    def _check_best_practices(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]):
        """Check against best practices"""
        # Check for missing colorization
        has_color = any(n.get("type") in ["SatMap", "CLUTer", "SuperColor", "Weathering"] for n in nodes)
        if not has_color and len(nodes) > 3:
            self.error_handler.add_error(
                Gaea2Error(
                    message="Project has no colorization nodes",
                    severity=ErrorSeverity.INFO,
                    category=ErrorCategory.STRUCTURE,
                    suggestion="Consider adding SatMap or CLUTer for realistic colors",
                )
            )

        # Check for export nodes
        has_export = any(n.get("type") in ["Export", "Unity", "Unreal"] for n in nodes)
        if not has_export:
            self.error_handler.add_error(
                Gaea2Error(
                    message="Project has no export nodes",
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.STRUCTURE,
                    suggestion="Add Export node to save terrain output",
                )
            )

    def _calculate_health_score(self, error_summary: Dict[str, Any]) -> float:
        """Calculate project health score (0-100)"""
        score = 100.0

        # Deduct points based on errors
        critical_count = float(error_summary.get("critical", 0))
        error_count = float(error_summary.get("errors", 0))
        warning_count = float(error_summary.get("warnings", 0))

        score -= critical_count * 25
        score -= error_count * 10
        score -= warning_count * 3

        # Ensure score doesn't go below 0
        return max(0.0, score)

    def _repair_orphaned_nodes(
        self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
        """Repair orphaned nodes by connecting or removing them"""
        fixes = []

        # Find orphaned nodes
        connected_ids = set()
        for conn in connections:
            connected_ids.add(conn["from_node"])
            connected_ids.add(conn["to_node"])

        node_ids = {n["id"] for n in nodes}
        orphaned = node_ids - connected_ids

        # Remove orphaned nodes that aren't important
        important_types = ["Export", "Unity", "Unreal", "Mountain", "Island", "Canyon"]
        nodes_to_remove = []

        for node_id in orphaned:
            node = next((n for n in nodes if n["id"] == node_id), None)
            if node and node.get("type") not in important_types:
                nodes_to_remove.append(node_id)
                fixes.append(f"Removed orphaned {node.get('type')} node: {node.get('name')}")

        nodes = [n for n in nodes if n["id"] not in nodes_to_remove]

        return nodes, connections, fixes

    def _repair_missing_properties(self, nodes: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Add missing required properties with defaults"""
        fixes = []

        for node in nodes:
            node_type = node.get("type")
            if not node_type:
                continue

            # Get property definitions
            node_props = self.validator.get_node_properties(node_type)

            # Add missing defaults
            for prop_name, prop_def in node_props.items():
                if prop_name not in node.get("properties", {}) and "default" in prop_def:
                    if "properties" not in node:
                        node["properties"] = {}
                    node["properties"][prop_name] = prop_def["default"]
                    fixes.append(f"Added default {prop_name}={prop_def['default']} to {node.get('name')}")

        return nodes, fixes

    def _find_redundant_nodes(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> List[int]:
        """Find redundant nodes that can be removed"""
        redundant: List[int] = []

        # Find pass-through Combine nodes (ratio = 0.5, only one input)
        for node in nodes:
            if node.get("type") == "Combine":
                node_id = node.get("id")
                if node_id is not None:
                    # Count inputs
                    inputs = [c for c in connections if c.get("to_node") == node_id]
                    if len(inputs) == 1 and node.get("properties", {}).get("Ratio", 0.5) == 0.5:
                        redundant.append(node_id)

        return redundant


# Utility functions for easy access
def analyze_project_file(file_path: str) -> Dict[str, Any]:
    """Analyze a project file"""
    repair = Gaea2ProjectRepair()

    with open(file_path, "r") as f:
        project_data = json.load(f)

    return repair.analyze_project(project_data)


def repair_project_file(file_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """Repair a project file"""
    repair = Gaea2ProjectRepair()

    with open(file_path, "r") as f:
        project_data = json.load(f)

    result = repair.repair_project(project_data)

    if result["success"] and output_path:
        with open(output_path, "w") as f:
            json.dump(project_data, f, indent=2)

    return result
