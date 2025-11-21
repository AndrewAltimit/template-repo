"""ElevenLabs Speech MCP tools registry"""

# Tool registry - exported for compatibility with CI tests
# Tool functions are implemented and assigned by the MCP server at runtime.
TOOLS = {
    # Primary synthesis tools
    "synthesize_speech_v3": None,
    "synthesize_emotional": None,
    "synthesize_dialogue": None,
    "generate_sound_effect": None,
    # Streaming tools
    "stream_speech_realtime": None,
    "stream_speech_http": None,
    # GitHub integration
    "generate_pr_audio_response": None,
    "generate_issue_audio_update": None,
    # Audio processing
    "combine_audio_segments": None,
    "add_background_sound": None,
    "generate_variations": None,
    "create_audio_scene": None,
    # Voice management
    "list_available_voices": None,
    "get_voice_details": None,
    "set_default_voice": None,
    # Configuration
    "configure_voice_settings": None,
    "set_voice_preset": None,
    "toggle_auto_upload": None,
    # Utility tools
    "parse_audio_tags": None,
    "suggest_audio_tags": None,
    "validate_synthesis_config": None,
    "get_synthesis_status": None,
    "clear_audio_cache": None,
    # User info
    "get_user_subscription": None,
    "get_character_usage": None,
}
