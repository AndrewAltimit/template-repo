"""
Content Sanitization

Defense-in-depth system to prevent secrets from being stored in memory.
Uses three layers:
1. Regex patterns for known secret formats
2. Entropy analysis for unknown high-variance strings
3. Redaction with consistent markers
"""

from collections import Counter
import math
import re
from typing import List, Tuple

# ─────────────────────────────────────────────────────────────
# Layer 1: Regex Patterns (Known Secret Formats)
# ─────────────────────────────────────────────────────────────

BLOCKED_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # Generic secrets with common labels
    ("generic_secret", re.compile(r"(api[_-]?key|secret|password|token)\s*[:=]\s*\S+", re.IGNORECASE)),
    ("private_key", re.compile(r"-----BEGIN.*PRIVATE KEY-----")),
    # API keys with vendor-specific prefixes
    ("openai_stripe", re.compile(r"(sk-|pk_|rk_)[a-zA-Z0-9]{20,}")),
    # AWS credentials
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("aws_secret_key", re.compile(r"(?<![A-Za-z0-9/+=])[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])")),
    # GitHub tokens
    ("github_pat_new", re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,}")),
    ("github_pat_fine", re.compile(r"github_pat_[A-Za-z0-9_]{22,}")),
    # Slack tokens
    ("slack_token", re.compile(r"xox[baprs]-[0-9a-zA-Z-]+")),
    # Google OAuth tokens
    ("google_oauth", re.compile(r"ya29\.[0-9A-Za-z_-]+")),
    # Anthropic API keys
    ("anthropic_key", re.compile(r"sk-ant-[a-zA-Z0-9-]+")),
    # OpenRouter API keys
    ("openrouter_key", re.compile(r"sk-or-[a-zA-Z0-9-]+")),
    # Generic bearer tokens
    ("bearer_token", re.compile(r"Bearer\s+[A-Za-z0-9_-]{20,}")),
    # Base64 encoded credentials (common in headers)
    ("basic_auth", re.compile(r"Basic\s+[A-Za-z0-9+/=]{20,}")),
    # Connection strings with passwords
    ("connection_string", re.compile(r"(postgres|mysql|mongodb|redis)://[^:]+:[^@]+@", re.IGNORECASE)),
]


# ─────────────────────────────────────────────────────────────
# Layer 2: Entropy Analysis (Unknown High-Variance Strings)
# ─────────────────────────────────────────────────────────────


def calculate_entropy(s: str) -> float:
    """
    Calculate Shannon entropy of a string (bits per character).

    Higher entropy indicates more randomness (likely a secret).
    - English text: ~4.0-4.5 bits/char
    - Random base64: ~5.5-6.0 bits/char
    """
    if not s:
        return 0.0
    counts = Counter(s)
    length = len(s)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def is_high_entropy_blob(s: str, threshold: float = 4.5, min_length: int = 20) -> bool:
    """
    Detect high-entropy strings that might be secrets.

    Args:
        s: String to check
        threshold: Entropy threshold (4.5 bits/char catches most secrets
                   while allowing normal text)
        min_length: Minimum length to check (avoids false positives
                    on short words)

    Returns:
        True if the string appears to be a high-entropy secret
    """
    if len(s) < min_length:
        return False

    # Only check strings that look like potential secrets (base64-like or hex-like)
    if not re.match(r"^[A-Za-z0-9+/=_-]+$", s):
        return False

    return calculate_entropy(s) > threshold


# ─────────────────────────────────────────────────────────────
# Layer 3: Redaction (Replacement Strategy)
# ─────────────────────────────────────────────────────────────


def sanitize_content(content: str) -> str:
    """
    Remove potential secrets before storing.

    Applies all three layers in sequence:
    1. Known secret patterns -> [REDACTED]
    2. High-entropy blobs -> [HIGH_ENTROPY_REDACTED]

    IMPORTANT: Preserves original whitespace and formatting (newlines, indentation).
    Uses regex substitution instead of split/join to maintain structure.

    Args:
        content: Raw content to sanitize

    Returns:
        Sanitized content with secrets replaced by markers
    """
    # Layer 1: Check known patterns
    for pattern_name, pattern in BLOCKED_PATTERNS:
        content = pattern.sub("[REDACTED]", content)

    # Layer 2 + 3: Check for high-entropy blobs and redact
    # Use regex to find potential tokens while preserving whitespace
    # Pattern matches sequences of base64-like characters (potential secrets)
    def check_and_redact(match: re.Match[str]) -> str:
        """Callback to check if a matched token is high-entropy."""
        token: str = match.group(0)
        if is_high_entropy_blob(token):
            return "[HIGH_ENTROPY_REDACTED]"
        return token

    # Match potential secret tokens (alphanumeric with base64/url-safe chars)
    # This preserves all whitespace, punctuation, and structure
    content = re.sub(r"[A-Za-z0-9+/=_-]{20,}", check_and_redact, content)

    return content


def contains_secrets(content: str) -> Tuple[bool, List[str]]:
    """
    Check if content contains potential secrets without modifying it.

    Useful for validation before storage.

    Args:
        content: Content to check

    Returns:
        Tuple of (contains_secrets: bool, detected_patterns: List[str])
    """
    detected = []

    # Check known patterns
    for pattern_name, pattern in BLOCKED_PATTERNS:
        if pattern.search(content):
            detected.append(pattern_name)

    # Check for high-entropy blobs using regex (preserves structure)
    for match in re.finditer(r"[A-Za-z0-9+/=_-]{20,}", content):
        if is_high_entropy_blob(match.group(0)):
            detected.append("high_entropy_blob")
            break  # Only report once

    return len(detected) > 0, detected


def get_redaction_summary(original: str, sanitized: str) -> dict:
    """
    Generate a summary of redactions performed.

    Args:
        original: Original content
        sanitized: Sanitized content

    Returns:
        Dict with redaction statistics
    """
    redacted_count = sanitized.count("[REDACTED]")
    high_entropy_count = sanitized.count("[HIGH_ENTROPY_REDACTED]")

    return {
        "original_length": len(original),
        "sanitized_length": len(sanitized),
        "redacted_secrets": redacted_count,
        "high_entropy_redacted": high_entropy_count,
        "total_redactions": redacted_count + high_entropy_count,
        "content_modified": original != sanitized,
    }
