# Injection Toolkit Architecture

## Design Philosophy

The Injection Toolkit follows a **minimal injection, maximal external processing** philosophy:

1. **Inject only what's necessary** - Code running inside the target application should be minimal
2. **Process externally** - Heavy lifting happens in the daemon and overlay
3. **Communicate via IPC** - Clean separation between components
4. **Fail gracefully** - Components should handle failures without crashing the target

## Component Responsibilities

### Injector (DLL/SO)

**What it does:**
- Connects to daemon via IPC
- Hooks strategic functions in the target
- Extracts minimal state data
- Sends state updates to daemon

**What it doesn't do:**
- Complex processing
- Rendering
- Network communication (beyond local IPC)
- Blocking operations

### Daemon

**What it does:**
- Receives state from injector
- Aggregates and caches state
- Serves queries from clients (overlay, MCP)
- Optionally handles multiplayer sync

**What it doesn't do:**
- Inject code
- Render anything
- Interact directly with target application

### Overlay

**What it does:**
- Renders content on top of target application
- Handles click-through mode
- Provides interactive UI when enabled
- Reads frame data from shared memory (for video)

**What it doesn't do:**
- Inject code
- Process video/audio
- Heavy computation

### Shared Memory

**What it does:**
- Transfer large data (video frames) between daemon and overlay
- Lock-free triple-buffered design
- Seqlock for consistency

**What it doesn't do:**
- Small message passing (use IPC)
- Cross-machine communication

## Data Flow

### State Extraction Flow

```
Target App Function
        │
        ▼
   [Hook triggers]
        │
        ▼
Injector extracts state
        │
        ▼
   [IPC message]
        │
        ▼
Daemon receives & caches
        │
        ▼
   [IPC query]
        │
        ▼
Client receives state
```

### Frame Data Flow (Video/Images)

```
Video Source (daemon)
        │
        ▼
   [Decode frame]
        │
        ▼
Write to shared memory
   (seqlock protected)
        │
        ▼
Overlay reads frame
        │
        ▼
   [GPU texture upload]
        │
        ▼
Render to screen
```

## Protocol Design

### Wire Format

All messages use a common header:

```
┌─────────┬─────────┬──────────┬─────────────┬─────────┬───────────┐
│ Magic   │ Version │ MsgType  │ PayloadLen  │ CRC32   │ Payload   │
│ 4 bytes │ 4 bytes │ 4 bytes  │ 4 bytes     │ 4 bytes │ N bytes   │
└─────────┴─────────┴──────────┴─────────────┴─────────┴───────────┘
```

- **Magic**: `"ITKP"` - identifies ITK protocol
- **Version**: Protocol version for compatibility
- **MsgType**: Enum identifying message type
- **PayloadLen**: Size of payload (max 1MB)
- **CRC32**: Checksum for validation
- **Payload**: bincode-serialized data

### Message Types

| Type | Direction | Purpose |
|------|-----------|---------|
| Ping/Pong | Any | Keepalive, latency measurement |
| ScreenRect | Injector → Daemon | Overlay positioning |
| WindowState | Injector → Daemon | Target window properties |
| StateSnapshot | Injector → Daemon | Full state dump |
| StateEvent | Injector → Daemon | Incremental state change |
| StateQuery | Client → Daemon | Request state |
| StateResponse | Daemon → Client | State data |

## Platform Abstraction

### IPC

| Platform | Implementation |
|----------|----------------|
| Windows | Named Pipes (`\\.\pipe\itk_*`) |
| Linux | Unix Domain Sockets (`/tmp/itk_*.sock`) |

### Shared Memory

| Platform | Implementation |
|----------|----------------|
| Windows | `CreateFileMappingW` + `MapViewOfFile` |
| Linux | `shm_open` + `mmap` |

### Overlay

| Platform | Click-Through | Always-on-Top |
|----------|---------------|---------------|
| Windows | `WS_EX_TRANSPARENT` | `HWND_TOPMOST` |
| Linux/X11 | SHAPE extension | `_NET_WM_STATE_ABOVE` |
| Linux/Wayland | Layer-shell* | Layer-shell* |

*Requires compositor support and additional dependencies.

## Synchronization

### Seqlock Algorithm

Used for lock-free shared memory access:

```rust
// Writer
seq.fetch_add(1, Release);  // Odd = writing, ensures visibility
// ... write data (Relaxed is fine here) ...
seq.fetch_add(1, Release);  // Even = done, makes writes visible

// Reader
loop {
    let s1 = seq.load(Acquire);  // Acquire synchronizes with writer's Release
    if s1 & 1 != 0 { continue; }  // Write in progress
    // ... read data (Relaxed, protected by seqlock) ...
    let s2 = seq.load(Acquire);
    if s1 == s2 { break; }  // Consistent read
}
```

### Memory Ordering Strategy

We use Acquire/Release ordering for seqlock operations:

- **Writer**: `fetch_add(1, Release)` ensures all prior data writes are visible
  before the sequence number update
- **Reader**: `load(Acquire)` synchronizes with writer's Release, ensuring data
  reads see the correct values
- **Data reads/writes**: Can use `Relaxed` ordering since the seqlock sequence
  number provides the necessary synchronization

This approach:
- **ARM compatible**: Works correctly on weakly-ordered architectures
- **Performant**: Avoids unnecessary full memory barriers
- **Correct**: Follows the standard seqlock pattern from academic literature

## Error Handling

### Graceful Degradation

| Failure | Detection | Behavior |
|---------|-----------|----------|
| Daemon unreachable | IPC error | Injector continues without state export |
| Injector disconnects | IPC timeout | Daemon serves stale state |
| Overlay crash | Process exit | Target unaffected |
| Target crash | Process exit | All components survive |

### Recovery

- IPC channels automatically reconnect with exponential backoff
- Shared memory handles are validated before each access
- Missing state returns explicit errors, not crashes

## Security

### Threat Model

The Injection Toolkit operates in a hostile environment where the injected code
runs inside an untrusted process. The daemon and overlay must treat ALL data
from the injector as **potentially malicious**.

| Component | Trust Level | Threat |
|-----------|-------------|--------|
| Injector | **UNTRUSTED** | Compromised target, malicious mods, memory corruption |
| Daemon | Trusted | Local process with validated inputs |
| Overlay | Trusted | Local process with validated inputs |
| Shared Memory | Untrusted data | Injector can write arbitrary bytes |

### Input Validation

The daemon validates all incoming data before use:

```rust
// String length limits
const MAX_STRING_LEN: usize = 256;
const MAX_DATA_SIZE: usize = 64 * 1024;  // 64 KB

// Numeric bounds checking
const MAX_SCREEN_DIM: f32 = 16384.0;

// Float validation (reject NaN/Inf)
if !value.is_finite() {
    bail!("Non-finite value rejected");
}

// Dimension validation
if width < 0.0 || height < 0.0 {
    bail!("Negative dimensions rejected");
}
```

### IPC Security

#### Windows Named Pipes

Named pipes should use appropriate security descriptors:

- Default: Local user access only (inherited from process token)
- Custom: Use `SECURITY_ATTRIBUTES` to restrict access further
- Never expose pipes to network without explicit intent

```rust
// Recommended: Restrict to current user
let mut sa = SECURITY_ATTRIBUTES::default();
// Set up DACL allowing only current user...
```

#### Linux Unix Sockets

Unix domain sockets use filesystem permissions:

- Socket created with `0600` permissions (owner only)
- Located in `/tmp` with sticky bit protection
- Consider `SO_PASSCRED` for peer authentication

```rust
// Socket path: /tmp/itk_{name}.sock
// Permissions: -rw------- (0600)
```

### Shared Memory Security

- Memory regions are created with restrictive permissions
- Size is fixed at creation to prevent overflow
- Triple-buffering prevents reader/writer corruption
- Seqlock provides consistency, not access control

### Defense in Depth

1. **Protocol validation**: Magic bytes, version, CRC32
2. **Size limits**: Payload bounded to 1MB max
3. **Type validation**: All fields checked before use
4. **Fail-safe**: Invalid data logged and rejected, never crashes
5. **Isolation**: Components run in separate processes

### What We Don't Protect Against

The toolkit does not protect against:

- Malicious overlay/daemon (these are trusted)
- Kernel-level attacks
- Physical access attacks
- Side-channel attacks

These are out of scope for a userspace injection framework.

## Performance Budgets

### Memory

| Component | Budget | Notes |
|-----------|--------|-------|
| Injector | < 5 MB | Minimal footprint |
| Daemon | < 30 MB | State caching |
| Overlay | < 20 MB | GPU resources |
| Shmem | ~10 MB | Triple-buffered 720p |

### Latency

| Operation | Target | Notes |
|-----------|--------|-------|
| State update (IPC) | < 1 ms | Local only |
| Frame copy (shmem) | < 1 ms | ~3.5 MB @ 720p |
| Overlay render | < 5 ms | Simple quad |

## Extending the Toolkit

### Adding a New Injector Platform

1. Create new crate in `injectors/`
2. Implement IPC client connection
3. Implement platform-specific initialization
4. Export state using `itk-protocol` messages

### Adding a New Message Type

1. Add variant to `MessageType` enum in `itk-protocol`
2. Define payload struct with serde derives
3. Update daemon message handlers
4. Update clients as needed

### Adding a New Platform

1. Add platform module in `itk-shmem` and `itk-ipc`
2. Implement platform traits
3. Update `cfg_if!` blocks
4. Add platform module in overlay if needed
