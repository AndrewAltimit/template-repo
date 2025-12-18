# Gaea2 Template Reference

> Auto-generated from YAML schema. Do not edit manually.
> Generated: 2025-12-18 15:07:28 UTC

## Overview

Total templates: **11**

## Templates by Category

### Advanced

Advanced templates using complex techniques

- **modular_portal_terrain** (advanced) - Advanced modular workflow using portals for node reuse [10 nodes]

### Arctic

Cold climate terrains with ice and snow

- **arctic_terrain** (intermediate) - Arctic terrain with glaciers, snow cover, and glacial lakes [8 nodes]

### Canyon

Canyon and gorge terrains

- **desert_canyon** (intermediate) - Layered canyon with terraces and sand accumulation [7 nodes]
- **canyon_system** (advanced) - Complex canyon system with rock layers and sediments [8 nodes]

### Coastal

Coastal and ocean-adjacent terrains

- **coastal_cliffs** (intermediate) - Coastal terrain with sea level, cliffs, terraces, and beaches [8 nodes]

### General

General purpose terrain templates

- **basic_terrain** (beginner) - Simple terrain with erosion and basic texturing [5 nodes]

### Mountain

Mountain and peak terrains

- **detailed_mountain** (intermediate) - Multi-peak mountain with rivers, snow, and detailed erosion [8 nodes]
- **mountain_range** (intermediate) - Extended mountain range with ridge detail and snow [7 nodes]

### River

River and valley terrains

- **river_valley** (intermediate) - River valley with terraces, floodplain, and vegetation colors [7 nodes]

### Volcanic

Volcanic terrains with lava features

- **volcanic_terrain** (intermediate) - Volcanic island with lava erosion and thermal weathering [7 nodes]
- **volcanic_island** (advanced) - Island with central volcano, lava flows, and beaches [8 nodes]

## Template Details

### Arctic Terrain

Arctic terrain with glaciers, snow cover, and glacial lakes

- **Category:** arctic
- **Difficulty:** intermediate

**Nodes:**

| # | Type | Name | Key Properties |
|---|------|------|----------------|
| 1 | Mountain | ArcticMountains | Scale=1.5, Height=0.7, Style=Old |
| 2 | Glacier | IceFlow | Scale=2.0, Depth=0.6, Flow=0.4 |
| 3 | Combine | GlacialCarving | Mode=Subtract, Ratio=0.4 |
| 4 | Snow | SnowCover | Duration=0.9, SnowLine=0.1, Melt=0.05 |
| 5 | Thermal | FrostShatter | Strength=0.6, Iterations=30, Angle=32.0 |
| 6 | Export | ArcticHeightmap | - |
| 7 | Lake | GlacialLakes | - |
| 8 | SatMap | ArcticColors | Library=Snow, Enhance=Autolevel |

---

### Basic Terrain

Simple terrain with erosion and basic texturing

- **Category:** general
- **Difficulty:** beginner

**Nodes:**

| # | Type | Name | Key Properties |
|---|------|------|----------------|
| 1 | Mountain | BaseTerrain | Scale=1.0, Height=0.7, Style=Alpine |
| 2 | Erosion2 | NaturalErosion | Duration=0.15, Downcutting=0.3, ErosionScale=5000.0 |
| 3 | Export | HeightmapExport | - |
| 4 | TextureBase | BaseTexture | - |
| 5 | SatMap | ColorMap | Library=Rock, LibraryItem=0 |

---

### Canyon System

Complex canyon system with rock layers and sediments

- **Category:** canyon
- **Difficulty:** advanced

**Nodes:**

| # | Type | Name | Key Properties |
|---|------|------|----------------|
| 1 | Strata | RockLayers | Scale=1.5, Layers=12, Variation=0.3 |
| 2 | Voronoi | CanyonPattern | Scale=0.8, Jitter=0.7, Style=Euclidean |
| 3 | Combine | CarveCanyons | Mode=Subtract, Ratio=0.6 |
| 4 | Erosion2 | RiverErosion | Duration=0.15, Downcutting=0.5, ErosionScale=6000.0 |
| 5 | Thermal | RockfallErosion | Strength=0.3, Iterations=20, Angle=38.0 |
| 6 | Sediments | ValleyFill | Deposition=0.4, Sediments=0.2, Seed=24680 |
| 7 | Export | CanyonSystemHeightmap | - |
| 8 | SatMap | CanyonColors | Library=Desert, Enhance=Equalize |

---

### Coastal Cliffs

Coastal terrain with sea level, cliffs, terraces, and beaches

- **Category:** coastal
- **Difficulty:** intermediate

**Nodes:**

| # | Type | Name | Key Properties |
|---|------|------|----------------|
| 1 | Mountain | CoastalTerrain | Scale=1.0, Height=0.6, Style=Eroded |
| 2 | SeaLevel | OceanLevel | Level=0.0, Precision=0.95 |
| 3 | Coast | Coastline | Erosion=0.7, Detail=0.8 |
| 4 | Terrace | CliffTerraces | Levels=5, Uniformity=0.2, Sharp=0.8 |
| 5 | Beach | SandyBeaches | Width=200.0, Slope=0.1 |
| 6 | Erosion2 | CoastalErosion | Duration=0.15, Downcutting=0.1, ErosionScale=5000.0 |
| 7 | Export | CoastalHeightmap | - |
| 8 | SatMap | CoastalColors | Library=Blue, LibraryItem=4, Reverse=True |

---

### Desert Canyon

Layered canyon with terraces and sand accumulation

- **Category:** canyon
- **Difficulty:** intermediate

**Nodes:**

| # | Type | Name | Key Properties |
|---|------|------|----------------|
| 1 | Canyon | MainCanyon | Scale=1.5, Depth=0.7 |
| 2 | Stratify | RockLayers | Layers=12, Strength=0.6 |
| 3 | FractalTerraces | TerraceFormation | Intensity=0.5, Spacing=0.2, Octaves=12 |
| 4 | Erosion2 | WindErosion | Duration=0.1, Downcutting=0.2, ErosionScale=3000.0 |
| 5 | Sand | SandAccumulation | Amount=0.4, Scale=0.5 |
| 6 | Export | CanyonHeightmap | - |
| 7 | SatMap | DesertColors | Library=Sand, LibraryItem=0 |

---

### Detailed Mountain

Multi-peak mountain with rivers, snow, and detailed erosion

- **Category:** mountain
- **Difficulty:** intermediate

**Nodes:**

| # | Type | Name | Key Properties |
|---|------|------|----------------|
| 1 | Mountain | PrimaryMountain | Scale=1.5, Height=0.85, Style=Alpine |
| 2 | Mountain | SecondaryPeaks | Scale=0.8, Height=0.6, Style=Eroded |
| 3 | Combine | MergePeaks | Mode=Max, Ratio=0.7 |
| 4 | Erosion2 | InitialErosion | Duration=0.15, Downcutting=0.35, ErosionScale=6000.0 |
| 5 | Rivers | MountainStreams | Water=0.3, Width=0.5, Depth=0.4 |
| 6 | Export | MountainHeightmap | - |
| 7 | Snow | SnowCaps | Duration=0.6, SnowLine=0.75 |
| 8 | SatMap | RealisticColors | Library=Rock, Enhance=Autolevel |

---

### Modular Portal Terrain

Advanced modular workflow using portals for node reuse

- **Category:** advanced
- **Difficulty:** advanced

**Nodes:**

| # | Type | Name | Key Properties |
|---|------|------|----------------|
| 1 | Mountain | PrimaryShape | Scale=1.2, Height=0.8, Style=Alpine |
| 2 | PortalTransmit | ShapePortal | PortalName=Primary_Shape |
| 3 | PortalReceive | ShapeForErosion | PortalName=Primary_Shape |
| 4 | Erosion2 | DetailedErosion | Duration=0.2, Downcutting=0.4, ErosionScale=8000.0 |
| 5 | PortalTransmit | ErodedPortal | PortalName=Eroded_Terrain |
| 6 | PortalReceive | ShapeForAnalysis | PortalName=Primary_Shape |
| 7 | Slope | SlopeAnalysis | - |
| 8 | PortalReceive | FinalTerrain | PortalName=Eroded_Terrain |
| 9 | Export | PortalTerrainHeightmap | - |
| 10 | SatMap | TerrainColors | Library=Rock, LibraryItem=2 |

---

### Mountain Range

Extended mountain range with ridge detail and snow

- **Category:** mountain
- **Difficulty:** intermediate

**Nodes:**

| # | Type | Name | Key Properties |
|---|------|------|----------------|
| 1 | Mountain | MainRange | Scale=2.0, Height=0.9, Style=Alpine |
| 2 | Ridge | RidgeDetail | Scale=0.5, Complexity=0.7 |
| 3 | Combine | MergeRidge | Mode=Add, Ratio=0.3 |
| 4 | Erosion2 | AdvancedErosion | Duration=0.15, Downcutting=0.3, ErosionScale=7000.0 |
| 5 | Export | RangeHeightmap | - |
| 6 | Snow | SnowLine | Duration=0.7, SnowLine=0.7, Melt=0.2 |
| 7 | SatMap | MountainColors | Library=Rock, LibraryItem=1, Enhance=Autolevel |

---

### River Valley

River valley with terraces, floodplain, and vegetation colors

- **Category:** river
- **Difficulty:** intermediate

**Nodes:**

| # | Type | Name | Key Properties |
|---|------|------|----------------|
| 1 | Mountain | ValleyBase | Scale=1.2, Height=0.5, Style=Basic |
| 2 | Rivers | MainRiver | Width=0.4, Depth=0.6, Downcutting=0.3 |
| 3 | Sediments | Floodplain | Deposition=0.5, Sediments=0.3, Seed=67890 |
| 4 | FractalTerraces | RiverTerraces | Intensity=0.5, Spacing=0.25, Octaves=12 |
| 5 | Erosion2 | ValleyErosion | Duration=0.15, Downcutting=0.3, ErosionScale=5000.0 |
| 6 | Export | ValleyHeightmap | - |
| 7 | SatMap | ValleyColors | Library=Green, LibraryItem=2, Enhance=Autolevel |

---

### Volcanic Island

Island with central volcano, lava flows, and beaches

- **Category:** volcanic
- **Difficulty:** advanced

**Nodes:**

| # | Type | Name | Key Properties |
|---|------|------|----------------|
| 1 | Island | BaseIsland | Size=0.8, Height=0.5, Beaches=0.7 |
| 2 | Volcano | CentralVolcano | Scale=0.6, Height=1.0, Mouth=0.35 |
| 3 | Combine | MergeVolcano | Mode=Max, Ratio=0.9 |
| 4 | LavaFlow | LavaChannels | Temperature=1200.0, Viscosity=0.6 |
| 5 | ThermalShatter | ThermalBreakdown | Intensity=0.7, Scale=0.4 |
| 6 | Export | IslandHeightmap | - |
| 7 | Beach | CoastalBeaches | Width=150.0, Slope=0.15 |
| 8 | SatMap | VolcanicColors | Library=Rock, LibraryItem=3, Bias=0.2 |

---

### Volcanic Terrain

Volcanic island with lava erosion and thermal weathering

- **Category:** volcanic
- **Difficulty:** intermediate

**Nodes:**

| # | Type | Name | Key Properties |
|---|------|------|----------------|
| 1 | Volcano | MainVolcano | Scale=1.2, Height=0.8, Mouth=0.3 |
| 2 | Island | VolcanicIsland | Size=0.5, Chaos=0.3, Seed=12345 |
| 3 | Combine | MergeVolcano | Mode=Add, Ratio=0.8 |
| 4 | Erosion2 | LavaErosion | Duration=0.15, Downcutting=0.4, ErosionScale=4000.0 |
| 5 | Thermal | ThermalWeathering | Strength=0.5, Angle=35.0 |
| 6 | Export | VolcanoHeightmap | - |
| 7 | SatMap | VolcanicColors | Library=Rock, LibraryItem=1 |

---
