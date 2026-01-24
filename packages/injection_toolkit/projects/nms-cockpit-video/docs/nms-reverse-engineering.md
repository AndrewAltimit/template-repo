# NMS Reverse Engineering Findings

## Session Info
- **NMS.exe PID**: 70572
- **NMS.exe Base**: 0x7FF6DF260000
- **NMS.exe Size**: ~112 MB
- **Game Version**: Current as of 2026-01-23
- **Player State**: Stationary in ship cockpit

## Key Structures

### cGcCameraManager

**RTTI Chain:**
- Type Descriptor: `NMS.exe+0x4B87380` (string: `.?AVcGcCameraManager@@`)
- Complete Object Locator: `NMS.exe+0x4628A70`
- Vtable: `NMS.exe+0x4528588` (RVA)
- Inherits from: `cTkCameraManager`

**Singleton Access:**
- Global pointer at: `NMS.exe+0x56666B0`
- Points to heap-allocated instance (current session: 0x2106B20CE80)
- Object size: 0x3340 bytes (from vtable function analysis)

**Pointer Chain (validated):**
```
NMS.exe+0x56666B0  →  [deref]  →  cGcCameraManager*
    +0x130  →  View Matrix (4x4 float, row-major)
    +0x1D0  →  FoV (float, degrees)
    +0x40   →  World Position (vec4)
```

### cTkCamera (Embedded Camera Object)

The camera manager embeds `cTkCamera` instances (engine-level camera class).

**RTTI:** `.?AVcTkCamera@@`
**Vtable:** `NMS.exe+0x45286C0` (RVA)

**cTkCamera Layout (size: 0xC0 bytes):**
| Offset | Type | Description | Example |
|--------|------|-------------|---------|
| +0x00 | ptr | Vtable (cTkCamera) | |
| +0x08 | - | Padding (zeros) | |
| +0x10 | mat4x4 | View/World Matrix | see below |
| +0x50 | vec4 | World Position | |
| +0x60 | mat4x4 | View Matrix (copy) | |
| +0xA0 | vec4 | World Position (copy) | |
| +0xB0 | float | FoV (degrees) | 75.0 |
| +0xB4 | float | Aspect/multiplier | 1.5 or 1.0 |
| +0xB8 | u32 | Active flag | 1 |

**Embedded cTkCamera instances in Camera Manager:**
- Camera Manager + 0x120 = First cTkCamera (ACTIVE, FoV=75, aspect=1.5)
- Camera Manager + 0x1E0 = Second cTkCamera (FoV=75, aspect=1.0)
- Camera Manager + 0x2A0 = Third cTkCamera (interpolated state?)

### Camera Manager Object Layout

| Offset | Type | Description | Example Value |
|--------|------|-------------|---------------|
| +0x00 | ptr | Vtable pointer | cGcCameraManager vtable |
| +0x08 | - | Base class padding (zeros) | 0 |
| +0x40 | vec4 | World position (x, y, z, sector=1024) | (-899072, -48128, -2243584, 1024) |
| +0x50 | ptr[25] | Camera behaviour pointers | 25 camera modes |
| +0x118 | u32 | **Camera mode enum** (NOT index!) | 0x10=cockpit, 0x40=on-foot |
| +0x11C | u32 | Camera behaviour count | 25 |
| +0x120 | cTkCamera | First embedded camera (ACTIVE) | |
| +0x130 | mat4x4 | **View/World Matrix** (= cTkCamera+0x10) | Current frame |
| +0x170 | vec4 | World position (= cTkCamera+0x50) | |
| +0x180 | mat4x4 | View Matrix copy (= cTkCamera+0x60) | |
| +0x1C0 | vec4 | World position copy (= cTkCamera+0xA0) | |
| +0x1D0 | float | **FoV degrees** (= cTkCamera+0xB0) | 75.0 |
| +0x1D4 | float | Aspect/multiplier (= cTkCamera+0xB4) | 1.5 |
| +0x1E0 | cTkCamera | Second embedded camera | |
| +0x2A0 | cTkCamera | Third embedded camera | |

### View Matrix Format (at +0x130)

Row-major 4x4 float matrix (world-to-local transform):
```
Row 0: (right.x,   right.y,   right.z,   0.0)    - Right vector
Row 1: (up.x,      up.y,      up.z,      0.0)    - Up vector
Row 2: (forward.x, forward.y, forward.z, 0.0)    - Forward vector
Row 3: (pos.x,     pos.y,     pos.z,     1.0)    - Local camera position
```

**Current values (cockpit, stationary):**
```
Right:    (-0.2428,  0.4305,  0.8693, 0.0)
Up:       ( 0.2465,  0.8941, -0.3740, 0.0)
Forward:  (-0.9383,  0.1235, -0.3232, 0.0)
Position: (1425.42, -252.66,  803.52, 1.0)  ← LOCAL coords
```

The position in row 3 is LOCAL coordinates (relative to sector/chunk origin).
The WORLD position at +0x40 gives absolute coordinates.

### Camera Behaviour Sub-Objects (ptr[0..24] at +0x50)

25 camera behaviour objects, indexed from 0. Active mode stored at +0x118.

**When in cockpit: Mode = 0x10 (16)**

| Index | Class | Notes |
|-------|-------|-------|
| 0 | `cGcCameraBehaviourFly` | Flight camera |
| 1 | `cTkCameraBehaviourInterpolate` | Camera transitions (engine-level) |
| 2 | `cGcCameraBehaviourOffset` | Offset camera |
| 3 | `cGcCameraBehaviourCharacter` | Character view |
| 4 | `cGcCameraBehaviourFirstPerson` | First person (on foot) |
| 5 | `cGcCameraBehaviourThirdPerson` | Generic 3rd person |
| 6 | `cGcCameraBehaviourPlayerThirdPerson` | Player 3rd person |
| 7 | `cGcCameraBehaviourGalacticTransition` | Galaxy map transition |
| 8 | `cGcCameraBehaviourGalacticNavigation` | Galaxy map navigation |
| 9 | `cGcCameraBehaviourGalacticLookAt` | Galaxy map look-at |
| 10 | `cGcCameraBehaviourInteraction` | NPC interaction |
| 11 | `cGcCameraBehaviourLookAt` | Generic look-at |
| 12 | `cGcCameraBehaviourAerialView` | Aerial/overhead view |
| 13 | `cGcCameraBehaviourScreenshot` | Screenshot mode |
| 14 | `cGcCameraBehaviourPhotoMode` | Photo mode |
| 15 | `cGcCameraBehaviourAmbient` | Ambient/idle camera |
| 16 | `cGcCameraBehaviourModelView` | **COCKPIT CAMERA** |
| 17 | `cGcCameraBehaviourAnimation` | Cutscene/animation |
| 18 | `cGcCameraBehaviourFollowTarget` | Follow target |
| 19 | `cGcCameraBehaviourShipWarp` | Ship warp effect |
| 20 | `cGcCameraBehaviourCockpitTransition` | Enter/exit cockpit |
| 21 | `cGcCameraBehaviourBuildingMode` | Building placement |
| 22 | `cGcCameraBehaviourFocusBuildingMode` | Building focus |
| 23 | `cGcCameraBehaviourOrbitBuildingMode` | Building orbit |
| 24 | `cGcCameraBehaviourFreighterWarp` | Freighter warp effect |

**Key modes for mod:**
- Index 16 (ModelView) = cockpit camera, used when mode == 0x10
- Index 19 (ShipWarp) = embedded at ModelView+0x90, used during warp
- Index 20 (CockpitTransition) = transition in/out of cockpit

### cGcCameraBehaviourModelView (Cockpit Camera, ptr[16])

**Vtable:** 0x7FF6E37EAD58 (`.?AVcGcCameraBehaviourModelView@@`)

**Layout:**
| Offset | Type | Description | Value |
|--------|------|-------------|-------|
| +0x00 | ptr | Vtable | |
| +0x28 | float | Unknown | 2.0 |
| +0x2C | float | Unknown | 3.0 |
| +0x30 | float | Unknown | 1.0 |
| +0x34 | float | Unknown | 2.0 |
| +0x36 | u8[2] | Flags | (1, 1) |
| +0x38 | u32[2] | Masks? | (0x7FFFF, 0x7FFFF) |
| +0x60 | float | Scale? | 1.0 |
| +0x68 | float | Scale? | 1.0 |
| +0x90 | ptr | Embedded vtable (ShipWarp) | |

**Camera Configuration Parameters (at +0x120):**
| Offset | Value | Possible Meaning |
|--------|-------|------------------|
| +0x120 | -4.0 | Min distance offset? |
| +0x124 | 0.5 | Interpolation speed? |
| +0x128 | 3.0 | Default distance? |
| +0x12C | 20.0 | Max distance? |
| +0x130 | 5.0 | Look distance? |
| +0x138 | 1.5 | Aspect/scale? |
| +0x140 | 0.5 | Sensitivity? |
| +0x148 | 0.1 | Min speed? |
| +0x14C | 1.5 | Speed multiplier? |
| +0x168 | 30.0 | Max angle? |
| +0x170 | 5.0 | Transition speed? |
| +0x1C0 | 50.0 | Far distance? |
| +0x1C8 | 15.0 | Medium distance? |
| +0x1F0 | 30.0 | Look range? |
| +0x1F4 | -15.0 | Vertical offset? |

### cGcApplication

**RTTI:** `.?AVcGcApplication@@`
- Type Descriptor: `NMS.exe+0x4C08EC8`
- COL: `NMS.exe+0x0468BA30`
- Vtable: `NMS.exe+0x0518C858`
- **Static global object** at: `NMS.exe+0x068F7460` (NOT heap-allocated!)
- Does NOT directly contain camera manager pointer

### Global Pointer Context

The camera manager global pointer is part of a global manager registry:
```
NMS.exe+0x56666A4: count = 4
NMS.exe+0x56666A8: ptr to unknown manager A
NMS.exe+0x56666B0: ptr to cGcCameraManager  ← TARGET
NMS.exe+0x56666B8: ptr to unknown manager C
NMS.exe+0x56666C0: [360 (0x168)]
```

Float data near the registry (at NMS.exe+0x5666690):
- 0.1169, 0.5649, 1.0, 0.9 (possibly rendering parameters)

## Cross-Mode Comparison (VERIFIED LIVE)

The cTkCamera at +0x120 ALWAYS reflects the active rendering camera:

| Field | Cockpit (mode=0x10) | On-Foot (mode=0x40) | Notes |
|-------|---------------------|---------------------|-------|
| FoV (+0x1D0) | 75.0 | 70.0 | Mode-specific |
| Aspect (+0x1D4) | 1.5 | 1.0 | Cockpit uses wider FoV multiplier |
| View Matrix (+0x130) | Changes with look | Changes with look | ALWAYS live |
| Position w | 1.0 | ~0.989 | Ignore w, use xyz only |
| World Pos (+0x40) | Sector coords | Same sector | Only changes on sector boundary |
| Mode (+0x118) | 0x10 (16) | 0x40 (64) | Powers of 2 = bitmask/enum |

**Key Insight**: For the mod, only check mode == 0x10 (cockpit) before rendering video overlay.
The view matrix and FoV at +0x130/+0x1D0 always give current frame data regardless of mode.

## Cockpit-Related Strings

**SpaceMap cockpit parameters (for hologram positioning):**
- `SpaceMapCockpitOffset`
- `SpaceMapCockpitScale`
- `SpaceMapCockpitScaleAdjustDropShip`
- `SpaceMapCockpitScaleAdjustFighter`
- `SpaceMapCockpitScaleAdjustScientific`
- `SpaceMapCockpitScaleAdjustShuttle`
- `SpaceMapCockpitScaleAdjustRoyal`

**Camera strings:**
- `CameraLook`, `CameraLookX`, `CameraLookY`
- `CameraRollLeft`, `CameraRollRight`
- `CameraHeight`, `CameraDistanceFade`, `CameraRelative`

## Module Info

Notable loaded modules:
- Vulkan renderer (vulkan-1.dll)
- D3D12 (d3d12.dll, dxgi.dll)
- DLSS (nvngx_dlss.dll)
- OpenVR (openvr_api.dll)
- Steam (steam_api64.dll)
- PlayFab networking

## Pattern Scanning Strategy for Mod

### Approach 1: RTTI-Based (Most Robust, Cross-Version)
```
1. Pattern scan NMS.exe for bytes: ".?AVcGcCameraManager@@"
2. Type Descriptor = match_addr - 0x10  (vtable+internal ptrs precede name)
3. type_desc_rva = type_desc_addr - nms_base
4. Scan .rdata for 4-byte value matching type_desc_rva (finds COL)
5. Verify COL: signature==1, pSelf matches
6. Vtable = COL_addr + sizeof(COL) = COL + 24  (COL ptr lives at vtable[-8])
7. Scan ALL process memory for 8-byte vtable address → singleton instance
```

### Approach 2: Global Pointer (Fastest, Version-Specific)
```
1. Read pointer at NMS.exe + 0x56666B0
2. WARNING: This RVA changes with each game update!
```

### Approach 3: Code Signature (TODO - Medium Robustness)
- Find unique instruction sequence that accesses the global pointer
- Use wildcard bytes for the RIP-relative displacement
- More robust than Approach 2, less overhead than Approach 1

## Key Offsets for Mod Implementation

```csharp
// C# offsets for Reloaded-II mod (cGcCameraManager)
const int OFFSET_WORLD_POS = 0x40;        // vec4 (x, y, z, sector_size=1024)
const int OFFSET_CAM_BEHAVIOURS = 0x50;   // ptr[25] camera behaviour objects
const int OFFSET_ACTIVE_CAM_IDX = 0x118;  // u32, current=16 for cockpit
const int OFFSET_CAM_COUNT = 0x11C;       // u32, always 25
const int OFFSET_ACTIVE_CAMERA = 0x120;   // cTkCamera embedded object
const int OFFSET_VIEW_MATRIX = 0x130;     // mat4x4 row-major (= cTkCamera+0x10)
const int OFFSET_VIEW_MATRIX_PREV = 0x180;// mat4x4 (previous/copy)
const int OFFSET_FOV = 0x1D0;             // float, degrees (currently 75.0)
const int OFFSET_ASPECT = 0x1D4;          // float (currently 1.5)
```

## Mod Implementation Notes

### Video Screen Placement
To place a video screen in the cockpit:
1. Read view matrix at +0x130
2. Extract forward vector (row 2) and up vector (row 1)
3. Position screen at: camera_pos + forward * SCREEN_DISTANCE + up * SCREEN_HEIGHT_OFFSET
4. Orient screen to face camera (billboard or fixed orientation)
5. Scale based on desired apparent size / FoV

### Projection Matrix
Not stored in camera manager. Near/far clip planes are NOT stored as named struct fields
(searched for "NearPlane"/"FarPlane" - only DOF and interaction-related matches found).
Near/far are likely hardcoded in the renderer or computed per-frame.

For the overlay mod, projection is computed independently:
```
fov_rad = FoV * PI / 180      // Read from +0x1D0
aspect = screen_width / screen_height  // Query from swapchain
near = 0.1                    // Reasonable default for overlay
far = 1000.0                  // Only need range for video screen quad

proj[0][0] = 1.0 / (aspect * tan(fov_rad / 2))
proj[1][1] = 1.0 / tan(fov_rad / 2)
proj[2][2] = far / (near - far)
proj[2][3] = -1.0
proj[3][2] = (near * far) / (near - far)
```

### Ship Type Enum (eShipClass)

String literals found at NMS.exe .rdata (contiguous at ~0x7FF6E22101A0):
```
"Ship"              // 0 - Base/generic
"Dropship"          // 1 - Sentinel Interceptor
"Fighter"           // 2
"Shuttle"           // 3
"PlayerFreighter"   // 4 - Capital ship
"Royal"             // 5 - Exotic
"Sail"              // 6 - Solar
```

Missing from this table: "Scientific" (Explorer) and "Hauler" - may use different names internally.

**SpaceMapCockpitScaleAdjust parameters exist per type:**
- `SpaceMapCockpitScaleAdjustFighter`
- `SpaceMapCockpitScaleAdjustScientific`
- `SpaceMapCockpitScaleAdjustShuttle`
- `SpaceMapCockpitScaleAdjustRoyal`
- `SpaceMapCockpitScaleAdjustSail`
- `SpaceMapCockpitScaleAdjustDropShip`

These confirm per-ship-type cockpit geometry differences. Finding the active ship type
at runtime would require tracing the player state → ship ownership reference chain,
which is complex. For basic mod functionality, dynamic FoV reading is sufficient.

### Rendering Hook
NMS uses **Vulkan** as primary renderer (vulkan-1.dll loaded).
Hook target: `vkQueuePresentKHR` or equivalent.
Alternative: DXGI hook if D3D12 mode is selected.

## Tools Built

### mem-scanner (Rust binary)
Location: `packages/injection_toolkit/tools/mem-scanner/`
```bash
mem-scanner.exe <pid> <pattern> [--min-addr <hex>] [--max-addr <hex>] [--max-results <n>]
```
- Scans ALL committed readable memory regions (heap + stack + mapped)
- Fast pattern matching with wildcard support (??)
- JSON output for MCP integration
- Scanned 2.87 GB in seconds to find the singleton

### Memory Explorer MCP Server (Python)
Location: `tools/mcp/mcp_memory_explorer/`
- STDIO MCP server for interactive memory exploration
- Uses pymem for process access
- Calls mem-scanner for heap scanning
- Tools: attach, read, dump, scan, watch, resolve pointers

## TODO

### Completed
- [x] Verify view matrix changes when camera moves (CONFIRMED: live every frame)
- [x] Identify all 25 camera behaviour types (DONE: full RTTI class map)
- [x] Find near/far clip plane values (NOT stored in camera; overlay computes its own)

### Remaining
- [ ] Find cockpit 3D model transform (for precise screen placement)
- [ ] Create stable code signature for cross-version pattern scanning
- [ ] Test offsets across game restarts (verify consistency)
- [ ] Hook Vulkan vkQueuePresentKHR for rendering overlay
- [ ] Find ship type at runtime (trace player state → ship → eShipClass enum)
- [ ] Map mode enum values to camera behaviour indices (0x10→16?, 0x40→?)
- [ ] Find render resolution / swapchain extent for overlay sizing
