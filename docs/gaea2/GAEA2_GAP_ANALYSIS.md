# Gaea2 Documentation Gap Analysis

## Overview
This document identifies gaps between our current Gaea2 MCP documentation and real-world Gaea2 project files. Based on analysis of 10 production terrain files (Level1-Level10.terrain).

## Major Gaps Identified

### 1. Missing Node Properties

#### NodeSize Property
**Current**: Not documented
**Real Projects**: Common on utility nodes
```json
"NodeSize": "Small" | "Standard" | "Compact"
```
- Affects UI representation
- Found on: Adjust, Combine, Weathering nodes

#### RenderIntentOverride Property
**Current**: Not documented
**Real Projects**: Critical for color processing
```json
"RenderIntentOverride": "Color"
```
- Found on Combine nodes used for color blending
- Essential for proper texture compositing

#### SaveDefinition Property
**Current**: Not documented
**Real Projects**: Used for export configuration
```json
"SaveDefinition": {
  "Node": 949,
  "Filename": "Rivers",
  "Format": "EXR",
  "IsEnabled": true
}
```

#### IsLocked Property
**Current**: Not documented
**Real Projects**: Prevents modification of final nodes
```json
"IsLocked": true
```

#### IsMaskable Property
**Current**: Not documented
**Real Projects**: Common on most nodes
```json
"IsMaskable": true
```

#### PortCount Property
**Current**: Not documented
**Real Projects**: Essential for Combine nodes
```json
"PortCount": 2
```

### 2. Missing Port System Details

#### Multi-Port Nodes
**Current**: Only documents "In" and "Out" ports
**Real Projects**: Complex port structures

Rivers Node Outputs:
- Out (primary terrain)
- Rivers (water mask)
- Depth (depth map)
- Surface (surface detail)
- Direction (flow direction)

Sea Node Outputs:
- Out (primary)
- Water (water mask)
- Shore (shoreline mask)
- Depth (depth map)
- Surface (surface detail)

Combine Node Inputs:
- In (primary input)
- Input2 (secondary input)
- Mask (can have multiple mask ports)

#### Port Type System
**Current**: Not documented
**Real Projects**: Critical for validation
```json
"Type": "PrimaryIn, Required" | "PrimaryIn" | "PrimaryOut" | "In" | "Out"
```

### 3. Missing Connection Storage Format

**Current**: Connections stored separately
**Real Projects**: Connections embedded in ports
```json
"Ports": {
  "$values": [{
    "Name": "In",
    "Type": "PrimaryIn, Required",
    "Record": {
      "From": 873,
      "To": 281,
      "FromPort": "Out",
      "ToPort": "In",
      "IsValid": true
    }
  }]
}
```

### 4. Missing Property Enumerations

#### Rivers - RiverValleyWidth
**Current**: Not documented
**Real Projects**:
```json
"RiverValleyWidth": "zero" | "plus2" | "plus4"
```

#### SatMap - Library Types
**Current**: Not documented
**Real Projects**:
- "Rock"
- "Green"
- "Blue"
- "Sand"
- "Color"

### 5. Missing Modifiers System

**Current**: Not documented
**Real Projects**: Intrinsic modifiers
```json
"Modifiers": {
  "$values": [{
    "$type": "QuadSpinner.Gaea.Nodes.Modifiers.Invert, Gaea.Nodes",
    "Name": "Invert",
    "Parent": {"$ref": "..."},
    "Intrinsic": true
  }]
}
```

### 6. Missing Variable Binding System

**Current**: Basic mention only
**Real Projects**: Sophisticated binding
```json
"Bindings": {
  "$values": [
    {"Node": 949, "Property": "Seed", "Variable": "949_Seed"},
    {"Node": 190, "Property": "Seed", "Variable": "949_Seed"}
  ]
},
"Variables": {
  "949_Seed": "58"
}
```

### 7. Incomplete Node Property Documentation

#### TextureBase
**Current**: Missing properties
**Real Projects**:
```json
{
  "Slope": 0.48291308,
  "Scale": 0.15,
  "Soil": 0.6,
  "Patches": 0.4,
  "Chaos": 0.1,
  "Seed": 48091
}
```

#### Height Node Range Format
**Current**: Simple range
**Real Projects**: Object with $id
```json
"Range": {
  "$id": "107",
  "X": 0.9815117,
  "Y": 1.0
}
```

### 8. Missing State Management

**Current**: Not documented
**Real Projects**:
```json
"State": {
  "BakeResolution": 2048,
  "PreviewResolution": 4096,
  "SelectedNode": 174,
  "LockedNode": 174,
  "Viewport": {
    "Camera": {...},
    "RenderMode": "Realistic",
    "SunAltitude": 33.0,
    // ... environmental settings
  }
}
```

### 9. ID Generation Pattern

**Current**: Sequential IDs suggested
**Real Projects**: Non-sequential scattered IDs
- Example: 183, 668, 427, 281, 294, 949
- No apparent pattern or correlation

### 10. Missing Workflow Templates

Several complex workflows discovered but not documented:
1. Volcano → MountainSide → Combine workflow
2. Island → Adjust(Invert) → Blur pattern
3. Multiple Terraces nodes in sequence
4. Weathering as final touch node

## Recommendations

### High Priority Updates

1. **Port System Documentation**
   - Document all multi-port nodes
   - Add port type system
   - Update connection format to use Record objects

2. **Node Properties**
   - Add NodeSize, RenderIntentOverride, IsLocked
   - Document IsMaskable and PortCount
   - Update Range format with $id

3. **Connection System**
   - Switch to embedded connection format
   - Document port type validation

### Medium Priority Updates

4. **Modifiers System**
   - Document intrinsic modifiers
   - Add Invert modifier support

5. **Variable Binding**
   - Full documentation of binding system
   - Examples of multi-node synchronization

6. **Missing Properties**
   - Complete TextureBase properties
   - Rivers RiverValleyWidth enum
   - SatMap library types

### Low Priority Updates

7. **State Management**
   - Document viewport settings
   - Add LockedNode support

8. **Workflow Templates**
   - Add discovered workflow patterns
   - Create templates for common combinations

9. **ID Generation**
   - Update to use non-sequential IDs
   - Document ID generation strategy

## Impact Assessment

### Critical for Functionality
- Port system (connections won't work without proper format)
- Connection Record objects (essential for terrain loading)
- Node properties (RenderIntentOverride, PortCount)

### Important for Compatibility
- ID generation pattern
- Property name formatting (spaces vs camelCase)
- Range object format

### Nice to Have
- State management
- Modifiers system
- Advanced workflow templates

## Next Steps

1. Update gaea2_schema.py with missing properties
2. Refactor connection system to use Record objects
3. Add comprehensive port definitions for all nodes
4. Create property validator for new enums
5. Update templates with discovered patterns
6. Document variable binding system
7. Add modifier support to node processing
