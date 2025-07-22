"""Stub implementations for Gaea2 dependencies"""

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


def validate_gaea2_project(project: Dict[str, Any]) -> Dict[str, Any]:
    return {"valid": True, "errors": []}


# Pattern knowledge stubs
COMMON_NODE_SEQUENCES: Dict[str, List[str]] = {}
NODE_COMPATIBILITY: Dict[str, List[str]] = {}
PROPERTY_RANGES: Dict[str, Dict[str, Any]] = {}


# Knowledge graph stub
class KnowledgeGraph:
    def get_node_category(self, node_type: str) -> str:
        return "Unknown"


knowledge_graph: KnowledgeGraph = KnowledgeGraph()


# Validator stubs
class Validator:
    def validate_node(self, node_type: str, properties: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        return True, [], properties


def create_accurate_validator() -> Validator:
    return Validator()


class Gaea2ConnectionValidator:
    def validate_connection(self, conn: Dict[str, Any], node_map: Dict[str, Any]) -> Tuple[bool, Any]:
        return True, None


class Gaea2PropertyValidator:
    def validate_properties(self, node_type: str, properties: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
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
    def repair_project(self, path: str, backup: bool = True) -> Dict[str, Any]:
        return {"success": True}


class Gaea2StructureValidator:
    def validate_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {"valid": True, "errors": []}
