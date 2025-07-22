#!/usr/bin/env python3
"""
Unit tests for Content Creation MCP Server
"""

import os
import sys
from unittest.mock import Mock, mock_open, patch

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.mcp.content_creation.tools import compile_latex, create_manim_animation  # noqa: E402


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
                                latex_content = r"\documentclass{article}" r"\begin{document}Test\end{document}"
                                result = await compile_latex(content=latex_content, format="pdf")

                                assert result["success"] is True
                                assert result["format"] == "pdf"
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
                                latex_content = r"\documentclass{article}" r"\begin{document}Test\end{document}"
                                result = await compile_latex(content=latex_content, format="dvi")

                                assert result["success"] is True
                                assert result["format"] == "dvi"
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
                        assert "LaTeX Error" in result["error"]

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
                            script = "from manim import *\n" "class TestScene(Scene): pass"
                            result = await create_manim_animation(script=script, output_format="mp4")

                            assert result["success"] is True
                            assert result["format"] == "mp4"
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
                            script = "from manim import *\n" "class TestScene(Scene): pass"
                            result = await create_manim_animation(
                                script=script,
                                output_format="gif",
                                quality="low",
                            )

                            assert result["success"] is True
                            assert result["format"] == "gif"
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
                            script = "from manim import *\n" "class TestScene(Scene): pass"
                            result = await create_manim_animation(script=script)

                            assert result["success"] is True
                            assert result["output_path"] is None
                            mock_unlink.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
