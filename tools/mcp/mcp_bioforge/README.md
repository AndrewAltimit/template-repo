# BioForge MCP Server (Rust)

> MCP front end for the [BioForge](../../../packages/bioforge/) lab-automation platform: liquid handling, thermal control, gantry motion, plate imaging, protocol validation, human-in-the-loop gates and emergency stop. Every actuator command goes through `bioforge-safety`'s `SafetyEnforcer` first.

## Status: simulated hardware

The server runs against **simulated drivers**. No pump, heater, motor or camera is driven. Every response includes `"simulated": true`.

- Pumps, motion, camera and sensors use the `bioforge-hal` mock drivers. Thermal uses an in-crate simulator (`src/sim.rs`) that tracks setpoints, because the HAL mock always reports 4 C / 37 C.
- Colony counting calls `bioforge-vision`, which is still a placeholder. It returns a fixed result whatever the image. `count_colonies` always reports `"simulated": true` and includes a note saying so.
- Safety enforcement, protocol validation, e-stop latching, human gates, the dispense budget and the audit log are **real**. They behave exactly as they would with hardware attached.

To use real hardware, build a `lab::Hardware` from real `bioforge-hal` trait implementations in place of `sim::simulated_hardware()` and set `simulated: false`. The tools themselves stay unchanged.

## Quick start

```bash
cd tools/mcp/mcp_bioforge
cargo build --release

# STDIO (Claude Code / local MCP clients). Run from the repo root so the
# default protocols dir (<config-dir>/../protocols) resolves.
./tools/mcp/mcp_bioforge/target/release/mcp-bioforge \
    --mode stdio --config-dir packages/bioforge/config

# Standalone HTTP
./tools/mcp/mcp_bioforge/target/release/mcp-bioforge \
    --mode standalone --port 8030 --config-dir packages/bioforge/config
curl http://localhost:8030/health
```

## Configuration

| Flag | Env var | Default | Purpose |
|------|---------|---------|---------|
| `--mode` | | `standalone` | `standalone`, `stdio`, `server` (REST only), `client` (proxy) |
| `--port` | | `8000` | HTTP port (ignored in stdio mode). Pass `--port 8030` explicitly if you want the port used in the examples |
| `--log-level` | | `info` | Log level. Logs go to stderr |
| `--config-dir` | `BIOFORGE_CONFIG_DIR` | `config` | Directory with `safety_limits.toml` and `hardware.toml` |
| `--protocols-dir` | `BIOFORGE_PROTOCOLS_DIR` | `<config-dir>/../protocols` | Protocol TOML files, plus an optional `custom/` subdirectory |
| `--confirm-dir` | `BIOFORGE_CONFIRM_DIR` | unset | Operator confirmation drop directory for human gates (created if it doesn't exist) |
| `--audit-log` | `BIOFORGE_AUDIT_LOG` | unset | Append-only JSONL audit log of every mutating tool call |

The server checks the config at startup and refuses to start if the config is inconsistent. Examples: `tool_min_c >= tool_max_c`, `tool_max_c > absolute_max_c`, `min_dispense_ul >= max_dispense_ul`, `max_calls_per_minute = 0`, a safe travel height outside the enclosure, or any non-finite value. All problems are reported together.

## Tools

| Tool | Purpose | Parameters (required in **bold**) |
|------|---------|-----------------------------------|
| `dispense` | Dispense a volume; counts against the per-run budget | **`target`**, **`volume_ul`**, **`reagent`**, `flow_rate` |
| `aspirate` | Aspirate from a source | **`source`**, **`volume_ul`**, `flow_rate` |
| `mix` | Aspirate/dispense strokes in place (not counted against the budget) | **`target`**, **`volume_ul`**, **`cycles`**, `flow_rate` |
| `move_to` | Absolute gantry move; `z_mm` defaults to the safe travel height | **`x_mm`**, **`y_mm`**, `z_mm` |
| `home_gantry` | Home all axes | none |
| `set_temperature` | Set a zone's setpoint and read it back. Cancels an active incubation on that zone | **`zone`** (`cold`/`warm`), **`target_c`**, `hold_seconds` (advisory) |
| `heat_shock` | Atomic ramp, hold and return in the warm zone. Fails if the temperature deviates by more than `max_overshoot_c` | **`ramp_to_c`**, **`hold_s`**, **`return_to_c`** |
| `incubate` | Start a long hold. Returns at once with `ends_at` | **`zone`**, **`target_c`**, **`duration_hours`** |
| `capture_plate_image` | Capture and register an image | **`plate_id`**, `lighting_mode` (`white`/`uv_blue`/`dark_field`) |
| `count_colonies` | Analyse a registered image (placeholder pipeline) | **`plate_id`**, **`image_id`** (or `latest`), `min_area_px`, `max_area_px` |
| `list_protocols` | List protocol ids with name and step count | none |
| `load_protocol` | Load a protocol and validate every step against the safety limits | **`protocol_id`** (`name` or `custom/name`) |
| `get_system_status` | Sensors, setpoints, incubations, gantry, e-stop, budget, protocol, gates, limits | none |
| `request_human_action` | Open a human gate. Actuators are refused while it is pending | **`description`**, **`timeout_min`** (1-1440), `wait_seconds` (0-300) |
| `get_human_action_status` | Poll or wait on a gate | **`action_id`**, `wait_seconds` (0-300) |
| `emergency_stop` | Halt everything and latch the stop | `reason` |

`home_gantry`, `list_protocols` and `get_human_action_status` are new in 0.2.0. All 13 original tool names and required parameters are unchanged.

### Error model

- **Malformed requests** fail with a JSON-RPC `-32602 Invalid params` error. Examples: a missing or wrongly typed parameter, an unknown `zone`, an integer out of range, a bad identifier, an unknown protocol or image.
- **Refusals** come back as a tool result with `isError: true` and a `refused: ...` message, so the model can read the reason. A refusal is a well-formed request stopped by a safety limit, the e-stop latch, a pending gate, the rate limit, a hardware fault, a timeout or "hardware busy".
- Integer fields accept integral floats (`45.0`) but reject lossy values (`2.5`, `-1`, values above `u32::MAX` for `cycles`).

### Safety pipeline (every actuator tool)

1. **Stateless validation** of every input. A rejected request consumes no rate-limit budget, actuator spacing or dispense volume. (Before 0.2.0, `dispense` counted the volume before it checked `flow_rate`.)
2. **Admission.** The e-stop latch, then any pending human gate, then `max_calls_per_minute`, then an exclusive hardware lock (gives up after 30 s with "hardware busy"), then `min_actuator_interval_ms`. The interval is waited out once instead of rejecting the call.
3. **Stateful checks.** Cumulative dispense is limited to `max_total_ml`. The budget lasts for the whole server process and reloading a protocol doesn't reset it.
4. **Hardware call** with a timeout: pumps 120 s, motion 60 s, thermal 30 s, heat shock `hold_s` + 180 s, camera 30 s. An emergency stop cancels the call immediately.

`capture_plate_image` is rate limited and serialized, but it still works during an e-stop or a pending gate so the operator can inspect the deck. Status, list and gate-status calls are never throttled.

### Emergency stop

`emergency_stop` does the following:

- cancels in-flight actuator calls
- sets both thermal zones to ambient (the HAL has no "heater off" primitive)
- cancels any open human gate and clears incubations
- latches: every actuator tool is refused after that

It is never rate limited and it is idempotent (`already_active`). **No tool can clear the latch.** Inspect the system, then restart the server.

### Human gates

`request_human_action` returns an `action_id` such as `ha_20260922120000_0001` and blocks every actuator tool until the gate resolves. The operator confirms out of band by creating `<confirm-dir>/<action_id>.confirmed`. The agent can't confirm its own gate. Without `--confirm-dir` a gate can only time out after `timeout_min`. Only one gate can be open at a time. Use `wait_seconds` to block for confirmation for up to 5 minutes. Action ids include the server start time, so confirmation files left over from a previous run never match a new gate.

### Protocols

Protocol ids map to `<protocols-dir>/<id>.toml` or `<protocols-dir>/custom/<id>.toml`. Ids are restricted to `[A-Za-z0-9_-]{1,64}`, and the resolved path is checked again after canonicalization, so traversal and symlink escapes are rejected. Files over 256 KiB are refused. `load_protocol` checks these steps against the live limits:

- volumes and flow rates
- temperatures, hold times and incubation hours
- mix cycles
- positions
- identifiers
- gate timeouts
- the protocol's total dispense against the run budget

It also checks structure: steps must exist, and step ids must be unique and ascending. If a protocol fails, `load_protocol` returns `"validation": "failed"` with per-step `issues` and loads nothing. The server tracks which protocol is active but doesn't execute it; the agent drives each step through the tools.

> The shipped `odin_crispr_rpsL` protocol currently **fails** validation. Steps 1 and 2 each dispense 20 000 uL of agar, and the single-dispense limit in `safety_limits.toml` is 1 000 uL.

### Example

```json
{"name": "heat_shock", "arguments": {"ramp_to_c": 42.0, "hold_s": 45, "return_to_c": 4.0}}
```

```json
{
  "status": "complete", "zone": "warm", "ramp_to_c": 42.0,
  "requested_hold_s": 45, "actual_hold_s": 45.0,
  "peak_temp_c": 42.3, "min_temp_during_hold_c": 41.7, "return_to_c": 4.0,
  "max_deviation_allowed_c": 1.5, "within_tolerance": true, "simulated": true
}
```

## Audit log

With `--audit-log`, every mutating tool call is appended as one JSON line with an fsync, whether it succeeded or was refused. The line records the timestamp, `run_id`, tool, raw arguments and the result or error. Read-only tools (`get_system_status`, `list_protocols`, `get_human_action_status`) aren't logged. A failed audit write is logged as an error but doesn't fail the tool call.

## MCP client configuration

```json
{
  "mcpServers": {
    "bioforge": {
      "command": "tools/mcp/mcp_bioforge/target/release/mcp-bioforge",
      "args": ["--mode", "stdio", "--config-dir", "packages/bioforge/config"],
      "env": { "BIOFORGE_CONFIRM_DIR": "/tmp/bioforge/confirm" }
    }
  }
}
```

## Development

```bash
cd tools/mcp/mcp_bioforge
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test          # offline; drives every tool through Tool::execute
cargo build --release
```

CI covers this crate with the `bio-*` stages of `automation-cli` (`bio-fmt`, `bio-clippy`, `bio-full`).

The tests use fault-injecting HAL doubles (hanging pump, faulting pump, overshooting thermal controller) to exercise timeouts, e-stop cancellation, "hardware busy", fault propagation and tolerance checks.

### Layout

```
src/
  main.rs       CLI, startup wiring
  config.rs     config loading + consistency validation
  lab.rs        safety pipeline, hardware plumbing, run state (the core)
  tools.rs      MCP tool adapters with typed argument parsing
  protocols.rs  protocol discovery, loading, step validation
  validate.rs   identifier / label / description validation
  sim.rs        simulated hardware stack
  error.rs      LabError -> MCP error mapping
  tests.rs      end-to-end tool tests
```

The release profile deliberately does **not** set `panic = "abort"`. mcp-core turns a panicking tool into an `isError` result with `catch_unwind`, and that only works when panics unwind.

## Known limitations

- All hardware is simulated and colony counting is a placeholder (see above).
- `set_temperature.hold_seconds` is advisory. The server validates it but doesn't time it.
- `incubate` doesn't return the zone to ambient when it finishes. The setpoint stays in place until it is changed.
- Aspirate doesn't track source volumes, since there is no reagent inventory model.
- Emergency stop can only safe the zones to ambient, because the HAL has no heater-disable primitive.
