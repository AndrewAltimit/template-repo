#!/usr/bin/env python3
"""Custom agent implementation example.

This example demonstrates creating specialized agents with custom behaviors,
triggers, and implementation logic.
"""

import asyncio
import sys
from typing import Dict


class BugFixAgent:
    """Specialized agent for fixing bugs with specific patterns."""

    def __init__(self, repo: str, github_token: str, openrouter_key: str):
        """Initialize bug fix agent."""
        self.repo = repo
        self.github_token = github_token
        self.openrouter_key = openrouter_key
        self.trigger_pattern = r"\[BugFix\]\[Auto\]"

    async def process_bug_reports(self) -> Dict[int, str]:
        """Process all open bug reports."""
        print("=" * 60)
        print("Bug Fix Agent")
        print("=" * 60)

        print("\nLooking for bugs with [BugFix][Auto] trigger...")
        print("Specialized behavior:")
        print("  - Only processes issues labeled 'bug'")
        print("  - Uses conservative temperature (0.2)")
        print("  - Includes test generation")
        print("  - Adds error handling")

        # Would implement custom bug-fixing logic
        # For demo, show the pattern
        return {}

    def customize_prompt(self, issue_body: str) -> str:
        """Create bug-fix specific prompt."""
        return f"""You are a bug-fixing specialist.

IMPORTANT GUIDELINES:
1. Identify root cause before fixing
2. Add comprehensive error handling
3. Include unit tests for the fix
4. Add logging for debugging
5. Consider edge cases

ISSUE:
{issue_body}

REQUIREMENTS:
- Fix must be minimal and focused
- All existing tests must pass
- Add new test covering the bug
- Include error messages
- Update documentation if needed
"""


class DocumentationAgent:
    """Specialized agent for documentation tasks."""

    def __init__(self, repo: str, github_token: str):
        """Initialize documentation agent."""
        self.repo = repo
        self.github_token = github_token
        self.trigger_pattern = r"\[Docs\]\[Auto\]"

    async def process_doc_requests(self) -> Dict[int, str]:
        """Process documentation requests."""
        print("=" * 60)
        print("Documentation Agent")
        print("=" * 60)

        print("\nLooking for documentation requests...")
        print("Specialized behavior:")
        print("  - Follows project documentation style")
        print("  - Includes code examples")
        print("  - Adds cross-references")
        print("  - Validates markdown formatting")

        return {}

    def customize_prompt(self, issue_body: str) -> str:
        """Create documentation-specific prompt."""
        return f"""You are a technical documentation specialist.

STYLE GUIDELINES:
1. Clear, concise language
2. Code examples for all features
3. Common use cases section
4. Troubleshooting section
5. Cross-references to related docs

DOCUMENTATION REQUEST:
{issue_body}

REQUIREMENTS:
- Follow existing documentation structure
- Use consistent terminology
- Include practical examples
- Add table of contents if >500 words
- Validate all links
- Check spelling and grammar
"""


class RefactoringAgent:
    """Specialized agent for code refactoring."""

    def __init__(self, repo: str, github_token: str, openrouter_key: str):
        """Initialize refactoring agent."""
        self.repo = repo
        self.github_token = github_token
        self.openrouter_key = openrouter_key
        self.trigger_pattern = r"\[Refactor\]\[Auto\]"

    async def process_refactoring_requests(self) -> Dict[int, str]:
        """Process refactoring requests."""
        print("=" * 60)
        print("Refactoring Agent")
        print("=" * 60)

        print("\nLooking for refactoring requests...")
        print("Specialized behavior:")
        print("  - Preserves existing functionality")
        print("  - Improves code quality metrics")
        print("  - Maintains test coverage")
        print("  - Updates related documentation")

        return {}

    def customize_prompt(self, issue_body: str) -> str:
        """Create refactoring-specific prompt."""
        return f"""You are a code refactoring expert.

REFACTORING PRINCIPLES:
1. Preserve exact functionality (no behavior changes)
2. Improve code readability
3. Reduce complexity
4. Follow project conventions
5. Maintain/improve test coverage

REFACTORING REQUEST:
{issue_body}

REQUIREMENTS:
- All existing tests must pass
- No new features
- Improve code quality metrics
- Update comments/docstrings
- Consider performance implications
- Make atomic, reviewable changes
"""


class SecurityFixAgent:
    """Specialized agent for security vulnerabilities."""

    def __init__(self, repo: str, github_token: str, openrouter_key: str):
        """Initialize security fix agent."""
        self.repo = repo
        self.github_token = github_token
        self.openrouter_key = openrouter_key
        self.trigger_pattern = r"\[Security\]\[Auto\]"

    async def process_security_issues(self) -> Dict[int, str]:
        """Process security issues."""
        print("=" * 60)
        print("Security Fix Agent")
        print("=" * 60)

        print("\nLooking for security issues...")
        print("Specialized behavior:")
        print("  - High priority processing")
        print("  - Secure coding practices")
        print("  - Input validation focus")
        print("  - Security test addition")
        print("  - Creates private PR (if supported)")

        return {}

    def customize_prompt(self, issue_body: str) -> str:
        """Create security-specific prompt."""
        return f"""You are a security specialist fixing vulnerabilities.

SECURITY REQUIREMENTS:
1. Fix root cause, not symptoms
2. Add input validation
3. Use secure APIs
4. Avoid common vulnerabilities (OWASP Top 10)
5. Include security tests

VULNERABILITY:
{issue_body}

REQUIREMENTS:
- Fix must be comprehensive
- Add input sanitization
- Use parameterized queries (SQL)
- Escape outputs (XSS)
- Validate file paths (Path Traversal)
- Check authentication/authorization
- Add security-focused tests
- Consider security implications
"""


class PerformanceAgent:
    """Specialized agent for performance optimization."""

    def __init__(self, repo: str, github_token: str, openrouter_key: str):
        """Initialize performance agent."""
        self.repo = repo
        self.github_token = github_token
        self.openrouter_key = openrouter_key
        self.trigger_pattern = r"\[Performance\]\[Auto\]"

    async def process_performance_issues(self) -> Dict[int, str]:
        """Process performance optimization requests."""
        print("=" * 60)
        print("Performance Optimization Agent")
        print("=" * 60)

        print("\nLooking for performance issues...")
        print("Specialized behavior:")
        print("  - Profiles before optimizing")
        print("  - Measures improvements")
        print("  - Adds performance tests")
        print("  - Considers memory usage")

        return {}

    def customize_prompt(self, issue_body: str) -> str:
        """Create performance-specific prompt."""
        return f"""You are a performance optimization specialist.

OPTIMIZATION GUIDELINES:
1. Profile first, optimize later
2. Measure improvement
3. Consider time/space tradeoffs
4. Avoid premature optimization
5. Keep code readable

PERFORMANCE ISSUE:
{issue_body}

REQUIREMENTS:
- Identify bottleneck
- Optimize hot paths
- Consider caching
- Use appropriate data structures
- Add performance benchmarks
- Document complexity improvements
- Maintain correctness
"""


async def demonstrate_custom_triggers() -> None:
    """Demonstrate custom trigger patterns."""
    print("=" * 60)
    print("Custom Trigger Patterns")
    print("=" * 60)

    triggers = {
        "Bug Fix": "[BugFix][Auto]",
        "Documentation": "[Docs][Auto]",
        "Refactoring": "[Refactor][Auto]",
        "Security": "[Security][Auto]",
        "Performance": "[Performance][Auto]",
        "Feature": "[Feature][Auto]",
        "Test": "[Test][Auto]",
    }

    print("\nCustom trigger patterns for specialized agents:\n")
    for agent_type, pattern in triggers.items():
        print(f"  {agent_type:15} → {pattern}")

    print("\n" + "-" * 60)
    print("Usage:")
    print("-" * 60)
    print("  1. User adds trigger comment to issue")
    print("  2. Specialized agent detects pattern")
    print("  3. Agent applies custom logic")
    print("  4. Creates PR with specialized prompt")


async def demonstrate_custom_behavior() -> None:
    """Demonstrate customizing agent behavior."""
    print("\n" + "=" * 60)
    print("Custom Agent Behavior")
    print("=" * 60)

    print("\nWays to customize agent behavior:")

    print("\n1. Custom Prompts:")
    print("   - Specialized instructions per agent type")
    print("   - Domain-specific guidelines")
    print("   - Project-specific conventions")

    print("\n2. Custom Validation:")
    print("   - Type-specific checks before implementation")
    print("   - Label-based filtering")
    print("   - Priority-based queuing")

    print("\n3. Custom Post-Processing:")
    print("   - Automatic test generation")
    print("   - Documentation updates")
    print("   - Metric collection")

    print("\n4. Custom Integration:")
    print("   - External tool integration")
    print("   - CI/CD pipeline hooks")
    print("   - Notification systems")


async def demonstrate_integration_example() -> None:
    """Show complete integration example."""
    print("\n" + "=" * 60)
    print("Complete Custom Agent Integration")
    print("=" * 60)

    print("\nExample: Integrating BugFixAgent with monitors")
    print(
        """
from github_ai_agents.monitors.issue_monitor import IssueMonitor

class BugFixMonitor(IssueMonitor):
    \"\"\"Custom monitor for bug fixes.\"\"\"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bug_fix_agent = BugFixAgent(
            repo=self.repo,
            github_token=self.github_token,
            openrouter_key=self.openrouter_api_key
        )

    async def detect_trigger(self, comment: str) -> bool:
        \"\"\"Detect custom trigger pattern.\"\"\"
        import re
        return bool(re.search(r'\\[BugFix\\]\\[Auto\\]', comment))

    async def generate_implementation(self, issue_data: dict) -> str:
        \"\"\"Generate bug fix with custom prompt.\"\"\"
        custom_prompt = self.bug_fix_agent.customize_prompt(
            issue_data['body']
        )

        # Call AI with custom prompt
        implementation = await self.call_ai(
            prompt=custom_prompt,
            temperature=0.2,  # Conservative for bug fixes
            max_tokens=4000
        )

        return implementation

# Usage
monitor = BugFixMonitor(
    repo="owner/repo",
    github_token=token,
    openrouter_api_key=key
)

# Automatically processes issues with [BugFix][Auto] trigger
await monitor.process_recent_issues()
"""
    )


def main() -> None:
    """Run custom agent examples."""
    print("GitHub AI Agents - Custom Agent Example\n")

    if "--help" in sys.argv:
        print("Usage: python custom_agent_example.py [OPTIONS]\n")
        print("Options:")
        print("  --triggers         Show custom trigger patterns")
        print("  --behavior         Show behavior customization")
        print("  --integration      Show integration example")
        print("  --all              Show all demonstrations")
        print("  --help             Show this help")
        print("\nThis example shows how to create specialized agents:")
        print("  - BugFixAgent: Focused on bug fixes")
        print("  - DocumentationAgent: Documentation generation")
        print("  - RefactoringAgent: Code quality improvements")
        print("  - SecurityFixAgent: Security vulnerability fixes")
        print("  - PerformanceAgent: Performance optimizations")
        return

    async def run_demos():
        if "--triggers" in sys.argv or "--all" in sys.argv:
            await demonstrate_custom_triggers()

        if "--behavior" in sys.argv or "--all" in sys.argv:
            await demonstrate_custom_behavior()

        if "--integration" in sys.argv or "--all" in sys.argv:
            await demonstrate_integration_example()

        # Default: show all
        if not any(opt in sys.argv for opt in ["--triggers", "--behavior", "--integration", "--all"]):
            await demonstrate_custom_triggers()
            await demonstrate_custom_behavior()
            await demonstrate_integration_example()

    try:
        asyncio.run(run_demos())

        print("\n" + "=" * 60)
        print("Next Steps")
        print("=" * 60)
        print("\n1. Identify specialized needs in your workflow")
        print("2. Create custom agent classes")
        print("3. Define custom trigger patterns")
        print("4. Integrate with existing monitors")
        print("5. Test with real issues")
        print("\nSee examples/README.md for more patterns")

    except KeyboardInterrupt:
        print("\n\nExample interrupted")


if __name__ == "__main__":
    main()
