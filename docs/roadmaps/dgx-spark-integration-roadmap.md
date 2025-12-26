# DGX Spark Integration Proposal: Hybrid Cognitive Architecture

**Status**: Planning (Hardware ETA: ~1 week)
**Created**: 2025-12-25
**Author**: Claude Code + Human

---

## Executive Summary

This proposal outlines the integration of an NVIDIA DGX Spark workstation as a **dedicated GPU inference server** to accelerate the cognitive architecture's real-time processing pipeline.

| Component | Role |
|-----------|------|
| **Claude API (Opus 4.5)** | Primary reasoning brain - analysis, insights, long-term thinking |
| **DGX Spark (Local GPU)** | Fast real-time processing - emotion, fillers, audio styling |
| **ElevenLabs** | Voice synthesis with expression tags |
| **Virtual Character** | Embodied avatar delivery |

**The Vision**: Sub-500ms immediate reactions while Claude thinks deeply, creating natural conversational flow with a virtual character.

---

## Hardware Overview

**NVIDIA DGX Spark (GB10 Blackwell)**:
- GB10 ARM Processor + GB10 Blackwell GPU
- 128 GB unified LPDDR5x memory
- 1 TB NVMe SSD
- 10GbE networking

## Architecture: Hybrid Intelligence Model

**Key Insight**: Claude API (Opus 4.5) remains the primary reasoning brain for analysis, insights, and long-term thinking. The DGX Spark handles **fast, real-time processing** that feeds into the audio/character pipeline.

```
┌────────────────────────────────────────────────────────────────────┐
│                    HYBRID COGNITIVE ARCHITECTURE                    │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   SLOW PATH (Quality)              FAST PATH (Real-time)           │
│   ─────────────────────           ──────────────────────           │
│   Claude API (Opus 4.5)           DGX Spark (Local GPU)            │
│   • Deep analysis                 • Emotion inference (<20ms)      │
│   • Complex reasoning             • Filler/thinking phrases        │
│   • Long-term planning            • Audio tag styling              │
│   • Insights & synthesis          • Pattern matching               │
│                                   • Real-time reactions            │
│            │                                │                       │
│            │ (formulated response)          │ (immediate reaction)  │
│            ▼                                ▼                       │
│   ┌────────────────────────────────────────────────────────┐       │
│   │              Audio Pipeline (ElevenLabs)                │       │
│   │  • Style with audio tags  • Convert to speech           │       │
│   │  • Send to Virtual Character                            │       │
│   └────────────────────────────────────────────────────────┘       │
└────────────────────────────────────────────────────────────────────┘
```

The DGX Spark will run as a **dedicated inference server** on the local network, accessed via HTTP by other machines.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Dev Machine                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Claude Code / MCP Clients                                │   │
│  │    ├── mcp_core/cognition (FastMind, SlowMind)           │   │
│  │    ├── Other MCP servers (code-quality, etc.)            │   │
│  │    └── .mcp.json configuration                            │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │ HTTP (10GbE LAN)                  │
└──────────────────────────────┼───────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────┐
│                      DGX Spark (192.168.x.x)                     │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  mcp_inference (Port 8024) - Unified Inference Server     │   │
│  │    ├── /infer/emotion      → GPU emotion classification   │   │
│  │    ├── /infer/embed        → GPU text embeddings          │   │
│  │    ├── /infer/reason       → Local LLM inference          │   │
│  │    ├── /vectors/search     → FAISS similarity search      │   │
│  │    └── /vectors/store      → Pattern storage              │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Models (pre-downloaded)                                  │   │
│  │    ├── Emotion: distilbert-emotion or similar (~500MB)   │   │
│  │    ├── Embeddings: all-MiniLM-L6-v2 (~90MB)              │   │
│  │    └── LLM: Llama 4 Scout (~50GB quantized)              │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## New MCP Server: mcp_inference

### File Structure

```
tools/mcp/mcp_inference/
├── mcp_inference/
│   ├── __init__.py
│   ├── server.py              # Main MCP server (BaseMCPServer)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── emotion.py         # GPU emotion classifier
│   │   ├── embeddings.py      # GPU embedding model
│   │   └── llm.py             # Local LLM wrapper (vLLM/llama.cpp)
│   ├── vector_store.py        # FAISS integration
│   └── config.py              # Model paths, device config
├── pyproject.toml
├── requirements.txt           # torch, transformers, vllm, faiss-gpu
├── scripts/
│   ├── download_models.sh     # Pre-download models
│   └── test_server.py
├── tests/
│   └── test_inference.py
└── docs/
    └── README.md
```

### Server Implementation

```python
# mcp_inference/server.py
class InferenceMCPServer(BaseMCPServer):
    def __init__(self, port: int = 8024):
        super().__init__(name="Inference Server", version="1.0.0", port=port)
        self._emotion_model = None   # Lazy load
        self._embed_model = None     # Lazy load
        self._llm = None             # Lazy load
        self._vector_store = None    # Lazy load

    def get_tools(self) -> Dict[str, Dict[str, Any]]:
        return {
            "infer_emotion": {...},      # Text → EmotionState
            "generate_embedding": {...}, # Text → List[float]
            "reason": {...},             # Prompt → Response
            "search_patterns": {...},    # Query → Similar patterns
            "store_pattern": {...},      # Pattern → Vector DB
        }
```

### Tools Specification

| Tool | Input | Output | Latency Target |
|------|-------|--------|----------------|
| `infer_emotion` | `text: str` | `EmotionState` JSON | <20ms |
| `generate_embedding` | `text: str` | `List[float]` (384-dim) | <10ms |
| `style_for_audio` | `text, emotion, style` | Styled text with audio tags | <100ms |
| `generate_filler` | `context, emotion` | Thinking phrase | <50ms |
| `search_patterns` | `query: str, top_k: int` | `List[PatternMatch]` | <50ms |
| `store_pattern` | `input: str, output: str` | `pattern_id: str` | <20ms |

**Note**: The `reason` tool exists for lightweight tasks but Claude API (Opus 4.5) remains the primary reasoner for quality.

---

## Integration Points with mcp_core/cognition

### 1. Emotion Inference (FastMind)

**Current**: `mcp_core/emotions/inference.py` - CPU-based, 400-1000ms

**Integration**:
```python
# mcp_core/cognition/fast_mind.py
class FastMind:
    def __init__(
        self,
        inference_url: Optional[str] = None,  # NEW: "http://dgx-spark:8024"
        ...
    ):
        self._inference_url = inference_url or os.getenv("INFERENCE_SERVER_URL")

    async def react(self, input_text: str, ...) -> FastReaction:
        if self._inference_url:
            emotion = await self._infer_emotion_gpu(input_text)  # <20ms
        else:
            emotion = infer_emotion(input_text)  # Fallback to CPU
```

### 2. Pattern Lookup (FastMind)

**Current**: `pattern_lookup: Callable[[str], Awaitable[Optional[str]]]` - string matching

**Integration**:
```python
# Create GPU-backed pattern lookup
async def gpu_pattern_lookup(text: str) -> Optional[str]:
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            f"{INFERENCE_URL}/mcp/execute",
            json={"tool": "search_patterns", "arguments": {"query": text, "top_k": 1}}
        )
        result = await response.json()
        if result["matches"]:
            return result["matches"][0]["pattern"]
        return None

# Pass to orchestrator
orchestrator = CognitiveOrchestrator(pattern_lookup=gpu_pattern_lookup)
```

### 3. SlowMind Reasoner (Claude API - Primary)

**Current**: Abstract `Reasoner` interface - Claude API remains the primary reasoner

**Note**: SlowMind continues to use Claude API (Opus 4.5) for quality reasoning. The local LLM on DGX Spark is NOT for primary reasoning - it's for the audio pipeline.

### 4. Audio Styling Pipeline (NEW - DGX Spark)

**Purpose**: Fast local LLM for styling responses with ElevenLabs audio tags and real-time formatting.

```python
# mcp_core/cognition/audio_styler.py (NEW FILE)
class AudioStyler:
    """GPU-accelerated audio styling via DGX Spark."""

    def __init__(self, inference_url: str):
        self._url = inference_url

    async def style_for_speech(
        self,
        response: str,
        emotion: EmotionState,
        speaking_style: str = "conversational",
    ) -> str:
        """
        Add ElevenLabs audio tags to a response.

        Input: "I think we should try a different approach here."
        Output: "<thoughtful>I think we should try</thoughtful>
                 <pause duration='0.3s'/>
                 <emphasis>a different approach</emphasis> here."
        """
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                f"{self._url}/mcp/execute",
                json={
                    "tool": "style_for_audio",
                    "arguments": {
                        "text": response,
                        "emotion": emotion.emotion.value,
                        "intensity": emotion.intensity,
                        "style": speaking_style,
                    }
                }
            )
            return (await response.json())["styled_text"]

    async def generate_thinking_phrase(
        self,
        context: str,
        emotion: EmotionState,
    ) -> str:
        """Generate a quick thinking/filler phrase for real-time response."""
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                f"{self._url}/mcp/execute",
                json={
                    "tool": "generate_filler",
                    "arguments": {
                        "context": context[:200],  # Brief context
                        "emotion": emotion.emotion.value,
                    }
                }
            )
            return (await response.json())["filler"]
```

### 5. Pattern Storage (SlowMind)

**Current**: `pattern_store: Callable[[str, str], Awaitable[None]]`

**Integration**:
```python
async def gpu_pattern_store(input_text: str, pattern: str) -> None:
    async with aiohttp.ClientSession() as session:
        await session.post(
            f"{INFERENCE_URL}/mcp/execute",
            json={
                "tool": "store_pattern",
                "arguments": {"input": input_text, "output": pattern}
            }
        )
```

---

## Configuration

### Environment Variables

```bash
# .env on dev machine
INFERENCE_SERVER_URL=http://192.168.x.x:8024

# .env on DGX Spark
INFERENCE_PORT=8024
EMOTION_MODEL=j-hartmann/emotion-english-distilroberta-base
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
LLM_MODEL=/models/llama-4-scout
VECTOR_DB_PATH=/data/patterns.faiss
CUDA_VISIBLE_DEVICES=0
```

### docker-compose.yml Addition

```yaml
# On DGX Spark machine
mcp-inference:
  build:
    context: .
    dockerfile: docker/mcp-inference.Dockerfile
  container_name: mcp-inference
  runtime: nvidia  # NVIDIA Container Toolkit
  ports:
    - "8024:8024"
  volumes:
    - /models:/models:ro          # Pre-downloaded models
    - /data/patterns:/data        # Vector DB persistence
  environment:
    - NVIDIA_VISIBLE_DEVICES=all
    - CUDA_VISIBLE_DEVICES=0
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8024/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

### .mcp.json Update (Dev Machine)

```json
{
  "mcpServers": {
    "inference": {
      "type": "http",
      "url": "http://192.168.x.x:8024"
    }
  }
}
```

---

## Implementation Phases

### Phase 1: Basic Inference Server
1. Create `mcp_inference` package structure
2. Implement `InferenceMCPServer` with health check
3. Add `infer_emotion` tool with GPU model
4. Add `generate_embedding` tool
5. Test on DGX Spark

### Phase 2: Vector Store Integration
1. Add FAISS GPU vector store
2. Implement `search_patterns` and `store_pattern` tools
3. Create persistence layer for patterns
4. Add batch embedding for initial population

### Phase 3: Local LLM Integration
1. Set up vLLM or llama.cpp server
2. Implement `style_for_audio` and `generate_filler` tools
3. Configure model loading and memory management

### Phase 4: mcp_core Integration
1. Add `inference_url` parameter to `FastMind`
2. Create `gpu_pattern_lookup` and `gpu_pattern_store` helpers
3. Add `AudioStyler` to cognition module
4. Update `CognitiveOrchestrator` for GPU-backed processing
5. Add fallback logic for when DGX Spark is unavailable

### Phase 5: Testing & Optimization
1. Benchmark latency improvements
2. Add integration tests with mocked inference server
3. Optimize batch processing
4. Document configuration and deployment

---

## Performance Targets

| Operation | Current (CPU) | Target (GPU) | Improvement |
|-----------|---------------|--------------|-------------|
| Emotion inference | 400-1000ms | <20ms | 20-50x |
| Pattern lookup | 50ms (string) | <50ms (semantic) | Better quality |
| Audio styling | N/A | <100ms | New capability |
| Filler generation | N/A | <50ms | New capability |
| Embedding generation | N/A | <10ms | New capability |

---

## Dependencies

### DGX Spark Requirements
```
# requirements-inference.txt
torch>=2.0.0
transformers>=4.30.0
sentence-transformers>=2.2.0
faiss-gpu>=1.7.0
vllm>=0.2.0  # Or llama-cpp-python for smaller models
aiohttp>=3.8.0
fastapi>=0.100.0
uvicorn>=0.22.0
```

### mcp_core Additions
```
# Add to existing requirements
aiohttp>=3.8.0  # For async HTTP to inference server
```

---

## Critical Files to Modify

| File | Change |
|------|--------|
| `tools/mcp/mcp_inference/` | NEW: Entire inference server package |
| `mcp_core/cognition/fast_mind.py` | Add `inference_url` parameter |
| `mcp_core/cognition/audio_styler.py` | NEW: Audio styling for ElevenLabs pipeline |
| `mcp_core/cognition/slow_mind.py` | No changes (uses Claude API via Reasoner) |
| `mcp_core/cognition/__init__.py` | Export `AudioStyler` |
| `docker-compose.yml` | Add `mcp-inference` service |
| `.mcp.json` | Add HTTP inference server config |
| `config/python/requirements.txt` | Add `aiohttp` |

---

## Fallback Strategy

When DGX Spark is unavailable:
1. **Emotion inference**: Fall back to CPU-based `infer_emotion()`
2. **Pattern lookup**: Fall back to string-based or AgentCore Memory
3. **Audio styling**: Fall back to no styling (plain text to ElevenLabs)

```python
class FastMind:
    async def _infer_emotion(self, text: str) -> EmotionState:
        if self._inference_url:
            try:
                return await self._infer_emotion_gpu(text)
            except (aiohttp.ClientError, asyncio.TimeoutError):
                logger.warning("GPU inference unavailable, falling back to CPU")
        return infer_emotion(text)  # CPU fallback
```

---

## Decisions Made

1. **LLM Model**: Llama 4 Scout (Meta's efficient model, ~50GB quantized)
2. **Vector DB**: FAISS GPU (fast local semantic search)
3. **Model Setup**: Pre-download models before deployment
4. **Network IP**: To be determined when hardware arrives
5. **Primary Reasoning**: Claude API (Opus 4.5) - quality over speed

---

## Llama 4 Scout Notes

Llama 4 Scout is part of Meta's Llama 4 family:
- Optimized for efficient inference
- Supports 128K context window
- Good balance of speed and capability for local reasoning
- Well-suited for the DGX Spark's 128GB unified memory
- Used for audio styling and filler generation, NOT primary reasoning

---

## Complete Audio Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         REAL-TIME AUDIO PIPELINE                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. INPUT                                                                │
│     User speaks or types → FastMind (DGX Spark GPU)                     │
│     • Emotion inference: <20ms                                           │
│     • Generate filler: "Hmm, let me think about that..."                │
│                                                                          │
│  2. IMMEDIATE RESPONSE (while Claude thinks)                            │
│     FastMind filler → AudioStyler (DGX Spark) → ElevenLabs → Character  │
│     • Total latency: <500ms                                              │
│     • Shows active listening/thinking                                    │
│                                                                          │
│  3. DEEP REASONING (parallel)                                           │
│     Input → Claude API (Opus 4.5) → Thoughtful response                 │
│     • Quality analysis and insights                                      │
│     • 2-30 seconds                                                       │
│                                                                          │
│  4. STYLED DELIVERY                                                      │
│     Claude response → AudioStyler (DGX Spark) → ElevenLabs → Character  │
│     • Add <emphasis>, <pause>, emotion tags                              │
│     • Match emotion to voice style                                       │
│     • Smooth transition from filler to main response                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Example Flow

```
User: "What's the best way to handle async errors in Python?"

[T+0ms]    FastMind infers: curious, focused
[T+50ms]   Filler generated: "<thoughtful>That's a great question...</thoughtful>"
[T+100ms]  ElevenLabs converts filler to speech
[T+300ms]  Character speaks filler, appears to be thinking

[T+0-5s]   Claude API analyzes question deeply
[T+5000ms] Claude returns: "There are several patterns for async error handling..."

[T+5050ms] AudioStyler adds tags: "<confident>There are several patterns</confident>
                                   <pause duration='0.2s'/>for async error handling..."
[T+5150ms] ElevenLabs converts styled response
[T+5400ms] Character delivers main response with natural transitions
```

---

## Related Documents

- [MCP Integration Roadmap](mcp-integration-roadmap.md) - Unified emotion taxonomy
- [Virtual Character + ElevenLabs Integration](../integrations/creative-tools/virtual-character-elevenlabs.md)
