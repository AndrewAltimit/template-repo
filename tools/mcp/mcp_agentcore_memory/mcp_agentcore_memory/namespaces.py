"""
Predefined Memory Namespaces

Hierarchical namespace organization for memory records.
Uses '/' separator for glob-style filtering support.
"""


class MemoryNamespace:
    """
    Predefined namespaces for organizing memories.

    Naming convention: category/subcategory
    Examples:
        - codebase/patterns
        - preferences/user
        - agents/claude

    Hierarchical design enables:
        - Glob-style filtering: "codebase/*"
        - Clear organization
        - Future access control per namespace branch
    """

    # ─────────────────────────────────────────────────────────────
    # Codebase Knowledge
    # ─────────────────────────────────────────────────────────────

    # Architectural patterns and design decisions
    ARCHITECTURE = "codebase/architecture"

    # Code patterns and idioms used in the codebase
    PATTERNS = "codebase/patterns"

    # Coding conventions and style guidelines
    CONVENTIONS = "codebase/conventions"

    # Dependency information and version constraints
    DEPENDENCIES = "codebase/dependencies"

    # ─────────────────────────────────────────────────────────────
    # Review Context
    # ─────────────────────────────────────────────────────────────

    # PR review context and feedback patterns
    PR_REVIEWS = "reviews/pr"

    # Issue context and resolution patterns
    ISSUE_CONTEXT = "reviews/issues"

    # ─────────────────────────────────────────────────────────────
    # User & Project Preferences
    # ─────────────────────────────────────────────────────────────

    # User-specific preferences (coding style, tool choices)
    USER_PREFS = "preferences/user"

    # Project-level preferences and configurations
    PROJECT_PREFS = "preferences/project"

    # ─────────────────────────────────────────────────────────────
    # Agent-Specific Learnings
    # ─────────────────────────────────────────────────────────────

    # Learnings specific to Claude Code
    CLAUDE_LEARNINGS = "agents/claude"

    # Learnings specific to Gemini
    GEMINI_LEARNINGS = "agents/gemini"

    # Learnings specific to OpenCode
    OPENCODE_LEARNINGS = "agents/opencode"

    # Learnings specific to Crush
    CRUSH_LEARNINGS = "agents/crush"

    # Learnings specific to Codex
    CODEX_LEARNINGS = "agents/codex"

    # ─────────────────────────────────────────────────────────────
    # Cross-Cutting Concerns
    # ─────────────────────────────────────────────────────────────

    # Security patterns and best practices
    SECURITY_PATTERNS = "security/patterns"

    # Testing patterns and strategies
    TESTING_PATTERNS = "testing/patterns"

    # Performance patterns and optimizations
    PERFORMANCE = "performance/patterns"

    # ─────────────────────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────────────────────

    @classmethod
    def all_namespaces(cls) -> list[str]:
        """Return all predefined namespace values."""
        return [
            value
            for name, value in vars(cls).items()
            if isinstance(value, str) and not name.startswith("_") and "/" in value
        ]

    @classmethod
    def get_category(cls, namespace: str) -> str:
        """
        Extract the top-level category from a namespace.

        Example: "codebase/patterns" -> "codebase"
        """
        return namespace.split("/")[0] if "/" in namespace else namespace

    @classmethod
    def matches_pattern(cls, namespace: str, pattern: str) -> bool:
        """
        Check if a namespace matches a glob-style pattern.

        Examples:
            matches_pattern("codebase/patterns", "codebase/*") -> True
            matches_pattern("agents/claude", "codebase/*") -> False
            matches_pattern("agents/claude", "agents/claude") -> True
        """
        if pattern.endswith("/*"):
            prefix = pattern[:-2]
            return namespace.startswith(prefix + "/") or namespace == prefix
        return namespace == pattern
