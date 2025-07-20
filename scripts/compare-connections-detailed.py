#!/usr/bin/env python3
"""
Detailed comparison of expected vs actual connections
"""

# Expected connections from our test
expected = [
    (183, 281, "Out", "In"),
    (668, 281, "Out", "Input2"),
    (281, 294, "Out", "In"),
    (294, 639, "Out", "In"),
    (639, 975, "Out", "In"),
    (975, 514, "Out", "In"),
    (514, 949, "Out", "In"),
    (949, 287, "Out", "In"),
    (949, 427, "Rivers", "In"),
    (287, 483, "Out", "In"),
    (483, 800, "Out", "In"),
    (483, 375, "Out", "In"),
    (483, 340, "Out", "In"),
    (483, 258, "Out", "In"),
    (800, 245, "Out", "In"),
    (375, 245, "Out", "Input2"),
    (427, 245, "Out", "Mask"),
    (245, 490, "Out", "In"),
    (340, 490, "Out", "Input2"),
    (287, 490, "Water", "Mask"),
    (287, 958, "Out", "In"),
    (490, 174, "Out", "In"),
    (258, 174, "Out", "Input2"),
    (958, 174, "Out", "Mask"),
]

# Actual connections found
actual = [
    (183, 281, "Out", "In"),
    (245, 490, "Out", "In"),
    (281, 294, "Out", "In"),
    (287, 490, "Water", "Mask"),
    (294, 639, "Out", "In"),
    (375, 245, "Out", "Input2"),
    (427, 245, "Out", "Mask"),
    (483, 258, "Out", "In"),
    (483, 340, "Out", "In"),
    (483, 375, "Out", "In"),
    (483, 800, "Out", "In"),
    (668, 281, "Out", "Input2"),
    (800, 245, "Out", "In"),
    (949, 287, "Out", "In"),
    (958, 174, "Out", "Mask"),
    (975, 514, "Out", "In"),
]

expected_set = set(expected)
actual_set = set(actual)

print(f"Expected: {len(expected)} connections")
print(f"Actual: {len(actual)} connections")
print()

missing = expected_set - actual_set
print(f"Missing {len(missing)} connections:")
for conn in sorted(missing):
    print(f"  {conn[0]} -> {conn[1]} ({conn[2]} -> {conn[3]})")

print()

# Group missing by target node
missing_by_target = {}
for conn in missing:
    target = conn[1]
    if target not in missing_by_target:
        missing_by_target[target] = []
    missing_by_target[target].append(conn)

print("Missing connections grouped by target node:")
for target, conns in sorted(missing_by_target.items()):
    print(f"\n  Node {target}:")
    for conn in conns:
        print(f"    <- {conn[0]} ({conn[2]} -> {conn[3]})")
