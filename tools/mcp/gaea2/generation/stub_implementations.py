"""Stub implementations to avoid circular dependencies during reorganization"""


class EnhancedGaea2Tools:
    """Stub for EnhancedGaea2Tools"""

    pass


class Gaea2WorkflowTools:
    """Stub for Gaea2WorkflowTools"""

    async def create_gaea2_project(self, **kwargs):
        return {"success": True, "project_data": {}}


def generate_non_sequential_id():
    """Generate a simple ID"""
    import uuid

    return str(uuid.uuid4())[:8]


def apply_format_fixes(data):
    """Stub for format fixes"""
    return data


def fix_property_names(props):
    """Stub for property name fixes"""
    return props
