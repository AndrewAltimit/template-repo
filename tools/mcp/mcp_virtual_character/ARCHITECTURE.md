# Virtual Character System Architecture

## Overview

The Virtual Character system provides a comprehensive platform for AI agent embodiment across multiple virtual environments (VRChat, Unity, Unreal, Blender). It handles animations, audio playback, event sequencing, and cross-machine file transfer.

## Core Components

### 1. MCP Server (`server.py`)
- **Port**: 8020
- **Modes**: HTTP (remote) / STDIO (local)
- **Features**:
  - Backend adapter pattern for multiple platforms
  - Event sequencing for complex performances
  - Audio playback with lip-sync support
  - Real-time animation control

### 2. Storage Service (`storage_service/`)
- **Port**: 8021
- **Purpose**: Secure file exchange between environments
- **Features**:
  - Auto-expiring storage (1-hour TTL by default)
  - Token-based authentication
  - Supports audio, animations, textures, configs
  - Prevents AI context window pollution

### 3. Backend Adapters (`backends/`)
- **Mock Backend**: Testing and development
- **VRChat Remote**: OSC protocol for VRChat avatars
- **Unity Backend** (planned): WebSocket communication
- **Unreal Backend** (planned): Direct integration
- **Blender Backend** (planned): Python API integration

## Audio Flow Architecture

### Traditional Flow (Context-Heavy)
```
[ElevenLabs] → [Base64 Audio] → [MCP Protocol] → [Virtual Character]
              ↑
         (100KB+ in context)
```

### Optimized Flow with Storage Service
```
[ElevenLabs] → [Local File] → [Storage Service] → [URL] → [Virtual Character]
                                    ↑                ↑
                            (Secure upload)    (Clean context)
```

### Seamless Integration
```python
# Auto-handles storage upload
from mcp_virtual_character.seamless_audio import play_audio_seamlessly

# Automatically:
# 1. Detects if file is local
# 2. Uploads to storage if needed
# 3. Sends only URL to remote server
result = await play_audio_seamlessly("/tmp/audio.mp3")
```

## Network Topology

### VM-to-Host Configuration
```
┌─────────────────────────┐
│   Linux VM (Claude)     │
│  ┌──────────────────┐   │
│  │ ElevenLabs MCP   │   │
│  │ (Generates Audio)│   │
│  └────────┬─────────┘   │
│           ↓              │
│  ┌──────────────────┐   │
│  │ Storage Service  │   │
│  │   (Port 8021)    │   │
│  └────────┬─────────┘   │
│           ↓ URL         │
└───────────┼─────────────┘
            ↓
┌───────────┼─────────────┐
│  Windows Host           │
│           ↓              │
│  ┌──────────────────┐   │
│  │  VC MCP Server   │   │
│  │   (Port 8020)    │   │
│  └────────┬─────────┘   │
│           ↓              │
│  ┌──────────────────┐   │
│  │  VoiceMeeter     │   │
│  │  (Audio Router)  │   │
│  └────────┬─────────┘   │
│           ↓              │
│  ┌──────────────────┐   │
│  │     VRChat       │   │
│  │  (OSC: 9000)     │   │
│  └──────────────────┘   │
└─────────────────────────┘
```

### Container Architecture
```
┌──────────────────────────┐
│   Docker Host            │
│                          │
│  ┌────────────────────┐  │
│  │ vc-storage         │  │
│  │ Container          │  │
│  │ (Port 8021)        │  │
│  └────────────────────┘  │
│                          │
│  ┌────────────────────┐  │
│  │ mcp-elevenlabs     │  │
│  │ Container          │  │
│  │ (Generates Audio)  │  │
│  └────────────────────┘  │
│                          │
│  Volume Mounts:          │
│  outputs/elevenlabs_*    │
└──────────────────────────┘
```

## Storage Service Details

### Authentication
- **Method**: HMAC-SHA256 token verification
- **Secret**: Shared via `STORAGE_SECRET_KEY` environment variable
- **Token**: Generated as `HMAC(secret, "audio_storage_token")`

### File Management
- **Upload**: Returns unique file ID and download URL
- **TTL**: Configurable (default 1 hour)
- **Cleanup**: Automatic background task every 5 minutes
- **Formats**: Any binary data (audio, images, animations)

### API Endpoints
```
POST /upload          - Upload file (multipart/form-data)
POST /upload_base64   - Upload base64 data (JSON)
GET  /download/{id}   - Download file with auth
GET  /health          - Service health check
```

## Event Sequencing System

The system supports complex, synchronized multimedia performances:

### Sequence Structure
```python
sequence = {
    "name": "greeting_performance",
    "events": [
        {"type": "expression", "timestamp": 0.0, "emotion": "happy"},
        {"type": "audio", "timestamp": 0.5, "audio_data": "storage_url"},
        {"type": "animation", "timestamp": 1.0, "gesture": "wave"},
        {"type": "movement", "timestamp": 2.0, "params": {"move_forward": 0.5}}
    ]
}
```

### Event Types
- **Animation**: Emotions and gestures
- **Audio**: TTS output with lip-sync
- **Expression**: Facial emotions
- **Movement**: Locomotion control
- **Wait**: Timing delays
- **Parallel**: Concurrent events

## Platform Integrations

### VRChat (Current)
- **Protocol**: OSC (Open Sound Control)
- **Ports**: 9000 (receive), 9001 (send)
- **Features**: VRCEmote system, avatar parameters
- **Audio**: VoiceMeeter virtual cable routing

### Unity (Planned)
- **Protocol**: WebSocket
- **Features**: Direct GameObject control
- **Audio**: Unity AudioSource integration

### Unreal (Planned)
- **Protocol**: HTTP REST API
- **Features**: Blueprint integration
- **Audio**: Unreal Audio System

### Blender (Planned)
- **Protocol**: Python API
- **Features**: Armature control, shape keys
- **Audio**: VSE integration

## Configuration

### Environment Variables
```bash
# Storage Service
STORAGE_SECRET_KEY=<32-byte-hex>  # Required for auth
STORAGE_BASE_URL=http://localhost:8021

# Virtual Character Server
VIRTUAL_CHARACTER_SERVER=http://192.168.0.152:8020
VRCHAT_HOST=127.0.0.1  # VRChat location
VRCHAT_USE_VRCEMOTE=true
```

### Docker Compose
```yaml
services:
  virtual-character-storage:
    container_name: vc-storage
    ports:
      - "8021:8021"
    environment:
      - STORAGE_SECRET_KEY=${STORAGE_SECRET_KEY}
```

## Best Practices

### 1. Context Window Management
- **Always** use storage service for binary data
- **Never** pass base64 through MCP when avoidable
- File paths in context, binary data in transport

### 2. Cross-Machine Communication
- Use storage service for VM-to-host transfer
- Configure firewall rules for ports 8020-8021
- Use environment variables for endpoint configuration

### 3. Audio Pipeline
```python
# Recommended approach
from seamless_audio import play_audio_seamlessly

# Auto-handles:
# - Local file detection
# - Storage upload
# - Remote server communication
# - Context optimization
await play_audio_seamlessly(audio_path)
```

### 4. Error Handling
- Storage service has automatic retry
- Backends implement reconnection logic
- Graceful degradation without storage

## Performance Considerations

### Storage Service
- **Upload Speed**: ~10MB/s typical
- **Max File Size**: 100MB (configurable)
- **Concurrent Requests**: 100+ supported
- **Memory Usage**: ~50MB base + file buffers

### MCP Server
- **OSC Messages**: <1ms latency
- **Audio Routing**: ~50ms latency (VoiceMeeter)
- **Animation Updates**: 60Hz capability
- **WebSocket**: Sub-millisecond response

## Security

### Authentication Flow
```
Client → Generate HMAC token → Include in Authorization header
                                           ↓
Server → Verify HMAC token → Process request or reject
```

### Data Protection
- Files auto-expire after TTL
- No permanent storage
- Token-based access control
- Isolated Docker networks

## Troubleshooting

### Common Issues

1. **Storage Service Unreachable**
   ```bash
   docker compose up virtual-character-storage
   ```

2. **Audio Not Playing in VRChat**
   - Check VoiceMeeter routing
   - Verify VRChat mic input settings
   - Ensure OSC is enabled in VRChat

3. **File Upload Fails**
   - Check STORAGE_SECRET_KEY is set
   - Verify network connectivity
   - Check file size (<100MB)

4. **Context Window Errors**
   - Enable storage service
   - Use seamless_audio helpers
   - Check for base64 in logs

## Future Enhancements

### Planned Features
- [ ] Animation sequence editor UI
- [ ] Real-time motion capture input
- [ ] Multi-character synchronization
- [ ] Cloud storage backend option
- [ ] WebRTC audio streaming
- [ ] Procedural animation generation
- [ ] Emotion detection from audio
- [ ] Automatic lip-sync generation

### Integration Roadmap
1. **Q1 2025**: Unity WebSocket backend
2. **Q2 2025**: Unreal Engine plugin
3. **Q3 2025**: Blender real-time control
4. **Q4 2025**: Cloud-native deployment

## Example Workflows

### Complete TTS to Avatar Pipeline
```python
# 1. Generate audio with ElevenLabs
audio_path = await elevenlabs.synthesize("Hello world!")

# 2. Play on virtual character (auto-uploads to storage)
await play_audio_seamlessly(
    audio_path,
    text="Hello world!"  # For lip-sync
)
```

### Complex Performance
```python
# Create synchronized audio-visual sequence
await create_sequence("introduction")
await add_sequence_event("expression", 0.0, expression="happy")
await add_sequence_event("audio", 0.5, audio_data=audio_url)
await add_sequence_event("gesture", 1.0, gesture="wave")
await play_sequence()
```

## Contributing

The Virtual Character system is designed for extensibility:

1. **New Backends**: Implement `BackendAdapter` interface
2. **Storage Providers**: Extend `StorageService` class
3. **Audio Processors**: Add to `audio_helper` module
4. **Animation Systems**: Extend `CanonicalAnimationData`

See `CONTRIBUTING.md` for detailed guidelines.
