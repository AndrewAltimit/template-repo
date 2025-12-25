"""
ExpressionOrchestrator - Unified multi-modal expression coordination.

This module provides the ExpressionOrchestrator class that coordinates
expression across multiple modalities (voice, avatar, visual reactions)
with emotional coherence and memory integration.

The orchestrator:
1. Maps canonical emotions to modality-specific representations
2. Coordinates parallel expression across voice, avatar, and reactions
3. Optionally stores expression patterns to memory for learning
4. Retrieves learned preferences to inform future expressions
"""

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

from ..emotions import CanonicalEmotion, EmotionState
from ..emotions.mappings import (
    emotion_to_avatar,
    emotion_to_reaction_query,
    get_audio_tags_for_emotion,
)
from .types import (
    AudioResult,
    AvatarResult,
    ExpressionConfig,
    ExpressionResult,
    Modality,
    ReactionResult,
)

# Type aliases for MCP client functions
SynthesizeFn = Callable[..., Coroutine[Any, Any, Dict[str, Any]]]
SendAnimationFn = Callable[..., Coroutine[Any, Any, Dict[str, Any]]]
PlayAudioFn = Callable[..., Coroutine[Any, Any, Dict[str, Any]]]
SearchReactionsFn = Callable[..., Coroutine[Any, Any, Dict[str, Any]]]
StoreFn = Callable[..., Coroutine[Any, Any, Dict[str, Any]]]
SearchFn = Callable[..., Coroutine[Any, Any, Dict[str, Any]]]


@dataclass
class MCPClients:
    """
    Container for MCP client functions.

    Each field is an async callable that interfaces with the respective MCP server.
    These can be actual MCP client methods or mock functions for testing.
    """

    # ElevenLabs Speech
    synthesize_speech: Optional[SynthesizeFn] = None

    # Virtual Character
    send_animation: Optional[SendAnimationFn] = None
    play_audio: Optional[PlayAudioFn] = None

    # Reaction Search
    search_reactions: Optional[SearchReactionsFn] = None

    # AgentCore Memory
    store_facts: Optional[StoreFn] = None
    search_memories: Optional[SearchFn] = None


class ExpressionOrchestrator:
    """
    Coordinates expression across multiple modalities with emotional coherence.

    The orchestrator serves as a unified interface for expressing emotions through:
    - Voice (ElevenLabs TTS with emotion-appropriate audio tags)
    - Avatar (Virtual Character with matching expression and gesture)
    - Visual reactions (contextually appropriate reaction images)

    It also integrates with memory to:
    - Store successful expression patterns for learning
    - Retrieve preferred voices/reactions for similar contexts

    Example usage:
        ```python
        orchestrator = ExpressionOrchestrator(
            clients=MCPClients(
                synthesize_speech=elevenlabs.synthesize_stream,
                send_animation=virtual_char.send_animation,
                play_audio=virtual_char.play_audio,
                search_reactions=reaction_search.search_reactions,
                store_facts=memory.store_facts,
                search_memories=memory.search_memories,
            )
        )

        result = await orchestrator.express(
            text="Finally fixed that bug!",
            emotion=CanonicalEmotion.JOY,
            intensity=0.7,
        )
        ```
    """

    def __init__(
        self,
        clients: Optional[MCPClients] = None,
        config: Optional[ExpressionConfig] = None,
    ):
        """
        Initialize the ExpressionOrchestrator.

        Args:
            clients: MCP client functions for each modality
            config: Configuration options for expression behavior
        """
        self.clients = clients or MCPClients()
        self.config = config or ExpressionConfig()

    async def express(
        self,
        text: str,
        emotion: Union[CanonicalEmotion, EmotionState],
        intensity: Optional[float] = None,
        modalities: Optional[List[Modality]] = None,
        voice_id: Optional[str] = None,
        gesture: Optional[str] = None,
        remember: Optional[bool] = None,
        context: Optional[str] = None,
    ) -> ExpressionResult:
        """
        Express a message across multiple modalities with emotional coherence.

        This method coordinates expression across voice, avatar, and reaction
        modalities in parallel, ensuring emotional consistency.

        Args:
            text: The text to express
            emotion: The canonical emotion or emotion state to express
            intensity: Emotion intensity (0-1), defaults to config default
            modalities: Which modalities to use, defaults to config defaults
            voice_id: Override voice ID for synthesis
            gesture: Optional gesture for avatar
            remember: Whether to store the expression pattern
            context: Additional context for reaction search/memory

        Returns:
            ExpressionResult containing results from each activated modality
        """
        # Normalize emotion to CanonicalEmotion
        if isinstance(emotion, EmotionState):
            canonical_emotion = emotion.emotion
            intensity = intensity or emotion.intensity
        else:
            canonical_emotion = emotion

        # Apply defaults
        intensity = intensity if intensity is not None else self.config.default_intensity
        modalities = modalities or self.config.default_modalities
        voice_id = voice_id or self.config.default_voice_id
        remember = remember if remember is not None else self.config.remember_expressions

        # Check voice preferences from memory if available
        if self.clients.search_memories:
            preferred_voice = await self._get_preferred_voice(canonical_emotion, context)
            if preferred_voice:
                voice_id = preferred_voice

        # Build parallel tasks for each modality
        audio_result: Optional[AudioResult] = None
        avatar_result: Optional[AvatarResult] = None
        reaction_result: Optional[ReactionResult] = None

        # Collect coroutines with their target keys
        task_keys: List[str] = []
        task_coros: List[Any] = []

        if Modality.VOICE in modalities and self.clients.synthesize_speech:
            task_keys.append("audio")
            task_coros.append(
                self._synthesize_with_emotion(
                    text=text,
                    emotion=canonical_emotion,
                    intensity=intensity,
                    voice_id=voice_id,
                )
            )

        if Modality.AVATAR in modalities and self.clients.send_animation:
            task_keys.append("avatar")
            task_coros.append(
                self._set_avatar_expression(
                    emotion=canonical_emotion,
                    intensity=intensity,
                    gesture=gesture if self.config.avatar_gesture_enabled else None,
                )
            )

        if Modality.REACTION in modalities and self.clients.search_reactions:
            task_keys.append("reaction")
            task_coros.append(
                self._search_reaction(
                    emotion=canonical_emotion,
                    intensity=intensity,
                    text=text,
                    context=context,
                )
            )

        # Execute all tasks in parallel
        if task_coros:
            task_results = await asyncio.gather(*task_coros, return_exceptions=True)
            for key, result in zip(task_keys, task_results):
                if isinstance(result, Exception):
                    continue
                if key == "audio" and isinstance(result, AudioResult):
                    audio_result = result
                elif key == "avatar" and isinstance(result, AvatarResult):
                    avatar_result = result
                elif key == "reaction" and isinstance(result, ReactionResult):
                    reaction_result = result

        # If audio was generated and avatar is available, play through avatar
        if audio_result and avatar_result and self.clients.play_audio:
            await self._play_audio_through_avatar(
                audio_result=audio_result,
                emotion=canonical_emotion,
            )

        # Store expression pattern if memory is available
        remembered = False
        if remember and self.clients.store_facts:
            results_dict: Dict[str, Any] = {}
            if audio_result:
                results_dict["audio"] = audio_result
            if avatar_result:
                results_dict["avatar"] = avatar_result
            if reaction_result:
                results_dict["reaction"] = reaction_result

            remembered = await self._store_expression_pattern(
                text=text,
                emotion=canonical_emotion,
                intensity=intensity,
                context=context,
                results=results_dict,
            )

        return ExpressionResult(
            audio=audio_result,
            avatar=avatar_result,
            reaction=reaction_result,
            text=text,
            emotion_name=canonical_emotion.value,
            intensity=intensity,
            remembered=remembered,
        )

    async def express_with_arc(
        self,
        segments: List[Dict[str, Any]],
        base_intensity: float = 0.5,
    ) -> List[ExpressionResult]:
        """
        Express a sequence of segments with emotional arc tracking.

        Useful for multi-part expressions that transition between emotions.

        Args:
            segments: List of dicts with 'text' and optional 'emotion', 'intensity'
            base_intensity: Default intensity for segments without explicit intensity

        Returns:
            List of ExpressionResult for each segment
        """
        results = []
        previous_emotion = None

        for segment in segments:
            text = segment.get("text", "")
            emotion = segment.get("emotion", CanonicalEmotion.CALM)
            intensity = segment.get("intensity", base_intensity)
            context = f"arc_segment prev={previous_emotion.value if previous_emotion else 'start'}"

            result = await self.express(
                text=text,
                emotion=emotion,
                intensity=intensity,
                context=context,
            )
            results.append(result)
            previous_emotion = emotion

        return results

    async def _synthesize_with_emotion(
        self,
        text: str,
        emotion: CanonicalEmotion,
        intensity: float,
        voice_id: str,
    ) -> Optional[AudioResult]:
        """Synthesize speech with emotion-appropriate audio tags."""
        if not self.clients.synthesize_speech:
            return None

        # Get audio tags for emotion
        audio_tags = get_audio_tags_for_emotion(emotion, intensity)
        tagged_text = f"{' '.join(audio_tags)} {text}" if audio_tags else text

        try:
            result = await self.clients.synthesize_speech(
                text=tagged_text,
                voice_id=voice_id,
            )

            return AudioResult(
                local_path=result.get("local_path", ""),
                duration=result.get("duration", 0.0),
                voice_id=voice_id,
                audio_tags=audio_tags,
            )
        except Exception:
            return None

    async def _set_avatar_expression(
        self,
        emotion: CanonicalEmotion,
        intensity: float,
        gesture: Optional[str] = None,
    ) -> Optional[AvatarResult]:
        """Set avatar expression and optional gesture."""
        if not self.clients.send_animation:
            return None

        avatar_mapping = emotion_to_avatar(emotion)

        try:
            await self.clients.send_animation(
                emotion=avatar_mapping["emotion"],
                emotion_intensity=intensity,
                gesture=gesture or avatar_mapping.get("gesture"),
            )

            return AvatarResult(
                emotion=avatar_mapping["emotion"],
                emotion_intensity=intensity,
                gesture=gesture or avatar_mapping.get("gesture"),
            )
        except Exception:
            return None

    async def _search_reaction(
        self,
        emotion: CanonicalEmotion,
        intensity: float,
        text: str,
        context: Optional[str] = None,
    ) -> Optional[ReactionResult]:
        """Search for a matching reaction image."""
        if not self.clients.search_reactions:
            return None

        query = emotion_to_reaction_query(emotion, intensity, context or text)

        try:
            result = await self.clients.search_reactions(
                query=query,
                limit=self.config.reaction_limit,
            )

            if result.get("results"):
                first = result["results"][0]
                return ReactionResult(
                    reaction_id=first.get("id", ""),
                    markdown=first.get("markdown", ""),
                    url=first.get("url", ""),
                    similarity=first.get("similarity", 0.0),
                    tags=first.get("tags", []),
                )
        except Exception:
            pass

        return None

    async def _play_audio_through_avatar(
        self,
        audio_result: AudioResult,
        emotion: CanonicalEmotion,
    ) -> None:
        """Play synthesized audio through the avatar."""
        if not self.clients.play_audio:
            return

        avatar_mapping = emotion_to_avatar(emotion)

        try:
            await self.clients.play_audio(
                audio_data=audio_result.local_path,
                format=audio_result.format,
                expression_tags=[avatar_mapping["emotion"]],
            )
        except Exception:
            pass

    async def _get_preferred_voice(
        self,
        emotion: CanonicalEmotion,
        context: Optional[str],
    ) -> Optional[str]:
        """Query memory for preferred voice for this emotion/context."""
        if not self.clients.search_memories:
            return None

        query = f"voice preference for {emotion.value}"
        if context:
            query += f" in {context}"

        try:
            result = await self.clients.search_memories(
                query=query,
                namespace="personality/voice_preferences",
                top_k=1,
            )

            # Parse voice ID from memory results
            if result.get("results"):
                content = result["results"][0].get("content", "")
                # Simple extraction - look for voice ID patterns
                if "Rachel" in content:
                    return "Rachel"
                if "Adam" in content:
                    return "Adam"
                # Add more voice patterns as needed
        except Exception:
            pass

        return None

    async def _store_expression_pattern(
        self,
        text: str,
        emotion: CanonicalEmotion,
        intensity: float,
        context: Optional[str],
        results: Dict[str, Any],
    ) -> bool:
        """Store the expression pattern to memory."""
        if not self.clients.store_facts:
            return False

        facts = []

        # Build fact about the expression
        fact_parts = [f"Expressed {emotion.value} (intensity {intensity:.1f})"]
        if context:
            fact_parts.append(f"in context: {context}")
        fact_parts.append(f"for text: {text[:50]}...")

        if results.get("reaction"):
            fact_parts.append(f"with reaction: {results['reaction'].reaction_id}")

        facts.append(" ".join(fact_parts))

        try:
            await self.clients.store_facts(
                facts=facts,
                namespace="personality/expression_patterns",
            )
            return True
        except Exception:
            return False

    def get_config(self) -> Dict[str, Any]:
        """Return current configuration as dictionary."""
        return self.config.to_dict()

    def update_config(self, **kwargs) -> None:
        """Update configuration options."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
