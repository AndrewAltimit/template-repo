# Gaea2 File Format Analysis: Why One Works and Another Fails

## Executive Summary

After analyzing the JSON structure of working and failing Gaea2 terrain files, the **critical difference** is:

**The failing file has NO CONNECTIONS between nodes, while working files embed connections as `Record` objects within port definitions.**

## Key Findings

### 1. JSON Formatting (NOT the issue)
- **Failing file**: Pretty-printed (indented)
- **Working files**: Minified (single line)
- **Verdict**: Both formats are valid JSON, formatting is not the issue

### 2. Node IDs (NOT the issue)
- **Simple working file**: Uses ID "1"
- **Complex reference files**: Use IDs like 183, 668, 427, 949, etc.
- **Failing file**: Uses IDs 183, 668, 427
- **Verdict**: Various ID formats work, this is not the issue

### 3. Node Properties (NOT the issue)
- **Simple working file**: No properties
- **Complex reference files**: Have properties (Scale, Height, Duration, etc.)
- **Failing file**: Has properties (Duration, Downcutting, ErosionScale, etc.)
- **Verdict**: Properties are valid and used in working files

### 4. Port Types (NOT the issue)
- **Simple working file**: Uses "PrimaryIn" and "PrimaryOut"
- **Complex reference files**: Use "PrimaryIn, Required" for connected ports
- **Failing file**: Uses "PrimaryIn, Required" for Export node
- **Verdict**: Both port type formats work

### 5. Connections (THIS IS THE ISSUE!)

#### Working Reference File Pattern:
```json
{
  "Name": "In",
  "Type": "PrimaryIn, Required",
  "Record": {
    "$id": "25",
    "From": 949,
    "To": 427,
    "FromPort": "Rivers",
    "ToPort": "In",
    "IsValid": true
  },
  "IsExporting": true,
  "Parent": {"$ref": "21"}
}
```

#### Failing File Pattern:
```json
{
  "Name": "In",
  "Type": "PrimaryIn, Required",
  "IsExporting": true,
  "Parent": {"$ref": "25"}
}
```

**The failing file is missing the `Record` objects that define connections!**

## Detailed Connection Analysis

### How Gaea2 Stores Connections

Unlike the MCP API which has a separate "connections" array, Gaea2 embeds connections directly in port definitions:

1. **Source node** has a regular port (no Record)
2. **Target node** has a port with a `Record` object containing:
   - `From`: Source node ID
   - `To`: Target node ID
   - `FromPort`: Name of the source port
   - `ToPort`: Name of the target port
   - `IsValid`: Always true for valid connections

### Example from Reference File

Node 281 (Combine) receives inputs from two nodes:
```json
"Ports": {
  "$values": [
    {
      "Name": "In",
      "Type": "PrimaryIn, Required",
      "Record": {
        "From": 183,
        "To": 281,
        "FromPort": "Out",
        "ToPort": "In",
        "IsValid": true
      }
    },
    {
      "Name": "Input2",
      "Type": "In",
      "Record": {
        "From": 668,
        "To": 281,
        "FromPort": "Out",
        "ToPort": "Input2",
        "IsValid": true
      }
    }
  ]
}
```

## Why the Simple Working File Works

The simple Mountain-only file works because:
1. It has no connections (single node)
2. Gaea2 can handle unconnected nodes
3. The Mountain node generates terrain independently

## Why the Failing File Fails

The failing file has multiple nodes (Fractal → Erosion2 → Export) but:
1. **NO connections defined between them**
2. Export node has "PrimaryIn, Required" but no Record
3. Gaea2 cannot process the workflow without connections

## Solution

The Gaea2 MCP server needs to:
1. Convert the API's separate "connections" array
2. Embed connections as `Record` objects in the target port definitions
3. Ensure the "Type" includes "Required" for connected ports

## Additional Observations

1. **Range objects** in reference files don't have their own `$id` (contrary to what the failing file shows)
2. **SnapIns** property exists in reference files (missing from failing file)
3. **SaveDefinition** can appear in nodes that export data
4. **Multiple Mask ports** can exist on the same node (see node 174 with 3 Mask ports)

## Conclusion

The Gaea2 MCP server is correctly generating nodes with properties, but it's not properly converting the connection format from the API representation to Gaea2's embedded format. This is why files with connections fail to open while single-node files work.
