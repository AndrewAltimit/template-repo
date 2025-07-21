"""Stub implementations to avoid circular dependencies during reorganization"""


class EnhancedGaea2Tools:
    """Stub for EnhancedGaea2Tools"""

    pass


class Gaea2WorkflowTools:
    """Stub for Gaea2WorkflowTools"""

    async def create_gaea2_project(self, **kwargs):
        return {"success": True, "project_data": {}}


def generate_non_sequential_id(base=100, used_ids=None):
    """Use the real implementation from gaea2_format_fixes"""
    from ...gaea2_format_fixes import generate_non_sequential_id as real_generate_id

    return real_generate_id(base=base, used_ids=used_ids)


def apply_format_fixes(data):
    """Use the real implementation from gaea2_format_fixes"""
    from ...gaea2_format_fixes import apply_format_fixes as real_apply_fixes

    return real_apply_fixes(data)


def fix_property_names(node_type, props):
    """Use the real implementation from gaea2_format_fixes"""
    from ...gaea2_format_fixes import fix_property_names as real_fix_names

    return real_fix_names(node_type, props)
