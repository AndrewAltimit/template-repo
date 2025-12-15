"""Stub implementations for Gaea2 dependencies

WARNING: These are minimal stub implementations used during development/testing.
Most of these classes have full implementations elsewhere in the codebase:

- Gaea2PropertyValidator: See validation/gaea2_property_validator.py
- Gaea2ConnectionValidator: See validation/gaea2_connection_validator.py
- Gaea2ErrorRecovery: See errors/gaea2_error_recovery.py
- OptimizedGaea2Validator: See validation/gaea2_optimized_validator.py
- Gaea2WorkflowAnalyzer: See utils/gaea2_workflow_analyzer.py
- Gaea2ProjectRepair: See repair/gaea2_project_repair.py
- Gaea2StructureValidator: See validation/gaea2_structure_validator.py

These stubs are kept for:
1. Preventing circular import issues during module initialization
2. Providing minimal interfaces for testing
3. Backward compatibility with code that may still reference them

If you're using any of these classes in production code, import from their
full implementation modules instead.
"""

from typing import Any, Dict, List, Tuple

# Schema stubs
WORKFLOW_TEMPLATES: Dict[str, Dict[str, List[Any]]] = {
    "basic_terrain": {"nodes": [], "connections": []},
    "detailed_mountain": {"nodes": [], "connections": []},
    "volcanic_terrain": {"nodes": [], "connections": []},
    "desert_canyon": {"nodes": [], "connections": []},
    "modular_portal_terrain": {"nodes": [], "connections": []},
    "mountain_range": {"nodes": [], "connections": []},
    "volcanic_island": {"nodes": [], "connections": []},
    "canyon_system": {"nodes": [], "connections": []},
    "coastal_cliffs": {"nodes": [], "connections": []},
    "arctic_terrain": {"nodes": [], "connections": []},
    "river_valley": {"nodes": [], "connections": []},
}


def create_workflow_from_template(name: str) -> Dict[str, List[Any]]:
    """Create a workflow from a template name"""
    return WORKFLOW_TEMPLATES.get(name, {"nodes": [], "connections": []})


def validate_gaea2_project(_project: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a Gaea2 project structure"""
    return {"valid": True, "errors": []}


# Pattern knowledge stubs
COMMON_NODE_SEQUENCES: Dict[str, List[str]] = {}
NODE_COMPATIBILITY: Dict[str, List[str]] = {}
PROPERTY_RANGES: Dict[str, Dict[str, Any]] = {}


# Knowledge graph stub
class KnowledgeGraph:
    """Stub knowledge graph for Gaea2 node categorization"""

    def get_node_category(self, _node_type: str) -> str:
        """Get the category of a node type"""
        return "Unknown"


knowledge_graph: KnowledgeGraph = KnowledgeGraph()


# Validator stubs
class Validator:
    """Stub validator for Gaea2 nodes"""

    def validate_node(self, _node_type: str, properties: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Validate a node and its properties"""
        return True, [], properties


def create_accurate_validator() -> Validator:
    """Create a validator instance"""
    return Validator()


class Gaea2ConnectionValidator:
    """Stub validator for Gaea2 connections"""

    def validate_connection(self, _conn: Dict[str, Any], _node_map: Dict[str, Any]) -> Tuple[bool, Any]:
        """Validate a connection between nodes"""
        return True, None


class Gaea2PropertyValidator:
    """Stub validator for Gaea2 node properties"""

    def validate_properties(self, _node_type: str, properties: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """Validate properties for a node type"""
        return True, [], properties


class Gaea2ErrorRecovery:
    """Stub error recovery for Gaea2 workflows"""

    def fix_workflow(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Attempt to fix errors in a workflow"""
        return {
            "nodes": nodes,
            "connections": connections,
            "fixed": False,
            "fixes_applied": [],
        }


class OptimizedGaea2Validator:
    """Stub optimized validator for Gaea2 projects"""


class Gaea2WorkflowAnalyzer:
    """Stub workflow analyzer for Gaea2 patterns"""


class Gaea2ProjectRepair:
    """Stub project repair tool for Gaea2 files"""

    def repair_project(self, path: str, backup: bool = True) -> Dict[str, Any]:  # pylint: disable=unused-argument
        """Repair a damaged Gaea2 project file"""
        return {"success": True}


class Gaea2StructureValidator:
    """Stub structure validator for Gaea2 projects"""

    def validate_structure(self, _data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the structure of Gaea2 project data"""
        return {"valid": True, "errors": []}
