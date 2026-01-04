#!/usr/bin/env python3
"""Tests for enhanced geometry nodes functionality."""

from unittest.mock import AsyncMock, Mock

import pytest

from mcp_blender.core.blender_executor import BlenderExecutor
from mcp_blender.server import BlenderMCPServer


class TestGeometryNodes:
    """Test suite for geometry nodes functionality."""

    @pytest.fixture
    def server(self, tmp_path):
        """Create a server instance with temp directories."""
        server = BlenderMCPServer(base_dir=str(tmp_path))
        return server

    @pytest.fixture
    def mock_executor(self):
        """Create a mock BlenderExecutor."""
        executor = Mock(spec=BlenderExecutor)
        executor.execute_script = AsyncMock(return_value={"success": True})
        executor.kill_process = Mock()
        return executor

    def test_geometry_nodes_tool_registered(self, server):
        """Test that geometry nodes tool is registered with all setup types."""
        tools = server.get_tools()

        assert "create_geometry_nodes" in tools
        tool = tools["create_geometry_nodes"]
        assert "description" in tool
        assert "parameters" in tool

        # Check that all node_setup types are available
        schema = tool["parameters"]
        node_setup_enum = schema["properties"]["node_setup"]["enum"]

        expected_setups = [
            "scatter",
            "array",
            "grid",
            "curve",
            "spiral",
            "volume",
            "wave_deform",
            "twist",
            "noise_displace",
            "extrude",
            "voronoi_scatter",
            "mesh_to_points",
            "crystal_scatter",
            "crystal_cluster",
            "custom",
        ]

        for setup in expected_setups:
            assert setup in node_setup_enum, f"Missing node_setup type: {setup}"

    @pytest.mark.asyncio
    async def test_scatter_setup(self, server, mock_executor):
        """Test scatter geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "ScatterPlane",
            "node_setup": "scatter",
            "parameters": {
                "count": 200,
                "seed": 42,
                "scale_variance": 0.3,
                "scale_base": 1.0,
                "random_rotation": True,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "scatter"
        assert result["object"] == "ScatterPlane"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_array_setup(self, server, mock_executor):
        """Test linear array geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "ArrayCube",
            "node_setup": "array",
            "parameters": {
                "count": 10,
                "offset_x": 2.5,
                "offset_y": 0.0,
                "offset_z": 0.0,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "array"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_grid_setup(self, server, mock_executor):
        """Test 2D/3D grid geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "GridArray",
            "node_setup": "grid",
            "parameters": {
                "count_x": 5,
                "count_y": 5,
                "count_z": 3,
                "spacing_x": 2.0,
                "spacing_y": 2.0,
                "spacing_z": 2.0,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "grid"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_spiral_setup(self, server, mock_executor):
        """Test spiral geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "SpiralCurve",
            "node_setup": "spiral",
            "parameters": {
                "turns": 5,
                "points": 150,
                "radius_start": 0.5,
                "radius_end": 4.0,
                "height": 3.0,
                "profile_radius": 0.15,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "spiral"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_curve_setup(self, server, mock_executor):
        """Test curve-based geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "TorusCurve",
            "node_setup": "curve",
            "parameters": {
                "radius": 3.0,
                "profile_radius": 0.2,
                "resolution": 64,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "curve"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_wave_deform_setup(self, server, mock_executor):
        """Test wave deformation geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "WavePlane",
            "node_setup": "wave_deform",
            "parameters": {
                "amplitude": 0.5,
                "frequency": 3.0,
                "phase": 0.0,
                "axis": "Z",
                "wave_axis": "X",
                "subdivisions": 4,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "wave_deform"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_twist_setup(self, server, mock_executor):
        """Test twist deformation geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "TwistedCylinder",
            "node_setup": "twist",
            "parameters": {
                "angle": 6.28,  # 2*pi = full rotation
                "axis": "Z",
                "subdivisions": 4,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "twist"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_noise_displace_setup(self, server, mock_executor):
        """Test noise displacement geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "DisplacedPlane",
            "node_setup": "noise_displace",
            "parameters": {
                "strength": 0.8,
                "scale": 5.0,
                "detail": 3.0,
                "roughness": 0.5,
                "use_normals": True,
                "subdivisions": 4,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "noise_displace"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_extrude_setup(self, server, mock_executor):
        """Test extrusion geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "ExtrudedPlane",
            "node_setup": "extrude",
            "parameters": {
                "offset": 2.0,
                "individual": False,
                "top_scale": 0.8,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "extrude"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_volume_setup(self, server, mock_executor):
        """Test volume-based geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "VolumeMesh",
            "node_setup": "volume",
            "parameters": {
                "density": 1.0,
                "size_x": 4.0,
                "size_y": 4.0,
                "size_z": 4.0,
                "threshold": 0.1,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "volume"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_voronoi_scatter_setup(self, server, mock_executor):
        """Test Voronoi-based scatter geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "VoronoiScatter",
            "node_setup": "voronoi_scatter",
            "parameters": {
                "scale": 5.0,
                "randomness": 1.0,
                "instance_scale": 0.15,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "voronoi_scatter"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_mesh_to_points_setup(self, server, mock_executor):
        """Test mesh to points geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "PointCloud",
            "node_setup": "mesh_to_points",
            "parameters": {
                "point_radius": 0.1,
                "use_spheres": True,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "mesh_to_points"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_crystal_scatter_setup(self, server, mock_executor):
        """Test crystal scatter geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "CrystalRock",
            "node_setup": "crystal_scatter",
            "parameters": {
                "density": 15.0,
                "seed": 42,
                "crystal_scale": 1.0,
                "crystal_height_min": 0.1,
                "crystal_height_max": 0.4,
                "crystal_radius": 0.05,
                "facets": 6,
                "tilt_variance": 0.2,
                "use_poisson": True,
                "apply_crystal_material": True,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "crystal_scatter"
        assert result["object"] == "CrystalRock"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_crystal_cluster_setup(self, server, mock_executor):
        """Test crystal cluster geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "CrystalCave",
            "node_setup": "crystal_cluster",
            "parameters": {
                "cluster_scale": 3.0,
                "cluster_density": 8.0,
                "crystals_per_cluster_min": 2,
                "crystals_per_cluster_max": 4,
                "cluster_radius": 0.3,
                "crystal_height_min": 0.1,
                "crystal_height_max": 0.3,
                "crystal_radius": 0.04,
                "facets": 6,
                "seed": 42,
                "apply_crystal_material": True,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "crystal_cluster"
        assert result["object"] == "CrystalCave"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_crystal_scatter_with_material_params(self, server, mock_executor):
        """Test crystal scatter with custom material parameters."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "AmethystCrystals",
            "node_setup": "crystal_scatter",
            "parameters": {
                "density": 20.0,
                "facets": 8,  # Octagonal crystals
                "crystal_color": [0.6, 0.4, 0.8, 1.0],  # Purple
                "crystal_transmission": 0.85,
                "crystal_ior": 1.55,
                "apply_crystal_material": True,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "crystal_scatter"
        mock_executor.execute_script.assert_called_once()

        # Verify parameters were passed correctly
        call_args = mock_executor.execute_script.call_args[0]
        script_args = call_args[1]
        assert script_args["parameters"]["facets"] == 8
        assert script_args["parameters"]["crystal_color"] == [0.6, 0.4, 0.8, 1.0]

    @pytest.mark.asyncio
    async def test_custom_setup(self, server, mock_executor):
        """Test custom geometry nodes setup."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "CustomMesh",
            "node_setup": "custom",
            "parameters": {
                "subdivision_level": 3,
                "noise_scale": 8.0,
                "noise_detail": 3.0,
                "displacement_strength": 0.5,
            },
        }

        result = await server._create_geometry_nodes(args)

        assert result["success"] is True
        assert result["node_setup"] == "custom"
        mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_geometry_nodes_with_minimal_params(self, server, mock_executor):
        """Test geometry nodes with minimal parameters (using defaults)."""
        server.blender_executor = mock_executor

        # Test each setup type with minimal params
        setups = [
            "scatter",
            "array",
            "grid",
            "curve",
            "spiral",
            "volume",
            "wave_deform",
            "twist",
            "noise_displace",
            "extrude",
            "voronoi_scatter",
            "mesh_to_points",
            "crystal_scatter",
            "crystal_cluster",
            "custom",
        ]

        for setup in setups:
            mock_executor.reset_mock()

            args = {
                "project": "test.blend",
                "object_name": f"{setup}_test",
                "node_setup": setup,
                "parameters": {},  # Empty params - should use defaults
            }

            result = await server._create_geometry_nodes(args)

            assert result["success"] is True, f"Failed for setup: {setup}"
            assert result["node_setup"] == setup
            mock_executor.execute_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_executor_receives_correct_args(self, server, mock_executor):
        """Test that the executor receives correctly formatted arguments."""
        server.blender_executor = mock_executor

        args = {
            "project": "test.blend",
            "object_name": "TestObject",
            "node_setup": "spiral",
            "parameters": {"turns": 5, "height": 3.0},
        }

        await server._create_geometry_nodes(args)

        # Verify the execute_script was called with correct script name
        call_args = mock_executor.execute_script.call_args[0]
        assert call_args[0] == "geometry_nodes.py"

        # Verify the script args contain the operation and parameters
        script_args = call_args[1]
        assert script_args["operation"] == "create_geometry_nodes"
        assert script_args["node_setup"] == "spiral"
        assert script_args["parameters"]["turns"] == 5
        assert script_args["parameters"]["height"] == 3.0


class TestGeometryNodesParameters:
    """Test geometry nodes parameter validation and handling."""

    @pytest.fixture
    def server(self, tmp_path):
        """Create a server instance."""
        return BlenderMCPServer(base_dir=str(tmp_path))

    def test_scatter_parameters_schema(self, server):
        """Test scatter setup has correct parameter options."""
        tools = server.get_tools()
        params = tools["create_geometry_nodes"]["parameters"]["properties"]["parameters"]["properties"]

        # Check scatter-relevant parameters
        assert "count" in params
        assert "seed" in params
        assert "scale_variance" in params
        assert "scale_base" in params
        assert "random_rotation" in params
        assert "align_to_normal" in params
        assert "instance_object" in params

    def test_grid_parameters_schema(self, server):
        """Test grid setup has correct parameter options."""
        tools = server.get_tools()
        params = tools["create_geometry_nodes"]["parameters"]["properties"]["parameters"]["properties"]

        # Check grid-relevant parameters
        assert "count_x" in params
        assert "count_y" in params
        assert "count_z" in params
        assert "spacing_x" in params
        assert "spacing_y" in params
        assert "spacing_z" in params

    def test_wave_deform_parameters_schema(self, server):
        """Test wave deform has correct parameter options."""
        tools = server.get_tools()
        params = tools["create_geometry_nodes"]["parameters"]["properties"]["parameters"]["properties"]

        # Check wave-relevant parameters
        assert "amplitude" in params
        assert "frequency" in params
        assert "phase" in params
        assert "axis" in params
        assert "wave_axis" in params
        assert "subdivisions" in params

    def test_spiral_parameters_schema(self, server):
        """Test spiral setup has correct parameter options."""
        tools = server.get_tools()
        params = tools["create_geometry_nodes"]["parameters"]["properties"]["parameters"]["properties"]

        # Check spiral-relevant parameters
        assert "turns" in params
        assert "radius_start" in params
        assert "radius_end" in params
        assert "height" in params
        assert "profile_radius" in params

    def test_crystal_scatter_parameters_schema(self, server):
        """Test crystal scatter setup has correct parameter options."""
        tools = server.get_tools()
        params = tools["create_geometry_nodes"]["parameters"]["properties"]["parameters"]["properties"]

        # Check crystal scatter parameters
        assert "crystal_scale" in params
        assert "crystal_height_min" in params
        assert "crystal_height_max" in params
        assert "crystal_radius" in params
        assert "facets" in params
        assert "tilt_variance" in params
        assert "use_poisson" in params
        assert "apply_crystal_material" in params

        # Check defaults
        assert params["facets"]["default"] == 6
        assert params["crystal_height_min"]["default"] == 0.1
        assert params["crystal_height_max"]["default"] == 0.5

    def test_crystal_cluster_parameters_schema(self, server):
        """Test crystal cluster setup has correct parameter options."""
        tools = server.get_tools()
        params = tools["create_geometry_nodes"]["parameters"]["properties"]["parameters"]["properties"]

        # Check cluster-specific parameters
        assert "cluster_scale" in params
        assert "cluster_density" in params
        assert "crystals_per_cluster_min" in params
        assert "crystals_per_cluster_max" in params
        assert "cluster_radius" in params

        # Check defaults
        assert params["cluster_scale"]["default"] == 5.0
        assert params["crystals_per_cluster_min"]["default"] == 2
        assert params["crystals_per_cluster_max"]["default"] == 5

    def test_crystal_material_parameters_schema(self, server):
        """Test crystal material parameters are in schema."""
        tools = server.get_tools()
        params = tools["create_geometry_nodes"]["parameters"]["properties"]["parameters"]["properties"]

        # Check material parameters
        assert "crystal_color" in params
        assert "crystal_transmission" in params
        assert "crystal_roughness" in params
        assert "crystal_ior" in params

        # Check defaults
        assert params["crystal_transmission"]["default"] == 0.9
        assert params["crystal_roughness"]["default"] == 0.1
        assert params["crystal_ior"]["default"] == 1.45


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
