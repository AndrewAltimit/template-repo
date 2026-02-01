# MCP Integration Proposal: Unified Expressive AI Agent System

> **Note**: This proposal was written when the Virtual Character server was implemented in Python.
> The server has since been **migrated to Rust**. The integration concepts and emotion model
> architecture remain valid, but code examples showing Python imports should be adapted
> for Rust. See `tools/mcp/mcp_virtual_character/src/types.rs` for the Rust emotion types.

## Executive Summary

This proposal outlines integration opportunities between four MCP servers that, when combined, create a **coherent expressive AI agent system** capable of multi-modal communication with persistent personality and contextual memory.

| Server | Core Capability |
|--------|----------------|
| **ElevenLabs Speech** | Emotional voice synthesis with 50+ expression tags |
| **Virtual Character** | Embodied avatar control with emotions, gestures, sequences |
| **Reaction Search** | Semantic search for contextual reaction images |
| **AgentCore Memory** | Persistent memory with semantic search across sessions |

**The Vision**: An AI agent that speaks with authentic emotion, embodies those emotions through an avatar, selects contextually appropriate visual reactions, and remembers its communication patterns across sessions.

---

## Part 1: Unified Emotion Taxonomy

> **Implementation Status**: Basic emotion support (EmotionType enum, EmotionVector PAD model, emotion blending) is implemented in `mcp_virtual_character/models/canonical.py`. Advanced features (mappings, inference) will also be added to `mcp_virtual_character` - other MCP servers can import from there.

### The Problem

Each system has its own emotion vocabulary:

| System | Emotion Representation |
|--------|----------------------|
| ElevenLabs | Audio tags: `[laughs]`, `[excited]`, `[whisper]`, `[sighs]` |
| Virtual Character | Enum: `HAPPY`, `SAD`, `ANGRY`, `SURPRISED`, `CALM` |
| Reaction Search | Tags: `happy`, `confused`, `annoyed`, `excited`, `smug` |

These don't map cleanly to each other, creating friction when expressing the same emotion across modalities.

### Proposed Solution: Canonical Emotion Model

Create a shared emotion model in `mcp_virtual_character` that other servers can import:

```
mcp_virtual_character/mcp_virtual_character/
├── models/
│   └── canonical.py  # EmotionType enum, EmotionVector (PAD model), blending [IMPLEMENTED]
├── emotions/
│   ├── mappings.py   # Bidirectional mappings for each system [PLANNED]
│   └── inference.py  # Emotion detection from text/context [PLANNED]
```

**Canonical Emotions** (12 primary + intensity):
```
JOY (intensity: 0-1)
  └─ 0.3: content, pleased
  └─ 0.6: happy, cheerful
  └─ 1.0: excited, elated, ecstatic

SADNESS (intensity: 0-1)
  └─ 0.3: disappointed, melancholy
  └─ 0.6: sad, sorrowful
  └─ 1.0: devastated, crying

ANGER (intensity: 0-1)
  └─ 0.3: annoyed, irritated
  └─ 0.6: angry, frustrated
  └─ 1.0: furious, enraged

FEAR (intensity: 0-1)
  └─ 0.3: nervous, uneasy
  └─ 0.6: anxious, worried
  └─ 1.0: terrified, panicked

SURPRISE (intensity: 0-1)
  └─ 0.3: curious, intrigued
  └─ 0.6: surprised, amazed
  └─ 1.0: shocked, astonished

DISGUST (intensity: 0-1)
CONTEMPT (intensity: 0-1)
CONFUSION (intensity: 0-1)
CALM (intensity: 0-1)
THINKING (intensity: 0-1)
SMUG (intensity: 0-1)
EMBARRASSMENT (intensity: 0-1)
ATTENTIVE (intensity: 0-1)    # NEW: focused, listening
BORED (intensity: 0-1)        # NEW: disengaged, distracted
```

### PAD Model (Dimensional Emotions)

Discrete emotion categories are useful for classification but brittle for animation. Underneath the 12 categories, use a **PAD (Pleasure, Arousal, Dominance)** 3D vector model:

```python
@dataclass
class EmotionVector:
    """PAD model for smooth emotion interpolation"""
    pleasure: float   # -1 (unhappy) to +1 (happy)
    arousal: float    # -1 (calm) to +1 (excited)
    dominance: float  # -1 (submissive) to +1 (dominant)

    def lerp(self, target: "EmotionVector", t: float) -> "EmotionVector":
        """Linear interpolation for smooth transitions"""
        return EmotionVector(
            pleasure=self.pleasure + (target.pleasure - self.pleasure) * t,
            arousal=self.arousal + (target.arousal - self.arousal) * t,
            dominance=self.dominance + (target.dominance - self.dominance) * t,
        )

# Map discrete emotions to PAD vectors
EMOTION_TO_PAD = {
    CanonicalEmotion.JOY:          EmotionVector(+0.8, +0.6, +0.2),
    CanonicalEmotion.SADNESS:      EmotionVector(-0.7, -0.3, -0.4),
    CanonicalEmotion.ANGER:        EmotionVector(-0.6, +0.8, +0.6),
    CanonicalEmotion.FEAR:         EmotionVector(-0.7, +0.7, -0.6),
    CanonicalEmotion.SURPRISE:     EmotionVector(+0.2, +0.8, -0.1),
    CanonicalEmotion.DISGUST:      EmotionVector(-0.6, +0.2, +0.3),
    CanonicalEmotion.CONTEMPT:     EmotionVector(-0.3, +0.1, +0.7),
    CanonicalEmotion.CONFUSION:    EmotionVector(-0.2, +0.4, -0.3),
    CanonicalEmotion.CALM:         EmotionVector(+0.3, -0.6, +0.1),
    CanonicalEmotion.THINKING:     EmotionVector(+0.1, +0.3, +0.2),
    CanonicalEmotion.SMUG:         EmotionVector(+0.4, +0.2, +0.8),
    CanonicalEmotion.EMBARRASSMENT:EmotionVector(-0.4, +0.5, -0.5),
    CanonicalEmotion.ATTENTIVE:    EmotionVector(+0.2, +0.5, +0.0),  # Focused listening
    CanonicalEmotion.BORED:        EmotionVector(-0.3, -0.7, -0.2),  # Disengaged
}
```

**Benefits of PAD Model**:
- Mathematically blend System 1 and System 2 outputs
- Smooth interpolation avoids "glitchy" state snaps
- Can average conflicting emotion signals
- Animation systems can map directly to blend shapes
- Single source of truth for emotional state
- Intensity-aware expression (subtle vs. exaggerated)

### Integration Points

1. **ElevenLabs → Canonical**: Parse audio tags, map to canonical emotion + intensity
2. **Canonical → Virtual Character**: Map to EmotionType + emotion_intensity
3. **Canonical → Reaction Search**: Generate semantic query from emotion state
4. **Text Analysis → Canonical**: Infer emotion from content being spoken

---

## Part 2: Memory-Enhanced Personality

### The Opportunity

AgentCore Memory can store personality traits and preferences that inform expression across all modalities.

### Proposed Namespaces

```
personality/
├── voice_preferences     # Preferred voices, speaking styles
├── expression_patterns   # Learned emotion expression preferences
├── reaction_history      # Which reactions resonate with users
└── avatar_settings       # Preferred gestures, emotion intensities

context/
├── conversation_tone     # Current conversation emotional arc
├── user_preferences      # User-specific communication preferences
└── interaction_history   # Past interaction patterns
```

### Use Cases

#### 1. **Voice Preference Learning**
```python
# After successful synthesis, store preference
await store_facts(
    facts=[
        "User responded positively to Rachel voice with github_review preset",
        "Professional tone with subtle humor works well for code reviews"
    ],
    namespace="personality/voice_preferences"
)

# Before synthesis, query preferences
memories = await search_memories(
    query="voice preferences for code review",
    namespace="personality/voice_preferences"
)
# → Use learned preferences to select voice/preset
```

#### 2. **Reaction Pattern Memory**
```python
# Store successful reaction usage
await store_facts(
    facts=[
        "felix reaction works well for celebrating bug fixes",
        "miku_confused appropriate for debugging sessions",
        "User prefers subtle reactions over exaggerated ones"
    ],
    namespace="personality/reaction_history"
)

# Query before selecting reaction
memories = await search_memories(
    query="reaction for celebrating completed feature",
    namespace="personality/reaction_history"
)
```

#### 3. **Emotional Arc Tracking**
```python
# Track conversation emotional progression
await store_event(
    content="Conversation started frustrated (debugging), now relieved (fix found)",
    actor_id="claude-code",
    session_id=session_id
)

# Query to maintain emotional coherence
events = await list_session_events(actor_id, session_id)
# → Adjust current expression based on emotional journey
```

### Implementation Considerations

- **Rate Limiting**: Use `store_facts` (no rate limit) for personality data, reserve `store_event` for key session moments
- **Namespace Organization**: Clear hierarchy for different preference types
- **Semantic Search**: Leverage similarity search for fuzzy preference matching

---

## Part 3: Multi-Modal Expression Pipeline

### The Vision

When an AI agent wants to express something, it should be able to:
1. **Speak** it (ElevenLabs) with appropriate emotion
2. **Embody** it (Virtual Character) with matching expression
3. **Illustrate** it (Reaction Search) with a fitting reaction
4. **Remember** it (Memory) for future consistency

### Proposed: Expression Orchestrator

A new tool or utility that coordinates multi-modal expression:

```python
class ExpressionOrchestrator:
    """Coordinates expression across all modalities"""

    async def express(
        self,
        text: str,
        emotion: CanonicalEmotion,
        intensity: float = 0.5,
        modalities: List[str] = ["voice", "avatar", "reaction"],
        remember: bool = True
    ) -> ExpressionResult:
        """
        Express a message across multiple modalities with emotional coherence.

        Returns paths/URLs for each modality output.
        """
        results = {}

        # 1. Generate voice with emotion-mapped audio tags
        if "voice" in modalities:
            audio_tags = self.emotion_to_audio_tags(emotion, intensity)
            results["audio"] = await self.elevenlabs.synthesize_stream(
                text=f"{audio_tags} {text}",
                voice_id=await self.get_preferred_voice(emotion),
            )

        # 2. Set avatar expression
        if "avatar" in modalities:
            avatar_emotion = self.emotion_to_avatar(emotion)
            await self.virtual_character.send_animation(
                emotion=avatar_emotion,
                emotion_intensity=intensity,
            )

            # If audio generated, play through avatar
            if results.get("audio"):
                await self.virtual_character.play_audio(
                    audio_data=results["audio"]["local_path"],
                    expression_tags=self.emotion_to_expression_tags(emotion),
                )

        # 3. Find matching reaction
        if "reaction" in modalities:
            query = self.emotion_to_reaction_query(emotion, intensity, text)
            reactions = await self.reaction_search.search_reactions(
                query=query,
                limit=1
            )
            results["reaction"] = reactions[0] if reactions else None

        # 4. Store expression pattern
        if remember:
            await self.memory.store_facts(
                facts=[f"Expressed {emotion.name} (intensity {intensity}) for: {text[:50]}..."],
                namespace="personality/expression_patterns"
            )

        return ExpressionResult(**results)
```

### Sequence Integration

For complex performances, integrate with Virtual Character sequences:

```python
async def create_expressive_sequence(
    script: List[DialogueLine],
    character_id: str
) -> str:
    """Create a choreographed sequence from dialogue with emotions"""

    await virtual_character.create_sequence(
        name=f"dialogue_{uuid4()}",
        description="Multi-modal expressive dialogue"
    )

    current_time = 0.0

    for line in script:
        # Infer emotion from text
        emotion = await infer_emotion(line.text)

        # Generate audio
        audio = await elevenlabs.synthesize_stream(
            text=line.text,
            voice_id=line.voice_id
        )

        # Add synchronized events
        await virtual_character.add_sequence_event(
            event_type="parallel",
            timestamp=current_time,
            parallel_events=[
                {
                    "event_type": "expression",
                    "expression": emotion.to_avatar_emotion(),
                    "expression_intensity": emotion.intensity
                },
                {
                    "event_type": "audio",
                    "audio_data": audio["local_path"],
                    "expression_tags": emotion.to_expression_tags()
                }
            ]
        )

        current_time += audio["duration"] + 0.5  # Gap between lines

    return await virtual_character.play_sequence()
```

---

## Part 4: Context-Aware Reaction Selection

### Current State

Reaction search uses semantic similarity on description + tags + usage scenarios.

### Enhancement: Memory-Informed Selection

Integrate memory to improve reaction selection:

```python
async def get_contextual_reaction(
    situation: str,
    emotion: Optional[CanonicalEmotion] = None
) -> ReactionResult:
    """Select reaction informed by memory and current emotional context"""

    # 1. Check memory for past successful reactions in similar situations
    memories = await memory.search_memories(
        query=f"reaction for {situation}",
        namespace="personality/reaction_history",
        top_k=3
    )

    # 2. Build enhanced query from context + memories
    query_parts = [situation]
    if emotion:
        query_parts.append(emotion.name.lower())
    for mem in memories:
        # Extract reaction preferences from memories
        if "works well" in mem.content:
            query_parts.append(mem.content)

    enhanced_query = " ".join(query_parts)

    # 3. Search with enhanced context
    reactions = await reaction_search.search_reactions(
        query=enhanced_query,
        limit=3
    )

    # 4. Optionally filter by learned preferences
    user_prefs = await memory.search_memories(
        query="reaction style preferences",
        namespace="context/user_preferences"
    )

    # Apply preference filtering (subtle vs exaggerated, etc.)
    filtered = apply_preference_filter(reactions, user_prefs)

    return filtered[0] if filtered else reactions[0]
```

### Reaction + Voice Pairing

When generating audio for a PR comment that will include a reaction:

```python
async def create_expressive_pr_comment(
    review_text: str,
    tone: str = "constructive"
) -> dict:
    """Generate PR comment with matched audio and reaction"""

    # 1. Infer emotion from review
    emotion = await infer_emotion(review_text)

    # 2. Generate audio review
    audio = await elevenlabs.generate_pr_audio_response(
        review_text=review_text,
        tone=tone
    )

    # 3. Find matching reaction
    reaction = await get_contextual_reaction(
        situation=f"PR review with {tone} tone",
        emotion=emotion
    )

    # 4. Compose comment
    comment = f"""
{review_text}

{reaction.markdown}

{audio.markdown_link}
"""

    # 5. Remember this pairing
    await memory.store_facts(
        facts=[f"Used {reaction.id} reaction with {tone} PR review tone"],
        namespace="personality/reaction_history"
    )

    return {"comment": comment, "audio": audio, "reaction": reaction}
```

---

## Part 5: Streaming Expression Pipeline

### The Opportunity

With ElevenLabs streaming at 75ms latency and Virtual Character supporting chunked audio, we can create real-time expressive streaming.

### Proposed: Real-Time Expression Stream

```python
async def stream_expressive_response(
    text_stream: AsyncGenerator[str, None],
    avatar_enabled: bool = True
) -> AsyncGenerator[ExpressionChunk, None]:
    """
    Stream text through synthesis with real-time avatar expression.

    As text arrives:
    1. Buffer until sentence boundary
    2. Infer emotion from buffered text
    3. Start avatar expression
    4. Stream audio to avatar
    5. Yield progress chunks
    """

    buffer = ""

    async for text_chunk in text_stream:
        buffer += text_chunk

        # Check for sentence boundary
        if any(buffer.endswith(p) for p in ['.', '!', '?', '\n']):
            sentence = buffer.strip()
            buffer = ""

            # Infer emotion
            emotion = await infer_emotion(sentence)

            # Set avatar expression immediately
            if avatar_enabled:
                await virtual_character.send_animation(
                    emotion=emotion.to_avatar_emotion(),
                    emotion_intensity=emotion.intensity
                )

            # Stream audio synthesis
            async for audio_chunk in elevenlabs.synthesize_with_websocket(
                StreamConfig(
                    text=sentence,
                    voice_id="Rachel",
                    auto_mode=True,
                    region=StreamingRegion.US
                )
            ):
                # Forward audio chunk to avatar
                if avatar_enabled:
                    # Note: This would require chunked audio support
                    pass

                yield ExpressionChunk(
                    text=sentence,
                    emotion=emotion,
                    audio_chunk=audio_chunk
                )
```

---

## Part 6: Implementation Priorities

### Phase 1: Foundation (Low Effort, High Impact)

| Task | Effort | Impact | Description |
|------|--------|--------|-------------|
| Canonical Emotion Taxonomy | Medium | High | ✅ Implemented in `mcp_virtual_character/models/canonical.py` |
| ElevenLabs → Emotion Mapping | Low | High | Parse audio tags to canonical emotions |
| Avatar ← Emotion Mapping | Low | High | Map canonical to Virtual Character emotions |
| Reaction Query Enhancement | Low | Medium | Use canonical emotion in search queries |

### Phase 2: Memory Integration (Medium Effort, High Impact)

| Task | Effort | Impact | Description |
|------|--------|--------|-------------|
| Personality Namespaces | Low | Medium | Add namespace definitions to memory |
| Voice Preference Storage | Medium | High | Store/retrieve voice preferences |
| Reaction History Tracking | Medium | Medium | Remember successful reaction usage |
| Expression Pattern Learning | Medium | High | Learn user-preferred expression styles |

### Phase 3: Orchestration (Higher Effort, Transformative)

| Task | Effort | Impact | Description |
|------|--------|--------|-------------|
| ExpressionOrchestrator | High | Transformative | Unified multi-modal expression |
| Sequence Integration | Medium | High | Emotion-aware sequence building |
| Streaming Pipeline | High | High | Real-time expressive streaming |
| GitHub Integration | Medium | Medium | Combined audio + reaction comments |

---

## Part 7: Specific Refinements by System

### ElevenLabs Speech Refinements

1. **Emotion Extraction Tool**: New tool to extract canonical emotion from audio tags
   ```python
   extract_emotion(audio_tags: List[str]) -> CanonicalEmotion
   ```

2. **Memory-Aware Voice Selection**: Query personality/voice_preferences before selecting voice

3. **Expression Tag Normalization**: Standardize tag output for downstream consumption

### Virtual Character Refinements

1. **Canonical Emotion Input**: Accept CanonicalEmotion directly in send_animation
   ```python
   send_animation(canonical_emotion=CanonicalEmotion.JOY, intensity=0.8)
   ```

2. **Expression Tag Processing**: Enhanced mapping from ElevenLabs tags to avatar expressions

3. **Sequence Emotion Tracking**: Track emotional arc through sequence for coherence

### Reaction Search Refinements

1. **Emotion-Based Search**: New search mode using canonical emotions
   ```python
   search_by_emotion(emotion: CanonicalEmotion, intensity: float) -> List[Reaction]
   ```

2. **Context Enhancement**: Accept additional context for better semantic matching

3. **Usage Tracking**: Optional callback to memory for tracking reaction usage

### AgentCore Memory Refinements

1. **Personality Namespace Presets**: Pre-defined namespaces for expression patterns

2. **Emotion Event Schema**: Structured event format for emotional state tracking

3. **Preference Aggregation**: Tool to aggregate preferences from stored facts

---

## Part 8: Example Integrated Workflow

### Scenario: AI Agent Completes a Challenging Bug Fix

```python
# 1. Context: Just fixed a tricky bug after 30 minutes of debugging
emotion = CanonicalEmotion.JOY
intensity = 0.7  # Relieved but not over-the-top

# 2. Check memory for expression preferences
voice_pref = await memory.search_memories(
    query="voice for celebrating accomplishment",
    namespace="personality/voice_preferences"
)
# → "Rachel voice with moderate enthusiasm works well"

# 3. Generate spoken response
text = "Finally got it! The race condition was in the mutex initialization."
audio = await elevenlabs.synthesize_stream(
    text=f"[relieved][laughs softly] {text}",
    voice_id="Rachel",
    speed=1.0
)

# 4. Set avatar expression
await virtual_character.send_animation(
    emotion="happy",
    emotion_intensity=0.7,
    gesture="cheer"
)

# 5. Play audio through avatar
await virtual_character.play_audio(
    audio_data=audio["local_path"],
    expression_tags=["relieved", "happy"]
)

# 6. Find matching reaction for PR comment
reaction = await reaction_search.search_reactions(
    query="relieved after fixing difficult bug",
    limit=1
)
# → nervous_sweat.webp (relief after struggle)

# 7. Create PR comment
comment = f"""
Fixed the race condition in mutex initialization.

The issue was that we were initializing the mutex after spawning threads,
causing intermittent deadlocks.

{reaction[0].markdown}
"""

# 8. Store this expression pattern
await memory.store_facts(
    facts=[
        f"Used {reaction[0].id} for bug fix relief - worked well",
        "Moderate joy intensity appropriate for professional context"
    ],
    namespace="personality/expression_patterns"
)
```

---

## Part 9: Dual-Speed Cognitive Architecture

### The Insight

Human cognition operates on two systems (Kahneman's System 1/System 2):
- **System 1**: Fast, intuitive, automatic, unconscious
- **System 2**: Slow, deliberate, analytical, conscious

Our AI agent should mirror this with **parallel processing streams** - fast reactions for immediate presence, slow synthesis for depth and insight.

### Architecture: Parallel Stream with Asynchronous Injection

```
┌─────────────────────────────────────────────────────────────────────┐
│                      COGNITIVE ORCHESTRATOR                         │
│                    (asyncio event loop hub)                         │
└─────────────────────┬───────────────────────┬───────────────────────┘
                      │                       │
         ┌────────────▼────────────┐ ┌────────▼────────────────────┐
         │   SYSTEM 1: FAST        │ │   SYSTEM 2: SLOW            │
         │   (The Unconscious)     │ │   (The Conscious)           │
         │                         │ │                              │
         │ • Embedding models      │ │ • Claude Opus 4.5            │
         │ • Pattern cache         │ │ • Full context reasoning     │
         │ • Reflex store          │ │ • Memory synthesis           │
         │ • <100ms response       │ │ • 2-30s processing           │
         │                         │ │                              │
         │ Components:             │ │ Components:                  │
         │ ├─ Reaction Search      │ │ ├─ Deep Reasoner             │
         │ ├─ Emotion Classifier   │ │ ├─ AgentCore Memory (R/W)    │
         │ ├─ Avatar Expressions   │ │ ├─ Pattern Compiler          │
         │ └─ Filler TTS           │ │ └─ Context Injector          │
         └────────────┬────────────┘ └────────┬────────────────────┘
                      │                       │
                      ▼                       ▼
         ┌─────────────────────────────────────────────────────────┐
         │              OUTPUT PRIORITY MANAGER                     │
         │  • Fast output streams immediately                       │
         │  • Slow can INTERRUPT with override signal               │
         │  • Animation mixer prioritizes slow over fast            │
         └─────────────────────────────────────────────────────────┘
```

### System 1: Fast Reactions (< 100ms)

**Purpose**: Immediate presence and acknowledgment

| Component | Model/Tech | Latency | Function |
|-----------|------------|---------|----------|
| Reaction Search | **Model2Vec potion-retrieval-32M** | **~0.02ms** | Semantic image search (500x faster) |
| Emotion Classifier | **distilbert-base-uncased-emotion** | ~2.5ms | 6-class emotion detection |
| Avatar Expression | Direct mapping | ~5ms | Set expression from emotion |
| Filler TTS | ElevenLabs Flash v2.5 | ~75ms | "I see...", "Hmm...", acknowledgments |
| Filler Text | **Llama 3.2 1B** (OpenRouter) | ~50ms | Generate contextual acknowledgments |
| Pattern Cache | Vector DB (local) | ~5ms | Pre-computed reaction patterns |

**Fast System Behavior**:
```python
class FastMind:
    """System 1: Immediate, intuitive responses"""

    def __init__(self):
        self.pattern_cache = VectorCache()  # Pre-baked reactions
        self.working_memory = deque(maxlen=3)  # Last 3 turns
        self.current_vibe = None  # Set by slow system

    async def react(self, input_text: str) -> FastReaction:
        """React immediately (<100ms)"""

        # 1. Quick emotion classification
        emotion = await self.classify_emotion(input_text)  # ~15ms

        # 2. Check pattern cache for learned responses
        cached = await self.pattern_cache.search(input_text, top_k=1)  # ~5ms

        # 3. Set avatar expression immediately
        await self.set_expression(emotion)  # ~5ms

        # 4. Generate filler acknowledgment
        filler = self.get_contextual_filler(emotion, self.current_vibe)

        # 5. Find reaction image
        reaction = await self.reaction_search.search(
            query=f"{emotion.name} {input_text[:50]}",
            limit=1
        )  # ~10ms

        return FastReaction(
            emotion=emotion,
            filler_text=filler,
            reaction=reaction,
            cached_pattern=cached
        )

    def get_contextual_filler(self, emotion: Emotion, vibe: str) -> str:
        """Non-committal fillers for first 500ms"""
        fillers = {
            "thinking": ["Hmm...", "Let me think...", "I see..."],
            "curious": ["Interesting...", "Oh?", "Tell me more..."],
            "acknowledging": ["Got it.", "I understand.", "Right..."],
        }
        # Vibe from slow system influences filler selection
        if vibe == "somber":
            return "I understand..."
        return random.choice(fillers.get(emotion.category, fillers["acknowledging"]))
```

### System 2: Slow Synthesis (2-30s)

**Purpose**: Deep reasoning, insight generation, memory synthesis

| Component | Model/Tech | Latency | Function |
|-----------|------------|---------|----------|
| Primary Reasoner | **Claude Opus 4.5** (Anthropic API) | 5-30s | Deep reasoning, synthesis, all cognitive tasks |
| Fallback Reasoner | **Gemma 2 9B** / **MiniMax M2** (OpenRouter) | 2-10s | Cost-effective alternative when Opus unavailable |
| Memory Query | AgentCore (semantic) | ~200ms | Retrieve relevant memories |
| Quality Embeddings | **all-MiniLM-L12-v2** (current) | ~15ms | High-quality semantic matching |
| Pattern Compiler | Batch process (offline) | N/A | Compile patterns during idle/"sleep" |
| Context Injector | Redis/shared state | ~5ms | Set "current vibe" for fast system |

**Slow System Behavior**:
```python
class SlowMind:
    """System 2: Deliberate, synthesized responses"""

    def __init__(self):
        self.memory = AgentCoreMemory()
        self.pattern_compiler = PatternCompiler()
        self.context_state = SharedState()  # Redis or shared memory

    async def synthesize(
        self,
        input_text: str,
        fast_reaction: FastReaction,
        session_context: List[Message]
    ) -> SlowSynthesis:
        """Deep synthesis (2-30s background)"""

        # 1. Query relevant memories
        memories = await self.memory.search_memories(
            query=input_text,
            namespace="context/interaction_history",
            top_k=5
        )

        # 2. Check if fast reaction needs correction
        if self.should_override(fast_reaction, input_text, memories):
            await self.send_interrupt()

        # 3. Deep reasoning with full context
        synthesis = await self.deep_reason(
            input_text=input_text,
            session_context=session_context,
            memories=memories,
            fast_reaction=fast_reaction
        )

        # 4. Update context for fast system
        await self.context_state.set("current_vibe", synthesis.detected_tone)

        # 5. Store interaction pattern
        await self.memory.store_facts(
            facts=[f"Responded to '{input_text[:50]}' with {synthesis.emotion}"],
            namespace="personality/expression_patterns"
        )

        # 6. Periodically compile patterns to cache
        if self.should_compile():
            await self.compile_patterns_to_cache()

        return synthesis

    async def compile_patterns_to_cache(self):
        """Compile frequent patterns from memory → fast system cache"""
        # Query common patterns
        patterns = await self.memory.search_memories(
            query="frequently used expressions and reactions",
            namespace="personality/expression_patterns",
            top_k=100
        )

        # Aggregate and weight by frequency
        compiled = self.pattern_compiler.compile(patterns)

        # Push to fast system's pattern cache
        await self.fast_mind.pattern_cache.bulk_update(compiled)
```

### Escalation Triggers

When should fast system defer to slow system?

| Trigger | Detection Method | Threshold |
|---------|-----------------|-----------|
| **Semantic Ambiguity** | Cosine distance to known patterns | > 0.4 |
| **Explicit Complexity** | Keyword detection | "explain", "why", "how does", "plan" |
| **Long Input** | Word count | > 20 words |
| **Emotional Spike** | Sentiment intensity | abs(valence) > 0.8 |
| **Follow-up Question** | Dialogue state | References previous turn |
| **Safety Concern** | Content classifier | Any flag |

```python
class EscalationDetector:
    """Determines when to escalate from fast to slow"""

    COMPLEXITY_KEYWORDS = {"explain", "why", "how", "plan", "analyze", "compare"}

    async def should_escalate(self, input_text: str, fast_reaction: FastReaction) -> bool:
        # 1. Semantic ambiguity
        if fast_reaction.cached_pattern is None:
            pattern_distance = await self.pattern_cache.min_distance(input_text)
            if pattern_distance > 0.4:
                return True

        # 2. Explicit complexity
        words = set(input_text.lower().split())
        if words & self.COMPLEXITY_KEYWORDS:
            return True

        # 3. Long input
        if len(input_text.split()) > 20:
            return True

        # 4. Emotional intensity
        if abs(fast_reaction.emotion.valence) > 0.8:
            return True

        return False
```

### Memory Integration: Fast vs Slow

| Aspect | System 1 (Fast) | System 2 (Slow) |
|--------|-----------------|-----------------|
| **Access** | Read-only | Read-write |
| **Scope** | Pattern cache + working memory | Full AgentCore Memory |
| **Writes** | Never | After each interaction |
| **Updates** | Receives compiled patterns | Compiles patterns from history |

### Failure Modes and Mitigations

| Failure | Description | Mitigation |
|---------|-------------|------------|
| **The Stutter** | Fast says "Sure!" then slow says "Actually, no." | Fast uses non-committal fillers for first 500ms |
| **Mood Whiplash** | Fast smiles at "I'm happy my enemy died" | Sentiment module has veto power over animations |
| **Race Condition** | Both systems move avatar arms | Priority animation mixer (slow > fast) |
| **Echo Chamber** | Fast patterns calcify, slow never updates | Periodic pattern expiration + recompilation |
| **Latency Spike** | Slow system overwhelmed | Backpressure queue with timeout fallback to fast |
| **Sync Drift** | Voice starts before avatar mouth opens | VRChat: automatic lip-sync. Other platforms: client-side sequencer |
| **Split Brain** | System 1→Surprised, System 2→Sad (3s later) | Emotional Decay/Transition Manager with curves |
| **Thinking Gap** | Avatar frozen during 2-30s Opus wait | Active Listening behaviors (nods, gaze shifts) |
| **Sarcasm Blindness** | Text says "happy" but tone is angry | Multi-modal trust hierarchy (voice > face > text) |

### Audio-Visual Synchronization

**Platform-Specific Approaches**:

| Platform | Lip-Sync | Emotion/Gesture | Complexity |
|----------|----------|-----------------|------------|
| **VRChat** | Automatic (built-in) | OSC parameters | Simple |
| **Blender** | Manual visemes | Python API | Full control |
| **Unreal Engine** | Manual visemes | Blueprints/C++ | Full control |
| **Unity (standalone)** | Manual visemes | WebSocket | Full control |

#### VRChat: Keep It Simple

VRChat's automatic lip-sync from audio is excellent - no need to manually control visemes. Focus on:

```python
class VRChatSimpleSync:
    """VRChat-optimized: let VRChat handle lip-sync"""

    async def play_expression_with_audio(
        self,
        audio_path: str,
        emotion: CanonicalEmotion,
        gesture: Optional[str] = None
    ):
        # 1. Set emotion/expression via OSC (VRChat parameters)
        await self.osc.send_float("/avatar/parameters/Emotion", emotion.to_float())

        # 2. Trigger gesture if specified
        if gesture:
            await self.osc.send_int("/avatar/parameters/Gesture", GESTURE_MAP[gesture])

        # 3. Play audio - VRChat handles lip-sync automatically!
        await self.virtual_character.play_audio(audio_path)

        # That's it. VRChat's built-in viseme system does the rest.
```

**What VRChat handles automatically**:
- Viseme detection from audio stream
- Blend shape animation for mouth movements
- Timing synchronization

**What we control via OSC**:
- Emotion expressions (happy, sad, angry, etc.)
- Hand gestures
- Body animations/emotes
- Custom avatar parameters

#### Future: Full Viseme Control (Blender/Unreal/Unity)

For platforms where we want full control, use the sequencer pattern:

```python
class FullVisemeSync:
    """For Blender/Unreal/Unity - manual viseme control"""

    async def play_synchronized(
        self,
        audio_asset: AudioAsset,
        animation_data: AnimationData
    ):
        # Only use this for non-VRChat platforms
        viseme_timeline = audio_asset.visemes

        start_time = time.monotonic()
        audio_task = asyncio.create_task(self.play_audio(audio_asset))

        for viseme in viseme_timeline:
            elapsed = time.monotonic() - start_time
            if (wait := viseme.timestamp - elapsed) > 0:
                await asyncio.sleep(wait)
            await self.avatar.set_viseme(viseme.shape)  # Blend shape control

        await audio_task
```

**MVP Priority**: Start with VRChat's simple approach. Add full viseme control later for other platforms.

### Emotional Transition Manager

**Problem**: Discrete emotion switches cause jarring "snaps" between states.

**Solution**: Treat System 2 output as "Target State" with transition curves:

```python
class EmotionTransitionManager:
    """Smooth emotional transitions using decay curves"""

    def __init__(self):
        self.current_state = EmotionVector(pleasure=0, arousal=0, dominance=0)
        self.target_state = self.current_state
        self.transition_speed = 0.3  # Blend factor per frame

    def set_target(self, emotion: CanonicalEmotion, intensity: float):
        """System 2 sets target, we interpolate smoothly"""
        self.target_state = emotion.to_pad_vector() * intensity

    def update(self, delta_time: float) -> EmotionVector:
        """Called each frame - smooth interpolation"""
        blend = min(1.0, self.transition_speed * delta_time * 60)
        self.current_state = self.current_state.lerp(self.target_state, blend)
        return self.current_state
```

### Active Listening Behaviors

**Problem**: Avatar appears frozen during 2-30s System 2 processing.

**Solution**: System 1 triggers ambient behaviors immediately:

```python
class ActiveListeningBehavior:
    """Fills the gap while System 2 thinks"""

    BEHAVIORS = {
        "listening": ["slight_nod", "head_tilt", "eye_contact"],
        "thinking": ["gaze_away", "slight_frown", "hand_to_chin"],
        "processing": ["slow_blink", "subtle_nod", "attentive_posture"],
    }

    async def run_while_waiting(self, mode: str = "thinking"):
        """Run ambient behaviors until System 2 completes"""
        behaviors = self.BEHAVIORS[mode]
        while not self.system2_complete.is_set():
            behavior = random.choice(behaviors)
            await self.avatar.trigger_behavior(behavior)
            await asyncio.sleep(random.uniform(1.5, 3.0))  # Natural pacing
```

### Layered Subsumption Architecture

**Problem**: "Optimistic execution with interrupts" is risky for character consistency.

**Solution**: Use a layered architecture where higher layers *suppress* or *modulate* lower layers rather than interrupt:

```
┌─────────────────────────────────────────────────────────────────────┐
│  LAYER 2: COGNITIVE (System 2)                                      │
│  • Deep reasoning, synthesized responses                            │
│  • Controls: Voice content, complex gestures                        │
│  • Suppresses: Layer 1 fillers when ready                          │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 1: HABIT/FILLER (System 1.5)                                 │
│  • Runs fillers ("Hmm," "I see...")                                 │
│  • Active Listening behaviors                                       │
│  • Suppresses: None (additive to Layer 0)                          │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 0: REFLEX (System 1)                                         │
│  • Always running, never suppressed                                 │
│  • Blinking, breathing, gaze tracking                              │
│  • Immediate mirroring (smile if user smiles)                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Key Principle**: Layer 2 takes control of "Voice" but leaves "Gaze" to Layer 0. Layers modulate, not replace.

```python
class SubsumptionController:
    """Layered behavior control"""

    def __init__(self):
        self.layers = [
            ReflexLayer(),      # Layer 0: Always active
            FillerLayer(),      # Layer 1: Active during processing
            CognitiveLayer(),   # Layer 2: When ready
        ]

    async def update(self, context: Context) -> BehaviorOutput:
        """Higher layers can suppress lower layer outputs"""
        output = BehaviorOutput()

        for layer in self.layers:
            layer_output = await layer.compute(context)

            # Higher layers can suppress specific channels
            for channel in ["voice", "gesture", "expression", "gaze"]:
                if not layer_output.suppresses(channel):
                    # Lower layer's output passes through
                    output.merge(channel, layer_output)
                else:
                    # Higher layer takes over this channel
                    output.set(channel, layer_output)

        return output
```

### Multi-Modal Input Processing

**Problem**: Text sentiment alone cannot detect sarcasm. "Great job" can be praise or mockery.

**Solution**: Multi-modal trust hierarchy with audio analysis:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SIGNAL TRUST HIERARCHY                           │
├─────────────────────────────────────────────────────────────────────┤
│  VOICE TONE (Audio)     │ Highest truth for EMOTION                │
│  ────────────────────── │ wav2vec2 extracts arousal/valence        │
├─────────────────────────────────────────────────────────────────────┤
│  FACIAL EXPRESSION      │ High truth for INTENT                    │
│  (Video/Camera)         │ Detects micro-expressions, eye contact   │
├─────────────────────────────────────────────────────────────────────┤
│  TEXT (Transcript)      │ Lowest truth for EMOTION                 │
│                         │ Highest truth for SEMANTIC CONTENT       │
└─────────────────────────────────────────────────────────────────────┘
```

**Conflict Resolution**:
```python
class MultiModalEmotionFusion:
    """Fuse signals from multiple modalities"""

    TRUST_WEIGHTS = {
        "audio": 0.5,   # Voice tone - highest for emotion
        "video": 0.3,   # Facial expression
        "text": 0.2,    # Text sentiment - lowest for emotion
    }

    async def fuse(
        self,
        audio_emotion: EmotionVector,
        video_emotion: Optional[EmotionVector],
        text_emotion: EmotionVector,
    ) -> tuple[EmotionVector, float]:
        """
        Fuse multi-modal signals with conflict detection.

        Returns: (fused_emotion, confidence)
        """
        # Check for conflicts (e.g., text=happy, audio=angry)
        if self._detect_conflict(audio_emotion, text_emotion):
            # Likely sarcasm - trigger CONFUSION or CAUTION
            return EmotionVector(-0.1, +0.4, -0.2), 0.6  # Cautious/uncertain

        # Weighted blend
        weights = self.TRUST_WEIGHTS
        fused = EmotionVector(
            pleasure=(
                audio_emotion.pleasure * weights["audio"] +
                (video_emotion.pleasure if video_emotion else 0) * weights["video"] +
                text_emotion.pleasure * weights["text"]
            ),
            arousal=...,  # Similar blend
            dominance=...,
        )

        return fused, self._compute_confidence(audio_emotion, text_emotion)

    def _detect_conflict(self, audio: EmotionVector, text: EmotionVector) -> bool:
        """Detect when audio and text emotions strongly disagree"""
        pleasure_diff = abs(audio.pleasure - text.pleasure)
        return pleasure_diff > 1.0  # Opposite valence
```

**Audio Emotion Extraction** (runs before transcription completes):
```python
class FastAudioClassifier:
    """Extract emotion from audio in ~50ms using wav2vec2"""

    def __init__(self):
        # Small wav2vec2 fine-tuned on emotion
        self.model = Wav2Vec2ForSequenceClassification.from_pretrained(
            "ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition"
        )

    async def extract_emotion(self, audio_chunk: bytes) -> EmotionVector:
        """Extract arousal/valence from raw audio"""
        # Process in parallel with transcription
        features = self.processor(audio_chunk, return_tensors="pt")
        logits = self.model(**features).logits
        # Map to PAD vector
        return self._logits_to_pad(logits)
```

### MCP Integration Points

**New Components Needed**:

1. **mcp_cognitive_orchestrator/** (new server)
   - Routes input to both systems
   - Manages output priority
   - Handles interrupt signals

2. **mcp_fast_mind/** (new server or mcp_virtual_character extension)
   - Lightweight embedding models
   - Pattern cache management
   - Filler generation

3. **Existing Server Enhancements**:
   - `mcp_reaction_search`: Already fast (~10ms), no changes needed
   - `mcp_elevenlabs_speech`: Add filler preset library
   - `mcp_virtual_character`: Add animation priority mixer
   - `mcp_agentcore_memory`: Add pattern compilation endpoint

### Example: Dual-Speed Response Flow

```python
# User asks: "Why did the mutex initialization cause a race condition?"

# ═══════════════════════════════════════════════════════════════════
# T+0ms: Input arrives at Cognitive Orchestrator
# ═══════════════════════════════════════════════════════════════════

async def orchestrate(input_text: str):
    # Fork to both systems simultaneously
    fast_task = asyncio.create_task(fast_mind.react(input_text))
    slow_task = asyncio.create_task(slow_mind.synthesize(input_text))

# ═══════════════════════════════════════════════════════════════════
# T+15ms: Fast system classifies emotion
# ═══════════════════════════════════════════════════════════════════

    # emotion = CURIOSITY (0.6 intensity)

# ═══════════════════════════════════════════════════════════════════
# T+20ms: Fast system checks patterns, finds none (technical question)
# ═══════════════════════════════════════════════════════════════════

    # pattern_distance = 0.62 > 0.4 threshold
    # Escalation flagged: will defer to slow system

# ═══════════════════════════════════════════════════════════════════
# T+25ms: Fast system sets avatar to "thinking" expression
# ═══════════════════════════════════════════════════════════════════

    await virtual_character.send_animation(
        emotion="thinking",
        emotion_intensity=0.6
    )

# ═══════════════════════════════════════════════════════════════════
# T+100ms: Fast system speaks filler
# ═══════════════════════════════════════════════════════════════════

    await elevenlabs.synthesize_stream(
        text="That's a great question... let me think about this.",
        voice_id="Rachel",
        preset="thoughtful_filler"
    )

# ═══════════════════════════════════════════════════════════════════
# T+5000ms: Slow system completes synthesis
# ═══════════════════════════════════════════════════════════════════

    synthesis = await slow_task
    # Deep explanation of mutex initialization order, thread spawning,
    # memory barriers, and the specific fix applied

# ═══════════════════════════════════════════════════════════════════
# T+5050ms: Full response with emotional coherence
# ═══════════════════════════════════════════════════════════════════

    await virtual_character.send_animation(
        emotion="explaining",  # Transitions smoothly from thinking
        gesture="pointing"
    )

    await elevenlabs.synthesize_stream(
        text=synthesis.explanation,
        voice_id="Rachel",
        speed=0.95  # Slightly slower for technical content
    )

    # Store pattern for future fast responses
    await memory.store_facts(
        facts=["Technical mutex question → thinking filler → detailed explanation"],
        namespace="personality/expression_patterns"
    )
```

### Phase 4: Dual-Speed Implementation (New)

| Task | Effort | Impact | Description |
|------|--------|--------|-------------|
| Escalation Detector | Low | High | Determine when to defer to slow system |
| Filler Library | Low | Medium | Pre-recorded acknowledgments for fast response |
| Pattern Cache | Medium | High | Vector DB for learned fast responses |
| Cognitive Orchestrator | High | Transformative | Central hub coordinating both systems |
| Pattern Compiler | Medium | High | Slow system → Fast system pattern transfer |
| Animation Mixer | Medium | Medium | Priority-based animation blending |

---

## Conclusion

These four MCP servers represent different facets of AI agent expression:

- **Voice** (ElevenLabs) - How it sounds
- **Body** (Virtual Character) - How it moves
- **Visual** (Reaction Search) - How it appears in text
- **Mind** (Memory) - What it remembers

The **Dual-Speed Cognitive Architecture** adds a fifth dimension:

- **Two Minds** (Fast + Slow) - How it thinks

By creating a unified emotion taxonomy, memory-enhanced preferences, orchestrated multi-modal expression, and dual-speed cognition, we transform four separate tools into a **coherent expressive personality system with authentic cognitive presence**.

### Key Insights

1. **Emotional coherence across modalities** creates authenticity. When an agent sounds happy, looks happy, uses happy reactions, and remembers that happiness - it feels genuine rather than mechanical.

2. **Immediate presence matters**. A 5-second pause before any response feels unnatural. The fast system provides instant acknowledgment while the slow system prepares thoughtful responses.

3. **Learning compounds**. The slow system's pattern compilation means the fast system gets smarter over time. Frequent interactions become reflexive.

4. **Memory bridges sessions**. Expression patterns persist across conversations, creating personality continuity.

### Recommended Implementation Order

**Phase 1: Foundation** (enables everything else) ✅ PARTIALLY COMPLETE
1. ✅ `mcp_virtual_character/models/canonical.py` - EmotionType, EmotionVector (PAD model), blending
2. Add emotion mapping utilities (`mcp_virtual_character/emotions/mappings.py`)
3. Test with a simple workflow that expresses the same emotion across all three output modalities

**Phase 2: Memory Integration** (personality persistence)
1. Define personality namespaces in AgentCore Memory
2. Implement preference storage/retrieval patterns
3. Add reaction history tracking

**Phase 3: Orchestration** (unified expression)
1. Build ExpressionOrchestrator for multi-modal coordination
2. Integrate with Virtual Character sequences
3. Add GitHub PR integration for audio + reaction comments

**Phase 4: Dual-Speed Cognition** (cognitive presence)
1. Implement EscalationDetector for fast→slow handoff
2. Build filler library for immediate acknowledgments
3. Create pattern cache and compilation pipeline
4. Build Cognitive Orchestrator for parallel processing

This progression builds each layer on the previous, with each phase delivering standalone value while enabling the next.

---

## Appendix A: Model Specifications & Benchmarks

### Embedding Models Comparison

| Model | Params | Size | Embed Dim | Speed vs L12 | MTEB Avg | Best For |
|-------|--------|------|-----------|--------------|----------|----------|
| **all-MiniLM-L12-v2** (current) | 33.4M | 120MB | 384 | 1x (baseline) | ~57 | Quality-focused search |
| **all-MiniLM-L6-v2** | 22.7M | 80MB | 384 | ~2x faster | ~56 | Balanced speed/quality |
| **all-mpnet-base-v2** | 109M | 420MB | 768 | 0.2x (slower) | ~63 | Maximum quality |
| **Model2Vec potion-base-32M** | Static | 32MB | 256 | **500x faster** | ~51 | Ultra-fast inference |
| **Model2Vec potion-retrieval-32M** | Static | 32MB | 256 | **500x faster** | ~50 | Fast retrieval tasks |
| **static-retrieval-mrl-en-v1** | Static | ~30MB | 256 | **400x faster** | ~50 | Sentence Transformers native |

### Speed vs Quality Tradeoff

```
Quality (MTEB Score)
    │
 63 │                                        ● all-mpnet-base-v2 (109M)
    │
 57 │            ● all-MiniLM-L12-v2 (33M) ← CURRENT (Slow System)
    │
 56 │        ● all-MiniLM-L6-v2 (23M)
    │
 51 │● Model2Vec potion-32M (32MB) ← RECOMMENDED (Fast System)
    │
    └──────────────────────────────────────────────────────────────► Speed
        500x        2x         1x        0.2x
       faster    faster    baseline    slower
```

### Emotion Classification Models

| Model | Architecture | Size | Speed | Classes | Accuracy |
|-------|--------------|------|-------|---------|----------|
| **distilbert-base-uncased-emotion** | DistilBERT | 250MB | 398 samples/sec | 6 | 93.8% |
| **j-hartmann/emotion-english-distilroberta-base** | DistilRoBERTa | 330MB | ~300 samples/sec | 7 (Ekman+neutral) | ~95% |
| **Panda0116/emotion-classification-model** | DistilBERT | 250MB | 398 samples/sec | 6 | ~92% |

**Emotion Classes** (distilbert-base-uncased-emotion):
- sadness (0), joy (1), love (2), anger (3), fear (4), surprise (5)

**Mapping to Canonical Emotions**:
```python
EMOTION_MAPPING = {
    0: CanonicalEmotion.SADNESS,      # sadness
    1: CanonicalEmotion.JOY,          # joy
    2: CanonicalEmotion.JOY,          # love → joy (high intensity)
    3: CanonicalEmotion.ANGER,        # anger
    4: CanonicalEmotion.FEAR,         # fear
    5: CanonicalEmotion.SURPRISE,     # surprise
}
```

### LLM Models for Filler Generation

| Model | Params | Provider | Latency | Cost | Best For |
|-------|--------|----------|---------|------|----------|
| **Llama 3.2 1B** | 1B | OpenRouter | ~50ms | $0.01/M tokens | Ultra-fast fillers |
| **Llama 3.2 3B** | 3B | OpenRouter | ~100ms | $0.02/M tokens | Smarter fillers |
| **Gemma 2 2B** | 2B | OpenRouter | ~80ms | $0.01/M tokens | Quality fillers |
| **GPT-5.2 Chat (Instant)** | - | OpenRouter | Low | $$ | Adaptive reasoning |

**OpenRouter Routing Tips**:
- Use `:nitro` suffix for fastest throughput
- Use `:floor` suffix for lowest price
- ~25-40ms added latency from OpenRouter edge

### Deep Reasoning Models (Slow System)

| Model | Provider | Latency | Cost | Best For |
|-------|----------|---------|------|----------|
| **Claude Opus 4.5** | Anthropic | 5-30s | $$$ | Primary reasoner (all cognitive tasks) |
| **Claude Sonnet 4.5** | Anthropic | 2-5s | $$ | Faster alternative if latency critical |
| **Gemma 2 9B** | OpenRouter | 2-10s | $ | Cost-effective fallback |
| **MiniMax M2** | OpenRouter | 2-8s | $$ | Near-frontier, efficient |

---

## Appendix B: Migration Guide

### Reaction Search: L12-v2 → Model2Vec

**Current Implementation** (`mcp_reaction_search/search_engine.py`):
```python
# Current: all-MiniLM-L12-v2
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L12-v2"
```

**Option 1: Environment Variable (No Code Changes)**
```bash
# Already supported via os.getenv()
REACTION_SEARCH_MODEL=minishlab/potion-retrieval-32M python -m mcp_reaction_search.server
```

**Option 2: Dual-Model Architecture**
```python
class DualSpeedSearchEngine:
    """Fast + Slow embedding search"""

    def __init__(self):
        # Fast: Model2Vec for immediate responses
        from model2vec import StaticModel
        self.fast_model = StaticModel.from_pretrained("minishlab/potion-retrieval-32M")

        # Slow: MiniLM for quality validation
        from sentence_transformers import SentenceTransformer
        self.slow_model = SentenceTransformer("sentence-transformers/all-MiniLM-L12-v2")

    def fast_search(self, query: str) -> List[ReactionResult]:
        """~0.02ms per query"""
        embedding = self.fast_model.encode([query])[0]
        return self._similarity_search(embedding, self.fast_embeddings)

    def slow_validate(self, query: str, candidates: List[str]) -> List[ReactionResult]:
        """~15ms - validates fast results with higher quality model"""
        embedding = self.slow_model.encode([query])[0]
        return self._rerank(embedding, candidates)
```

### Emotion Classification Integration

**New Component** (`mcp_virtual_character/emotions/classifier.py`):
```python
from transformers import pipeline

class FastEmotionClassifier:
    """DistilBERT-based emotion classification (~2.5ms/sample)"""

    def __init__(self):
        self.classifier = pipeline(
            "text-classification",
            model="bhadresh-savani/distilbert-base-uncased-emotion",
            top_k=1
        )
        self.label_to_emotion = {
            "sadness": (CanonicalEmotion.SADNESS, 0.6),
            "joy": (CanonicalEmotion.JOY, 0.6),
            "love": (CanonicalEmotion.JOY, 0.9),  # High intensity joy
            "anger": (CanonicalEmotion.ANGER, 0.6),
            "fear": (CanonicalEmotion.FEAR, 0.6),
            "surprise": (CanonicalEmotion.SURPRISE, 0.6),
        }

    def classify(self, text: str) -> tuple[CanonicalEmotion, float]:
        """Classify text emotion in ~2.5ms"""
        result = self.classifier(text)[0][0]
        emotion, base_intensity = self.label_to_emotion[result["label"]]
        # Scale intensity by confidence
        intensity = base_intensity * result["score"]
        return emotion, intensity
```

### Filler Generation with Llama 3.2 1B

**New Component** (`mcp_virtual_character/fillers/generator.py`):
```python
import httpx

class FillerGenerator:
    """Generate contextual fillers via OpenRouter (~50ms)"""

    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient()

    async def generate(self, emotion: CanonicalEmotion, context: str) -> str:
        """Generate a non-committal filler acknowledgment"""
        response = await self.client.post(
            self.OPENROUTER_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": "meta-llama/llama-3.2-1b-instruct:nitro",  # :nitro for speed
                "messages": [{
                    "role": "system",
                    "content": f"Generate a brief, non-committal acknowledgment. Emotion: {emotion.name}. Be concise (3-8 words). No promises or commitments."
                }, {
                    "role": "user",
                    "content": context[:100]
                }],
                "max_tokens": 20,
                "temperature": 0.7
            }
        )
        return response.json()["choices"][0]["message"]["content"]
```

---

## Appendix C: Latency Budget

### Fast System Target: < 100ms Total

| Stage | Component | Target | Model |
|-------|-----------|--------|-------|
| 1 | Emotion Classification | 3ms | distilbert-base-uncased-emotion |
| 2 | Pattern Cache Lookup | 5ms | Local vector DB |
| 3 | Reaction Search | 1ms | Model2Vec potion-retrieval-32M |
| 4 | Avatar Expression Set | 5ms | Direct OSC/WebSocket |
| 5 | Filler TTS Start | 75ms | ElevenLabs Flash v2.5 |
| **Total** | | **~89ms** | |

### Slow System: 5-30s (Background)

| Stage | Component | Expected | Model |
|-------|-----------|----------|-------|
| 1 | Memory Query | 200ms | AgentCore semantic search |
| 2 | Quality Embedding | 15ms | all-MiniLM-L12-v2 |
| 3 | Primary Reasoning | 5-30s | Claude Opus 4.5 |
| 4 | Pattern Compilation | N/A | Batch during idle/"sleep" cycles |

**Note**: The 5-30s Opus latency is masked by System 1's Active Listening behaviors (nods, gaze shifts, fillers). Users perceive an immediately responsive agent even while deep reasoning occurs in the background.

---

## Appendix D: Dependencies

### Fast System Requirements

```txt
# requirements-fast.txt
model2vec>=0.3.0              # Static embeddings (500x faster)
transformers>=4.30.0          # Emotion classification
torch>=2.0.0                  # PyTorch backend
httpx>=0.24.0                 # Async HTTP for OpenRouter
```

### Slow System Requirements

```txt
# requirements-slow.txt
sentence-transformers>=2.2.0  # Quality embeddings (L12-v2)
anthropic>=0.18.0             # Claude API
openai>=1.0.0                 # OpenRouter compatibility
```

### Model Download Sizes

| Model | Download Size | First Load Time |
|-------|---------------|-----------------|
| Model2Vec potion-retrieval-32M | 32MB | ~1s |
| distilbert-base-uncased-emotion | 250MB | ~3s |
| all-MiniLM-L12-v2 | 120MB | ~2s |
| Llama 3.2 1B | API (no download) | N/A |

---

## Appendix E: References

### Embedding Models
- [Model2Vec GitHub](https://github.com/MinishLab/model2vec) - Fast static embeddings
- [Model2Vec: 50x Smaller, 500x Faster](https://huggingface.co/blog/Pringled/model2vec) - Hugging Face blog
- [Sentence Transformers Static Embeddings](https://huggingface.co/blog/static-embeddings) - Official docs
- [all-MiniLM-L12-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2) - Current model
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard) - Benchmark comparisons

### Emotion Classification
- [distilbert-base-uncased-emotion](https://huggingface.co/bhadresh-savani/distilbert-base-uncased-emotion) - Fast emotion model
- [j-hartmann/emotion-english-distilroberta-base](https://huggingface.co/j-hartmann/emotion-english-distilroberta-base) - 7-class alternative

### LLM Providers
- [OpenRouter Models](https://openrouter.ai/models) - Multi-provider gateway
- [Llama 3.2 1B on OpenRouter](https://openrouter.ai/meta-llama/llama-3.2-1b-instruct) - Fast filler generation
- [Gemma 2 Performance](https://artificialanalysis.ai/models/gemma-2-9b) - Benchmark data

### Cognitive Architecture
- Kahneman, D. (2011). *Thinking, Fast and Slow* - System 1/System 2 framework
- [Gemini Consultation](https://openrouter.ai/) - Dual-speed architecture review
