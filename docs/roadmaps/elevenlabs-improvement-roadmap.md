# ElevenLabs MCP Improvement Plan for Virtual Character Integration

**Status: IMPLEMENTED** (December 2025)

## Executive Summary

This plan addressed gaps between the ElevenLabs MCP implementation and official API capabilities, focusing on **low-latency streaming for real-time virtual character animation**. The goal was to achieve **<100ms time-to-first-audio** for responsive character interactions.

**Note**: Timestamp/alignment features were intentionally excluded since VRChat's automatic lip-sync system provides excellent results without manual viseme data.

---

## Current State Analysis

### What We Have (Strengths)

| Feature | Status | Notes |
|---------|--------|-------|
| v3 model support | Excellent | Full audio tag support ([laughs], [whisper], etc.) |
| Async-first architecture | Good | httpx.AsyncClient with 60s timeout |
| WebSocket streaming | Partial | Exists but not optimized for latency |
| Audio format support | Good | MP3, PCM, ulaw variants |
| Virtual character integration | Good | Storage service, seamless audio flow |
| Voice presets | Excellent | 10+ presets for different use cases |
| Metadata tracking | Excellent | Comprehensive synthesis metadata |

### Critical Gaps Identified

| Gap | Severity | Impact |
|-----|----------|--------|
| No timestamps/alignment data | HIGH | Lip-sync requires pre-extracted viseme data |
| WebSocket not using Flash models | HIGH | Using Turbo v2.5, not Flash v2.5 (75ms latency) |
| Missing `auto_mode` for WebSocket | HIGH | Manual chunk scheduling increases latency |
| No regional endpoint support | MEDIUM | US-only, EU/Asia users get 200-350ms added |
| Missing HTTP streaming endpoint | MEDIUM | WebSocket-only streaming currently |
| No `optimize_streaming_latency` param | LOW | Deprecated but still useful for v2 models |
| Speed parameter missing | LOW | New 0.7-1.2x speed control not exposed |

---

## Improvement Plan

### Phase 1: Low-Latency Streaming (Priority: CRITICAL)

**Goal**: Achieve <100ms time-to-first-audio for virtual character responses

#### 1.1 Add Flash v2.5 Model for Streaming
```python
# In voice_settings.py - Add Flash model as streaming default
VoiceModel.ELEVEN_FLASH_V2_5 = "eleven_flash_v2_5"  # 75ms latency

# In StreamConfig - Change default
class StreamConfig:
    model: VoiceModel = VoiceModel.ELEVEN_FLASH_V2_5  # Was TURBO_V2_5
```

**Rationale**: Flash v2.5 delivers ~75ms inference speed vs. ~150ms for Turbo models.

#### 1.2 Implement `auto_mode` for WebSocket
```python
# In client.py - WebSocket connection
async def synthesize_with_websocket_v2(self, config: StreamConfig) -> AsyncGenerator[bytes, None]:
    """Optimized streaming with auto_mode"""
    ws_url = f"{self.WS_URL}/{config.voice_id}/stream-input"
    params = {
        "model_id": config.model.value,
        "auto_mode": "true",  # NEW: Automatic generation triggers
        "output_format": config.output_format.value,
    }
```

**Rationale**: `auto_mode` removes manual chunk scheduling overhead, allowing the API to automatically trigger audio generation.

#### 1.3 Add Regional Endpoint Support
```python
# In client.py
REGIONAL_ENDPOINTS = {
    "us": "wss://api.elevenlabs.io/v1",
    "eu": "wss://api.eu.residency.elevenlabs.io/v1",
    "global": "wss://api-global-preview.elevenlabs.io/v1",  # 80-100ms EU/Japan
}
```

**Rationale**: Regional routing can reduce TTFB by 100-150ms for non-US users.

#### 1.4 Add HTTP Streaming Endpoint
```python
async def stream_speech_http(self, config: SynthesisConfig) -> AsyncGenerator[bytes, None]:
    """HTTP streaming for when full text is available upfront"""
    url = f"{self.BASE_URL}/text-to-speech/{config.voice_id}/stream"
    async with self.client.stream("POST", url, json=payload) as response:
        async for chunk in response.aiter_bytes():
            yield chunk
```

**Rationale**: HTTP streaming is actually **faster** than WebSocket when full text is available upfront (no buffering overhead).

---

### Phase 2: Timestamp/Alignment Support (Priority: HIGH)

**Goal**: Enable frame-perfect lip-sync for virtual characters

#### 2.1 Add `/with-timestamps` Endpoint Support
```python
# New model for alignment data
@dataclass
class CharacterAlignment:
    characters: List[str]
    character_start_times_seconds: List[float]
    character_end_times_seconds: List[float]

@dataclass
class SynthesisResultWithTimestamps(SynthesisResult):
    alignment: Optional[CharacterAlignment] = None
    normalized_alignment: Optional[CharacterAlignment] = None

# New method in client.py
async def synthesize_with_timestamps(self, config: SynthesisConfig) -> SynthesisResultWithTimestamps:
    """Synthesize speech with character-level alignment data for lip-sync"""
    url = f"{self.BASE_URL}/text-to-speech/{config.voice_id}/with-timestamps"
    response = await self.client.post(url, json=payload)
    # Parse audio_base64 and alignment data
```

**Rationale**: Character timestamps enable precise viseme generation. Currently, VRChat does auto lip-sync, but this gives us frame-perfect control.

#### 2.2 Derive Word-Level Timing
```python
def derive_word_timing(alignment: CharacterAlignment) -> List[Tuple[str, float, float]]:
    """Convert character alignment to word-level timing"""
    words = []
    current_word = ""
    word_start = 0.0

    for i, char in enumerate(alignment.characters):
        if char == " " or i == len(alignment.characters) - 1:
            if current_word:
                words.append((
                    current_word,
                    word_start,
                    alignment.character_end_times_seconds[i-1]
                ))
            current_word = ""
            word_start = alignment.character_start_times_seconds[i+1] if i+1 < len(alignment.characters) else 0
        else:
            if not current_word:
                word_start = alignment.character_start_times_seconds[i]
            current_word += char

    return words
```

#### 2.3 WebSocket Alignment Data Integration
```python
# Enable sync_alignment in WebSocket params
params = {
    "sync_alignment": "true",  # NEW: Get alignment with each audio chunk
    # ...
}

# Parse alignment from response
if "alignment" in response:
    alignment = CharacterAlignment(
        characters=response["alignment"]["chars"],
        character_start_times_seconds=[
            ms / 1000 for ms in response["alignment"]["charStartTimesMs"]
        ],
        # Note: durations need conversion to end times
    )
```

---

### Phase 3: Virtual Character Integration Enhancements (Priority: MEDIUM)

#### 3.1 Direct ElevenLabs-to-VirtualCharacter Pipeline
```python
# New tool: synthesize_and_animate
async def synthesize_and_animate(
    text: str,
    voice_id: str,
    character_backend: str = "vrchat",
    emotion_from_tags: bool = True
) -> dict:
    """Generate speech and send directly to virtual character with timing"""

    # 1. Synthesize with timestamps
    result = await synthesize_with_timestamps(config)

    # 2. Extract visemes from alignment
    visemes = derive_visemes_from_alignment(result.alignment)

    # 3. Send to virtual character in single call
    await virtual_character.play_audio(
        audio_data=result.local_path,
        viseme_timestamps=visemes,
        expression_tags=extract_tags(text)
    )
```

#### 3.2 Streaming Audio to Virtual Character
```python
async def stream_to_character(config: StreamConfig, backend: str):
    """Stream audio chunks directly to virtual character as they're generated"""

    async for audio_chunk, alignment_chunk in synthesize_stream_with_alignment(config):
        # Send chunk immediately - don't wait for full audio
        await virtual_character.send_audio_chunk(
            audio_data=audio_chunk,
            chunk_index=chunk_index,
            is_final=is_final
        )
```

**Rationale**: Start playback while still generating - reduces perceived latency significantly.

---

### Phase 4: Model & Format Optimization (Priority: LOW)

#### 4.1 Add Speed Parameter
```python
@dataclass
class VoiceSettings:
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = False
    speed: float = 1.0  # NEW: 0.7 to 1.2
```

#### 4.2 Add Opus Format Support
```python
class OutputFormat(Enum):
    # ... existing formats
    OPUS_48000_32 = "opus_48000_32"    # Low bandwidth
    OPUS_48000_64 = "opus_48000_64"    # Balanced
    OPUS_48000_128 = "opus_48000_128"  # High quality
```

**Rationale**: Opus offers better quality/size ratio than MP3 for speech.

#### 4.3 Add PCM Streaming Preference
For virtual characters, PCM is ideal (no decompression needed):
```python
class StreamConfig:
    output_format: OutputFormat = OutputFormat.PCM_24000  # Change default for streaming
```

---

## Implementation Priority Matrix

| Phase | Tasks | Effort | Impact | Priority |
|-------|-------|--------|--------|----------|
| 1.1 | Flash v2.5 default | Low | High | P0 |
| 1.2 | auto_mode WebSocket | Low | High | P0 |
| 1.3 | Regional endpoints | Medium | Medium | P1 |
| 1.4 | HTTP streaming | Medium | Medium | P1 |
| 2.1 | /with-timestamps | Medium | High | P0 |
| 2.2 | Word-level timing | Low | Medium | P1 |
| 2.3 | WebSocket alignment | Medium | High | P0 |
| 3.1 | Direct pipeline | High | High | P1 |
| 3.2 | Stream to character | High | High | P1 |
| 4.1 | Speed parameter | Low | Low | P2 |
| 4.2 | Opus format | Low | Low | P2 |
| 4.3 | PCM streaming default | Low | Medium | P1 |

---

## Expected Latency Improvements

| Scenario | Current | After Phase 1 | After Phase 2 |
|----------|---------|---------------|---------------|
| First audio chunk (US) | ~200ms | ~100ms | ~80ms |
| First audio chunk (EU) | ~350ms | ~150ms | ~120ms |
| Full synthesis (short text) | ~500ms | ~300ms | ~250ms |
| Lip-sync start | Variable (VRChat auto) | ~100ms (with alignment) | ~50ms (streaming) |

---

## Files to Modify

### Phase 1
- `tools/mcp/mcp_elevenlabs_speech/models/voice_settings.py` - Add speed param, update defaults
- `tools/mcp/mcp_elevenlabs_speech/models/synthesis_config.py` - Add regional endpoint config
- `tools/mcp/mcp_elevenlabs_speech/mcp_elevenlabs_speech/client.py` - New streaming methods

### Phase 2
- `tools/mcp/mcp_elevenlabs_speech/models/synthesis_config.py` - Add alignment models
- `tools/mcp/mcp_elevenlabs_speech/mcp_elevenlabs_speech/client.py` - Add /with-timestamps
- `tools/mcp/mcp_elevenlabs_speech/mcp_elevenlabs_speech/server.py` - New tools

### Phase 3
- `tools/mcp/mcp_virtual_character/src/server.rs` - Integration tools (Rust)
- `tools/mcp/mcp_elevenlabs_speech/mcp_elevenlabs_speech/server.py` - Direct pipeline

---

## Important Notes

1. **WebSockets NOT available for eleven_v3 model** - Use Flash/Turbo for streaming, v3 for quality synthesis
2. **Regional endpoints are preview** - `api-global-preview.elevenlabs.io` offers best non-US latency
3. **Alignment is chunk-relative** - When using WebSocket streaming, timestamps are per-chunk, not global

---

## Sources

- [ElevenLabs Stream Speech API](https://elevenlabs.io/docs/api-reference/text-to-speech/stream)
- [ElevenLabs WebSocket API](https://elevenlabs.io/docs/api-reference/text-to-speech/v-1-text-to-speech-voice-id-stream-input)
- [ElevenLabs Latency Optimization](https://elevenlabs.io/docs/developers/best-practices/latency-optimization)
- [ElevenLabs Python SDK](https://github.com/elevenlabs/elevenlabs-python)
- [ElevenLabs TTS with Timestamps](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps)
