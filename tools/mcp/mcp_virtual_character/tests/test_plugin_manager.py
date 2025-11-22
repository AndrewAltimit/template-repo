"""
Unit tests for plugin manager.
"""

from pathlib import Path

import pytest
import pytest_asyncio

from mcp_virtual_character.backends.base import BackendAdapter
from mcp_virtual_character.backends.mock import MockBackend
from mcp_virtual_character.server.plugin_manager import PluginManager


class TestPluginManager:
    """Test PluginManager class."""

    @pytest_asyncio.fixture
    async def manager(self):
        """Create plugin manager instance."""
        manager = PluginManager()
        yield manager
        await manager.cleanup()

    @pytest.mark.asyncio
    async def test_creation(self, manager):
        """Test PluginManager creation."""
        assert manager.plugins == {}
        assert manager.instances == {}
        assert manager.active_backend is None

    @pytest.mark.asyncio
    async def test_discover_builtin(self, manager):
        """Test discovering built-in plugins."""
        plugins = await manager.discover_plugins()

        # Should at least find the mock backend
        assert "mock" in plugins
        assert "mock" in manager.plugins
        assert manager.plugins["mock"] == MockBackend

    @pytest.mark.asyncio
    async def test_load_plugin(self, manager):
        """Test loading a plugin."""
        # Discover plugins first
        await manager.discover_plugins()

        # Load mock backend
        config = {"world_name": "TestWorld"}
        backend = await manager.load_plugin("mock", config)

        assert backend is not None
        assert isinstance(backend, MockBackend)
        assert backend.is_connected is True
        assert "mock" in manager.instances

    @pytest.mark.asyncio
    async def test_load_nonexistent_plugin(self, manager):
        """Test loading non-existent plugin."""
        with pytest.raises(ValueError, match="Plugin 'nonexistent' not found"):
            await manager.load_plugin("nonexistent", {})

    @pytest.mark.asyncio
    async def test_switch_backend(self, manager):
        """Test switching backends."""
        # Discover plugins
        await manager.discover_plugins()

        # Switch to mock backend
        success = await manager.switch_backend("mock", {"world_name": "World1"})
        assert success is True
        assert manager.active_backend == "mock"

        # Get active backend
        backend = manager.get_active_backend()
        assert backend is not None
        assert isinstance(backend, MockBackend)

    @pytest.mark.asyncio
    async def test_switch_backend_disconnects_current(self, manager):
        """Test that switching backends disconnects current one."""
        await manager.discover_plugins()

        # Load first backend
        await manager.switch_backend("mock", {"world_name": "World1"})
        backend1 = manager.get_active_backend()
        assert backend1.is_connected is True

        # Create a second mock backend class for testing
        class MockBackend2(MockBackend):
            @property
            def backend_name(self) -> str:
                return "mock2"

        manager.plugins["mock2"] = MockBackend2

        # Switch to second backend
        await manager.switch_backend("mock2", {"world_name": "World2"})

        # First backend should be disconnected
        assert backend1.is_connected is False
        assert manager.active_backend == "mock2"

    @pytest.mark.asyncio
    async def test_disconnect_current(self, manager):
        """Test disconnecting current backend."""
        await manager.discover_plugins()
        await manager.switch_backend("mock", {})

        backend = manager.get_active_backend()
        assert backend.is_connected is True

        await manager.disconnect_current()

        assert backend.is_connected is False
        assert manager.active_backend is None
        assert manager.get_active_backend() is None

    @pytest.mark.asyncio
    async def test_cleanup(self, manager):
        """Test cleanup of all instances."""
        await manager.discover_plugins()

        # Load multiple backends
        backend1 = await manager.load_plugin("mock", {"world_name": "World1"})

        # Create another mock backend for testing
        class MockBackend2(MockBackend):
            @property
            def backend_name(self) -> str:
                return "mock2"

        manager.plugins["mock2"] = MockBackend2
        backend2 = await manager.load_plugin("mock2", {"world_name": "World2"})

        assert backend1.is_connected is True
        assert backend2.is_connected is True

        # Cleanup
        await manager.cleanup()

        assert backend1.is_connected is False
        assert backend2.is_connected is False
        assert len(manager.instances) == 0
        assert manager.active_backend is None

    @pytest.mark.asyncio
    async def test_list_available_plugins(self, manager):
        """Test listing available plugins."""
        await manager.discover_plugins()
        await manager.switch_backend("mock", {})

        plugins = manager.list_available_plugins()

        assert len(plugins) > 0

        # Find mock plugin info
        mock_info = next((p for p in plugins if p["name"] == "mock"), None)
        assert mock_info is not None
        assert mock_info["class"] == "MockBackend"
        assert mock_info["loaded"] is True
        assert mock_info["active"] is True
        assert "capabilities" in mock_info

    @pytest.mark.asyncio
    async def test_health_check(self, manager):
        """Test health check on all plugins."""
        await manager.discover_plugins()
        await manager.load_plugin("mock", {"world_name": "World1"})

        health = await manager.health_check()

        assert health["active_backend"] is None  # Not set as active yet
        assert "backends" in health
        assert "mock" in health["backends"]
        assert health["backends"]["mock"]["connected"] is True

    @pytest.mark.asyncio
    async def test_plugin_validation(self, manager):
        """Test plugin validation."""

        # Valid plugin class
        class ValidPlugin(BackendAdapter):
            @property
            def backend_name(self) -> str:
                return "valid"

            async def connect(self, config):
                return True

            async def disconnect(self):
                pass

            async def send_animation_data(self, data):
                return True

            async def send_audio_data(self, audio):
                return True

            async def receive_state(self):
                return None

            async def capture_video_frame(self):
                return None

        assert manager._is_valid_plugin(ValidPlugin) is True

        # Invalid plugin (base class)
        assert manager._is_valid_plugin(BackendAdapter) is False

        # Invalid plugin (not a class)
        assert manager._is_valid_plugin("not_a_class") is False

        # Invalid plugin (not a subclass)
        class NotABackend:
            pass

        assert manager._is_valid_plugin(NotABackend) is False

    @pytest.mark.asyncio
    async def test_plugin_with_custom_directory(self):
        """Test plugin manager with custom directory."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = PluginManager(plugin_directory=tmpdir)

            # Should include the custom directory in paths
            assert Path(tmpdir) in manager.plugin_paths

            # Should still discover built-in plugins
            plugins = await manager.discover_plugins()
            assert "mock" in plugins

    @pytest.mark.asyncio
    async def test_error_handling_in_plugin_load(self, manager):
        """Test error handling when plugin fails to connect."""

        # Create a failing plugin
        class FailingPlugin(BackendAdapter):
            @property
            def backend_name(self) -> str:
                return "failing"

            async def connect(self, config):
                raise Exception("Connection failed")

            async def disconnect(self):
                pass

            async def send_animation_data(self, data):
                return False

            async def send_audio_data(self, audio):
                return False

            async def receive_state(self):
                return None

            async def capture_video_frame(self):
                return None

        manager.plugins["failing"] = FailingPlugin

        with pytest.raises(RuntimeError, match="Failed to load plugin 'failing'"):
            await manager.load_plugin("failing", {})

    @pytest.mark.asyncio
    async def test_plugin_connection_failure(self, manager):
        """Test plugin that returns False on connect."""

        class NoConnectPlugin(BackendAdapter):
            @property
            def backend_name(self) -> str:
                return "noconnect"

            async def connect(self, config):
                return False  # Connection fails

            async def disconnect(self):
                pass

            async def send_animation_data(self, data):
                return False

            async def send_audio_data(self, audio):
                return False

            async def receive_state(self):
                return None

            async def capture_video_frame(self):
                return None

        manager.plugins["noconnect"] = NoConnectPlugin

        with pytest.raises(RuntimeError, match="Plugin 'noconnect' failed to connect"):
            await manager.load_plugin("noconnect", {})
