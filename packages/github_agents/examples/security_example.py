#!/usr/bin/env python3
"""Security features and best practices example.

This example demonstrates the security model for AI agents including:
- User authorization
- Commit validation
- Trigger pattern validation
- API key management
- Rate limiting
- Security audit logging
"""

import sys


def demonstrate_user_authorization() -> None:
    """Demonstrate user authorization features."""
    print("=" * 60)
    print("1. User Authorization")
    print("=" * 60)

    print("\nOnly authorized users can trigger agents.")
    print("\nConfiguration:")
    print(
        """
# Method 1: Environment variable
export ALLOWED_USERS=admin,maintainer,contributor

# Method 2: In code
monitor = IssueMonitor(
    repo="owner/repo",
    github_token=token,
    allowed_users=["admin", "maintainer", "contributor"]
)
"""
    )

    print("\nBehavior:")
    print("  ✓ Authorized user adds [Approved][Agent] → Agent executes")
    print("  ✗ Unauthorized user adds [Approved][Agent] → Ignored")

    print("\nExample Scenario:")
    scenarios = [
        ("admin", "[Approved][OpenCode]", "ALLOWED", "Implementation proceeds"),
        ("contributor", "[Approved][OpenCode]", "ALLOWED", "Implementation proceeds"),
        ("external-user", "[Approved][OpenCode]", "DENIED", "Trigger ignored"),
        ("bot-account", "[Approved][OpenCode]", "DENIED", "Trigger ignored"),
    ]

    print(f"\n{'User':<20} {'Comment':<25} {'Result':<10} {'Action'}")
    print("-" * 80)
    for user, comment, result, action in scenarios:
        print(f"{user:<20} {comment:<25} {result:<10} {action}")

    print("\n" + "-" * 60)
    print("Best Practices:")
    print("-" * 60)
    print("  1. Use GitHub usernames, not display names")
    print("  2. Keep list minimal (maintainers only)")
    print("  3. Review periodically and remove inactive users")
    print("  4. Use GitHub teams for easier management (future feature)")
    print("  5. Log all authorization attempts")


def demonstrate_commit_validation() -> None:
    """Demonstrate commit validation security."""
    print("\n" + "=" * 60)
    print("2. Commit Validation")
    print("=" * 60)

    print("\nPrevents code injection after approval.")

    print("\n" + "-" * 60)
    print("Attack Scenario (Prevented):")
    print("-" * 60)

    timeline = [
        ("10:00", "User approves issue with [Approved][Agent]"),
        ("10:01", "Approval recorded with commit SHA abc123"),
        ("10:02", "Attacker modifies issue description"),
        ("10:03", "Agent starts processing"),
        ("10:04", "✓ Validation detects commit change"),
        ("10:05", "✗ Execution blocked, requires re-approval"),
    ]

    for time, event in timeline:
        status = "✓" if "Validation" in event or "blocked" in event else " "
        print(f"  {time}  {status} {event}")

    print("\n" + "-" * 60)
    print("Implementation:")
    print("-" * 60)
    print(
        """
def validate_approval_comment(issue_id: int, approval_time: datetime) -> bool:
    # Get comments after approval
    comments_after = get_comments_after(issue_id, approval_time)

    # Check if description changed
    if description_changed_after(issue_id, approval_time):
        return False

    # Check if commits changed (for PR fixes)
    if issue_is_pr(issue_id):
        if commits_changed_after(issue_id, approval_time):
            return False

    return True
"""
    )

    print("\n" + "-" * 60)
    print("Security Guarantees:")
    print("-" * 60)
    print("  ✓ Code generated matches approved description")
    print("  ✓ No injection possible after approval")
    print("  ✓ Any changes require re-approval")
    print("  ✓ Audit trail maintained in GitHub")


def demonstrate_trigger_validation() -> None:
    """Demonstrate trigger pattern validation."""
    print("\n" + "=" * 60)
    print("3. Trigger Pattern Validation")
    print("=" * 60)

    print("\nOnly valid trigger patterns activate agents.")

    print("\n" + "-" * 60)
    print("Valid Triggers:")
    print("-" * 60)

    valid_triggers = [
        ("[Approved][OpenCode]", "OpenCode agent for issue/PR implementation"),
        ("[Approved][Claude]", "Claude agent for complex tasks"),
        ("[Approved][Gemini]", "Gemini agent for validation"),
        ("[Approved][Crush]", "Crush agent for quick fixes"),
        ("[Approved][Codex]", "Codex agent for OpenAI tasks"),
        ("[Review][OpenCode]", "OpenCode for code review"),
        ("[Review][Gemini]", "Gemini for code review"),
    ]

    for trigger, description in valid_triggers:
        print(f"  ✓ {trigger:<25} {description}")

    print("\n" + "-" * 60)
    print("Invalid Triggers (Ignored):")
    print("-" * 60)

    invalid_triggers = [
        ("Approved OpenCode", "Missing brackets"),
        ("[Approved]OpenCode", "Missing space"),
        ("[approved][opencode]", "Wrong case"),
        ("[Approved][Unknown]", "Unknown agent"),
        ("[Execute][OpenCode]", "Wrong action"),
        ("# [Approved][OpenCode]", "Inside code block"),
    ]

    for trigger, reason in invalid_triggers:
        print(f"  ✗ {trigger:<25} {reason}")

    print("\n" + "-" * 60)
    print("Pattern Regex:")
    print("-" * 60)
    print(
        """
TRIGGER_PATTERN = r'\\[(?:Approved|Fix)\\]\\[(?:OpenCode|Claude|Gemini|Crush|Codex)\\]'

def is_valid_trigger(comment: str) -> bool:
    # Exclude code blocks
    if in_code_block(comment):
        return False

    # Match trigger pattern
    match = re.search(TRIGGER_PATTERN, comment)
    return match is not None
"""
    )


def demonstrate_api_key_management() -> None:
    """Demonstrate secure API key management."""
    print("\n" + "=" * 60)
    print("4. API Key Management")
    print("=" * 60)

    print("\n" + "-" * 60)
    print("NEVER DO THIS:")
    print("-" * 60)
    print(
        """
# ✗ WRONG: Hardcoded key
openrouter_key = "sk-or-v1-abc123..."

# ✗ WRONG: In version control
config.yml:
  openrouter_key: "sk-or-v1-abc123..."

# ✗ WRONG: In log messages
print(f"Using key: {openrouter_key}")
"""
    )

    print("\n" + "-" * 60)
    print("DO THIS INSTEAD:")
    print("-" * 60)
    print(
        """
# ✓ RIGHT: Environment variables
export OPENROUTER_API_KEY=sk-or-v1-abc123...

# ✓ RIGHT: GitHub Secrets (for Actions)
secrets:
  OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}

# ✓ RIGHT: Load from environment
openrouter_key = os.getenv("OPENROUTER_API_KEY")

# ✓ RIGHT: Never log keys
print("Using key: ***" + openrouter_key[-4:])  # Only last 4 chars
"""
    )

    print("\n" + "-" * 60)
    print("Key Rotation:")
    print("-" * 60)
    print("  1. Generate new key in OpenRouter dashboard")
    print("  2. Update environment variable")
    print("  3. Test with new key")
    print("  4. Revoke old key")
    print("  5. Update documentation")

    print("\n" + "-" * 60)
    print("Key Permissions:")
    print("-" * 60)
    print("  - Use service accounts, not personal keys")
    print("  - Limit scope to required operations")
    print("  - Set expiration dates")
    print("  - Monitor usage")
    print("  - Revoke compromised keys immediately")


def demonstrate_rate_limiting() -> None:
    """Demonstrate rate limiting features."""
    print("\n" + "=" * 60)
    print("5. Rate Limiting")
    print("=" * 60)

    print("\nPrevents API abuse and manages costs.")

    print("\n" + "-" * 60)
    print("Built-in Rate Limits:")
    print("-" * 60)

    limits = [
        ("GitHub API", "5000 requests/hour", "GraphQL: 5000 points/hour"),
        ("OpenRouter API", "Varies by tier", "Check dashboard for limits"),
        ("Agent Timeout", "600 seconds default", "Prevents runaway execution"),
        ("Concurrent Jobs", "1 per issue", "Claim system prevents conflicts"),
    ]

    print(f"\n{'Service':<20} {'Limit':<25} {'Notes'}")
    print("-" * 70)
    for service, limit, notes in limits:
        print(f"{service:<20} {limit:<25} {notes}")

    print("\n" + "-" * 60)
    print("Configuration:")
    print("-" * 60)
    print(
        """
# Agent timeout
monitor = IssueMonitor(
    repo="owner/repo",
    github_token=token,
    timeout=600  # 10 minutes max
)

# Retry with backoff
async def with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await func()
        except RateLimitError:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # Exponential backoff
                await asyncio.sleep(wait)
            else:
                raise

# Request throttling
from ratelimit import limits, sleep_and_retry

@sleep_and_retry
@limits(calls=10, period=60)  # 10 calls per minute
async def make_api_call():
    ...
"""
    )

    print("\n" + "-" * 60)
    print("Best Practices:")
    print("-" * 60)
    print("  1. Cache responses when possible")
    print("  2. Use exponential backoff for retries")
    print("  3. Monitor API usage")
    print("  4. Set reasonable timeouts")
    print("  5. Handle rate limit errors gracefully")


def demonstrate_audit_logging() -> None:
    """Demonstrate security audit logging."""
    print("\n" + "=" * 60)
    print("6. Security Audit Logging")
    print("=" * 60)

    print("\nTrack all security-relevant events.")

    print("\n" + "-" * 60)
    print("Events to Log:")
    print("-" * 60)

    events = [
        ("Authorization Attempt", "High", "Track all trigger attempts"),
        ("Authorization Denial", "High", "Unauthorized user detection"),
        ("Commit Validation Failure", "Critical", "Potential injection attempt"),
        ("API Key Usage", "Medium", "Monitor for abuse"),
        ("Rate Limit Hit", "Medium", "Capacity planning"),
        ("Agent Execution", "Low", "Normal operation tracking"),
        ("Error/Exception", "High", "Debugging and security"),
    ]

    print(f"\n{'Event':<30} {'Priority':<10} {'Purpose'}")
    print("-" * 70)
    for event, priority, purpose in events:
        print(f"{event:<30} {priority:<10} {purpose}")

    print("\n" + "-" * 60)
    print("Implementation:")
    print("-" * 60)
    print(
        """
import logging
from datetime import datetime

# Configure audit logger
audit_logger = logging.getLogger("ai_agents.audit")
audit_logger.setLevel(logging.INFO)

# Log structure
def log_security_event(
    event_type: str,
    user: str,
    action: str,
    result: str,
    details: dict = None
):
    audit_logger.info(
        f"SECURITY_EVENT",
        extra={
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user": user,
            "action": action,
            "result": result,
            "details": details or {},
        }
    )

# Example usage
log_security_event(
    event_type="AUTHORIZATION",
    user="external-user",
    action="trigger_agent",
    result="DENIED",
    details={
        "issue": 123,
        "trigger": "[Approved][OpenCode]",
        "reason": "User not in allowed list"
    }
)
"""
    )

    print("\n" + "-" * 60)
    print("Log Analysis:")
    print("-" * 60)
    print("  - Review daily for unusual activity")
    print("  - Alert on critical events")
    print("  - Aggregate metrics (success rate, denials)")
    print("  - Correlate with GitHub audit log")
    print("  - Retain for compliance (30-90 days)")


def main() -> None:
    """Run security examples."""
    print("GitHub AI Agents - Security Example\n")

    if "--help" in sys.argv:
        print("Usage: python security_example.py [OPTIONS]\n")
        print("Options:")
        print("  --authorization    User authorization details")
        print("  --commit-validation  Commit validation details")
        print("  --triggers         Trigger pattern validation")
        print("  --api-keys         API key management")
        print("  --rate-limiting    Rate limiting features")
        print("  --audit-logging    Security audit logging")
        print("  --all              Show all security features")
        print("  --help             Show this help")
        return

    if "--authorization" in sys.argv or "--all" in sys.argv:
        demonstrate_user_authorization()

    if "--commit-validation" in sys.argv or "--all" in sys.argv:
        demonstrate_commit_validation()

    if "--triggers" in sys.argv or "--all" in sys.argv:
        demonstrate_trigger_validation()

    if "--api-keys" in sys.argv or "--all" in sys.argv:
        demonstrate_api_key_management()

    if "--rate-limiting" in sys.argv or "--all" in sys.argv:
        demonstrate_rate_limiting()

    if "--audit-logging" in sys.argv or "--all" in sys.argv:
        demonstrate_audit_logging()

    # Default: show all
    if not any(
        opt in sys.argv
        for opt in [
            "--authorization",
            "--commit-validation",
            "--triggers",
            "--api-keys",
            "--rate-limiting",
            "--audit-logging",
            "--all",
        ]
    ):
        demonstrate_user_authorization()
        demonstrate_commit_validation()
        demonstrate_trigger_validation()
        demonstrate_api_key_management()
        demonstrate_rate_limiting()
        demonstrate_audit_logging()

    print("\n" + "=" * 60)
    print("Security Checklist")
    print("=" * 60)
    print("\nBefore deploying to production:")
    print("  ☐ Configure allowed_users list")
    print("  ☐ Enable commit validation")
    print("  ☐ Store API keys in secrets")
    print("  ☐ Set appropriate timeouts")
    print("  ☐ Enable audit logging")
    print("  ☐ Review rate limits")
    print("  ☐ Test authorization (positive and negative)")
    print("  ☐ Test commit validation")
    print("  ☐ Document security procedures")
    print("  ☐ Set up monitoring and alerts")

    print("\n" + "=" * 60)
    print("Additional Resources")
    print("=" * 60)
    print("\n- Security documentation: docs/security.md")
    print("- GitHub security best practices:")
    print("  https://docs.github.com/en/actions/security-guides")
    print("- OpenRouter security:")
    print("  https://openrouter.ai/docs/security")


if __name__ == "__main__":
    main()
