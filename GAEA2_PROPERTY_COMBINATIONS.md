# Gaea2 Node Property Combinations

## Summary
Based on analysis of working reference files and testing, certain nodes fail when they have too many properties or invalid property combinations.

## Snow Node Property Rules

### Working Combinations:
1. **Reference combination** (from tut-highMountain.terrain):
   - SettleThaw + Melt (2 properties only)

2. **Single properties** (all work individually):
   - Duration only
   - SnowLine only
   - Melt only
   - MeltType only
   - RealScale only

3. **Small combinations** (2-3 properties max):
   - Duration + SnowLine
   - Duration + SnowLine + Melt

### Failing Combinations:
- Any combination with 8+ properties
- Full property set (10 properties)

## Property Compatibility Matrix

| Property | Works Alone | Compatible With | Incompatible With |
|----------|-------------|-----------------|-------------------|
| Duration | ✓ | SnowLine, Melt | Full set |
| SnowLine | ✓ | Duration, Melt | Full set |
| Melt | ✓ | Duration, SnowLine, SettleThaw | Full set |
| SettleThaw | ✓ | Melt | Unknown |
| MeltType | ✓ | Duration, SnowLine | Full set |
| RealScale | ✓ | Duration, SnowLine | Full set |

## Recommendations

1. **For Snow nodes**: Use maximum 3 properties
2. **Essential properties**: Duration, SnowLine, Melt
3. **Reference-based**: Use SettleThaw + Melt for compatibility

## Other Problematic Nodes

Based on failing templates, these nodes should also have limited properties:
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

## Unit Test Results

- snow_reference_combo: ✓ (2 properties)
- snow_duration_only: ✓ (1 properties)
- snow_snowline_only: ✓ (1 properties)
- snow_basic_combo: ✓ (2 properties)
- snow_with_melt_combo: ✓ (3 properties)
