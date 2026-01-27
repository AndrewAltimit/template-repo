# NMS Cockpit Video Player

> A video player that renders inside your No Man's Sky spaceship cockpit, supporting both desktop and VR.

## Architecture

Two rendering paths are available:

### Vulkan Injector (Desktop + VR)

The injector DLL hooks NMS's Vulkan pipeline directly to render a textured quad in 3D space, visible to both desktop and VR users.

```
┌─────────────────────────────────────────────────────────────────┐
│                         NMS Process                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           nms-cockpit-injector.dll                       │   │
│  │  • Hook vkCreateDevice/SwapchainKHR/QueuePresentKHR     │   │
│  │  • Read camera matrices from cGcCameraManager           │   │
│  │  • Read video frames from shared memory                 │   │
│  │  • Render textured quad via Vulkan pipeline             │   │
│  │  • (VR) Hook IVRCompositor::Submit for per-eye render   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Shared Memory (video frames)
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      nms-video-daemon                           │
│  • Decode video (ffmpeg + yt-dlp) → shared memory              │
│  • Audio playback (cpal + ffmpeg resampler)                    │
│  • Handle commands (play/pause/seek/load)                      │
│  • P2P multiplayer sync (laminar)                              │
└─────────────────────────────────────────────────────────────────┘
```

### Overlay (Desktop Only, Legacy)

A separate overlay window renders on top of NMS. Simpler but limited to desktop borderless/windowed mode.

```
┌─────────────────────────────────────────────────────────────────┐
│                      nms-video-daemon                           │
│  • Decode video → shared memory                                │
│  • Audio playback                                              │
└──────────────────────────────┬──────────────────────────────────┘
                               │ Shared Memory (video frames)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      nms-video-overlay                          │
│  • Read frames from shared memory                              │
│  • Render video at screen position                             │
│  • egui controls (F9 toggles interactive mode)                 │
│  • Click-through by default                                    │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Launcher (`launcher/`)
Orchestrates the full workflow: starts daemon, launches NMS with `--disable-eac`, waits for the game process, injects the DLL, and shuts down the daemon when the game exits.

### 2. Daemon (`daemon/`)
Video decode and audio playback. Decodes via ffmpeg with D3D11VA hardware acceleration (falls back to software), writes RGBA frames to shared memory via seqlock, plays audio through system output via cpal. Supports YouTube URLs (via yt-dlp) and local files.

### 3. Injector (`injector/`)
Vulkan rendering hook DLL. Intercepts NMS's Vulkan calls to render a textured quad inside the game's 3D pipeline. Includes keyboard input handler (F5-F9) that sends IPC commands to the daemon. Works in desktop and VR, any display mode. Requires nightly Rust toolchain.

### 4. Overlay (`overlay/`)
Desktop overlay window with egui controls. Simpler alternative to the injector for desktop-only use in borderless/windowed mode.

## Building

### Prerequisites
- Rust nightly MSVC toolchain (injector requires nightly; daemon/overlay work on stable)
- FFmpeg libraries (via vcpkg: `vcpkg install ffmpeg:x64-windows`)
- yt-dlp in PATH (for YouTube URL extraction, optional)
- GPU with D3D11VA support (optional, falls back to software decode)

### Rust Components
```bash
cd packages/injection_toolkit

# Set up environment (MSVC + vcpkg)
export FFMPEG_DIR="C:/vcpkg/installed/x64-windows"

# Build all (daemon, launcher, injector) - requires nightly for injector
cargo +nightly-x86_64-pc-windows-msvc build --release \
  -p nms-video-daemon -p nms-video-launcher -p nms-cockpit-injector

# Build overlay (desktop-only alternative, stable toolchain)
cargo +stable-x86_64-pc-windows-msvc build --release -p nms-video-overlay
```

YouTube support (yt-dlp) is enabled by default in the daemon. D3D11VA hardware-accelerated decoding is used automatically when available (NVIDIA/AMD/Intel GPUs).

## Usage

### With Launcher (Recommended)

Place all binaries in the same directory with an optional video file:
```
nms-video-launcher.exe
nms-video-daemon.exe
nms_cockpit_injector.dll
nms_video.mp4              (optional: auto-loads on startup)
nms_video.txt              (optional: path/URL to load instead of .mp4)
```

Run the launcher:
```bash
nms-video-launcher.exe [nms-exe-path] [dll-path]
```

The launcher handles everything:
1. Starts the daemon (with `--load` if a video file is found)
2. Launches NMS with `--disable-eac`
3. Waits for the game process to spawn
4. Injects the DLL via CreateRemoteThread
5. When NMS exits, shuts down the daemon

### Keyboard Shortcuts (Injector)
| Key | Action |
|-----|--------|
| F5 | Toggle video overlay on/off |
| F6 | Play/Pause |
| F7 | Seek backward 10s |
| F8 | Seek forward 10s |
| F9 | Load video URL from clipboard (YouTube supported) |

### With Injector (Manual)

1. Start the daemon: `nms-video-daemon.exe --load <url-or-path>`
2. Launch NMS with `--disable-eac`
3. Inject `nms_cockpit_injector.dll` via the launcher or LoadLibrary
4. Press F5 to show the video overlay

### With Overlay (Desktop Only)

1. Start the daemon: `nms-video-daemon.exe`
2. Launch NMS in **borderless** or **windowed** mode
3. Start the overlay: `nms-video-overlay.exe`
4. Press **F9** to open controls, enter a video URL
5. Press **F9** again to return to click-through mode

### Keyboard Shortcuts (Overlay)
| Key | Action |
|-----|--------|
| F9 | Toggle interactive/click-through mode |
| Space | Play/Pause (when interactive) |
| Left/Right | Seek -10s/+10s (when interactive) |

## Multiplayer (P2P)

1. All players must have the daemon + injector/overlay
2. One player hosts (enters video URL first)
3. Other players join by entering the same URL
4. Sync happens automatically via P2P (laminar)

## Limitations

- **PC only** - Console modding not possible
- **Singleplayer/P2P coop** - EAC must be disabled for injection
- **Overlay: borderless/windowed only** - Exclusive fullscreen blocks the overlay window
- **Injector: NMS updates may shift memory offsets** - Camera RVA needs updating per patch

## Troubleshooting

### Injector Not Rendering
1. Check DebugView for `[NMS-VIDEO]` log messages
2. Ensure DLL is injected before NMS creates its Vulkan device (early load)
3. Verify `vulkan-1.dll` is loaded in the process
4. Check that shared memory frames are being written by the daemon

### Overlay Not Visible
1. Ensure NMS is in **borderless** or **windowed** mode
2. Check that daemon and overlay processes are running
3. Look for "Connected to video frame buffer" in overlay logs

### Video Not Playing
1. Check daemon logs for decode errors
2. Verify ffmpeg libraries are in PATH or vcpkg
3. For YouTube: ensure yt-dlp is installed and up to date
4. Try a local file to isolate network issues

## Injector Architecture

The injector DLL is organized into four modules that implement the full rendering pipeline:

```
injector/src/
├── lib.rs              DllMain, init thread, module declarations
├── log.rs              OutputDebugString logging (view with DebugView)
├── input.rs            Keyboard hotkeys (F5-F9), IPC to daemon, clipboard
├── shmem_reader.rs     Lock-free shared memory frame polling (itk-shmem seqlock)
├── hooks/
│   ├── mod.rs          Hook install/remove orchestration
│   ├── vulkan.rs       Vulkan function detours (retour static_detour)
│   └── openvr.rs       IVRCompositor::Submit vtable hook
├── renderer/
│   ├── mod.rs          VulkanRenderer: pipeline, draw commands, VR rendering
│   ├── pipeline.rs     Render pass, graphics pipeline, descriptor sets
│   ├── texture.rs      VideoTexture: staging buffer upload, device-local image
│   └── geometry.rs     Quad vertex buffer (6 vertices, pos3 + uv2)
├── camera/
│   ├── mod.rs          CameraReader: NMS process memory reads
│   └── projection.rs   Perspective projection, cockpit MVP computation
└── shaders/
    ├── quad.vert.wgsl  Vertex shader (push constant mat4 MVP)
    └── quad.frag.wgsl  Fragment shader (texture2d + sampler)
```

### Hook Points

| Hook | Method | Purpose |
|------|--------|---------|
| `vkCreateInstance` | retour static_detour | Capture VkInstance for ash loader |
| `vkCreateDevice` | retour static_detour | Capture VkDevice, VkPhysicalDevice, queue family |
| `vkCreateSwapchainKHR` | retour + ICD RawDetour | Track format, extent, swapchain images |
| `vkQueuePresentKHR` | retour + ICD RawDetour | Render quad before desktop present |
| `IVRCompositor::Submit` | vtable swap | Render quad per VR eye before compositor |

Extension functions (`*KHR`) bypass the Vulkan loader when obtained via `vkGetDeviceProcAddr`, so they are hooked at both the loader trampoline level (retour static_detour) and the ICD level (RawDetour on the address returned by `vkGetDeviceProcAddr`).

### Rendering Flow

**Desktop**: `vkQueuePresentKHR` hook -> read camera -> poll shmem -> compute MVP -> transition swapchain image -> render pass (LOAD) -> draw quad -> transition back -> submit

**VR**: `IVRCompositor::Submit` hook -> read VRVulkanTextureData_t -> get VkImage per eye -> create temp framebuffer -> render pass (LOAD) -> draw quad -> cleanup

### Shader Compilation

Shaders are written in WGSL and compiled to SPIR-V at build time via naga (pure Rust, no Vulkan SDK required). The fragment shader uses separate `texture_2d<f32>` and `sampler` bindings (WGSL requirement).

## Development

### Memory Offsets (cGcCameraManager)

See `docs/nms-reverse-engineering.md` for camera singleton details:
```
Singleton pointer: NMS.exe + 0x56666B0
+0x118  Camera mode (u32, cockpit = 0x10)
+0x130  View matrix (4x4 f32, row-major)
+0x1D0  FoV (f32, degrees)
+0x1D4  Aspect ratio (f32)
```

### Updating for NMS Patches
When NMS updates shift memory layouts:
1. Use `mem-scanner` tool or x64dbg to find new cGcCameraManager RVA
2. Update the offset in the injector's camera module
3. Verify camera mode detection still works

## License

Part of the template-repo project. See repository LICENSE file.
