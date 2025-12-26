"""
Personality Memory Management for Expressive AI Agent System.

Provides structured access to personality-related memory storage:
- Voice preferences
- Expression patterns
- Reaction history
- Avatar settings

Works with AgentCore Memory via MCP calls or direct API.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Protocol

from ..emotions import CanonicalEmotion

# =============================================================================
# Namespace Constants (matching mcp_agentcore_memory/namespaces.py)
# =============================================================================

NAMESPACE_VOICE_PREFERENCES = "personality/voice_preferences"
NAMESPACE_EXPRESSION_PATTERNS = "personality/expression_patterns"
NAMESPACE_REACTION_HISTORY = "personality/reaction_history"
NAMESPACE_AVATAR_SETTINGS = "personality/avatar_settings"
NAMESPACE_CONVERSATION_TONE = "context/conversation_tone"
NAMESPACE_INTERACTION_HISTORY = "context/interaction_history"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class VoicePreference:
    """
    Stored preference for a voice configuration.

    Attributes:
        voice_id: ElevenLabs voice ID
        use_case: Context where this voice works well
        preset: Voice settings preset name
        effectiveness: How well this worked (0-1)
        notes: Additional observations
        timestamp: When this preference was recorded
    """

    voice_id: str
    use_case: str
    preset: Optional[str] = None
    effectiveness: float = 0.5
    notes: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_fact(self) -> str:
        """Convert to storable fact string."""
        parts = [f"Voice '{self.voice_id}'"]

        if self.preset:
            parts.append(f"with preset '{self.preset}'")

        parts.append(f"works {'well' if self.effectiveness > 0.6 else 'okay'}")
        parts.append(f"for {self.use_case}")

        if self.notes:
            parts.append(f"- {self.notes}")

        return " ".join(parts)

    @classmethod
    def from_memory(cls, content: str, metadata: Dict) -> "VoicePreference":
        """Parse from memory search result."""
        return cls(
            voice_id=metadata.get("voice_id", ""),
            use_case=metadata.get("use_case", ""),
            preset=metadata.get("preset"),
            effectiveness=metadata.get("effectiveness", 0.5),
            notes=content,
            timestamp=datetime.fromisoformat(metadata.get("timestamp", datetime.utcnow().isoformat())),
        )


@dataclass
class ExpressionPattern:
    """
    Learned pattern for expressing emotions.

    Attributes:
        emotion: The canonical emotion
        intensity: Typical intensity for this pattern
        audio_tags: ElevenLabs audio tags that work well
        avatar_emotion: Virtual Character emotion to use
        avatar_gesture: Optional gesture to pair with emotion
        context: When this pattern applies
        effectiveness: How well this worked (0-1)
    """

    emotion: CanonicalEmotion
    intensity: float = 0.5
    audio_tags: List[str] = field(default_factory=list)
    avatar_emotion: str = "neutral"
    avatar_gesture: Optional[str] = None
    context: str = ""
    effectiveness: float = 0.5

    def to_fact(self) -> str:
        """Convert to storable fact string."""
        parts = [f"For {self.emotion.value}"]

        if self.context:
            parts.append(f"in {self.context}")

        if self.audio_tags:
            parts.append(f"use audio tags {', '.join(self.audio_tags)}")

        parts.append(f"with avatar emotion '{self.avatar_emotion}'")

        if self.avatar_gesture:
            parts.append(f"and gesture '{self.avatar_gesture}'")

        if self.effectiveness > 0.7:
            parts.append("- very effective")
        elif self.effectiveness > 0.5:
            parts.append("- moderately effective")

        return " ".join(parts)


@dataclass
class ReactionUsage:
    """
    Record of a reaction image usage.

    Attributes:
        reaction_id: Reaction image identifier
        context: Where/when this reaction was used
        emotion: The emotion being expressed
        user_response: How the user responded (positive/negative/neutral)
        effectiveness: How appropriate the reaction was (0-1)
    """

    reaction_id: str
    context: str
    emotion: Optional[CanonicalEmotion] = None
    user_response: str = "neutral"
    effectiveness: float = 0.5

    def to_fact(self) -> str:
        """Convert to storable fact string."""
        parts = [f"Reaction '{self.reaction_id}'"]

        if self.emotion:
            parts.append(f"for {self.emotion.value}")

        parts.append(f"in {self.context}")

        if self.user_response == "positive":
            parts.append("- user responded positively")
        elif self.user_response == "negative":
            parts.append("- user responded negatively")

        return " ".join(parts)


# =============================================================================
# Memory Access Protocol
# =============================================================================


class MemoryProvider(Protocol):
    """Protocol for memory storage/retrieval."""

    async def store_facts(self, facts: List[str], namespace: str, source: Optional[str] = None) -> Dict[str, Any]:
        """Store facts to memory."""
        ...

    async def search_memories(self, query: str, namespace: str, top_k: int = 5) -> Dict[str, Any]:
        """Search memories by semantic query."""
        ...


# =============================================================================
# Personality Memory Manager
# =============================================================================


class PersonalityMemory:
    """
    High-level interface for personality memory operations.

    Provides structured methods for storing and retrieving:
    - Voice preferences
    - Expression patterns
    - Reaction history
    - Avatar settings

    Can work with MCP client or direct function calls.
    """

    def __init__(
        self,
        store_facts_fn: Optional[Callable] = None,
        search_memories_fn: Optional[Callable] = None,
        mcp_client: Optional[Any] = None,
    ):
        """
        Initialize PersonalityMemory.

        Args:
            store_facts_fn: Async function to store facts
            search_memories_fn: Async function to search memories
            mcp_client: Optional MCP client (uses its methods if provided)
        """
        self._store_facts = store_facts_fn
        self._search_memories = search_memories_fn
        self._mcp_client = mcp_client

    async def _do_store_facts(self, facts: List[str], namespace: str, source: str = "personality_memory") -> Dict[str, Any]:
        """Internal method to store facts."""
        if self._store_facts:
            result = await self._store_facts(facts=facts, namespace=namespace, source=source)
            return dict(result) if result else {}
        elif self._mcp_client:
            result = await self._mcp_client.store_facts(facts=facts, namespace=namespace, source=source)
            return dict(result) if result else {}
        else:
            raise RuntimeError("No memory provider configured")

    async def _do_search(self, query: str, namespace: str, top_k: int = 5) -> Dict[str, Any]:
        """Internal method to search memories."""
        if self._search_memories:
            result = await self._search_memories(query=query, namespace=namespace, top_k=top_k)
            return dict(result) if result else {}
        elif self._mcp_client:
            result = await self._mcp_client.search_memories(query=query, namespace=namespace, top_k=top_k)
            return dict(result) if result else {}
        else:
            raise RuntimeError("No memory provider configured")

    # ─────────────────────────────────────────────────────────────
    # Voice Preferences
    # ─────────────────────────────────────────────────────────────

    async def store_voice_preference(
        self,
        voice_id: str,
        use_case: str,
        preset: Optional[str] = None,
        effectiveness: float = 0.5,
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Store a voice preference.

        Args:
            voice_id: ElevenLabs voice ID
            use_case: Context (e.g., "code_review", "narration")
            preset: Voice settings preset name
            effectiveness: How well this worked (0-1)
            notes: Additional observations

        Returns:
            Result from memory storage
        """
        pref = VoicePreference(
            voice_id=voice_id,
            use_case=use_case,
            preset=preset,
            effectiveness=effectiveness,
            notes=notes,
        )

        return await self._do_store_facts(
            facts=[pref.to_fact()],
            namespace=NAMESPACE_VOICE_PREFERENCES,
            source="personality_memory",
        )

    async def get_voice_preferences(self, use_case: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Get voice preferences for a use case.

        Args:
            use_case: Context to search for
            top_k: Number of results

        Returns:
            List of matching preferences
        """
        result = await self._do_search(
            query=f"voice preferences for {use_case}",
            namespace=NAMESPACE_VOICE_PREFERENCES,
            top_k=top_k,
        )

        return list(result.get("results", []))

    # ─────────────────────────────────────────────────────────────
    # Expression Patterns
    # ─────────────────────────────────────────────────────────────

    async def store_expression_pattern(
        self,
        emotion: CanonicalEmotion,
        intensity: float = 0.5,
        audio_tags: Optional[List[str]] = None,
        avatar_emotion: str = "neutral",
        avatar_gesture: Optional[str] = None,
        context: str = "",
        effectiveness: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Store an expression pattern.

        Args:
            emotion: The canonical emotion
            intensity: Typical intensity
            audio_tags: ElevenLabs audio tags that work
            avatar_emotion: Virtual Character emotion
            avatar_gesture: Optional gesture
            context: When this pattern applies
            effectiveness: How well this worked

        Returns:
            Result from memory storage
        """
        pattern = ExpressionPattern(
            emotion=emotion,
            intensity=intensity,
            audio_tags=audio_tags or [],
            avatar_emotion=avatar_emotion,
            avatar_gesture=avatar_gesture,
            context=context,
            effectiveness=effectiveness,
        )

        return await self._do_store_facts(
            facts=[pattern.to_fact()],
            namespace=NAMESPACE_EXPRESSION_PATTERNS,
            source="personality_memory",
        )

    async def get_expression_patterns(
        self, emotion: CanonicalEmotion, context: str = "", top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get expression patterns for an emotion.

        Args:
            emotion: The emotion to search for
            context: Optional context filter
            top_k: Number of results

        Returns:
            List of matching patterns
        """
        query = f"expression pattern for {emotion.value}"
        if context:
            query += f" in {context}"

        result = await self._do_search(
            query=query,
            namespace=NAMESPACE_EXPRESSION_PATTERNS,
            top_k=top_k,
        )

        return list(result.get("results", []))

    # ─────────────────────────────────────────────────────────────
    # Reaction History
    # ─────────────────────────────────────────────────────────────

    async def store_reaction_usage(
        self,
        reaction_id: str,
        context: str,
        emotion: Optional[CanonicalEmotion] = None,
        user_response: str = "neutral",
        effectiveness: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Store a reaction usage record.

        Args:
            reaction_id: Reaction image identifier
            context: Where this was used
            emotion: The emotion being expressed
            user_response: How user responded
            effectiveness: How appropriate it was

        Returns:
            Result from memory storage
        """
        usage = ReactionUsage(
            reaction_id=reaction_id,
            context=context,
            emotion=emotion,
            user_response=user_response,
            effectiveness=effectiveness,
        )

        return await self._do_store_facts(
            facts=[usage.to_fact()],
            namespace=NAMESPACE_REACTION_HISTORY,
            source="personality_memory",
        )

    async def get_reaction_history(
        self,
        context: str = "",
        emotion: Optional[CanonicalEmotion] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get reaction usage history.

        Args:
            context: Context to search for
            emotion: Optional emotion filter
            top_k: Number of results

        Returns:
            List of matching reaction records
        """
        query_parts = ["reaction"]

        if emotion:
            query_parts.append(f"for {emotion.value}")

        if context:
            query_parts.append(f"in {context}")

        query = " ".join(query_parts)

        result = await self._do_search(
            query=query,
            namespace=NAMESPACE_REACTION_HISTORY,
            top_k=top_k,
        )

        return list(result.get("results", []))

    # ─────────────────────────────────────────────────────────────
    # Avatar Settings
    # ─────────────────────────────────────────────────────────────

    async def store_avatar_setting(
        self,
        setting_type: str,
        value: str,
        context: str = "",
        effectiveness: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Store an avatar setting preference.

        Args:
            setting_type: Type of setting (e.g., "gesture", "intensity")
            value: The setting value
            context: When this setting applies
            effectiveness: How well this worked

        Returns:
            Result from memory storage
        """
        fact = f"Avatar {setting_type} '{value}'"
        if context:
            fact += f" for {context}"
        if effectiveness > 0.7:
            fact += " works very well"
        elif effectiveness > 0.5:
            fact += " works okay"

        return await self._do_store_facts(
            facts=[fact],
            namespace=NAMESPACE_AVATAR_SETTINGS,
            source="personality_memory",
        )

    async def get_avatar_settings(self, setting_type: str = "", context: str = "", top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Get avatar setting preferences.

        Args:
            setting_type: Type of setting to search for
            context: Optional context filter
            top_k: Number of results

        Returns:
            List of matching settings
        """
        query_parts = ["avatar"]

        if setting_type:
            query_parts.append(setting_type)

        if context:
            query_parts.append(f"for {context}")

        query = " ".join(query_parts)

        result = await self._do_search(
            query=query,
            namespace=NAMESPACE_AVATAR_SETTINGS,
            top_k=top_k,
        )

        return list(result.get("results", []))

    # ─────────────────────────────────────────────────────────────
    # Conversation Context
    # ─────────────────────────────────────────────────────────────

    async def store_emotional_arc(
        self,
        start_emotion: CanonicalEmotion,
        end_emotion: CanonicalEmotion,
        context: str,
        session_id: str = "",
    ) -> Dict[str, Any]:
        """
        Store an emotional arc from a conversation.

        Args:
            start_emotion: Emotion at conversation start
            end_emotion: Emotion at conversation end
            context: What happened in the conversation
            session_id: Optional session identifier

        Returns:
            Result from memory storage
        """
        fact = f"Conversation went from {start_emotion.value} to {end_emotion.value}"
        if context:
            fact += f" - {context}"

        return await self._do_store_facts(
            facts=[fact],
            namespace=NAMESPACE_CONVERSATION_TONE,
            source=session_id or "personality_memory",
        )

    async def store_interaction_pattern(
        self,
        pattern: str,
        outcome: str,
        effectiveness: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Store an interaction pattern.

        Args:
            pattern: Description of the interaction pattern
            outcome: What happened as a result
            effectiveness: How well it worked

        Returns:
            Result from memory storage
        """
        fact = f"Pattern: {pattern} -> {outcome}"
        if effectiveness > 0.7:
            fact += " (effective)"
        elif effectiveness < 0.3:
            fact += " (avoid)"

        return await self._do_store_facts(
            facts=[fact],
            namespace=NAMESPACE_INTERACTION_HISTORY,
            source="personality_memory",
        )
