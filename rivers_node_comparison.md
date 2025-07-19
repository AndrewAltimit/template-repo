# Rivers Node Format Comparison

## What We're Generating (FAILING):
```json
"668": {
  "$id": "14",
  "$type": "QuadSpinner.Gaea.Nodes.Rivers, Gaea.Nodes",
  "Water": 0.4,
  "Width": 0.6,
  "Depth": 0.7,
  "Downcutting": 0.3,
  "RiverValleyWidth": "plus2",
  "Headwaters": 150,
  "RenderSurface": true,
  "Seed": 12345,
  "NodeSize": "Standard",
  "IsMaskable": true,
  "Id": 668,
  "Name": "River System",
  "Position": {...},
  "Ports": {...},
  "Modifiers": {...},
  "SnapIns": {...}
}

// SaveDefinitions are SEPARATE at asset level:
"SaveDefinitions": {
  "$id": "61",
  "$values": [
    {
      "$id": "59",
      "Node": 427,
      "Filename": "rivers_terrain",
      "Format": "EXR",
      "IsEnabled": true
    }
  ]
}
```

## What Reference Files Have (WORKING):

### Example 1 - Level1.terrain:
```json
"949": {
  "$id": "50",
  "$type": "QuadSpinner.Gaea.Nodes.Rivers, Gaea.Nodes",
  "Water": 0.5,
  "Width": 0.8865791,
  "Depth": 0.9246184,
  "Downcutting": 0.3400796,
  "RiverValleyWidth": "zero",
  "Headwaters": 200,
  "RenderSurface": true,
  "Seed": 21713,
  "Id": 949,
  "Name": "Rivers",
  "NodeSize": "Standard",
  "Position": {...},
  "SaveDefinition": {  // EMBEDDED IN NODE!
    "$id": "52",
    "Node": 949,
    "Filename": "Rivers",
    "Format": "EXR",
    "IsEnabled": true
  },
  "Ports": {...},
  "IsMaskable": true,
  "Modifiers": {...},
  "SnapIns": {...}
}
```

### Example 2 - tut-riverValley.terrain (minimal):
```json
"390": {
  "$id": "44",
  "$type": "QuadSpinner.Gaea.Nodes.Rivers, Gaea.Nodes",
  "Seed": 31128,  // ONLY Seed property!
  "Id": 390,
  "Name": "Rivers",
  "Position": {...},
  "Ports": {...}
}
```

## Key Differences:

1. **SaveDefinition Location**:
   - OURS: Separate at asset level
   - REAL: Embedded in the node that has the export

2. **Property Storage**:
   - OURS: All properties explicitly set
   - REAL: Only non-default properties stored (see tutorial example)

3. **NodeSize/IsMaskable**:
   - OURS: Mixed with Rivers-specific properties
   - REAL: Also mixed, but this seems OK

4. **Property Names**:
   - Both use same names (RiverValleyWidth, RenderSurface - no spaces)

5. **Port Structure**:
   - OURS: 7 ports (In, Out, Rivers, Depth, Surface, Direction, Mask)
   - REAL: 7-8 ports (same + sometimes Headwaters as input port)

## Questions for Analysis:
1. Why is the SaveDefinition placement causing failures?
2. Should we only store non-default property values?
3. Is the port structure exactly right?
4. Are there any other structural differences we're missing?
