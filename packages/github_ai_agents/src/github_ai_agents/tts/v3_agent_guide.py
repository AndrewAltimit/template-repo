"""V3 prompting guide for AI agents - provides examples without modifying agent text."""

from typing import Dict, List


class V3AgentGuide:
    """Provides v3 prompting guidance and examples for agents without modifying their text."""

    # Example templates showing proper v3 usage - Discord/Reddit/programmer style
    V3_EXAMPLES = {
        "casual_review": """
[amused] Yo, this pull request is actually pretty based.

[impressed] The way you handled that race condition?

Chef's kiss.

[sarcastic] Though I see you're still using nested loops in 2024... brave choice.

[friendly] Jokes aside, ship it after you fix that one cursed line in auth.js.
""",
        "critical_security": """
[concerned] Okay... we've got a problem.

[serious] Someone could literally yeet our entire database with this SQL injection.

[urgent] This is a certified "drop everything and fix" moment.

[supportive] Hit me up if you need help fixing this.
""",
        "enthusiastic_praise": """
[excited] Yooooo this slaps!

[laughs] Did you just solve our quadratic complexity problem with a cache? Galaxy brain move.

[amazed] Tests are green, performance is incredible... this is beautiful.

[grateful] You absolute legend. This is going straight to production.
""",
        "reddit_style": """
[casual] Not gonna lie, this is pretty clean.

[analytical] Your implementation works, but that try-catch is doing too much heavy lifting.

[amused] Also... did you really name that variable "data"? Come on, be more specific.

[encouraging] Fix those nitpicks and we're golden. Good stuff overall.
""",
        "discord_vibe": """
[friendly] Alright, looked at your pull request.

[explaining] You're treating that promise like it's synchronous... classic JavaScript moment.

[helpful] Add an await on line 42 and it should stop crying.

[casual] Also "temp" in production code? We're better than this.
""",
        "programmer_humor": """
[deadpan] I see you've discovered copy-paste driven development.

[amused] You've got a race condition, a memory leak, AND an off-by-one error... achievement unlocked?

[impressed] But somehow it works? Task failed successfully.

[friendly] Clean up the war crimes in that useEffect and we're good.
""",
        "meme_review": """
[laughs] This code is giving me "it works on my machine" energy.

[sarcastic] Ah yes, the classic "TODO: fix this later" from 2019.

[amused] That regex looks like you keyboard-smashed and called it a day.

[encouraging] But hey, at least the tests pass... wait, you wrote tests, right?

Right?
""",
    }

    # Voice-specific guidance - updated for casual tech culture
    VOICE_GUIDANCE = {
        "blondie": {
            "character": "British wit meets Discord mod",
            "best_tags": ["amused", "sarcastic", "deadpan", "laughs", "sighs"],
            "avoid_tags": ["shouting", "crying", "desperate"],
            "stability": 0.0,  # Maximum expression
            "v3_compatible": True,  # Confirmed working with v3 tags
            "example_opener": "[amused] Right, let's see what fresh hell you've created...",
        },
        "hope_conversational": {
            "character": "That one friend who's always on Discord at 3am",
            "best_tags": ["friendly", "casual", "laughs", "excited", "confused"],
            "avoid_tags": ["professional", "authoritative", "dramatic"],
            "stability": 0.0,  # Maximum natural expression
            "v3_compatible": True,  # Confirmed working with v3 tags
            "example_opener": "[casual] So... about this code...",
        },
        "old_radio": {
            "character": "Distinguished, theatrical (Captain Picard-like)",
            "best_tags": ["dramatic", "serious", "concerned", "authoritative"],
            "avoid_tags": ["giggles", "cute", "mischievous"],
            "stability": 0.0,  # Maximum theatrical expression
            "v3_compatible": True,  # Works well with dramatic v3 tags
            "example_opener": "[clears throat] [dramatic] Attention all developers...",
        },
        "peter": {
            "character": "Clear, educational, professional",
            "best_tags": ["professional", "analytical", "explaining", "thoughtful"],
            "avoid_tags": ["laughs harder", "wheezing", "crying"],
            "stability": 0.5,  # Balanced for clarity
            "v3_compatible": False,  # Less expressive, may read tags literally
            "example_opener": "[professional] Let me provide a comprehensive analysis...",
        },
    }

    # Best practices for agents
    BEST_PRACTICES = """
# V3 Prompting Best Practices for Agents

## Critical Requirements
1. **MUST USE eleven_v3 MODEL** - Tags only work with v3, not v2 models!
2. **Minimum 250 characters** - Short prompts cause inconsistencies
3. **Voice must match tags** - Can't make a whisper voice shout
4. **Line breaks between emotions** - Helps v3 understand transitions

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

## Model & Voice Compatibility

### V3-Compatible Voices (confirmed):
- **Blondie**: British wit, great with sarcasm
- **Hope**: Casual bestie, natural emotions
- **Old Radio**: Dramatic broadcast style

### May NOT work with v3 tags:
- Some professional/narrator voices may read tags literally
- Test your voice first!

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
        suggestions: List[str] = []
        text_length = len(text)
        analysis = {
            "has_tags": "[" in text and "]" in text,
            "has_line_breaks": "\n\n" in text,
            "has_emphasis": any(word.isupper() and len(word) > 2 for word in text.split()),
            "has_pauses": "..." in text,
            "length": text_length,
            "suggestions": suggestions,
        }

        if not analysis["has_tags"]:
            suggestions.append("Consider adding emotional tags like [thoughtful] or [excited]")

        if not analysis["has_line_breaks"]:
            suggestions.append("Use line breaks between emotional transitions")

        if not analysis["has_emphasis"]:
            suggestions.append("CAPITALIZE key words for emphasis")

        if not analysis["has_pauses"]:
            suggestions.append("Use '...' for natural pauses")

        if text_length < 250:
            suggestions.append("Expand to at least 250 characters for stability")

        return analysis
