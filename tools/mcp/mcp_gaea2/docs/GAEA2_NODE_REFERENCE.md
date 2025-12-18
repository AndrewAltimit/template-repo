# Gaea2 Node Reference

> Auto-generated from YAML schema. Do not edit manually.
> Generated: 2025-12-18 15:07:28 UTC

## Table of Contents

- [Colorize](#colorize)
- [Derive](#derive)
- [Modify](#modify)
- [Output](#output)
- [Primitive](#primitive)
- [Simulate](#simulate)
- [Surface](#surface)
- [Terrain](#terrain)
- [Utility](#utility)
- [Common Properties](#common-properties)
- [Port Types](#port-types)

## Overview

Total nodes: **187**

| Category | Count | Description |
|----------|-------|-------------|
| Colorize | 13 | Color map generation nodes |
| Derive | 13 | Data derivation and analysis nodes |
| Modify | 41 | Height field modification nodes |
| Output | 13 | Export and output nodes |
| Primitive | 24 | Basic noise and shape generators |
| Simulate | 25 | Physical simulation nodes (erosion, etc.) |
| Surface | 21 | Surface detail and texture nodes |
| Terrain | 14 | Natural terrain feature generators |
| Utility | 23 | Utility and helper nodes |

## Colorize

<a name="colorize"></a>

### CLUTer

Color lookup table mapping

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (color)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Preset | enum | Default | Default, Warm, Cool, Earth, Custom |

---

### ColorErosion

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Gamma

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### HSL

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### RGBMerge

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### RGBSplit

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### SatMap

Satellite-style color mapping

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (color)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Bias | float | 0.5 | 0.0 - 1.0 |
| Enhance | enum | None | None, Autolevel, Equalize |
| Hue | float | 0.0 | -1.0 - 1.0 |
| Library | enum | Rock | New, Rock, Sand, Green, Blue... |
| LibraryItem | int | 0 | 0 - 50 |
| Lightness | float | 0.0 | -1.0 - 1.0 |
| Randomize | bool | False | - |
| Reverse | bool | False | - |
| Saturation | float | 0.0 | -1.0 - 1.0 |

---

### Splat

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### SuperColor

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Synth

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Tint

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### WaterColor

Water coloring based on depth

**Ports:**

*Inputs:*
- `In` (heightfield)
- `Water` (mask)

*Outputs:*
- `Out` (color)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| DeepColor | color | #1A365D | - |
| Depth | float | 0.5 | 0.0 - 1.0 |
| ShallowColor | color | #4A90D9 | - |

---

### Weathering

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

## Derive

<a name="derive"></a>

### Angle

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Curvature

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### FlowMap

Water flow direction map

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (mask)
- `Flow` (mask)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Iterations | int | 100 | 10 - 500 |

---

### FlowMapClassic

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Height

Height-based mask

**Ports:**

*Inputs:*
- `In` (heightfield)
- `Mask` (mask) (optional)

*Outputs:*
- `Out` (mask)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| High | float | 1.0 | 0.0 - 1.0 |
| Low | float | 0.0 | 0.0 - 1.0 |

---

### Normals

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Occlusion

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Peaks

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### RockMap

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Slope

Slope-based mask

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (mask)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| MaxAngle | float | 90.0 | 0.0 - 90.0 |
| MinAngle | float | 0.0 | 0.0 - 90.0 |

---

### Soil

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### TextureBase

Base texture extraction

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Texturizer

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

## Modify

<a name="modify"></a>

### Adjust

Height adjustment

**Ports:**

*Inputs:*
- `In` (heightfield)
- `Mask` (mask) (optional)

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Brightness | float | 0.0 | -1.0 - 1.0 |
| Contrast | float | 0.0 | -1.0 - 1.0 |

---

### Aperture

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Autolevel

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### BlobRemover

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Blur

Gaussian blur

**Ports:**

*Inputs:*
- `In` (heightfield)
- `Mask` (mask) (optional)

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Amount | float | 0.5 | 0.0 - 1.0 |

---

### Clamp

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Clip

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Curve

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Deflate

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Denoise

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Dilate

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### DirectionalWarp

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Distance

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Equalize

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Extend

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Filter

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Flip

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Fold

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### GraphicEQ

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Heal

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Match

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Median

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Meshify

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Origami

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Pixelate

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Recurve

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Shaper

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Sharpen

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### SlopeBlur

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### SlopeWarp

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### SoftClip

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Swirl

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### ThermalShaper

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Threshold

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Transform

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Transform3D

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Transpose

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### TriplanarDisplacement

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### VariableBlur

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Warp

Displacement warp

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Scale | float | 1.0 | 0.1 - 10.0 |
| Seed | int | 0 | 0 - 999999 |
| Strength | float | 0.5 | 0.0 - 1.0 |

---

### Whorl

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

## Output

<a name="output"></a>

### AO

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Cartography

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Export

Export heightfield to file

**Ports:**

*Inputs:*
- `In` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Filename | string | export | - |
| Format | enum | PNG16 | PNG8, PNG16, PNG64, EXR, RAW16... |

---

### Halftone

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### LightX

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Mesher

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### PointCloud

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Shade

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Sunlight

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### TextureBaker

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Unity

Export for Unity engine

**Ports:**

*Inputs:*
- `In` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Format | enum | RAW16 | RAW16, RAW32 |

---

### Unreal

Export for Unreal Engine

**Ports:**

*Inputs:*
- `In` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Format | enum | PNG16 | PNG16, RAW16 |

---

### VFX

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

## Primitive

<a name="primitive"></a>

### Cellular

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Cellular3D

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Cone

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Constant

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Cracks

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### CutNoise

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### DotNoise

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Draw

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### DriftNoise

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### File

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Gabor

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Hemisphere

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### LineNoise

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### LinearGradient

Linear gradient generator

**Ports:**

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Angle | float | 0.0 | 0.0 - 360.0 |

---

### MultiFractal

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Noise

Generic noise generator

**Ports:**

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Scale | float | 1.0 | 0.1 - 10.0 |
| Seed | int | 0 | 0 - 999999 |
| Type | enum | Perlin | Perlin, Simplex, Value, Worley |

---

### Object

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Pattern

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Perlin

Perlin noise generator

**Ports:**

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Octaves | int | 8 | 1 - 16 |
| Persistence | float | 0.5 | 0.0 - 1.0 |
| Scale | float | 1.0 | 0.1 - 10.0 |
| Seed | int | 0 | 0 - 999999 |

---

### RadialGradient

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Shape

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### TileInput

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Voronoi

Voronoi noise generator

**Ports:**

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Jitter | float | 1.0 | 0.0 - 1.0 |
| Scale | float | 1.0 | 0.1 - 10.0 |
| Seed | int | 0 | 0 - 999999 |

---

### WaveShine

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

## Simulate

<a name="simulate"></a>

### Anastomosis

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Crumble

Rock crumbling effect

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Intensity | float | 0.5 | 0.0 - 1.0 |
| Seed | int | 0 | 0 - 999999 |
| Size | float | 0.5 | 0.0 - 1.0 |

---

### Debris

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Dusting

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### EasyErosion

Simplified erosion with presets

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Influence | float | 0.5 | 0.0 - 1.0 |
| Style | enum | Alpine | Alpine, Fluvial, Coastal, Glacial, Desert |

---

### Erosion

Classic erosion simulation

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)
- `Flow` (mask)
- `Wear` (mask)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Downcutting | float | 0.0 | 0.0 - 1.0 |
| Duration | float | 0.04 | 0.0 - 20.0 |
| FeatureScale | int | 2000 | 50 - 10000 |
| RockSoftness | float | 0.4 | 0.0 - 1.0 |
| Seed | int | 0 | 0 - 999999 |
| Strength | float | 0.5 | 0.0 - 2.0 |

---

### Erosion2

Advanced hydraulic erosion simulation

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)
- `Flow` (mask)
- `Wear` (mask)
- `Deposits` (mask)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Downcutting | float | 0.3 | 0.0 - 1.0 |
| Duration | float | 0.15 | 0.01 - 2.0 |
| ErosionScale | float | 5000.0 | 1000.0 - 20000.0 |
| Seed | int | 0 | 0 - 999999 |
| Shape | float | 0.5 | 0.0 - 1.0 |
| ShapeDetailScale | float | 0.5 | 0.0 - 1.0 |
| ShapeSharpness | float | 0.5 | 0.0 - 1.0 |

---

### Glacier

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Hillify

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### HydroFix

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### IceFloe

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Lake

Lake formation simulation

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)
- `Water` (mask)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| AltitudeBias | float | 0.0 | -1.0 - 1.0 |
| Precipitation | float | 10.0 | 0.0 - 100.0 |
| ShoreSize | float | 0.15 | 0.0 - 1.0 |
| SmallLakes | float | 0.2 | 0.0 - 1.0 |

---

### Lichtenberg

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Rivers

River network simulation

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)
- `Rivers` (mask)
- `Flow` (mask)
- `Depth` (mask)
- `Wear` (mask)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Depth | float | 0.5 | 0.0 - 1.0 |
| Downcutting | float | 0.0 | 0.0 - 1.0 |
| Headwaters | int | 100 | 10 - 1000 |
| RenderSurface | bool | False | - |
| Seed | int | 0 | 0 - 999999 |
| Water | float | 0.3 | 0.0 - 1.0 |
| Width | float | 0.5 | 0.0 - 1.0 |

---

### Scree

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Sea

Ocean/sea level simulation

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)
- `Water` (mask)
- `Beach` (mask)
- `Depth` (mask)
- `Shore` (mask)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| BeachSize | float | 0.1 | 0.0 - 1.0 |
| Level | float | 0.2 | 0.0 - 1.0 |

---

### Sediments

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Shrubs

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Snow

Snow accumulation simulation

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)
- `Snow` (mask)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Duration | float | 0.5 | 0.0 - 1.0 |
| Intensity | float | 0.5 | 0.0 - 1.0 |
| Melt | float | 0.0 | 0.0 - 1.0 |
| MeltType | enum | Uniform | Uniform, Directional |
| SettleDuration | float | 0.5 | 0.0 - 1.0 |
| SlipOffAngle | float | 35.0 | 0.0 - 90.0 |
| SnowLine | float | 0.7 | 0.0 - 1.0 |

---

### Snowfield

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Thermal

Thermal erosion simulation

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)
- `Talus` (mask)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Angle | float | 35.0 | 0.0 - 90.0 |
| Intensity | float | 0.5 | 0.0 - 1.0 |
| Iterations | int | 15 | 1 - 50 |
| Strength | float | 0.4 | 0.0 - 1.0 |

---

### Thermal2

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Trees

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Wizard

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Wizard2

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

## Surface

<a name="surface"></a>

### Bomber

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Bulbous

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Contours

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Craggy

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Distress

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### FractalTerraces

Fractal terrace formations

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Intensity | float | 0.5 | 0.0 - 1.0 |
| MacroOctaves | int | 5 | 1 - 8 |
| Octaves | int | 12 | 1 - 16 |
| Seed | int | 0 | 0 - 999999 |
| Spacing | float | 0.2 | 0.1 - 0.4 |
| StrataDetails | float | 0.6 | 0.0 - 1.0 |
| WarpAmount | float | 0.33 | 0.0 - 1.0 |

---

### Grid

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### GroundTexture

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Outcrops

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Pockmarks

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### RockNoise

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Rockscape

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Roughen

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Sand

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Sandstone

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)
- `Layers` (mask) - Layer stratification

---

### Shatter

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Shear

Shearing deformation

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Angle | float | 45.0 | 0.0 - 360.0 |
| Intensity | float | 0.5 | 0.0 - 1.0 |

---

### Steps

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Stones

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Stratify

Stratification layers

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Layers | int | 12 | 2 - 50 |
| Spacing | float | 0.5 | 0.0 - 1.0 |
| Strength | float | 0.6 | 0.0 - 1.0 |

---

### Terraces

Simple terrace formations

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| NumTerraces | int | 10 | 2 - 256 |
| Seed | int | 0 | 0 - 999999 |
| Steepness | float | 0.5 | 0.0 - 1.0 |
| Uniformity | float | 0.5 | 0.0 - 1.0 |

---

## Terrain

<a name="terrain"></a>

### Canyon

Creates canyon formations

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)
- `Depth` (mask)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Depth | float | 0.5 | 0.0 - 1.0 |
| Seed | int | 0 | 0 - 999999 |
| Width | float | 0.3 | 0.0 - 1.0 |

---

### Crater

Creates impact crater

**Ports:**

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Depth | float | 0.8 | 0.0 - 1.0 |
| InnerSlope | float | 0.7 | 0.0 - 1.0 |
| OuterSlope | float | 0.3 | 0.0 - 1.0 |
| Radius | float | 0.4 | 0.1 - 1.0 |

---

### CraterField

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### DuneSea

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Island

Creates an island terrain

**Ports:**

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Beaches | float | 0.8 | 0.0 - 1.0 |
| Chaos | float | 0.3 | 0.0 - 1.0 |
| Height | float | 0.7 | 0.0 - 1.0 |
| Seed | int | 0 | 0 - 999999 |
| Size | float | 0.6 | 0.1 - 1.0 |

---

### Mountain

Creates a procedural mountain terrain

**Ports:**

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Bulk | enum | Medium | Low, Medium, High |
| Height | float | 0.7 | 0.0 - 1.0 |
| ReduceDetails | bool | False | - |
| Scale | float | 1.0 | 0.1 - 5.0 |
| Seed | int | 0 | 0 - 999999 |
| Style | enum | Basic | Basic, Eroded, Old, Alpine, Strata |
| X | float | 0.0 | -1000.0 - 1000.0 |
| Y | float | 0.0 | -1000.0 - 1000.0 |

---

### MountainRange

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### MountainSide

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Plates

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Ridge

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Rugged

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Slump

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Uplift

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Volcano

Creates a volcanic cone terrain

**Ports:**

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Bulk | float | 0.5 | 0.0 - 1.0 |
| Height | float | 0.8 | 0.0 - 1.0 |
| Mouth | float | 0.3 | 0.0 - 1.0 |
| Scale | float | 1.0 | 0.1 - 5.0 |
| Seed | int | 0 | 0 - 999999 |
| Surface | enum | Smooth | Smooth, Eroded |
| X | float | 0.0 | -1000.0 - 1000.0 |
| Y | float | 0.0 | -1000.0 - 1000.0 |

---

## Utility

<a name="utility"></a>

### Accumulator

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Chokepoint

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Combine

Blend two heightfields

**Ports:**

*Inputs:*
- `In` (heightfield)
- `Input2` (heightfield)
- `Mask` (mask) (optional)

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Clamp | enum | Clamp | None, Clamp, Normalize |
| Mode | enum | Blend | Blend, Add, Screen, Subtract, Difference... |
| Ratio | float | 0.5 | 0.0 - 1.0 |

---

### Compare

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Construction

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### DataExtractor

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Edge

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Gate

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Layers

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### LoopBegin

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### LoopEnd

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Mask

Create or modify masks

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (mask)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Invert | bool | False | - |

---

### Math

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Mixer

**Ports:**

*Inputs:*
- `In` (heightfield) - Base input
- `Terrain` (heightfield) (optional)

*Outputs:*
- `Out` (heightfield)

---

### Portal

Portal connection point

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| Direction | enum | Transmit | Transmit, Receive |
| PortalName | string | Portal_1 | - |

---

### PortalReceive

Portal receiver

**Ports:**

*Outputs:*
- `Out` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| PortalName | string | Portal_1 | - |

---

### PortalTransmit

Portal transmitter

**Ports:**

*Inputs:*
- `In` (heightfield)

**Properties:**

| Property | Type | Default | Range/Options |
|----------|------|---------|---------------|
| PortalName | string | Portal_1 | - |

---

### Repeat

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Reseed

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Route

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Seamless

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Switch

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

### Var

**Ports:**

*Inputs:*
- `In` (heightfield)

*Outputs:*
- `Out` (heightfield)

---

## Common Properties

These properties are shared across multiple node types.

| Property | Type | Default | Range | Description |
|----------|------|---------|-------|-------------|
| Height | float | 0.5 | 0.0 - 1.0 | Height or intensity |
| Scale | float | 1.0 | 0.01 - 10.0 | Perceptual scale |
| Seed | int | 0 | 0 - 999999 | Randomization seed |
| Strength | float | 0.5 | 0.0 - 2.0 | Effect strength |
| X | float | 0.0 | -1000.0 - 1000.0 | X position offset |
| Y | float | 0.0 | -1000.0 - 1000.0 | Y position offset |

## Port Types

| Type | Description | Compatible With |
|------|-------------|-----------------|
| color | RGB color data | color |
| heightfield | Grayscale heightfield data (terrain elevation) | heightfield, mask |
| mask | Grayscale mask data (0-1 range) | heightfield, mask |
| vector | Vector/normal data | vector |
