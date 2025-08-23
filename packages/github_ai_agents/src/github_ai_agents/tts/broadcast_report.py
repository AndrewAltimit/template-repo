"""Broadcast report generator for dramatic PR reviews."""

import re
from typing import Dict, List, Optional, Tuple

from .voice_catalog import VOICE_CATALOG, get_voice_settings_for_emotion


class BroadcastReportGenerator:
    """Generate dramatic broadcast-style reports for critical PRs."""

    # Broadcast templates for different scenarios
    BROADCAST_TEMPLATES = {
        "security_critical": """
[{agent_voice}] {initial_assessment}

[{broadcast_voice}] [clears throat] We interrupt our regular programming for an urgent security bulletin.
This is the Continental Code Review System.

[{broadcast_voice}] [serious] Good evening, developers. This is the automated review system
reporting from repository headquarters. At approximately {time}, our security scanners
detected critical vulnerabilities in Pull Request #{pr_number}.

[{broadcast_voice}] [concerned] The vulnerabilities appear to be {vulnerability_type},
affecting approximately {impact_scope}. [short pause] This is not a drill.
[nervous] The security rating has dropped to... [pause] critical.
""",
        "build_failure": """
[{agent_voice}] {initial_assessment}

[{broadcast_voice}] [static] This is an emergency broadcast from the Continuous Integration Network.

[{broadcast_voice}] [urgent] Ladies and gentlemen of the development team, we have a situation.
At {time}, the build pipeline reported catastrophic failures across {failure_count} test suites.

[{broadcast_voice}] [crackling connection] The failures are cascading through the system.
[pause] Module after module going dark. [worried] We've never seen anything quite like this before.
""",
        "performance_crisis": """
[{agent_voice}] {initial_assessment}

[{broadcast_voice}] We interrupt this code review for breaking news from the Performance Monitoring Division.

[{broadcast_voice}] [authoritative] This is an automated alert. Benchmark results show
performance degradation of {degradation_percent} percent. [pause] I repeat,
{degradation_percent} percent slower than baseline.

[{broadcast_voice}] [concerned] Response times are climbing. Memory usage is... [shocked] extraordinary.
The application is struggling to maintain acceptable performance thresholds.
""",
        "major_achievement": """
[{agent_voice}] {initial_assessment}

[{broadcast_voice}] [fanfare] We interrupt this session for a special achievement bulletin from Code Excellence Broadcasting.

[{broadcast_voice}] [excited] Remarkable news from the repository! Pull Request #{pr_number}
has achieved something extraordinary. [pause] Perfect scores across all metrics.

[{broadcast_voice}] [impressed] Test coverage: one hundred percent. Code quality: exemplary.
Performance improvements: [amazed] beyond our wildest calculations.
This is... this is history in the making!
""",
    }

    @staticmethod
    def should_use_broadcast(review_text: str, pr_metadata: dict) -> bool:
        """Determine if a review warrants broadcast treatment.

        Args:
            review_text: The review content
            pr_metadata: PR metadata including labels, CI status

        Returns:
            Whether to use broadcast format
        """
        # Keywords that trigger broadcast mode
        critical_keywords = [
            "critical",
            "emergency",
            "urgent",
            "breaking",
            "catastrophic",
            "severe",
            "blocker",
            "security",
            "vulnerability",
            "exploit",
            "breach",
        ]

        positive_keywords = [
            "perfect",
            "exceptional",
            "extraordinary",
            "remarkable",
            "historic",
            "unprecedented",
            "breakthrough",
        ]

        review_lower = review_text.lower()

        # Check for critical issues
        has_critical = any(keyword in review_lower for keyword in critical_keywords)

        # Check for exceptional achievements
        has_exceptional = any(keyword in review_lower for keyword in positive_keywords)

        # Check PR metadata
        has_security_label = any(
            label.get("name", "").lower() in ["security", "critical", "urgent"]
            for label in pr_metadata.get("labels", [])
        )

        ci_failed = pr_metadata.get("ci_status") == "failed"

        return has_critical or has_exceptional or has_security_label or ci_failed

    @staticmethod
    def analyze_review_type(review_text: str) -> str:
        """Determine the type of broadcast report needed.

        Args:
            review_text: The review content

        Returns:
            Broadcast template type
        """
        review_lower = review_text.lower()

        if any(word in review_lower for word in ["security", "vulnerability", "exploit"]):
            return "security_critical"
        elif any(word in review_lower for word in ["build fail", "ci fail", "test fail"]):
            return "build_failure"
        elif any(word in review_lower for word in ["performance", "slow", "memory", "latency"]):
            return "performance_crisis"
        elif any(word in review_lower for word in ["perfect", "exceptional", "100%"]):
            return "major_achievement"
        else:
            return "security_critical"  # Default to critical

    @staticmethod
    def extract_key_points(review_text: str) -> dict:
        """Extract key information from review for broadcast.

        Args:
            review_text: The review content

        Returns:
            Dictionary of extracted information
        """
        # Extract numbers and percentages
        numbers = re.findall(r"\d+", review_text)
        percentages = re.findall(r"(\d+)%", review_text)

        # Extract first important sentence
        sentences = re.split(r"[.!?]", review_text)
        initial_assessment = sentences[0].strip() if sentences else "Code review complete"

        # Count issues mentioned
        issue_keywords = ["error", "fail", "issue", "problem", "bug", "vulnerability"]
        issue_count = sum(1 for keyword in issue_keywords if keyword in review_text.lower())

        return {
            "initial_assessment": initial_assessment,
            "failure_count": numbers[0] if numbers else "multiple",
            "degradation_percent": percentages[0] if percentages else "significant",
            "impact_scope": f"{issue_count} critical areas" if issue_count else "core functionality",
            "vulnerability_type": "high-severity" if "high" in review_text.lower() else "critical",
        }

    @classmethod
    def generate_broadcast_script(
        cls, review_text: str, agent_name: str, pr_number: int, pr_metadata: Optional[Dict] = None
    ) -> Tuple[str, List[str]]:
        """Generate a broadcast-style script for dramatic reviews.

        Args:
            review_text: Original review text
            agent_name: Name of the reviewing agent
            pr_number: PR number
            pr_metadata: Additional PR metadata

        Returns:
            Tuple of (formatted_script, voice_sequence)
        """
        pr_metadata = pr_metadata or {}

        # Check if broadcast is warranted
        if not cls.should_use_broadcast(review_text, pr_metadata):
            return review_text, [agent_name]

        # Determine broadcast type
        broadcast_type = cls.analyze_review_type(review_text)

        # Extract key information
        info = cls.extract_key_points(review_text)
        info.update(
            {
                "pr_number": pr_number,
                "time": "moments ago",
                "agent_voice": agent_name,
                "broadcast_voice": "old_radio",
            }
        )

        # Get the template
        template = cls.BROADCAST_TEMPLATES.get(broadcast_type, cls.BROADCAST_TEMPLATES["security_critical"])

        # Format the script
        script = template.format(**info)

        # Extract voice sequence (agent_voice for first line, then broadcast_voice)
        voice_sequence = [agent_name, "old_radio", "old_radio"]

        return script, voice_sequence

    @classmethod
    def format_for_tts(cls, script: str, voice_sequence: List[str]) -> List[dict]:
        """Format broadcast script for TTS synthesis.

        Args:
            script: The broadcast script
            voice_sequence: Sequence of voices to use

        Returns:
            List of segments with voice assignments
        """
        # Split script by voice markers
        segments = []

        # Find all voice-marked sections
        lines = script.strip().split("\n")
        current_voice_idx = 0

        for line in lines:
            if not line.strip():
                continue

            # Extract voice marker if present
            voice_match = re.match(r"^\[([^\]]+)\]", line)
            if voice_match:
                voice_key = voice_match.group(1)
                # Remove voice marker from line
                line_text = re.sub(r"^\[[^\]]+\]\s*", "", line)

                # Determine which voice to use
                if voice_key in ["agent_voice", "broadcast_voice"]:
                    if "broadcast_voice" in voice_key:
                        voice = "old_radio"
                    else:
                        voice = voice_sequence[0] if voice_sequence else "blondie"
                else:
                    voice = voice_sequence[min(current_voice_idx, len(voice_sequence) - 1)]

                current_voice_idx += 1
            else:
                # No voice marker, use current voice in sequence
                line_text = line
                voice = voice_sequence[min(current_voice_idx, len(voice_sequence) - 1)]

            if line_text.strip():
                # Get voice profile and settings
                voice_profile = VOICE_CATALOG.get(voice, VOICE_CATALOG["old_radio"])
                settings = get_voice_settings_for_emotion(voice_profile, emotion_intensity=0.7)

                segments.append(
                    {
                        "text": line_text.strip(),
                        "voice": voice,
                        "voice_id": voice_profile.voice_id,
                        "settings": settings,
                    }
                )

        return segments


def create_broadcast_review(
    review_text: str, agent_name: str, pr_number: int, pr_metadata: Optional[Dict] = None
) -> str:
    """Create a dramatic broadcast-style review.

    Args:
        review_text: Original review
        agent_name: Reviewing agent
        pr_number: PR number
        pr_metadata: PR metadata

    Returns:
        Formatted broadcast script
    """
    generator = BroadcastReportGenerator()
    script, voices = generator.generate_broadcast_script(review_text, agent_name, pr_number, pr_metadata)
    return script
