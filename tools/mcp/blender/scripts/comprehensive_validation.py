#!/usr/bin/env python3
"""Comprehensive validation script for Blender MCP Server.

This script tests all major capabilities of the Blender MCP server including:
- Project creation from various templates
- 3D object creation and manipulation
- Material application and lighting
- Physics simulations
- Animation
- Geometry nodes
- Rendering (both images and animations)
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict  # noqa: F401

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from tools.mcp.core.client import MCPClient
except ImportError:
    # Try alternative import for Docker environment
    sys.path.insert(0, "/app")
    from core.client import MCPClient


class BlenderValidationSuite:
    """Comprehensive validation suite for Blender MCP Server."""

    def __init__(self, base_url: str = "http://localhost:8017"):
        self.client = MCPClient(base_url)
        self.test_results = []
        self.created_projects = []

    async def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result."""
        result = {
            "test": test_name,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
        self.test_results.append(result)
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {test_name}")
        if details:
            print(f"  Details: {details}")

    async def test_project_templates(self):
        """Test creating projects with different templates."""
        print("\n🎬 Testing Project Templates...")
        print("-" * 50)

        templates = [
            "empty",
            "basic_scene",
            "studio_lighting",
            "procedural",
            "animation",
            "physics",
            "architectural",
            "product",
            "vfx",
            "game_asset",
            "sculpting",
        ]

        for template in templates:
            try:
                project_name = f"test_{template}_project"
                result = await self.client.call_tool(
                    "create_blender_project",
                    {
                        "name": project_name,
                        "template": template,
                        "settings": {
                            "resolution": [1920, 1080],
                            "fps": 24,
                            "engine": "EEVEE",
                        },
                    },
                )

                if result.get("success"):
                    self.created_projects.append(result.get("project_path"))
                    await self.log_result(f"Create {template} template", True, f"Project: {project_name}")
                else:
                    await self.log_result(
                        f"Create {template} template",
                        False,
                        result.get("error", "Unknown error"),
                    )

            except Exception as e:
                await self.log_result(f"Create {template} template", False, str(e))

    async def test_object_creation(self):
        """Test adding various primitive objects."""
        print("\n🔷 Testing Object Creation...")
        print("-" * 50)

        # Create a test project first
        project_result = await self.client.call_tool(
            "create_blender_project",
            {
                "name": "object_test",
                "template": "empty",
                "settings": {"engine": "EEVEE"},
            },
        )

        if not project_result.get("success"):
            await self.log_result("Object creation setup", False, "Failed to create project")
            return

        project_path = project_result["project_path"]
        self.created_projects.append(project_path)

        # Test all primitive types
        object_types = [
            "cube",
            "sphere",
            "cylinder",
            "cone",
            "torus",
            "plane",
            "monkey",
        ]

        objects_to_add = []
        for i, obj_type in enumerate(object_types):
            x_pos = (i - 3) * 2  # Spread objects horizontally
            objects_to_add.append(
                {
                    "type": obj_type,
                    "name": f"Test_{obj_type.capitalize()}",
                    "location": [x_pos, 0, 1],
                    "rotation": [0.1 * i, 0.2 * i, 0.3 * i],
                    "scale": [1, 1, 1],
                }
            )

        try:
            result = await self.client.call_tool(
                "add_primitive_objects",
                {"project": project_path, "objects": objects_to_add},
            )

            await self.log_result(
                "Add primitive objects",
                result.get("success", False),
                f"Added {len(object_types)} objects",
            )

        except Exception as e:
            await self.log_result("Add primitive objects", False, str(e))

    async def test_materials_and_lighting(self):
        """Test material application and lighting setups."""
        print("\n💡 Testing Materials and Lighting...")
        print("-" * 50)

        # Create a test project
        project_result = await self.client.call_tool(
            "create_blender_project",
            {"name": "materials_test", "template": "basic_scene"},
        )

        if not project_result.get("success"):
            await self.log_result("Materials test setup", False, "Failed to create project")
            return

        project_path = project_result["project_path"]
        self.created_projects.append(project_path)

        # Add test objects
        objects = [
            {"type": "sphere", "name": "MetalSphere", "location": [-3, 0, 1]},
            {"type": "cube", "name": "GlassCube", "location": [0, 0, 1]},
            {"type": "monkey", "name": "EmissiveSuzanne", "location": [3, 0, 1]},
            {"type": "torus", "name": "PlasticTorus", "location": [0, 3, 1]},
            {"type": "cylinder", "name": "WoodCylinder", "location": [0, -3, 1]},
        ]

        await self.client.call_tool("add_primitive_objects", {"project": project_path, "objects": objects})

        # Test different material types
        material_tests = [
            ("MetalSphere", {"type": "metal", "roughness": 0.2, "metallic": 1.0}),
            ("GlassCube", {"type": "glass", "roughness": 0.0}),
            ("EmissiveSuzanne", {"type": "emission", "emission_strength": 5.0}),
            ("PlasticTorus", {"type": "plastic", "roughness": 0.4}),
            ("WoodCylinder", {"type": "wood", "roughness": 0.8}),
        ]

        for obj_name, material in material_tests:
            try:
                result = await self.client.call_tool(
                    "apply_material",
                    {
                        "project": project_path,
                        "object_name": obj_name,
                        "material": material,
                    },
                )

                await self.log_result(
                    f"Apply {material['type']} material",
                    result.get("success", False),
                    f"Applied to {obj_name}",
                )

            except Exception as e:
                await self.log_result(f"Apply {material['type']} material", False, str(e))

        # Test lighting setups
        lighting_types = ["three_point", "studio", "sun", "area"]

        for light_type in lighting_types:
            try:
                result = await self.client.call_tool(
                    "setup_lighting",
                    {
                        "project": project_path,
                        "type": light_type,
                        "settings": {"strength": 2.0, "color": [1, 0.95, 0.8]},
                    },
                )

                await self.log_result(f"Setup {light_type} lighting", result.get("success", False))

            except Exception as e:
                await self.log_result(f"Setup {light_type} lighting", False, str(e))

    async def test_physics_simulation(self):
        """Test physics simulation capabilities."""
        print("\n⚛️ Testing Physics Simulation...")
        print("-" * 50)

        # Create physics test project
        project_result = await self.client.call_tool("create_blender_project", {"name": "physics_demo", "template": "physics"})

        if not project_result.get("success"):
            await self.log_result("Physics test setup", False, "Failed to create project")
            return

        project_path = project_result["project_path"]
        self.created_projects.append(project_path)

        # Create a physics scene: ground plane and falling objects
        objects = [
            {
                "type": "plane",
                "name": "Ground",
                "location": [0, 0, 0],
                "scale": [10, 10, 1],
            },
            {"type": "cube", "name": "FallingBox1", "location": [0, 0, 5]},
            {"type": "sphere", "name": "FallingBall", "location": [2, 0, 7]},
            {
                "type": "cube",
                "name": "FallingBox2",
                "location": [-2, 0, 9],
                "rotation": [0.5, 0.3, 0.2],
            },
            {"type": "cylinder", "name": "FallingCylinder", "location": [0, 2, 6]},
        ]

        await self.client.call_tool("add_primitive_objects", {"project": project_path, "objects": objects})

        # Setup physics for ground (static)
        try:
            result = await self.client.call_tool(
                "setup_physics",
                {
                    "project": project_path,
                    "object_name": "Ground",
                    "physics_type": "rigid_body",
                    "settings": {"mass": 0, "friction": 0.5},  # Static object
                },
            )
            await self.log_result("Setup ground physics", result.get("success", False))
        except Exception as e:
            await self.log_result("Setup ground physics", False, str(e))

        # Setup physics for falling objects
        falling_objects = [
            "FallingBox1",
            "FallingBall",
            "FallingBox2",
            "FallingCylinder",
        ]

        for obj_name in falling_objects:
            try:
                result = await self.client.call_tool(
                    "setup_physics",
                    {
                        "project": project_path,
                        "object_name": obj_name,
                        "physics_type": "rigid_body",
                        "settings": {
                            "mass": 1.0,
                            "friction": 0.5,
                            "bounce": 0.3,
                            "collision_shape": "convex_hull",
                        },
                    },
                )
                await self.log_result(f"Setup physics for {obj_name}", result.get("success", False))
            except Exception as e:
                await self.log_result(f"Setup physics for {obj_name}", False, str(e))

        # Bake the simulation
        try:
            result = await self.client.call_tool(
                "bake_simulation",
                {"project": project_path, "start_frame": 1, "end_frame": 120},
            )
            await self.log_result(
                "Bake physics simulation",
                result.get("success", False),
                "120 frames baked",
            )
        except Exception as e:
            await self.log_result("Bake physics simulation", False, str(e))

    async def test_animation(self):
        """Test animation capabilities."""
        print("\n🎭 Testing Animation...")
        print("-" * 50)

        # Create animation test project
        project_result = await self.client.call_tool(
            "create_blender_project",
            {"name": "animation_test", "template": "animation"},
        )

        if not project_result.get("success"):
            await self.log_result("Animation test setup", False, "Failed to create project")
            return

        project_path = project_result["project_path"]
        self.created_projects.append(project_path)

        # Add animated objects
        objects = [
            {"type": "cube", "name": "RotatingCube", "location": [-3, 0, 1]},
            {"type": "sphere", "name": "BouncingSphere", "location": [0, 0, 1]},
            {"type": "monkey", "name": "SpinningSuzanne", "location": [3, 0, 1]},
        ]

        await self.client.call_tool("add_primitive_objects", {"project": project_path, "objects": objects})

        # Create keyframe animations
        animations = [
            {
                "object": "RotatingCube",
                "property": "rotation",
                "keyframes": [
                    {"frame": 1, "value": [0, 0, 0]},
                    {"frame": 60, "value": [0, 3.14159, 0]},
                    {"frame": 120, "value": [0, 6.28318, 0]},
                ],
            },
            {
                "object": "BouncingSphere",
                "property": "location",
                "keyframes": [
                    {"frame": 1, "value": [0, 0, 1]},
                    {"frame": 30, "value": [0, 0, 4]},
                    {"frame": 60, "value": [0, 0, 1]},
                    {"frame": 90, "value": [0, 0, 4]},
                    {"frame": 120, "value": [0, 0, 1]},
                ],
            },
        ]

        for anim in animations:
            try:
                result = await self.client.call_tool(
                    "create_animation",
                    {
                        "project": project_path,
                        "object_name": anim["object"],
                        "property_path": anim["property"],
                        "keyframes": anim["keyframes"],
                    },
                )
                await self.log_result(
                    f"Animate {anim['object']} {anim['property']}",
                    result.get("success", False),
                )
            except Exception as e:
                await self.log_result(f"Animate {anim['object']} {anim['property']}", False, str(e))

    async def test_geometry_nodes(self):
        """Test geometry nodes and procedural generation."""
        print("\n🔷 Testing Geometry Nodes...")
        print("-" * 50)

        # Create procedural test project
        project_result = await self.client.call_tool(
            "create_blender_project",
            {"name": "geometry_nodes_test", "template": "procedural"},
        )

        if not project_result.get("success"):
            await self.log_result("Geometry nodes test setup", False, "Failed to create project")
            return

        project_path = project_result["project_path"]
        self.created_projects.append(project_path)

        # Add base object for geometry nodes
        await self.client.call_tool(
            "add_primitive_objects",
            {
                "project": project_path,
                "objects": [{"type": "plane", "name": "ScatterBase", "scale": [10, 10, 1]}],
            },
        )

        # Test different geometry node setups
        geometry_tests = [
            {
                "name": "Point scatter",
                "type": "scatter",
                "settings": {
                    "count": 100,
                    "seed": 42,
                    "scale_min": 0.5,
                    "scale_max": 1.5,
                },
            },
            {
                "name": "Array modifier",
                "type": "array",
                "settings": {"count": 10, "offset": [2, 0, 0]},
            },
        ]

        for test in geometry_tests:
            try:
                result = await self.client.call_tool(
                    "setup_geometry_nodes",
                    {
                        "project": project_path,
                        "object_name": "ScatterBase",
                        "node_type": test["type"],
                        "settings": test["settings"],
                    },
                )
                await self.log_result(f"Geometry nodes: {test['name']}", result.get("success", False))
            except Exception as e:
                await self.log_result(f"Geometry nodes: {test['name']}", False, str(e))

    async def test_rendering(self):
        """Test rendering capabilities."""
        print("\n🎨 Testing Rendering...")
        print("-" * 50)

        # Create a beautiful test scene for rendering
        project_result = await self.client.call_tool(
            "create_blender_project",
            {"name": "render_showcase", "template": "studio_lighting"},
        )

        if not project_result.get("success"):
            await self.log_result("Render test setup", False, "Failed to create project")
            return

        project_path = project_result["project_path"]
        self.created_projects.append(project_path)

        # Create an interesting scene
        objects = [
            {"type": "monkey", "name": "MainSubject", "location": [0, 0, 1.5]},
            {
                "type": "torus",
                "name": "Decoration1",
                "location": [2.5, 0, 1],
                "scale": [0.7, 0.7, 0.7],
            },
            {
                "type": "sphere",
                "name": "Decoration2",
                "location": [-2.5, 0, 1],
                "scale": [0.8, 0.8, 0.8],
            },
            {
                "type": "plane",
                "name": "Floor",
                "location": [0, 0, 0],
                "scale": [10, 10, 1],
            },
        ]

        await self.client.call_tool("add_primitive_objects", {"project": project_path, "objects": objects})

        # Apply nice materials
        materials = [
            (
                "MainSubject",
                {"type": "metal", "roughness": 0.3, "base_color": [0.8, 0.6, 0.2, 1.0]},
            ),
            ("Decoration1", {"type": "glass", "roughness": 0.0}),
            (
                "Decoration2",
                {
                    "type": "emission",
                    "emission_strength": 2.0,
                    "base_color": [0.2, 0.5, 1.0, 1.0],
                },
            ),
            (
                "Floor",
                {
                    "type": "principled",
                    "roughness": 0.8,
                    "base_color": [0.3, 0.3, 0.3, 1.0],
                },
            ),
        ]

        for obj_name, material in materials:
            await self.client.call_tool(
                "apply_material",
                {
                    "project": project_path,
                    "object_name": obj_name,
                    "material": material,
                },
            )

        # Test different render engines and settings
        render_tests = [
            {
                "name": "EEVEE preview",
                "engine": "EEVEE",
                "samples": 32,
                "resolution": [1280, 720],
            },
            {
                "name": "CYCLES high quality",
                "engine": "CYCLES",
                "samples": 128,
                "resolution": [1920, 1080],
            },
            {
                "name": "WORKBENCH technical",
                "engine": "WORKBENCH",
                "samples": 1,
                "resolution": [1280, 720],
            },
        ]

        for test in render_tests:
            try:
                result = await self.client.call_tool(
                    "render_image",
                    {
                        "project": project_path,
                        "frame": 1,
                        "settings": {
                            "engine": test["engine"],
                            "samples": test["samples"],
                            "resolution": test["resolution"],
                            "format": "PNG",
                        },
                    },
                )

                if result.get("success"):
                    # If job_id is returned, it's async - wait for it
                    if "job_id" in result:
                        await self.wait_for_job(result["job_id"])

                    await self.log_result(
                        f"Render {test['name']}",
                        True,
                        f"{test['engine']} @ {test['resolution'][0]}x{test['resolution'][1]}",
                    )
                else:
                    await self.log_result(f"Render {test['name']}", False, result.get("error"))

            except Exception as e:
                await self.log_result(f"Render {test['name']}", False, str(e))

    async def test_import_export(self):
        """Test model import and export capabilities."""
        print("\n📦 Testing Import/Export...")
        print("-" * 50)

        # Create test project
        project_result = await self.client.call_tool(
            "create_blender_project",
            {"name": "import_export_test", "template": "empty"},
        )

        if not project_result.get("success"):
            await self.log_result("Import/Export test setup", False, "Failed to create project")
            return

        project_path = project_result["project_path"]
        self.created_projects.append(project_path)

        # Add some objects to export
        await self.client.call_tool(
            "add_primitive_objects",
            {
                "project": project_path,
                "objects": [
                    {"type": "cube", "name": "ExportCube", "location": [0, 0, 1]},
                    {"type": "sphere", "name": "ExportSphere", "location": [2, 0, 1]},
                ],
            },
        )

        # Test different export formats
        export_formats = ["OBJ", "FBX", "GLTF", "STL", "PLY"]

        for format in export_formats:
            try:
                result = await self.client.call_tool(
                    "export_model",
                    {
                        "project": project_path,
                        "format": format,
                        "objects": ["ExportCube", "ExportSphere"],
                        "output_name": f"test_export.{format.lower()}",
                    },
                )
                await self.log_result(f"Export to {format}", result.get("success", False))
            except Exception as e:
                await self.log_result(f"Export to {format}", False, str(e))

    async def wait_for_job(self, job_id: str, timeout: int = 60):
        """Wait for an async job to complete."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                status = await self.client.call_tool("get_job_status", {"job_id": job_id})

                if status.get("status") in ["COMPLETED", "FAILED", "CANCELLED"]:
                    return status

                await asyncio.sleep(2)

            except Exception:
                break

        return {"status": "TIMEOUT"}

    async def run_validation_suite(self):
        """Run the complete validation suite."""
        print("\n" + "=" * 60)
        print("🎬 BLENDER MCP SERVER VALIDATION SUITE")
        print("=" * 60)
        print(f"Server URL: {self.client.base_url}")
        print(f"Started: {datetime.now().isoformat()}")

        # Check server health first
        try:
            health = await self.client.call_tool("health", {})
            if health.get("status") != "healthy":
                print("❌ Server is not healthy!")
                return
        except Exception as e:
            print(f"❌ Cannot connect to server: {e}")
            print("\n📝 To start the server locally:")
            print("  1. Using Docker: docker-compose up -d mcp-blender")
            print("  2. Using Python: python -m tools.mcp.blender.server")
            return

        # Run all tests
        test_methods = [
            self.test_project_templates,
            self.test_object_creation,
            self.test_materials_and_lighting,
            self.test_physics_simulation,
            self.test_animation,
            self.test_geometry_nodes,
            self.test_rendering,
            self.test_import_export,
        ]

        for test_method in test_methods:
            try:
                await test_method()
            except Exception as e:
                print(f"❌ Test failed with exception: {e}")

        # Print summary
        print("\n" + "=" * 60)
        print("📊 VALIDATION SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in self.test_results if r["success"])
        failed = len(self.test_results) - passed

        print(f"Total Tests: {len(self.test_results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Success Rate: {(passed/len(self.test_results)*100):.1f}%")

        if failed > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['details']}")

        # List created projects
        if self.created_projects:
            print(f"\n📁 Created {len(self.created_projects)} test projects:")
            for project in self.created_projects[:5]:  # Show first 5
                print(f"  - {project}")
            if len(self.created_projects) > 5:
                print(f"  ... and {len(self.created_projects) - 5} more")

        print("\n" + "=" * 60)
        print("Validation completed!")
        print("=" * 60)


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Blender MCP Server Validation")
    parser.add_argument("--server-url", default="http://localhost:8017", help="Blender MCP server URL")

    args = parser.parse_args()

    validator = BlenderValidationSuite(args.server_url)
    await validator.run_validation_suite()


if __name__ == "__main__":
    asyncio.run(main())
