# BioForge: Agent-Driven CRISPR Automation Platform

A Raspberry Pi 5-driven biological automation platform combining liquid handling, thermal control, plate imaging, and colony analysis with AI agent orchestration over the Model Context Protocol (MCP). Designed for closed-loop CRISPR-Cas9 gene editing workflows in BSL-1 organisms, with defense-in-depth safety architecture and immutable audit logging.

**Implementation**: [`packages/bioforge/`](../../packages/bioforge/)

**MCP Server**: [`tools/mcp/mcp_bioforge/`](../../tools/mcp/mcp_bioforge/)

## Purpose

Automate and optimize CRISPR gene editing experiments through AI agent orchestration, starting with The Odin's DIY CRISPR kit (E. coli K-12, BSL-1) and extending to arbitrary molecular biology protocols. The platform treats physical lab hardware as MCP tool endpoints, enabling closed-loop experiment design, execution, analysis, and iterative optimization.

This is explicitly a governance-aware design -- the architecture embodies safety principles that should govern any system where AI agents have physical-world actuation capability over biological materials. Every design decision maps to a principle in the broader AI safety governance conversation: defense in depth, human oversight, audit trails, and capability bounding.

---

## System Architecture

```
+------------------------------------------------------------+
|  LAYER 1: AI AGENT (Claude / local LLM)                    |
|  Experiment design, protocol reasoning, data analysis       |
|  Iterative optimization, failure diagnosis                  |
+------------------------------+-----------------------------+
                               | MCP (JSON-RPC over stdio/SSE)
+------------------------------+-----------------------------+
|  LAYER 2: MCP SERVER (Rust binary on Pi 5)                  |
|  Protocol validation, safety interlocks, state machine       |
|  Audit logging, human-in-the-loop gates                     |
+------------------------------+-----------------------------+
                               | Internal API (async channels)
+------------------------------+-----------------------------+
|  LAYER 3: HARDWARE ABSTRACTION (Rust drivers)               |
|  Pump drivers, temp controllers, camera, sensors            |
|  Calibration state, error recovery                          |
+------------------------------+-----------------------------+
                               | GPIO / SPI / I2C / USB
+------------------------------+-----------------------------+
|  LAYER 4: PHYSICAL ACTUATORS                                |
|  Syringe pumps, peristaltic pumps, Peltier modules,         |
|  stepper motors, Pi Camera, temp/humidity sensors            |
+------------------------------------------------------------+
```

### Data Flow

**Protocol Execution**: Agent designs experiment -> emits MCP tool calls -> MCP server validates against safety constraints -> commands dispatched to hardware drivers -> actuators execute -> sensor data returned -> agent analyzes and decides next step.

**Monitoring**: Sensors continuously stream temperature, humidity, and optical data to the MCP server -> server publishes as MCP resources -> agent subscribes and reacts to anomalies.

**Human-in-the-Loop Gates**: Certain operations require explicit human confirmation. Enforced at the MCP server layer and cannot be bypassed by agent commands. The agent receives a `pending_human_approval` status and waits.

---

## Hardware Design

### Bill of Materials -- Core Compute

| Component | Recommended Model | Purpose | Est. Cost | Interface |
|-----------|-------------------|---------|-----------|-----------|
| Raspberry Pi 5 (8GB) | Official Pi 5 kit w/ PSU | Main compute | $80-100 | N/A |
| Pi Camera Module 3 | Sony IMX708, autofocus | Plate imaging | $25-35 | CSI |
| MicroSD Card (128GB) | Samsung EVO Select | OS + data | $15 | N/A |
| 7" Touchscreen (optional) | Official Pi display | Human gate interface | $60-80 | DSI |

### Bill of Materials -- Liquid Handling

| Component | Recommended Model | Qty | Est. Cost | Interface |
|-----------|-------------------|-----|-----------|-----------|
| Syringe Pump (precision) | 3D-printed, NEMA 17 stepper | 2 | $30-50 ea | GPIO/Step |
| Peristaltic Pump (bulk) | 12V DC, silicone tubing | 2 | $15-25 ea | GPIO/PWM |
| Stepper Motor Drivers | TMC2209 or A4988 | 4 | $5-10 ea | SPI/Step |
| Co-Processor | ESP32-S3 or RP2040 | 1 | $8-15 | UART/USB |

### Bill of Materials -- Thermal Control

| Component | Recommended Model | Qty | Est. Cost | Interface |
|-----------|-------------------|-----|-----------|-----------|
| Peltier Module (TEC) | TEC1-12706, 60W | 2 | $8-12 ea | PWM/H-Bridge |
| H-Bridge Motor Driver | L298N or BTS7960 | 2 | $5-10 ea | GPIO |
| Heat Sink + Fan | 40mm aluminum + 5V fan | 2 | $5 ea | 5V |
| DS18B20 Temp Sensors | Waterproof probe style | 4 | $3-5 ea | 1-Wire |
| DHT22 Humidity Sensor | Enclosure ambient | 1 | $5 | GPIO |

### Bill of Materials -- Enclosure

| Component | Recommended Model | Est. Cost |
|-----------|-------------------|-----------|
| Enclosure Frame | 2020 aluminum extrusion (~2m) | $20-40 |
| Acrylic Panels | 3mm clear/tinted (~0.5m2) | $15-25 |
| 3D-Printed Parts | PLA/PETG, custom mounts | $10-30 |
| LED Ring Light | White + UV/Blue, dimmable | $10-20 |

### Bill of Materials -- Biology

| Component | Specific Part | Est. Cost |
|-----------|--------------|-----------|
| The Odin CRISPR Kit | Complete home lab kit | $160-800 |
| Consumables Restock | Plates, agar, antibiotics | $30-50/run |
| Micropipettes (manual) | For human-in-loop steps (set of 3) | $40-80 |

**Estimated total**: $800-1,500 depending on sourcing and 3D printing availability.

### Enclosure Design

The enclosure serves three purposes: contamination reduction, thermal zone isolation, and camera positioning.

**Thermal Zones**: Divided into a cold zone (~4C via Peltier) and a warm zone (42C heat shock / 37C incubation via separate Peltier). DS18B20 probes provide closed-loop PID temperature control managed by the Rust firmware.

**Camera Mount**: Fixed overhead Pi Camera position captures plate images after incubation. LED ring provides consistent illumination for colony counting. UV/blue LED option enables GFP fluorescence imaging.

**Liquid Handling Gantry**: Simplified XY gantry using linear rails and NEMA 17 steppers positions syringe pump tips over wells and plates. Positional accuracy target: +/-1mm (sufficient for 50-200uL plate dispensing).

### Wiring and Interface Architecture

```
Pi 5 (Rust MCP Server + HAL)
  +-- USB Serial -> ESP32 (stepper control, PID loops)
  |     +-- GPIO -> TMC2209 drivers -> NEMA 17 steppers (XY + syringe)
  |     +-- PWM -> H-Bridge -> Peltier modules (heat/cool)
  |     +-- PWM -> Peristaltic pumps (bulk dispense)
  |     +-- 1-Wire -> DS18B20 temperature probes
  +-- CSI -> Pi Camera Module 3 (plate imaging)
  +-- GPIO -> DHT22 (ambient temp/humidity)
  +-- GPIO -> LED ring (PWM dimming)
  +-- GPIO -> Physical E-Stop button (hardware interrupt)
  +-- WiFi/Ethernet -> MCP transport (SSE to agent host)
```

---

## Software Architecture

### Crate Structure

See [`packages/bioforge/`](../../packages/bioforge/) for the full implementation:

| Crate | Binary | Role |
|-------|--------|------|
| `bioforge-types` | (library) | Shared types: config, protocol schema, errors, tool params |
| `bioforge-safety` | (library) | Stateful safety enforcement (cumulative volume, rate limiting, actuator interval), NaN/Inf guards, audit log (JSON Lines) |
| `bioforge-hal` | (library) | Hardware drivers: pumps, thermal (PID), motion, camera, sensors |
| `bioforge-protocol` | (library) | Protocol state machine, step validation, human gates |
| `bioforge-vision` | (library) | Colony counting, plate analysis pipeline |

MCP server at [`tools/mcp/mcp_bioforge/`](../../tools/mcp/mcp_bioforge/):

| Binary | Role |
|--------|------|
| `mcp-bioforge` | MCP server exposing all tools, transport (stdio/SSE), safety validation |

### MCP Tool Definitions

#### Liquid Handling Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `dispense` | `target, volume_ul, reagent, flow_rate` | Dispense precise volume to target position. Cumulative tracking (50 mL/run). Flow rate validated |
| `aspirate` | `source, volume_ul, flow_rate` | Aspirate from source container |
| `mix` | `target, volume_ul, cycles, flow_rate` | Aspirate-dispense cycles to mix in place |
| `move_to` | `x_mm, y_mm, z_mm` | Move gantry to absolute position. `z_mm` optional (defaults to 15mm safe travel height) |

#### Thermal Control Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `set_temperature` | `zone, target_c, hold_seconds` | PID-controlled temperature hold |
| `heat_shock` | `ramp_to_c, hold_s, return_to_c` | Atomic heat shock sequence |
| `incubate` | `zone, target_c, duration_hours` | Long-duration monitored hold |

#### Imaging and Analysis Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `capture_plate_image` | `plate_id, lighting_mode` | High-res image (white/UV/dark field) |
| `count_colonies` | `plate_id, image_id` | Colony counting with size distribution |

#### Protocol and System Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `load_protocol` | `protocol_id` | Load and validate a saved protocol TOML |
| `get_system_status` | (none) | All sensor readings, actuator states, safety status |
| `request_human_action` | `action_description, timeout_min` | Pause for human confirmation |
| `emergency_stop` | (none) | Halt all actuators, disable heaters, safe the system |

### Protocol State Machine

```
Protocol States (CRISPR Workflow):

  IDLE
    |
    +-- [agent: load_protocol] -> PROTOCOL_LOADED
    |
  PROTOCOL_LOADED
    |
    +-- [agent: prepare_media] -> MEDIA_PREP
    |
  MEDIA_PREP -> MEDIA_READY (after solidification timer)
    |
    +-- [HUMAN GATE: load cells + reagents] -> REAGENTS_LOADED
    |
  REAGENTS_LOADED
    |
    +-- [agent: execute_transformation] -> TRANSFORMING
    |     (mix cells + DNA, ice incubation, heat shock, recovery)
    |
  TRANSFORMING -> TRANSFORMATION_COMPLETE
    |
    +-- [agent: plate_cells] -> PLATING
    |
  PLATING -> PLATES_READY
    |
    +-- [HUMAN GATE: confirm plates into incubator] -> INCUBATING
    |
  INCUBATING (37C, 12-16 hours, monitored)
    |
    +-- [timer + temp stable] -> INCUBATION_COMPLETE
    |
    +-- [agent: capture + analyze] -> ANALYZING
    |
  ANALYZING -> EXPERIMENT_COMPLETE
    |
    +-- [agent: design_next_experiment] -> PROTOCOL_LOADED (loop)
```

Human Gates are enforced at the state machine level and cannot be bypassed by agent commands. Loading biological reagents onto the deck and confirming plate placement in the incubator require a human to verify the physical state matches the system's assumptions.

---

## Agent Integration

### Closed-Loop Experiment Cycle

```
  1. DESIGN    -- Agent reasons about goals, prior results, reagents.
  |              Generates protocol TOML.
  |
  2. VALIDATE  -- MCP server validates against safety limits,
  |              hardware capabilities, reagent inventory.
  |
  3. EXECUTE   -- Protocol runs through state machine. Agent monitors
  |              sensor telemetry, intervenes on anomalies.
  |
  4. OBSERVE   -- Agent captures plate images, runs colony counting,
  |              computes metrics (transformation efficiency, morphology).
  |
  5. ANALYZE   -- Agent compares results to hypothesis, updates
  |              internal model of parameter effects.
  |
  6. ITERATE   -- Agent designs next experiment (adjust DNA concentration,
  |              heat shock duration, recovery time, plating volume).
  |
  +------------ Return to step 1
```

### Capabilities by Workflow Phase

| Phase | Agent Capability | Automation Level | Human Role |
|-------|-----------------|------------------|------------|
| Media Prep | Calculate volumes, concentrations; sequence dispense | Full automation | Verify reagent placement |
| Transformation | Optimize timing, temperature profiles; monitor PID | Full automation with monitoring | Load cells/DNA onto deck |
| Plating | Design plate layout, calculate dilutions, control dispense | Full automation | Confirm plate quality |
| Incubation | Monitor temp stability, predict completion, alert on drift | Automated monitoring | Physical plate transfer |
| Analysis | Colony counting, morphology assessment, efficiency calculation | Full automation | Validate counts visually |
| Iteration | Parameter optimization, experiment design | Agent-driven with approval | Approve next experiment |

### Example MCP Interaction (Heat Shock)

```json
// Agent -> MCP Server: Initiate heat shock
{
  "method": "tools/call",
  "params": {
    "name": "heat_shock",
    "arguments": {
      "ramp_to_c": 42.0,
      "hold_s": 45,
      "return_to_c": 4.0
    }
  }
}

// MCP Server -> Agent: Progress notification
{
  "method": "notifications/resources/updated",
  "params": {
    "uri": "bioforge://thermal/warm_zone",
    "contents": {
      "current_c": 41.8,
      "target_c": 42.0,
      "phase": "ramping",
      "elapsed_s": 12
    }
  }
}

// MCP Server -> Agent: Complete
{
  "result": {
    "status": "complete",
    "actual_hold_s": 45.2,
    "peak_temp_c": 42.3,
    "min_temp_during_hold_c": 41.7,
    "thermal_profile": "bioforge://data/run_007/heat_shock.csv"
  }
}
```

---

## Safety Architecture

Safety is architected at multiple layers following a defense-in-depth model. No single layer's failure should allow unsafe operation.

### Safety Layers

| Layer | Mechanism | What It Prevents | Bypass Policy |
|-------|-----------|-----------------|---------------|
| Hardware | Physical E-Stop button | Any unsafe actuator state | Cannot be bypassed |
| Hardware | Thermal fuse on Peltier | Overheating beyond 60C | Cannot be bypassed |
| Firmware | Watchdog timer on ESP32 | Firmware hang / runaway | Auto-resets to safe state |
| Firmware | Motor current limiting | Stepper stall / jam | Cannot be bypassed |
| HAL | Volume bounds checking | Dispensing impossible volumes | Agent cannot override |
| HAL | Temperature range limits | Heating beyond safe range (-5 to 50C) | Configurable but logged |
| HAL | Cumulative volume tracking | Exceeding 50 mL per run | Resets on new run only |
| Protocol | State machine ordering | Steps executed out of order | Agent cannot override |
| Protocol | Human-in-the-loop gates | Unattended bio operations | Requires physical confirm |
| MCP | NaN/Infinity guards | Bypassing comparisons via NaN | Agent cannot override |
| MCP | Tool input validation | Malformed or out-of-range params | Agent cannot override |
| MCP | `absolute_max_c` guard | Misconfigured tool limits above 60C fuse | Defense-in-depth |
| MCP | Sliding-window rate limit | >60 calls per minute | Configurable but logged |
| MCP | Actuator interval (100ms) | Rapid-fire actuator abuse | Configurable but logged |
| MCP | Flow rate validation | Pump speed above 500 uL/s | Agent cannot override |
| Audit | Immutable operation log | Untracked changes to protocol | Append-only, no deletion |

### Stateful Safety Enforcer

The `SafetyEnforcer` in `bioforge-safety` is a stateful validator that tracks cumulative state across tool calls within a single experiment run. All limits are config-driven, loaded from `safety_limits.toml` and `hardware.toml` at server startup via the `--config-dir` flag. Internal state is protected by `Mutex<EnforcerState>` and the enforcer is shared across all MCP tools via `Arc<SafetyEnforcer>`.

Key capabilities:
- **Input sanitization** -- All numeric inputs pass through `require_finite()` guards that reject NaN and Infinity before any comparison
- **Defense-in-depth temperature guard** -- Checks both `tool_max_c` (50C) and `absolute_max_c` (60C hardware fuse) independently
- **Cumulative volume tracking** -- Tracks total dispensed volume across all `dispense` calls, rejecting operations that would exceed 50 mL per run
- **Flow rate validation** -- Enforces maximum pump speed (500 uL/s) on all liquid handling tools
- **Sliding-window rate limiting** -- 60-second sliding window, rejecting calls that exceed 60 calls/minute
- **Actuator interval enforcement** -- Minimum 100ms gap between consecutive actuator commands
- **Operation-specific limits** -- Max incubation (72h), max heat shock hold (300s), max mix cycles (20), safe travel height (15mm) -- all from config

### Audit Logging

Every tool call, sensor reading, state transition, and human interaction is logged as append-only JSON Lines:

```jsonl
{"ts":"2026-02-05T14:23:01Z","event":"tool_call","tool":"heat_shock",
  "args":{"ramp_to_c":42.0,"hold_s":45,"return_to_c":4.0},
  "caller":"agent","run_id":"run_007"}

{"ts":"2026-02-05T14:23:47Z","event":"sensor","zone":"warm",
  "temp_c":42.3,"target_c":42.0,"stable":true,"run_id":"run_007"}

{"ts":"2026-02-05T14:24:32Z","event":"tool_result","tool":"heat_shock",
  "status":"complete","actual_hold_s":45.2,"run_id":"run_007"}

{"ts":"2026-02-05T14:25:00Z","event":"human_gate",
  "action":"confirm_plate_placement","status":"approved",
  "confirmed_by":"touchscreen","run_id":"run_007"}
```

---

## Build Phases

### Phase 1: Foundation (Weeks 1-2)

Pi 5 running Rust MCP server with simulated hardware, basic enclosure frame. Safety enforcement is fully active even in mock mode -- all tool inputs are validated through the stateful `SafetyEnforcer` before mock responses are returned. Limits are config-driven, loaded from `safety_limits.toml` and `hardware.toml` via the `--config-dir` flag.

1. Set up Pi 5 with Rust toolchain and cross-compilation for ARM64.
2. Implement MCP server with all tool definitions returning mock responses.
3. Build basic enclosure frame from 2020 extrusion. No actuators yet.
4. Verify MCP transport end-to-end: agent issues commands, server responds.
5. Implement audit logging infrastructure.
6. Implement stateful safety enforcement: config-driven limits from TOML, cumulative volume tracking, sliding-window rate limiting, actuator interval enforcement, NaN/Infinity guards.

**Milestone**: Agent can "run" a full protocol against simulated hardware with all safety enforcement active.

### Phase 2: Thermal Control (Weeks 3-4)

Working temperature control with Peltier modules and PID tuning.

1. Wire Peltier modules with H-bridge drivers and DS18B20 probes.
2. Implement PID controller in `bioforge-hal/thermal.rs`. Tune Kp, Ki, Kd.
3. Build cold zone (4C) and warm zone (37-42C).
4. Implement `heat_shock` tool as atomic operation with real thermal control.
5. Validate temperature accuracy over 1-hour holds.

**Milestone**: Heat shock cycle (4C -> 42C hold 45s -> 4C) with +/-0.5C accuracy.

### Phase 3: Liquid Handling (Weeks 5-7)

Working syringe pumps on XY gantry, dispensing calibrated volumes.

1. 3D-print syringe pump bodies and gantry mounts.
2. Wire NEMA 17 steppers with TMC2209 drivers on ESP32 co-processor.
3. Build XY gantry with linear rails (+/-1mm accuracy target).
4. Calibrate syringe pump: steps-per-microliter mapping.
5. Implement dispense, aspirate, and mix tools with real hardware.

**Milestone**: Accurately dispense 10-500uL volumes to specified positions.

### Phase 4: Imaging and Vision (Weeks 8-9)

Pi Camera captures plate images, colony counting pipeline operational.

1. Mount Pi Camera with fixed focal distance over plate imaging position.
2. Build LED ring light with white and UV/blue modes.
3. Implement `capture_plate_image` tool with consistent lighting.
4. Build colony counting pipeline in `bioforge-vision`.
5. Validate colony counts against manual counting.

**Milestone**: Colony counting with >90% accuracy versus manual count.

### Phase 5: Integration and First Run (Weeks 10-12)

Complete system running The Odin CRISPR protocol end-to-end with agent orchestration.

1. Integrate all subsystems through the protocol state machine.
2. Implement human-in-the-loop gates on touchscreen.
3. Run first agent-orchestrated experiment using The Odin kit.
4. Agent analyzes results and proposes parameter adjustments.
5. Validate closed-loop optimization over 3-5 experiment iterations.

**Milestone**: Multiple agent-orchestrated experiments with measurable optimization.

---

## Testing Procedure

```
Test 1 -- MCP tools (mock mode):
  Start mcp-bioforge in standalone mode.
  Issue each tool call via curl. Verify mock responses are well-formed JSON.
  Verify all calls are logged to audit file.

Test 2 -- Protocol state machine:
  Load odin_crispr_rpsL.toml protocol.
  Step through transitions. Verify ordering constraints enforced.
  Attempt invalid transition -- verify rejection.
  Verify human gate blocks execution until confirmed.

Test 3 -- Safety limits:
  Attempt set_temperature above tool_max_c (50C) -- verify rejection.
  Attempt set_temperature above absolute_max_c (60C) -- verify rejection.
  Attempt dispense above max_dispense_ul (1000 uL) -- verify rejection.
  Attempt cumulative dispense above max_total_ml (50 mL) -- verify rejection.
  Attempt dispense with NaN volume -- verify rejection before comparison.
  Attempt move_to outside enclosure bounds -- verify rejection.
  Attempt flow_rate above max_flow_rate_ul_s (500 uL/s) -- verify rejection.
  Verify all rejections logged to audit file.

Test 4 -- Thermal control (Phase 2):
  Set cold zone to 4C. Verify PID converges within 5 minutes.
  Set warm zone to 37C. Verify stability (+/-0.5C) over 1 hour.
  Execute heat shock cycle. Verify timing and temperature profile.

Test 5 -- Liquid handling (Phase 3):
  Dispense 100uL water onto scale. Verify volume accuracy (+/-5%).
  Move gantry to 5 positions. Verify positional accuracy (+/-1mm).
  Run 10-cycle mix operation. Verify no air bubbles or spills.

Test 6 -- Colony counting (Phase 4):
  Capture image of known plate (manual count as ground truth).
  Run colony counter. Compare automated count to manual.
  Verify >90% accuracy on 5 test plates.

Test 7 -- End-to-end (Phase 5):
  Run complete protocol with agent orchestration.
  Verify all state transitions, human gates, sensor readings logged.
  Compare transformation efficiency to manual protocol execution.
```

---

## Security Considerations

| Threat | Mitigation |
|--------|------------|
| Agent commands out-of-range parameters | Stateful `SafetyEnforcer` validates all inputs at MCP layer; NaN/Infinity rejected before comparison |
| NaN/Infinity bypass of bounds checks | All numeric inputs pass through `require_finite()` -- NaN silently passes `<` comparisons but is caught explicitly |
| Cumulative reagent exhaustion | Enforcer tracks dispensed volume per run (50 mL cap); resets only via explicit `reset_run()` |
| Agent attempts to bypass human gates | State machine enforces gates; agent receives pending status |
| Rapid-fire actuator commands | Sliding-window rate limiting (60 calls/min) + minimum 100ms actuator interval |
| Thermal runaway | Hardware thermal fuses (60C), `absolute_max_c` software guard, PID overshoot detection, auto-abort |
| Mechanical jam / stall | Motor current limiting on stepper drivers |
| Firmware hang | ESP32 watchdog timer auto-resets to safe state |
| Audit log tampering | Append-only file with nanosecond timestamps and `sync_data()`, no deletion API exposed to agent |
| Malicious protocol injection | Protocol validation checks all steps against safety limits; step IDs must be unique and ascending |
| Power loss during operation | All actuators default to safe state (heaters off, pumps stopped) |
| Reagent contamination | Human gates require physical verification of deck state |

---

## Planned Enhancements

### Hardware Expansion
- **Gel electrophoresis module** -- verify DNA fragment sizes at the molecular level
- **Spectrophotometer (OD600)** -- growth curve monitoring for real-time agent decisions
- **Multi-plate incubator carousel** -- parallel experiments for higher throughput

### Protocol Expansion
- **Fluorescent yeast engineering** (GFP insertion) -- adds fluorescence imaging
- **Antibiotic resistance profiling** -- MIC measurement across bacterial strains
- **Gene expression optimization** -- promoter strength and RBS sequence optimization

### Software Expansion
- **Multi-agent coordination** -- planning, execution, and analysis agents in delegate pattern
- **Protocol sharing** -- federated learning across multiple BioForge installations
- **Sleeper agent detection** -- apply existing detection framework to monitor for anomalous agent behavior during autonomous operation
- **Digital twin simulation** -- agent tests protocol variations against simulated model before committing physical reagents
