# BioForge

> Agent-driven biological automation platform combining a Raspberry Pi 5 liquid handling system with AI agent orchestration over the Model Context Protocol (MCP).

## Overview

BioForge automates CRISPR-Cas9 gene editing workflows in bacteria, starting with The Odin's DIY CRISPR kit as the foundational experiment set and extending to arbitrary molecular biology protocols through agent-designed experiment pipelines. The platform treats physical lab hardware as MCP tool endpoints, enabling any compatible AI agent to design experiments, issue commands, monitor sensors, analyze results, and iteratively optimize protocols in a closed-loop fashion. All firmware and hardware control code is written in Rust.

**Scope today**: the control, safety, and audit layers are implemented and tested against a simulated hardware layer; the physical instrument is Phases 2 through 5 below, so nothing here has yet driven an actuator or touched biological material. The extension to arbitrary protocols is an ambition, not a capability: an agent-designed protocol cannot run until a human reviews it and adds it to the approved-protocol manifest, and the platform performs no screening of what a protocol targets (see [Safety Features](#safety-features)).

**Design documentation**: [`docs/hardware/bioforge-crispr-automation.md`](../../docs/hardware/bioforge-crispr-automation.md)

**Governance analysis**: [`docs/governance-implications.md`](docs/governance-implications.md)

## Architecture

```
+------------------------------------------------------------+
|  LAYER 1: AI AGENT (Claude / local LLM)                    |
|  Experiment design, protocol reasoning, data analysis       |
+------------------------------+-----------------------------+
                               | MCP (JSON-RPC over stdio/SSE)
+------------------------------+-----------------------------+
|  LAYER 2: MCP SERVER (tools/mcp/mcp_bioforge/)             |
|  Protocol validation, safety interlocks, state machine      |
|  Audit logging, human-in-the-loop gates                     |
+------------------------------+-----------------------------+
                               | Internal API (async channels)
+------------------------------+-----------------------------+
|  LAYER 3: HARDWARE ABSTRACTION (bioforge-hal)               |
|  Pump drivers, temp controllers, camera, sensors            |
+------------------------------+-----------------------------+
                               | GPIO / SPI / I2C / USB
+------------------------------+-----------------------------+
|  LAYER 4: PHYSICAL ACTUATORS                                |
|  Syringe pumps, peristaltic pumps, Peltier modules,         |
|  stepper motors, Pi Camera, temp/humidity sensors            |
+------------------------------------------------------------+
```

## Workspace Structure

```
packages/bioforge/
+-- Cargo.toml                      # Workspace root
+-- deny.toml                       # cargo-deny license/advisory checks
+-- crates/
|   +-- bioforge-types/             # Shared types (config, protocol, errors, tool params)
|   +-- bioforge-safety/            # Safety interlocks, audit log (JSON Lines), rate limiter
|   +-- bioforge-hal/               # Hardware abstraction (pumps, thermal, motion, camera, sensors)
|   +-- bioforge-protocol/          # Protocol state machine, step validation, approval allowlist
|   +-- bioforge-vision/            # Colony counting, plate analysis pipeline
+-- config/
|   +-- hardware.toml               # Pin mappings, calibration values
|   +-- safety_limits.toml          # Max temps, volumes, rates
|   +-- approved_protocols.toml     # Allowlist: content hash + approver per protocol
+-- protocols/
|   +-- odin_crispr_rpsL.toml       # The Odin kit default protocol (approved)
|   +-- custom/                     # Agent-generated protocols; unloadable until approved
+-- firmware/
|   +-- esp32-coprocessor/          # Planned: Embassy no_std real-time firmware
+-- docs/
    +-- governance-implications.md  # AI agent governance analysis
```

MCP server: [`tools/mcp/mcp_bioforge/`](../../tools/mcp/mcp_bioforge/)

## Build

Targets `aarch64-unknown-linux-gnu` (Raspberry Pi 5). Cross-compile from x86_64:

```bash
# Install cross-compilation toolchain
rustup target add aarch64-unknown-linux-gnu

# Build
cd packages/bioforge
cargo build --release --target aarch64-unknown-linux-gnu
```

For development/CI on x86_64 (check + lint only, no hardware access):

```bash
cargo check --workspace
cargo clippy --workspace
cargo fmt --check
```

## Crate Dependencies

| Crate | Key Dependencies |
|-------|-----------------|
| `bioforge-types` | serde, toml, chrono, thiserror |
| `bioforge-safety` | bioforge-types, tracing, chrono |
| `bioforge-hal` | bioforge-types, tokio, async-trait (mock drivers only; no hardware deps yet) |
| `bioforge-protocol` | bioforge-types, toml, tracing, chrono, sha2 |
| `bioforge-vision` | bioforge-types (colony counter is a placeholder; no image processing yet) |

MCP server (`mcp-bioforge`): mcp-core, all bioforge-* crates, tokio, clap, serde_json

## Safety Features

- **Defense-in-depth**: Safety enforced at hardware (E-Stop, thermal fuses), firmware (watchdog, current limiting), HAL (bounds checking), protocol (state machine ordering), and MCP (input validation, rate limiting) layers.
- **Human-in-the-loop gates**: While a gate is open, every actuator tool is refused. Confirmation is out of band (a file the operator creates in the confirmation directory), so the agent cannot confirm its own gate. Two caveats worth knowing: gate placement comes from the `human_gate` flag on protocol steps, which the agent is expected to honor because there is no step executor that enforces it, and a gate whose timeout elapses resolves as `timed_out` and stops blocking actuators. See [Graduated Autonomy](docs/governance-implications.md#graduated-autonomy) for the policy that governs both.
- **Approved-protocol allowlist**: `load_protocol` hashes the protocol file it just read and refuses the load unless that SHA-256 appears in `config/approved_protocols.toml` alongside an approver and a date. Editing an approved protocol revokes its approval; a missing or malformed manifest denies every protocol. No tool writes the manifest. Refusals are audit-logged with the computed hash so an operator who does want to approve the file has the value to record. The shipped manifest approves nothing: each lab that runs a protocol must have its own responsible biosafety reviewer sign off, and a placeholder approver is rejected.
- **Immutable audit log**: Every tool call, sensor reading, state transition, and human interaction logged as append-only JSON Lines.
- **Temperature bounding**: Configurable min/max with overshoot protection and automatic abort.
- **Volume validation**: Dispense volumes checked against configurable limits before actuator commands.
- **Position bounds**: Gantry movements validated against enclosure dimensions.

### What is not bounded

The interlocks above bound *how much* the agent may command (degrees, microliters, microliters per second, millimeters, calls per minute) and, through the allowlist, *whether a human approved this protocol file*. Nothing bounds *what a protocol targets*. There is no sequence or target screening, no gating of nucleic acid orders, and no automated provenance check on an agent-designed protocol beyond a human signature on its content hash. The allowlist prevents unreviewed protocols from running; it is not screening, it cannot judge biological content, and because there is no step executor it does not stop an agent from issuing ad-hoc actuator calls with no protocol loaded.

This is proportionate to one reviewed protocol for a commercially sold BSL-1 teaching kit and is not proportionate to a wider protocol set. Anything beyond that needs screening against established frameworks through an accredited provider, human biosafety review of every new protocol before first execution, and a registry that carries both records. See [What the Interlocks Do Not Bound](docs/governance-implications.md#what-the-interlocks-do-not-bound-protocol-content) for the full argument and why the physical-envelope limits become less informative, not more, as the protocol space grows.

## MCP Tools

| Category | Tools |
|----------|-------|
| Liquid Handling | `dispense`, `aspirate`, `mix`, `move_to` |
| Thermal Control | `set_temperature`, `heat_shock`, `incubate` |
| Imaging | `capture_plate_image`, `count_colonies` |
| Protocol | `list_protocols`, `load_protocol`, `get_system_status`, `request_human_action`, `emergency_stop` |

`list_protocols` reports each protocol's content hash and whether that content is approved; `load_protocol` refuses anything that is not.

## Planned Enhancements

- **Phase 2**: Peltier thermal control with PID tuning, heat shock validation
- **Phase 3**: 3D-printed syringe pumps on XY gantry, ESP32 co-processor integration
- **Phase 4**: Pi Camera imaging pipeline, colony counting with >90% accuracy
- **Phase 5**: Full end-to-end agent-orchestrated experiment with closed-loop optimization
- **Future**: Gel electrophoresis module, spectrophotometer (OD600), multi-plate carousel, multi-agent coordination, sleeper agent detection integration
