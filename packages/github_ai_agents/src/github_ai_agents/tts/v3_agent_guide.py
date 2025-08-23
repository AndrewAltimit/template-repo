"""V3 prompting guide for AI agents - provides examples without modifying agent text."""

from typing import Dict, List


class V3AgentGuide:
    """Provides v3 prompting guidance and examples for agents without modifying their text."""
    
    # Example templates showing proper v3 usage
    V3_EXAMPLES = {
        "emotional_review": """
[thoughtful] This pull request demonstrates excellent architecture and careful consideration of edge cases.

[impressed] The test coverage is particularly noteworthy... reaching 98% with meaningful assertions.

[concerned] However, there are some performance implications we should discuss.

[analytical] The nested loops in the data processing module could become problematic at scale.

[hopeful] With some optimization, this could be a fantastic addition to our codebase!
""",
        
        "critical_security": """
[serious] I need to bring an urgent matter to your attention.

[alarmed] Multiple CRITICAL security vulnerabilities have been detected in the authentication module.

[firm] These issues MUST be addressed before any merge can occur... the risk is too significant.

[professional] I recommend immediate remediation following OWASP guidelines.

[supportive] I'm here to help guide you through the fixes if needed.
""",
        
        "enthusiastic_praise": """
[excited] WOW! This is exactly what we've been looking for!

[laughs] I can't believe how elegant this solution is... seriously impressive work.

[amazed] The performance improvements are... [pause] absolutely incredible. 300% faster!

[warm] This kind of innovation is what makes our project special.

[grateful] Thank you for this outstanding contribution!
""",
        
        "conversational_feedback": """
[friendly] Hey! Thanks for submitting this PR. Let me share some thoughts...

[curious] So, I'm wondering about the architectural choice here. Could you elaborate?

[thoughtful] Hmm... I see what you're going for. It's actually quite clever.

[hesitant] I'm... well, I'm a bit concerned about the error handling though.

[encouraging] But overall? This is really solid work! Just needs a few tweaks.
""",
        
        "broadcast_style": """
[clears throat] Good evening, developers. This is your automated code review system.

[dramatic] We interrupt our regular programming for an important bulletin.

[serious] At approximately 14:32 UTC, our continuous integration pipeline detected... [pause] catastrophic failures.

[urgent] Twenty-three test suites have gone dark. The build is completely broken.

[determined] But fear not... we've identified the root cause and a path forward.
""",
    }
    
    # Voice-specific guidance
    VOICE_GUIDANCE = {
        "blondie": {
            "character": "British, warm, conversational",
            "best_tags": ["thoughtful", "curious", "warm", "laughs", "sighs"],
            "avoid_tags": ["shouting", "crying", "desperate"],
            "stability": 0.0,  # Maximum expression
            "example_opener": "[warm] Let me review this pull request for you...",
        },
        "hope_conversational": {
            "character": "Natural with imperfections (mmms, ahhs, chuckles)",
            "best_tags": ["friendly", "curious", "laughs", "excited", "hesitant"],
            "avoid_tags": ["professional", "authoritative", "dramatic"],
            "stability": 0.0,  # Maximum natural expression
            "example_opener": "[friendly] Hey! So... um, I've been looking at your code...",
        },
        "old_radio": {
            "character": "Distinguished, theatrical (Captain Picard-like)",
            "best_tags": ["dramatic", "serious", "concerned", "authoritative"],
            "avoid_tags": ["giggles", "cute", "mischievous"],
            "stability": 0.0,  # Maximum theatrical expression
            "example_opener": "[clears throat] [dramatic] Attention all developers...",
        },
        "peter": {
            "character": "Clear, educational, professional",
            "best_tags": ["professional", "analytical", "explaining", "thoughtful"],
            "avoid_tags": ["laughs harder", "wheezing", "crying"],
            "stability": 0.5,  # Balanced for clarity
            "example_opener": "[professional] Let me provide a comprehensive analysis...",
        },
    }
    
    # Best practices for agents
    BEST_PRACTICES = """
# V3 Prompting Best Practices for Agents

## Critical Requirements
1. **Minimum 250 characters** - Short prompts cause inconsistencies
2. **Voice must match tags** - Can't make a whisper voice shout
3. **Line breaks between emotions** - Helps v3 understand transitions

## Punctuation Power
- Use "..." for natural pauses and weight
- CAPITALIZE words for emphasis (CRITICAL, MUST, NEVER)
- Standard punctuation provides rhythm

## Emotional Structure
- Start each emotional section with a tag: [thoughtful], [concerned], [happy]
- Separate different emotions with line breaks
- Keep similar emotions grouped together

## Tag Usage
- Voice-related: [laughs], [sighs], [whispers], [clears throat]
- Emotions: [excited], [concerned], [curious], [thoughtful]
- Delivery: [pause], [hesitant], [firmly], [warmly]
- Special: [strong French accent], [singing]

## Stability Settings
- 0.0-0.3: Creative (maximum expression, some hallucinations)
- 0.3-0.6: Natural (balanced, closest to original voice)
- 0.6-0.9: Robust (stable but less responsive to tags)

## Examples of Good Prompting

### Short Review (BAD - under 250 chars):
"The code looks good. Fix the tests."

### Properly Formatted Review (GOOD):
"[thoughtful] I've reviewed your pull request and the code structure looks excellent.

[analytical] The implementation follows our design patterns well... particularly the error handling.

[concerned] However, the failing tests need attention before we can proceed.

[encouraging] Once those are fixed, this will be ready to merge!"
"""
    
    @classmethod
    def get_voice_guidance(cls, voice_name: str) -> Dict:
        """Get guidance for a specific voice without modifying agent text.
        
        Args:
            voice_name: Name of the voice
            
        Returns:
            Guidance dictionary for the voice
        """
        return cls.VOICE_GUIDANCE.get(voice_name, cls.VOICE_GUIDANCE["blondie"])
    
    @classmethod
    def get_example_for_context(cls, context: str) -> str:
        """Get an example for a specific context.
        
        Args:
            context: Type of review context
            
        Returns:
            Example text showing proper v3 usage
        """
        context_map = {
            "critical": "critical_security",
            "positive": "enthusiastic_praise",
            "normal": "emotional_review",
            "casual": "conversational_feedback",
            "dramatic": "broadcast_style",
        }
        
        example_key = context_map.get(context, "emotional_review")
        return cls.V3_EXAMPLES.get(example_key, cls.V3_EXAMPLES["emotional_review"])
    
    @classmethod
    def suggest_tags_for_sentiment(cls, sentiment: str) -> List[str]:
        """Suggest appropriate tags for a sentiment without modifying text.
        
        Args:
            sentiment: The sentiment to express
            
        Returns:
            List of suggested tags
        """
        sentiment_tags = {
            "positive": ["excited", "happy", "impressed", "grateful", "warm"],
            "negative": ["concerned", "disappointed", "frustrated", "serious"],
            "critical": ["urgent", "alarmed", "firm", "serious", "concerned"],
            "thoughtful": ["analytical", "curious", "thoughtful", "considering"],
            "casual": ["friendly", "relaxed", "conversational", "curious"],
        }
        
        return sentiment_tags.get(sentiment, ["professional", "thoughtful"])
    
    @classmethod
    def validate_prompt_length(cls, text: str) -> Dict:
        """Check if prompt meets v3 requirements without modifying it.
        
        Args:
            text: The prompt text
            
        Returns:
            Validation result with suggestions
        """
        length = len(text)
        
        if length < 250:
            return {
                "valid": False,
                "length": length,
                "message": "Text is too short for v3 stability. Consider expanding your review.",
                "suggestion": "Add more detail, context, or use multiple emotional sections.",
            }
        else:
            return {
                "valid": True,
                "length": length,
                "message": "Text length is good for v3.",
            }
    
    @classmethod
    def analyze_prompt_quality(cls, text: str) -> Dict:
        """Analyze prompt quality for v3 without modifying it.
        
        Args:
            text: The prompt to analyze
            
        Returns:
            Analysis with suggestions
        """
        analysis = {
            "has_tags": "[" in text and "]" in text,
            "has_line_breaks": "\n\n" in text,
            "has_emphasis": any(word.isupper() and len(word) > 2 for word in text.split()),
            "has_pauses": "..." in text,
            "length": len(text),
            "suggestions": [],
        }
        
        if not analysis["has_tags"]:
            analysis["suggestions"].append("Consider adding emotional tags like [thoughtful] or [excited]")
        
        if not analysis["has_line_breaks"]:
            analysis["suggestions"].append("Use line breaks between emotional transitions")
        
        if not analysis["has_emphasis"]:
            analysis["suggestions"].append("CAPITALIZE key words for emphasis")
        
        if not analysis["has_pauses"]:
            analysis["suggestions"].append("Use '...' for natural pauses")
        
        if analysis["length"] < 250:
            analysis["suggestions"].append("Expand to at least 250 characters for stability")
        
        return analysis