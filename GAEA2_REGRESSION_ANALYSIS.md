# Gaea2 Regression Test Failure Analysis

## Summary

The regression test (`test_fixed_regression.terrain`) fails because it's missing critical node properties that templates automatically add.

## Root Cause

1. **Templates use `apply_default_properties()`** which adds all missing properties from `NODE_PROPERTY_DEFINITIONS`
2. **Direct project creation doesn't add defaults** (we disabled this to fix the simple Mountain case)
3. **Erosion2 nodes require many properties** to function correctly

## Key Differences Found

### Working Template File:
- Erosion2 has **13 properties** including:
  - Duration: 0.15
  - All discharge properties (BedLoad, CoarseSediments, SuspendedLoad)
  - Shape properties (Shape, ShapeDetailScale, ShapeSharpness)
- Export SaveDefinition.Format: **EXR**

### Failing Regression File:
- Erosion2 has only **3 properties**:
  - Downcutting: 0.3
  - ErosionScale: 5000.0
  - Seed: 12345
  - **MISSING: Duration and 10 other properties**
- Export SaveDefinition.Format: **PNG**

## The Dilemma

We face a conflict between two use cases:

1. **Simple nodes** (like a single Mountain) work best with NO properties
2. **Complex nodes** (like Erosion2) REQUIRE many properties to function

## Solution Options

### Option 1: Smart Property Addition (Recommended)
- Add a parameter to control property behavior:
  ```python
  create_gaea2_project(
      ...,
      property_mode="minimal"  # or "full" or "template"
  )
  ```
- "minimal": No default properties (current behavior)
- "full": Add all default properties from NODE_PROPERTY_DEFINITIONS
- "template": Only for template-based creation

### Option 2: Node-Specific Logic
- Simple nodes (Mountain, Primitive): No defaults
- Complex nodes (Erosion2, Rivers): Add required defaults
- Based on node complexity/category

### Option 3: Fix Only Critical Properties
- Always add Duration to Erosion2 (it's required)
- Keep other properties optional
- Change Export format default to EXR

## Immediate Fix

For the failing test to work, either:
1. Add all missing Erosion2 properties manually
2. Enable default property addition for Erosion2
3. Use the template system instead of direct creation
