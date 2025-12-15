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
    return WORKFLOW_TEMPLATES.get(name, {"nodes": [], "connections": []})


def validate_gaea2_project(_project: Dict[str, Any]) -> Dict[str, Any]:
    return {"valid": True, "errors": []}


# Pattern knowledge stubs
COMMON_NODE_SEQUENCES: Dict[str, List[str]] = {}
NODE_COMPATIBILITY: Dict[str, List[str]] = {}
PROPERTY_RANGES: Dict[str, Dict[str, Any]] = {}


# Knowledge graph stub
class KnowledgeGraph:
    def get_node_category(self, _node_type: str) -> str:
        return "Unknown"


knowledge_graph: KnowledgeGraph = KnowledgeGraph()


# Validator stubs
class Validator:
    def validate_node(self, _node_type: str, properties: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        return True, [], properties


def create_accurate_validator() -> Validator:
    return Validator()


class Gaea2ConnectionValidator:
    def validate_connection(self, _conn: Dict[str, Any], _node_map: Dict[str, Any]) -> Tuple[bool, Any]:
        return True, None


class Gaea2PropertyValidator:
    def validate_properties(self, _node_type: str, properties: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        return True, [], properties


class Gaea2ErrorRecovery:
    def fix_workflow(self, nodes: List[Dict[str, Any]], connections: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "nodes": nodes,
            "connections": connections,
            "fixed": False,
            "fixes_applied": [],
        }


class OptimizedGaea2Validator:
    pass


class Gaea2WorkflowAnalyzer:
    pass


class Gaea2ProjectRepair:
    def repair_project(self, path: str, backup: bool = True) -> Dict[str, Any]:  # pylint: disable=unused-argument
        return {"success": True}


class Gaea2StructureValidator:
    def validate_structure(self, _data: Dict[str, Any]) -> Dict[str, Any]:
        return {"valid": True, "errors": []}
