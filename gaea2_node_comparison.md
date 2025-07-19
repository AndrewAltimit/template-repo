# Gaea2 Node Comparison: Reference Files vs Generated Files

## Key Findings from Reference .terrain Files

### 1. Rivers Node Structure (from Level1.terrain)

```json
"949":{"$id":"50","$type":"QuadSpinner.Gaea.Nodes.Rivers, Gaea.Nodes",
  "Water":0.5,
  "Width":0.8865791,
  "Depth":0.9246184,
  "Downcutting":0.3400796,
  "RiverValleyWidth":"zero",
  "Headwaters":200,
  "RenderSurface":true,
  "Seed":21713,
  "Id":949,
  "Name":"Rivers",
  "NodeSize":"Standard",
  "Position":{"$id":"51","X":25814.795,"Y":26000.443},
  "SaveDefinition":{"$id":"52","Node":949,"Filename":"Rivers","Format":"EXR","IsEnabled":true},
  "Ports":{"$id":"53","$values":[
    {"$id":"54","Name":"In","Type":"PrimaryIn, Required","Record":...},
    {"$id":"55","Name":"Out","Type":"PrimaryOut","IsExporting":true,"Parent":{"$ref":"50"}},
    {"$id":"57","Name":"Headwaters","Type":"In","IsExporting":true,"Parent":{"$ref":"50"}},
    {"$id":"58","Name":"Rivers","Type":"Out","IsExporting":true,"Parent":{"$ref":"50"}},
    {"$id":"59","Name":"Depth","Type":"Out","IsExporting":true,"Parent":{"$ref":"50"}},
    {"$id":"60","Name":"Surface","Type":"Out","IsExporting":true,"Parent":{"$ref":"50"}},
    {"$id":"61","Name":"Direction","Type":"Out","IsExporting":true,"Parent":{"$ref":"50"}},
    {"$id":"62","Name":"Mask","Type":"In","IsExporting":true,"Parent":{"$ref":"50"}}
  ]},
  "IsMaskable":true,
  "Modifiers":{"$id":"63","$values":[]},
  "SnapIns":{"$id":"64","$values":[]}
}
```

### 2. Erosion2 Node Structure (from mountain_landscape_01.terrain)

```json
"611":{"$id":"7","$type":"QuadSpinner.Gaea.Nodes.Erosion2, Gaea.Nodes",
  "Duration":200.0,
  "Downcutting":0.3549525,
  "ErosionScale":3664.8945,
  "Seed":38350,
  "CoarseSedimentsDischargeAmount":0.849545,
  "ShapeSharpness":0.3826497,
  "Id":611,
  "Name":"Erosion2",
  "Position":{"$id":"8","X":27317.092,"Y":26157.076},
  "Ports":{"$id":"9","$values":[
    {"$id":"10","Name":"In","Type":"PrimaryIn, Required","Record":...},
    {"$id":"12","Name":"Out","Type":"PrimaryOut","IsExporting":true,"Parent":{"$ref":"7"}},
    {"$id":"13","Name":"Flow","Type":"Out","IsExporting":true,"Parent":{"$ref":"7"}},
    {"$id":"14","Name":"Wear","Type":"Out","IsExporting":true,"Parent":{"$ref":"7"}},
    {"$id":"15","Name":"Deposits","Type":"Out","IsExporting":true,"Parent":{"$ref":"7"}}
  ]},
  "Modifiers":{"$id":"16","$values":[]}
}
```

### 3. Combine Node Structure (from mountain_landscape_01.terrain)

```json
"870":{"$id":"116","$type":"QuadSpinner.Gaea.Nodes.Combine, Gaea.Nodes",
  "PortCount":2,
  "Mode":"Max",
  "Id":870,
  "Name":"Combine",
  "NodeSize":"Small",
  "Position":{"$id":"117","X":27137.002,"Y":26187.076},
  "Ports":{"$id":"118","$values":[
    {"$id":"119","Name":"In","Type":"PrimaryIn, Required","Record":...},
    {"$id":"121","Name":"Out","Type":"PrimaryOut","IsExporting":true,"Parent":{"$ref":"116"}},
    {"$id":"122","Name":"Input2","Type":"In","Record":...},
    {"$id":"124","Name":"Mask","Type":"In","IsExporting":true,"Parent":{"$ref":"116"}}
  ]},
  "Modifiers":{"$id":"125","$values":[]}
}
```

### 4. Export Node Structure (from traveled_canyon.terrain)

```json
"842":{"$id":"141","$type":"QuadSpinner.Gaea.Nodes.Export, Gaea.Nodes",
  "Format":"PNG64",
  "Id":842,
  "Name":"Texture Eport",
  "NodeSize":"Standard",
  "Position":{"$id":"142","X":30792.006,"Y":26057.076},
  "SaveDefinition":{"$id":"143","Node":842,"Filename":"Heightmap","Format":"EXR","IsEnabled":true,"DisabledInProfiles":{"$id":"144","$values":[]}},
  "Ports":{"$id":"145","$values":[
    {"$id":"146","Name":"In","Type":"PrimaryIn, Required","Record":...},
    {"$id":"148","Name":"Out","Type":"PrimaryOut","IsExporting":true,"Parent":{"$ref":"141"}}
  ]},
  "Modifiers":{"$id":"149","$values":[]}
}
```

## Critical Differences Found

### 1. **Property Names with Spaces**
- Reference files use multi-word properties like `"Rock Softness"`, `"Erosion Scale"`
- Properties are NOT camelCase in the actual files
- Our generated files incorrectly use `"RockSoftness"`, `"ErosionScale"`

### 2. **Additional Node Fields**
- `IsMaskable`: Present on many nodes (Rivers, Combine, etc.)
- `SnapIns`: Empty array field present on nodes
- `SaveDefinition`: Optional field for some nodes
- `RenderIntentOverride`: Present on some nodes

### 3. **Port Structure Differences**
- Each port has `IsExporting: true` field
- Ports have `Parent` field with `{"$ref": "nodeId"}` reference
- Records have `IsValid: true` field

### 4. **Range Object Format**
- Range objects in reference files have their own `$id`:
  ```json
  "Range":{"$id":"57","X":0.35,"Y":0.69}
  ```
- NOT just `{"X":0.35,"Y":0.69}` as we're generating

### 5. **Missing Properties on Rivers Node**
- `RiverValleyWidth`: String property with value like `"zero"`
- `RenderSurface`: Boolean property
- Additional ports: `Headwaters` (In), `Rivers` (Out), `Depth` (Out), `Surface` (Out), `Direction` (Out), `Mask` (In)

### 6. **Node-Specific Fields**
- Some nodes have `Modifiers` array (usually empty)
- Some nodes have `Version` field
- `NodeSize` can be "Small", "Standard", etc.

## Recommendations for Fixing Gaea2 MCP Server

1. **Fix Property Name Mapping**: Update the property name mapping to use spaces instead of camelCase
2. **Add Missing Node Fields**: Include `IsMaskable`, `SnapIns`, `Modifiers` fields
3. **Fix Range Object Format**: Ensure Range objects have their own `$id`
4. **Update Port Definitions**: Add `IsExporting` and proper `Parent` references
5. **Complete Rivers Node**: Add all missing properties and ports
6. **Add Node Metadata**: Include optional fields like `SaveDefinition`, `RenderIntentOverride`

These changes should make the generated .terrain files match the format that Gaea2 expects.
