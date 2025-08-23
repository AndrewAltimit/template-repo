#!/bin/bash
# Example: Run PR review with TTS audio generation
set -e

echo "GitHub AI Agent PR Review with TTS"
echo "===================================="
echo ""

# Check for required environment variables
if [ -z "$ELEVENLABS_API_KEY" ]; then
    echo "⚠️  Warning: ELEVENLABS_API_KEY not set"
    echo "   Audio reviews will not be generated"
    echo "   Set it in .env or export ELEVENLABS_API_KEY=your_key"
    echo ""
fi

# Enable TTS for this session
export AGENT_TTS_ENABLED=true
export ELEVENLABS_MCP_URL=${ELEVENLABS_MCP_URL:-"http://localhost:8018"}

# Optional: Set specific PR to review
if [ -n "$1" ]; then
    export TARGET_PR_NUMBERS="$1"
    echo "Reviewing PR #$1 with TTS enabled"
else
    echo "Reviewing all recent PRs with TTS enabled"
fi

echo ""
echo "Configuration:"
echo "  TTS Enabled: $AGENT_TTS_ENABLED"
echo "  MCP Server: $ELEVENLABS_MCP_URL"
echo "  Review Mode: ${REVIEW_ONLY_MODE:-false}"
echo ""

# Start the ElevenLabs MCP server if not running
echo "Checking ElevenLabs MCP server..."
if ! curl -s "$ELEVENLABS_MCP_URL/health" > /dev/null 2>&1; then
    echo "Starting ElevenLabs MCP server..."
    docker-compose up -d mcp-elevenlabs-speech 2>/dev/null || {
        echo "⚠️  Could not start MCP server via Docker"
        echo "   You may need to start it manually:"
        echo "   python -m tools.mcp.elevenlabs_speech.server"
    }
    sleep 2
fi

# Run PR monitor with TTS
echo "Starting PR review with audio generation..."
echo ""

python -m github_ai_agents.cli pr-monitor

echo ""
echo "Review complete!"
echo ""
echo "Audio reviews (if generated) include:"
echo "  - Emotional context tags ([thoughtful], [concerned], [happy])"
echo "  - Key sentences from the review (1-3 sentences)"
echo "  - Uploaded audio links in GitHub comments"
