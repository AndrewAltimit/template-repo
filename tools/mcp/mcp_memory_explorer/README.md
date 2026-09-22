# Memory Explorer MCP Server (Rust)

> A read-only Model Context Protocol server for process memory exploration and
> reverse engineering: process/module listing, typed reads, hex dumps,
> signature scans, value search with refinement ("next scan"), pointer chains,
> and change watches.

This is a native binary, a documented exception to the repo's container-first
rule: it has to see host processes, which a container cannot.

## Platform support

| Feature | Windows | Linux | macOS / other |
|---------|---------|-------|---------------|
| `list_processes` | Yes | Yes | Yes |
| Attach, read, scan, watch, pointers | Yes (`ReadProcessMemory`, `VirtualQueryEx`, Toolhelp) | Yes (`/proc/<pid>/mem`, `/proc/<pid>/maps`) | No (tools return a clear "not supported" error) |
| 32-bit (WoW64) targets | Yes (pointer width detected) | Yes (ELF class detected) | - |

**Permissions.** The server only *reads* memory and never writes it.
- Windows: the process is opened with `PROCESS_VM_READ | PROCESS_QUERY_INFORMATION | SYNCHRONIZE`
  (not `PROCESS_ALL_ACCESS`). Same-user processes normally work; other users'
  or elevated processes need an elevated server. Protected processes and
  anti-cheat-guarded games refuse access.
- Linux: the kernel's ptrace access check applies. Use the same user with
  `kernel.yama.ptrace_scope=0`, or grant `CAP_SYS_PTRACE`. Wine/Proton games
  work: their PE images appear as file-backed modules.

Only inspect software you are permitted to analyze.

## Quick start

```bash
cd tools/mcp/mcp_memory_explorer
cargo build --release

# STDIO transport (Claude Code / local MCP clients)
./target/release/mcp-memory-explorer --mode stdio

# HTTP transport (default port 8028)
./target/release/mcp-memory-explorer --mode standalone
curl http://localhost:8028/health
```

### CLI arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--mode` | `standalone` (HTTP MCP), `stdio`, `server` (REST only), `client` (proxy) | `standalone` |
| `--port` | HTTP port (ignored in stdio mode) | `8028` |
| `--backend-url` | Backend for `client` mode | - |
| `--log-level` | `trace`, `debug`, `info`, `warn`, `error` (logs go to stderr) | `info` |

No environment variables are required.

### MCP configuration (`.mcp.json`)

```json
{
  "mcpServers": {
    "memory-explorer": {
      "command": "mcp-memory-explorer",
      "args": ["--mode", "stdio"]
    }
  }
}
```

## Address syntax

Every `address` / `base` parameter accepts:

| Form | Meaning |
|------|---------|
| `0x7FF6A1B2C3D4` | Hex absolute address (the `0x` prefix is required for hex) |
| `140737488355328` | Decimal absolute address (a JSON integer also works) |
| `NMS.exe` or `NMS` | Base of a module (case-insensitive; the extension may be omitted when unambiguous) |
| `NMS.exe+0x1234`, `NMS.exe+4660` | Module base plus an offset |
| `NMS.exe-0x10` | Module base minus an offset |

Module names that contain `-` (for example `api-ms-win-core-synch-l1-2-0.dll`)
are handled correctly. The module list is refreshed automatically when a name
is not found, so DLLs loaded after attaching resolve too.

## Tools

All responses are JSON with `"success": true|false`. Failures carry `"error"`
and set the MCP `isError` flag. Missing or mistyped arguments are rejected as
invalid parameters and never crash the server. Numeric parameters also accept
numeric strings (`"64"`, `"0x40"`).

| Tool | Parameters | Description |
|------|------------|-------------|
| `list_processes` | `filter?` | Running processes (`name`, `pid`), sorted by name. |
| `attach_process` | `process_name`, `pid?` | Attach read-only. `.exe` is optional. If several processes share the name, the lowest pid is chosen and the others are listed in `other_matching_pids`; pass `pid` to choose one. |
| `detach_process` | - | Close the handle and clear watches and scan candidates. |
| `get_modules` | `filter?` | Modules sorted by base: `name`, `base_address`, `end_address`, `size`, `size_mb`, `path`. |
| `get_memory_regions` | `module?`, `writable_only?`, `executable_only?`, `limit?` (200) | Committed regions with protection flags, kind (`image`/`private`/`mapped`) and owning module. |
| `read_memory` | `address`, `type?` (`bytes`), `size?` (64) | Decode a value (see types below). `size` applies to `bytes`/`string`/`wstring` (max 64 KiB). Variable-size reads return the readable prefix with `truncated`. Fixed-size reads fail if not every byte is readable. |
| `dump_memory` | `address`, `size?` (256) | Hex + ASCII dump, 16 bytes per line, max 64 KiB. Stops at the first unreadable page (`truncated: true`). |
| `scan_pattern` | `pattern`, `module?`, `return_all?` (false), `max_results?` (20), `timeout_secs?` (30) | Signature scan with `??` wildcards. Scope: main executable by default, a named module, or `*` for all readable memory. Hits include a stable `module_offset` (`Game.exe+0x1A2B`). |
| `find_value` | `value`, `type?` (`float`), `module?`, `tolerance?`, `aligned?` (true), `max_results?` (50), `timeout_secs?` (30) | Value search. Default scope is **all writable memory** (heap, stack, globals), where game state lives. Up to 100,000 matches are kept for `refine_value`. |
| `refine_value` | `mode?` (`equal`), `value?`, `tolerance?`, `max_results?` (50) | Re-read the previous `find_value` matches and keep those that are `equal` to a new value, or that `changed`, stayed `unchanged`, `increased`, or `decreased`. |
| `resolve_pointer` | `base`, `offsets`, `type?`, `size?` | Follow a pointer chain; optionally decode a value at the final address. |
| `watch_address` | `label`, `address`, `type?` (`float`), `size?` | Add or replace a watch. The address must be readable now. Max 256 watches. |
| `read_watches` | - | All watches sorted by label: `value`, `raw_hex`, `changed`, `previous_value`. Unreadable watches carry an `error` and the rest are still reported. |
| `remove_watch` | `label` | Remove a watch (an error if the label does not exist). |
| `get_status` | - | Attached process, pid, bitness, `process_alive`, watches, scan count, candidate count, platform support. |

### Data types

| Type | Size | Notes |
|------|------|-------|
| `bytes` | `size` | Lowercase hex string |
| `int8`/`int16`/`int32`/`int64` | 1/2/4/8 | Signed, little-endian |
| `uint8`/`uint16`/`uint32`/`uint64` | 1/2/4/8 | Unsigned |
| `float` / `double` | 4 / 8 | Shortest round-trip form (`1234.56`, not `1234.56005859375`). NaN/inf are returned as strings. |
| `string` | `size` | NUL-terminated UTF-8/ANSI (lossy) |
| `wstring` | `size` | NUL-terminated UTF-16LE (Windows `wchar_t*`) |
| `pointer` | 4 or 8 | Width follows the target's bitness; returned as hex |
| `vector3` / `vector4` | 12 / 16 | `{x, y, z[, w]}` floats |
| `matrix4x4` | 64 | Row-major `[[f32; 4]; 4]` |

Aliases such as `i32`, `f32`, `f64`, `ptr`, `vec3`, and `matrix` are accepted.
`find_value` and `refine_value` accept the scalar types, including `pointer`,
which finds everything that points at an address.

### Pattern syntax

Whitespace-separated hex bytes. `??`, `?`, `*`, or `**` is a wildcard. Runs
like `488B05` are also accepted. A pattern needs at least one literal byte and
is limited to 1024 bytes.

### Pointer chain semantics

For each offset, the server reads a pointer at the current address and then
adds the offset. This matches Cheat Engine's notation:

```
final = [[[base] + o1] + o2] + o3
```

- `offsets: []` returns `base` unchanged. To dereference once without an
  offset, use `offsets: [0]`.
- Offsets can be integers or strings (`"0x10"`, `"-0x8"`). A string that does
  not parse is rejected; it is never silently dropped.
- A null pointer or an unreadable step fails with the step index and address.
- The response has `final_address`, `steps` (the address after each hop,
  starting with `base`), and a detailed `chain` (`read_from`, `pointer`,
  `offset`, `result`).

### Value search details

- Integers are range-checked against the type. `256` as `uint8` or `1.5` as
  `int32` is an error; nothing is silently truncated. Use strings for exact
  64-bit values or hex: `"0xFFFFFFFFFFFFFFFF"`.
- Float search is exact by default. Set `tolerance` (for example `0.01`) to
  match displayed values that are rounded.
- `aligned: true` (the default) checks only addresses that are multiples of the
  value size. This is much faster and matches how compilers lay out data.

### Limits and timeouts

| Limit | Value |
|-------|-------|
| `read_memory` / `dump_memory` size | 64 KiB |
| Scan time budget | `timeout_secs`, default 30 s, max 300 s. Partial results are returned with `timed_out: true`. |
| `max_results` | 1 - 10,000 |
| Retained `find_value` candidates | 100,000 (`candidates_truncated: true` when hit) |
| Watches | 256, each up to 4096 bytes |
| Pointer chain depth | 32 offsets |

Scans read memory in 1 MiB chunks (with overlap, so matches that straddle a
chunk boundary are found exactly once), skip unreadable and guard pages, and
run on a blocking worker thread so the MCP transport stays responsive.

## Example session

```
> attach_process process_name="NMS"
{"result": {"process_name": "NMS.exe", "pid": 12345, "base_address": "0x7ff6a1b20000",
            "main_module": "NMS.exe", "module_count": 187, "is_32bit": false}}

# Find the player's health (currently 100) and narrow it down
> find_value value=100 type="float"
{"total_found": 3120, "results": [...], "hint": "Change the value in the target, then call refine_value ..."}
  (take damage in game; health is now 75)
> refine_value mode="equal" value=75
{"before": 3120, "remaining": 2, "results": [{"address": "0x1f2a3b4c5d0", "value": 75.0}, ...]}

# Watch it
> watch_address label="health" address="0x1f2a3b4c5d0" type="float"
> read_watches
{"watches": [{"label": "health", "value": 60.0, "changed": true, "previous_value": 75.0}]}

# Signature scan in the main module, then follow a static pointer
> scan_pattern pattern="48 8B 05 ?? ?? ?? ?? 48 85 C0"
{"results": [{"address": "0x7ff6a1c45678", "module_offset": "NMS.exe+0x125678"}]}
> resolve_pointer base="NMS.exe+0x3A1B2C0" offsets=["0x10", "0x8"] type="vector3"
{"final_address": "0x1f2a3b4c5e8", "value": {"value": {"x": 12.5, "y": 3.0, "z": -40.25}}}
```

## Architecture

```
src/
  main.rs            CLI (mcp-core MCPServerArgs, default port 8028)
  server.rs          MCP tools: typed args, blocking-pool execution, JSON responses
  explorer.rs        Platform-independent engine: scopes, chunked scanning,
                     value search/refine, pointer chains, watches
  types.rs           Value types, decode/encode rules, search targets
  address.rs         Address/offset parsing
  pattern.rs         Wildcard byte patterns (memchr-accelerated)
  backend/
    mod.rs           ProcessMemory trait, page-wise partial-read fallback
    windows.rs       OpenProcess/ReadProcessMemory/VirtualQueryEx/Toolhelp (RAII handles)
    linux.rs         /proc/<pid>/mem + /proc/<pid>/maps
    mock.rs          In-memory fake process for unit tests
```

All OS-specific `unsafe` code is in `backend/windows.rs`, and each block
documents why it is sound. Kernel handles are owned by an RAII wrapper, so no
path leaks them. Every read is bounded by the size of its caller-provided
buffer. The Linux backend needs no `unsafe`.

## Development

```bash
cd tools/mcp/mcp_memory_explorer
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test
cargo build --release
```

Tests run offline and need no privileges. The engine and tool layer run
against an in-memory mock process that covers scans across chunk boundaries,
partial reads, 32-bit pointers, refinement, watches, and process exit. On
Windows and Linux, one extra test attaches to the test process itself and
exercises the real OS backend.

To check the Linux build from Windows (mount the repo root so the
`../mcp_core_rust` path dependency resolves):

```bash
docker run --rm -v "$PWD/../../..:/w" -w /w/tools/mcp/mcp_memory_explorer \
  -e CARGO_TARGET_DIR=/tmp/target rust:1.93 \
  sh -c "rustup component add clippy && cargo clippy --all-targets -- -D warnings && cargo test"
```

## Known limitations

- Read-only by design: there is no memory writing, code injection, or
  breakpoint/debugger support.
- One attached process per server instance. Tool calls are serialized, so a
  long scan delays other calls until it finishes or times out.
- `refine_value` `increased`/`decreased` compares 64-bit integers as `f64`, so
  values above 2^53 lose precision.
- On Windows, a 32-bit build of the server cannot inspect 64-bit processes.
  Release builds are 64-bit.
- macOS has no memory backend.
