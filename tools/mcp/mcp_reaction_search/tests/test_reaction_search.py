"""Tests for Reaction Search MCP Server.

Tests tool registration and basic functionality.
"""

from pathlib import Path
import sys

# Insert source directory at beginning of path to import from source, not site-packages
_source_dir = Path(__file__).parent.parent
if str(_source_dir) not in sys.path:
    sys.path.insert(0, str(_source_dir))

# Remove any cached imports from site-packages
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith("mcp_reaction_search"):
        del sys.modules[mod_name]


import tempfile

import pytest


class TestReactionSearchToolsRegistry:
    """Test tools registry structure."""

    def test_tools_metadata_import(self):
        """Test tool metadata can be imported."""
        from mcp_reaction_search.tools import TOOL_METADATA

        assert isinstance(TOOL_METADATA, dict)
        assert "name" in TOOL_METADATA
        assert "tools" in TOOL_METADATA

    def test_tools_registry_has_expected_tools(self):
        """Test tools registry contains expected tools."""
        from mcp_reaction_search.tools import TOOL_METADATA

        expected_tools = [
            "search_reactions",
            "get_reaction",
            "list_reaction_tags",
            "refresh_reactions",
            "reaction_search_status",
        ]
        for tool in expected_tools:
            assert tool in TOOL_METADATA["tools"], f"Missing tool: {tool}"

    def test_list_tool_names(self):
        """Test list_tool_names function."""
        from mcp_reaction_search.tools import list_tool_names

        names = list_tool_names()
        assert isinstance(names, list)
        assert "search_reactions" in names
        assert "get_reaction" in names

    def test_get_metadata(self):
        """Test get_metadata function."""
        from mcp_reaction_search.tools import get_metadata

        metadata = get_metadata()
        assert metadata["name"] == "mcp-reaction-search"
        assert "version" in metadata


class TestReactionSearchServerImport:
    """Test server can be imported."""

    def test_server_import(self):
        """Test server module can be imported."""
        from mcp_reaction_search.server import ReactionSearchServer

        assert ReactionSearchServer is not None

    def test_server_init(self):
        """Test server initialization."""
        from mcp_reaction_search.server import ReactionSearchServer

        server = ReactionSearchServer()
        assert server.name == "reaction-search"
        assert server.version == "1.0.0"
        assert server.port == 8024
        assert server._initialized is False

    def test_server_init_custom_port(self):
        """Test server initialization with custom port."""
        from mcp_reaction_search.server import ReactionSearchServer

        server = ReactionSearchServer(port=9999)
        assert server.port == 9999

    def test_server_get_tools(self):
        """Test get_tools returns valid schema."""
        from mcp_reaction_search.server import ReactionSearchServer

        server = ReactionSearchServer()
        tools = server.get_tools()

        assert isinstance(tools, dict)
        assert "search_reactions" in tools
        assert "get_reaction" in tools
        assert "list_reaction_tags" in tools
        assert "refresh_reactions" in tools
        assert "reaction_search_status" in tools

    def test_tools_have_descriptions(self):
        """Test all tools have descriptions."""
        from mcp_reaction_search.server import ReactionSearchServer

        server = ReactionSearchServer()
        tools = server.get_tools()

        for name, tool_info in tools.items():
            assert "description" in tool_info, f"Tool {name} missing description"
            assert len(tool_info["description"]) > 0

    def test_tools_have_parameters(self):
        """Test all tools have parameter definitions."""
        from mcp_reaction_search.server import ReactionSearchServer

        server = ReactionSearchServer()
        tools = server.get_tools()

        for name, tool_info in tools.items():
            assert "parameters" in tool_info, f"Tool {name} missing parameters"


class TestConfigLoaderImport:
    """Test config loader can be imported."""

    def test_config_loader_import(self):
        """Test ConfigLoader can be imported."""
        from mcp_reaction_search.config_loader import ConfigLoader

        assert ConfigLoader is not None

    def test_config_loader_init(self):
        """Test ConfigLoader initialization."""
        from mcp_reaction_search.config_loader import ConfigLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(cache_dir=Path(tmpdir))
            assert loader.cache_dir == Path(tmpdir)

    def test_config_loader_cache_paths(self):
        """Test ConfigLoader cache paths."""
        from mcp_reaction_search.config_loader import ConfigLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(cache_dir=Path(tmpdir))
            assert loader.cache_file == Path(tmpdir) / "reaction_config.json"
            assert loader.cache_meta_file == Path(tmpdir) / "cache_meta.json"

    def test_config_loader_cache_validity(self):
        """Test cache validity checking."""
        from mcp_reaction_search.config_loader import ConfigLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(cache_dir=Path(tmpdir), cache_ttl=3600)

            # No cache exists yet
            assert loader._is_cache_valid() is False

    def test_config_loader_cache_save_and_load(self):
        """Test saving and loading from cache."""
        from mcp_reaction_search.config_loader import ConfigLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(cache_dir=Path(tmpdir))

            # Create mock config
            mock_config = {
                "reaction_images": [
                    {"id": "test1", "description": "Test reaction 1"},
                    {"id": "test2", "description": "Test reaction 2"},
                ]
            }

            # Save to cache
            loader._save_to_cache(mock_config)

            # Verify files exist
            assert loader.cache_file.exists()
            assert loader.cache_meta_file.exists()

            # Load from cache
            loaded = loader._load_from_cache()
            assert loaded is not None
            assert len(loaded["reaction_images"]) == 2

            # Cache should be valid now
            assert loader._is_cache_valid() is True

    def test_config_loader_clear_cache(self):
        """Test clearing cache."""
        from mcp_reaction_search.config_loader import ConfigLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(cache_dir=Path(tmpdir))

            # Create mock config
            mock_config = {"reaction_images": [{"id": "test"}]}
            loader._save_to_cache(mock_config)

            assert loader.cache_file.exists()

            # Clear cache
            result = loader.clear_cache()
            assert result is True
            assert not loader.cache_file.exists()

    def test_config_loader_get_cache_info(self):
        """Test getting cache info."""
        from mcp_reaction_search.config_loader import ConfigLoader

        with tempfile.TemporaryDirectory() as tmpdir:
            loader = ConfigLoader(cache_dir=Path(tmpdir))

            info = loader.get_cache_info()
            assert "cache_dir" in info
            assert "cache_file_exists" in info
            assert "cache_valid" in info


class TestSearchEngineImport:
    """Test search engine can be imported."""

    def test_search_engine_import(self):
        """Test ReactionSearchEngine can be imported."""
        from mcp_reaction_search.search_engine import ReactionSearchEngine

        assert ReactionSearchEngine is not None

    def test_search_engine_init(self):
        """Test search engine initialization."""
        from mcp_reaction_search.search_engine import ReactionSearchEngine

        engine = ReactionSearchEngine()
        assert engine.initialized is False
        assert engine.reaction_count == 0

    def test_reaction_result_dataclass(self):
        """Test ReactionResult dataclass."""
        from mcp_reaction_search.search_engine import ReactionResult

        result = ReactionResult(
            id="test",
            url="https://example.com/test.png",
            markdown="![Reaction](https://example.com/test.png)",
            description="A test reaction",
            similarity=0.95,
            tags=["happy"],
            usage_scenarios=["When celebrating"],
            character_appearance="Anime girl with pink hair",
        )
        assert result.id == "test"
        assert result.similarity == 0.95

    def test_search_engine_build_searchable_text(self):
        """Test building searchable text from reaction."""
        from mcp_reaction_search.search_engine import ReactionSearchEngine

        engine = ReactionSearchEngine()
        reaction = {
            "id": "test",
            "description": "A happy anime girl",
            "tags": ["happy", "excited"],
            "usage_scenarios": ["When celebrating", "After fixing a bug"],
            "character_appearance": "Pink hair",
        }

        text = engine._build_searchable_text(reaction)
        assert "happy anime girl" in text
        assert "happy" in text
        assert "excited" in text
        assert "celebrating" in text
        assert "Pink hair" in text


@pytest.mark.asyncio
class TestServerMethods:
    """Test server async methods."""

    async def test_reaction_search_status_not_initialized(self):
        """Test status when not initialized."""
        from mcp_reaction_search.server import ReactionSearchServer

        server = ReactionSearchServer()
        result = await server.reaction_search_status()

        assert result["initialized"] is False
        assert "note" in result
