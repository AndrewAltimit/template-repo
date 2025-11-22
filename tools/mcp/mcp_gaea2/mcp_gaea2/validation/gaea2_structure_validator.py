#!/usr/bin/env python3
"""
Structure validation for Gaea2 project files
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class Gaea2StructureValidator:
    """Validates and fixes Gaea2 project structure"""

    # Required top-level keys
    REQUIRED_KEYS = ["$id", "Assets", "Id", "Metadata"]

    # Required asset structure
    REQUIRED_ASSET_KEYS = ["Terrain", "Automation", "BuildDefinition", "State"]

    # Required terrain keys
    REQUIRED_TERRAIN_KEYS = ["Id", "Metadata", "Nodes", "Groups", "Notes", "GraphTabs"]

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.fixes_applied = []

    def validate_structure(self, project_data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """
        Validate project structure

        Returns:
            - is_valid: Whether structure is valid
            - errors: List of critical errors
            - warnings: List of warnings
        """
        self.errors = []
        self.warnings = []

        # Check top-level structure
        self._validate_top_level(project_data)

        # Check assets structure
        if "Assets" in project_data:
            self._validate_assets(project_data["Assets"])

        # Check metadata
        if "Metadata" in project_data:
            self._validate_metadata(project_data["Metadata"])

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

    def fix_structure(self, project_data: Dict[str, Any], project_name: Optional[str] = None) -> Dict[str, Any]:
        """Fix common structure issues"""
        self.fixes_applied = []
        fixed = project_data.copy()

        # Fix top-level structure
        if "$id" not in fixed:
            fixed["$id"] = "1"
            self.fixes_applied.append("Added missing $id")

        if "Id" not in fixed:
            fixed["Id"] = str(uuid.uuid4())[:8]
            self.fixes_applied.append("Generated missing project Id")

        if "Branch" not in fixed:
            fixed["Branch"] = 1
            self.fixes_applied.append("Added default Branch=1")

        # Fix metadata
        if "Metadata" not in fixed:
            fixed["Metadata"] = self._create_default_metadata(project_name)
            self.fixes_applied.append("Created default metadata")
        else:
            fixed["Metadata"] = self._fix_metadata(fixed["Metadata"], project_name)

        # Fix assets
        if "Assets" not in fixed:
            fixed["Assets"] = self._create_default_assets(project_name)
            self.fixes_applied.append("Created default assets structure")
        else:
            fixed["Assets"] = self._fix_assets(fixed["Assets"], project_name)

        return fixed

    def _validate_top_level(self, project_data: Dict[str, Any]):
        """Validate top-level structure"""
        for key in self.REQUIRED_KEYS:
            if key not in project_data:
                error_msg = f"Missing required top-level key: {key}"
                self.errors.append(error_msg)
                # Could raise exception here if desired
                # raise Gaea2StructureError(error_msg, missing_key=key)

        # Check types
        if "$id" in project_data and not isinstance(project_data["$id"], str):
            self.warnings.append("$id should be a string")

        if "Id" in project_data and not isinstance(project_data["Id"], str):
            self.warnings.append("Id should be a string")

    def _validate_assets(self, assets: Dict[str, Any]):
        """Validate assets structure"""
        if not isinstance(assets, dict):
            self.errors.append("Assets must be a dictionary")
            return

        if "$values" not in assets:
            self.errors.append("Assets missing $values array")
            return

        values = assets.get("$values", [])
        if not isinstance(values, list):
            self.errors.append("Assets.$values must be an array")
            return

        if len(values) == 0:
            self.errors.append("Assets.$values is empty")
            return

        # Check first asset
        asset = values[0]
        for key in self.REQUIRED_ASSET_KEYS:
            if key not in asset:
                self.warnings.append(f"Asset missing key: {key}")

        # Validate terrain
        if "Terrain" in asset:
            self._validate_terrain(asset["Terrain"])

    def _validate_terrain(self, terrain: Dict[str, Any]):
        """Validate terrain structure"""
        if not isinstance(terrain, dict):
            self.errors.append("Terrain must be a dictionary")
            return

        for key in self.REQUIRED_TERRAIN_KEYS:
            if key not in terrain:
                self.warnings.append(f"Terrain missing key: {key}")

        # Check nodes
        if "Nodes" in terrain:
            nodes = terrain["Nodes"]
            if not isinstance(nodes, dict):
                self.errors.append("Terrain.Nodes must be a dictionary")
            elif "$id" not in nodes and len(nodes) > 0:
                # Check if it's a node dictionary
                first_key = list(nodes.keys())[0]
                if not isinstance(nodes[first_key], dict):
                    self.errors.append("Invalid Nodes structure")

    def _validate_metadata(self, metadata: Dict[str, Any]):
        """Validate metadata structure"""
        required_meta = ["Name", "Version", "DateCreated", "DateLastSaved"]

        for key in required_meta:
            if key not in metadata:
                self.warnings.append(f"Metadata missing {key}")

        # Validate date formats
        date_fields = ["DateCreated", "DateLastBuilt", "DateLastSaved"]
        for field in date_fields:
            if field in metadata:
                date_str = metadata[field]
                if not self._is_valid_date(date_str):
                    self.warnings.append(f"Invalid date format in {field}: {date_str}")

    def _is_valid_date(self, date_str: str) -> bool:
        """Check if date string is valid"""
        try:
            # Try to parse the date
            if "T" in date_str:
                # ISO format
                datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                # Gaea format
                datetime.strptime(date_str, "%Y-%m-%d %H:%M:%SZ")
            return True
        except (ValueError, TypeError):
            return False

    def _create_default_metadata(self, project_name: Optional[str] = None) -> Dict[str, Any]:
        """Create default metadata"""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")

        return {
            "$id": "236",
            "Name": project_name or "Untitled",
            "Description": "",
            "Version": "1.0",
            "Owner": "",
            "DateCreated": timestamp,
            "DateLastBuilt": timestamp,
            "DateLastSaved": timestamp,
        }

    def _fix_metadata(self, metadata: Dict[str, Any], project_name: Optional[str] = None) -> Dict[str, Any]:
        """Fix metadata issues"""
        fixed = metadata.copy()
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")

        if "Name" not in fixed or not fixed["Name"]:
            fixed["Name"] = project_name or "Untitled"
            self.fixes_applied.append("Added missing metadata Name")

        if "Version" not in fixed:
            fixed["Version"] = "1.0"
            self.fixes_applied.append("Added default Version")

        # Fix date fields
        date_fields = ["DateCreated", "DateLastBuilt", "DateLastSaved"]
        for field in date_fields:
            if field not in fixed or not self._is_valid_date(fixed.get(field, "")):
                fixed[field] = timestamp
                self.fixes_applied.append(f"Fixed {field}")

        return fixed

    def _create_default_assets(self, project_name: Optional[str] = None) -> Dict[str, Any]:
        """Create default assets structure"""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
        terrain_id = str(uuid.uuid4())

        return {
            "$id": "2",
            "$values": [
                {
                    "$id": "3",
                    "Terrain": {
                        "$id": "4",
                        "Id": terrain_id,
                        "Metadata": {
                            "$id": "5",
                            "Name": project_name or "Terrain",
                            "Description": f"Generated by MCP Server on {timestamp}",
                            "Version": "2.0",
                            "DateCreated": timestamp,
                            "DateLastBuilt": timestamp,
                            "DateLastSaved": timestamp,
                        },
                        "Nodes": {"$id": "6"},
                        "Groups": {"$id": "221"},
                        "Notes": {"$id": "222"},
                        "GraphTabs": {
                            "$id": "223",
                            "$values": [
                                {
                                    "$id": "224",
                                    "Name": "Graph 1",
                                    "Color": "Brass",
                                    "ZoomFactor": 0.5,
                                    "ViewportLocation": {
                                        "$id": "225",
                                        "X": 25000.0,
                                        "Y": 25000.0,
                                    },
                                }
                            ],
                        },
                        "Width": 5000.0,
                        "Height": 2500.0,
                        "Ratio": 0.5,
                    },
                    "Automation": {
                        "$id": "226",
                        "Bindings": {"$id": "227", "$values": []},
                        "Variables": {"$id": "228"},
                        "BoundProperties": {"$id": "229", "$values": []},
                    },
                    "BuildDefinition": self._create_default_build_definition(),
                    "State": self._create_default_state(),
                }
            ],
        }

    def _fix_assets(self, assets: Dict[str, Any], project_name: Optional[str] = None) -> Dict[str, Any]:
        """Fix assets structure"""
        fixed = assets.copy()

        if "$id" not in fixed:
            fixed["$id"] = "2"
            self.fixes_applied.append("Added missing Assets.$id")

        if "$values" not in fixed:
            fixed["$values"] = [self._create_default_assets(project_name)["$values"][0]]
            self.fixes_applied.append("Created default Assets.$values")
            return fixed

        if not isinstance(fixed["$values"], list) or len(fixed["$values"]) == 0:
            fixed["$values"] = [self._create_default_assets(project_name)["$values"][0]]
            self.fixes_applied.append("Fixed Assets.$values")
            return fixed

        # Fix first asset
        asset = fixed["$values"][0]

        if "Terrain" not in asset:
            asset["Terrain"] = self._create_default_assets(project_name)["$values"][0]["Terrain"]
            self.fixes_applied.append("Added missing Terrain")

        if "BuildDefinition" not in asset:
            asset["BuildDefinition"] = self._create_default_build_definition()
            self.fixes_applied.append("Added default BuildDefinition")

        if "State" not in asset:
            asset["State"] = self._create_default_state()
            self.fixes_applied.append("Added default State")

        return fixed

    def _create_default_build_definition(self) -> Dict[str, Any]:
        """Create default build definition"""
        return {
            "$id": "230",
            "Destination": "<Builds>\\[Filename]\\[+++]",
            "Resolution": 2048,
            "BakeResolution": 2048,
            "TileResolution": 1024,
            "BucketResolution": 2048,
            "BucketCount": 1,
            "WorldResolution": 2048,
            "NumberOfTiles": 3,
            "TotalTiles": 9,
            "BucketSizeWithMargin": 3072,
            "EdgeBlending": 0.25,
            "EdgeSize": 512,
            "TileZeroIndex": True,
            "TilePattern": "_y%Y%_x%X%",
            "OrganizeFiles": "NodeSubFolder",
            "Regions": {"$id": "231", "$values": []},
            "PostBuildScript": "",
            "OpenFolder": True,
        }

    def _create_default_state(self) -> Dict[str, Any]:
        """Create default state"""
        return {
            "$id": "232",
            "BakeResolution": 2048,
            "PreviewResolution": 4096,
            "SelectedNode": None,
            "NodeBookmarks": {"$id": "233", "$values": []},
            "Viewport": {
                "$id": "234",
                "Camera": {"$id": "235"},
                "RenderMode": "Realistic",
                "SunAltitude": 33.0,
                "SunAzimuth": 45.0,
                "SunIntensity": 1.0,
                "AmbientOcclusion": True,
                "Shadows": True,
                "AirDensity": 1.0,
                "AmbientIntensity": 1.0,
                "Exposure": 1.0,
                "FogDensity": 0.2,
                "GroundBrightness": 0.8,
                "Haze": 1.0,
                "Ozone": 1.0,
            },
        }

    def get_structure_report(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a detailed structure report"""
        report = {
            "has_required_keys": all(key in project_data for key in self.REQUIRED_KEYS),
            "structure_depth": self._get_structure_depth(project_data),
            "node_count": 0,
            "has_export": False,
            "has_metadata": "Metadata" in project_data,
            "has_build_definition": False,
        }

        # Count nodes
        try:
            assets = project_data.get("Assets", {}).get("$values", [])
            if assets:
                nodes = assets[0].get("Terrain", {}).get("Nodes", {})
                report["node_count"] = len([k for k in nodes.keys() if k != "$id"])

                # Check for export
                for node_id, node_data in nodes.items():
                    if isinstance(node_data, dict) and node_data.get("$type", "").find("Export") != -1:
                        report["has_export"] = True
                        break

                report["has_build_definition"] = "BuildDefinition" in assets[0]
        except (KeyError, TypeError, IndexError, AttributeError):
            pass

        return report

    def _get_structure_depth(self, obj: Any, depth: int = 0) -> int:
        """Get maximum depth of structure"""
        if not isinstance(obj, dict) or depth > 10:
            return depth

        max_depth = depth
        for value in obj.values():
            if isinstance(value, dict):
                max_depth = max(max_depth, self._get_structure_depth(value, depth + 1))
            elif isinstance(value, list) and value:
                if isinstance(value[0], dict):
                    max_depth = max(max_depth, self._get_structure_depth(value[0], depth + 1))

        return max_depth
