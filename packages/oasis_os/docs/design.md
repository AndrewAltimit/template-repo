# OASIS_OS

## An Embeddable Operating System Framework in Rust

**Technical Design Document**
Version 2.3 -- February 2026
Author: Andrew
Classification: Personal Project -- Open Source

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Project Goals and Non-Goals](#2-project-goals-and-non-goals)
3. [System Architecture](#3-system-architecture)
4. [Core Framework](#4-core-framework)
5. [Backend Abstraction Layer](#5-backend-abstraction-layer)
6. [Skin System](#6-skin-system)
7. [Unreal Engine 5 Integration](#7-unreal-engine-5-integration)
8. [PSP Platform Implementation](#8-psp-platform-implementation)
9. [Linux / Raspberry Pi Platform](#9-linux--raspberry-pi-platform)
10. [Briefcase Agent Terminal](#10-briefcase-agent-terminal)
11. [PSP Remote Agent Control](#11-psp-remote-agent-control)
12. [Virtual File System](#12-virtual-file-system)
13. [Development Workflow](#13-development-workflow)
14. [Plugin System](#14-plugin-system)
15. [Security Considerations](#15-security-considerations)
16. [Build System and CI/CD](#16-build-system-and-cicd)
17. [Migration Strategy from Original C Codebase](#17-migration-strategy-from-original-c-codebase)
18. [Risk Assessment](#18-risk-assessment)
19. [Success Criteria](#19-success-criteria)
20. [References and Resources](#20-references-and-resources)

---

## 1. Executive Summary

OASIS_OS is an embeddable operating system framework written in Rust. It provides a fully functional, skinnable shell interface -- complete with a scene-graph UI, command interpreter, virtual file system, plugin system, and remote terminal -- that can render anywhere you can provide a pixel buffer and an input stream.

The project originated as a Rust port of a PSP homebrew shell OS written in C circa 2006-2008. The original source archive (`psixpsp.7z`) is preserved at the repository root. The original architecture -- a themed dashboard driven by a custom scene-graph engine called SDI (Simple Display Interface), with platform abstraction via compile-time guards -- turned out to be a natural foundation for something more general. The trait-based backend system designed for cross-platform PSP/SDL/framebuffer portability extends cleanly to a fourth target: rendering onto a texture inside Unreal Engine 5, where in-game computer props become fully interactive systems rather than scripted UI sequences.

The framework supports multiple "skins" -- visual and behavioral personalities that determine what the OS looks like and what it exposes to the user. The Classic skin (implemented) renders a PSIX-style icon grid dashboard with document icons, tabbed bars, and chrome bezels. Planned skins include: a cyberpunk terminal skin with green-on-black CRT text, a military console skin exposing only the command line, and a corrupted OS skin that randomly permutes visual state. All skins share the same core: scene graph, command interpreter, virtual file system, networking, and plugin infrastructure. The skin defines layout, theme, feature gating, and visual style.

Primary deployment targets are: in-game computers in UE5 projects (rendered as interactive props), real PSP hardware running modern custom firmware (6.60/6.61 with ARK-4), and the tamper-responsive briefcase system (`packages/tamper_briefcase/`) where a Raspberry Pi 5 boots directly into OASIS_OS as the field-deployable agent terminal OS. On the briefcase, OASIS_OS is the operator-facing interface for managing AI agents in untrusted environments -- the tamper detection, LUKS encryption, and cryptographic wipe services run alongside it as systemd units. On a PSP connected to infrastructure WiFi, OASIS_OS's remote terminal enables direct command sessions to machines running AI agents, making a 2005 handheld a viable field controller for the agent ecosystem described in `docs/agents/README.md`. The original C codebase (~15,000 lines) provides the proven UI design; the Rust rewrite provides memory safety, cross-platform backends, and the extensibility to support all targets from a single codebase.

---

## 2. Project Goals and Non-Goals

### 2.1 Goals

- Build an embeddable OS framework in Rust that renders to any pixel buffer and consumes any input stream
- Implement a skin system that separates visual/behavioral personality from core OS logic
- Integrate as a native library in Unreal Engine 5 for interactive in-game computer props
- Port the original C shell OS as the Classic skin, preserving its icon-grid dashboard and theming
- Achieve cross-platform execution on PSP hardware (via rust-psp), PPSSPP emulator, Raspberry Pi (via SDL2/framebuffer), and UE5 (via render target)
- Provide a virtual file system abstraction backed by real files, game assets, or procedural content depending on platform
- Add remote terminal access for headless device management over TCP/IP, doubling as the primary interface for controlling remote AI agents from portable devices
- Implement a scriptable command layer for automation and gameplay scripting
- Establish a plugin/module system for runtime-extensible functionality
- Serve as the user-facing OS for the tamper-responsive briefcase agent terminal (`packages/tamper_briefcase/`), replacing bare TTY login with a themed, interactive shell
- Leverage the existing AI agent pipelines (Claude, Gemini, Codex, OpenCode, Crush) and MCP server ecosystem for code translation, build orchestration, and automated testing

### 2.2 Non-Goals

- Building a general-purpose operating system kernel (the framework runs atop existing kernels, firmware, or game engines)
- WASM-based sandboxing or binary compatibility (unnecessary complexity for the use case; pure Rust provides better performance and simpler integration)
- Porting the vendored ffmpeg codebase (replaced by modern alternatives or external linkage)
- Supporting commercial game piracy or circumventing DRM protections
- Achieving feature parity with full Linux desktop environments
- Real-time or safety-critical certification

---

## 3. System Architecture

### 3.1 High-Level Architecture

OASIS_OS follows a layered architecture with strict separation between the platform-agnostic core framework, platform-specific backends, skin definitions, and host applications. The core framework never calls platform-specific APIs directly -- all I/O passes through trait boundaries.

| Layer | Responsibility | Scope |
|-------|---------------|-------|
| Core Framework | Scene graph (SDI), command interpreter, virtual file system, config/theming engine, plugin interface, input event pipeline | All platforms |
| Backends | Rendering (GU, SDL2, framebuffer, UE5 render target), input (PSP pad, keyboard/mouse, gamepad, UE5 interaction), networking (pspnet, std::net), file I/O (real FS, game assets) | Platform-specific impl |
| Skins | Layout definitions, theme assets, feature gating, visual style, "personality" (which commands exist, what the file tree looks like, what apps are discoverable) | Content layer |
| Host Application | UE5 game, PSP firmware, Linux init system, briefcase tamper services, or desktop window manager -- owns the OS instance, ticks it, provides render target and input | Integration layer |

### 3.2 Repository Structure

The project is organized as a Cargo workspace under `packages/oasis_os/`, following the same conventions as other research packages in this repository (`tamper_briefcase`, `economic_agents`, `bioforge`, `injection_toolkit`). The core crate depends on `std`. Skins are data-driven configurations loaded at runtime.

The rust-psp SDK is an external dependency hosted at [github.com/AndrewAltimit/rust-psp](https://github.com/AndrewAltimit/rust-psp) and referenced as a git dependency. The PSP backend crate is excluded from the workspace because it requires the `mipsel-sony-psp` target and is built separately with `cargo psp`.

```
packages/oasis_os/
+-- Cargo.toml                     # Workspace root (resolver="2", edition 2024)
+-- crates/
|   +-- oasis-core/                 # Platform-agnostic framework (requires std)
|   |   +-- src/
|   |       +-- sdi/               # Scene graph: named registry, z-order, alpha, layout, theming
|   |       +-- terminal/          # Command interpreter, command trait, registry, remote listener
|   |       +-- vfs/               # Virtual file system: trait-based I/O
|   |       +-- dashboard/         # Application grid discovery and state
|   |       +-- skin/              # Skin loading and management
|   |       +-- wm/                # Window manager: lifecycle, drag/resize, hit testing, clipping
|   |       +-- plugin/            # Plugin loading interface, lifecycle, host API
|   |       +-- agent/             # Agent terminal integration
|   |       +-- audio/             # Audio subsystem with playlist support
|   |       +-- apps/              # Application launcher and runner
|   |       +-- platform/          # Platform services (time, power, USB)
|   |       +-- (and more modules: bottombar, statusbar, cursor, osk, pbp, theme, wallpaper, ...)
|   +-- oasis-backend-sdl/          # SDL2 rendering and input (desktop dev + Raspberry Pi)
|   +-- oasis-backend-ue5/          # UE5 render target, software RGBA framebuffer, FFI input queue
|   +-- oasis-backend-psp/          # [EXCLUDED] GU hardware rendering, PSP controller input (no_std, standalone)
|   +-- oasis-ffi/                  # C FFI boundary for UE5: exported functions, opaque handles
|   +-- oasis-app/                  # Binary entry points: desktop app + screenshot tool
+-- skins/
|   +-- classic/                    # Icon grid dashboard, status bar, PSIX-style chrome (implemented)
+-- docs/
|   +-- design.md                   # This document
```

**External dependencies:**

- [rust-psp SDK](https://github.com/AndrewAltimit/rust-psp) (MIT) -- modernized fork with edition 2024, safety fixes, kernel mode support. Referenced as a git dependency from `oasis-backend-psp/Cargo.toml`.

**Planned directories (not yet created):**

- `skins/terminal/` -- Full-screen CRT command line, monospace layout
- `skins/tactical/` -- Military/tactical: stripped-down command interface
- `skins/corrupted/` -- Glitched OS: randomized layouts, visual artifacts
- `skins/desktop/` -- Window-like panels, taskbar, start menu analog
- `skins/agent-terminal/` -- Briefcase-specific: agent status, MCP tool access
- `ppsspp/` -- PPSSPP Docker container with MCP patches for agent-assisted debugging
- `asm/` -- Preserved MIPS assembly (me.S, audiolib.S, pspstub.s) from original C codebase

**Planned crates (not yet created):**

- `oasis-backend-framebuffer` -- Direct Linux framebuffer rendering (headless Pi)
- `oasis-platform-psp` -- PSP hardware services: USB, UMD, power, Media Engine, kernel services
- `oasis-platform-linux` -- Pi-specific: GPIO (rppal), systemd integration, sysfs queries

**Workspace Cargo.toml:**

```toml
[workspace]
resolver = "2"
members = [
    "crates/oasis-core",
    "crates/oasis-backend-sdl",
    "crates/oasis-backend-ue5",
    "crates/oasis-ffi",
    "crates/oasis-app",
]
# PSP crate excluded from workspace -- it requires mipsel-sony-psp target
# and the rust-psp SDK (github.com/AndrewAltimit/rust-psp). Build separately with cargo-psp:
#   cd crates/oasis-backend-psp && cargo psp --release
exclude = [
    "crates/oasis-backend-psp",
]

[workspace.package]
version = "0.1.0"
edition = "2024"
license = "MIT"
repository = "https://github.com/AndrewAltimit/template-repo"
authors = ["AndrewAltimit"]

[workspace.dependencies]
# Serialization
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
toml = "0.8"

# Logging
log = "0.4"
env_logger = "0.11"

# Error handling
thiserror = "2.0"
anyhow = "1.0"

# Graphics (desktop / Pi)
sdl2 = "0.37"

# Image encoding (screenshots)
png = "0.17"

# Internal crates
oasis-core = { path = "crates/oasis-core" }
oasis-backend-ue5 = { path = "crates/oasis-backend-ue5" }

[workspace.lints.clippy]
clone_on_ref_ptr = "warn"
dbg_macro = "warn"
todo = "warn"
unimplemented = "warn"

[workspace.lints.rust]
unsafe_op_in_unsafe_fn = "warn"

[profile.release]
lto = true
codegen-units = 1
panic = "abort"
strip = true

[profile.dev]
opt-level = 0
debug = true
```

The PSP backend crate has its own standalone `Cargo.toml` (not workspace-inherited) because it targets `mipsel-sony-psp` and depends on the standalone rust-psp SDK:

```toml
# crates/oasis-backend-psp/Cargo.toml
[workspace]  # standalone workspace

[package]
name = "oasis-backend-psp"
version = "0.1.0"
edition = "2024"
license = "MIT"

[dependencies]
psp = { git = "https://github.com/AndrewAltimit/rust-psp", branch = "initial_release" }
```

### 3.3 Platform Targeting

| Target | Cargo Command | Render Backend | Input Backend | VFS Backend | Status |
|--------|--------------|----------------|---------------|-------------|--------|
| Desktop (dev) | `cargo build --release -p oasis-app` | SDL2 | Keyboard/mouse | Real Linux FS | Implemented |
| PSP / PPSSPP | `cd crates/oasis-backend-psp && cargo +nightly psp --release` | sceGu hardware (Sprites) | PSP controller | ms0:/ real FS | Implemented |
| UE5 (in-game) | `cargo build --release -p oasis-ffi` (cdylib) | UE5 render target | UE5 interaction | Game asset VFS | Implemented (FFI ready) |
| Raspberry Pi (briefcase) | `cargo build --release -p oasis-app --target aarch64-unknown-linux-gnu` | SDL2 | Keyboard/gamepad | Real Linux FS | Planned (SDL2 backend works, cross-compile not yet tested) |

Note: The PSP backend is a standalone crate excluded from the workspace. It does not depend on `oasis-core` (which requires `std`) -- instead it duplicates minimal types (`Color`, `Button`, `Trigger`, `TextureId`) for `no_std` compatibility. The PSP backend uses sceGu hardware-accelerated 2D rendering with `Sprites` primitives and renders a PSIX-style UI (document icons, tabbed bars, chrome bezels, wave arc wallpaper) matching the desktop layout.

---

## 4. Core Framework

### 4.1 SDI -- Simple Display Interface

SDI is the scene-graph engine at the center of the framework. The original C implementation (~1,574 lines in `sdi.c`) manages named UI objects with position, size, alpha, z-order, and image data through a flat registry. The Rust SDI replaces string-keyed C arrays with a `HashMap<String, SdiObject>` registry, with the borrow checker enforcing exclusive mutation.

SDI is deliberately simple. It is not a DOM, not a layout engine, and not a retained-mode GUI framework. It is a flat collection of named, positionable, blittable objects with z-ordering and alpha blending. This simplicity is a feature -- it maps directly to what every backend can provide efficiently, from PSP GU hardware to a UE5 texture blit.

| SDI Operation | Original C | Rust Equivalent |
|--------------|-----------|-----------------|
| Create object | `sdi_new("name")` | `sdi.create("name")` |
| Set position | `sdi_set_x("name", 100)` | `sdi.get_mut("name")?.x = 100` |
| Load image | `sdi_load_png("name", path)` | `sdi.load_png("name", path)?` |
| Draw frame | `sdi_draw()` | `sdi.draw(&mut backend)?` |
| Z-ordering | `sdi_move_top("name")` | `sdi.move_to_top("name")` |
| Theme loading | `sdi_load_state(path)` | `sdi.load_theme(path)?` |

**Key trait:** `SdiBackend` abstracts all rendering. The scene graph calls `backend.blit()`, `backend.clear()`, `backend.swap_buffers()` -- it never knows what surface it's drawing to.

### 4.2 Command Interpreter

The command interpreter is a registry-based dispatch system. Commands implement a `Command` trait with an `execute()` method returning structured output. Skins control which commands are registered -- a terminal skin exposes everything, a locked-down kiosk skin exposes only approved commands, a corrupted skin registers broken versions of standard commands that produce garbled output. The agent-terminal skin adds commands for remote agent interaction (see Section 11).

| Command Category | Examples | Description |
|-----------------|----------|-------------|
| System | status, power, clock, memory, threads | Hardware/host queries and system state |
| File | ls, cd, cp, mv, rm, cat, find | Virtual file system operations |
| Network | ifconfig, ping, netstat, scan | Network status and diagnostics (where available) |
| Dashboard | apps, launch \<n\>, kill, refresh | Application management (skin-dependent) |
| Settings | theme, brightness, volume, wifi | Device/instance configuration |
| Plugin | plugin list, plugin load \<n\>, plugin unload | Plugin lifecycle management |
| Script | run \<script\>, cron, startup | Script execution and scheduling |
| Transfer | ftp start, http start, push, pull | File transfer services (real-network platforms only) |
| Game | query, trade, deck, inbox | Game-specific commands (UE5 skin only) |
| Agent | agent list, agent status, remote \<host\>, mcp \<tool\> | AI agent interaction (agent-terminal and terminal skins) |

### 4.3 Input Pipeline

The input system translates platform-specific events into a platform-agnostic `InputEvent` enum. Every backend maps its native input to this enum. The core framework never sees raw platform input.

| Event Type | PSP Source | Desktop/Pi Source | UE5 Source |
|-----------|-----------|-------------------|------------|
| `CursorMove(x, y)` | Analog stick | Mouse motion / gamepad stick | Line trace UV -> screen coords |
| `ButtonPress(Button)` | D-pad, face buttons | Keyboard / gamepad | Mapped interact keys |
| `Trigger(Trigger)` | L/R shoulder | Keyboard / gamepad triggers | Shoulder buttons on gamepad |
| `TextInput(char)` | On-screen keyboard | Physical keyboard | Captured keyboard when "seated" |
| `PointerClick(x, y)` | N/A | Mouse click | Line trace hit on monitor mesh |
| `FocusGained` | N/A (always focused) | Window focus event | Player enters interaction range |
| `FocusLost` | N/A | Window blur event | Player walks away from terminal |

### 4.4 Remote Terminal

On platforms with networking (PSP via infrastructure WiFi, Linux, desktop), the framework runs a TCP listener that accepts remote terminal connections. The remote terminal feeds keystrokes into the same command interpreter as local input. This is functional on real hardware and in PPSSPP (1.19+ maps `sceNetInet` to host sockets). In UE5, the terminal is available for debugging -- connect to `localhost:9000` while the game is running to interact with any in-game computer's OS instance directly.

On the briefcase Pi, the remote terminal is the primary access path for headless operation -- SSH into the Pi, then connect to the OASIS_OS terminal port for a full interactive shell over the network. On a PSP, the remote terminal works in the opposite direction: OASIS_OS acts as a client, establishing outbound TCP sessions to remote machines (see Section 11).

### 4.5 Window Manager

The window manager (WM) enables skins that present multiple movable, resizable, overlapping windows -- producing the feel of a real desktop operating system. The WM is a consumer of the SDI API, not a modification to it. SDI remains a flat, dumb scene graph; the WM is the smart layer that creates, positions, and manipulates groups of SDI objects to simulate windowed interfaces.

#### 4.5.1 Design Principle: SDI Stays Flat

SDI has no concept of grouping, containment, or parent-child relationships. Every object is independent. The WM introduces the illusion of hierarchy by adopting a naming convention: a window named `"editor_01"` owns SDI objects `"editor_01.frame"`, `"editor_01.titlebar"`, `"editor_01.title_text"`, `"editor_01.btn_close"`, `"editor_01.btn_minimize"`, and `"editor_01.content"`. When the WM moves a window, it updates the position of every object sharing that prefix by the same delta. When it brings a window to front, it calls `sdi.move_to_top()` for every object in the group.

This design preserves SDI's simplicity and portability. The PSP target (which has no use for overlapping windows on a 480x272 screen) never instantiates a WM. Skins that don't need windows (Terminal, Tactical, Classic) skip it entirely. The WM only exists when a skin's `features.toml` enables it.

#### 4.5.2 Window Anatomy

Each window is a `Window` struct in the WM that tracks its SDI child objects, state, and geometry. The visual composition of a window is defined by the active skin's theme -- the WM handles behavior, the skin handles appearance.

| SDI Object | Role | Skin Provides |
|-----------|------|---------------|
| `{id}.frame` | Background rectangle, receives drop shadow or border | Frame image/color, corner radius, border width |
| `{id}.titlebar` | Draggable title bar region, colored band at top | Titlebar height, background color/gradient, active vs inactive colors |
| `{id}.title_text` | Window title label | Font, size, color, alignment within titlebar |
| `{id}.btn_close` | Close button, top-right of titlebar | Button icon (normal, hover, pressed states) |
| `{id}.btn_minimize` | Minimize button, left of close | Button icon (normal, hover, pressed states) |
| `{id}.btn_maximize` | Maximize/restore toggle | Button icon (normal, restore states) |
| `{id}.resize_n/s/e/w/ne/nw/se/sw` | Invisible resize handles at edges and corners | Handle hit area size (typically 4-8 pixels) |
| `{id}.content` | Content area where the "app" renders | Content background color, padding, scrollbar style |

#### 4.5.3 Window Operations

| Operation | WM Behavior | SDI Calls |
|-----------|------------|-----------|
| **Create** | Allocate Window struct, create all child SDI objects at initial position, register in window list | `sdi.create()` for each child object, `sdi.load_png()` for frame/button assets |
| **Move (drag)** | On titlebar drag: calculate cursor delta per frame, apply to all child object positions | `sdi.get_mut("{id}.*")?.x += dx` for every child |
| **Resize** | On resize handle drag: update window dimensions, reposition edges and corners, notify content renderer of new available area | Reposition/resize affected child objects, `backend.set_clip_rect()` updated |
| **Focus (bring to front)** | Move all child objects to top of z-order, mark as active, update titlebar to active color | `sdi.move_to_top("{id}.*")` for every child |
| **Minimize** | Hide all child objects, add icon to taskbar (if skin has one) | `sdi.set_visible("{id}.*", false)`, create/show taskbar entry |
| **Maximize** | Snap window to full content area, store previous geometry for restore | Update all child positions/sizes to fill screen |
| **Close** | Call app's shutdown hook, destroy all child SDI objects, remove from window list | `sdi.destroy("{id}.*")` for every child |
| **Cascade** | Position newly created windows offset from the last, wrapping when reaching screen edge | Initial position = last window position + (24, 24) offset |

#### 4.5.4 Hit Testing

When a `PointerClick(x, y)` event arrives, the WM performs hit testing to determine the target. The test walks the window list in reverse z-order (topmost first) and checks regions in priority order:

1. **Titlebar buttons** -- close, minimize, maximize. Triggers the corresponding window operation.
2. **Titlebar body** -- initiates a drag operation. Subsequent `CursorMove` events move the window until pointer release.
3. **Resize handles** -- initiates a resize operation on the corresponding edge/corner.
4. **Content area** -- forwards the click (translated to content-local coordinates) to the app running inside the window.
5. **No hit** -- click landed on the desktop background. Deselects all windows, optionally triggers a desktop context menu.

If the clicked window is not already the topmost, the WM brings it to front before dispatching the event. This matches the standard desktop behavior of click-to-focus.

#### 4.5.5 Content Clipping

When a window's content exceeds its content area (scrolling text, tall file listings, large images), the content must be clipped at the window boundary. This requires a `set_clip_rect(x, y, w, h)` method on the `SdiBackend` trait -- the one addition to SDI's backend interface that the WM necessitates.

| Backend | Clip Implementation |
|---------|-------------------|
| PSP (GU) | `sceGuScissor(x, y, w, h)` -- hardware scissor rectangle |
| SDL2 | `SDL_RenderSetClipRect(&rect)` -- renderer-level clip |
| Framebuffer | Software clip during blit -- skip pixels outside rect |
| UE5 Render Target | Software clip during blit into RGBA buffer |

Clip state is pushed before rendering a window's content and popped afterward, so each window's content is isolated. The clip stack supports nesting for windows that contain sub-panels.

#### 4.5.6 Window Types

Skins define which window types are available. The WM provides the behavioral templates; the skin provides the visual treatment.

| Window Type | Behavior | Use Case |
|------------|----------|----------|
| **App Window** | Draggable, resizable, closable, minimizable, maximizable. Content rendered by an app module. Has titlebar, frame, and all controls. | Card database viewer, deck builder, text editor, file browser, email client |
| **Dialog** | Modal. Centered on screen, not draggable (or constrained to screen center). Blocks input to other windows until dismissed. Dim overlay behind. | Confirmation prompts, error messages, login screens, save dialogs |
| **Panel** | Docked to a screen edge. Not draggable (or constrained to its edge). Auto-hides optionally. | Taskbar (bottom), sidebar (left), notification tray (top-right), status bar |
| **Floating Widget** | Small, always-on-top, draggable. No minimize/maximize. Minimal or no frame. | Clock, system monitor, notification toasts, quick-launch shortcuts |
| **Fullscreen** | No frame, no titlebar, covers entire content area. App controls its own exit mechanism. | Terminal emulator, game within a game, video player, boot splash |

#### 4.5.7 Platform Applicability

Not every platform needs or benefits from the window manager. The skin's feature gates control availability.

| Platform | WM Enabled | Rationale |
|----------|-----------|-----------|
| PSP | No | 480x272 at 30-60fps. Screen too small for overlapping windows. Classic skin uses fixed-position SDI objects for its icon grid. |
| Raspberry Pi (briefcase) | Optional | Depends on display. Pi 5 with HDMI to a monitor inside or attached to the briefcase lid can run the Desktop or Agent Terminal skin with windowing. Headless operation uses Terminal skin via remote terminal. |
| Desktop (dev) | Yes | Full resolution display. Desktop skin uses windowed interface. Also useful for debugging -- inspect multiple OS subsystems simultaneously. |
| UE5 (in-game) | Yes | In-game computers with Desktop skin present windowed interfaces on the virtual monitor. The WM resolution matches the virtual screen texture (e.g., 1024x768 for a high-res in-game monitor, 480x272 for a handheld prop). |

#### 4.5.8 Skin-Driven Appearance

The WM handles behavior uniformly; the skin defines every visual detail. Two skins using the same WM can look completely different:

| Visual Property | Desktop Skin | Corrupted Skin |
|----------------|-------------|---------------|
| Titlebar | Clean gradient, centered text, rounded top corners | Jagged edges, flickering title text, random color shifts per frame |
| Frame | 1px subtle border, soft drop shadow | Torn border with missing segments, no shadow, occasional frame duplication offset by a few pixels |
| Close button | Standard x icon, red on hover | Glitched icon that sometimes shows x, sometimes shows random glyph |
| Drag behavior | Smooth 1:1 cursor tracking | Jittery -- WM adds random +/-2px noise to position each frame |
| Resize | Smooth, snaps to grid optionally | Fights back -- window occasionally resizes itself randomly |
| Window creation | Clean fade-in animation | Stuttered appearance with screen tear artifact |

The corrupted skin demonstrates that the WM's behavioral hooks (position update, resize calculation, animation tick) can be intercepted by skin-defined modifiers. The WM exposes optional callback points where the skin can inject visual distortion, and the skin's `features.toml` declares which modifiers to apply.

---

## 5. Backend Abstraction Layer

### 5.1 Rendering Backend Trait

Every rendering operation passes through `SdiBackend`. Three implementations exist; a fourth (framebuffer) is planned.

| Method | PSP (GU) | SDL2 | Framebuffer [PLANNED] | UE5 Render Target |
|--------|---------|------|-------------|-------------------|
| `init()` | sceGuInit + display list | SDL_CreateWindow + Renderer | open /dev/fb0 + mmap | Allocate RGBA buffer |
| `blit(tex, x, y, w, h)` | sceGuDrawArray (Sprites) | SDL_RenderCopy | memcpy to mapped buf | memcpy to RGBA buffer |
| `swap_buffers()` | sceGuSwapBuffers + VBlank | SDL_RenderPresent | ioctl WAITFORVSYNC | Set dirty flag (UE5 reads) |
| `load_texture(data)` | RAM alloc (16-byte aligned) | SDL_CreateTexture | Decode to RGB buf | Decode to RGBA buf |
| `clear(color)` | sceGuClear | SDL_RenderClear | memset framebuffer | memset RGBA buffer |
| `shutdown()` | sceGuTerm | SDL_Destroy* | munmap + close | Free buffer |
| `get_buffer()` | N/A | N/A | N/A | Return raw RGBA ptr |
| `set_clip_rect(x,y,w,h)` | sceGuScissor | SDL_RenderSetClipRect | Software clip bounds | Software clip bounds |
| `reset_clip_rect()` | sceGuScissor(full) | SDL_RenderSetClipRect(NULL) | Clear clip bounds | Clear clip bounds |

The UE5 backend is unique in that it doesn't own a display. It renders to a shared memory buffer that UE5 reads via `get_buffer()`. This is the zero-copy bridge: Rust writes pixels, UE5's `UpdateTextureRegions()` reads them directly.

### 5.2 Input Backend Trait

| Event Type | PSP Source | Desktop/Pi Source | UE5 Source |
|-----------|-----------|-------------------|------------|
| `CursorMove(x, y)` | Analog stick via sceCtrlReadBufferPositive | Mouse motion or gamepad right stick | Line trace UV mapped to virtual screen |
| `ButtonPress(Button)` | D-pad, Cross, Circle, Triangle, Square | Keyboard keys or gamepad buttons | Interact key bindings |
| `Trigger(Trigger)` | L/R shoulder buttons | Keyboard L/R or gamepad triggers | Gamepad triggers |
| `TextInput(char)` | On-screen keyboard (sceUtilityOsk) | Physical keyboard input | Keyboard captured during interaction |

### 5.3 Network Backend Trait

| Operation | PSP (sceNetInet) | Linux (std::net) | UE5 (debug only) |
|-----------|-----------------|------------------|-------------------|
| TCP listen | sceNetInetSocket + Bind + Listen | TcpListener::bind() | TcpListener::bind() on localhost |
| TCP accept | sceNetInetAccept | listener.accept() | listener.accept() |
| TCP send/recv | sceNetInetSend / Recv | stream.read() / write() | stream.read() / write() |
| TCP connect (outbound) | sceNetInetConnect | TcpStream::connect() | TcpStream::connect() |
| WiFi connect | sceNetApctlConnect | N/A (OS manages) | N/A |
| DNS resolve | sceNetResolverStartNtoA | std::net::ToSocketAddrs | std::net::ToSocketAddrs |

Note: outbound TCP connect is essential for the PSP remote agent control use case (Section 11).

---

## 6. Skin System

### 6.1 Skin Architecture

A skin is a data-driven configuration that defines the visual and behavioral personality of an OS instance. Skins do not contain code -- they are TOML manifests referencing layout definitions, theme assets, and feature flags. The core framework interprets skins at runtime.

| Skin Component | Description | Format |
|---------------|-------------|--------|
| Manifest | Name, version, author, description, target resolution, required plugins | `skin.toml` |
| Layout | SDI object definitions: names, positions, sizes, z-order, visibility defaults | `layout.toml` |
| Theme | Colors, fonts, images, backgrounds, icon sets, animations | Asset directory + `theme.toml` |
| Feature gates | Which command categories are available, which dashboard pages exist, whether file browser is enabled | `features.toml` |
| VFS overlay | What the virtual file system root looks like -- which directories exist, what files are pre-populated | `filesystem.toml` + content directory |
| Strings | All user-facing text: menu labels, command help text, error messages, boot sequence text | `strings.toml` |

### 6.2 Skins

| Skin | Description | Primary Target | Use Case | Status |
|------|-------------|---------------|----------|--------|
| Classic | PSIX-style icon grid dashboard with document icons, tabbed status/bottom bars, chrome bezels, wave arc wallpaper | PSP / Pi / Desktop | Homebrew shell OS, the original C codebase experience modernized with PSIX styling | **Implemented** |
| Terminal | Full-screen command line with CRT visual metadata (scanlines, phosphor glow, screen curvature -- applied by host shader) | UE5 / Desktop | In-game hacking terminals, retro computer props, SSH-style remote access | Planned |
| Tactical | Stripped-down command interface with status displays, no visual chrome, monospace grid layout | UE5 | Military command consoles, security systems, restricted-access terminals | Planned |
| Corrupted | Randomized SDI object positions/alpha, garbled command output, visual glitch artifacts, "repair" puzzle hooks | UE5 | Damaged terminals the player must fix, environmental storytelling | Planned |
| Desktop | Window-like panels, taskbar, start menu analog, multiple "apps" visible simultaneously | UE5 / Pi | Civilian in-game computers, player home terminals | Planned |
| Agent Terminal | Agent-focused dashboard: agent status panel, MCP tool browser, remote session manager, system health, tamper status indicator | Pi (briefcase) | Briefcase field terminal for AI agent management (see Section 10) | Planned |

### 6.3 Skin Loading and Switching

Each OS instance is initialized with a skin. Skins can be hot-swapped at runtime (e.g., a "corrupted" terminal that the player "repairs" transitions to the "tactical" skin). The core framework loads the new skin manifest, tears down the current SDI object tree, rebuilds it from the new layout, reloads theme assets, and reconfigures feature gates. The VFS overlay is preserved across skin swaps -- file state persists.

---

## 7. Unreal Engine 5 Integration

### 7.1 Integration Architecture

OASIS_OS compiles as a static library (`.lib` / `.a`) or C-compatible dynamic library (`.dll` / `.so`) that UE5 links against. A C FFI boundary in `crates/oasis-ffi/` exports an opaque handle API. The UE5 side wraps this in an Actor Component that owns an OS instance, ticks it per frame, and bridges rendering and input.

```
+-----------------------------------------------------+
|  Unreal Engine 5                                    |
|                                                     |
|  AComputerTerminalActor                             |
|    +-- UStaticMeshComponent (monitor prop)          |
|    +-- UOasisOSComponent                             |
|    |     +-- Owns: oasis_instance_t* (opaque FFI)    |
|    |     +-- Owns: UTexture2D (render target)       |
|    |     +-- Tick(): oasis_tick(handle, dt)           |
|    |     +-- Render(): oasis_get_buffer(handle)       |
|    |     |            -> UpdateTextureRegions()      |
|    |     +-- Input(): oasis_send_input(handle, evt)   |
|    +-- UMaterialInstanceDynamic (maps texture to mesh)|
|                                                     |
|  On player interaction:                             |
|    Line trace -> hit monitor mesh                   |
|    Calculate UV at hit point                        |
|    Map UV to virtual screen coordinates             |
|    Send CursorMove/PointerClick to oasis_send_input  |
|    Capture keyboard -> send TextInput events        |
+-----------------------------------------------------+
        | FFI boundary (C ABI)
+-------+---------------------------------------------+
|  OASIS_OS (Rust static lib)                          |
|                                                     |
|  oasis_create(skin, config) -> handle                |
|  oasis_tick(handle, delta_time)                      |
|  oasis_send_input(handle, event_type, x, y, key)    |
|  oasis_get_buffer(handle) -> *const u8, width, height|
|  oasis_get_dirty(handle) -> bool                     |
|  oasis_destroy(handle)                               |
|                                                     |
|  Internal: SdiBackend::UE5RenderTarget              |
|            InputBackend::FFIInput                   |
|            VfsBackend::GameAssetVFS                 |
+-----------------------------------------------------+
```

### 7.2 FFI Boundary

The FFI layer exports a minimal C-ABI surface. All internal Rust state is behind an opaque pointer. UE5 never sees Rust types.

| FFI Function | Signature | Description |
|-------------|-----------|-------------|
| `oasis_create` | `(skin_path: *const c_char, config_path: *const c_char) -> *mut OasisInstance` | Create a new OS instance with the specified skin |
| `oasis_destroy` | `(handle: *mut OasisInstance)` | Tear down and free an OS instance |
| `oasis_tick` | `(handle: *mut OasisInstance, delta_seconds: f32)` | Advance OS state by one frame |
| `oasis_send_input` | `(handle: *mut OasisInstance, event: *const OasisInputEvent)` | Deliver an input event |
| `oasis_get_buffer` | `(handle: *mut OasisInstance, width: *mut u32, height: *mut u32) -> *const u8` | Get pointer to RGBA framebuffer |
| `oasis_get_dirty` | `(handle: *mut OasisInstance) -> bool` | Check if framebuffer changed since last read |
| `oasis_send_command` | `(handle: *mut OasisInstance, cmd: *const c_char) -> *mut c_char` | Execute a terminal command, return output (caller frees) |
| `oasis_set_vfs_root` | `(handle: *mut OasisInstance, path: *const c_char)` | Change VFS root (e.g., per-terminal game content) |
| `oasis_register_callback` | `(handle: *mut OasisInstance, event: u32, cb: extern fn(*const c_char))` | Register callback for OS events (app launch, file access, etc.) |

### 7.3 Render Pipeline

1. `oasis_tick()` advances the OS state (cursor animation, blinking cursors, scrolling text, pending command output)
2. SDI scene graph draws all visible objects to the UE5RenderTarget backend's internal RGBA buffer
3. Backend sets dirty flag
4. UE5's `TickComponent()` checks `oasis_get_dirty()` -- if true, calls `oasis_get_buffer()` and `UpdateTextureRegions()` to push pixels to the `UTexture2D`
5. The `UTexture2D` is sampled by a material applied to the monitor mesh
6. Optional: the material applies CRT shader effects (scanlines, curvature, phosphor bloom) based on skin metadata -- the Rust side renders clean pixels, UE5 applies the aesthetic

This is effectively zero-copy when Rust and UE5 share the same memory page for the buffer. On platforms where that's not possible, it's a single memcpy per dirty frame.

### 7.4 Input Pipeline

1. Player aims at in-game monitor, presses interact key
2. UE5 enters "computer interaction mode": HUD suppressed, camera locks, input rerouted
3. Line trace from crosshair hits monitor mesh -> compute UV at hit point
4. UV coordinates mapped to virtual screen resolution (e.g., UV(0.5, 0.5) -> screen(240, 136) on a 480x272 virtual display)
5. Mouse movement -> `CursorMove` events; mouse click -> `PointerClick` events
6. Keyboard input captured -> `TextInput` events (for terminal skins) or `ButtonPress` events (for dashboard skins)
7. Player presses escape/interact key again -> exit interaction mode, restore normal camera and input

### 7.5 Gameplay Integration via Callbacks

The `oasis_register_callback` function lets UE5 react to OS-level events. This enables gameplay mechanics driven by in-game computer interaction:

| Callback Event | Trigger | Gameplay Example |
|---------------|---------|-----------------|
| `ON_FILE_ACCESS` | Player opens a file via `cat` or file browser | Unlock a lore entry, trigger a quest objective |
| `ON_COMMAND_EXEC` | Player executes a terminal command | Hacking puzzle: execute the right sequence of commands to bypass "security" |
| `ON_APP_LAUNCH` | Player launches an "app" from the dashboard | Open a game-specific interface, launch a mini-game |
| `ON_LOGIN` | Player enters the correct pre-shared key | Gain access to a restricted terminal with new commands |
| `ON_NETWORK_SEND` | Player sends a message via in-game email | Deliver message to another player's in-game computer, NPC responds |
| `ON_PLUGIN_LOAD` | Player installs a "plugin" found elsewhere in the game world | Unlock new terminal capabilities as a progression mechanic |

### 7.6 Multiple Instances

Each in-game computer is an independent OS instance with its own skin, VFS root, plugin set, and state. A single UE5 level might contain a dozen terminals, each running a different skin with different content. Instances share no state unless explicitly connected (e.g., an in-game "network" where sending a message on one terminal delivers it to another's VFS inbox).

---

## 8. PSP Platform Implementation

### 8.1 Memory and Resource Constraints

The PSP has 32MB of main RAM (64MB on PSP-2000+), a 333MHz MIPS R4000 CPU, and 2MB of dedicated VRAM. The original C codebase allocates a 20MB heap (`PSP_HEAP_SIZE_KB(1024 * 20)`) and runs 5-6 concurrent threads.

| Constraint | Impact on Rust Design | Mitigation |
|-----------|----------------------|------------|
| 32MB RAM | No std collections with unbounded growth; fixed-capacity containers preferred | Use heapless or tinyvec for bounded collections; arena allocators for scene graph |
| No MMU isolation | All threads share address space; corruption in one affects all | Rust ownership prevents data races; unsafe blocks minimized and audited |
| 333MHz CPU | No room for abstraction overhead; zero-cost abstractions critical | Monomorphization over dynamic dispatch; inline hot paths; profile with PPSSPP |
| 2MB VRAM | Textures must be carefully managed; power-of-two dimensions required | Texture atlas for UI elements; lazy loading; VRAM allocation tracker |
| No ASLR/stack canaries | Network-facing code is high-value exploit target | Rust memory safety eliminates buffer overflows at compile time |

### 8.2 Kernel Mode and Privileges

The original C codebase runs in kernel mode (`PSP_MODULE_INFO` flag `0x1000`), granting access to all hardware registers, the ability to load arbitrary PRX modules, and direct Memory Stick I/O.

**rust-psp SDK:** OASIS_OS depends on a standalone fork of the rust-psp SDK at [github.com/AndrewAltimit/rust-psp](https://github.com/AndrewAltimit/rust-psp), referenced as a git dependency. The upstream project (`github.com/overdrivenpotato/rust-psp`, MIT license) is maintained at a low cadence (~3-4 commits/year) and lacks kernel mode support (issue #48, open since June 2020). The fork extends the SDK with kernel mode module support (`PSP_MODULE_INFO` flag `0x1000`), `#![no_std]` improvements, edition 2024 modernization, safety fixes, and additional syscall bindings -- without waiting on upstream. The fork tracks upstream for bug fixes but diverges for kernel-mode and feature additions.

OASIS_OS initially targets user mode, which is sufficient for rendering, input, networking, and file I/O on modern custom firmware. Kernel-mode features (Media Engine coprocessor, raw hardware register access) are the primary motivation for extending the SDK fork. Until kernel mode is fully implemented, these features are accessed through pre-compiled PRX modules loaded at runtime. The `#![no_std]` + `#![no_main]` entry point uses `psp::module!()` macro with `psp_main()`.

### 8.3 Assembly Preservation [PLANNED]

> **Status:** The assembly files have not yet been extracted from the original C archive. The `asm/` directory does not yet exist.

Three assembly files from the original C codebase must be preserved rather than ported:

- **me.S:** Media Engine coprocessor initialization. Directly manipulates CP0 registers, performs cache invalidation, and boots the ME. ~60 lines of hand-tuned MIPS assembly.
- **audiolib.S:** PRX module stub definitions for the audio library (MP3_Init, MP3_Load, MP3_Play, etc.).
- **pspstub.s:** Macro definitions for STUB_START/STUB_FUNC/STUB_END used by the audio stubs.

Included in the Rust build via `global_asm!` or linked as pre-assembled object files in `build.rs`.

### 8.4 Firmware Modernization: 1.50 to 6.60/6.61

The original C codebase was architecturally coupled to PSP firmware 1.50, the only firmware that ran unsigned homebrew without custom firmware. OASIS_OS targets firmware 6.60/6.61 with modern custom firmware (ARK-4, PRO CFW, or ME CFW, made persistent via Infinity 2). This eliminates every firmware-specific hack in the original codebase.

#### 8.4.1 Eliminated Legacy Mechanisms

| Original Mechanism | Why It Existed (FW 1.50) | OASIS_OS Disposition (FW 6.60/6.61) |
|------------------------|-------------------------|-------------------------------------|
| KXploit directory scanning (`GAMEFOLDER` + `GAMEFOLDER%`) | Firmware 1.50 required a paired directory exploit to trick the kernel into running unsigned code. The '%' suffix exploited a directory validation bug. | Eliminated entirely. Modern CFW runs unsigned EBOOTs directly from `ms0:/PSP/GAME/`. Dashboard scanner reduced to simple recursive directory traversal. |
| KXploit title stripping ("KXPloit Boot by PSP-DEV Team") | KXploit injected a watermark string into PBP titles that cluttered the dashboard. | Eliminated. No watermarks exist in modern homebrew EBOOTs. |
| Dual default icons (`icon_default_15` vs `icon_default_10`) | Distinguished between homebrew targeting FW 1.50 vs FW 1.00 based on directory structure. | Eliminated. Single default icon for all homebrew. Icons extracted from PBP ICON0 section when available. |
| `__attribute__((constructor))` kernel escalation | `pspKernelSetKernelPC()` and `pspSdkInstallNoPlainModuleCheckPatch()` patched the 1.50 kernel at load time to gain kernel-mode access and disable module signature checks. | Replaced by CFW-provided kernel access. rust-psp targets the CFW's documented entry points. Privilege escalation is the CFW's responsibility. |
| `pspSdkInstallNoDeviceCheckPatch()` | Disabled firmware 1.50's device check that prevented certain I/O operations on unsigned code. | Eliminated. Modern CFW disables all such checks globally. |
| DevHook integration (`devhook.c`, `ms0:/dh/`) | Firmware 1.50 lacked APIs required by newer commercial games. DevHook emulated a higher firmware's flash filesystem from the Memory Stick. | Eliminated entirely. Firmware 6.60/6.61 natively includes all game APIs. ISO loading is a built-in CFW feature via Inferno/NP9660/Prometheus drivers. |
| DevHook config structure (DH04 magic, flash path, reboot path) | Stored emulated firmware version, CPU/bus speeds, ISO path, and flash redirect path for the DevHook kernel module. | Eliminated. No equivalent needed. ISO path stored in standard OASIS_OS config. |
| `sceKernelLoadModuleBufferUsbWlan()` | Firmware 1.50-specific kernel function for loading modules from memory buffers, used to bypass signature checks on PRX modules. | Replaced by standard `sceKernelLoadModule()` which loads unsigned PRX files natively on modern CFW. |
| Commented-out error handling in network init | Firmware 1.50's WiFi stack was unreliable (limited WPA support, buggy AP connection). | Proper error handling restored. Firmware 6.60/6.61 has a mature, stable WiFi stack with full WPA2 support. |

#### 8.4.2 New Capabilities Enabled by Modern Firmware

| Capability | Details |
|-----------|---------|
| 64MB RAM (PSP-2000+) | Firmware 1.50 only ran on the PSP-1000 (32MB). Modern CFW on PSP-2000/3000/Go exposes the full 64MB. ARK-4 provides an "Auto" mode that enables extra RAM for homebrew that requests it. OASIS_OS detects the model at runtime via `sceKernelDevkitVersion()` and adjusts heap allocation, texture cache size, and plugin memory budget accordingly. |
| Stable kernel API surface | Modern CFW provides a consistent, well-documented kernel API across all PSP models. The fragile 1.50-specific patches are replaced by a stable interface maintained by the CFW community. |
| Built-in ISO/CSO driver | CFW's Inferno driver handles ISO mounting transparently. The dashboard can launch ISOs via standard `sceKernelLoadExec` -- no kernel patching, no DevHook, no flash emulation. |
| Plugin (PRX) hot-loading | `sceKernelLoadModule` works reliably for unsigned PRX on modern CFW. The plugin system can dynamically load/unload modules without signature bypass hacks. |
| WPA2 WiFi | Full WPA2-PSK support with stable AP connection handling. The remote terminal module can rely on infrastructure mode networking being functional and robust. This is what makes PSP-based remote agent control viable (Section 11). |
| PSP Go support | The original codebase never supported the PSP Go. Modern CFW abstracts storage access, allowing OASIS_OS to run on all PSP models including the Go (`ef0:/` instead of `ms0:/`). |

#### 8.4.3 Target Custom Firmware Stack

- **Base firmware:** 6.61 (Sony's final official firmware, with all security and stability patches)
- **Custom firmware:** ARK-4 (actively maintained, supports all PSP models including Street/E-1000, provides Inferno ISO driver, extra RAM management, and comprehensive plugin support)
- **Persistence:** Infinity 2 for semi-permanent CFW on PSP-2000 (TA-088v3+), PSP-3000, and PSP Go; cIPL flasher for permanent CFW on PSP-1000 and early PSP-2000 (TA-088v2 and older)
- **Storage paths:** `ms0:/PSP/GAME/OASISOS/` for Memory Stick models; `ef0:/PSP/GAME/OASISOS/` for PSP Go. Runtime detection via `sceIoDevctl()` determines available storage.

OASIS_OS does not require or depend on any specific custom firmware choice. Any CFW that provides kernel-mode access and unsigned code execution on firmware 6.60 or 6.61 is sufficient.

#### 8.4.4 Simplified Application Discovery

The firmware modernization dramatically simplifies the dashboard's application discovery logic. The original `scan_for_exec` was 128 lines of C with complex KXploit handling. The OASIS_OS equivalent:

- Recursively scan `ms0:/PSP/GAME/` (or `ef0:/` on PSP Go) for directories containing EBOOT.PBP
- Parse each PBP header to extract title (SFO section) and icon (ICON0 section)
- Scan configured ISO directories for .ISO/.CSO files (CFW handles mounting)
- Skip the OASIS_OS directory itself
- Register discovered applications with the dashboard grid

No KXploit handling, no '%' directory pairing, no title watermark stripping, no firmware-version-specific icon selection. The code reduction is approximately 60% in the discovery module alone.

---

## 9. Linux / Raspberry Pi Platform

### 9.1 Behavioral Differences

| Behavior | PSP | Raspberry Pi / Linux |
|----------|-----|---------------------|
| App launching | `sceKernelLoadExec` (replaces process) | fork/exec (returns to shell) |
| Multitasking | Single process, multiple threads | Full process isolation |
| Plugin loading | PRX modules via `sceKernelLoadModule` | Dynamic .so via dlopen/libloading |
| File system root | `ms0:/` (Memory Stick) | Configurable path (e.g., `/home/pi/apps/`) |
| Power management | `scePowerGetBatteryLifePercent` | `/sys/class/power_supply/` sysfs reads |
| Display | 480x272 fixed, 32-bit color via GU | Configurable resolution via SDL2 or fbdev |
| Networking | sceNetInet (WiFi only, infrastructure mode) | std::net (Ethernet or WiFi, full stack) |
| Boot flow | Custom firmware loads EBOOT.PBP | systemd service, auto-login to kiosk mode |

### 9.2 Raspberry Pi Deployment

On the Raspberry Pi, OASIS_OS operates as a kiosk-mode application booting directly into the shell interface. Recommended deployment uses Raspberry Pi OS Lite with auto-login to launch the OASIS_OS binary on TTY1.

- **Boot-to-shell time:** Approximately 3-5 seconds on a Pi 5, from power-on to rendered dashboard.
- **Display options:** Official Raspberry Pi touchscreen (800x480), HDMI at configurable resolution, or headless with remote terminal only.
- **Input options:** USB keyboard/mouse, USB gamepad, GPIO-wired buttons, touchscreen (via SDL2 touch events), or remote terminal.
- **Systemd integration:** A `oasis-os.service` unit file manages lifecycle, restart-on-crash, and dependency on `network-online.target`.
- **Coexistence with tamper services:** On the briefcase Pi, `oasis-os.service` runs alongside `tamper-sensor.service` and `tamper-gate.service`. OASIS_OS is the user-facing interface; the tamper services are the physical security layer. They share the Pi but do not interact directly -- the tamper system operates at the systemd level independent of whatever user-space application is running.

---

## 10. Briefcase Agent Terminal [PLANNED]

> **Status:** The agent-terminal skin and its integration with tamper services described in this section are planned but not yet implemented. The core framework supports the necessary abstractions (skin system, command interpreter, remote terminal), and the tamper_briefcase package exists, but the agent-terminal skin configuration and briefcase-specific commands have not been created.

### 10.1 Context

The repository includes a tamper-responsive briefcase system (`packages/tamper_briefcase/`) -- a Raspberry Pi 5 inside a hardened Pelican 1490 case with dual-sensor tamper detection, LUKS2 full-disk encryption, cryptographic wipe on unauthorized access, and hybrid classical+post-quantum recovery USB. The detailed hardware design is documented in `docs/hardware/secure-terminal-briefcase.md`.

Currently, the briefcase Pi boots to a bare Linux TTY. OASIS_OS replaces this with a themed, interactive shell OS that serves as the operator-facing interface for the field-deployable agent terminal.

### 10.2 Agent Terminal Skin

The `agent-terminal` skin is purpose-built for the briefcase use case. It presents a dashboard tailored to AI agent management rather than homebrew launching or game interaction.

| Dashboard Element | Description |
|-------------------|-------------|
| Agent Status Panel | Shows connected agents (Claude, Gemini, Codex, OpenCode, Crush) with availability indicators. Reads from `.agents.yaml` configuration. |
| Remote Session Manager | List of saved remote hosts. Select one to open an outbound terminal session (SSH-like) to a machine running agent infrastructure. |
| MCP Tool Browser | Lists available MCP tools from configured servers. Invoke tools directly from the command line: `mcp code-quality lint /path/to/file`. |
| System Health | CPU temp, memory, battery (via `/sys/class/power_supply/`), disk usage, network status. |
| Tamper Status | Current state of the tamper system (DISARMED / ARMING / ARMED). Reads the tamper-gate state file. Visual indicator changes color. |
| Quick Actions | One-key shortcuts: lock screen, arm system, open remote session, run CI check, pull latest code. |

### 10.3 Integration Points

| Component | Interaction |
|-----------|-------------|
| `tamper-sensor.service` | OASIS_OS reads the state file to display tamper status. No write access -- display only. |
| `tamper-gate.service` | OASIS_OS can send a disarm request via FIFO when the user authenticates through the OASIS_OS login screen (equivalent to the challenge prompt). |
| `automation-cli` | The `agent-terminal` skin registers CI commands: `ci run full`, `ci run rust-full`, etc. These invoke `automation-cli` installed on the Pi or accessible via Docker. |
| MCP servers | On the local network, MCP servers (code-quality, gemini, etc.) are reachable via their configured transports. The `mcp` command category in the interpreter dispatches tool calls. |
| Board manager | `board-manager query` shows ready work from the GitHub Projects board. Claim and release issues from the terminal. |

### 10.4 Boot Sequence

```
1. Pi 5 powers on (USB-C bank)
2. LUKS passphrase prompt (initramfs) -- user unlocks root partition
3. systemd starts tamper-sensor.service + tamper-gate.service
4. systemd starts oasis-os.service (After=tamper-gate.service)
5. OASIS_OS initializes with agent-terminal skin
6. Framebuffer or SDL2 backend renders dashboard to display
7. Remote terminal listener binds to configured port
8. Operator interacts via local keyboard/display or remote terminal
```

### 10.5 Headless Operation

When no display is attached (e.g., briefcase closed, operating purely via network), OASIS_OS still runs with the framebuffer backend writing to `/dev/fb0` (which is simply not visible). The remote terminal is the sole interaction path. An operator on the same network can:

```bash
# From a laptop or another device on the network
telnet 192.168.x.x 9000

# Full OASIS_OS command session
> agent status
Claude: available (CLI)
Gemini: available (MCP)
Codex: available (MCP)

> board query
#142 [Todo] Fix authentication edge case
#147 [Todo] Add rate limiting to API

> remote dev-server
Connecting to dev-server (192.168.0.100:22)...
Connected. Type 'exit' to return to OASIS_OS.
$
```

---

## 11. PSP Remote Agent Control [PLANNED]

> **Status:** The outbound TCP remote session capability described here is planned. The core framework's remote terminal module supports inbound TCP listening, but the outbound `remote` command, VT100 emulation, saved hosts configuration, and PSP-specific input shortcuts are not yet implemented.

### 11.1 Concept

A PSP running OASIS_OS on infrastructure WiFi can establish outbound TCP connections to machines running AI agent infrastructure. The remote terminal works bidirectionally -- the PSP is both a server (accepting inbound sessions for its own OS) and a client (initiating outbound sessions to remote hosts). This makes a PSP with modern custom firmware (and its reliable WPA2 WiFi stack) a viable portable controller for the agent ecosystem.

This is not a theoretical capability. PPSSPP runs locally on the development machine and version 1.19+ maps `sceNetInet` to real host sockets, meaning the entire remote session stack can be developed and tested in the emulator against real network services before deploying to hardware.

### 11.2 Architecture

```
+----------------------------+          +----------------------------+
|  PSP (OASIS_OS)             |  WiFi    |  Agent Host Machine        |
|                            | -------> |                            |
|  remote dev-server         |  TCP     |  SSH / agent-terminal port |
|    +-- outbound TCP        |          |    +-- Claude Code CLI     |
|    +-- VT100 emulation     |          |    +-- automation-cli      |
|    +-- command passthrough  |          |    +-- board-manager       |
|                            |          |    +-- MCP servers         |
+----------------------------+          +----------------------------+
```

The `remote` command in the OASIS_OS interpreter opens an outbound TCP session to a saved host. The session runs inside the OASIS_OS terminal UI -- keystrokes from the PSP's on-screen keyboard or USB keyboard (on PSP-2000+) are sent over the wire, and received text is rendered in the terminal view. A minimal VT100 escape sequence parser handles cursor positioning, color, and clearing.

### 11.3 Use Cases

| Scenario | How It Works |
|----------|-------------|
| Check agent status from a PSP | `remote briefcase` -> `agent status` -- see which agents are online |
| Claim board work | `remote briefcase` -> `board query` -> `board claim 142` -- claim an issue for implementation |
| Trigger CI | `remote dev-server` -> `automation-cli ci run full` -- kick off CI from anywhere on the network |
| Monitor PR feedback | `remote dev-server` -> `pr-monitor 48` -- watch for review comments |
| Emergency wipe trigger | `remote briefcase` -> `tamper arm` -- re-arm the briefcase tamper system remotely |

### 11.4 Saved Hosts Configuration

Hosts are stored in the OASIS_OS config file on the Memory Stick:

```toml
# ms0:/PSP/GAME/OASISOS/config/hosts.toml

[[host]]
name = "briefcase"
address = "192.168.0.50"
port = 9000
protocol = "oasis-terminal"

[[host]]
name = "dev-server"
address = "192.168.0.100"
port = 22
protocol = "raw-tcp"

[[host]]
name = "gpu-box"
address = "192.168.0.222"
port = 9000
protocol = "oasis-terminal"
```

### 11.5 PSP Input Considerations

The PSP's input limitations shape the remote terminal experience:

| Input Method | Availability | Speed | Use Case |
|-------------|-------------|-------|----------|
| On-screen keyboard (sceUtilityOsk) | All PSP models | Slow (d-pad character selection) | Short commands, passwords |
| USB keyboard | PSP-2000+ only | Full typing speed | Extended terminal sessions |
| D-pad shortcuts | All models | Instant | Mapped to common commands (L+Up = `agent status`, R+Triangle = `board query`) |
| Analog stick cursor | All models | Moderate | Scrolling terminal output, selecting from menus |

The `agent-terminal` skin on PSP adapts by offering a command palette accessible via the Triangle button -- a scrollable list of frequently used agent commands that can be executed with a single button press rather than typed out character by character.

---

## 12. Virtual File System

### 12.1 VFS Architecture

The virtual file system is the abstraction that makes the same command interpreter work across all platforms. On PSP, `ls` lists Memory Stick contents. On Pi, it lists real Linux directories. In UE5, it lists game-authored content. The VFS trait provides a uniform interface over fundamentally different storage backends.

| VFS Operation | Trait Method | Description |
|--------------|-------------|-------------|
| List directory | `readdir(path) -> Vec<Entry>` | Return entries at path |
| Read file | `read(path) -> Vec<u8>` | Return file contents |
| Write file | `write(path, data)` | Write data to path |
| File info | `stat(path) -> Metadata` | Size, modified time, type |
| Create directory | `mkdir(path)` | Create directory |
| Delete | `remove(path)` | Delete file or directory |
| Exists | `exists(path) -> bool` | Check existence |

### 12.2 VFS Backends

| Backend | Backing Store | Use Case |
|---------|--------------|----------|
| RealFS | Native filesystem (ms0:/, Linux paths) | PSP, Pi, desktop |
| GameAssetVFS | UE5 data assets + save game data | In-game computers in UE5 projects |
| OverlayVFS | Layered: read-only base (skin defaults) + writable layer (user changes) | All platforms -- skin-provided files with user modifications |
| MemoryVFS | In-memory tree, no persistence | Unit tests, ephemeral terminals |

### 12.3 Game Asset VFS

The GameAssetVFS is the most novel backend. It presents game-authored content as a filesystem that players navigate with standard commands. Each in-game terminal has its own VFS root configured by level designers.

Examples of in-game file content:

- `/home/user/inbox/message_from_rival.txt` -- lore-delivering text file, triggers `ON_FILE_ACCESS` callback when read
- `/var/log/system.log` -- procedurally generated log file with clues for a puzzle
- `/opt/trading/deck_analyzer` -- "executable" that, when launched, opens a game-specific UI
- `/etc/security/access.conf` -- file the player must edit (via a `nano`-like command or `echo >>`) to solve a hacking puzzle
- `/tmp/upload/card_data.json` -- file deposited by another player via the in-game network

The VFS root, pre-populated content, and write permissions are all defined per-terminal in the skin's `filesystem.toml`.

---

## 13. Development Workflow

### 13.1 Three-Tier Testing Strategy

| Tier | Environment | Tests | Cycle Time |
|------|------------|-------|------------|
| 1 -- Desktop | Native SDL2 build on dev machine | UI layout, theming, scene graph, command interpreter, plugin loading, VFS, skins | < 1 second (hot rebuild) |
| 2 -- PPSSPP (container) | PSP build running in MCP-patched PPSSPP container | GU rendering, PSP input, networking (infra mode), memory constraints, thread behavior, agent-assisted debugging via MCP | ~5 seconds (cross-compile + launch) |
| 3 -- Hardware/UE5 | Real PSP + Raspberry Pi + UE5 editor | WiFi, USB, Media Engine, GPIO, boot-to-shell, in-game render target, interaction flow | ~30 seconds (deploy + reboot/PIE) |

### 13.2 Containerized PPSSPP with MCP Integration [PLANNED]

> **Status:** This section describes planned infrastructure that has not yet been built. Currently, PPSSPP is used for testing via the project's existing `ppsspp` Docker Compose service (a stock PPSSPP build with X11 forwarding). The MCP-patched container, patch files, and MCP schema directory described below are future work.

PPSSPP runs inside a Docker container built from source with a set of patches that embed an MCP server directly into the emulator. This gives AI agents deep introspection into the running PSP environment -- memory state, GPU pipeline, thread scheduling, network sockets -- through the same MCP tool interface used by every other tool in the repository. The container follows the project's container-first philosophy: no local PPSSPP installation required, reproducible builds, and CI-ready headless mode.

#### 13.2.1 Container Architecture

```
+----------------------------------------------------------+
|  Docker: ppsspp-mcp                                      |
|                                                          |
|  PPSSPP (patched)                                        |
|    +-- PSP emulation core                                |
|    +-- MCP server (STDIO or TCP :8808)                   |
|    |     +-- psp.memory.read / write / search            |
|    |     +-- psp.gpu.state / vram_dump / texture_list    |
|    |     +-- psp.debug.breakpoint / step / registers     |
|    |     +-- psp.debug.threads / stack_trace             |
|    |     +-- psp.net.sockets / capture / inject_latency  |
|    |     +-- psp.emu.screenshot / save_state / load_state|
|    |     +-- psp.emu.frame_advance / set_speed           |
|    +-- Headless renderer (no X11 required for CI)        |
|    +-- Infrastructure networking (sceNetInet -> host)    |
|                                                          |
|  Mounts:                                                 |
|    /eboot  <- packages/oasis_os/target/mipsel-sony-psp/  |
|    /states <- ppsspp/states/ (save states, snapshots)    |
+----------------------------------------------------------+
        |  MCP (TCP :8808)        |  PSP net (TCP :9000)
        v                         v
  AI agents (Claude,        telnet / OASIS_OS
  automation-cli, etc.)     remote terminal
```

#### 13.2.2 MCP Tool Surface

The patches add an MCP server to PPSSPP that exposes the emulator's internal state as tools. The tool schemas live in `packages/oasis_os/ppsspp/mcp-schema/` and follow the same conventions as the project's other MCP servers.

| Tool | Description | Agent Use Case |
|------|-------------|---------------|
| `psp.memory.read` | Read bytes at a PSP address (user or kernel space) | Inspect SDI object registry in memory, verify scene graph state |
| `psp.memory.write` | Write bytes at a PSP address | Hot-patch values during debugging, inject test data |
| `psp.memory.search` | Scan memory for byte pattern or string | Find leaked allocations, locate specific SDI objects by name string |
| `psp.memory.heap_info` | Return heap allocation map (block list, free list, fragmentation) | Diagnose memory budget issues on 32MB PSP |
| `psp.gpu.state` | Current GU state: display list position, matrix stack, texture bindings, blend mode | Debug rendering issues -- agent can compare expected vs actual GU state |
| `psp.gpu.vram_dump` | Dump VRAM contents as PNG | Visual regression testing -- agent compares VRAM snapshot against reference |
| `psp.gpu.texture_list` | List all loaded textures with dimensions, format, VRAM address | Track VRAM budget, find texture leaks |
| `psp.gpu.draw_call_trace` | Log the next N draw calls with parameters | Profile rendering pipeline, identify redundant draws |
| `psp.debug.breakpoint` | Set/clear/list breakpoints at MIPS addresses or symbol names | Agent-driven debugging -- set breakpoint on `sdi_draw`, inspect state when hit |
| `psp.debug.step` | Single-step or continue execution | Step through problematic code paths |
| `psp.debug.registers` | Read MIPS register file (GPR, FPR, HI/LO, PC, CP0) | Low-level debugging of crashes or hangs |
| `psp.debug.threads` | List PSP threads with state, priority, stack pointer, wait reason | Diagnose deadlocks or scheduling issues in the 5-6 thread OASIS_OS runtime |
| `psp.debug.stack_trace` | Walk stack frames for a given thread | Identify crash location, trace call chain |
| `psp.debug.symbols` | Query symbol table (from ELF before PBP packing) | Resolve addresses to function names for readable debugging |
| `psp.net.sockets` | List open sceNetInet sockets with state, addresses, buffer contents | Debug remote terminal connection issues |
| `psp.net.capture` | Capture next N packets on a socket | Inspect the OASIS_OS terminal protocol wire format |
| `psp.net.inject_latency` | Add artificial latency to socket operations | Test remote terminal behavior under poor WiFi conditions |
| `psp.emu.screenshot` | Capture current frame as PNG | Visual verification in CI, skin rendering checks |
| `psp.emu.save_state` | Save emulator state to file | Reproducible debugging -- save state at crash, reload to investigate |
| `psp.emu.load_state` | Restore emulator state from file | Reproduce exact conditions from a bug report |
| `psp.emu.frame_advance` | Advance exactly N frames | Frame-precise testing of animations and transitions |
| `psp.emu.set_speed` | Set emulation speed (0.1x to unlimited) | Fast-forward through boot sequence in CI; slow down for debugging |

#### 13.2.3 Docker Compose Service

```yaml
# In project root docker-compose.yml
ppsspp-mcp:
  build:
    context: packages/oasis_os/ppsspp
    dockerfile: Dockerfile
  ports:
    - "8808:8808"   # MCP server (TCP transport)
    - "9000:9000"   # OASIS_OS remote terminal (forwarded from emulated PSP)
  volumes:
    - ./packages/oasis_os/target/mipsel-sony-psp/release:/eboot:ro
    - ./packages/oasis_os/ppsspp/states:/states
  environment:
    - PPSSPP_HEADLESS=1           # No display required (CI mode)
    - PPSSPP_MCP_TRANSPORT=tcp    # tcp or stdio
    - PPSSPP_MCP_PORT=8808
    - PPSSPP_NET_INFRA=1          # Enable infrastructure networking
    - PPSSPP_EBOOT=/eboot/EBOOT.PBP
```

#### 13.2.4 Dockerfile Build Strategy

The Dockerfile clones PPSSPP from source at a pinned commit, applies the patch series in order, and builds. PPSSPP is GPL-2.0+, so the patches (which are derivative works distributed as part of the container build, not as a modified PPSSPP binary in the repository) comply with the license -- the patches themselves and the Dockerfile are the source.

```dockerfile
FROM ubuntu:24.04 AS builder
# Install PPSSPP build deps (CMake, SDL2-dev, etc.)
RUN apt-get update && apt-get install -y ...

# Clone at pinned commit for reproducibility
ARG PPSSPP_COMMIT=<pinned-hash>
RUN git clone --recursive https://github.com/hrydgard/ppsspp.git /ppsspp \
    && cd /ppsspp && git checkout $PPSSPP_COMMIT

# Apply MCP patches
COPY patches/ /patches/
RUN cd /ppsspp && for p in /patches/*.patch; do git apply "$p"; done

# Build (headless + SDL for optional display forwarding)
RUN cd /ppsspp && cmake -B build -DHEADLESS=ON -DUSING_X11_VULKAN=OFF ... \
    && cmake --build build -j$(nproc)

FROM ubuntu:24.04
COPY --from=builder /ppsspp/build/PPSSPPSDL /usr/local/bin/ppsspp
COPY --from=builder /ppsspp/build/assets /usr/local/share/ppsspp/assets
ENTRYPOINT ["ppsspp"]
```

#### 13.2.5 Patch Architecture

The patches are minimal, focused modifications to PPSSPP's C++ source. Each patch is self-contained and applies cleanly to the pinned commit.

| Patch | Files Modified | Approach |
|-------|---------------|----------|
| `0001-mcp-server.patch` | New `Core/MCP/` directory, hooks into `Core/System.cpp` startup | Adds a lightweight MCP server (JSON-RPC over TCP or STDIO). The server runs on a dedicated thread, accepts tool calls, and dispatches to handler functions. Uses PPSSPP's existing `Core/Debugger/` infrastructure for memory/CPU access. |
| `0002-memory-tools.patch` | `Core/MCP/MemoryTools.cpp` | Wraps `Memory::Read_U8/U16/U32`, `Memory::Write_*`, and `Memory::GetPointer` as MCP tools. Heap info reads the PSP kernel's internal allocation structures. |
| `0003-gpu-tools.patch` | `Core/MCP/GPUTools.cpp`, minor hooks in `GPU/GPUCommonHW.cpp` | Reads GU state from the GPU emulation layer. VRAM dump uses `GPU::GetFramebuffer()`. Draw call trace hooks into the display list interpreter. |
| `0004-debug-tools.patch` | `Core/MCP/DebugTools.cpp`, hooks in `Core/MIPS/MIPSDebugInterface.cpp` | Wraps PPSSPP's existing breakpoint, stepping, and register read APIs. Symbol lookup uses the ELF symbol table loaded at boot. Thread list reads from the emulated kernel's thread manager. |
| `0005-network-tools.patch` | `Core/MCP/NetTools.cpp`, hooks in `Core/HLE/sceNetInet.cpp` | Intercepts socket operations at the HLE layer. Packet capture records data flowing through `sceNetInetSend`/`Recv`. Latency injection adds `usleep()` before forwarding to host sockets. |
| `0006-headless-mode.patch` | `headless/Headless.cpp` | Extends PPSSPP's existing headless mode to support the MCP server and long-running execution (original headless mode is designed for screenshot comparison tests that exit immediately). |

#### 13.2.6 Agent Debugging Workflow

With the MCP-patched PPSSPP container running, AI agents can debug OASIS_OS on the PSP target the same way they debug desktop code -- but with hardware-accurate emulation:

```bash
# 1. Build OASIS_OS for PSP
docker compose run --rm -w /app/packages/oasis_os rust-ci \
    cargo build --features psp --release

# 2. Launch PPSSPP container (headless, MCP on :8808)
docker compose up -d ppsspp-mcp

# 3. Agent connects via MCP and inspects running state
# (via mcp-code-quality or direct TCP to 8808)
```

**Example: Agent diagnosing a rendering bug**

```
Agent -> psp.emu.screenshot
  <- PNG showing garbled dashboard icons

Agent -> psp.gpu.texture_list
  <- 12 textures loaded, texture #7 "icon_browser" has wrong dimensions (128x128, expected 64x64)

Agent -> psp.memory.search { pattern: "icon_browser" }
  <- Found at 0x08A03400 (SDI registry entry)

Agent -> psp.memory.read { address: 0x08A03400, length: 64 }
  <- SDI object struct: width=128, height=128, tex_ptr=0x04110000

Agent -> psp.gpu.state
  <- Current scissor rect: (0,0,480,272), blend mode: SRC_ALPHA

# Agent now has enough information to identify the bug:
# icon_browser loaded at 2x resolution, SDI blit stretches it
# Fix: check texture loading code for dimension handling
```

**Example: Agent diagnosing a deadlock**

```
Agent -> psp.debug.threads
  <- Thread 0 "main": WAIT (sema 0x00000003)
     Thread 1 "render": WAIT (sema 0x00000002)
     Thread 2 "network": RUNNING
     Thread 3 "terminal": WAIT (sema 0x00000003)

Agent -> psp.debug.stack_trace { thread: 0 }
  <- #0 sceKernelWaitSema at 0x08801234
     #1 sdi_draw at 0x08805678
     #2 main_loop at 0x08800ABC

# Agent identifies: main and terminal both waiting on sema 3,
# render waiting on sema 2 -- classic lock ordering inversion
```

#### 13.2.7 PPSSPP Networking (Passthrough)

PPSSPP 1.19+ maps `sceNetInet` socket calls to real host sockets. With the container's port forwarding, the OASIS_OS remote terminal running inside the emulated PSP is accessible from the host:

1. Cross-compile OASIS_OS for MIPS, producing EBOOT.PBP
2. Container launches PPSSPP with infrastructure networking enabled
3. OASIS_OS starts TCP listener on port 9000 (forwarded to host)
4. From another terminal: `telnet localhost 9000`
5. Full interactive command session with the running instance

This also works for outbound connections -- the `remote` command from the containerized PPSSPP instance connects to real services on the Docker network or host network, enabling full testing of the PSP agent control flow without physical hardware.

### 13.3 UE5 Development Workflow

1. Build OASIS_OS as a cdylib (`cargo build --features ue5 --release`)
2. Copy `.dll`/`.so` to UE5 project's `Binaries/ThirdParty/` directory
3. UE5 Build.cs references the library; C++ actor component calls FFI functions
4. Place `AComputerTerminalActor` in level, assign skin and VFS root via editor properties
5. Press Play-in-Editor; interact with in-game terminal
6. Optional: `telnet localhost 9000` for direct terminal access while PIE is running

### 13.4 AI Agent Integration

The project benefits from the existing agent ecosystem documented in `docs/agents/README.md`:

| Agent | Task | Automation Level |
|-------|------|-----------------|
| Claude Code | Architecture design, complex refactoring, C-to-Rust translation of SDI patterns, PSP debugging via PPSSPP MCP tools | Primary -- deep codebase understanding |
| Codex / OpenCode / Crush | Repetitive code translation (C getter/setter -> Rust methods), test generation | High -- patterns are mechanical |
| Gemini CLI | Automated PR review of OASIS_OS changes | Automatic -- runs on every PR |
| automation-cli | CI orchestration: `automation-cli ci run oasis-full` | High -- deterministic pipeline |
| PPSSPP MCP container | Live PSP debugging: memory inspection, GPU state, breakpoints, screenshots, network capture | High -- agents interact via standard MCP tools |

The original C source (`psixpsp.7z` at repo root) serves as the reference for AI-assisted translation. Agents can diff the original C against the Rust port to verify behavioral equivalence. The PPSSPP MCP container (Section 13.2) enables agents to debug the PSP target with the same depth as desktop code -- inspecting memory, setting breakpoints, capturing screenshots, and diagnosing deadlocks through standard MCP tool calls rather than manual printf debugging.

---

## 14. Plugin System

OASIS_OS supports runtime-extensible functionality through a platform-appropriate plugin system. On PSP, plugins are PRX modules loaded via `sceKernelLoadModule`. On Linux, shared libraries (`.so`) loaded via `libloading`. In UE5, plugins can also be authored as UE5 Blueprint-callable FFI extensions.

### 14.1 Plugin Lifecycle

| Phase | Description | PSP | Linux | UE5 |
|-------|------------|-----|-------|-----|
| Discovery | Scan plugin directory | `ms0:/.../plugins/` for .prx | `/etc/oasis-os/plugins/` for .so | Game asset directory for plugin manifests |
| Load | Load binary, resolve symbols | `sceKernelLoadModule` | `libloading::Library::new` | `libloading` or static registration |
| Initialize | Call init with host API handle | `oasis_plugin_init()` | `oasis_plugin_init()` | `oasis_plugin_init()` |
| Register | Plugin registers commands, UI, handlers | Function pointer table | `Box<dyn Plugin>` | `Box<dyn Plugin>` |
| Update | Per-frame tick | Main loop call | Main loop call | Main loop call |
| Unload | Shutdown, free memory | `sceKernelUnloadModule` | Drop Library | Drop Library |

### 14.2 Host API Surface

Plugins interact with OASIS_OS through a stable, versioned API providing access to: SDI scene graph (create/modify UI elements), command registry (register new commands), VFS (read/write files), network sockets, configuration storage, and event bus (subscribe to OS events).

---

## 15. Security Considerations

| Threat | Mitigation |
|--------|-----------|
| Buffer overflow in network input parsing | Rust ownership model eliminates buffer overflows at compile time; no unsafe in terminal module |
| Unauthorized remote access | Pre-shared key authentication; configurable IP allowlist; bind to specific interfaces |
| Plugin loading malicious code | Plugins explicitly installed by user; no remote plugin installation; signed manifests optional |
| Memory corruption via unsafe blocks | Unsafe limited to platform FFI wrappers; all unsafe blocks documented with safety invariants |
| Denial of service via resource exhaustion | Connection limit on terminal listener; per-command timeout; bounded input buffer size |
| Man-in-the-middle on terminal connection | Optional TLS via embedded certificates (Linux only; PSP lacks TLS libraries) |
| UE5 FFI boundary safety | All pointers validated on Rust side; null checks on every FFI entry point; opaque handles prevent UE5 from accessing Rust internals |
| Game save tampering via VFS | Write permissions per-path in VFS config; integrity checks on game-critical files; read-only base layer in OverlayVFS |
| Briefcase physical compromise | Handled by `tamper_briefcase` package -- dual-sensor detection, LUKS2 encryption, cryptographic wipe. OASIS_OS does not implement physical security; it delegates to the tamper services. |
| PSP remote session interception | Pre-shared key per host; connection limited to local network (no internet-facing listener). Defense in depth: sensitive operations on the remote host require their own authentication. |

---

## 16. Build System and CI/CD

### 16.1 Build Targets

| Target Triple | Toolchain | Output | Deploy Target |
|--------------|-----------|--------|--------------|
| mipsel-sony-psp (custom) | rust-psp + psp-gcc | EBOOT.PBP | PPSSPP / Memory Stick |
| aarch64-unknown-linux-gnu | cross (Docker) or native Pi | ELF binary | Raspberry Pi 5 (briefcase) via SSH/SCP |
| x86_64-unknown-linux-gnu | Native Rust toolchain | ELF binary / .so | Desktop dev / UE5 Linux |
| x86_64-pc-windows-msvc | Native Rust toolchain | .dll / .lib | UE5 Windows |

### 16.2 CI Pipeline Integration

OASIS_OS integrates with the existing CI system via Docker-based execution (container-first philosophy):

```bash
# Docker-based execution (current approach)
docker compose run --rm -w /app/packages/oasis_os rust-ci cargo fmt --check --all
docker compose run --rm -w /app/packages/oasis_os rust-ci cargo clippy --workspace -- -D warnings
docker compose run --rm -w /app/packages/oasis_os rust-ci cargo test --workspace
docker compose run --rm -w /app/packages/oasis_os rust-ci cargo build --release --workspace
```

> **Status:** Dedicated `oasis-*` CI stages (e.g., `automation-cli ci run oasis-full`) are planned but not yet registered in `automation-cli` or `run-ci.sh`. Currently, CI checks for the oasis_os workspace are run manually via the Docker commands above. The PSP backend is built separately on the host with `cargo +nightly psp --release` (requires the nightly toolchain and `cargo-psp`).

**Planned CI stages** (to be added to `automation-cli`):

| Stage | Tool | Purpose |
|-------|------|---------|
| `oasis-fmt` | rustfmt | Formatting check |
| `oasis-clippy` | clippy | Lint (all features) |
| `oasis-test` | cargo test | Unit tests (desktop target, core + VFS + commands + skins) |
| `oasis-build` | cargo build | Release build verification |
| `oasis-deny` | cargo-deny | License and advisory audit |
| PSP build | cargo +nightly psp --release | Verify EBOOT.PBP builds |
| PSP integration (PPSSPP) [PLANNED] | docker compose up ppsspp-mcp + MCP test sequence | Boot EBOOT in container, verify screenshot |

### 16.3 Context Protection

Following repo convention, verbose CI output is redirected to prevent context window pollution:

```bash
automation-cli ci run oasis-full > /tmp/ci-output.log 2>&1 \
    && echo "CI passed" \
    || (echo "CI failed - check /tmp/ci-output.log"; exit 1)
```

---

## 17. Migration Strategy from Original C Codebase

The original C source (`psixpsp.7z` at repository root) contains ~15,000 lines of C. The port follows a phased approach. Each phase produces a working, testable binary. The framework refactoring (core/backend/skin separation) happens in Phase 1-2, with original codebase features migrating in Phase 3-4 as the Classic skin.

| Phase | Deliverable | Source | Status |
|-------|-----------|--------|--------|
| 1 -- Framework scaffold | SDI core + backend trait + blank screen on SDL2 + UE5 render target stub | `sdi/sdi.c`, `sdi/backends/psp/gu.c` (architecture only) | **Complete** |
| 2 -- SDI + VFS + Commands | Full scene graph, VFS trait + RealFS + MemoryVFS, command interpreter with basic commands | `sdi/sdi.c`, `sdi/png.c`, `font.c`, new VFS code | **Complete** |
| 3 -- Classic skin | Icon grid dashboard, PBP scanning, app discovery, cursor navigation | `dashboard.c`, `pbp.c`, `image.c`, skin config | **Complete** |
| 4 -- PSP subsystems | Input, power, time, USB, file browser, on-screen keyboard, GU backend | `input.c`, `power.c`, `time.c`, `usb.c`, `file.c`, `osk.c` | **Complete** |
| 5 -- Remote terminal | TCP listener + outbound client, authentication, full command suite, remote access on all platforms | `net.c` (partial), new code | **Complete** |
| 6 -- UE5 integration | FFI boundary, UE5 render target backend, interaction input, GameAssetVFS | All new code | **Complete** |
| 7 -- Window manager | WM core: window lifecycle, grouping, drag/resize/focus, hit testing, clipping, window types | All new code | **Complete** |
| 8 -- Skin system | Skin loading, hot-swap (Classic skin implemented; Terminal/Tactical/Corrupted/Desktop skins planned) | All new code + skin configs | **Partial** |
| 9 -- Agent terminal skin | Agent status dashboard, MCP tool integration, remote session manager, tamper status display | All new code | Planned |
| 10 -- Plugins | Plugin system, host API, 2-3 example plugins | All new code | **Complete** (framework; example plugins planned) |
| 11 -- Audio | MP3 playback with ME offloading (PSP) or rodio (Linux) | `audio.c`, `me.S`, `modules/audio/*` | **Complete** (framework) |
| 12 -- Polish | Transitions, update checker, scripting, FTP server | `transition.c`, `update.c` + new | **Complete** |
| 13 -- PSP GU backend | Hardware-accelerated sceGu rendering, PSIX-style UI matching desktop layout | New code | **Complete** |

Phase 13 was added after the original plan. The PSP backend was initially software-rendered, then switched to sceGu hardware acceleration with `Sprites` primitives for all 2D drawing. The PSP UI now renders the full PSIX-style layout: document icons with 6 layers, tabbed status/bottom bars, chrome bezels, procedural wave arc wallpaper, and paginated grid navigation.

Total estimated Rust codebase: approximately 24,000 lines, exceeding the original C codebase by ~9,000 lines due to the framework abstraction, window manager, VFS, UE5 integration, and multiple skins. The vendored ffmpeg (~176,000 lines) is eliminated entirely.

---

## 18. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| rust-psp SDK fork lacks needed PSP syscall bindings | Medium | Medium | Add bindings directly to the fork; fallback to raw unsafe FFI via C headers |
| Kernel mode support in SDK fork not yet implemented | High | Medium | Design for user mode first; kernel-mode features (ME, raw hardware) accessed via pre-compiled PRX loaded at runtime; extend SDK fork incrementally |
| PPSSPP infrastructure networking breaks on edge cases | Medium | Medium | Test on latest PPSSPP builds; report issues upstream; fallback to real hardware |
| PPSSPP MCP patches break on upstream update | Medium | Low | Pin to specific PPSSPP commit in Dockerfile; re-apply and fix patches when bumping version; patches are small and isolated to new files |
| PPSSPP internal APIs change (debugger, memory, GPU) | Medium | Medium | Patches primarily hook into stable internal APIs (Memory::Read, MIPSDebugInterface); GPU tools are more fragile -- pin to known-good PPSSPP version |
| PPSSPP headless mode inaccurate vs real PSP | Low | Medium | Validate critical rendering against real hardware at phase milestones; use VRAM dumps from MCP for automated visual regression |
| UE5 texture update latency causes visible lag on in-game monitors | Medium | Medium | Double-buffer the RGBA surface; only update on dirty frames; profile UpdateTextureRegions cost |
| FFI boundary introduces undefined behavior | Low | High | Fuzz the FFI boundary; validate all pointers on Rust side; use miri for unsafe auditing |
| GU rendering differences between PPSSPP and real PSP | Low | Medium | Validate rendering on real hardware at each phase milestone |
| Memory budget exceeded on PSP (32MB) | Low | High | Profile in PPSSPP; use bounded collections; lazy-load textures |
| Skin hot-swap causes state corruption | Medium | Medium | Snapshot VFS and command state before swap; validate SDI tree consistency after rebuild |
| UE5 version upgrade breaks FFI linkage | Low | Medium | Pin to C ABI only; no C++ mangled symbols; version the FFI header |
| Scope creep beyond embeddable OS into general-purpose OS | Medium | Medium | Strict adherence to non-goals; resist adding package management or virtual memory |
| SDL2 dependency issues on Pi (wayland vs X11 vs kms) | Low | Low | Provide framebuffer backend as fallback; document tested Pi OS versions |
| Window manager hit testing incorrect under high object count | Medium | Medium | Spatial index (grid-based) for hit testing if linear scan exceeds frame budget; benchmark with 20+ open windows |
| WM drag/resize latency from updating many SDI objects per frame | Low | Medium | Batch position updates; defer non-visible object updates; profile with Desktop skin at max window count |
| Conflict between OASIS_OS and tamper services on Pi | Low | Low | Strict separation via systemd unit ordering; OASIS_OS reads tamper state files but never writes to them |

---

## 19. Success Criteria

| Criterion | Verification Method |
|----------|-------------------|
| OASIS_OS boots to a themed dashboard on real PSP hardware | Visual verification on PSP-2000 with custom firmware |
| OASIS_OS boots to the same dashboard on Raspberry Pi | Visual verification on Pi 5 with SDL2 or framebuffer backend |
| In-game computer in UE5 renders a functional OS with player interaction | Play-in-Editor: interact with terminal, execute commands, browse files |
| At least 4 distinct skins render correctly from the same core framework | Load Classic, Terminal, Tactical, and Agent Terminal skins; verify layout, features, and visuals differ |
| Dashboard discovers and launches homebrew (PSP) / executables (Pi) / game UI (UE5) | Launch 3+ apps from dashboard on each platform |
| Remote terminal accessible via TCP from another machine | Telnet/netcat session with successful command execution |
| PSP establishes outbound remote session to agent host | From OASIS_OS on PSP (or PPSSPP), `remote dev-server` connects and allows command execution |
| Agent terminal skin displays live agent status and tamper state on briefcase Pi | Boot Pi with agent-terminal skin, verify agent and tamper panels populate |
| VFS abstraction works across RealFS, GameAssetVFS, and MemoryVFS | Automated test: same command sequence produces correct results on all VFS backends |
| Command interpreter correctly gates features per skin | Terminal skin exposes all commands; Tactical skin restricts to approved set; verify gating |
| UE5 callback system fires on file access and command execution | Automated test: access file -> verify ON_FILE_ACCESS callback fires in UE5 |
| Full development cycle runs in PPSSPP container without real hardware | End-to-end: build EBOOT, launch container, terminal connect, command test, MCP memory read -- all in Docker |
| PPSSPP MCP tools accessible by AI agents | Agent connects to container MCP port, reads PSP memory, takes screenshot, lists threads -- verified in CI |
| FFI boundary passes fuzz testing with no undefined behavior | Run cargo-fuzz on all FFI entry points; miri audit on unsafe blocks |
| Boot-to-dashboard time under 5 seconds on Raspberry Pi | Timed measurement from power-on to rendered dashboard |
| Zero unsafe blocks outside of platform FFI wrappers | `cargo geiger` audit of core and backend crates |
| Window manager supports drag, resize, focus, minimize, maximize, and close on Desktop skin | Manual test: open 5+ windows, perform all operations, verify correct z-ordering and clipping |
| Content clipping prevents rendering outside window boundaries on all backends | Automated test: render overflowing content in a window, verify no pixel bleed outside clip rect |
| Corrupted skin modifiers produce visible distortion without crashing WM | Load Corrupted skin, open windows, verify drag jitter, glitched frames, and visual artifacts render without panics |
| CI pipeline runs via `automation-cli ci run oasis-full` | All stages pass: fmt, clippy, test, build, deny |

---

## 20. References and Resources

| Resource | URL / Location |
|----------|---------------|
| Original C source (v1.90) | `psixpsp.7z` (repository root) |
| rust-psp upstream | github.com/overdrivenpotato/rust-psp |
| rust-psp SDK fork | github.com/AndrewAltimit/rust-psp |
| PPSSPP emulator (GPL-2.0+) | github.com/hrydgard/ppsspp |
| PPSSPP infrastructure networking PR | github.com/hrydgard/ppsspp/pull/19827 |
| PPSSPP MCP patches [PLANNED] | `packages/oasis_os/ppsspp/patches/` (not yet created) |
| MCP specification | modelcontextprotocol.io |
| PSP SDK documentation | psp-archive.github.io/pspsdk-docs/ |
| PSP homebrew wiki | pspdev.github.io/ |
| Unreal Engine 5 C++ API | docs.unrealengine.com |
| UE5 UTexture2D / UpdateTextureRegions | docs.unrealengine.com/API/Runtime/Engine/Engine/UTexture2D/ |
| Rust FFI guide | doc.rust-lang.org/nomicon/ffi.html |
| libloading crate | crates.io/crates/libloading |
| Raspberry Pi OS Lite | raspberrypi.com/software/operating-systems/ |
| SDL2 Rust bindings | github.com/Rust-SDL2/rust-sdl2 |
| ARK-4 custom firmware | github.com/PSP-Archive/ARK-4 |
| Infinity 2 persistent CFW | infinity.lolhax.org |
| cargo-fuzz | github.com/rust-fuzz/cargo-fuzz |
| This design document | `packages/oasis_os/docs/design.md` |
| Tamper briefcase design | `docs/hardware/secure-terminal-briefcase.md` |
| Tamper briefcase implementation | `packages/tamper_briefcase/` |
| Agent ecosystem documentation | `docs/agents/README.md` |
| Board-centric workflow | `docs/agents/board-workflow.md` |
| automation-cli (CI/CD) | `tools/rust/automation-cli/` |
| MCP server architecture | `docs/mcp/README.md` |

---

*End of Document*
