# Virtual Character Locomotion MCP Server - Implementation Plan v2.0

## Table of Contents

- [Executive Summary](#executive-summary)
- [Vision: AI Agents in Virtual Worlds](#vision-ai-agents-in-virtual-worlds)
- [Architecture Overview](#architecture-overview)
  - [Core Design Pattern](#core-design-pattern-plugin-based-middleware-architecture)
  - [System Architecture](#system-architecture)
- [Core Middleware Components](#core-middleware-components)
  - [1. Backend Adapter Interface](#1-backend-adapter-interface)
  - [2. Canonical Data Model](#2-canonical-data-model)
  - [3. Plugin Manager](#3-plugin-manager)
- [Backend Plugin Implementations](#backend-plugin-implementations)
  - [1. VRChat Remote Plugin](#1-vrchat-remote-plugin-windows-gpu-required)
  - [2. Blender Plugin](#2-blender-plugin)
  - [3. Unity WebSocket Plugin](#3-unity-websocket-plugin)
  - [4. Future Plugins](#4-future-plugins-extensibility-examples)
- [VRChat Remote Architecture](#vrchat-remote-architecture-windows-gpu-required)
  - [Overview](#overview)
  - [Solution: Remote Windows Bridge](#solution-remote-windows-bridge--obs-pipeline)
  - [Key Components](#key-components)
  - [Practical Workarounds](#practical-workarounds)
- [Immersive Agent Features](#immersive-agent-features)
  - [1. Video Feed Integration](#1-video-feed-integration)
  - [2. Multi-Agent Coordination](#2-multi-agent-coordination)
  - [3. Environmental Awareness](#3-environmental-awareness)
- [MCP Tool Interface](#mcp-tool-interface)
- [Integration Architecture](#integration-architecture)
  - [Service Dependencies](#service-dependencies)
- [Deployment Topology](#deployment-topology)
  - [Multi-Machine Architecture](#multi-machine-architecture)
  - [Network Requirements](#network-requirements)
  - [Windows Machine Setup](#windows-machine-setup)
- [Implementation Phases](#implementation-phases)
  - [Phase 1: Core Middleware Foundation](#phase-1-core-middleware-foundation)
  - [Phase 2: First Backend - VRChat OSC](#phase-2-first-backend---vrchat-osc)
  - [Phase 3: Audio & Animation Pipeline](#phase-3-audio--animation-pipeline)
  - [Phase 4: Additional Backends](#phase-4-additional-backends)
  - [Phase 5: Immersive Features](#phase-5-immersive-features)
  - [Phase 6: Production Ready](#phase-6-production-ready)
- [Testing Strategy](#testing-strategy)
  - [Unit Tests](#unit-tests)
  - [Integration Tests](#integration-tests)
  - [Performance Tests](#performance-tests)
- [Configuration Examples](#configuration-examples)
  - [Main Server Configuration](#main-server-configuration)
  - [Avatar Configuration](#avatar-configuration)
  - [Docker Compose](#docker-compose-linux-side)
  - [Windows Bridge Setup](#windows-bridge-setup-gpu-machine)
- [Security Considerations](#security-considerations)
- [Performance Targets](#performance-targets)
- [Alternative Approaches](#alternative-approaches)
  - [Alternative 1: Unity Plugin Integration](#alternative-1-unity-plugin-integration)
  - [Alternative 2: WebRTC Streaming](#alternative-2-webrtc-streaming)
  - [Alternative 3: Machine Learning Pipeline](#alternative-3-machine-learning-pipeline)
- [Risk Mitigation](#risk-mitigation)
- [Use Cases & Applications](#use-cases--applications)
  - [1. Virtual Customer Service](#1-virtual-customer-service)
  - [2. Virtual Education & Training](#2-virtual-education--training)
  - [3. Entertainment & Social](#3-entertainment--social)
  - [4. Research & Development](#4-research--development)
  - [5. Creative Production](#5-creative-production)
- [Architecture Benefits](#architecture-benefits)
- [Success Metrics](#success-metrics)
  - [Technical Metrics](#technical-metrics)
  - [Quality Metrics](#quality-metrics)
  - [Adoption Metrics](#adoption-metrics)
- [Next Steps](#next-steps)
  - [Immediate Actions](#immediate-actions)
  - [Research Tasks](#research-tasks)
- [Appendix](#appendix)
  - [A. Viseme Reference](#a-viseme-reference)
  - [B. OSC Message Format Examples](#b-osc-message-format-examples)
  - [C. Useful Resources](#c-useful-resources)
  - [D. Practical Usage Examples](#d-practical-usage-examples)
- [Conclusion](#conclusion)

## Executive Summary

This document outlines a comprehensive plan for creating a **middleware** Model Context Protocol (MCP) server that bridges AI agents with virtual character systems. The server acts as a protocol-agnostic translation layer, enabling AI agents to control virtual characters across multiple platforms (VRChat, Blender, Unity, Unreal, etc.) through a unified interface.

**Key Innovation**: This is not just a VRChat controller - it's a universal middleware that enables AI agents to have an immersive presence in any virtual environment, complete with bidirectional communication and video feed capabilities.

## Vision: AI Agents in Virtual Worlds

Imagine AI agents that can:
- **Exist** in virtual environments with full embodiment
- **Interact** with humans and other AI agents in shared virtual spaces
- **See** through virtual cameras and respond to their environment
- **Communicate** with natural speech and body language
- **Learn** from interactions in persistent virtual worlds

## Architecture Overview

### Core Design Pattern: Plugin-Based Middleware Architecture

The system uses a **Plugin Pattern** combined with **Strategy** and **Adapter** patterns to create a truly extensible middleware that can connect to any backend system.

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Agents / MCP Clients                    │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│              Virtual Character Middleware (MCP Server)            │
├─────────────────────────────────────────────────────────────────┤
│  • Canonical Data Model (Animation, Audio, State)               │
│  • Plugin Manager & Registry                                     │
│  • Synchronization Engine                                        │
│  • State Management & Caching                                    │
│  • Bidirectional Communication Hub                               │
└──────────────────────┬──────────────────────────────────────────┘
                       │
         ┌─────────────┴─────────────┬─────────────┬──────────────┐
         ▼                           ▼             ▼              ▼
┌──────────────────┐      ┌──────────────────┐ ┌──────────────────┐
│  VRChat Plugin   │      │  Blender Plugin  │ │  Unity Plugin    │
│  (OSC Protocol)  │      │  (Python API)    │ │  (WebSocket)     │
└──────────────────┘      └──────────────────┘ └──────────────────┘
         │                           │                    │
         ▼                           ▼                    ▼
   [VRChat World]            [Blender Scene]       [Unity Game]
   [Camera Feed]             [Rendered View]       [Game Camera]
```

## Core Middleware Components

### 1. Backend Adapter Interface

The heart of the extensibility - a contract that all backend plugins must implement:

```python
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, Callable

class BackendAdapter(ABC):
    """Base interface for all backend plugins."""

    @abstractmethod
    async def connect(self, config: Dict[str, Any]) -> bool:
        """Establish connection to the backend system."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Clean up and close connections."""
        pass

    @abstractmethod
    async def send_animation_data(self, data: CanonicalAnimationData) -> None:
        """Send animation data in canonical format to backend."""
        pass

    @abstractmethod
    async def send_audio_data(self, audio: bytes, metadata: Dict) -> None:
        """Send audio data with sync metadata."""
        pass

    @abstractmethod
    async def receive_state(self) -> Dict[str, Any]:
        """Receive current state from virtual environment."""
        pass

    @abstractmethod
    async def capture_video_frame(self) -> Optional[bytes]:
        """Capture current view from agent's perspective."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> Dict[str, bool]:
        """Report backend capabilities."""
        pass
```

### 2. Canonical Data Model

A universal representation format that all backends can translate from:

```python
@dataclass
class CanonicalAnimationData:
    """Universal animation data format."""
    timestamp: float

    # Skeletal animation
    bone_transforms: Dict[str, Transform]  # Bone name -> transform

    # Facial animation
    blend_shapes: Dict[str, float]  # Shape name -> weight (0-1)
    visemes: Dict[str, float]  # Viseme name -> weight

    # Procedural parameters
    parameters: Dict[str, Any]  # Generic parameters

    # High-level states
    emotion: Optional[str]
    gesture: Optional[str]
    locomotion: Optional[LocomotionState]

@dataclass
class Transform:
    position: Vector3
    rotation: Quaternion
    scale: Vector3

@dataclass
class LocomotionState:
    velocity: Vector3
    is_grounded: bool
    movement_mode: str  # "walk", "run", "fly", etc.
```

### 3. Plugin Manager

Handles plugin discovery, loading, and lifecycle management:

```python
class PluginManager:
    """Manages backend plugin lifecycle."""

    def __init__(self):
        self.plugins: Dict[str, BackendAdapter] = {}
        self.active_backend: Optional[str] = None

    async def discover_plugins(self) -> List[str]:
        """Discover available plugins via entry points or directory scan."""
        # Use Python entry points for clean plugin installation
        discovered = []
        for entry_point in pkg_resources.iter_entry_points('virtual_character.backends'):
            discovered.append(entry_point.name)
        return discovered

    async def load_plugin(self, name: str, config: Dict) -> BackendAdapter:
        """Load and initialize a specific plugin."""
        pass

    async def switch_backend(self, name: str) -> bool:
        """Switch active backend, handling disconnection/connection."""
        pass
```

### 4. Storage Service (IMPLEMENTED)

Provides efficient cross-machine file transfer and context window optimization:

```python
class StorageService:
    """Secure temporary storage for virtual character assets."""

    def __init__(self, ttl_hours: float = 1.0):
        self.storage_path = Path("/tmp/audio_storage")
        self.ttl_seconds = ttl_hours * 3600
        self.secret_key = os.getenv("STORAGE_SECRET_KEY")

    async def store_file(self, content: bytes, filename: str) -> Dict:
        """Store file with TTL and return URL."""
        file_id = secrets.token_urlsafe(32)
        # Save file and track metadata
        return {
            "file_id": file_id,
            "url": f"{base_url}/download/{file_id}",
            "expires_at": expiry_time
        }

    def verify_token(self, token: str) -> bool:
        """HMAC-SHA256 authentication."""
        expected = hmac.new(self.secret_key, b"audio_storage_token", hashlib.sha256)
        return hmac.compare_digest(token, expected)
```

#### Key Features:
- **Auto-Upload**: Local files automatically uploaded when needed
- **Context Optimization**: Keeps base64 data out of AI context windows
- **Cross-Machine Transfer**: VM to host, container to host, remote servers
- **Auto-Cleanup**: Files expire after configurable TTL
- **Secure Transfer**: Token-based authentication

#### Integration with Audio Pipeline:
```python
# Seamless audio flow
from seamless_audio import play_audio_seamlessly

# Automatically handles:
# 1. File detection (local vs remote)
# 2. Storage upload if needed
# 3. URL-only transfer to remote server
await play_audio_seamlessly("/tmp/speech.mp3")
```

## Backend Plugin Implementations

### 1. VRChat Remote Plugin (Windows GPU Required)

Enables AI agents to control VRChat avatars on remote Windows machines with NVIDIA GPU:

```python
class VRChatRemoteAdapter(BackendAdapter):
    """VRChat remote backend for Windows GPU machines with HTTP streaming."""

    def __init__(self):
        self.remote_host = None     # Windows machine IP
        self.http_client = None     # HTTP API client
        self.osc_bridge = None      # OSC-over-HTTP bridge
        self.obs_controller = None  # Remote OBS WebSocket
        self.video_stream = None    # HTTP video stream
        self.avatar_config = None

    async def connect(self, config: Dict) -> bool:
        self.remote_host = config['remote_host']  # e.g., "192.168.0.150"

        # 1. Connect to remote Windows VRChat bridge server
        self.http_client = aiohttp.ClientSession()
        bridge_url = f"http://{self.remote_host}:8021"

        # Health check
        async with self.http_client.get(f"{bridge_url}/health") as resp:
            if resp.status != 200:
                raise ConnectionError(f"VRChat bridge not available at {bridge_url}")

        # 2. Initialize OSC-over-HTTP bridge
        self.osc_bridge = OSCHTTPBridge(bridge_url, self.http_client)

        # 3. Connect to remote OBS WebSocket
        self.obs_controller = OBSWebSocketController(
            host=self.remote_host,
            port=config.get('obs_port', 4455),
            password=config.get('obs_password')
        )
        await self.obs_controller.connect()

        # 4. Setup HTTP video stream from OBS
        stream_port = config.get('stream_port', 8022)
        self.video_stream = HTTPVideoStream(
            url=f"http://{self.remote_host}:{stream_port}/video_feed",
            auth_token=config.get('stream_token')
        )
        await self.video_stream.connect()

        # 5. Load avatar configuration
        self.avatar_config = await self.load_avatar_config(config['avatar'])

        # 6. Configure remote OBS scene
        await self.setup_remote_obs_scene(config)

        return True

    async def setup_remote_obs_scene(self, config: Dict):
        """Configure OBS scene for VRChat camera capture with chroma key."""
        scene_name = config.get('obs_scene', 'VRChat_AI_Agent')

        # Create or switch to scene
        await self.obs_controller.set_scene(scene_name)

        # Add VRChat camera window capture
        await self.obs_controller.add_source({
            'name': 'VRChat_Camera',
            'type': 'window_capture',
            'settings': {
                'window': 'VRChat - Desktop (PC, VR Optional)*Camera',
                'capture_cursor': False
            }
        })

        # Apply chroma key filter for green screen removal
        await self.obs_controller.add_filter('VRChat_Camera', {
            'name': 'Green_Screen',
            'type': 'chroma_key',
            'settings': {
                'key_color': 0x00FF00,  # Green
                'similarity': 400,
                'smoothness': 80,
                'spill': 100
            }
        })

        # Add default background
        await self.obs_controller.add_source({
            'name': 'AI_Background',
            'type': 'image_source',
            'settings': {
                'file': config.get('default_background', './backgrounds/default.png')
            }
        })

    async def send_animation_data(self, data: CanonicalAnimationData):
        # Translate and send OSC messages via HTTP bridge
        osc_messages = []

        for shape, weight in data.blend_shapes.items():
            if shape in self.avatar_config['mappings']:
                osc_path = self.avatar_config['mappings'][shape]
                osc_messages.append({
                    "address": osc_path,
                    "value": weight
                })

        # Send gesture parameters
        if data.gesture:
            gesture_index = self.avatar_config['gestures'].get(data.gesture, 0)
            osc_messages.append({
                "address": "/avatar/parameters/GestureLeft",
                "value": gesture_index
            })

        # Send batch of OSC messages via HTTP
        await self.osc_bridge.send_batch(osc_messages)

    async def capture_video_frame(self) -> Optional[bytes]:
        """Capture from HTTP video stream."""
        return await self.video_stream.get_frame()

    async def change_environment(self, background_path: str):
        """Change virtual environment by updating OBS background."""
        await self.obs_controller.set_source_setting(
            'AI_Background',
            'file',
            background_path
        )

    async def toggle_green_screen(self, enabled: bool):
        """Toggle between green screen and natural VRChat world."""
        # In VRChat: Can only toggle green screen mode via in-game menu
        # In OBS: Enable/disable chroma key filter
        await self.obs_controller.set_filter_enabled(
            'VRChat_Camera',
            'Green_Screen',
            enabled
        )

    @property
    def capabilities(self) -> Dict[str, bool]:
        return {
            "audio": True,
            "animation": True,
            "video_capture": True,  # Via OBS Virtual Camera
            "bidirectional": True,
            "environment_control": True,  # Via OBS backgrounds
            "streaming": True,  # Via OBS streaming
            "multi_agent": False  # Single avatar per VRChat instance
        }
```

#### Windows Bridge Server (Runs on GPU Machine)

```python
class VRChatBridgeServer:
    """HTTP bridge server running on Windows with VRChat."""

    def __init__(self, port: int = 8021):
        self.app = FastAPI()
        self.osc_client = SimpleUDPClient("127.0.0.1", 9001)
        self.setup_routes()

    def setup_routes(self):
        @self.app.get("/health")
        async def health():
            return {"status": "ok", "vrchat": self.check_vrchat_running()}

        @self.app.post("/osc/send")
        async def send_osc(messages: List[Dict]):
            """Receive OSC messages via HTTP and forward locally."""
            for msg in messages:
                self.osc_client.send_message(msg["address"], msg["value"])
            return {"sent": len(messages)}

        @self.app.get("/osc/receive")
        async def receive_osc():
            """Stream OSC feedback from VRChat."""
            # Implementation for bidirectional communication
            pass

class OSCHTTPBridge:
    """Client-side bridge for OSC-over-HTTP."""

    def __init__(self, bridge_url: str, session: aiohttp.ClientSession):
        self.bridge_url = bridge_url
        self.session = session

    async def send_batch(self, messages: List[Dict]):
        """Send OSC messages via HTTP to Windows bridge."""
        async with self.session.post(
            f"{self.bridge_url}/osc/send",
            json=messages
        ) as resp:
            return await resp.json()

class HTTPVideoStream:
    """Client for receiving video stream from remote OBS."""

    def __init__(self, url: str, auth_token: str = None):
        self.url = url
        self.auth_token = auth_token
        self.frame_buffer = asyncio.Queue(maxsize=5)

    async def connect(self):
        """Start receiving video frames via HTTP."""
        asyncio.create_task(self._stream_loop())

    async def _stream_loop(self):
        """Continuously fetch frames from HTTP stream."""
        headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    async with session.get(self.url, headers=headers) as resp:
                        frame = await resp.read()
                        await self.frame_buffer.put(frame)
                except Exception as e:
                    print(f"Stream error: {e}")
                    await asyncio.sleep(1)

    async def get_frame(self) -> bytes:
        """Get latest video frame."""
        return await self.frame_buffer.get()

class OBSWebSocketController:
    """Controls OBS Studio via WebSocket plugin."""

    def __init__(self, host: str, port: int, password: str = None):
        self.host = host  # Can be remote IP
        self.port = port
        self.password = password

    async def connect(self):
        """Connect to OBS WebSocket server."""
        import obswebsocket as obs
        self.client = obs.ReqClient(
            host=self.host,
            port=self.port,
            password=self.password
        )

    async def set_scene(self, scene_name: str):
        """Switch to a specific scene."""
        self.client.set_current_program_scene(scene_name)

    async def set_source_setting(self, source: str, setting: str, value: Any):
        """Update source settings (e.g., change background image)."""
        self.client.set_input_settings(
            inputName=source,
            inputSettings={setting: value}
        )

    async def start_streaming(self):
        """Start streaming to configured platform."""
        self.client.start_stream()

    async def start_virtual_camera(self):
        """Start OBS Virtual Camera output."""
        self.client.start_virtual_cam()
```

### 2. Blender Plugin

For cinematic quality animations and offline rendering:

```python
class BlenderAdapter(BackendAdapter):
    """Blender backend for high-quality animation."""

    async def connect(self, config: Dict) -> bool:
        # Connect to Blender via Python API or command port
        self.blender_conn = BlenderConnection(config['blender_path'])
        self.scene = await self.blender_conn.load_scene(config['scene_file'])
        return True

    async def send_animation_data(self, data: CanonicalAnimationData):
        # Apply animation to Blender armature
        for bone_name, transform in data.bone_transforms.items():
            bone = self.scene.armature.bones.get(bone_name)
            if bone:
                bone.location = transform.position
                bone.rotation_quaternion = transform.rotation

        # Apply shape keys for facial animation
        for shape_name, value in data.blend_shapes.items():
            if shape_name in self.scene.mesh.shape_keys:
                self.scene.mesh.shape_keys[shape_name].value = value

        # Queue frame for rendering
        await self.scene.update()
```

### 3. Unity WebSocket Plugin

For game engine integration:

```python
class UnityWebSocketAdapter(BackendAdapter):
    """Unity game engine backend via WebSocket."""

    async def connect(self, config: Dict) -> bool:
        self.websocket = await websockets.connect(config['unity_ws_url'])
        await self.authenticate(config['api_key'])
        return True

    async def send_animation_data(self, data: CanonicalAnimationData):
        # Serialize to Unity-friendly format
        unity_data = {
            "type": "animation_update",
            "timestamp": data.timestamp,
            "bones": self.serialize_transforms(data.bone_transforms),
            "blendshapes": data.blend_shapes,
            "parameters": data.parameters
        }
        await self.websocket.send(json.dumps(unity_data))
```

### 4. Future Plugins (Extensibility Examples)

```yaml
potential_backends:
  - name: "Unreal Engine"
    protocol: "Pixel Streaming or custom TCP"
    use_case: "AAA game quality avatars"

  - name: "Roblox"
    protocol: "HTTP API + WebSocket"
    use_case: "Massively multiplayer agent interactions"

  - name: "Mozilla Hubs"
    protocol: "WebRTC + Phoenix Channels"
    use_case: "Web-based VR agent presence"

  - name: "NeosVR/Resonite"
    protocol: "WebSocket + custom API"
    use_case: "Advanced collaborative VR"

  - name: "Omniverse"
    protocol: "USD + Connector API"
    use_case: "Digital twin and simulation"
```

## VRChat Remote Architecture (Windows GPU Required)

### Overview
VRChat requirements and constraints:
- **Windows only** with NVIDIA GPU for optimal performance
- **No Linux support** - must run on remote Windows machine
- Camera creates a separate window (not API-accessible)
- Green screen toggle only (no dynamic backgrounds in-game)
- OSC control limited to avatar parameters

### Solution: Remote Windows Bridge + OBS Pipeline

```
Linux Development Machine                 Windows GPU Machine (192.168.0.150)
┌──────────────────────┐                 ┌──────────────────────────────────┐
│   MCP Middleware     │                 │      Windows Bridge Server       │
│  (Port 8020)         │ HTTP/WebSocket  │         (Port 8021)              │
│                      │ ◄─────────────► │                                  │
│  - Plugin Manager    │                 │  - OSC-HTTP Bridge               │
│  - State Management  │                 │  - Local OSC → VRChat            │
│  - AI Agent Logic    │                 │  - Video Stream Server           │
└──────────────────────┘                 └──────────┬──────────────────────┘
                                                     │ Local OSC
                                                     ▼
                                         ┌──────────────────────────────────┐
                                         │         VRChat                    │
                                         │   [Avatar + Camera Window]       │
                                         │    Green Screen: ON              │
                                         └──────────┬──────────────────────┘
                                                     │ Window Capture
                                                     ▼
                                         ┌──────────────────────────────────┐
                                         │       OBS Studio                  │
                                         ├──────────────────────────────────┤
                                         │ • Window Capture + Chroma Key    │
                                         │ • Dynamic Backgrounds            │
                                         │ • HTTP Stream Output (Port 8022) │
                                         │ • WebSocket Control (Port 4455)  │
                                         └──────────┬──────────────────────┘
                                                     │ HTTP Stream
                                                     ▼
                    Linux Machine ◄──────────────────┘
                    [Receives video stream for AI vision]
```

### Key Components

1. **VRChat Configuration**
   - Enable Stream Camera (creates window)
   - Set green screen mode ON
   - Position camera for optimal framing
   - Configure avatar with OSC parameters

2. **OBS Setup**
   - Install obs-websocket plugin for API control
   - Create scene with layered sources
   - Configure chroma key filter
   - Enable Virtual Camera output

3. **AI Control Flow**
   ```python
   # Avatar Control
   AI → OSC → VRChat Avatar

   # Environment Control
   AI → WebSocket → OBS Background

   # Vision Pipeline
   OBS Virtual Camera → AI Vision Module
   ```

### Practical Workarounds

| VRChat Limitation | OBS Solution |
|-------------------|--------------|
| No dynamic backgrounds | Change OBS background source via WebSocket |
| Camera window only | Window capture with GPU optimization |
| No API for camera | OBS Virtual Camera provides clean feed |
| Green screen toggle only | Chroma key filter in OBS (programmable) |

## Immersive Agent Features

### 1. Video Feed Integration

Enable agents to "see" through composited OBS output:

```python
class VideoFeedManager:
    """Manages video capture from virtual environments."""

    async def start_capture(self, backend: str, config: Dict):
        """Start capturing video from the active backend."""
        self.capture_thread = asyncio.create_task(
            self.capture_loop(backend, config)
        )

    async def capture_loop(self, backend: str, config: Dict):
        """Continuous capture loop."""
        while self.capturing:
            frame = await self.active_backend.capture_video_frame()
            if frame:
                # Process frame (e.g., object detection, scene analysis)
                await self.process_frame(frame)

                # Stream to AI agent for visual understanding
                await self.stream_to_agent(frame)

            await asyncio.sleep(1.0 / config['fps'])  # Target FPS

    async def process_frame(self, frame: bytes):
        """Analyze frame for scene understanding."""
        # Could integrate with vision models for:
        # - Object detection
        # - Face recognition
        # - Environment mapping
        # - Gesture recognition from other avatars
        pass
```

### 2. Multi-Agent Coordination

Enable multiple AI agents to interact in the same virtual space:

```python
class MultiAgentCoordinator:
    """Coordinates multiple agents in shared virtual spaces."""

    def __init__(self):
        self.agents: Dict[str, AgentInstance] = {}
        self.shared_state = SharedWorldState()

    async def spawn_agent(self, agent_id: str, backend: str, config: Dict):
        """Spawn a new agent in the virtual world."""
        agent = AgentInstance(agent_id, backend, config)
        await agent.connect()
        self.agents[agent_id] = agent

        # Notify other agents
        await self.broadcast_agent_joined(agent_id)

    async def coordinate_interaction(self, agent1_id: str, agent2_id: str,
                                    interaction_type: str):
        """Coordinate interaction between two agents."""
        # Examples: handshake, conversation, collaborative task
        pass

    async def synchronize_states(self):
        """Ensure all agents have consistent world view."""
        for agent in self.agents.values():
            state = await agent.get_state()
            await self.shared_state.update(agent.id, state)
```

### 3. Environmental Awareness

Agents can sense and respond to their virtual environment:

```python
class EnvironmentalSensor:
    """Provides environmental awareness to agents."""

    async def scan_environment(self, agent_position: Vector3) -> EnvironmentData:
        """Scan the environment around the agent."""
        return EnvironmentData(
            nearby_objects=await self.detect_objects(agent_position),
            nearby_agents=await self.detect_agents(agent_position),
            ambient_conditions=await self.get_ambient_data(),
            interaction_zones=await self.find_interaction_zones(agent_position)
        )

    async def monitor_events(self) -> AsyncIterator[WorldEvent]:
        """Stream world events to the agent."""
        async for event in self.event_stream:
            if event.type in ['agent_joined', 'object_spawned', 'zone_activated']:
                yield event
```

## MCP Tool Interface

The middleware exposes a clean, unified interface regardless of backend:

```python
# MCP Tool Definitions
tools = [
    {
        "name": "set_backend",
        "description": "Switch to a different backend system",
        "parameters": {
            "backend": {"type": "string", "enum": ["vrchat", "blender", "unity"]},
            "config": {"type": "object"}
        }
    },
    {
        "name": "send_animation",
        "description": "Send animation data to current backend",
        "parameters": {
            "animation_data": {"type": "object"},  # CanonicalAnimationData
            "audio_data": {"type": "string"},      # Base64 encoded audio
            "duration": {"type": "number"}
        }
    },
    {
        "name": "capture_view",
        "description": "Capture current view from agent perspective",
        "parameters": {
            "format": {"type": "string", "enum": ["jpeg", "png", "raw"]}
        }
    },
    {
        "name": "receive_state",
        "description": "Get current state from virtual environment",
        "parameters": {}
    },
    {
        "name": "execute_behavior",
        "description": "Execute high-level behavior",
        "parameters": {
            "behavior": {"type": "string"},  # "greet", "dance", "sit", etc.
            "parameters": {"type": "object"}
        }
    }
]
```

## Integration Architecture

### Service Dependencies

```yaml
dependencies:
  existing_services:
    elevenlabs_speech:
      port: 8018
      usage: "Generate TTS audio with emotions"
      integration: "Client calls for audio generation"

    blender:
      port: 8016
      usage: "Create/edit animations, render scenes"
      integration: "Backend plugin or animation source"

    video_editor:
      port: 8019
      usage: "Process audio, compose timelines"
      integration: "Audio processing pipeline"

  new_requirements:
    core:
      - python-osc>=1.8.0      # VRChat OSC protocol
      - obsws-python>=1.6.0    # OBS WebSocket control
      - websockets>=11.0       # WebSocket connections
      - asyncio>=3.4.3         # Async operations
      - pyyaml>=6.0           # Configuration

    audio_processing:
      - pydub>=0.25.1         # Audio manipulation
      - librosa>=0.10.0       # Audio analysis
      - soundfile>=0.12.1     # Audio I/O

    animation:
      - numpy>=1.24.0         # Mathematical operations
      - scipy>=1.10.0         # Signal processing
      - transforms3d>=0.4.1   # 3D transformations

    video:
      - opencv-python>=4.8.0  # Virtual camera capture
      - pillow>=10.0.0        # Image processing
      - v4l2py>=0.6.0         # Linux virtual camera
      - pyvirtualcam>=0.10.0  # Cross-platform virtual cam

    optional:
      - rhubarb-lip-sync      # Accurate viseme generation
      - mediapipe>=0.10.0     # Pose/gesture recognition

  external_software:
    required:
      - OBS Studio 30+        # Video composition hub
      - obs-websocket 5.0+    # API control plugin
      - VRChat Desktop        # Avatar rendering

    optional:
      - VB-Cable              # Virtual audio routing
      - NDI Tools             # Network video routing
```

## Deployment Topology

### Multi-Machine Architecture

| Component | Location | Requirements | Purpose |
|-----------|----------|--------------|---------|
| **MCP Middleware** | Linux Dev Machine | Python 3.11+ | Main AI agent logic |
| **VRChat** | Windows GPU Machine | NVIDIA GPU, Windows 10/11 | Avatar rendering |
| **OBS Studio** | Windows GPU Machine | Same as VRChat | Video composition |
| **Bridge Server** | Windows GPU Machine | Python, FastAPI | OSC-HTTP bridge |
| **ElevenLabs MCP** | Linux Dev Machine | API access | TTS generation |
| **Blender MCP** | Linux Dev Machine | Blender 3.0+ | Animation creation |

### Network Requirements

```yaml
connectivity:
  linux_to_windows:
    - HTTP API: Port 8021 (Bridge Server)
    - WebSocket: Port 4455 (OBS Control)
    - HTTP Stream: Port 8022 (Video Feed)

  latency_requirements:
    - OSC Commands: < 50ms
    - Video Stream: < 100ms
    - Control API: < 20ms

  bandwidth:
    - Video Stream: 5-10 Mbps (1080p @ 30fps)
    - Control Channel: < 100 Kbps
    - Audio Stream: 128 Kbps
```

### Windows Machine Setup

```powershell
# 1. Install VRChat via Steam
# 2. Install OBS Studio + obs-websocket plugin
# 3. Install Python 3.11+
# 4. Setup bridge server
git clone https://github.com/your-repo/vrchat-bridge
cd vrchat-bridge
pip install -r requirements.txt
python bridge_server.py --port 8021

# 5. Configure OBS
# - Install Virtual Camera plugin
# - Setup HTTP streaming output
# - Configure WebSocket authentication
```

## Implementation Phases

### Phase 1: Core Middleware Foundation (✅ COMPLETED)
- [x] Create `tools/mcp/virtual_character/` structure
- [x] Implement `BackendAdapter` interface
- [x] Build `PluginManager` with discovery system
- [x] Design `CanonicalDataModel` classes
- [x] Set up base MCP server extending `BaseMCPServer`
- [x] Implement plugin loading system

### Phase 2: First Backend - VRChat OSC (✅ COMPLETED)
- [x] Implement `VRChatRemoteBackend` plugin
- [x] Create OSC communication layer
- [x] Build avatar parameter system
- [x] Support VRCEmote system
- [x] Test bidirectional communication
- [x] Create Windows launcher scripts

### Phase 3: Audio & Animation Pipeline (✅ MOSTLY COMPLETED)
- [x] Integrate with `elevenlabs_speech` MCP
- [x] Support ElevenLabs expression tags
- [x] Build event sequencing system
- [x] Create storage service for efficient audio transfer
- [x] Implement seamless audio flow (auto-upload to storage)
- [x] Add emotion → animation mapping
- [ ] Implement viseme generation service (future)
- [ ] Add animation blending system (future)

### Phase 4: Additional Backends
- [ ] Implement `BlenderAdapter` plugin
- [ ] Create `UnityWebSocketAdapter`
- [ ] Build backend switching mechanism
- [ ] Test cross-platform compatibility
- [ ] Document plugin development guide

### Phase 5: Immersive Features
- [ ] Implement video feed processing
- [ ] Build multi-agent coordinator
- [ ] Add environmental awareness
- [ ] Create agent-to-agent communication
- [ ] Implement world event monitoring

### Phase 6: Production Ready
- [ ] Performance optimization
- [ ] Error handling and resilience
- [ ] Docker containerization
- [ ] Comprehensive documentation
- [ ] Integration test suite
- [ ] Example applications

## Testing Strategy

### Unit Tests
```python
# tests/test_virtual_character.py
- Test viseme generation accuracy
- Test OSC message formatting
- Test timeline synchronization
- Test avatar configuration parsing
```

### Integration Tests
```python
# tests/integration/test_vrchat_osc.py
- Test end-to-end OSC communication
- Test parameter updates
- Test state synchronization
- Test error recovery
```

### Performance Tests
```python
# tests/performance/test_latency.py
- Measure TTS → Viseme latency
- Measure OSC round-trip time
- Test concurrent avatar control
- Benchmark timeline generation
```

## Configuration Examples

### Main Server Configuration
```yaml
# config/mcp/virtual_character/config.yaml
server:
  host: "0.0.0.0"
  port: 8020

middleware:
  default_backend: "vrchat"
  plugin_directory: "./plugins"
  enable_video_capture: true
  enable_multi_agent: true

plugins:
  vrchat_remote:
    enabled: true
    config:
      remote_host: "192.168.0.150"  # Windows GPU machine
      bridge_port: 8021             # VRChat bridge server
      stream_port: 8022              # OBS HTTP stream
      obs_port: 4455                 # OBS WebSocket
      obs_password: "${OBS_PASSWORD}"
      avatar_config: "./config/avatars/default.yaml"
      stream_token: "${STREAM_AUTH_TOKEN}"

  blender:
    enabled: true
    config:
      blender_path: "/usr/local/blender"
      default_scene: "./scenes/agent_world.blend"
      render_engine: "EEVEE"

  unity:
    enabled: false
    config:
      websocket_url: "ws://localhost:8080"
      api_key: "${UNITY_API_KEY}"

integrations:
  elevenlabs:
    server_url: "http://localhost:8018"
    default_voice: "Rachel"
    model: "eleven_turbo_v3"

  video_processing:
    enable_object_detection: true
    enable_face_recognition: true
    model: "mediapipe"
```

### Avatar Configuration
```yaml
# config/mcp/avatars/vrchat_default.yaml
avatar:
  name: "AI_Agent_Avatar"
  version: "2.0"

mapping:
  # Viseme mappings
  visemes:
    neutral: "/avatar/parameters/Viseme/v_sil"
    AA: "/avatar/parameters/Viseme/v_aa"
    EE: "/avatar/parameters/Viseme/v_ee"
    IH: "/avatar/parameters/Viseme/v_ih"
    OH: "/avatar/parameters/Viseme/v_oh"
    UH: "/avatar/parameters/Viseme/v_uh"

  # Emotion to blend shape mappings
  emotions:
    happy:
      - {parameter: "/avatar/parameters/FaceHappy", value: 1.0}
      - {parameter: "/avatar/parameters/MouthSmile", value: 0.8}
    sad:
      - {parameter: "/avatar/parameters/FaceSad", value: 1.0}
      - {parameter: "/avatar/parameters/EyesDroop", value: 0.5}

  # Gesture mappings
  gestures:
    wave: "/avatar/parameters/GestureLeft"
    point: "/avatar/parameters/GestureRight"
    thumbs_up: "/avatar/parameters/GestureLeftWeight"

behaviors:
  greet:
    - {action: "gesture", gesture: "wave", duration: 2.0}
    - {action: "emotion", emotion: "happy", intensity: 0.8}
    - {action: "speak", text: "Hello! Nice to meet you!"}
```

### Docker Compose (Linux Side)
```yaml
# docker-compose.yml - Runs on Linux development machine
mcp-virtual-character:
  build:
    context: .
    dockerfile: docker/mcp-virtual-character.Dockerfile
  ports:
    - "8020:8020"          # MCP server
    - "8080:8080"          # Unity WebSocket (if local)
  volumes:
    - ./config/mcp/virtual_character:/app/config
    - ./config/mcp/avatars:/app/avatars
    - ./plugins:/app/plugins
    - ./cache:/app/cache
  environment:
    - VRCHAT_REMOTE_HOST=192.168.0.150
    - OBS_PASSWORD=${OBS_PASSWORD}
    - STREAM_AUTH_TOKEN=${STREAM_AUTH_TOKEN}
    - ELEVENLABS_API_KEY=${ELEVENLABS_API_KEY}
    - UNITY_API_KEY=${UNITY_API_KEY}
  depends_on:
    - mcp-elevenlabs-speech
    - mcp-blender
  extra_hosts:
    - "vrchat-gpu:192.168.0.150"  # Windows GPU machine
```

### Windows Bridge Setup (GPU Machine)
```yaml
# windows-bridge/docker-compose.yml - Runs on Windows GPU machine
vrchat-bridge:
  image: python:3.11-slim
  ports:
    - "8021:8021"  # Bridge API
    - "8022:8022"  # Video stream
  volumes:
    - ./bridge:/app
  environment:
    - VRCHAT_PATH="C:\\Program Files (x86)\\Steam\\steamapps\\common\\VRChat"
  command: python /app/bridge_server.py

obs-streamer:
  image: obsproject/obs-studio:latest  # If containerized OBS available
  ports:
    - "4455:4455"  # WebSocket control
    - "8022:8022"  # HTTP stream output
  devices:
    - /dev/dri:/dev/dri  # GPU access
```

## Security Considerations

1. **OSC Security**
   - Bind to localhost only by default
   - Implement rate limiting
   - Validate parameter ranges
   - Sanitize avatar configurations

2. **API Security**
   - Authentication for MCP endpoints
   - Input validation for all commands
   - Secure storage of API keys
   - Audit logging for avatar control

3. **Content Moderation**
   - Text content filtering
   - Animation sequence validation
   - Rate limiting per client
   - Abuse detection and prevention

## Performance Targets

| Metric | Target | Stretch Goal |
|--------|--------|--------------|
| TTS Latency | < 500ms | < 200ms |
| Viseme Generation | < 1s | < 500ms |
| OSC Round-trip | < 50ms | < 20ms |
| Animation Blend | 60 FPS | 120 FPS |
| Concurrent Avatars | 10 | 50 |
| Cache Hit Rate | > 80% | > 95% |

## Alternative Approaches

### Alternative 1: Unity Plugin Integration
Instead of OSC, create a Unity plugin that directly interfaces with the MCP server:
- **Pros**: Lower latency, more control, custom protocols
- **Cons**: Platform-specific, requires Unity development

### Alternative 2: WebRTC Streaming
Stream rendered character video instead of data:
- **Pros**: Universal compatibility, visual consistency
- **Cons**: Higher bandwidth, server-side rendering required

### Alternative 3: Machine Learning Pipeline
Use ML models for all generation:
- **Pros**: High quality, natural motion
- **Cons**: High computational cost, training data required

## Risk Mitigation

| Risk | Impact | Mitigation Strategy |
|------|--------|-------------------|
| OSC Protocol Changes | High | Version detection, fallback modes |
| ElevenLabs API Limits | Medium | Caching, fallback TTS options |
| Latency Issues | High | Local processing, edge deployment |
| Avatar Compatibility | Medium | Template system, auto-discovery |
| Scalability | Low | Horizontal scaling, load balancing |

## Use Cases & Applications

### 1. Virtual Customer Service
AI agents embodied in virtual spaces providing immersive customer support:
- Visual product demonstrations in VR showrooms
- Emotionally responsive service agents
- Multi-language support with accurate lip-sync
- Persistent agent presence across sessions

### 2. Virtual Education & Training
Teachers and tutors in virtual classrooms:
- Interactive lessons with gesture-based teaching
- Emotional engagement monitoring via video feed
- Multi-agent collaborative learning scenarios
- Personalized avatar expressions for student engagement

### 3. Entertainment & Social
AI companions and entertainers in social VR:
- Virtual concerts with AI performers
- Interactive storytelling with embodied narrators
- AI dungeon masters for VR RPGs
- Social companions for VR chat spaces

### 4. Research & Development
Testing ground for embodied AI research:
- Human-AI interaction studies
- Non-verbal communication research
- Multi-agent coordination experiments
- Virtual world sociology studies

### 5. Creative Production
Content creation with AI actors:
- Automated machinima production
- Virtual influencer content generation
- Procedural animation for game NPCs
- Real-time motion capture translation

## Architecture Benefits

| Benefit | Description | Impact |
|---------|-------------|--------|
| **Protocol Agnostic** | Single interface for all platforms | Reduced complexity |
| **Plugin Extensibility** | Easy to add new backends | Future-proof design |
| **Bidirectional Comms** | Agents can see and respond | True interaction |
| **Multi-Agent Support** | Multiple AIs in same space | Collaborative AI |
| **Video Feed Capture** | Visual understanding | Environmental awareness |

## Success Metrics

### Technical Metrics
- **Latency**: < 100ms for OSC commands
- **Throughput**: 10+ concurrent agents
- **Reliability**: 99.9% uptime
- **Scalability**: Horizontal scaling ready

### Quality Metrics
- **Lip-sync Accuracy**: > 95% with Rhubarb
- **Animation Smoothness**: 60+ FPS
- **Audio Sync**: < 50ms deviation
- **Emotion Recognition**: 90% accuracy

### Adoption Metrics
- **Setup Time**: < 5 minutes for first backend
- **API Simplicity**: 5 core methods
- **Documentation**: 100% coverage
- **Plugin Development**: < 1 day for new backend

## Next Steps

### Immediate Actions
1. **Architecture Review**
   - Validate plugin interface design
   - Confirm canonical data model
   - Review backend priorities

2. **Proof of Concept**
   - Basic plugin manager
   - Simple VRChat OSC test
   - Video capture prototype

3. **Community Engagement**
   - Reach out to VRChat developers
   - Connect with Unity/Unreal communities
   - Explore partnerships with virtual world platforms

### Research Tasks
- Investigate VRChat OSC query protocol
- Evaluate screen capture vs API methods
- Test WebRTC for video streaming
- Explore volumetric capture options

## Appendix

### A. Viseme Reference
Standard viseme set for lip-sync:
- **Neutral/Closed**: Default mouth position
- **AA**: As in "father"
- **EE**: As in "bee"
- **IH**: As in "bit"
- **OH**: As in "go"
- **UH**: As in "book"
- **M/B/P**: Bilabial closure
- **F/V**: Labiodental
- **TH**: As in "think"
- **L**: Tongue tip up
- **R**: Retroflex
- **S/Z**: Sibilant
- **SH/CH**: Postalveolar
- **N/NG**: Nasal

### B. OSC Message Format Examples
```
/avatar/parameters/VRCEmote 1
/avatar/parameters/FaceBlendshapes/Smile 0.75
/avatar/parameters/ToggleHat true
/avatar/parameters/GestureLeft 3
```

### C. Useful Resources
- [VRChat OSC Documentation](https://docs.vrchat.com/docs/osc-overview)
- [Rhubarb Lip Sync](https://github.com/DanielSWolf/rhubarb-lip-sync)
- [python-osc Documentation](https://python-osc.readthedocs.io/)
- [ElevenLabs API Docs](https://docs.elevenlabs.io/)
- [MCP Protocol Specification](https://github.com/modelcontextprotocol/specification)

### D. Practical Usage Examples

#### Complete Remote VRChat Setup Flow
```python
async def setup_ai_agent_in_remote_vrchat():
    """Setup AI agent on remote Windows VRChat instance."""

    # 1. Initialize the middleware on Linux machine
    client = MCPClient("http://localhost:8020")

    # 2. Connect to remote Windows VRChat setup
    await client.execute({
        "tool": "set_backend",
        "parameters": {
            "backend": "vrchat_remote",
            "config": {
                "remote_host": "192.168.0.150",  # Windows GPU machine
                "bridge_port": 8021,
                "stream_port": 8022,
                "obs_port": 4455,
                "obs_password": os.getenv("OBS_PASSWORD"),
                "stream_token": os.getenv("STREAM_AUTH_TOKEN"),
                "avatar_config": "./avatars/ai_agent.yaml",
                "obs_scene": "AI_Agent_Scene",
                "default_background": "./backgrounds/virtual_office.png"
            }
        }
    })

    # 3. Start OBS virtual camera for AI vision
    await client.execute({
        "tool": "start_virtual_camera"
    })

    # 4. Begin interaction loop
    while True:
        # Capture what the agent "sees"
        frame = await client.execute({
            "tool": "capture_view",
            "parameters": {"format": "jpeg"}
        })

        # Process vision (detect people, objects, etc.)
        scene_analysis = await analyze_scene(frame)

        # React based on what's seen
        if "person_waving" in scene_analysis:
            await wave_back_and_greet(client)

        await asyncio.sleep(0.1)  # 10 FPS vision

async def wave_back_and_greet(client):
    """AI agent waves and greets."""

    # 1. Generate speech with ElevenLabs
    audio_response = await client.execute({
        "tool": "generate_speech",
        "parameters": {
            "text": "[excited] Oh hello there! [happy] Nice to meet you!",
            "voice": "Rachel",
            "emotion": "friendly"
        }
    })

    # 2. Send synchronized animation and audio
    await client.execute({
        "tool": "send_animation",
        "parameters": {
            "animation_data": {
                "gesture": "wave",
                "emotion": "happy",
                "visemes": audio_response["viseme_timeline"],
                "parameters": {
                    "GestureLeft": 3,  # Wave gesture
                    "FaceHappy": 0.8
                }
            },
            "audio_data": audio_response["audio_base64"],
            "duration": audio_response["duration"]
        }
    })

async def change_virtual_location(client, location: str):
    """Change the AI's virtual environment via OBS."""

    backgrounds = {
        "office": "./backgrounds/modern_office.png",
        "classroom": "./backgrounds/virtual_classroom.png",
        "park": "./backgrounds/city_park.png",
        "space": "./backgrounds/space_station.png"
    }

    # Change OBS background to simulate location change
    await client.execute({
        "tool": "change_environment",
        "parameters": {
            "background": backgrounds[location]
        }
    })

    # AI acknowledges the change
    await client.execute({
        "tool": "send_animation",
        "parameters": {
            "animation_data": {
                "gesture": "look_around",
                "emotion": "curious"
            }
        }
    })
```

#### Multi-Platform Example
```python
async def cross_platform_demo():
    """Demonstrate switching between different backends."""

    client = MCPClient("http://localhost:8020")

    # Start in VRChat for social interaction
    await client.execute({
        "tool": "set_backend",
        "parameters": {"backend": "vrchat", "config": vrchat_config}
    })

    await interact_in_vrchat()

    # Switch to Blender for high-quality recording
    await client.execute({
        "tool": "set_backend",
        "parameters": {"backend": "blender", "config": blender_config}
    })

    await create_animation_sequence()

    # Switch to Unity for game integration
    await client.execute({
        "tool": "set_backend",
        "parameters": {"backend": "unity", "config": unity_config}
    })

    await participate_in_game()
```

## Conclusion

This Virtual Character Locomotion MCP represents a paradigm shift in how AI agents interact with virtual worlds. By creating a protocol-agnostic middleware layer, we're not just building a VRChat controller or a Blender animator - we're establishing a universal bridge between artificial intelligence and virtual embodiment.

The plugin architecture ensures that as new platforms emerge, they can be easily integrated without disrupting existing functionality. The bidirectional communication and video feed capabilities transform AI agents from mere controllers into true participants in virtual spaces, capable of seeing, understanding, and responding to their environment.

This middleware will enable unprecedented applications:
- AI agents teaching in virtual classrooms
- Virtual customer service with genuine emotional presence
- Multi-agent collaborations in shared virtual spaces
- Immersive AI research in controlled virtual environments

The vision is clear: AI agents that don't just control avatars, but truly inhabit virtual worlds, creating meaningful interactions with humans and other AI agents alike.

---

*This plan is a living document and will be updated as development progresses and new requirements emerge.*

*Version: 2.0 - Middleware Architecture*
*Last Updated: 2024*
*Status: Ready for Review*
