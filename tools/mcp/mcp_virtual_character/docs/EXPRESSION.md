# Expression & Personality Modules

> **Status**: This documentation describes planned/future features. The ExpressionOrchestrator and PersonalityMemory modules have not yet been implemented. Current emotion support is available in `mcp_virtual_character/models/canonical.py`.

These modules will enable coordinated multi-modal expression and persistent personality learning for expressive AI agents.

## Overview

| Module | Purpose |
|--------|---------|
| **expression** | Orchestrates voice, avatar, and reaction modalities in parallel |
| **personality** | Stores and retrieves expression preferences via AgentCore Memory |

## Expression Orchestrator

The `ExpressionOrchestrator` coordinates expression across multiple modalities with emotional coherence.

### Basic Usage

```python
from mcp_core.expression import ExpressionOrchestrator, MCPClients, Modality
from mcp_core.emotions import CanonicalEmotion

# Configure with MCP client functions
clients = MCPClients(
    synthesize_speech=elevenlabs_client.synthesize_stream,
    send_animation=virtual_char_client.send_animation,
    play_audio=virtual_char_client.play_audio,
    search_reactions=reaction_search_client.search_reactions,
    store_facts=memory_client.store_facts,
    search_memories=memory_client.search_memories,
)

orchestrator = ExpressionOrchestrator(clients=clients)

# Express with emotional coherence across all modalities
result = await orchestrator.express(
    text="Finally fixed that race condition!",
    emotion=CanonicalEmotion.JOY,
    intensity=0.8,
)

# Result contains outputs from each modality
print(result.audio.local_path)      # "/tmp/audio/speech.mp3"
print(result.avatar.emotion)        # "happy"
print(result.reaction.markdown)     # "![Reaction](url)"
print(result.remembered)            # True (stored to memory)
```

### Selective Modalities

```python
# Voice only
result = await orchestrator.express(
    text="Processing your request...",
    emotion=CanonicalEmotion.THINKING,
    modalities=[Modality.VOICE],
)

# Avatar and reaction only (no audio)
result = await orchestrator.express(
    text="Hmm, interesting approach",
    emotion=CanonicalEmotion.ATTENTIVE,
    modalities=[Modality.AVATAR, Modality.REACTION],
)
```

### Custom Configuration

```python
from mcp_core.expression import ExpressionConfig

config = ExpressionConfig(
    default_voice_id="Adam",
    default_intensity=0.6,
    default_modalities=[Modality.VOICE, Modality.AVATAR],
    remember_expressions=True,
    avatar_gesture_enabled=True,
    reaction_limit=1,
)

orchestrator = ExpressionOrchestrator(clients=clients, config=config)
```

### Emotional Arcs

Express sequences with emotional progression:

```python
segments = [
    {"text": "Let me look at this...", "emotion": CanonicalEmotion.THINKING},
    {"text": "Ah, I see the issue!", "emotion": CanonicalEmotion.SURPRISE, "intensity": 0.6},
    {"text": "Fixed it!", "emotion": CanonicalEmotion.JOY, "intensity": 0.8},
]

results = await orchestrator.express_with_arc(segments)
# Each segment expressed with context of the previous emotion
```

### What Happens During Expression

1. **Voice**: Text is tagged with emotion-appropriate audio tags and synthesized
2. **Avatar**: Expression and optional gesture are set via Virtual Character
3. **Reaction**: Semantic search finds matching reaction image
4. **Audio Playback**: If both voice and avatar succeed, audio plays through avatar
5. **Memory**: Expression pattern stored for future preference learning

## Personality Memory

The `PersonalityMemory` class provides structured storage for expression preferences using AgentCore Memory.

### Setup

```python
from mcp_core.personality import PersonalityMemory

# Option 1: With direct function references
memory = PersonalityMemory(
    store_facts_fn=agentcore_client.store_facts,
    search_memories_fn=agentcore_client.search_memories,
)

# Option 2: With MCP client
memory = PersonalityMemory(mcp_client=agentcore_client)
```

### Voice Preferences

Learn which voices work well for different contexts:

```python
# Store a successful voice choice
await memory.store_voice_preference(
    voice_id="Rachel",
    use_case="code_review",
    preset="github_review",
    effectiveness=0.9,
    notes="Professional yet approachable",
)

# Retrieve preferences for a use case
preferences = await memory.get_voice_preferences("code_review")
# Returns list of matching preference records
```

### Expression Patterns

Track successful emotion expressions:

```python
from mcp_core.emotions import CanonicalEmotion

# Store a pattern that worked well
await memory.store_expression_pattern(
    emotion=CanonicalEmotion.JOY,
    intensity=0.7,
    audio_tags=["[laughs]", "[excited]"],
    avatar_emotion="happy",
    avatar_gesture="cheer",
    context="bug fix celebration",
    effectiveness=0.85,
)

# Find patterns for similar contexts
patterns = await memory.get_expression_patterns(
    emotion=CanonicalEmotion.JOY,
    context="celebrating",
)
```

### Reaction History

Remember which reactions resonate with users:

```python
# Store reaction usage
await memory.store_reaction_usage(
    reaction_id="nervous_sweat",
    context="relief after debugging",
    emotion=CanonicalEmotion.JOY,
    user_response="positive",
    effectiveness=0.9,
)

# Query reaction history
history = await memory.get_reaction_history(
    context="debugging",
    emotion=CanonicalEmotion.JOY,
)
```

### Avatar Settings

Track preferred avatar configurations:

```python
await memory.store_avatar_setting(
    setting_type="gesture",
    value="thinking",
    context="code analysis",
    effectiveness=0.8,
)

settings = await memory.get_avatar_settings(
    setting_type="gesture",
    context="reviewing code",
)
```

### Emotional Arcs

Track conversation emotional progressions:

```python
await memory.store_emotional_arc(
    start_emotion=CanonicalEmotion.CONFUSION,
    end_emotion=CanonicalEmotion.JOY,
    context="Debugging session: started confused, ended with fix",
    session_id="session-123",
)
```

### Interaction Patterns

Store general interaction learnings:

```python
await memory.store_interaction_pattern(
    pattern="Use examples before explanations for complex topics",
    outcome="User understood faster",
    effectiveness=0.85,
)
```

## Memory Namespaces

The personality module uses these AgentCore Memory namespaces:

| Namespace | Purpose |
|-----------|---------|
| `personality/voice_preferences` | Preferred voices per use case |
| `personality/expression_patterns` | Successful emotion expressions |
| `personality/reaction_history` | Reaction usage and feedback |
| `personality/avatar_settings` | Avatar configuration preferences |

These namespaces are defined in `mcp_agentcore_memory/namespaces.py`.

## Data Classes

### VoicePreference

```python
from mcp_core.personality import VoicePreference

pref = VoicePreference(
    voice_id="Rachel",
    use_case="tutorial",
    preset="audiobook",
    effectiveness=0.8,
    notes="Clear and educational",
)

# Convert to storable fact
fact = pref.to_fact()
# "Voice Rachel works well for tutorial (preset: audiobook). Clear and educational"
```

### ExpressionPattern

```python
from mcp_core.personality import ExpressionPattern
from mcp_core.emotions import CanonicalEmotion

pattern = ExpressionPattern(
    emotion=CanonicalEmotion.THINKING,
    intensity=0.6,
    audio_tags=["[thoughtful]"],
    avatar_emotion="neutral",
    avatar_gesture="thinking",
    context="code analysis",
    effectiveness=0.75,
)

fact = pattern.to_fact()
```

### ReactionUsage

```python
from mcp_core.personality import ReactionUsage

usage = ReactionUsage(
    reaction_id="miku_typing",
    context="working on implementation",
    emotion=CanonicalEmotion.ATTENTIVE,
    user_response="positive",
    effectiveness=0.8,
)

fact = usage.to_fact()
```

## Integration with ExpressionOrchestrator

The orchestrator automatically integrates with personality memory:

```python
# Orchestrator queries memory before expressing
result = await orchestrator.express(
    text="Let me review this code",
    emotion=CanonicalEmotion.ATTENTIVE,
)

# If memory contains "Rachel voice works well for code review":
# - Orchestrator uses Rachel instead of default voice
# - Pattern is stored after successful expression
# - Future similar contexts will use learned preferences
```

## Complete Example

```python
from mcp_core.expression import ExpressionOrchestrator, MCPClients
from mcp_core.personality import PersonalityMemory
from mcp_core.emotions import CanonicalEmotion, infer_emotion

# Setup clients
clients = MCPClients(
    synthesize_speech=elevenlabs.synthesize_stream,
    send_animation=virtual_char.send_animation,
    play_audio=virtual_char.play_audio,
    search_reactions=reactions.search_reactions,
    store_facts=memory.store_facts,
    search_memories=memory.search_memories,
)

orchestrator = ExpressionOrchestrator(clients=clients)
personality = PersonalityMemory(
    store_facts_fn=memory.store_facts,
    search_memories_fn=memory.search_memories,
)

# Respond to user message
user_message = "I finally fixed that impossible bug!"

# 1. Infer emotion
emotion_result = infer_emotion(user_message)

# 2. Check for learned preferences
voice_prefs = await personality.get_voice_preferences("celebration")
reaction_history = await personality.get_reaction_history(
    context="bug fix",
    emotion=emotion_result.primary_emotion,
)

# 3. Express with full orchestration
result = await orchestrator.express(
    text="That's fantastic! Great debugging work!",
    emotion=emotion_result.primary_emotion,
    intensity=emotion_result.intensity,
    voice_id=voice_prefs[0]["voice_id"] if voice_prefs else None,
)

# 4. Result has audio, avatar, and reaction ready
print(f"Audio: {result.audio.local_path}")
print(f"Avatar: {result.avatar.emotion} with {result.avatar.gesture}")
print(f"Reaction: {result.reaction.markdown}")
```

## API Reference

### expression/orchestrator.py

| Class | Description |
|-------|-------------|
| `ExpressionOrchestrator` | Main orchestration class |
| `MCPClients` | Container for MCP client functions |

| Method | Description |
|--------|-------------|
| `express(text, emotion, ...)` | Express across modalities |
| `express_with_arc(segments)` | Express emotional sequence |
| `get_config()` | Get current configuration |
| `update_config(**kwargs)` | Update configuration |

### expression/types.py

| Class | Description |
|-------|-------------|
| `Modality` | Enum: VOICE, AVATAR, REACTION |
| `ExpressionConfig` | Orchestrator configuration |
| `ExpressionResult` | Combined result from all modalities |
| `AudioResult` | Voice synthesis result |
| `AvatarResult` | Avatar expression result |
| `ReactionResult` | Reaction search result |

### personality/memory.py

| Class | Description |
|-------|-------------|
| `PersonalityMemory` | Memory manager for preferences |
| `VoicePreference` | Voice preference data |
| `ExpressionPattern` | Expression pattern data |
| `ReactionUsage` | Reaction usage data |

## See Also

- [Emotions Module](EMOTIONS.md) - Canonical emotion taxonomy
- [MCP Integration Roadmap](../../../../docs/roadmaps/mcp-integration-roadmap.md) - Full architecture including Phase 4: Dual-Speed Cognition
- [AgentCore Memory Integration](../../../../docs/integrations/ai-services/agentcore-memory-integration.md) - Memory system details
