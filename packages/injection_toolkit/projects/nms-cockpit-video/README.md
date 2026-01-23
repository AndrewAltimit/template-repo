# NMS Cockpit Video Player

A video player that renders inside your No Man's Sky spaceship cockpit, supporting both desktop and VR.

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

### 1. Daemon (`daemon/`)
Video decode and audio playback. Decodes via ffmpeg, writes RGBA frames to shared memory via seqlock, plays audio through system output via cpal. Supports YouTube URLs (via yt-dlp) and local files.

### 2. Injector (`injector/`)
Vulkan rendering hook DLL. Intercepts NMS's Vulkan calls to render a textured quad inside the game's 3D pipeline. Works in desktop and VR, any display mode. Requires nightly Rust toolchain.

### 3. Overlay (`overlay/`)
Desktop overlay window with egui controls. Simpler alternative to the injector for desktop-only use in borderless/windowed mode.

## Building

### Prerequisites
- Rust stable (daemon, overlay) and nightly MSVC (injector)
- FFmpeg libraries (via vcpkg: `vcpkg install ffmpeg:x64-windows`)
- yt-dlp in PATH (for YouTube support)

### Rust Components
```bash
cd packages/injection_toolkit

# Set up environment (MSVC + vcpkg)
export VCPKG_ROOT="C:/vcpkg"

# Build daemon (with YouTube support)
cargo +stable-x86_64-pc-windows-msvc build --release -p nms-video-daemon --features youtube

# Build overlay
cargo +stable-x86_64-pc-windows-msvc build --release -p nms-video-overlay

# Build injector (requires nightly)
cargo +nightly-x86_64-pc-windows-msvc build --release -p nms-cockpit-injector
```

## Usage

### With Injector (Recommended)

1. Start the daemon: `nms-video-daemon.exe --load <url-or-path>`
2. Launch NMS in singleplayer (with `--disable-eac` if needed)
3. Inject `nms_cockpit_injector.dll` via Reloaded-II or LoadLibrary
4. Video renders as a 3D quad in the cockpit

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

## Development

### Memory Offsets (cGcCameraManager)

See `docs/nms-reverse-engineering.md` for camera singleton details:
```
Singleton pointer: NMS.exe + 0x56666B0
+0x118  Camera mode (u32, cockpit = 0x10)
+0x130  View matrix (4x4 f32, row-major)
+0x1D0  FoV (f32, degrees)
```

### Updating for NMS Patches
When NMS updates shift memory layouts:
1. Use `mem-scanner` tool or x64dbg to find new cGcCameraManager RVA
2. Update the offset in the injector's camera module
3. Verify camera mode detection still works
