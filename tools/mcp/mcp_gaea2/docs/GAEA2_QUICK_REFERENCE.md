# Gaea2 MCP Quick Reference

> One-page cheat sheet. Full details: [crate README](../README.md).

## Typical agent flow

1. `list_gaea2_templates` (optionally `include_workflow: true`) or `list_gaea2_nodes`
2. Build or edit `nodes` / `connections`; `suggest_gaea2_nodes` for ideas
3. `validate_and_fix_workflow` to see errors, warnings and fixes
4. `create_gaea2_project` (validates again; refuses to write invalid workflows)
5. On the Windows host: `run_gaea2_project`, then `analyze_execution_history` if it fails
6. For hand-edited or old files: `repair_gaea2_project` with `dry_run: true` first

## Minimal workflow

```json
{
  "project_name": "simple_mountain",
  "nodes": [
    {"id": 1, "type": "Mountain"},
    {"id": 2, "type": "Erosion2", "properties": {"Duration": 0.15}},
    {"id": 3, "type": "Export", "save_definition": {"filename": "height", "format": "PNG16"}}
  ],
  "connections": [[1, 2], [2, 3]]
}
```

Nothing is added implicitly except random `Seed`s on generator nodes and automatic
positions; add your own Export (with `save_definition`) and colorization nodes.

## Ports

| Node | Inputs | Extra outputs |
|------|--------|---------------|
| Generators (Mountain, Volcano, Perlin, ...) | none | - |
| Most nodes | `In` | - |
| Combine / Blend / Max / Min / Multiply / Compare | `In`, `Input2`, `Mask` | - |
| Erosion2 / Erosion | `In` | `Flow`, `Wear`, `Deposits` |
| Rivers | `In`, `Headwaters`, `Mask` | `Rivers`, `Flow`, `Depth`, `Wear`, `Surface`, `Direction` |
| Sea / Lake | `In` | `Water`, `Beach`, `Depth`, `Shore` (+`Surface` on Sea) |
| Export / Unity / Unreal | `In` | no `Out` |

`list_gaea2_nodes {"node_type": "..."}` shows the exact table. Declare other ports via the
node's `ports` field. Each input port accepts one connection; merge with Combine.

## Validation cheat sheet

| Problem | Result |
|---------|--------|
| `erosion2`, `Erosoin2`, `erosion_2` | fixed to `Erosion2` |
| `"erosion scale": "6000"` | renamed `ErosionScale`, converted to number |
| `Duration: 50` on Erosion2 | clamped to 2.0 |
| Connection to missing node / self / duplicate | removed |
| Unknown port, two inputs into one port, cycle, duplicate id | **error** |
| Unknown property name | warning (Gaea2 ignores it) |
| No Export, unconnected node | warning (error with `strict_mode`) |

## Optimization modes

| Mode | Effect | Suggested resolution |
|------|--------|----------------------|
| `performance` | lowers Erosion2/Erosion/Snow durations, Thermal/FlowMap iterations above preview targets | 1024 |
| `balanced` | only fills unset cost properties with typical values | 2048 |
| `quality` | raises those values below final-render targets | 4096 |

## Build config

`{"resolution": 2048, "bake_resolution": 2048, "tile_resolution": 1024, "number_of_tiles": 3,
"edge_blending": 0.25, "build_type": "Standard", "color_space": "sRGB"}` - resolutions must be
powers of two from 256 to 16384.
