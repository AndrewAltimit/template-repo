# Gaea2 Failing Nodes Analysis

## Summary of Findings

Based on analysis of working vs failing terrain files, I've identified specific nodes that cause files to fail to open in Gaea2.

## Working Files
These files successfully open in Gaea2:
- test_minimal_mode.terrain
- test_full_mode.terrain
- test_regression_smart.terrain
- test_smart_mode.terrain
- regression_volcanic_terrain.terrain
- regression_river_valley.terrain
- regression_desert_canyon.terrain
- regression_basic_terrain.terrain

Common nodes in working files:
- Mountain, Erosion2, Volcano, Rivers, Thermal, Canyon, Stratify, Sand, TextureBase, SatMap, Export, FractalTerraces, Sediments, Island, Combine

## Failing Files
These files fail to open in Gaea2:
- regression_volcanic_island.terrain
- regression_mountain_range.terrain
- regression_detailed_mountain.terrain
- regression_coastal_cliffs.terrain
- regression_canyon_system.terrain
- regression_arctic_terrain.terrain

## Problematic Nodes (ONLY in failing files)
The following nodes appear ONLY in files that fail to open:
1. **Snow** - Appears in 3 failing files
2. **Beach** - Appears in 2 failing files
3. **Coast** - Appears in 1 failing file
4. **Lakes** - Appears in 1 failing file
5. **Glacier** - Appears in 1 failing file
6. **SeaLevel** - Appears in 1 failing file
7. **LavaFlow** - Appears in 1 failing file
8. **ThermalShatter** - Appears in 1 failing file
9. **Ridge** - Appears in 1 failing file
10. **Strata** - Appears in 1 failing file
11. **Voronoi** - Appears in 1 failing file
12. **Terrace** - Appears in 1 failing file

## Analysis

### Snow Node (Most Common Problematic Node)
The Snow node appears in 3 failing files with these properties:
```json
{
  "Duration": 0.7-0.9,
  "SnowLine": 0.1-0.75,
  "Melt": 0.0-0.2,
  "Intensity": 0.5,
  "SettleDuration": 0.5,
  "MeltType": "Uniform",
  "MeltRemnants": 0.0,
  "Direction": 0.0,
  "SlipOffAngle": 35.0,
  "RealScale": false
}
```

### Hypothesis
These nodes might be:
1. From a newer version of Gaea2 not supported by the current installation
2. Missing required properties or connections
3. Using incorrect property formats or values
4. Part of a plugin/extension not installed

## Recommended Fix

### Option 1: Remove Problematic Nodes from Templates
Update the templates to remove or replace these nodes:
- Replace Snow with a simple mask-based approach
- Replace Beach/Coast with erosion-based alternatives
- Replace Lakes with depression-based masks
- Remove advanced nodes like LavaFlow, ThermalShatter

### Option 2: Check Node Definitions
These nodes might not be properly defined in our NODE_DEFINITIONS. We should:
1. Verify if these nodes exist in the Gaea2 version being used
2. Check if they require special properties or formats
3. Update NODE_DEFINITIONS if they're missing

### Option 3: Version Compatibility
These nodes might be from Gaea2 v2.0+ while the system uses v1.x:
- Check Gaea2 version compatibility
- Update templates to use only v1.x compatible nodes

## Immediate Action Plan

1. **Update Templates**: Remove problematic nodes from failing templates
2. **Create Alternative Workflows**: Replace advanced nodes with compatible alternatives
3. **Test Fixes**: Verify files open after removing problematic nodes
4. **Document Limitations**: Note which nodes are not supported
