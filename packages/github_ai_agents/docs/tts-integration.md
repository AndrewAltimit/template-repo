# TTS Integration for GitHub AI Agents

## Overview

The GitHub AI agents now support Text-to-Speech (TTS) generation for PR reviews using ElevenLabs v3 API with emotional context.

## Features

- **Emotional Tags**: Reviews are automatically tagged with emotions like `[thoughtful]`, `[concerned]`, `[happy]` based on sentiment analysis
- **Key Sentence Extraction**: Extracts 1-3 most important sentences from the review
- **Audio Links**: Adds audio links to GitHub comments for easy listening
- **Agent-Specific Voices**: Each agent has a unique voice personality
- **V3 Model Support**: Uses ElevenLabs v3 model for emotional expression
- **Configurable**: Can be enabled/disabled via environment variables

## Configuration

### Enable TTS

Set the following environment variables:

```bash
# Enable TTS for agents
export AGENT_TTS_ENABLED=true

# Set your ElevenLabs API key
export ELEVENLABS_API_KEY=your_api_key_here

# Optional: Set MCP server URL (defaults to localhost:8018)
export ELEVENLABS_MCP_URL=http://localhost:8018
```

### Running with TTS

1. **Start the ElevenLabs MCP server**:
```bash
# Using Docker (recommended)
docker-compose up -d mcp-elevenlabs-speech

# Or locally for development
python -m tools.mcp.elevenlabs_speech.server
```

2. **Run PR monitoring with TTS enabled**:
```bash
AGENT_TTS_ENABLED=true python -m github_ai_agents.cli pr-monitor
```

## Example Output

When TTS is enabled, PR review comments will include an audio link:

```markdown
🎤 **[Listen to Audio Review (8.5s)](http://example.com/audio.mp3)**

---

[AI Agent] Review by Gemini

This is an impressive pull request with well-structured code...
```

## Emotional Context

The TTS system automatically detects emotions from review text:

- **Positive indicators**: "impressive", "excellent", "great" → `[happy]` or `[excited]`
- **Concerns**: "failing", "error", "blocker" → `[concerned]` or `[annoyed]`
- **Thoughtful**: "however", "consider", "suggest" → `[thoughtful]`
- **Professional**: "recommend", "should" → `[professional]`

## Voice Models & Agent Personalities

### V3-Compatible Voices
Each agent has a carefully selected voice that matches their personality:

- **Gemini**: *Blondie - Conversational* (British, casual, expressive)
  - Low stability (0.0) for maximum emotional expression
  - Speaker boost enabled for clarity

- **Claude**: *Alice* (British, professional, thoughtful)
  - Balanced stability (0.5) for professional tone

- **OpenCode**: *Daniel* (British, formal, educational)
  - Moderate stability (0.4) for clear explanations

- **Crush**: *Rachel* (American, young, casual)
  - Low-moderate stability (0.3) for friendly tone

### Emotional Expression Format
The v3 model works best with line-separated emotional sections:

```
[thoughtful] This is an impressive pull request!

[concerned] However, there are some issues to address.

[happy] Once resolved, this will be great!
```

### Model Features
The integration uses ElevenLabs v3 model (`eleven_v3`) which supports:
- Emotional tags for expressive speech
- Multiple languages
- Natural pauses and breathing
- Professional voice quality
- Voice-specific settings optimization

## Limitations

- Maximum 3 sentences per audio review (to keep it concise)
- Requires ElevenLabs API key with v3 access
- Audio files are hosted temporarily on upload service

## Testing

Test the TTS integration:

```bash
# Test with a specific PR
AGENT_TTS_ENABLED=true TARGET_PR_NUMBERS=123 python -m github_ai_agents.cli pr-monitor

# Test in review-only mode (no changes)
AGENT_TTS_ENABLED=true REVIEW_ONLY_MODE=true python -m github_ai_agents.cli pr-monitor
```

## Troubleshooting

1. **No audio generated**: Check that `ELEVENLABS_API_KEY` is set and valid
2. **MCP server connection error**: Ensure the ElevenLabs MCP server is running
3. **Empty audio URL**: Verify the API key has access to v3 models

## Future Enhancements

- [ ] Support for multiple voices per agent
- [ ] Dialogue mode for multi-agent reviews
- [ ] Custom emotion mapping per agent personality
- [ ] Sound effects for critical issues
