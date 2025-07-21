# Gaea2 Test Files Summary

## Files to Test in Gaea2

### 1. Basic/Minimal Files (Should Work)
- **`test_minimal_mountain.json`** ✓ Already confirmed working
  - Single Mountain node
  - No properties
  - No Export node
  - Simple ID: "1"

### 2. Fixed Regression Test (Should Work Now)
- **`test_fixed_regression.json`** - The previously failing configuration with fixes applied
  - 5 nodes: Mountain → Erosion2 → TextureBase → SatMap → Export
  - Node IDs: 100-104
  - Export node has NO Format property (fixed)
  - Erosion2 using proper Duration defaults
  - All connections present

### 3. Template Test (Should Work)
- **`test_fixed_template.json`** - Basic terrain template with fixes
  - Generated from 'basic_terrain' template
  - Should have proper Export node handling

### 4. Alternative Configurations (For Comparison)
- **`test_no_export.json`** - Complex project without Export node
  - 3 nodes: Mountain → Erosion2 → SatMap
  - Simple IDs: 1,2,3
  - Properties on all nodes
  - NO Export node

- **`test_export_format_fixed.json`** - Manual fix test
  - Same as regression but with Duration=0.15 explicitly set

## What Was Fixed

1. **Export Node Format Conflict**
   - Removed Format property from node level
   - Only SaveDefinition.Format remains
   - Case-insensitive property handling

2. **Erosion2 Duration**
   - Default increased: 0.04 → 0.15
   - Range extended: max 0.15 → 2.0
   - Templates updated: 0.02-0.06 → 0.10-0.20

3. **Export Node Auto-Addition**
   - Disabled in error recovery
   - Templates still add Export nodes but without conflicts

## Expected Results

The `test_fixed_regression.json` file should now open successfully in Gaea2, as it has:
- ✓ Proper connection structure
- ✓ No Format property conflicts
- ✓ Reasonable Duration values
- ✓ Valid node properties (X,Y are valid terrain parameters)

If this file opens, it confirms our diagnosis and fixes were correct!
