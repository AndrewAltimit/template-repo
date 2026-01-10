"""Unit tests for Desktop Control MCP Server"""

import os
from unittest.mock import Mock, patch

from mcp_desktop_control.backends.base import ScreenInfo, WindowInfo
import pytest


class TestWindowInfo:
    """Tests for WindowInfo dataclass"""

    def test_window_info_creation(self):
        """Test creating a WindowInfo object"""
        info = WindowInfo(
            id="12345",
            title="Test Window",
            x=100,
            y=200,
            width=800,
            height=600,
        )
        assert info.id == "12345"
        assert info.title == "Test Window"
        assert info.x == 100
        assert info.y == 200
        assert info.width == 800
        assert info.height == 600
        assert info.is_visible is True  # default

    def test_window_info_to_dict(self):
        """Test converting WindowInfo to dictionary"""
        info = WindowInfo(
            id="12345",
            title="Test Window",
            x=100,
            y=200,
            width=800,
            height=600,
            process_id=1234,
            process_name="test_process",
        )
        result = info.to_dict()
        assert result["id"] == "12345"
        assert result["title"] == "Test Window"
        assert result["process_id"] == 1234
        assert result["process_name"] == "test_process"


class TestScreenInfo:
    """Tests for ScreenInfo dataclass"""

    def test_screen_info_creation(self):
        """Test creating a ScreenInfo object"""
        info = ScreenInfo(
            id=0,
            x=0,
            y=0,
            width=1920,
            height=1080,
            is_primary=True,
        )
        assert info.id == 0
        assert info.width == 1920
        assert info.height == 1080
        assert info.is_primary is True

    def test_screen_info_to_dict(self):
        """Test converting ScreenInfo to dictionary"""
        info = ScreenInfo(
            id=1,
            x=1920,
            y=0,
            width=1920,
            height=1080,
            name="HDMI-1",
        )
        result = info.to_dict()
        assert result["id"] == 1
        assert result["x"] == 1920
        assert result["name"] == "HDMI-1"


class TestDesktopControlServer:  # pylint: disable=too-many-public-methods
    """Tests for DesktopControlMCPServer"""

    @pytest.fixture
    def mock_backend(self):
        """Create a mock desktop backend"""
        backend = Mock()
        backend.platform_name = "mock"
        backend.is_available.return_value = True
        backend.get_screen_size.return_value = (1920, 1080)
        backend.list_screens.return_value = [ScreenInfo(id=0, x=0, y=0, width=1920, height=1080, is_primary=True)]
        backend.list_windows.return_value = [WindowInfo(id="123", title="Test Window", x=0, y=0, width=800, height=600)]
        backend.get_active_window.return_value = WindowInfo(id="123", title="Active Window", x=0, y=0, width=800, height=600)
        backend.get_mouse_position.return_value = (500, 500)
        backend.screenshot_screen.return_value = b"\x89PNG\r\n\x1a\n"  # PNG header
        return backend

    @pytest.fixture
    def server(self, mock_backend):
        """Create server with mock backend"""
        with patch("mcp_desktop_control.server.get_backend", return_value=mock_backend):
            from mcp_desktop_control.server import DesktopControlMCPServer

            server = DesktopControlMCPServer()
            return server

    def test_get_tools(self, server):
        """Test that get_tools returns expected tools"""
        tools = server.get_tools()
        assert "list_windows" in tools
        assert "screenshot_screen" in tools
        assert "click_mouse" in tools
        assert "type_text" in tools
        assert "desktop_status" in tools

    @pytest.mark.asyncio
    async def test_desktop_status(self, server):
        """Test desktop_status tool"""
        result = await server.desktop_status()
        assert result["success"] is True
        assert result["available"] is True
        assert "platform" in result
        assert "screen_count" in result

    @pytest.mark.asyncio
    async def test_list_windows(self, server):
        """Test list_windows tool"""
        result = await server.list_windows()
        assert result["success"] is True
        assert result["count"] == 1
        assert len(result["windows"]) == 1
        assert result["windows"][0]["title"] == "Test Window"

    @pytest.mark.asyncio
    async def test_list_windows_with_filter(self, server, mock_backend):
        """Test list_windows with title filter"""
        result = await server.list_windows(title_filter="Test.*")
        assert result["success"] is True
        mock_backend.list_windows.assert_called_with(title_filter="Test.*", visible_only=True)

    @pytest.mark.asyncio
    async def test_get_active_window(self, server):
        """Test get_active_window tool"""
        result = await server.get_active_window()
        assert result["success"] is True
        assert result["window"]["title"] == "Active Window"

    @pytest.mark.asyncio
    async def test_focus_window(self, server, mock_backend):
        """Test focus_window tool"""
        mock_backend.focus_window.return_value = True
        result = await server.focus_window("123")
        assert result["success"] is True
        assert result["window_id"] == "123"
        mock_backend.focus_window.assert_called_with("123")

    @pytest.mark.asyncio
    async def test_move_window(self, server, mock_backend):
        """Test move_window tool"""
        mock_backend.move_window.return_value = True
        result = await server.move_window("123", 100, 200)
        assert result["success"] is True
        assert result["position"] == {"x": 100, "y": 200}
        mock_backend.move_window.assert_called_with("123", 100, 200)

    @pytest.mark.asyncio
    async def test_resize_window(self, server, mock_backend):
        """Test resize_window tool"""
        mock_backend.resize_window.return_value = True
        result = await server.resize_window("123", 1024, 768)
        assert result["success"] is True
        assert result["size"] == {"width": 1024, "height": 768}

    @pytest.mark.asyncio
    async def test_screenshot_screen(self, server, mock_backend, tmp_path):
        """Test screenshot_screen tool"""
        # Override output dir to use temp path
        server._output_dir = str(tmp_path)
        mock_backend.screenshot_screen.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        result = await server.screenshot_screen()
        assert result["success"] is True
        assert result["format"] == "png"
        assert "output_path" in result
        assert result["output_path"].endswith(".png")
        # Verify file was created
        assert os.path.exists(result["output_path"])

    @pytest.mark.asyncio
    async def test_screenshot_window(self, server, mock_backend, tmp_path):
        """Test screenshot_window tool"""
        server._output_dir = str(tmp_path)
        mock_backend.screenshot_window.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        result = await server.screenshot_window("123")
        assert result["success"] is True
        assert result["window_id"] == "123"
        assert "output_path" in result

    @pytest.mark.asyncio
    async def test_screenshot_region(self, server, mock_backend, tmp_path):
        """Test screenshot_region tool"""
        server._output_dir = str(tmp_path)
        mock_backend.screenshot_region.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        result = await server.screenshot_region(100, 100, 200, 200)
        assert result["success"] is True
        assert result["region"] == {"x": 100, "y": 100, "width": 200, "height": 200}
        assert "output_path" in result

    @pytest.mark.asyncio
    async def test_get_mouse_position(self, server):
        """Test get_mouse_position tool"""
        result = await server.get_mouse_position()
        assert result["success"] is True
        assert result["x"] == 500
        assert result["y"] == 500

    @pytest.mark.asyncio
    async def test_move_mouse(self, server, mock_backend):
        """Test move_mouse tool"""
        mock_backend.move_mouse.return_value = True
        result = await server.move_mouse(300, 400)
        assert result["success"] is True
        mock_backend.move_mouse.assert_called_with(300, 400, relative=False)

    @pytest.mark.asyncio
    async def test_move_mouse_relative(self, server, mock_backend):
        """Test move_mouse with relative movement"""
        mock_backend.move_mouse.return_value = True
        result = await server.move_mouse(50, -50, relative=True)
        assert result["success"] is True
        assert result["relative"] is True
        mock_backend.move_mouse.assert_called_with(50, -50, relative=True)

    @pytest.mark.asyncio
    async def test_click_mouse(self, server, mock_backend):
        """Test click_mouse tool"""
        mock_backend.click_mouse.return_value = True
        result = await server.click_mouse(button="left", x=100, y=200, clicks=1)
        assert result["success"] is True
        assert result["button"] == "left"
        assert result["clicks"] == 1

    @pytest.mark.asyncio
    async def test_click_mouse_double_click(self, server, mock_backend):
        """Test double click"""
        mock_backend.click_mouse.return_value = True
        result = await server.click_mouse(clicks=2)
        assert result["success"] is True
        assert result["clicks"] == 2

    @pytest.mark.asyncio
    async def test_drag_mouse(self, server, mock_backend):
        """Test drag_mouse tool"""
        mock_backend.drag_mouse.return_value = True
        result = await server.drag_mouse(100, 100, 200, 200, duration=0.5)
        assert result["success"] is True
        assert result["start"] == {"x": 100, "y": 100}
        assert result["end"] == {"x": 200, "y": 200}

    @pytest.mark.asyncio
    async def test_scroll_mouse(self, server, mock_backend):
        """Test scroll_mouse tool"""
        mock_backend.scroll_mouse.return_value = True
        result = await server.scroll_mouse(amount=3)
        assert result["success"] is True
        assert result["amount"] == 3
        assert result["direction"] == "vertical"

    @pytest.mark.asyncio
    async def test_type_text(self, server, mock_backend):
        """Test type_text tool"""
        mock_backend.type_text.return_value = True
        result = await server.type_text("Hello World")
        assert result["success"] is True
        assert result["text_length"] == 11
        mock_backend.type_text.assert_called_with("Hello World", interval=0.0)

    @pytest.mark.asyncio
    async def test_send_key(self, server, mock_backend):
        """Test send_key tool"""
        mock_backend.send_key.return_value = True
        result = await server.send_key("enter")
        assert result["success"] is True
        assert result["key"] == "enter"
        mock_backend.send_key.assert_called_with("enter", modifiers=None)

    @pytest.mark.asyncio
    async def test_send_key_with_modifiers(self, server, mock_backend):
        """Test send_key with modifiers"""
        mock_backend.send_key.return_value = True
        result = await server.send_key("c", modifiers=["ctrl"])
        assert result["success"] is True
        assert result["modifiers"] == ["ctrl"]

    @pytest.mark.asyncio
    async def test_send_hotkey(self, server, mock_backend):
        """Test send_hotkey tool"""
        mock_backend.send_hotkey.return_value = True
        result = await server.send_hotkey(keys=["ctrl", "alt", "delete"])
        assert result["success"] is True
        assert result["keys"] == ["ctrl", "alt", "delete"]


class TestBackendFactory:
    """Tests for backend factory"""

    def test_get_backend_linux(self):
        """Test getting Linux backend"""
        with patch("platform.system", return_value="Linux"):
            with patch("mcp_desktop_control.backends.linux.LinuxBackend") as MockBackend:
                mock_instance = Mock()
                mock_instance.is_available.return_value = True
                MockBackend.return_value = mock_instance

                from mcp_desktop_control.backends.factory import get_backend

                backend = get_backend(force_platform="linux")
                assert backend is mock_instance

    def test_get_backend_windows(self):
        """Test getting Windows backend"""
        with patch("mcp_desktop_control.backends.windows.WindowsBackend") as MockBackend:
            mock_instance = Mock()
            mock_instance.is_available.return_value = True
            MockBackend.return_value = mock_instance

            from mcp_desktop_control.backends.factory import get_backend

            backend = get_backend(force_platform="windows")
            assert backend is mock_instance

    def test_get_backend_unavailable(self):
        """Test error when backend is unavailable"""
        with patch("mcp_desktop_control.backends.linux.LinuxBackend") as MockBackend:
            mock_instance = Mock()
            mock_instance.is_available.return_value = False
            MockBackend.return_value = mock_instance

            from mcp_desktop_control.backends.factory import get_backend

            with pytest.raises(RuntimeError, match="not available"):
                get_backend(force_platform="linux")

    def test_get_backend_unsupported_platform(self):
        """Test error for unsupported platform"""
        from mcp_desktop_control.backends.factory import get_backend

        with pytest.raises(RuntimeError, match="not yet supported"):
            get_backend(force_platform="darwin")


class TestLinuxBackend:
    """Tests for Linux backend"""

    @pytest.fixture
    def backend(self):
        """Create Linux backend with mocked tools"""
        with patch("shutil.which") as mock_which:
            # Mock all tools as available
            mock_which.return_value = "/usr/bin/xdotool"

            from mcp_desktop_control.backends.linux import LinuxBackend

            backend = LinuxBackend()
            return backend

    def test_platform_name(self, backend):
        """Test platform name"""
        assert backend.platform_name == "linux"

    def test_is_available_with_xdotool(self, backend):
        """Test availability check"""
        assert backend.is_available() is True

    def test_list_windows(self, backend):
        """Test list_windows command"""
        mock_output = "0x12345 0 1234 100 200 800 600 hostname Test Window\n"
        with patch.object(backend, "_run_command") as mock_cmd:
            mock_cmd.return_value = Mock(returncode=0, stdout=mock_output)
            with patch.object(backend, "_get_window_class", return_value="testclass"):
                with patch.object(backend, "_get_process_name", return_value="test"):
                    windows = backend.list_windows()
                    assert len(windows) == 1
                    assert windows[0].title == "Test Window"

    def test_get_mouse_position(self, backend):
        """Test get_mouse_position"""
        mock_output = "x:500 y:300 screen:0 window:12345\n"
        with patch.object(backend, "_run_command") as mock_cmd:
            mock_cmd.return_value = Mock(returncode=0, stdout=mock_output)
            x, y = backend.get_mouse_position()
            assert x == 500
            assert y == 300
