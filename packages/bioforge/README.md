# BioForge

> Agent-driven biological automation platform combining a Raspberry Pi 5 liquid handling system with AI agent orchestration over the Model Context Protocol (MCP).

## Overview

BioForge automates CRISPR-Cas9 gene editing workflows in bacteria, starting with The Odin's DIY CRISPR kit as the foundational experiment set and extending to arbitrary molecular biology protocols through agent-designed experiment pipelines. The platform treats physical lab hardware as MCP tool endpoints, enabling any compatible AI agent to design experiments, issue commands, monitor sensors, analyze results, and iteratively optimize protocols in a closed-loop fashion. All firmware and hardware control code is written in Rust.

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
|   +-- bioforge-protocol/          # Protocol state machine, step validation
|   +-- bioforge-vision/            # Colony counting, plate analysis pipeline
+-- config/
|   +-- hardware.toml               # Pin mappings, calibration values
|   +-- safety_limits.toml          # Max temps, volumes, rates
+-- protocols/
|   +-- odin_crispr_rpsL.toml       # The Odin kit default protocol
|   +-- custom/                     # Agent-generated protocols saved here
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
| `bioforge-hal` | bioforge-types, tokio, async-trait, pid, rppal (aarch64 only) |
| `bioforge-protocol` | bioforge-types, toml, tracing |
| `bioforge-vision` | bioforge-types, image, imageproc |

MCP server (`mcp-bioforge`): mcp-core, all bioforge-* crates, tokio, clap, serde_json

## Safety Features

- **Defense-in-depth**: Safety enforced at hardware (E-Stop, thermal fuses), firmware (watchdog, current limiting), HAL (bounds checking), protocol (state machine ordering), and MCP (input validation, rate limiting) layers.
- **Human-in-the-loop gates**: Certain protocol transitions require physical human confirmation and cannot be bypassed by agent commands.
- **Immutable audit log**: Every tool call, sensor reading, state transition, and human interaction logged as append-only JSON Lines.
- **Temperature bounding**: Configurable min/max with overshoot protection and automatic abort.
- **Volume validation**: Dispense volumes checked against configurable limits before actuator commands.
- **Position bounds**: Gantry movements validated against enclosure dimensions.

## MCP Tools

| Category | Tools |
|----------|-------|
| Liquid Handling | `dispense`, `aspirate`, `mix`, `move_to` |
| Thermal Control | `set_temperature`, `heat_shock`, `incubate` |
| Imaging | `capture_plate_image`, `count_colonies` |
| Protocol | `load_protocol`, `get_system_status`, `request_human_action`, `emergency_stop` |

## Planned Enhancements

- **Phase 2**: Peltier thermal control with PID tuning, heat shock validation
- **Phase 3**: 3D-printed syringe pumps on XY gantry, ESP32 co-processor integration
- **Phase 4**: Pi Camera imaging pipeline, colony counting with >90% accuracy
- **Phase 5**: Full end-to-end agent-orchestrated experiment with closed-loop optimization
- **Future**: Gel electrophoresis module, spectrophotometer (OD600), multi-plate carousel, multi-agent coordination, sleeper agent detection integration
