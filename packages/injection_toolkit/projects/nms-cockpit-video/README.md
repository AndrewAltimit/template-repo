# NMS Cockpit Video Player

A multiplayer-synchronized video player that renders inside your No Man's Sky spaceship cockpit.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         NMS Process                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Reloaded2 Mod (C#)                         │    │
│  │  • Signature scan for camera matrices                   │    │
│  │  • Compute screen-space cockpit rect                    │    │
│  │  • Send ScreenRect via named pipe                       │    │
│  └─────────────────────────────────────┬───────────────────┘    │
└────────────────────────────────────────┼────────────────────────┘
                                         │ Named Pipe (ScreenRect)
                                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      nms-video-daemon                            │
│  • Receive ScreenRect from mod                                  │
│  • Decode video (ffmpeg) → shared memory                        │
│  • Handle UI commands (play/pause/seek)                         │
│  • P2P multiplayer sync (laminar)                               │
└──────────────────────┬──────────────────┬───────────────────────┘
                       │                  │
         Shared Memory │                  │ IPC (commands)
         (video frames)│                  │
                       ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      nms-video-overlay                           │
│  • Read frames from shared memory                               │
│  • Render video quad at ScreenRect position                     │
│  • egui controls (F9 toggles interactive mode)                  │
│  • Click-through by default                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Daemon (`daemon/`)
NMS-specific configuration of the ITK daemon with video playback.

### 2. Overlay (`overlay/`)
NMS-specific overlay configuration with UI controls.

### 3. Reloaded2 Mod (`mod/`)
C# mod that runs inside NMS to extract camera data.

## Building

### Prerequisites
- Rust 1.70+ (with MSVC toolchain on Windows)
- .NET 8 SDK (for Reloaded2 mod)
- FFmpeg libraries (via vcpkg or system install)
- Reloaded-II mod loader

### Rust Components
```bash
cd packages/injection_toolkit

# Build daemon
cargo build --release -p nms-video-daemon

# Build overlay
cargo build --release -p nms-video-overlay
```

### C# Mod (Reloaded-II)
```bash
cd packages/injection_toolkit/projects/nms-cockpit-video/mod
dotnet restore
dotnet build -c Release

# Output: mod/NmsCockpitOverlay/bin/Release/net8.0-windows/
```

## Installation

1. Install Reloaded-II mod manager
2. Copy `nms-video-daemon.exe` and `nms-video-overlay.exe` to a permanent location
3. Add the built mod (`NmsCockpitOverlay.dll`) to Reloaded-II
4. Enable the mod for No Man's Sky

## Usage

1. Start the daemon: `nms-video-daemon.exe`
2. Launch NMS through Reloaded-II with mod enabled
3. Start the overlay: `nms-video-overlay.exe`
4. Press **F9** to open controls
5. Enter a video URL or file path
6. Press **F9** again to return to click-through mode

### Keyboard Shortcuts
| Key | Action |
|-----|--------|
| F9 | Toggle interactive/click-through mode |
| Space | Play/Pause (when interactive) |
| Left/Right | Seek -10s/+10s (when interactive) |

## Multiplayer

1. All players must have the mod installed
2. One player hosts (enters video URL first)
3. Other players join by entering the same URL
4. Sync happens automatically via P2P

## Limitations

- **PC only** - Console modding not possible
- **Borderless/windowed only** - Exclusive fullscreen blocks overlays
- **NMS updates may break mod** - Signature patterns need updating

## Troubleshooting

### Overlay Not Visible
1. Ensure NMS is in **borderless** or **windowed** mode
2. Check that daemon and overlay processes are running
3. Look for "Connected to video frame buffer" in overlay logs

### Video Not Playing
1. Check daemon logs for decode errors
2. Verify ffmpeg libraries are installed
3. Try a local file to isolate network issues

### Mod Not Loading
1. Verify Reloaded-II is installed correctly
2. Check that mod is enabled in Reloaded-II
3. Look for signature scan failures in mod logs

## Development

### Updating Signatures
When NMS updates break the mod:
1. Find new signatures using x64dbg or IDA
2. Update patterns in `mod/CockpitTracker/MatrixReader.cs`
3. Add new EXE hash to known versions
4. Test thoroughly before release

See `docs/SIGNATURES.md` for signature scanning guide.
