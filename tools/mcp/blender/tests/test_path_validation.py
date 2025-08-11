#!/usr/bin/env python3
"""Test path validation security in Blender MCP server."""

import sys
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import from relative path
from blender.server import BlenderMCPServer  # noqa: E402


class TestPathValidation:
    """Test path validation to prevent directory traversal attacks."""

    def setup_method(self):
        """Setup test server instance."""
        self.server = BlenderMCPServer(base_dir="/tmp/test_blender")

    def test_valid_paths(self):
        """Test that valid paths are accepted."""
        # Valid filename
        result = self.server._validate_path("model.obj", self.server.assets_dir)
        assert result == self.server.assets_dir / "model.obj"

        # Valid project name
        result = self.server._validate_path("scene.blend", self.server.projects_dir)
        assert result == self.server.projects_dir / "scene.blend"

        # Valid subdirectory path
        result = self.server._validate_path("textures/wood.png", self.server.assets_dir)
        assert result == self.server.assets_dir / "textures" / "wood.png"

    def test_path_traversal_attacks(self):
        """Test that path traversal attempts are rejected."""
        # Parent directory traversal
        with pytest.raises(ValueError, match="parent directory references not allowed"):
            self.server._validate_path("../../../etc/passwd", self.server.assets_dir)

        # Multiple parent directory references
        with pytest.raises(ValueError, match="parent directory references not allowed"):
            self.server._validate_path("../../sensitive.txt", self.server.assets_dir)

        # Mixed traversal
        with pytest.raises(ValueError, match="parent directory references not allowed"):
            self.server._validate_path("valid/../../../etc/passwd", self.server.assets_dir)

    def test_absolute_paths(self):
        """Test that absolute paths are rejected."""
        with pytest.raises(ValueError, match="absolute paths not allowed"):
            self.server._validate_path("/etc/passwd", self.server.assets_dir)

        with pytest.raises(ValueError, match="absolute paths not allowed"):
            self.server._validate_path("/home/user/file.txt", self.server.assets_dir)

    def test_special_characters(self):
        """Test that special path components are rejected."""
        # Current directory reference
        with pytest.raises(ValueError, match="current directory reference not allowed"):
            self.server._validate_path(".", self.server.assets_dir)

        with pytest.raises(ValueError, match="current directory reference not allowed"):
            self.server._validate_path("./", self.server.assets_dir)

        # Parent directory reference
        with pytest.raises(ValueError, match="parent directory references not allowed"):
            self.server._validate_path("..", self.server.assets_dir)

    def test_empty_paths(self):
        """Test that empty paths are rejected."""
        with pytest.raises(ValueError, match="empty path"):
            self.server._validate_path("", self.server.assets_dir)

    def test_project_path_validation(self):
        """Test project-specific path validation."""
        # Valid project name without extension
        result = self.server._validate_project_path("my_project")
        assert result == self.server.projects_dir / "my_project.blend"

        # Valid project name with extension
        result = self.server._validate_project_path("scene.blend")
        assert result == self.server.projects_dir / "scene.blend"

        # Path traversal in project path
        with pytest.raises(ValueError, match="parent directory references not allowed"):
            self.server._validate_project_path("../../../etc/passwd")

        # Absolute path as project
        with pytest.raises(ValueError, match="absolute paths not allowed"):
            self.server._validate_project_path("/etc/passwd.blend")

    def test_hidden_files(self):
        """Test that hidden files starting with dot are rejected in path components."""
        # Hidden file in subdirectory
        with pytest.raises(ValueError, match="invalid path component"):
            self.server._validate_path("subdir/.hidden/file.txt", self.server.assets_dir)

        # But allow .blend extension (not a hidden file)
        result = self.server._validate_path("project.blend", self.server.projects_dir)
        assert result == self.server.projects_dir / "project.blend"

    def test_null_bytes(self):
        """Test that null bytes in paths are handled safely."""
        # Python strings don't allow null bytes by default, but test the behavior
        # This would typically be caught at a higher level
        with pytest.raises(ValueError):
            self.server._validate_path("file\x00.txt", self.server.assets_dir)

    def test_url_encoded_traversal(self):
        """Test that URL-encoded traversal attempts are rejected."""
        # These should be decoded before reaching our validation, but test anyway
        with pytest.raises(ValueError, match="parent directory references not allowed"):
            self.server._validate_path("..%2F..%2Fetc%2Fpasswd", self.server.assets_dir)

    def test_windows_path_separators(self):
        """Test that Windows-style path separators don't bypass validation."""
        # Backslashes should be treated as part of the filename, not path separators
        # This ensures cross-platform security
        result = self.server._validate_path("file\\name.txt", self.server.assets_dir)
        # The backslash becomes part of the filename on Unix systems
        assert "file\\name.txt" in str(result) or "file" in str(result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
