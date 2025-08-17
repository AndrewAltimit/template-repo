"""Asset management for Blender projects."""

import logging
import mimetypes
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

logger = logging.getLogger(__name__)


class ProjectInfo(TypedDict):
    """Type definition for project information."""

    name: str
    path: str
    size: int
    modified: float
    created: float


class DetailedProjectInfo(TypedDict, total=False):
    """Type definition for detailed project information."""

    name: str
    path: str
    size: int
    size_mb: float
    modified: float
    created: float
    extension: str
    has_assets: bool
    asset_count: int


class AssetInfo(TypedDict):
    """Type definition for asset information."""

    name: str
    path: str
    type: str
    size: int
    extension: str
    format: Optional[str]
    category: Optional[str]


class AssetManager:
    """Manages Blender projects and assets."""

    def __init__(self, projects_dir: str = "/app/projects", assets_dir: str = "/app/assets"):
        """Initialize asset manager.

        Args:
            projects_dir: Directory for Blender projects
            assets_dir: Directory for assets (textures, models, etc.)
        """
        self.projects_dir = Path(projects_dir)
        self.assets_dir = Path(assets_dir)

        # Create directories
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

        # Create asset subdirectories
        self._create_asset_structure()

        # File format mappings
        self.model_formats = {
            ".fbx": "FBX",
            ".obj": "OBJ",
            ".gltf": "GLTF",
            ".glb": "GLTF",
            ".stl": "STL",
            ".ply": "PLY",
            ".dae": "COLLADA",
            ".3ds": "3DS",
            ".usd": "USD",
            ".usdc": "USD",
            ".usda": "USD",
        }

        self.texture_formats = {
            ".png": "PNG",
            ".jpg": "JPEG",
            ".jpeg": "JPEG",
            ".exr": "OPEN_EXR",
            ".hdr": "HDR",
            ".tiff": "TIFF",
            ".tif": "TIFF",
            ".bmp": "BMP",
            ".tga": "TARGA",
        }

    def _create_asset_structure(self):
        """Create organized asset directory structure."""
        subdirs = ["textures", "models", "hdri", "materials", "references", "scripts"]

        for subdir in subdirs:
            try:
                (self.assets_dir / subdir).mkdir(exist_ok=True)
            except PermissionError:
                logger.warning(f"Could not create {subdir} directory - permission denied. Continuing without it.")

    def list_projects(self) -> List[ProjectInfo]:
        """List all Blender projects.

        Returns:
            List of project information
        """
        projects: List[ProjectInfo] = []

        for project_file in self.projects_dir.glob("*.blend"):
            try:
                stat = project_file.stat()
                project_info: ProjectInfo = {
                    "name": project_file.stem,
                    "path": str(project_file),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "created": stat.st_ctime,
                }
                projects.append(project_info)
            except Exception as e:
                logger.error(f"Failed to stat project {project_file}: {e}")

        # Sort by modification time (newest first)
        projects.sort(key=lambda p: p["modified"], reverse=True)

        return projects

    def get_project_info(self, project_path: str) -> Optional[DetailedProjectInfo]:
        """Get detailed information about a project.

        Args:
            project_path: Path to .blend file

        Returns:
            Project information or None
        """
        path = Path(project_path)

        if not path.exists():
            return None

        try:
            stat = path.stat()

            # Try to read blend file metadata (if possible)
            info: DetailedProjectInfo = {
                "name": path.stem,
                "path": str(path),
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "modified": stat.st_mtime,
                "created": stat.st_ctime,
                "extension": path.suffix,
            }

            # Check for associated files
            project_dir = path.parent / path.stem
            if project_dir.exists() and project_dir.is_dir():
                info["has_assets"] = True
                info["asset_count"] = len(list(project_dir.iterdir()))

            return info

        except Exception as e:
            logger.error(f"Failed to get project info: {e}")
            return None

    def list_assets(self, asset_type: Optional[str] = None) -> List[AssetInfo]:
        """List available assets.

        Args:
            asset_type: Filter by type (textures, models, hdri, etc.)

        Returns:
            List of assets
        """
        assets: List[AssetInfo] = []

        if asset_type:
            search_dirs = [self.assets_dir / asset_type]
        else:
            search_dirs = [
                self.assets_dir / "textures",
                self.assets_dir / "models",
                self.assets_dir / "hdri",
                self.assets_dir / "materials",
            ]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            for asset_file in search_dir.rglob("*"):
                if asset_file.is_file():
                    try:
                        stat = asset_file.stat()
                        asset_info: AssetInfo = {
                            "name": asset_file.name,
                            "path": str(asset_file),
                            "type": search_dir.name,
                            "size": stat.st_size,
                            "extension": asset_file.suffix.lower(),
                            "format": None,
                            "category": None,
                        }

                        # Detect format
                        if asset_file.suffix.lower() in self.model_formats:
                            asset_info["format"] = self.model_formats[asset_file.suffix.lower()]
                            asset_info["category"] = "model"
                        elif asset_file.suffix.lower() in self.texture_formats:
                            asset_info["format"] = self.texture_formats[asset_file.suffix.lower()]
                            asset_info["category"] = "texture"

                        assets.append(asset_info)

                    except Exception as e:
                        logger.error(f"Failed to process asset {asset_file}: {e}")

        return assets

    def import_asset(self, source_path: str, asset_type: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Import an asset into the library.

        Args:
            source_path: Path to source file
            asset_type: Type of asset (textures, models, etc.)
            name: Optional custom name

        Returns:
            Import result
        """
        source = Path(source_path)

        if not source.exists():
            return {"error": f"Source file not found: {source_path}"}

        # Determine destination
        dest_dir = self.assets_dir / asset_type
        dest_dir.mkdir(exist_ok=True)

        if name:
            dest_name = name + source.suffix
        else:
            dest_name = source.name

        dest_path = dest_dir / dest_name

        # Check for conflicts
        if dest_path.exists():
            # Add number suffix
            i = 1
            while dest_path.exists():
                stem = dest_path.stem.rstrip("0123456789_")
                dest_path = dest_dir / f"{stem}_{i}{dest_path.suffix}"
                i += 1

        try:
            # Copy file
            shutil.copy2(source, dest_path)

            return {
                "success": True,
                "asset_path": str(dest_path),
                "asset_type": asset_type,
                "message": f"Asset imported to {dest_path}",
            }

        except Exception as e:
            logger.error(f"Failed to import asset: {e}")
            return {"error": str(e)}

    def detect_format(self, file_path: str) -> Optional[str]:
        """Detect file format from extension.

        Args:
            file_path: Path to file

        Returns:
            Format string or None
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext in self.model_formats:
            return self.model_formats[ext]
        elif ext in self.texture_formats:
            return self.texture_formats[ext]
        else:
            # Try to detect from mimetype
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type:
                if mime_type.startswith("image/"):
                    return "IMAGE"
                elif mime_type.startswith("video/"):
                    return "VIDEO"

            return None

    def create_project_backup(self, project_path: str) -> Optional[str]:
        """Create a backup of a project.

        Args:
            project_path: Path to project file

        Returns:
            Path to backup or None
        """
        source = Path(project_path)

        if not source.exists():
            return None

        # Create backups directory
        backup_dir = self.projects_dir / "backups"
        backup_dir.mkdir(exist_ok=True)

        # Generate backup name with timestamp
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{source.stem}_backup_{timestamp}{source.suffix}"
        backup_path = backup_dir / backup_name

        try:
            shutil.copy2(source, backup_path)
            logger.info(f"Created backup: {backup_path}")
            return str(backup_path)
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            return None

    def clean_temp_files(self):
        """Clean temporary files and caches."""
        temp_patterns = [
            "*.blend1",  # Blender backup files
            "*.blend2",
            "*.blend@",  # Blender temp files
            "*.tmp",
            "*~",  # Editor backup files
        ]

        cleaned = 0

        for pattern in temp_patterns:
            for temp_file in self.projects_dir.rglob(pattern):
                try:
                    temp_file.unlink()
                    cleaned += 1
                except Exception as e:
                    logger.error(f"Failed to remove {temp_file}: {e}")

        logger.info(f"Cleaned {cleaned} temporary files")
        return cleaned

    def get_asset_metadata(self, asset_path: str) -> Dict[str, Any]:
        """Get metadata for an asset.

        Args:
            asset_path: Path to asset file

        Returns:
            Asset metadata
        """
        path = Path(asset_path)

        if not path.exists():
            return {"error": "Asset not found"}

        try:
            stat = path.stat()
            metadata = {
                "name": path.name,
                "path": str(path),
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "modified": stat.st_mtime,
                "created": stat.st_ctime,
                "extension": path.suffix.lower(),
                "format": self.detect_format(str(path)),
            }

            # Add type-specific metadata
            if path.suffix.lower() in self.texture_formats:
                # Could add image dimensions if we have PIL
                metadata["type"] = "texture"
            elif path.suffix.lower() in self.model_formats:
                metadata["type"] = "model"

            return metadata

        except Exception as e:
            logger.error(f"Failed to get asset metadata: {e}")
            return {"error": str(e)}
