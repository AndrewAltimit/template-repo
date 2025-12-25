# Emotions Module

The emotions module provides a canonical emotion taxonomy for unified expression across MCP servers. It enables consistent emotional representation between ElevenLabs Speech, Virtual Character, Reaction Search, and other expressive AI systems.

## Overview

The module consists of three main components:

1. **Taxonomy** (`emotions/taxonomy.py`) - Core emotion definitions and PAD model
2. **Mappings** (`emotions/mappings.py`) - Bidirectional mappings between systems
3. **Inference** (`emotions/inference.py`) - Emotion detection from text

## Canonical Emotions

The taxonomy defines 14 primary emotions with intensity support (0.0 to 1.0):

| Emotion | Description | Example Intensities |
|---------|-------------|---------------------|
| `JOY` | Happiness, pleasure | 0.3: pleased, 0.6: happy, 1.0: ecstatic |
| `SADNESS` | Sorrow, grief | 0.3: disappointed, 0.6: sad, 1.0: devastated |
| `ANGER` | Frustration, rage | 0.3: annoyed, 0.6: angry, 1.0: furious |
| `FEAR` | Anxiety, terror | 0.3: nervous, 0.6: anxious, 1.0: terrified |
| `SURPRISE` | Amazement, shock | 0.3: curious, 0.6: surprised, 1.0: astonished |
| `DISGUST` | Revulsion | 0.3: distaste, 0.6: disgusted, 1.0: revolted |
| `CONTEMPT` | Disdain, scorn | 0.3: dismissive, 0.6: contemptuous, 1.0: scornful |
| `CONFUSION` | Uncertainty | 0.3: puzzled, 0.6: confused, 1.0: bewildered |
| `CALM` | Peace, serenity | 0.3: relaxed, 0.6: calm, 1.0: serene |
| `THINKING` | Contemplation | 0.3: pondering, 0.6: thinking, 1.0: deep thought |
| `SMUG` | Self-satisfaction | 0.3: pleased, 0.6: smug, 1.0: triumphant |
| `EMBARRASSMENT` | Self-consciousness | 0.3: shy, 0.6: embarrassed, 1.0: mortified |
| `ATTENTIVE` | Focused listening | 0.3: interested, 0.6: attentive, 1.0: engrossed |
| `BORED` | Disengagement | 0.3: uninterested, 0.6: bored, 1.0: completely disengaged |

## PAD Model (Dimensional Emotions)

Underneath discrete categories, emotions are represented as 3D vectors using the PAD (Pleasure, Arousal, Dominance) model:

```python
from mcp_core.emotions import EmotionVector, CanonicalEmotion, EMOTION_TO_PAD

# Get PAD vector for an emotion
joy_vector = EMOTION_TO_PAD[CanonicalEmotion.JOY]
# EmotionVector(pleasure=0.8, arousal=0.6, dominance=0.2)

# Interpolate between emotions for smooth transitions
calm = EMOTION_TO_PAD[CanonicalEmotion.CALM]
excited = EMOTION_TO_PAD[CanonicalEmotion.JOY]
halfway = calm.lerp(excited, 0.5)  # Blend 50%

# Find closest discrete emotion from a PAD vector
emotion = find_closest_emotion(halfway)
```

**PAD Dimensions:**
- **Pleasure** (-1 to +1): Negative/unhappy to positive/happy
- **Arousal** (-1 to +1): Calm/relaxed to excited/energetic
- **Dominance** (-1 to +1): Submissive/controlled to dominant/controlling

**Benefits:**
- Smooth interpolation between emotions (no jarring "snaps")
- Mathematical blending of conflicting signals
- Direct mapping to animation blend shapes
- Intensity-aware expression

## Emotion Mappings

The mappings module provides bidirectional translation between systems:

### ElevenLabs Audio Tags

```python
from mcp_core.emotions import get_audio_tags_for_emotion, CanonicalEmotion

# Get appropriate audio tags for an emotion
tags = get_audio_tags_for_emotion(CanonicalEmotion.JOY, intensity=0.8)
# ["[laughs]", "[excited]"]

tags = get_audio_tags_for_emotion(CanonicalEmotion.SADNESS, intensity=0.6)
# ["[sighs]", "[somber]"]
```

### Virtual Character Emotions

```python
from mcp_core.emotions import emotion_to_avatar, CanonicalEmotion

# Map to Virtual Character emotion
avatar_config = emotion_to_avatar(CanonicalEmotion.JOY)
# {"emotion": "happy", "gesture": "cheer"}

avatar_config = emotion_to_avatar(CanonicalEmotion.THINKING)
# {"emotion": "neutral", "gesture": "thinking"}
```

### Reaction Search Queries

```python
from mcp_core.emotions import emotion_to_reaction_query, CanonicalEmotion

# Generate semantic search query
query = emotion_to_reaction_query(
    CanonicalEmotion.JOY,
    intensity=0.8,
    context="fixed a bug"
)
# "excited celebrating fixed a bug"
```

### Text Analysis

```python
from mcp_core.emotions import extract_emotions_from_text

# Extract emotions from ElevenLabs-style tagged text
emotions = extract_emotions_from_text("[laughs] That's hilarious! [excited]")
# [(CanonicalEmotion.JOY, 0.7), (CanonicalEmotion.JOY, 0.8)]
```

## Emotion Inference

The inference module detects emotions from plain text:

### Rule-Based Inference (Fast)

```python
from mcp_core.emotions import infer_emotion

# Infer emotion from text patterns
result = infer_emotion("I can't believe this worked!")
# InferenceResult(
#     primary_emotion=CanonicalEmotion.SURPRISE,
#     intensity=0.7,
#     confidence=0.6,
#     method="rule"
# )

# Convert to EmotionState for use with other modules
state = result.to_emotion_state()
```

### ML-Based Classification (Optional)

Requires `transformers` package:

```python
from mcp_core.emotions.inference import MLEmotionClassifier

classifier = MLEmotionClassifier()
if classifier.is_available:
    result = classifier.classify("I'm so frustrated with this bug!")
    # InferenceResult with higher confidence
```

### Hybrid Inference

Combines rule-based and ML approaches:

```python
from mcp_core.emotions.inference import infer_emotion_hybrid

result = infer_emotion_hybrid(
    text="Finally! After hours of debugging, it works!",
    use_ml=True
)
# Uses both methods, combines results for higher confidence
```

### Context-Aware Inference

Maintains conversation context for better accuracy:

```python
from mcp_core.emotions.inference import ContextAwareEmotionInference

inferrer = ContextAwareEmotionInference(context_window=5)

# Track conversation
inferrer.add_message("user", "This bug is driving me crazy")
inferrer.add_message("assistant", "Let me help debug that")
inferrer.add_message("user", "Oh! I found the issue!")

# Infer with context
result = inferrer.infer_with_context("It's working now!")
# Understands the emotional arc: frustration -> relief -> joy
```

## EmotionState

The `EmotionState` dataclass captures a complete emotional moment:

```python
from mcp_core.emotions import EmotionState, CanonicalEmotion

state = EmotionState(
    emotion=CanonicalEmotion.JOY,
    intensity=0.8,
    secondary_emotion=CanonicalEmotion.SURPRISE,
    secondary_intensity=0.4,
    context="Bug fix celebration"
)

# Get PAD vector
vector = state.to_vector()

# Blend with another state
calm_state = EmotionState(emotion=CanonicalEmotion.CALM)
blended = state.blend(calm_state, weight=0.3)
```

## Integration Example

Complete example using all components:

```python
from mcp_core.emotions import (
    CanonicalEmotion,
    EmotionState,
    infer_emotion,
    get_audio_tags_for_emotion,
    emotion_to_avatar,
    emotion_to_reaction_query,
)

# 1. Infer emotion from user message
text = "Finally got the tests passing after 3 hours!"
result = infer_emotion(text)

# 2. Create emotion state
state = EmotionState(
    emotion=result.primary_emotion,  # JOY
    intensity=result.intensity,       # ~0.8
    context=text
)

# 3. Get expression for each modality
audio_tags = get_audio_tags_for_emotion(state.emotion, state.intensity)
# ["[laughs]", "[excited]", "[relieved]"]

avatar_config = emotion_to_avatar(state.emotion)
# {"emotion": "happy", "gesture": "cheer"}

reaction_query = emotion_to_reaction_query(
    state.emotion,
    state.intensity,
    "tests passing"
)
# "excited relieved tests passing celebration"

# 4. Use with MCP servers
# - ElevenLabs: synthesize_speech(text=f"{' '.join(audio_tags)} {text}")
# - Virtual Character: send_animation(**avatar_config)
# - Reaction Search: search_reactions(query=reaction_query)
```

## API Reference

### taxonomy.py

| Class/Function | Description |
|----------------|-------------|
| `CanonicalEmotion` | Enum of 14 primary emotions |
| `EmotionVector` | PAD model 3D vector with lerp, distance, scale |
| `EmotionState` | Complete emotional state with context |
| `EMOTION_TO_PAD` | Dict mapping emotions to PAD vectors |
| `find_closest_emotion(vector)` | Find nearest discrete emotion |
| `blend_emotions(emotions, weights)` | Weighted blend of multiple emotions |

### mappings.py

| Function | Description |
|----------|-------------|
| `get_audio_tags_for_emotion(emotion, intensity)` | Get ElevenLabs audio tags |
| `emotion_to_avatar(emotion)` | Get Virtual Character config |
| `emotion_to_reaction_query(emotion, intensity, context)` | Generate search query |
| `extract_emotions_from_text(text)` | Parse emotions from tagged text |

### inference.py

| Class/Function | Description |
|----------------|-------------|
| `infer_emotion(text)` | Rule-based emotion inference |
| `MLEmotionClassifier` | Optional ML-based classification |
| `infer_emotion_hybrid(text, use_ml)` | Combined inference |
| `ContextAwareEmotionInference` | Context-tracking inference |
| `InferenceResult` | Result dataclass with confidence |

## See Also

- [Expression Module](EXPRESSION.md) - Multi-modal expression orchestration
- [MCP Integration Proposal](../../../docs/proposals/mcp-integration-proposal.md) - Full architecture vision including Phase 4: Dual-Speed Cognition
