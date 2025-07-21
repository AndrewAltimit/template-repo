# Gaea2 Property Limitation Fix

## Problem Summary

Certain Gaea2 templates fail to open due to specific nodes having too many properties. Through extensive testing, we discovered that nodes like Snow, Beach, Coast, etc. fail when they have 8+ properties but work fine with 1-3 properties.

## Root Cause

The issue is NOT about specific property incompatibility, but rather the total number of properties on certain node types. Reference files from working Gaea2 projects show these nodes typically have 0-3 properties maximum.

## Affected Nodes

The following nodes must have LIMITED properties (max 3):
- **Snow** - Most problematic, appears in 3 failing templates
- Beach
- Coast
- Lakes
- Glacier
- SeaLevel
- LavaFlow
- ThermalShatter
- Ridge
- Strata
- Voronoi
- Terrace

## Solution Implemented

### 1. Server Code Changes (gaea2_mcp_server.py)

Added property limitation logic in the `smart` property mode:

```python
# In property_mode == "smart" block:

# Nodes that fail with too many properties
limited_property_nodes = [
    'Snow', 'Beach', 'Coast', 'Lakes', 'Glacier', 'SeaLevel',
    'LavaFlow', 'ThermalShatter', 'Ridge', 'Strata', 'Voronoi', 'Terrace'
]

if node_type in limited_property_nodes:
    # These nodes can only have limited properties (max 3)
    essential_props = {
        'Snow': ['Duration', 'SnowLine', 'Melt'],
        'Beach': ['Width', 'Slope'],
        'Coast': ['Erosion', 'Detail'],
        # ... etc
    }

    # Only include essential properties
    node_essentials = essential_props.get(node_type, [])
    properties = {}

    for prop in node_essentials:
        if prop in raw_properties:
            properties[prop] = raw_properties[prop]

    # Limit to max 3 properties
    if len(properties) > 3:
        properties = dict(list(properties.items())[:3])
```

### 2. Template Mode Change

Changed templates from using `property_mode="full"` to `property_mode="smart"` so the limitation logic is applied.

## Test Results

### Working Property Combinations for Snow:
- **0 properties**: ✅ Works
- **1 property** (Duration only): ✅ Works
- **1 property** (SnowLine only): ✅ Works
- **2 properties** (Duration + SnowLine): ✅ Works
- **3 properties** (Duration + SnowLine + Melt): ✅ Works
- **8+ properties**: ❌ Fails to open
- **10 properties** (full set): ❌ Fails to open

### Reference File Evidence
From `tut-highMountain.terrain` (working file):
- Snow node has only 2 properties: `SettleThaw` and `Melt`

## Templates Fixed

The following templates that were failing should now work:
1. arctic_terrain
2. mountain_range
3. detailed_mountain
4. coastal_cliffs
5. canyon_system
6. volcanic_island

## Important Notes

1. **Server Update Required**: The Gaea2 MCP server needs to be restarted with the latest code for the fix to take effect.

2. **Property Count Matters**: The issue is about the NUMBER of properties, not specific property values or combinations.

3. **Essential Properties**: Each problematic node has 2-3 essential properties defined. Only these are included when using smart mode.

4. **Backwards Compatibility**: This change only affects nodes in the `limited_property_nodes` list. Other nodes continue to work as before.

## Verification

To verify the fix is working:
1. Check that Snow nodes have max 3 properties
2. Check that Lakes, Glacier nodes have max 2-3 properties
3. Test that previously failing templates now open in Gaea2

## Future Improvements

1. Investigate why Gaea2 has this limitation on certain nodes
2. Consider making property limits configurable
3. Add warnings when users try to add too many properties to limited nodes
