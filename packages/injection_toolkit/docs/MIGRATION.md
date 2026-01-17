# Migration Plans

## FlatBuffers Migration (Planned)

The current `itk-protocol` crate uses bincode for payload serialization. This
works well for pure-Rust projects but limits cross-language interoperability.

### Why Migrate?

| Aspect | bincode (Current) | FlatBuffers (Proposed) |
|--------|-------------------|------------------------|
| Languages | Rust only | C, C++, C#, Go, Python, etc. |
| Schema evolution | Breaking changes | Backwards compatible |
| Zero-copy reads | No | Yes |
| Performance | Good | Excellent |
| Tooling | Simple | Requires flatc compiler |

### Use Cases Enabled by FlatBuffers

1. **C++ Injectors**: Direct injection without Rust compilation
2. **Python MCP Servers**: Read state without Rust bindings
3. **Unity/C# Overlays**: Native integration
4. **Version Compatibility**: Old injectors work with new daemons

### Migration Strategy

#### Phase 1: Schema Definition

Create FlatBuffers schema files alongside existing Rust code:

```flatbuffers
// itk-protocol/schemas/messages.fbs
namespace itk.protocol;

enum MessageType : uint32 {
  Ping = 0,
  Pong = 1,
  ScreenRect = 2,
  WindowState = 3,
  StateSnapshot = 4,
  StateEvent = 5,
  StateQuery = 6,
  StateResponse = 7,
}

table Header {
  magic: uint32;
  version: uint32;
  msg_type: MessageType;
  payload_len: uint32;
  crc32: uint32;
}

table ScreenRect {
  x: float32;
  y: float32;
  width: float32;
  height: float32;
  rotation: float32;
}

table StateEvent {
  app_id: string;
  event_type: string;
  timestamp_ms: uint64;
  data: string;
}

// ... additional tables
```

#### Phase 2: Dual Support

1. Add `flatbuffers` crate dependency
2. Generate Rust code from schemas
3. Support both formats with version detection
4. Header byte indicates format: bincode=0x00, flatbuffers=0x01

```rust
pub fn decode(data: &[u8]) -> Result<(Header, T)> {
    let header = decode_header(data)?;
    match header.version & 0xFF {
        0x00 => decode_bincode(data),
        0x01 => decode_flatbuffers(data),
        _ => Err(ProtocolError::UnsupportedVersion),
    }
}
```

#### Phase 3: Default Switch

1. Update default encoding to FlatBuffers
2. Mark bincode as deprecated
3. Update all injector templates

#### Phase 4: Removal (Major Version)

1. Remove bincode support in next major version
2. Simplify codebase
3. Update documentation

### Compatibility Matrix

| Client Version | Server Version | Wire Format |
|----------------|----------------|-------------|
| 1.x | 1.x | bincode |
| 2.x | 1.x | bincode (fallback) |
| 1.x | 2.x | bincode (detected) |
| 2.x | 2.x | flatbuffers |

### Build Changes

FlatBuffers requires the `flatc` compiler:

```bash
# Ubuntu/Debian
apt install flatbuffers-compiler

# macOS
brew install flatbuffers

# Windows
# Download from https://github.com/google/flatbuffers/releases
```

Build script integration:

```rust
// build.rs
fn main() {
    // Generate Rust from .fbs files
    flatc_rust::run(flatc_rust::Args {
        inputs: &["schemas/messages.fbs"],
        out_dir: "src/generated/",
        ..Default::default()
    }).expect("flatc failed");
}
```

### Alternatives Considered

#### Protocol Buffers

- Pros: Mature ecosystem, widely used
- Cons: Requires copy on read, larger runtime

#### Cap'n Proto

- Pros: Zero-copy like FlatBuffers
- Cons: Less portable, fewer language bindings

#### MessagePack

- Pros: Simple, schemaless
- Cons: No schema evolution guarantees

### Decision

FlatBuffers chosen for:
1. Zero-copy reads (important for high-frequency state updates)
2. Broad language support (C++ injectors, Python tools)
3. Schema evolution (version compatibility)
4. Google backing and active development

### Timeline

This migration is planned but not scheduled. Implementation will begin when:
- Cross-language injector support is needed
- Python MCP direct integration is prioritized
- Major version bump is planned

### References

- [FlatBuffers Documentation](https://flatbuffers.dev/)
- [FlatBuffers Rust Crate](https://crates.io/crates/flatbuffers)
- [Schema Evolution Best Practices](https://flatbuffers.dev/flatbuffers_guide_writing_schema.html)
