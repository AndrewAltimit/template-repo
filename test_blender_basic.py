#!/usr/bin/env python3
"""Basic test to verify Blender MCP server components."""

import os
import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Test if all modules can be imported."""
    print("Testing imports...")
    errors = []

    try:
        from tools.mcp.core.base_server import BaseMCPServer

        print("✓ BaseMCPServer imported")
    except ImportError as e:
        errors.append(f"Failed to import BaseMCPServer: {e}")

    try:
        from tools.mcp.blender.core.blender_executor import BlenderExecutor

        print("✓ BlenderExecutor imported")
    except ImportError as e:
        errors.append(f"Failed to import BlenderExecutor: {e}")

    try:
        from tools.mcp.blender.core.job_manager import JobManager

        print("✓ JobManager imported")
    except ImportError as e:
        errors.append(f"Failed to import JobManager: {e}")

    try:
        from tools.mcp.blender.core.asset_manager import AssetManager

        print("✓ AssetManager imported")
    except ImportError as e:
        errors.append(f"Failed to import AssetManager: {e}")

    try:
        from tools.mcp.blender.core.templates import TemplateManager

        print("✓ TemplateManager imported")
    except ImportError as e:
        errors.append(f"Failed to import TemplateManager: {e}")

    try:
        from tools.mcp.blender.server import BlenderMCPServer

        print("✓ BlenderMCPServer imported")
    except Exception as e:
        errors.append(f"Failed to import BlenderMCPServer: {e}")
        import traceback

        traceback.print_exc()

    return errors


def test_instantiation():
    """Test if we can create instances."""
    print("\nTesting instantiation...")
    errors = []

    try:
        from tools.mcp.blender.core.job_manager import JobManager

        jm = JobManager("/tmp/test_jobs")
        print("✓ JobManager instantiated")
    except Exception as e:
        errors.append(f"Failed to instantiate JobManager: {e}")

    try:
        from tools.mcp.blender.core.asset_manager import AssetManager

        am = AssetManager("/tmp/test_projects", "/tmp/test_assets")
        print("✓ AssetManager instantiated")
    except Exception as e:
        errors.append(f"Failed to instantiate AssetManager: {e}")

    try:
        from tools.mcp.blender.core.templates import TemplateManager

        tm = TemplateManager("/tmp/test_templates")
        print("✓ TemplateManager instantiated")
    except Exception as e:
        errors.append(f"Failed to instantiate TemplateManager: {e}")

    try:
        from tools.mcp.blender.core.blender_executor import BlenderExecutor

        be = BlenderExecutor()
        print("✓ BlenderExecutor instantiated")
    except Exception as e:
        errors.append(f"Failed to instantiate BlenderExecutor: {e}")

    return errors


def test_server_creation():
    """Test if we can create the server."""
    print("\nTesting server creation...")
    errors = []

    try:
        # First check if FastAPI is available
        import fastapi
        import uvicorn

        print("✓ FastAPI and Uvicorn available")
    except ImportError as e:
        errors.append(f"Missing dependency: {e}")
        return errors

    try:
        import tempfile

        from tools.mcp.blender.server import BlenderMCPServer

        # Use temp directory for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            server = BlenderMCPServer(base_dir=tmpdir)
            print("✓ BlenderMCPServer created")

            # Check if it has the expected attributes
            assert hasattr(server, "blender_executor"), "Missing blender_executor"
            assert hasattr(server, "job_manager"), "Missing job_manager"
            assert hasattr(server, "asset_manager"), "Missing asset_manager"
            assert hasattr(server, "template_manager"), "Missing template_manager"
            print("✓ Server has all expected attributes")

            # Check tools
            tools = server.get_tools()
            print(f"✓ Server has {len(tools)} tools defined")

    except Exception as e:
        errors.append(f"Failed to create server: {e}")
        import traceback

        traceback.print_exc()

    return errors


def main():
    """Run all tests."""
    print("=" * 50)
    print("Blender MCP Basic Tests")
    print("=" * 50)

    all_errors = []

    # Test imports
    errors = test_imports()
    all_errors.extend(errors)

    if not errors:
        # Test instantiation
        errors = test_instantiation()
        all_errors.extend(errors)

        if not errors:
            # Test server
            errors = test_server_creation()
            all_errors.extend(errors)

    print("\n" + "=" * 50)
    if all_errors:
        print("❌ TESTS FAILED")
        print("\nErrors found:")
        for error in all_errors:
            print(f"  - {error}")
        return 1
    else:
        print("✅ ALL TESTS PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
