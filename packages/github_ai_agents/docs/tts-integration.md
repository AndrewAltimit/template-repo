# Text-to-Speech Integration

## Overview

The GitHub AI agents support Text-to-Speech (TTS) generation for PR reviews using the ElevenLabs v3 API with emotional context and voice personalization.

## Architecture

### Components

```
┌─────────────────────────────────────────────────┐
│                  PR Monitor                      │
├─────────────────────────────────────────────────┤
│                TTSIntegration                    │
│  ├── Sentiment Analysis                          │
│  ├── Voice Selection (voice_catalog.py)          │
│  └── Audio Generation                            │
├─────────────────────────────────────────────────┤
│           ElevenLabs MCP Server                  │
│         (localhost:8018 or remote)               │
├─────────────────────────────────────────────────┤
│            ElevenLabs API (v3)                   │
└─────────────────────────────────────────────────┘
```

### Core Modules

- **`tts/integration.py`**: Main TTS integration class
- **`tts/voice_catalog.py`**: Voice profiles and agent personality mappings
- **`tts/broadcast_report.py`**: Dramatic broadcast-style reports for critical PRs
- **`tts/v3_agent_guide.py`**: V3 prompting guidance (duplicated in MCP server for independence)

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_TTS_ENABLED` | `false` | Enable TTS for agent reviews |
| `ELEVENLABS_API_KEY` | - | ElevenLabs API key (optional if MCP server has key) |
| `ELEVENLABS_MCP_URL` | `http://localhost:8018` | MCP server URL |
| `TTS_MOCK_MODE` | `false` | Enable mock mode for testing without API credits |

### Docker Deployment

```bash
# Start ElevenLabs MCP server
docker-compose up -d mcp-elevenlabs-speech

# Run PR monitor with TTS
AGENT_TTS_ENABLED=true python -m github_ai_agents.cli pr-monitor
```

## Voice Profiles

### Agent Personality Mappings

| Agent | Default Voice | Contexts |
|-------|--------------|----------|
| **Gemini** | Hope (American, conversational) | critical→Tia, excited→Hope (upbeat), thoughtful→Adam |
| **Claude** | Blondie (British, warm) | technical→Peter, friendly→Cassidy, serious→Juniper |
| **OpenCode** | Peter (British, educational) | casual→Stokes, enthusiastic→Amelia, professional→Juniper |
| **Crush** | Hope (American, friendly) | energetic→Hope (upbeat), calm→Rhea, direct→Tia |

### Voice Categories

- **Conversational**: Natural, friendly voices for general reviews
- **Professional**: Clear, formal voices for technical content
- **Dramatic**: Theatrical voices for critical broadcasts
- **Character**: Specialized voices for unique personalities

## API Reference

### TTSIntegration Class

```python
class TTSIntegration:
    async def generate_audio_review(
        review_text: str,
        agent_name: str,
        pr_number: Optional[int] = None,
        voice_id: Optional[str] = None,
        provide_guidance: bool = True,
    ) -> Optional[str]
```

**Parameters:**
- `review_text`: Full review text from the agent
- `agent_name`: Name of the agent (gemini, claude, etc.)
- `pr_number`: Optional PR number for context
- `voice_id`: Optional specific voice to override default
- `provide_guidance`: Whether to log v3 guidance

**Returns:** Audio URL if successful, None otherwise

### Voice Selection

```python
def get_voice_for_context(
    agent_name: str,
    review_sentiment: str = "default",
    pr_criticality: str = "normal"
) -> VoiceCharacter
```

Context-aware voice selection based on agent personality and review sentiment.

## V3 Model Features

### Emotional Tags

The v3 model supports emotional expression through inline tags:

| Category | Tags | Usage |
|----------|------|-------|
| **Emotions** | `[happy]`, `[sad]`, `[angry]`, `[excited]`, `[concerned]` | Express feelings |
| **Actions** | `[laughs]`, `[sighs]`, `[clears throat]`, `[pause]` | Add natural actions |
| **Speech Styles** | `[whisper]`, `[shouting]`, `[emphasis]` | Modify delivery |
| **Professional** | `[thoughtful]`, `[analytical]`, `[professional]` | Review tones |

### Best Practices

1. **Minimum Length**: Prompts should be at least 250 characters for consistent v3 behavior
2. **Line Separation**: Use line breaks between emotional sections for clarity
3. **Voice Compatibility**: Match tags to voice personality (e.g., avoid `[giggles]` with serious voices)
4. **Natural Flow**: Use ellipses and punctuation for pacing

### Example Prompt

```
[thoughtful] This pull request demonstrates excellent architectural design
with clear separation of concerns.

[concerned] However, there are some performance implications that need
careful consideration... particularly in the data processing pipeline.

[encouraging] Once these are addressed, this will significantly improve
our codebase!
```

## Broadcast Reports

Critical PRs trigger dramatic broadcast-style reports with multi-voice narration.

### Trigger Conditions

- Security vulnerabilities or critical keywords
- Failed CI/CD status
- Security/critical/urgent PR labels
- Exceptional achievements (100% coverage, perfect scores)

### Example Output

```
[agent_voice] Critical security vulnerability detected!

[broadcast_voice] [clears throat] We interrupt our regular programming
for an urgent security bulletin...

[broadcast_voice] [serious] At approximately 14:32 UTC, our scanners
detected critical vulnerabilities in Pull Request #247...
```

## Testing

### Mock Mode

Tests default to mock mode to prevent API credit usage:

```python
# Enable mock mode for testing
os.environ["TTS_MOCK_MODE"] = "true"

# Returns mock URLs without API calls
result = await tts.generate_audio_review(...)
# Returns: "mock://audio/pr123_gemini.mp3"
```

### Unit Tests

```bash
# Run unit tests with mocking
pytest packages/github_ai_agents/tests/test_tts_unit.py

# Run integration tests (uses mock mode by default)
python packages/github_ai_agents/tests/test_voice_profiles.py

# Use real API (consumes credits)
TTS_USE_REAL_API=true python test_voice_profiles.py --generate
```

## GitHub Integration

### Comment Format

Audio reviews are automatically formatted with player links:

```markdown
🎤 **[Listen to Audio Review (8.5s)](https://example.com/audio.mp3)**

---

[AI Agent] Review by Gemini

This pull request implements...
```

## Technical Notes

### Service Independence

The `v3_agent_guide.py` file is intentionally duplicated in both:
- `packages/github_ai_agents/src/github_ai_agents/tts/`
- `tools/mcp/elevenlabs_speech/`

This maintains MCP server independence for containerization. Changes must be synchronized between both files.

### Future Improvements

- **TODO**: Externalize voice configuration to YAML/JSON for easier maintenance
- **TODO**: Replace keyword-based broadcast triggers with scoring system or NLP
- **TODO**: Support for multi-voice dialogue in reviews

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No audio generated | Verify `ELEVENLABS_API_KEY` is set and valid |
| MCP server connection error | Ensure server is running: `docker-compose up -d mcp-elevenlabs-speech` |
| Empty audio URL | Check API key has v3 model access |
| Tests using API credits | Ensure `TTS_MOCK_MODE=true` or don't set `TTS_USE_REAL_API` |

## Rate Limits

- ElevenLabs API has character-based quotas
- Mock mode recommended for development and testing
- Production usage should implement caching for repeated reviews
