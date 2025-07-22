#!/usr/bin/env python3
"""
Enhanced property validation for Gaea2 nodes using pattern knowledge
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..utils.gaea2_pattern_knowledge import PROPERTY_RECOMMENDATIONS

logger = logging.getLogger(__name__)


class Gaea2PropertyValidator:
    """Advanced property validation with pattern-based recommendations"""

    def __init__(self):
        # Load property patterns from analysis
        self.patterns = self._load_property_patterns()
        self.warnings = []
        self.fixes_applied = []

    def _load_property_patterns(self) -> Dict[str, Any]:
        """Load property patterns from analysis results"""
        patterns = {}

        # Try to load from analysis results
        analysis_path = Path(__file__).parent.parent.parent / "gaea2_analysis_results.json"
        if analysis_path.exists():
            try:
                with open(analysis_path) as f:
                    data = json.load(f)
                    # Extract property patterns from node sequences
                    patterns = data.get("property_patterns", {})
            except Exception as e:
                logger.warning(f"Could not load analysis results: {e}")

        # Merge with hardcoded recommendations
        for node_type, props in PROPERTY_RECOMMENDATIONS.items():
            if node_type not in patterns:
                patterns[node_type] = props
            else:
                patterns[node_type].update(props)

        return patterns

    def validate_properties(
        self, node_type: str, properties: Dict[str, Any], strict: bool = False
    ) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate and fix node properties

        Returns:
            - is_valid: Whether properties are valid
            - errors: List of error messages
            - fixed_properties: Properties with corrections applied
        """
        errors = []
        warnings = []
        fixed_properties = properties.copy()

        # Get property definitions for this node type
        node_patterns = self.patterns.get(node_type, {})

        # Special handling for common properties
        if node_type == "Erosion2":
            fixed_properties, errs, warns = self._validate_erosion_properties(properties)
            errors.extend(errs)
            warnings.extend(warns)

        elif node_type == "Rivers":
            fixed_properties, errs, warns = self._validate_rivers_properties(properties)
            errors.extend(errs)
            warnings.extend(warns)

        elif node_type == "Combine":
            fixed_properties, errs, warns = self._validate_combine_properties(properties)
            errors.extend(errs)
            warnings.extend(warns)

        elif node_type == "SatMap":
            fixed_properties, errs, warns = self._validate_satmap_properties(properties)
            errors.extend(errs)
            warnings.extend(warns)

        elif node_type == "Export":
            # Export nodes shouldn't have format/bitdepth properties
            if "Format" in fixed_properties:
                del fixed_properties["Format"]
                warnings.append("Removed 'Format' property from Export node (handled by build system)")
            if "BitDepth" in fixed_properties:
                del fixed_properties["BitDepth"]
                warnings.append("Removed 'BitDepth' property from Export node (handled by build system)")

        # Generic validation for numeric properties
        for prop_name, prop_value in list(fixed_properties.items()):
            if prop_name in node_patterns:
                pattern = node_patterns[prop_name]

                # Range validation with type safety
                if "range" in pattern:
                    min_val, max_val = pattern["range"]

                    # Ensure we can compare values
                    try:
                        # Convert string numbers to appropriate type
                        if isinstance(prop_value, str) and prop_value.replace(".", "").replace("-", "").isdigit():
                            prop_value = float(prop_value)
                            if prop_value == int(prop_value):
                                prop_value = int(prop_value)

                        # Ensure min/max are same type as value for comparison
                        if isinstance(prop_value, (int, float)):
                            # Convert min/max to match value type if needed
                            if isinstance(prop_value, int) and isinstance(min_val, float):
                                if min_val == int(min_val):
                                    min_val = int(min_val)
                            if isinstance(prop_value, int) and isinstance(max_val, float):
                                if max_val == int(max_val):
                                    max_val = int(max_val)

                            if prop_value < min_val:
                                fixed_properties[prop_name] = min_val
                                warnings.append(f"{prop_name} value {prop_value} below minimum {min_val}, set to {min_val}")
                            elif prop_value > max_val:
                                fixed_properties[prop_name] = max_val
                                warnings.append(f"{prop_name} value {prop_value} above maximum {max_val}, set to {max_val}")
                    except (TypeError, ValueError) as e:
                        # If comparison fails, log warning but don't crash
                        warnings.append(f"Could not validate range for {prop_name}: {str(e)}")

                # Enum validation
                if "options" in pattern and prop_value not in pattern["options"]:
                    if "default" in pattern:
                        fixed_properties[prop_name] = pattern["default"]
                        warnings.append(
                            f"{prop_name} value '{prop_value}' not in valid options, set to default '{pattern['default']}'"
                        )
                    else:
                        errors.append(f"{prop_name} value '{prop_value}' not in valid options: {pattern['options']}")

        # Store warnings for retrieval
        self.warnings = warnings

        is_valid = len(errors) == 0 or not strict
        return is_valid, errors, fixed_properties

    def _validate_erosion_properties(self, properties: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """Validate Erosion2 node properties"""
        errors: List[str] = []
        warnings: List[str] = []
        fixed = properties.copy()

        # Duration check
        if "Duration" in fixed:
            duration = fixed["Duration"]
            # Convert string to float if needed
            if isinstance(duration, str):
                try:
                    duration = float(duration)
                    fixed["Duration"] = duration
                except ValueError:
                    warnings.append(f"Invalid Duration value: {duration}, using default 0.07")
                    duration = 0.07
                    fixed["Duration"] = duration

            if isinstance(duration, (int, float)):
                if duration > 0.15:
                    fixed["Duration"] = 0.1
                    warnings.append(f"Erosion Duration {duration} too high for performance, reduced to 0.1")
                elif duration < 0.01:
                    fixed["Duration"] = 0.04
                    warnings.append(f"Erosion Duration {duration} too low, increased to 0.04")
        else:
            # Add default duration
            fixed["Duration"] = 0.07
            warnings.append("Added default Duration=0.07 to Erosion2 node")

        # Scale validation
        if "Scale" in fixed and isinstance(fixed["Scale"], (int, float)):
            if fixed["Scale"] < 1:
                fixed["Scale"] = 1
                warnings.append("Erosion Scale below 1, set to minimum 1")
            elif fixed["Scale"] > 100000:
                fixed["Scale"] = 50000
                warnings.append("Erosion Scale above 100000, reduced to 50000")

        return fixed, errors, warnings

    def _validate_rivers_properties(self, properties: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """Validate Rivers node properties"""
        errors: List[str] = []
        warnings: List[str] = []
        fixed = properties.copy()

        # Headwaters check
        if "Headwaters" in fixed:
            headwaters = fixed["Headwaters"]
            if isinstance(headwaters, (int, float)):
                if headwaters > 300:
                    fixed["Headwaters"] = 200
                    warnings.append(f"Rivers Headwaters {headwaters} too high for performance, reduced to 200")
                elif headwaters < 10:
                    fixed["Headwaters"] = 50
                    warnings.append(f"Rivers Headwaters {headwaters} too low, increased to 50")

                # Ensure integer
                fixed["Headwaters"] = int(fixed["Headwaters"])
        else:
            fixed["Headwaters"] = 100
            warnings.append("Added default Headwaters=100 to Rivers node")

        return fixed, errors, warnings

    def _validate_combine_properties(self, properties: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """Validate Combine node properties"""
        errors: List[str] = []
        warnings: List[str] = []
        fixed = properties.copy()

        # Ratio check
        if "Ratio" in fixed:
            ratio = fixed["Ratio"]
            if isinstance(ratio, (int, float)):
                if ratio < 0:
                    fixed["Ratio"] = 0.0
                    warnings.append("Combine Ratio below 0, set to 0.0")
                elif ratio > 1:
                    fixed["Ratio"] = 1.0
                    warnings.append("Combine Ratio above 1, set to 1.0")
        else:
            # Default ratio for balanced blend
            fixed["Ratio"] = 0.5
            warnings.append("Added default Ratio=0.5 to Combine node")

        # Method validation
        if "Method" in fixed:
            valid_methods = [
                "Add",
                "Subtract",
                "Multiply",
                "Max",
                "Min",
                "Average",
                "Blend",
            ]
            if fixed["Method"] not in valid_methods:
                fixed["Method"] = "Blend"
                warnings.append("Invalid Combine Method, set to 'Blend'")

        return fixed, errors, warnings

    def _validate_satmap_properties(self, properties: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """Validate SatMap node properties"""
        errors: List[str] = []
        warnings: List[str] = []
        fixed = properties.copy()

        # Common presets
        valid_presets = ["Rocky", "Desert", "Alpine", "Volcanic", "Custom"]

        if "Preset" in fixed and fixed["Preset"] not in valid_presets:
            # Try to find closest match
            preset = str(fixed["Preset"])
            for valid in valid_presets:
                if valid.lower() in preset.lower():
                    fixed["Preset"] = valid
                    warnings.append(f"Corrected SatMap Preset '{preset}' to '{valid}'")
                    break

        return fixed, errors, warnings

    def suggest_missing_properties(self, node_type: str, existing_properties: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest properties that are commonly used but missing"""
        suggestions = {}

        if node_type in self.patterns:
            pattern = self.patterns[node_type]

            for prop_name, prop_info in pattern.items():
                if prop_name not in existing_properties:
                    if isinstance(prop_info, dict) and "default" in prop_info:
                        suggestions[prop_name] = prop_info["default"]

        return suggestions

    def get_performance_optimized_properties(self, node_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Get performance-optimized version of properties"""
        optimized = properties.copy()

        if node_type == "Erosion2":
            optimized["Duration"] = min(properties.get("Duration", 0.07), 0.05)
            if "Iterations" in optimized:
                optimized["Iterations"] = min(optimized["Iterations"], 3)

        elif node_type == "Rivers":
            optimized["Headwaters"] = min(properties.get("Headwaters", 100), 100)

        elif node_type == "Thermal2":
            if "Duration" in optimized:
                optimized["Duration"] = min(optimized["Duration"], 0.05)

        return optimized

    def get_quality_optimized_properties(self, node_type: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Get quality-optimized version of properties"""
        optimized = properties.copy()

        if node_type == "Erosion2":
            optimized["Duration"] = max(properties.get("Duration", 0.07), 0.1)
            if "Scale" in optimized:
                optimized["Scale"] = max(optimized["Scale"], 10000)

        elif node_type == "Rivers":
            optimized["Headwaters"] = max(properties.get("Headwaters", 100), 150)

        elif node_type == "TextureBase":
            if "Scale" in optimized:
                optimized["Scale"] = min(optimized["Scale"], 0.1)  # Finer detail

        return optimized
