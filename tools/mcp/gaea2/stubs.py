"""Stub implementations for Gaea2 dependencies"""

# Schema stubs
WORKFLOW_TEMPLATES = {
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


def create_workflow_from_template(name):
    return WORKFLOW_TEMPLATES.get(name, {"nodes": [], "connections": []})


def validate_gaea2_project(project):
    return {"valid": True, "errors": []}


# Pattern knowledge stubs
COMMON_NODE_SEQUENCES = {}
NODE_COMPATIBILITY = {}
PROPERTY_RANGES = {}


# Knowledge graph stub
class KnowledgeGraph:
    def get_node_category(self, node_type):
        return "Unknown"


knowledge_graph = KnowledgeGraph()


# Validator stubs
def create_accurate_validator():
    class Validator:
        def validate_node(self, node_type, properties):
            return True, [], properties

    return Validator()


class Gaea2ConnectionValidator:
    def validate_connection(self, conn, node_map):
        return True, None


class Gaea2PropertyValidator:
    def validate_properties(self, node_type, properties):
        return True, [], properties


class Gaea2ErrorRecovery:
    def fix_workflow(self, nodes, connections):
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
    def repair_project(self, path, backup=True):
        return {"success": True}


class Gaea2StructureValidator:
    def validate_structure(self, data):
        return {"valid": True, "errors": []}
