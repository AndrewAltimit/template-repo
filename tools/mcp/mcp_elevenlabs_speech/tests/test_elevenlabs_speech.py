"""Tests for ElevenLabs Speech MCP Server.

Tests tool registration and basic functionality.
Note: The package structure has models/ as a sibling directory, so we import
tools.py directly to avoid the broken import chain in __init__.py.
"""

import sys
import importlib.util
from pathlib import Path


def load_tools_module():
    """Load tools.py directly from file to avoid broken import chain."""
    tools_path = Path(__file__).parent.parent / "mcp_elevenlabs_speech" / "tools.py"
    spec = importlib.util.spec_from_file_location("elevenlabs_tools", tools_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


import pytest
from typing import Dict, Any


class TestElevenLabsToolsRegistry:
    """Test tools registry structure."""

    def test_tools_import(self):
        """Test tools registry can be imported."""
        tools_module = load_tools_module()

        assert isinstance(tools_module.TOOLS, dict)
        assert len(tools_module.TOOLS) > 0

    def test_tools_registry_has_expected_tools(self):
        """Test tools registry contains expected tools."""
        tools_module = load_tools_module()

        expected_tools = [
            "synthesize_speech_v3",
            "synthesize_emotional",
            "synthesize_dialogue",
            "generate_sound_effect",
            "list_available_voices",
            "parse_audio_tags",
            "suggest_audio_tags",
            "stream_speech_realtime",
            "stream_speech_http",
        ]
        for tool in expected_tools:
            assert tool in tools_module.TOOLS, f"Missing tool: {tool}"

    def test_tools_registry_has_github_integration(self):
        """Test tools registry has GitHub integration tools."""
        tools_module = load_tools_module()

        github_tools = [
            "generate_pr_audio_response",
            "generate_issue_audio_update",
        ]
        for tool in github_tools:
            assert tool in tools_module.TOOLS, f"Missing GitHub tool: {tool}"

    def test_tools_registry_has_voice_management(self):
        """Test tools registry has voice management tools."""
        tools_module = load_tools_module()

        voice_tools = [
            "list_available_voices",
            "get_voice_details",
            "set_default_voice",
            "configure_voice_settings",
            "set_voice_preset",
        ]
        for tool in voice_tools:
            assert tool in tools_module.TOOLS, f"Missing voice tool: {tool}"

    def test_tools_registry_has_audio_processing(self):
        """Test tools registry has audio processing tools."""
        tools_module = load_tools_module()

        audio_tools = [
            "combine_audio_segments",
            "add_background_sound",
            "generate_variations",
            "create_audio_scene",
        ]
        for tool in audio_tools:
            assert tool in tools_module.TOOLS, f"Missing audio tool: {tool}"

    def test_tools_registry_has_utilities(self):
        """Test tools registry has utility tools."""
        tools_module = load_tools_module()

        utility_tools = [
            "parse_audio_tags",
            "suggest_audio_tags",
            "validate_synthesis_config",
            "get_synthesis_status",
            "clear_audio_cache",
        ]
        for tool in utility_tools:
            assert tool in tools_module.TOOLS, f"Missing utility tool: {tool}"


class TestElevenLabsToolCount:
    """Test total tool count."""

    def test_total_tool_count(self):
        """Test the total number of registered tools."""
        tools_module = load_tools_module()

        # Should have at least 20 tools
        assert len(tools_module.TOOLS) >= 20, f"Expected at least 20 tools, got {len(tools_module.TOOLS)}"

    def test_all_tools_are_none_placeholders(self):
        """Test that tools are initially None (populated at runtime)."""
        tools_module = load_tools_module()

        # All tools should be None in the registry (they get assigned at runtime)
        for name, func in tools_module.TOOLS.items():
            assert func is None, f"Tool {name} should be None placeholder"
