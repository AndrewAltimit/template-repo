"""
Tests for memory namespaces.
"""

from mcp_agentcore_memory.namespaces import MemoryNamespace


class TestMemoryNamespace:
    """Tests for MemoryNamespace."""

    def test_predefined_namespaces_exist(self):
        """Predefined namespaces should be defined."""
        assert MemoryNamespace.PATTERNS == "codebase/patterns"
        assert MemoryNamespace.ARCHITECTURE == "codebase/architecture"
        assert MemoryNamespace.CONVENTIONS == "codebase/conventions"
        assert MemoryNamespace.PR_REVIEWS == "reviews/pr"
        assert MemoryNamespace.USER_PREFS == "preferences/user"
        assert MemoryNamespace.CLAUDE_LEARNINGS == "agents/claude"

    def test_all_namespaces(self):
        """all_namespaces should return all predefined values."""
        namespaces = MemoryNamespace.all_namespaces()

        assert len(namespaces) > 0
        assert all("/" in ns for ns in namespaces)
        assert "codebase/patterns" in namespaces
        assert "agents/claude" in namespaces

    def test_get_category(self):
        """get_category should extract top-level category."""
        assert MemoryNamespace.get_category("codebase/patterns") == "codebase"
        assert MemoryNamespace.get_category("agents/claude") == "agents"
        assert MemoryNamespace.get_category("single") == "single"

    def test_matches_pattern_exact(self):
        """Exact pattern match."""
        assert MemoryNamespace.matches_pattern("codebase/patterns", "codebase/patterns") is True
        assert MemoryNamespace.matches_pattern("codebase/patterns", "codebase/conventions") is False

    def test_matches_pattern_wildcard(self):
        """Wildcard pattern match."""
        assert MemoryNamespace.matches_pattern("codebase/patterns", "codebase/*") is True
        assert MemoryNamespace.matches_pattern("codebase/conventions", "codebase/*") is True
        assert MemoryNamespace.matches_pattern("agents/claude", "codebase/*") is False

    def test_matches_pattern_prefix_only(self):
        """Wildcard should match category itself."""
        # "codebase/*" should match "codebase" (the category itself)
        assert MemoryNamespace.matches_pattern("codebase", "codebase/*") is True
