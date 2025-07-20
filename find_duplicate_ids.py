#!/usr/bin/env python3
"""Find where duplicate $id values occur"""

import json


def find_duplicate_ids(data, path="", id_locations=None):
    """Find all locations of $id values"""
    if id_locations is None:
        id_locations = {}

    if isinstance(data, dict):
        if "$id" in data:
            id_val = data["$id"]
            if id_val not in id_locations:
                id_locations[id_val] = []
            id_locations[id_val].append(path)

        for key, value in data.items():
            find_duplicate_ids(value, f"{path}.{key}" if path else key, id_locations)

    elif isinstance(data, list):
        for i, item in enumerate(data):
            find_duplicate_ids(item, f"{path}[{i}]", id_locations)

    return id_locations


def main():
    # Load the failing file
    with open("failing_terrain_new.json", "r") as f:
        data = json.load(f)

    # Find all ID locations
    id_locations = find_duplicate_ids(data)

    # Find duplicates
    print("=== DUPLICATE $ID ANALYSIS ===\n")

    duplicate_count = 0
    for id_val, locations in sorted(id_locations.items(), key=lambda x: int(x[0])):
        if len(locations) > 1:
            duplicate_count += 1
            print(f"$id: {id_val} appears {len(locations)} times:")
            for loc in locations:
                print(f"  - {loc}")
            print()

    print(f"\nTotal duplicate IDs: {duplicate_count}")

    # Show the pattern
    print("\n=== ID ASSIGNMENT PATTERN ===")
    print("\nLooking at the pattern of duplicate IDs:")
    duplicates = ["17", "41", "57", "11", "49", "28"]

    for dup_id in duplicates:
        print(f"\n$id {dup_id}:")
        for loc in id_locations[dup_id]:
            # Extract the context
            parts = loc.split(".")
            if len(parts) > 2:
                context = parts[-3:]
                print(f"  - Context: {'.'.join(context)}")


if __name__ == "__main__":
    main()
