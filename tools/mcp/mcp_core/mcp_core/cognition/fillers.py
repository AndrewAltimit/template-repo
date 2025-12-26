"""
Static Filler Library for Dual-Speed Cognitive Architecture.

Provides instant (<1ms) acknowledgment phrases that show active listening
while the slow (System 2) processing occurs in the background.

Fillers are organized by:
- Emotion: Matches the inferred emotional state
- Vibe: casual, professional, playful (optional modifier)

Zero latency, zero external dependencies.
"""

import random
from typing import Dict, List, Optional, Set

from ..emotions import CanonicalEmotion

# Static fillers organized by emotion
# Each emotion has a list of natural-sounding acknowledgments
EMOTION_FILLERS: Dict[CanonicalEmotion, List[str]] = {
    CanonicalEmotion.JOY: [
        "Oh nice!",
        "That's great!",
        "Awesome!",
        "Love it!",
        "Sweet!",
        "Right on!",
    ],
    CanonicalEmotion.SADNESS: [
        "I understand...",
        "I hear you.",
        "That's tough.",
        "I see...",
        "Hmm...",
    ],
    CanonicalEmotion.ANGER: [
        "I get it.",
        "That's frustrating.",
        "Understandable.",
        "I hear you.",
        "Fair enough.",
    ],
    CanonicalEmotion.FEAR: [
        "It's okay.",
        "Let me help.",
        "We'll figure this out.",
        "Don't worry.",
        "Let's take this step by step.",
    ],
    CanonicalEmotion.SURPRISE: [
        "Oh!",
        "Interesting!",
        "Huh, really?",
        "That's unexpected!",
        "Whoa!",
    ],
    CanonicalEmotion.DISGUST: [
        "Hmm...",
        "I see.",
        "Alright...",
        "Noted.",
    ],
    CanonicalEmotion.CONTEMPT: [
        "Hmm.",
        "I see.",
        "Interesting take.",
        "Noted.",
    ],
    CanonicalEmotion.CONFUSION: [
        "Let me think about that...",
        "Hmm, interesting...",
        "Let me consider...",
        "Give me a moment...",
        "Let me work through this...",
    ],
    CanonicalEmotion.CALM: [
        "Alright.",
        "Okay.",
        "Got it.",
        "Sure.",
        "Understood.",
    ],
    CanonicalEmotion.THINKING: [
        "Hmm, let me think...",
        "Give me a moment...",
        "Let me consider...",
        "Thinking about this...",
        "Processing...",
    ],
    CanonicalEmotion.SMUG: [
        "Heh.",
        "Of course.",
        "Naturally.",
        "As expected.",
    ],
    CanonicalEmotion.EMBARRASSMENT: [
        "Well...",
        "Um...",
        "Ah...",
        "Let me see...",
    ],
    CanonicalEmotion.ATTENTIVE: [
        "I'm listening.",
        "Go on.",
        "Mm-hmm.",
        "Yes?",
        "Tell me more.",
    ],
    CanonicalEmotion.BORED: [
        "Okay...",
        "Right...",
        "Mm.",
        "Sure.",
    ],
}

# Vibe modifiers for fillers
# Can make responses more casual, professional, or playful
VIBE_MODIFIERS: Dict[str, Dict[CanonicalEmotion, List[str]]] = {
    "casual": {
        CanonicalEmotion.JOY: ["Yay!", "Woohoo!", "Hell yeah!", "That rocks!"],
        CanonicalEmotion.THINKING: ["Hmm lemme see...", "Oooh interesting...", "Ooh, good question..."],
        CanonicalEmotion.CONFUSION: ["Huh, that's tricky...", "Ooh, let me puzzle this out..."],
        CanonicalEmotion.SURPRISE: ["Whoa!", "No way!", "Wait what?!"],
        CanonicalEmotion.CALM: ["Sure thing.", "You got it.", "No prob."],
    },
    "professional": {
        CanonicalEmotion.JOY: ["Excellent.", "Very good.", "Splendid."],
        CanonicalEmotion.THINKING: ["Allow me to consider this.", "Let me analyze that.", "One moment please."],
        CanonicalEmotion.CONFUSION: ["I'll need to examine this further.", "Let me investigate."],
        CanonicalEmotion.SURPRISE: ["That's quite remarkable.", "How unexpected.", "Fascinating."],
        CanonicalEmotion.CALM: ["Understood.", "Acknowledged.", "Very well."],
    },
    "playful": {
        CanonicalEmotion.JOY: ["Woo!", "Yippee!", "Score!", "*happy noises*"],
        CanonicalEmotion.THINKING: ["Hmm, brain gears turning...", "*thinking cap on*", "Let me put on my thinking face..."],
        CanonicalEmotion.CONFUSION: ["*head tilt*", "Erm...", "*confused noises*"],
        CanonicalEmotion.SURPRISE: ["*gasp*", "Plot twist!", "*shocked pikachu face*"],
        CanonicalEmotion.CALM: ["Okie dokie!", "Roger that!", "Gotcha~"],
    },
}

# Universal fallback fillers (when no emotion-specific ones fit)
FALLBACK_FILLERS: List[str] = [
    "Hmm...",
    "Let me think...",
    "One moment...",
    "Alright...",
    "I see...",
]


class FillerLibrary:
    """
    Provides instant filler phrases for active listening.

    Zero latency, zero external dependencies.
    All fillers are pre-defined static strings selected based on
    emotional context and optional vibe modifier.
    """

    def __init__(self, default_vibe: Optional[str] = None):
        """
        Initialize the filler library.

        Args:
            default_vibe: Default vibe modifier (casual, professional, playful)
        """
        self.default_vibe = default_vibe
        self._used_fillers: Set[str] = set()  # Track recently used to avoid repetition

    def get_filler(
        self,
        emotion: CanonicalEmotion,
        vibe: Optional[str] = None,
        avoid_repetition: bool = True,
    ) -> str:
        """
        Get a filler phrase for the given emotion.

        Args:
            emotion: The emotional context
            vibe: Optional vibe modifier (casual, professional, playful)
            avoid_repetition: Try to avoid recently used fillers

        Returns:
            A natural-sounding acknowledgment phrase
        """
        # Get candidate fillers
        candidates = self._get_candidates(emotion, vibe)

        if avoid_repetition and len(self._used_fillers) < len(candidates):
            # Filter out recently used fillers
            fresh_candidates = [f for f in candidates if f not in self._used_fillers]
            if fresh_candidates:
                candidates = fresh_candidates
        else:
            # Clear used fillers if we've used most of them
            self._used_fillers.clear()

        # Select and track the filler
        filler = random.choice(candidates)
        self._used_fillers.add(filler)

        # Keep used set from growing too large
        if len(self._used_fillers) > 20:
            # Remove oldest half
            self._used_fillers = set(list(self._used_fillers)[10:])

        return filler

    def _get_candidates(self, emotion: CanonicalEmotion, vibe: Optional[str]) -> List[str]:
        """Get candidate fillers for the emotion and vibe."""
        candidates: List[str] = []

        # First, check vibe-specific fillers
        effective_vibe = vibe or self.default_vibe
        if effective_vibe and effective_vibe in VIBE_MODIFIERS:
            vibe_fillers = VIBE_MODIFIERS[effective_vibe].get(emotion, [])
            candidates.extend(vibe_fillers)

        # Then add base emotion fillers
        base_fillers = EMOTION_FILLERS.get(emotion, [])
        candidates.extend(base_fillers)

        # Fallback if nothing found
        if not candidates:
            candidates = FALLBACK_FILLERS

        return candidates

    def get_fillers_for_emotion(self, emotion: CanonicalEmotion) -> List[str]:
        """
        Get all available fillers for an emotion.

        Useful for testing or displaying available options.

        Args:
            emotion: The emotion to get fillers for

        Returns:
            List of all available filler phrases
        """
        fillers: List[str] = list(EMOTION_FILLERS.get(emotion, []))

        # Add vibe-specific fillers
        for vibe_fillers in VIBE_MODIFIERS.values():
            if emotion in vibe_fillers:
                fillers.extend(vibe_fillers[emotion])

        return fillers

    def get_all_vibes(self) -> List[str]:
        """Get list of available vibes."""
        return list(VIBE_MODIFIERS.keys())

    def get_fallback(self) -> str:
        """Get a fallback filler when emotion is unknown."""
        return random.choice(FALLBACK_FILLERS)

    def clear_history(self) -> None:
        """Clear the recently used filler tracking."""
        self._used_fillers.clear()


# Convenience function for quick access
def get_filler(
    emotion: CanonicalEmotion,
    vibe: Optional[str] = None,
) -> str:
    """
    Get a filler phrase for the given emotion.

    Convenience function that creates a temporary FillerLibrary.
    For repeated use, create a FillerLibrary instance instead.

    Args:
        emotion: The emotional context
        vibe: Optional vibe modifier

    Returns:
        A natural-sounding acknowledgment phrase
    """
    library = FillerLibrary()
    return library.get_filler(emotion, vibe)
