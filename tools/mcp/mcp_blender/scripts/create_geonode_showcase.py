#!/usr/bin/env python3
"""Create geometry nodes showcase projects for review.

This script creates multiple Blender projects demonstrating each
geometry node setup type. Run this to generate sample .blend files
that can be opened locally for review.
"""

import asyncio
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_blender.server import BlenderMCPServer


async def create_showcase_projects():
    """Create showcase projects for all geometry node setup types."""
    # Initialize server with output directory
    output_base = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..",
        "..",
        "..",
        "..",
        "outputs",
        "blender",
        "geonode_showcase",
    )
    os.makedirs(output_base, exist_ok=True)

    server = BlenderMCPServer(base_dir=output_base)

    print("=" * 60)
    print("Creating Geometry Nodes Showcase Projects")
    print("=" * 60)

    # Define showcase projects with their configurations
    showcases = [
        {
            "name": "01_scatter_forest",
            "description": "Forest floor with scattered objects",
            "node_setup": "scatter",
            "parameters": {
                "count": 150,
                "seed": 42,
                "scale_variance": 0.4,
                "scale_base": 0.5,
                "random_rotation": True,
            },
        },
        {
            "name": "02_linear_array",
            "description": "Linear array of cubes",
            "node_setup": "array",
            "parameters": {
                "count": 15,
                "offset_x": 1.5,
                "offset_y": 0.0,
                "offset_z": 0.0,
            },
        },
        {
            "name": "03_3d_grid",
            "description": "3D grid array of spheres",
            "node_setup": "grid",
            "parameters": {
                "count_x": 4,
                "count_y": 4,
                "count_z": 4,
                "spacing_x": 2.0,
                "spacing_y": 2.0,
                "spacing_z": 2.0,
            },
        },
        {
            "name": "04_spiral_staircase",
            "description": "Spiral curve with tube profile",
            "node_setup": "spiral",
            "parameters": {
                "turns": 4,
                "points": 200,
                "radius_start": 1.0,
                "radius_end": 3.0,
                "height": 5.0,
                "profile_radius": 0.2,
            },
        },
        {
            "name": "05_torus_ring",
            "description": "Torus shape from curve",
            "node_setup": "curve",
            "parameters": {
                "radius": 3.0,
                "profile_radius": 0.5,
                "resolution": 64,
            },
        },
        {
            "name": "06_wave_terrain",
            "description": "Wave-deformed terrain",
            "node_setup": "wave_deform",
            "parameters": {
                "amplitude": 0.8,
                "frequency": 2.5,
                "phase": 0.0,
                "axis": "Z",
                "wave_axis": "X",
                "subdivisions": 5,
            },
        },
        {
            "name": "07_twisted_tower",
            "description": "Twisted cylinder tower",
            "node_setup": "twist",
            "parameters": {
                "angle": 6.28,  # Full 360-degree twist
                "axis": "Z",
                "subdivisions": 5,
            },
        },
        {
            "name": "08_noise_terrain",
            "description": "Noise-displaced terrain",
            "node_setup": "noise_displace",
            "parameters": {
                "strength": 1.0,
                "scale": 3.0,
                "detail": 4.0,
                "roughness": 0.6,
                "use_normals": True,
                "subdivisions": 5,
            },
        },
        {
            "name": "09_extruded_building",
            "description": "Extruded building shape",
            "node_setup": "extrude",
            "parameters": {
                "offset": 3.0,
                "individual": False,
                "top_scale": 0.7,
            },
        },
        {
            "name": "10_volume_cloud",
            "description": "Volume-based cloud mesh",
            "node_setup": "volume",
            "parameters": {
                "density": 1.0,
                "size_x": 4.0,
                "size_y": 4.0,
                "size_z": 3.0,
                "threshold": 0.15,
            },
        },
        {
            "name": "11_voronoi_pattern",
            "description": "Voronoi-based scatter pattern",
            "node_setup": "voronoi_scatter",
            "parameters": {
                "scale": 3.0,
                "randomness": 0.8,
                "instance_scale": 0.2,
            },
        },
        {
            "name": "12_point_cloud",
            "description": "Mesh vertices as point cloud",
            "node_setup": "mesh_to_points",
            "parameters": {
                "point_radius": 0.1,
                "use_spheres": True,
            },
        },
        {
            "name": "13_custom_displacement",
            "description": "Custom noise displacement",
            "node_setup": "custom",
            "parameters": {
                "subdivision_level": 4,
                "noise_scale": 5.0,
                "noise_detail": 3.0,
                "displacement_strength": 0.5,
            },
        },
    ]

    results = []

    for i, showcase in enumerate(showcases, 1):
        print(f"\n[{i}/{len(showcases)}] Creating: {showcase['name']}")
        print(f"    Description: {showcase['description']}")

        try:
            # Create project
            project_result = await server._create_project(
                {
                    "name": showcase["name"],
                    "template": "procedural",
                    "settings": {
                        "resolution": [1920, 1080],
                        "fps": 24,
                        "engine": "CYCLES",
                    },
                }
            )

            if not project_result.get("success"):
                print(f"    ERROR: Failed to create project")
                results.append({"name": showcase["name"], "success": False, "error": "Project creation failed"})
                continue

            project_path = project_result["project_path"]
            print(f"    Project created: {project_path}")

            # Apply geometry nodes
            geonode_result = await server._create_geometry_nodes(
                {
                    "project": project_path,
                    "object_name": f"{showcase['name']}_object",
                    "node_setup": showcase["node_setup"],
                    "parameters": showcase["parameters"],
                }
            )

            if geonode_result.get("success"):
                print(f"    Geometry nodes applied: {showcase['node_setup']}")
                results.append({"name": showcase["name"], "success": True, "path": project_path})
            else:
                print(f"    ERROR: Failed to apply geometry nodes")
                results.append({"name": showcase["name"], "success": False, "error": "Geometry nodes failed"})

        except Exception as e:
            print(f"    ERROR: {e}")
            results.append({"name": showcase["name"], "success": False, "error": str(e)})

    # Print summary
    print("\n" + "=" * 60)
    print("SHOWCASE CREATION SUMMARY")
    print("=" * 60)

    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]

    print(f"\nSuccessful: {len(successful)}/{len(results)}")
    for r in successful:
        print(f"  - {r['name']}: {r['path']}")

    if failed:
        print(f"\nFailed: {len(failed)}/{len(results)}")
        for r in failed:
            print(f"  - {r['name']}: {r.get('error', 'Unknown error')}")

    print(f"\nOutput directory: {output_base}/projects/")
    print("Open these .blend files in Blender to review the geometry nodes!")

    return results


async def create_combined_showcase():
    """Create a single project with multiple geometry node objects."""
    output_base = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..",
        "..",
        "..",
        "..",
        "outputs",
        "blender",
        "geonode_showcase",
    )
    os.makedirs(output_base, exist_ok=True)

    server = BlenderMCPServer(base_dir=output_base)

    print("\n" + "=" * 60)
    print("Creating Combined Geometry Nodes Showcase")
    print("=" * 60)

    # Create single project
    project_result = await server._create_project(
        {
            "name": "combined_geonode_showcase",
            "template": "procedural",
            "settings": {
                "resolution": [1920, 1080],
                "fps": 24,
                "engine": "CYCLES",
            },
        }
    )

    if not project_result.get("success"):
        print("ERROR: Failed to create combined project")
        return

    project_path = project_result["project_path"]
    print(f"Project created: {project_path}")

    # Add multiple objects with different geometry node setups
    setups = [
        ("spiral_obj", "spiral", {"turns": 3, "height": 4, "radius_end": 2}, [0, 0, 0]),
        ("wave_obj", "wave_deform", {"amplitude": 0.5, "frequency": 3}, [-6, 0, 0]),
        ("twist_obj", "twist", {"angle": 4.71}, [6, 0, 0]),
        ("scatter_obj", "scatter", {"count": 50, "scale_base": 0.3}, [0, -6, 0]),
        ("grid_obj", "grid", {"count_x": 3, "count_y": 3, "spacing_x": 1}, [0, 6, 0]),
    ]

    for obj_name, node_setup, params, _location in setups:
        try:
            result = await server._create_geometry_nodes(
                {
                    "project": project_path,
                    "object_name": obj_name,
                    "node_setup": node_setup,
                    "parameters": params,
                }
            )
            status = "OK" if result.get("success") else "FAILED"
            print(f"  {obj_name} ({node_setup}): {status}")
        except Exception as e:
            print(f"  {obj_name} ({node_setup}): ERROR - {e}")

    print(f"\nCombined showcase saved to: {project_path}")


if __name__ == "__main__":
    print("Geometry Nodes Showcase Creator")
    print("-" * 40)

    # Run both individual and combined showcases
    asyncio.run(create_showcase_projects())
    asyncio.run(create_combined_showcase())
