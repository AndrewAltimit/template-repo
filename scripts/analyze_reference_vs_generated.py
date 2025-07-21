#!/usr/bin/env python3
"""Analyze differences between reference Level1.terrain and our generated output"""

import json


def analyze_volcano_node():
    """Analyze the Volcano node from Level1.terrain"""

    # From Level1.terrain - Volcano node (first node)
    reference_volcano = {
        "$id": "7",
        "$type": "QuadSpinner.Gaea.Nodes.Volcano, Gaea.Nodes",
        "Scale": 1.0131434,
        "Height": 0.5547645,
        "Mouth": 0.85706466,
        "Bulk": -0.1467689,
        "Surface": "Eroded",
        "X": 0.296276,  # <-- X and Y ARE at root level!
        "Y": 0.5,  # <-- This is different from Position X/Y
        "Seed": 44922,
        "Id": 183,  # Integer, not string
        "Name": "Volcano",
        "Position": {
            "$id": "8",
            "X": 24472.023,  # Different from root X
            "Y": 25987.605,  # Different from root Y
        },
    }

    print("CRITICAL DISCOVERY: Volcano node HAS X and Y at root level!")
    print("These appear to be different from Position X/Y:")
    print(f"  Root X: {reference_volcano['X']} (normalized 0-1 range)")
    print(f"  Root Y: {reference_volcano['Y']} (normalized 0-1 range)")
    print(f"  Position X: {reference_volcano['Position']['X']} (canvas coordinates)")
    print(f"  Position Y: {reference_volcano['Position']['Y']} (canvas coordinates)")

    # Check other key format details
    print("\nOther format observations:")
    print(f"  Groups: {{'$id': '205'}} - no $values")
    print(f"  Notes: {{'$id': '206'}} - no $values")
    print(f"  Camera: {{'$id': '219'}} - no properties")
    print(f"  Variables: {{'$id': '212'}} - just $id")

    # Analyze property order in node
    print("\nProperty order in Volcano node:")
    for i, key in enumerate(reference_volcano.keys()):
        print(f"  {i+1}. {key}")

    # Analyze Erosion2 node properties
    erosion2_props = [
        "Duration",
        "Downcutting",
        "ErosionScale",
        "Seed",
        "SuspendedLoadDischargeAmount",
        "SuspendedLoadDischargeAngle",
        "BedLoadDischargeAmount",
        "BedLoadDischargeAngle",
        "CoarseSedimentsDischargeAmount",
        "CoarseSedimentsDischargeAngle",
        "Shape",
        "ShapeSharpness",
        "ShapeDetailScale",
    ]
    print("\nErosion2 specific properties found:")
    for prop in erosion2_props:
        print(f"  - {prop}")

    # Check node ID pattern
    node_ids = [
        183,
        668,
        427,
        281,
        294,
        949,
        483,
        800,
        375,
        245,
        958,
        174,
        258,
        975,
        639,
        514,
        287,
        490,
        340,
    ]
    print(f"\nNode ID pattern: {node_ids[:5]}...")
    print("  Non-sequential, large gaps between IDs")

    # Property name observations
    print("\nProperty names in reference:")
    print("  - CoastalErosion (no space)")
    print("  - ExtraCliffDetails (no space)")
    print("  - RiverValleyWidth (no space)")
    print("  - All properties use PascalCase without spaces")


if __name__ == "__main__":
    analyze_volcano_node()
