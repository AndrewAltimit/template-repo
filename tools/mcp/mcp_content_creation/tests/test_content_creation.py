#!/usr/bin/env python3
"""
Unit tests for Content Creation MCP Server
"""

from unittest.mock import Mock, mock_open, patch

import pytest

from mcp_content_creation.server import ContentCreationMCPServer
from mcp_content_creation.tools import compile_latex, create_manim_animation


class TestContentCreationTools:
    """Test suite for Content Creation MCP tools"""

    @pytest.mark.asyncio
    async def test_compile_latex_pdf(self):
        """Test LaTeX compilation to PDF"""
        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            with patch("subprocess.run") as mock_run:
                with patch("os.path.exists") as mock_exists:
                    with patch("shutil.copy") as _mock_copy:
                        with patch("os.makedirs") as mock_makedirs:
                            with patch("builtins.open", mock_open()):
                                # Setup mocks
                                mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"
                                mock_run.return_value = Mock(returncode=0)
                                mock_exists.return_value = True
                                mock_makedirs.return_value = None

                                # Test compilation
                                latex_content = r"\documentclass{article}" + r"\begin{document}Test\end{document}"
                                result = await compile_latex(content=latex_content, output_format="pdf")

                                assert result["success"] is True
                                assert "output_path" in result
                                _mock_copy.assert_called_once()

    @pytest.mark.asyncio
    async def test_compile_latex_dvi(self):
        """Test LaTeX compilation to DVI"""
        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            with patch("subprocess.run") as mock_run:
                with patch("os.path.exists") as mock_exists:
                    with patch("shutil.copy"):
                        with patch("os.makedirs") as mock_makedirs:
                            with patch("builtins.open", mock_open()):
                                # Setup mocks
                                mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"
                                mock_run.return_value = Mock(returncode=0)
                                mock_exists.return_value = True
                                mock_makedirs.return_value = None

                                # Test compilation
                                latex_content = r"\documentclass{article}" + r"\begin{document}Test\end{document}"
                                result = await compile_latex(content=latex_content, output_format="dvi")

                                assert result["success"] is True
                                assert "output_path" in result

    @pytest.mark.asyncio
    async def test_compile_latex_error(self):
        """Test LaTeX compilation with error"""
        with patch("tempfile.TemporaryDirectory") as mock_tmpdir:
            with patch("subprocess.run") as mock_run:
                with patch("os.makedirs") as mock_makedirs:
                    with patch("builtins.open", mock_open()):
                        # Setup mocks
                        mock_tmpdir.return_value.__enter__.return_value = "/tmp/test"
                        mock_run.return_value = Mock(
                            returncode=1,
                            stderr="LaTeX Error: Missing \\begin{document}",
                        )
                        mock_makedirs.return_value = None

                        # Test compilation
                        latex_content = r"\documentclass{article}Invalid"
                        result = await compile_latex(content=latex_content)

                        assert result["success"] is False
                        assert "error" in result

    @pytest.mark.asyncio
    async def test_create_manim_animation(self):
        """Test Manim animation creation"""
        with patch("tempfile.NamedTemporaryFile") as mock_tmp:
            with patch("subprocess.run") as mock_run:
                with patch("os.listdir") as mock_listdir:
                    with patch("os.unlink") as mock_unlink:
                        with patch("os.makedirs") as mock_makedirs:
                            # Setup mocks
                            mock_file = Mock()
                            mock_file.name = "/tmp/test.py"
                            mock_tmp.return_value.__enter__.return_value = mock_file
                            mock_run.return_value = Mock(returncode=0)
                            mock_listdir.return_value = ["TestScene.mp4"]
                            mock_makedirs.return_value = None

                            # Test animation
                            script = "from manim import *\n" + "class TestScene(Scene): pass"
                            result = await create_manim_animation(script=script, output_format="mp4")

                            assert result["success"] is True
                            assert "output_path" in result
                            mock_unlink.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_manim_animation_with_options(self):
        """Test Manim animation with custom options"""
        with patch("tempfile.NamedTemporaryFile") as mock_tmp:
            with patch("subprocess.run") as mock_run:
                with patch("os.listdir") as mock_listdir:
                    with patch("os.unlink"):
                        with patch("os.makedirs") as mock_makedirs:
                            # Setup mocks
                            mock_file = Mock()
                            mock_file.name = "/tmp/test.py"
                            mock_tmp.return_value.__enter__.return_value = mock_file
                            mock_run.return_value = Mock(returncode=0)
                            mock_listdir.return_value = ["TestScene.gif"]
                            mock_makedirs.return_value = None

                            # Test animation
                            script = "from manim import *\n" + "class TestScene(Scene): pass"
                            result = await create_manim_animation(
                                script=script,
                                output_format="gif",
                            )

                            assert result["success"] is True
                            assert "output_path" in result

    @pytest.mark.asyncio
    async def test_create_manim_animation_error(self):
        """Test Manim animation with error"""
        with patch("tempfile.NamedTemporaryFile") as mock_tmp:
            with patch("subprocess.run") as mock_run:
                with patch("os.unlink") as mock_unlink:
                    with patch("os.makedirs") as mock_makedirs:
                        # Setup mocks
                        mock_file = Mock()
                        mock_file.name = "/tmp/test.py"
                        mock_tmp.return_value.__enter__.return_value = mock_file
                        mock_run.return_value = Mock(returncode=1, stderr="Manim Error: Invalid scene")
                        mock_makedirs.return_value = None

                        # Test animation
                        script = "invalid python code"
                        result = await create_manim_animation(script=script)

                        assert result["success"] is False
                        assert "error" in result
                        mock_unlink.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_manim_animation_no_output_files(self):
        """Test Manim animation when no output files are found"""
        with patch("tempfile.NamedTemporaryFile") as mock_tmp:
            with patch("subprocess.run") as mock_run:
                with patch("os.listdir") as mock_listdir:
                    with patch("os.unlink") as mock_unlink:
                        with patch("os.path.exists") as mock_exists:
                            # Setup mocks
                            mock_file = Mock()
                            mock_file.name = "/tmp/test.py"
                            mock_tmp.return_value.__enter__.return_value = mock_file
                            mock_run.return_value = Mock(returncode=0)
                            mock_listdir.return_value = []  # No output files
                            mock_exists.return_value = False

                            # Test animation
                            script = "from manim import *\n" + "class TestScene(Scene): pass"
                            result = await create_manim_animation(script=script)

                            assert result["success"] is True
                            assert result["output_path"] is None
                            mock_unlink.assert_called_once()


class TestPathResolution:
    """Test suite for path resolution and conversion functionality"""

    def test_container_path_to_host_path_output_directory(self):
        """Test conversion of /output paths to host-relative paths"""
        server = ContentCreationMCPServer()

        # Test /output mapping
        result = server._container_path_to_host_path("/output/latex/document.pdf")
        assert result == "outputs/mcp-content/latex/document.pdf"

        # Test nested paths
        result = server._container_path_to_host_path("/output/previews/doc_page1.png")
        assert result == "outputs/mcp-content/previews/doc_page1.png"

    def test_container_path_to_host_path_app_directory(self):
        """Test conversion of /app paths to host-relative paths"""
        server = ContentCreationMCPServer()

        # Test /app mapping (maps to ".")
        result = server._container_path_to_host_path("/app/documents/thesis.tex")
        assert result == "documents/thesis.tex"

    def test_container_path_to_host_path_unmapped(self):
        """Test that unmapped paths are returned as-is"""
        server = ContentCreationMCPServer()

        # Test unmapped path
        result = server._container_path_to_host_path("/tmp/something.pdf")
        assert result == "/tmp/something.pdf"

    def test_resolve_input_path_absolute(self):
        """Test that absolute paths are returned as-is"""
        server = ContentCreationMCPServer()

        result = server._resolve_input_path("/absolute/path/to/file.tex")
        assert result == "/absolute/path/to/file.tex"

    def test_resolve_input_path_relative(self):
        """Test that relative paths are resolved relative to project root"""
        server = ContentCreationMCPServer()

        result = server._resolve_input_path("documents/thesis.tex")
        assert result == "/app/documents/thesis.tex"

    def test_resolve_input_path_with_custom_project_root(self):
        """Test path resolution with custom project root"""
        with patch.dict("os.environ", {"MCP_PROJECT_ROOT": "/custom/root"}):
            server = ContentCreationMCPServer()
            result = server._resolve_input_path("docs/file.tex")
            assert result == "/custom/root/docs/file.tex"

    def test_resolve_input_path_blocks_traversal_relative(self):
        """Test that relative paths with traversal are blocked"""
        server = ContentCreationMCPServer()
        # Attempting to traverse outside project root should raise ValueError
        with pytest.raises(ValueError, match="Path traversal detected"):
            server._resolve_input_path("../../../etc/passwd")

    def test_resolve_input_path_allows_absolute_outside_project(self):
        """Test that absolute paths outside project root are allowed (explicit user intent)"""
        server = ContentCreationMCPServer()
        # Absolute paths are allowed even outside project root - user explicitly requested
        result = server._resolve_input_path("/etc/passwd")
        assert result == "/etc/passwd"

    def test_resolve_input_path_normalizes_absolute_with_traversal(self):
        """Test that absolute paths with '..' are normalized"""
        server = ContentCreationMCPServer()
        # Absolute path with ".." should be normalized
        result = server._resolve_input_path("/app/../etc/passwd")
        assert result == "/etc/passwd"

    def test_resolve_input_path_allows_valid_nested_paths(self):
        """Test that valid nested paths within project root are allowed"""
        server = ContentCreationMCPServer()
        # Valid nested path with ".." that stays within project root
        result = server._resolve_input_path("docs/../documents/thesis.tex")
        assert result == "/app/documents/thesis.tex"

    def test_resolve_input_path_allows_absolute_within_project(self):
        """Test that absolute paths within project root are allowed"""
        server = ContentCreationMCPServer()
        result = server._resolve_input_path("/app/documents/thesis.tex")
        assert result == "/app/documents/thesis.tex"


class TestSymlinkWarnings:
    """Test suite for symlink warning functionality"""

    def test_symlink_warnings_included_in_response(self):
        """Test that symlink_warnings parameter is included in response"""
        server = ContentCreationMCPServer()

        # Test that _build_compile_success_response includes warnings when symlink_warnings provided
        with patch("mcp_content_creation.server.shutil.copy"):
            with patch("mcp_content_creation.server.os.path.exists", return_value=True):
                with patch.object(server, "_get_pdf_page_count", return_value=1):
                    with patch.object(server, "_get_file_size_kb", return_value=10.0):
                        result = server._build_compile_success_response(
                            output_file="/tmp/test/document.pdf",
                            output_format="pdf",
                            start_time=0.0,
                            preview_pages="none",
                            preview_dpi=150,
                            response_mode="standard",
                            symlink_warnings=["chapter1.tex", "image.png"],
                        )

                        assert result["success"] is True
                        assert "warnings" in result
                        assert any("symlink" in w.lower() for w in result["warnings"])
                        assert "chapter1.tex" in result["warnings"][0]
                        assert "image.png" in result["warnings"][0]

    def test_no_warnings_when_no_symlink_failures(self):
        """Test that no warnings are included when symlinks succeed"""
        server = ContentCreationMCPServer()

        with patch("mcp_content_creation.server.shutil.copy"):
            with patch("mcp_content_creation.server.os.path.exists", return_value=True):
                with patch.object(server, "_get_pdf_page_count", return_value=1):
                    with patch.object(server, "_get_file_size_kb", return_value=10.0):
                        result = server._build_compile_success_response(
                            output_file="/tmp/test/document.pdf",
                            output_format="pdf",
                            start_time=0.0,
                            preview_pages="none",
                            preview_dpi=150,
                            response_mode="standard",
                            symlink_warnings=None,
                        )

                        assert result["success"] is True
                        assert "warnings" not in result


class TestResponseFormat:
    """Test suite for response format with host paths"""

    @pytest.mark.asyncio
    async def test_compile_latex_returns_host_path(self):
        """Test that compile_latex returns host-relative output_path"""
        # Patch at the module level where the functions are used
        with patch("mcp_content_creation.server.tempfile.mkdtemp") as mock_mkdtemp:
            with patch("mcp_content_creation.server.subprocess.run") as mock_run:
                with patch("mcp_content_creation.server.os.path.exists") as mock_exists:
                    with patch("mcp_content_creation.server.shutil.copy"):
                        with patch("builtins.open", mock_open()):
                            with patch("mcp_content_creation.server.shutil.rmtree"):
                                # Setup mocks
                                mock_mkdtemp.return_value = "/tmp/test"
                                mock_run.return_value = Mock(returncode=0)
                                mock_exists.return_value = True

                                server = ContentCreationMCPServer()
                                result = await server.compile_latex(
                                    content=r"\documentclass{article}\begin{document}Test\end{document}",
                                    output_format="pdf",
                                )

                                assert result["success"] is True
                                # output_path should be host-relative
                                assert result["output_path"].startswith("outputs/mcp-content/")
                                # container_path should be the original container path
                                assert "/output/" in result["container_path"] or "/app/output/" in result["container_path"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
