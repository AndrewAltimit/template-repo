# Gaea2 Extended Node Properties Documentation

## Overview
This document provides comprehensive property documentation for Gaea2 nodes based on real-world project analysis. It includes properties not found in official documentation but observed in production terrain files.

## Core Node Properties

### Common Properties (Found on Most Nodes)

```typescript
interface BaseNodeProperties {
  // Position and Identity
  Id: number;                    // Unique node identifier (non-sequential)
  Name: string;                  // Display name
  Position: {
    X: number;                   // Canvas X coordinate
    Y: number;                   // Canvas Y coordinate
  };

  // Visual Properties
  NodeSize?: "Small" | "Standard" | "Compact";
  IsLocked?: boolean;            // Prevents modification
  RenderIntentOverride?: "Color" | "Height";

  // Port Configuration
  IsMaskable?: boolean;          // Can accept mask inputs
  PortCount?: number;            // For dynamic port nodes

  // Export Configuration
  SaveDefinition?: {
    Node: number;
    Filename: string;
    Format: "EXR" | "PNG" | "TIF";
    IsEnabled: boolean;
  };

  // Modifiers
  Modifiers?: {
    $values: Array<{
      $type: string;
      Name: string;
      Parent: { $ref: string };
      Intrinsic: boolean;
    }>;
  };
}
```

## Node-Specific Properties

### Mountain
```typescript
interface MountainProperties extends BaseNodeProperties {
  Scale: number;              // 0.1-10.0 (default: 1.0)
  Height: number;             // 0.0-1.0 (default: 0.7)
  Style: "Basic" | "Eroded" | "Old" | "Alpine" | "Strata";
  Bulk: "Low" | "Medium" | "High";
  "Reduce Details": boolean;
  Seed: number;               // 0-999999
  X: number;                  // -1000.0 to 1000.0
  Y: number;                  // -1000.0 to 1000.0
}
```

### Volcano
```typescript
interface VolcanoProperties extends BaseNodeProperties {
  Scale: number;              // 0.1-5.0 (default: 1.0)
  Height: number;             // 0.0-1.0 (default: 0.8)
  Mouth: number;              // 0.0-1.0 (default: 0.3)
  Bulk: number;               // -1.0 to 1.0
  Surface: "Smooth" | "Eroded";
  X: number;
  Y: number;
  Seed: number;
}
```

### MountainSide
```typescript
interface MountainSideProperties extends BaseNodeProperties {
  Detail: number;             // 0.0-1.0 (default: 0.25)
  Style: "Smooth" | "Eroded" | "Rocky";
  Seed: number;
}
```

### Rivers
```typescript
interface RiversProperties extends BaseNodeProperties {
  Water: number;              // 0.0-1.0
  Width: number;              // 0.0-1.0
  Depth: number;              // 0.0-1.0
  Downcutting: number;        // 0.0-1.0
  RiverValleyWidth: "zero" | "plus2" | "plus4";
  Headwaters: number;         // 1-1000
  RenderSurface: boolean;
  Seed: number;

  // Special port configuration
  Ports: {
    Out: Port;                // Primary terrain output
    Rivers: Port;             // River mask output
    Depth: Port;              // Depth map output
    Surface: Port;            // Surface detail output
    Direction: Port;          // Flow direction output
  };
}
```

### Sea
```typescript
interface SeaProperties extends BaseNodeProperties {
  Level: number;              // 0.0-1.0
  CoastalErosion: boolean;
  ShoreSize: number;          // 0.0-1.0
  ShoreHeight: number;        // 0.0-1.0
  Variation: number;          // 0.0-1.0
  UniformVariations: boolean;
  ExtraCliffDetails: boolean;
  RenderSurface: boolean;

  // Special port configuration
  Ports: {
    Out: Port;
    Water: Port;              // Water mask
    Shore: Port;              // Shoreline mask
    Depth: Port;              // Water depth
    Surface: Port;            // Surface detail
  };
}
```

### Erosion2
```typescript
interface Erosion2Properties extends BaseNodeProperties {
  Duration: number;                        // 0.0-20.0
  Downcutting: number;                     // 0.0-1.0
  ErosionScale: number;                    // 10.0-100000.0
  Seed: number;

  // Sediment Properties
  SuspendedLoadDischargeAmount: number;   // 0.0-1.0
  SuspendedLoadDischargeAngle: number;    // 0.0-90.0
  BedLoadDischargeAmount: number;          // 0.0-1.0
  BedLoadDischargeAngle: number;           // 0.0-90.0
  CoarseSedimentsDischargeAmount: number; // 0.0-1.0
  CoarseSedimentsDischargeAngle: number;  // 0.0-90.0

  // Shape Properties
  Shape: number;                           // 0.0-1.0
  ShapeSharpness: number;                  // 0.0-1.0
  ShapeDetailScale: number;                // 0.0-1.0

  // Output Ports
  Ports: {
    Out: Port;
    Flow: Port;
    Wear: Port;
    Deposits: Port;
  };
}
```

### Combine
```typescript
interface CombineProperties extends BaseNodeProperties {
  PortCount: number;          // 2-6 (dynamic)
  Ratio: number;              // 0.0-1.0
  Mode?: "Default" | "Add" | "Subtract" | "Multiply";
  Clamp: "None" | "Clamp" | "Normalize";

  // Critical for color operations
  RenderIntentOverride?: "Color";

  // Dynamic ports
  Ports: {
    In: Port;                 // Primary input
    Out: Port;
    Input2: Port;             // Secondary input
    Input3?: Port;            // Optional additional inputs
    Input4?: Port;
    Mask: Port[];             // Can have multiple mask ports
  };
}
```

### TextureBase
```typescript
interface TextureBaseProperties extends BaseNodeProperties {
  Slope: number;              // 0.0-1.0
  Scale: number;              // 0.0-1.0
  Soil: number;               // 0.0-1.0
  Patches: number;            // 0.0-1.0
  Chaos: number;              // 0.0-1.0
  Seed: number;
}
```

### SatMap
```typescript
interface SatMapProperties extends BaseNodeProperties {
  Library: "Rock" | "Green" | "Blue" | "Sand" | "Color";
  LibraryItem: number;        // Texture index within library
  Range?: {
    $id: string;
    X: number;                // Min value
    Y: number;                // Max value
  };
  Bias?: number;              // -1.0 to 1.0
  Enhance: "None" | "Autolevel" | "Equalize";
  Reverse: boolean;
}
```

### Height
```typescript
interface HeightProperties extends BaseNodeProperties {
  Range: {
    $id: string;              // Important: Must have $id
    X: number;                // Min height (0.0-1.0)
    Y: number;                // Max height (0.0-1.0)
  };
  Falloff: number;            // 0.0-1.0
}
```

### Adjust
```typescript
interface AdjustProperties extends BaseNodeProperties {
  Multiply: number;           // 0.0-10.0
  Add?: number;               // -1.0 to 1.0
  Shaper?: number;            // 0.0-1.0
  Clamp?: {
    X: number;                // Min
    Y: number;                // Max
  };
  Equalize: boolean;
  Invert?: boolean;
}
```

### FractalTerraces
```typescript
interface FractalTerracesProperties extends BaseNodeProperties {
  Spacing: number;            // 0.0-1.0
  Octaves: number;            // 1-16
  Intensity: number;          // 0.0-1.0
  Seed: number;
  MacroOctaves: number;       // 1-8
  StrataDetails: number;      // 0.0-1.0
  TiltAmount: number;         // 0.0-1.0
  TiltSeed: number;
  WarpAmount: number;         // 0.0-1.0
  WarpSize: number;           // 0.0-1.0

  // Output Ports
  Ports: {
    Out: Port;
    Layers: Port;             // Layer mask output
  };
}
```

### Weathering
```typescript
interface WeatheringProperties extends BaseNodeProperties {
  Scale: number;              // 0.0-1.0
  Creep: number;              // 0.0-1.0
  Dirt: number;               // 0.0-1.0
}
```

### Terraces
```typescript
interface TerracesProperties extends BaseNodeProperties {
  NumTerraces: number;        // 1-500
  Uniformity: number;         // 0.0-1.0
  Steepness: number;          // 0.0-1.0
  Intensity: number;          // 0.0-1.0
  Seed: number;
}
```

### Crumble
```typescript
interface CrumbleProperties extends BaseNodeProperties {
  Duration: number;           // 0.0-1.0
  Strength: number;           // 0.0-1.0
  Coverage: number;           // 0.0-1.0
  Horizontal: number;         // 0.0-1.0
  RockHardness: number;       // 0.0-1.0
  Edge: number;               // 0.0-1.0
  Depth: number;              // 0.0-1.0

  // Output Ports
  Ports: {
    Out: Port;
    Wear: Port;               // Wear mask output
  };
}
```

### Island
```typescript
interface IslandProperties extends BaseNodeProperties {
  Size: number;               // 0.0-1.0
  Chaos?: number;             // 0.0-1.0
  Seed: number;
}
```

### Slump
```typescript
interface SlumpProperties extends BaseNodeProperties {
  Scale: number;              // 0.0-1.0
  Seed: number;
}
```

### Blur
```typescript
interface BlurProperties extends BaseNodeProperties {
  Radius: number;             // 0.0-1.0
}
```

### Shear
```typescript
interface ShearProperties extends BaseNodeProperties {
  Strength: number;           // 0.0-1.0
  Seed: number;
}
```

### Stratify
```typescript
interface StratifyProperties extends BaseNodeProperties {
  Spacing: number;            // 0.0-1.0
  Octaves: number;            // 1-16
  Intensity: number;          // 0.0-1.0
  Seed: number;
  TiltAmount?: number;        // 0.0-1.0

  // Output Ports
  Ports: {
    Out: Port;
    Layers: Port;             // Stratification layers
  };
}
```

### Dusting
```typescript
interface DustingProperties extends BaseNodeProperties {
  Snowline: number;           // 0.0-1.0
  Falloff: number;            // 0.0-1.0
  Coverage: number;           // 0.0-1.0
  Flow: number;               // 0.0-1.0
  Melt: number;               // 0.0-1.0
  Gritty: boolean;
  Seed: number;
}
```

### Perlin
```typescript
interface PerlinProperties extends BaseNodeProperties {
  Type: "Default" | "Ridged" | "Billowy";
  Scale: number;              // 0.0-1.0
  Octaves: number;            // 1-10
  Gain: number;               // 0.0-1.0
  Clamp: number;              // 0.0-1.0
  Seed: number;

  // Warp Properties
  WarpType: "None" | "Simple" | "Complex";
  Frequency: number;          // 0.0-1.0
  Amplitude: number;          // 0.0-1.0
  WarpOctaves: number;        // 1-10

  // Scale Properties
  ScaleX: number;             // 0.1-10.0
  ScaleY: number;             // 0.1-10.0
  X: number;                  // Position
  Y: number;                  // Position
}
```

## Port System Details

### Port Types
```typescript
enum PortType {
  "PrimaryIn, Required",      // Must be connected
  "PrimaryIn",                // Optional primary input
  "PrimaryOut",               // Main output
  "In",                       // Secondary input
  "Out",                      // Secondary output
}
```

### Port Structure
```typescript
interface Port {
  Name: string;
  Type: PortType;
  IsExporting: boolean;
  Parent: { $ref: string };   // Reference to parent node

  // Connection information (when connected)
  Record?: {
    From: number;             // Source node ID
    To: number;               // Target node ID
    FromPort: string;         // Source port name
    ToPort: string;           // Target port name
    IsValid: boolean;
  };
}
```

## Special Properties

### Variables Object
Used for automation and synchronization:
```typescript
interface Variables {
  [key: string]: string | number;
}

// Example:
{
  "949_Seed": "58",
  "GlobalScale": 1.0
}
```

### Bindings Array
Links node properties to variables:
```typescript
interface Binding {
  Node: number;               // Node ID
  Property: string;           // Property name
  Variable: string;           // Variable name
}
```

### Graph Tabs
UI state for different views:
```typescript
interface GraphTab {
  Name: string;
  Color: "Brass" | "Steel" | "Copper";
  ZoomFactor: number;
  ViewportLocation: {
    X: number;
    Y: number;
  };
}
```

## Property Name Formatting Rules

**Critical**: Property names in terrain files use spaces, not camelCase:

| Code Property | Terrain File Property |
|---------------|----------------------|
| RockSoftness | "Rock Softness" |
| ReduceDetails | "Reduce Details" |
| CoastalErosion | "Coastal Erosion" |
| ExtraCliffDetails | "Extra Cliff Details" |

## Default Values Summary

Common defaults across nodes:
- Seed: 0 (but usually randomized)
- Scale: 1.0
- Intensity: 0.5
- Falloff: 0.2
- Ratio: 0.5
- NodeSize: "Standard"
- IsMaskable: true
