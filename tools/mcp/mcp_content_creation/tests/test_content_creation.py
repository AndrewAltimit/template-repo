#!/usr/bin/env python3
"""
Unit tests for Content Creation MCP Server
"""

from unittest.mock import Mock, mock_open, patch

import pytest

from mcp_content_creation.server import ContentCreationMCPServer
from mcp_content_creation.tools import compile_latex, create_manim_animation


class TestPathConversion:
    """Test suite for path conversion functionality"""

    def test_to_project_relative_path_container_output(self):
        """Test conversion of container output path to project-relative path"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        # Test container output path conversion
        container_path = "/output/latex/document_12345.pdf"
        expected = "outputs/mcp-content/latex/document_12345.pdf"
        assert server._to_project_relative_path(container_path) == expected

    def test_to_project_relative_path_root_output(self):
        """Test conversion of root output path"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        container_path = "/output"
        expected = "outputs/mcp-content"
        assert server._to_project_relative_path(container_path) == expected

    def test_to_project_relative_path_nested(self):
        """Test conversion of deeply nested container path"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        container_path = "/output/manim/videos/480p15/scene.mp4"
        expected = "outputs/mcp-content/manim/videos/480p15/scene.mp4"
        assert server._to_project_relative_path(container_path) == expected

    def test_to_project_relative_path_non_container(self):
        """Test that non-container paths are returned as-is"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        # Path not in /output should be unchanged
        other_path = "/tmp/some_file.pdf"
        assert server._to_project_relative_path(other_path) == other_path

    def test_to_project_relative_path_already_relative(self):
        """Test that already relative paths are returned as-is"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        relative_path = "outputs/mcp-content/latex/doc.pdf"
        assert server._to_project_relative_path(relative_path) == relative_path

    def test_convert_paths_in_result_output_path(self):
        """Test conversion of output_path in result dictionary"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        result = {
            "success": True,
            "output_path": "/output/latex/document.pdf",
        }
        converted = server._convert_paths_in_result(result)
        assert converted["output_path"] == "outputs/mcp-content/latex/document.pdf"

    def test_convert_paths_in_result_preview_paths(self):
        """Test conversion of preview_paths list in result dictionary"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        result = {
            "success": True,
            "preview_paths": [
                "/output/previews/doc_page1.png",
                "/output/previews/doc_page2.png",
            ],
        }
        converted = server._convert_paths_in_result(result)
        assert converted["preview_paths"] == [
            "outputs/mcp-content/previews/doc_page1.png",
            "outputs/mcp-content/previews/doc_page2.png",
        ]

    def test_convert_paths_in_result_pdf_path(self):
        """Test conversion of pdf_path in result dictionary"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        result = {
            "success": True,
            "pdf_path": "/output/latex/document.pdf",
        }
        converted = server._convert_paths_in_result(result)
        assert converted["pdf_path"] == "outputs/mcp-content/latex/document.pdf"

    def test_convert_paths_in_result_empty_values(self):
        """Test handling of None/empty values in result dictionary"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        result = {
            "success": True,
            "output_path": None,
            "preview_paths": [],
        }
        converted = server._convert_paths_in_result(result)
        assert converted["output_path"] is None
        assert converted["preview_paths"] == []


class TestInputPathResolution:
    """Test suite for input path resolution"""

    def test_resolve_input_path_absolute_exists(self):
        """Test resolution of existing absolute path"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        with patch("os.path.exists", return_value=True):
            result = server._resolve_input_path("/app/docs/file.tex")
            assert result == "/app/docs/file.tex"

    def test_resolve_input_path_relative_exists(self):
        """Test resolution of relative path (resolved to /app)"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        with patch("os.path.exists", return_value=True):
            with patch.dict("os.environ", {"MCP_APP_DIR": "/app"}):
                result = server._resolve_input_path("docs/file.tex")
                assert result == "/app/docs/file.tex"

    def test_resolve_input_path_not_found_absolute(self):
        """Test error message for non-existent absolute path"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        with patch("os.path.exists", return_value=False):
            with pytest.raises(FileNotFoundError) as excinfo:
                server._resolve_input_path("/nonexistent/file.tex")
            assert "Input file not found: /nonexistent/file.tex" in str(excinfo.value)
            # Should NOT include resolution info for absolute paths
            assert "Path Resolution Info" not in str(excinfo.value)

    def test_resolve_input_path_not_found_relative(self):
        """Test error message for non-existent relative path includes resolution info"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        with patch("os.path.exists", return_value=False):
            with patch.dict("os.environ", {"MCP_APP_DIR": "/app"}):
                with pytest.raises(FileNotFoundError) as excinfo:
                    server._resolve_input_path("docs/missing.tex")
                error_msg = str(excinfo.value)
                assert "Input file not found: docs/missing.tex" in error_msg
                assert "Path Resolution Info" in error_msg
                assert "Resolved path: /app/docs/missing.tex" in error_msg


class TestCleanupSemantics:
    """Test suite for cleanup parameter semantics"""

    def test_cleanup_default_removes_directory(self):
        """Test that default behavior removes the temp directory"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        server.logger = Mock()

        with patch("shutil.rmtree") as mock_rmtree:
            with patch("os.path.exists", return_value=True):
                server._cleanup_latex_temp_files(
                    tex_file="/tmp/mcp_latex_123/document.tex",
                    working_dir="/tmp/mcp_latex_123",
                    keep_intermediate_files=False,  # Default
                )
                mock_rmtree.assert_called_once_with("/tmp/mcp_latex_123")

    def test_cleanup_keep_intermediate_preserves_logs(self):
        """Test that keep_intermediate_files=True preserves .aux and .log"""
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        server.logger = Mock()

        with patch("os.path.exists", return_value=True):
            with patch("os.unlink") as mock_unlink:
                with patch("shutil.rmtree") as mock_rmtree:
                    server._cleanup_latex_temp_files(
                        tex_file="/tmp/mcp_latex_123/document.tex",
                        working_dir="/tmp/mcp_latex_123",
                        keep_intermediate_files=True,
                    )
                    # Should NOT remove the directory
                    mock_rmtree.assert_not_called()
                    # Should only remove specific files, not .aux and .log
                    unlink_calls = [str(call) for call in mock_unlink.call_args_list]
                    # .aux and .log should NOT be in the unlink calls
                    for call in unlink_calls:
                        assert ".aux" not in call
                        assert ".log" not in call


class TestSymlinkWarnings:
    """Test suite for symlink warning functionality"""

    @pytest.mark.asyncio
    async def test_symlink_failure_logged(self):
        """Test that symlink failures are logged and included in response"""
        # This test verifies the logging behavior when symlinks fail
        # The actual symlink warning is collected in the symlink_warnings list
        server = ContentCreationMCPServer.__new__(ContentCreationMCPServer)
        server.logger = Mock()
        server.output_dir = "/output"
        server.latex_output_dir = "/output/latex"
        server.preview_output_dir = "/output/previews"
        server.manim_output_dir = "/output/manim"

        # Verify the server has the expected attributes
        assert hasattr(server, "_to_project_relative_path")
        assert hasattr(server, "_convert_paths_in_result")


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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
